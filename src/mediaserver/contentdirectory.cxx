/* Copyright (C) 2016 J.F.Dockes
 *	 This program is free software; you can redistribute it and/or modify
 *	 it under the terms of the GNU General Public License as published by
 *	 the Free Software Foundation; either version 2 of the License, or
 *	 (at your option) any later version.
 *
 *	 This program is distributed in the hope that it will be useful,
 *	 but WITHOUT ANY WARRANTY; without even the implied warranty of
 *	 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *	 GNU General Public License for more details.
 *
 *	 You should have received a copy of the GNU General Public License
 *	 along with this program; if not, write to the
 *	 Free Software Foundation, Inc.,
 *	 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#include "contentdirectory.hxx"

#include <upnp/upnp.h>

#include <functional>
#include <iostream>
#include <map>
#include <utility>
#include <unordered_map>
#include <sstream>

#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"
#include "libupnpp/device/device.hxx"

#include "pathut.h"
#include "smallut.h"
#include "upmpdutils.hxx"
#include "main.hxx"
#include "cdplugins/plgwithslave.hxx"
#include "conftree.h"

using namespace std;
using namespace std::placeholders;
using namespace UPnPProvider;

class ContentDirectory::Internal {
public:
    Internal (ContentDirectory *sv, MediaServer *dv)
	: service(sv), msdev(dv), updateID("1") { }

    ~Internal() {
	for (auto& it : plugins) {
	    delete it.second;
	}
    }

    // Start plugins which have long init so that the user has less to
    // wait on first access
    void maybeStartSomePlugins(bool enabled);
    CDPlugin *pluginFactory(const string& appname) {
	LOGDEB("ContentDirectory::pluginFactory: for " << appname << endl);

	if (host.empty()) {
	    UpnpDevice *dev;
	    if (!service || !(dev = service->getDevice())) {
		LOGERR("ContentDirectory::Internal: no service or dev ??\n");
		return nullptr;
	    }
	    unsigned short usport;
	    if (!dev->ipv4(&host, &usport)) {
		LOGERR("ContentDirectory::Internal: can't get server IP\n");
		return nullptr;
	    }
            port = usport;
	    LOGDEB("ContentDirectory: host "<< host<< " port " << port << endl);
	}
        return new PlgWithSlave(appname, service);
    }
    CDPlugin *pluginForApp(const string& appname) {
	auto it = plugins.find(appname);
	if (it != plugins.end()) {
	    return it->second;
	} else {
	    CDPlugin *plug = pluginFactory(appname);
	    if (plug) {
		plugins[appname] = plug;
	    }
	    return plug;
	}
    }

    ContentDirectory *service;
    MediaServer *msdev;
    unordered_map<string, CDPlugin *> plugins;
    string host;
    int port;
    string updateID;
};

static const string
sTpContentDirectory("urn:schemas-upnp-org:service:ContentDirectory:1");
static const string
sIdContentDirectory("urn:upnp-org:serviceId:ContentDirectory");

ContentDirectory::ContentDirectory(MediaServer *dev, bool enabled)
    : UpnpService(sTpContentDirectory, sIdContentDirectory,
                  "ContentDirectory.xml", dev),
      m(new Internal(this, dev))
{
    dev->addActionMapping(
        this, "GetSearchCapabilities",
        bind(&ContentDirectory::actGetSearchCapabilities, this, _1, _2));
    dev->addActionMapping(
        this, "GetSortCapabilities",
        bind(&ContentDirectory::actGetSortCapabilities, this, _1, _2));
    dev->addActionMapping(
        this, "GetSystemUpdateID",
        bind(&ContentDirectory::actGetSystemUpdateID, this, _1, _2));
    dev->addActionMapping(
        this, "Browse",
        bind(&ContentDirectory::actBrowse, this, _1, _2));
    dev->addActionMapping(
        this, "Search",
        bind(&ContentDirectory::actSearch, this, _1, _2));
    m->maybeStartSomePlugins(enabled);
}

ContentDirectory::~ContentDirectory()
{
    delete m;
}

int ContentDirectory::actGetSearchCapabilities(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("ContentDirectory::actGetSearchCapabilities: " << endl);

    std::string out_SearchCaps(
        "upnp:class,upnp:artist,dc:creator,upnp:album,dc:title");
    data.addarg("SearchCaps", out_SearchCaps);
    return UPNP_E_SUCCESS;
}

int ContentDirectory::actGetSortCapabilities(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("ContentDirectory::actGetSortCapabilities: " << endl);

    std::string out_SortCaps;
    data.addarg("SortCaps", out_SortCaps);
    return UPNP_E_SUCCESS;
}

int ContentDirectory::actGetSystemUpdateID(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("ContentDirectory::actGetSystemUpdateID: " << endl);

    std::string out_Id = m->updateID;
    data.addarg("Id", out_Id);
    return UPNP_E_SUCCESS;
}

static vector<UpSong> rootdir;
static bool makerootdir()
{
    rootdir.clear();
    string pathplg = path_cat(g_datadir, "cdplugins");
    string reason;
    set<string> entries;
    if (!readdir(pathplg, reason, entries)) {
        LOGERR("ContentDirectory::makerootdir: can't read " << pathplg <<
               " : " << reason << endl);
        return false;
    }

    for (const auto& entry : entries) {
        if (!entry.compare("pycommon")) {
            continue;
        }
        string userkey = entry + "user";
        string autostartkey = entry + "autostart";
        if (!g_config->hasNameAnywhere(userkey) &&
            !g_config->hasNameAnywhere(autostartkey)) {
            LOGINF("ContentDirectory: not creating entry for " << entry <<
                   " because neither " << userkey << " nor " << autostartkey <<
                   " are defined in the configuration\n");
            continue;
        }

        // If the title parameter is not defined in the configuration,
        // we compute a title (to be displayed in the root directory)
        // from the plugin name.
        string title;
        if (!g_config->get(entry + "title", title)) {
            title = stringtoupper((const string&)entry.substr(0,1)) +
                entry.substr(1, entry.size()-1);
        }
        rootdir.push_back(UpSong::container("0$" + entry + "$", "0", title));
    }

    if (rootdir.empty()) {
        // This should not happen, as we only start the CD if services
        // are configured !
        rootdir.push_back(UpSong::item("0$none$", "0", "No services found"));
        return false;
    } else {
        return true;
    }
}

bool ContentDirectory::mediaServerNeeded()
{
    return makerootdir();
}

// Returns totalmatches
static size_t readroot(int offs, int cnt, vector<UpSong>& out)
{
    //LOGDEB("readroot: offs " << offs << " cnt " << cnt << endl);
    if (rootdir.empty()) {
	makerootdir();
    }
    out.clear();
    if (cnt <= 0)
        cnt = rootdir.size();
    
    if (offs < 0 || cnt <= 0) {
	return rootdir.size();
    }
	
    for (int i = 0; i < cnt; i++) {
	if (size_t(offs + i) < rootdir.size()) {
	    out.push_back(rootdir[offs + i]);
	} else {
	    break;
	}
    }
    //LOGDEB("readroot: returning " << out.size() << " entries\n");
    return rootdir.size();
}

static string appForId(const string& id)
{
    string app;
    string::size_type dol0 = id.find_first_of("$");
    if (dol0 == string::npos) {
	LOGERR("ContentDirectory::appForId: bad id [" << id << "]\n");
	return string();
    } 
    string::size_type dol1 = id.find_first_of("$", dol0 + 1);
    if (dol1 == string::npos) {
	LOGERR("ContentDirectory::appForId: bad id [" << id << "]\n");
	return string();
    } 
    return id.substr(dol0 + 1, dol1 - dol0 -1);
}


void ContentDirectory::Internal::maybeStartSomePlugins(bool enabled)
{
    // If enabled is false, no service is locally enabled, we are
    // working for ohcredentials. In the previous version, we
    // explicitely started the microhttpd daemon in this case (only as
    // we'll need it before any plugin is created.
    //
    // The problem was that, if we do have plugins enabled (and not
    // autostarted) but the first access is through OHCredentials, the
    // microhttp server will not be running and the connection from
    // the renderer will fail. Could not find a way to fix this. We'd
    // need to trigger the proxy start from the credentials service
    // (in the other process!) on first access. So just always run the
    // Proxy. Only inconvenient is that it opens one more port. 
    // This is rather messy.
    PlgWithSlave::maybeStartProxy(this->service);
    
    for (auto& entry : rootdir) {
        string app = appForId(entry.id);
        string sas;
        if (g_config->get(app + "autostart", sas) && stringToBool(sas)) {
            LOGDEB0("ContentDirectory::Internal::maybeStartSomePlugins: "
                    "starting " << app << endl);
            CDPlugin *p = pluginForApp(app);
            if (p) {
                p->startInit();
            }
        }
    }
}

// Really preposterous: bubble (and maybe others) searches in root,
// but we can't do this. So memorize the last browsed object ID and
// use this as a replacement when root search is requested. Forget
// about multiaccess, god forbid multithreading etc. Will work in most
// cases though :)
static string last_objid;

int ContentDirectory::actBrowse(const SoapIncoming& sc, SoapOutgoing& data)
{
    bool ok = false;
    std::string in_ObjectID;
    ok = sc.get("ObjectID", &in_ObjectID);
    if (!ok) {
        LOGERR("ContentDirectory::actBrowse: no ObjectID in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    std::string in_BrowseFlag;
    ok = sc.get("BrowseFlag", &in_BrowseFlag);
    if (!ok) {
        LOGERR("ContentDirectory::actBrowse: no BrowseFlag in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    std::string in_Filter;
    ok = sc.get("Filter", &in_Filter);
    if (!ok) {
        LOGERR("ContentDirectory::actBrowse: no Filter in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    int in_StartingIndex;
    ok = sc.get("StartingIndex", &in_StartingIndex);
    if (!ok) {
        LOGERR("ContentDirectory::actBrowse: no StartingIndex in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    int in_RequestedCount;
    ok = sc.get("RequestedCount", &in_RequestedCount);
    if (!ok) {
        LOGERR("ContentDirectory::actBrowse: no RequestedCount in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    std::string in_SortCriteria;
    ok = sc.get("SortCriteria", &in_SortCriteria);
    if (!ok) {
        LOGERR("ContentDirectory::actBrowse: no SortCriteria in params\n");
        return UPNP_E_INVALID_PARAM;
    }

    LOGDEB("ContentDirectory::actBrowse: " << " ObjectID " << in_ObjectID <<
	   " BrowseFlag " << in_BrowseFlag << " Filter " << in_Filter <<
	   " StartingIndex " << in_StartingIndex <<
	   " RequestedCount " << in_RequestedCount <<
	   " SortCriteria " << in_SortCriteria << endl);

    last_objid = in_ObjectID;
    
    vector<string> sortcrits;
    stringToStrings(in_SortCriteria, sortcrits);

    CDPlugin::BrowseFlag bf;
    if (!in_BrowseFlag.compare("BrowseMetadata")) {
	bf = CDPlugin::BFMeta;
    } else {
	bf = CDPlugin::BFChildren;
    }
    std::string out_Result;
    std::string out_NumberReturned;
    std::string out_TotalMatches;
    std::string out_UpdateID;

    // Go fetch
    vector<UpSong> entries;
    size_t totalmatches = 0;
    if (!in_ObjectID.compare("0")) {
	// Root directory: we do this ourselves
	totalmatches = readroot(in_StartingIndex, in_RequestedCount, entries);
    } else {
	// Pass off request to appropriate app, defined by 1st elt in id
	string app = appForId(in_ObjectID);
	CDPlugin *plg = m->pluginForApp(app);
	if (plg) {
	    totalmatches = plg->browse(in_ObjectID, in_StartingIndex,
                                       in_RequestedCount, entries,
                                       sortcrits, bf);
	} else {
	    LOGERR("ContentDirectory::Browse: unknown app: [" << app << "]\n");
            return UPNP_E_INVALID_PARAM;
	}
    }

    // Process and send out result
    out_NumberReturned = ulltodecstr(entries.size());
    out_TotalMatches = ulltodecstr(totalmatches);
    out_UpdateID = m->updateID;
    out_Result = headDIDL();
    for (unsigned int i = 0; i < entries.size(); i++) {
	out_Result += entries[i].didl();
    } 
    out_Result += tailDIDL();
    LOGDEB1("ContentDirectory::Browse: didl: " << out_Result << endl);
    
    data.addarg("Result", out_Result);
    LOGDEB1("ContentDirectory::actBrowse: result [" << out_Result << "]\n");
    data.addarg("NumberReturned", out_NumberReturned);
    data.addarg("TotalMatches", out_TotalMatches);
    data.addarg("UpdateID", out_UpdateID);
    return UPNP_E_SUCCESS;
}

int ContentDirectory::actSearch(const SoapIncoming& sc, SoapOutgoing& data)
{
    bool ok = false;
    std::string in_ContainerID;
    ok = sc.get("ContainerID", &in_ContainerID);
    if (!ok) {
        LOGERR("ContentDirectory::actSearch: no ContainerID in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    std::string in_SearchCriteria;
    ok = sc.get("SearchCriteria", &in_SearchCriteria);
    if (!ok) {
        LOGERR("ContentDirectory::actSearch: no SearchCriteria in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    std::string in_Filter;
    ok = sc.get("Filter", &in_Filter);
    if (!ok) {
        LOGERR("ContentDirectory::actSearch: no Filter in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    int in_StartingIndex;
    ok = sc.get("StartingIndex", &in_StartingIndex);
    if (!ok) {
        LOGERR("ContentDirectory::actSearch: no StartingIndex in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    int in_RequestedCount;
    ok = sc.get("RequestedCount", &in_RequestedCount);
    if (!ok) {
        LOGERR("ContentDirectory::actSearch: no RequestedCount in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    std::string in_SortCriteria;
    ok = sc.get("SortCriteria", &in_SortCriteria);
    if (!ok) {
        LOGERR("ContentDirectory::actSearch: no SortCriteria in params\n");
        return UPNP_E_INVALID_PARAM;
    }

    LOGDEB("ContentDirectory::actSearch: " <<
	   " ContainerID " << in_ContainerID <<
	   " SearchCriteria " << in_SearchCriteria <<
	   " Filter " << in_Filter << " StartingIndex " << in_StartingIndex <<
	   " RequestedCount " << in_RequestedCount <<
	   " SortCriteria " << in_SortCriteria << endl);

    vector<string> sortcrits;
    stringToStrings(in_SortCriteria, sortcrits);

    std::string out_Result;
    std::string out_NumberReturned = "0";
    std::string out_TotalMatches = "0";
    std::string out_UpdateID;

    // Go fetch
    vector<UpSong> entries;
    size_t totalmatches = 0;
    if (!in_ContainerID.compare("0")) {
	// Root directory: can't search in there: we don't know what
	// plugin to pass the search to. Substitute last browsed. Yes
	// it does break in multiuser mode, and yes it's preposterous.
	LOGERR("ContentDirectory::actSearch: Can't search in root. "
               "Substituting last browsed container\n");
        in_ContainerID = last_objid;
    }

    // Pass off request to appropriate app, defined by 1st elt in id
    string app = appForId(in_ContainerID);
    CDPlugin *plg = m->pluginForApp(app);
    if (plg) {
        totalmatches = plg->search(in_ContainerID, in_StartingIndex,
                                   in_RequestedCount, in_SearchCriteria,
                                   entries, sortcrits);
    } else {
        LOGERR("ContentDirectory::Search: unknown app: [" << app << "]\n");
        return UPNP_E_INVALID_PARAM;
    }

    // Process and send out result
    out_NumberReturned = ulltodecstr(entries.size());
    out_TotalMatches = ulltodecstr(totalmatches);
    out_UpdateID = m->updateID;
    out_Result = headDIDL();
    for (unsigned int i = 0; i < entries.size(); i++) {
	out_Result += entries[i].didl();
    } 
    out_Result += tailDIDL();
    
    data.addarg("Result", out_Result);
    data.addarg("NumberReturned", out_NumberReturned);
    data.addarg("TotalMatches", out_TotalMatches);
    data.addarg("UpdateID", out_UpdateID);
    return UPNP_E_SUCCESS;
}

static string firstpathelt(const string& path)
{
    // The parameter is normally a path, but make this work with an URL too
    string::size_type pos = path.find("://");
    if (pos != string::npos) {
        pos += 3;
        pos = path.find("/", pos);
    } else {
        pos = 0;
    }
    pos = path.find_first_not_of("/", pos);
    if (pos == string::npos) {
        return string();
    }
    string::size_type epos = path.find_first_of("/", pos);
    if (epos != string::npos) {
        return path.substr(pos, epos -pos);
    } else {
        return path.substr(pos);
    }
}

CDPlugin *ContentDirectory::getpluginforpath(const string& path)
{
    string app = firstpathelt(path);
    return m->pluginForApp(app);
}

std::string ContentDirectory::getupnpaddr(CDPlugin *)
{
    return m->host;
}


int ContentDirectory::getupnpport(CDPlugin *)
{
    return m->port;
}

std::string ContentDirectory::getfname()
{
    return m->msdev->getfname();
}

bool CDPluginServices::config_get(const string& nm, string& val)
{
    if (nullptr == g_config) {
        return false;
    }
    return g_config->get(nm, val);
}

int CDPluginServices::microhttpport()
{
    int port = 49149;
    string sport;
    if (g_config->get("plgmicrohttpport", sport)) {
        port = atoi(sport.c_str());
    }
    return port;
}


