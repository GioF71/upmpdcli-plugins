/* Copyright (C) 2016-2023 J.F.Dockes
 *       This program is free software; you can redistribute it and/or modify
 *       it under the terms of the GNU Lesser General Public License as published by
 *       the Free Software Foundation; either version 2.1 of the License, or
 *       (at your option) any later version.
 *
 *       This program is distributed in the hope that it will be useful,
 *       but WITHOUT ANY WARRANTY; without even the implied warranty of
 *       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *       GNU Lesser General Public License for more details.
 *
 *       You should have received a copy of the GNU Lesser General Public License
 *       along with this program; if not, write to the
 *       Free Software Foundation, Inc.,
 *       59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#include "config.h"

#include "contentdirectory.hxx"

#include <functional>
#include <utility>
#include <unordered_map>

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
        : service(sv), msdev(dv), updateID("1") {}

    ~Internal() {
        for (auto& it : plugins) {
            delete it.second;
        }
    }

    // Start plugins which have long init so that the user has less to wait on first access
    void maybeStartSomePlugins(bool enabled);

    void maybeInit() {
        if (upnphost.empty()) {
            UpnpDevice *dev;
            if (!service || !(dev = service->getDevice())) {
                LOGERR("ContentDirectory::Internal: no service or dev ??\n");
                return;
            }
            unsigned short usport;
            if (!dev->ipv4(&upnphost, &usport)) {
                LOGERR("ContentDirectory::Internal: can't get server IP\n");
                return;
            }
            upnpport = usport;
            getOptionValue("msrootalias", rootalias);
            LOGDEB("ContentDirectory: upnphost ["<< upnphost << "] upnpport [" << upnpport <<
                   "] rootalias [" << rootalias << "]\n");
        }
    }
    
    CDPlugin *pluginFactory(const string& appname) {
        LOGDEB("ContentDirectory::pluginFactory: for " << appname << "\n");
        maybeInit();
        return new PlgWithSlave(appname, service);
    }

    CDPlugin *pluginForApp(const string& appname) {
        auto it = plugins.find(appname);
        if (it != plugins.end()) {
            return it->second;
        } else {
            return plugins[appname] = pluginFactory(appname);
        }
    }

    ContentDirectory *service;
    MediaServer *msdev;
    unordered_map<string, CDPlugin *> plugins;
    string upnphost;
    int upnpport;
    string rootalias;
    string updateID;
};

static const string sTpContentDirectory("urn:schemas-upnp-org:service:ContentDirectory:1");
static const string sIdContentDirectory("urn:upnp-org:serviceId:ContentDirectory");

ContentDirectory::ContentDirectory(MediaServer *dev, bool enabled)
    : UpnpService(sTpContentDirectory, sIdContentDirectory, "ContentDirectory.xml", dev),
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
    LOGDEB("ContentDirectory::actGetSearchCapabilities: " << "\n");

    std::string out_SearchCaps("upnp:class,upnp:artist,dc:creator,upnp:album,dc:title");
    data.addarg("SearchCaps", out_SearchCaps);
    return UPNP_E_SUCCESS;
}

int ContentDirectory::actGetSortCapabilities(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("ContentDirectory::actGetSortCapabilities: " << "\n");

    std::string out_SortCaps;
    data.addarg("SortCaps", out_SortCaps);
    return UPNP_E_SUCCESS;
}

int ContentDirectory::actGetSystemUpdateID(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("ContentDirectory::actGetSystemUpdateID: " << "\n");

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
    if (!listdir(pathplg, reason, entries)) {
        LOGERR("ContentDirectory::makerootdir: can't read " << pathplg << " : " << reason << "\n");
        return false;
    }

    for (const auto& entry : entries) {
        if (!entry.compare("pycommon")) {
            continue;
        }
        string userkey = entry + "user";
        string autostartkey = entry + "autostart";
        std::string v;
        if (!getOptionValue(userkey, v) && !getOptionValue(autostartkey, v)) {
            LOGINF("ContentDirectory: not creating entry for " << entry <<
                   " because neither " << userkey << " nor " << autostartkey <<
                   " are defined in the configuration\n");
            continue;
        }

        // If the title parameter is not defined in the configuration,
        // we compute a title (to be displayed in the root directory)
        // from the plugin name.
        string title;
        if (!getOptionValue(entry + "title", title)) {
            title = stringtoupper((const string&)entry.substr(0, 1)) +
                entry.substr(1, entry.size() - 1);
        }
        rootdir.push_back(UpSong::container("0$" + entry + "$", "0", title));
    }

    if (rootdir.empty()) {
        // Just as a precaution. The rootdir should never be used in this case because the media
        // server will not be started.
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
    //LOGDEB("readroot: offs " << offs << " cnt " << cnt << "\n");
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

std::string CDPluginServices::pluginRootFromObjid(const std::string& objid)
{
    auto app = appForId(objid);
    if (app.empty()) { // ??
        return "0";
    } 
    return std::string("0$") + app + "$";
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
        if (getBoolOptionValue(app + "autostart", false)) {
            LOGDEB0("ContentDirectory::Internal::maybeStartSomePlugins: starting " << app << "\n");
            CDPlugin *p = pluginForApp(app);
            if (p) {
                p->startInit();
            }
        }
    }
}

// Really preposterous: bubble (and maybe others) searches in root, but we can't do this. So
// memorize the last browsed object ID and use this as a replacement when root search is
// requested. Forget about multiaccess, god forbid multithreading etc. Will work in most cases
// though :)
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
    if (!m->rootalias.empty() && in_ObjectID.find(m->rootalias) != 0) {
        in_ObjectID = m->rootalias + in_ObjectID.substr(1);
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
           " SortCriteria " << in_SortCriteria << "\n");

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
        if (bf == CDPlugin::BFChildren) {
            totalmatches = readroot(in_StartingIndex, in_RequestedCount, entries);
        } else {
            entries.push_back(UpSong::container("0", "0", ""));
            totalmatches = 1;
        }
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
    LOGDEB1("ContentDirectory::Browse: didl: " << out_Result << "\n");
    
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
    if (!m->rootalias.empty() && in_ContainerID.find(m->rootalias) != 0) {
        in_ContainerID = m->rootalias + in_ContainerID.substr(1);
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
           " SortCriteria " << in_SortCriteria << "\n");

    vector<string> sortcrits;
    stringToStrings(in_SortCriteria, sortcrits);

    std::string out_Result;
    std::string out_NumberReturned = "0";
    std::string out_TotalMatches = "0";
    std::string out_UpdateID;

    // Go fetch
    vector<UpSong> entries;
    size_t totalmatches = 0;
    if (in_ContainerID == "0") {
        // Root directory: can't search in there: we don't know what plugin to pass the search to
        // (and we don't want to search all). Substitute last browsed. Yes it does break in
        // multiuser mode, and yes it's preposterous.
        in_ContainerID = pluginRootFromObjid(last_objid);
        if (in_ContainerID == "0") {
            LOGERR("ContentDirectory::actSearch: CP requested search in root and could not find "
                   "plugin from last browsed container\n");
            // Fallthrough, appForId is going to fail just below.
        } else {
            LOGINF("ContentDirectory::actSearch: CP requested search in global root: substituting "
                   "plugin root [" << in_ContainerID << "] from last browsed container\n");
        }
    }

    // Pass off request to appropriate app, defined by 1st elt in id
    string app = appForId(in_ContainerID);
    CDPlugin *plg = m->pluginForApp(app);
    if (plg) {
        totalmatches = plg->search(in_ContainerID, in_StartingIndex,
                                   in_RequestedCount, in_SearchCriteria, entries, sortcrits);
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
        LOGDEB1("Search result title: " << entries[i].title << "\n");
        out_Result += entries[i].didl();
    } 
    out_Result += tailDIDL();
    
    data.addarg("Result", out_Result);
    data.addarg("NumberReturned", out_NumberReturned);
    data.addarg("TotalMatches", out_TotalMatches);
    data.addarg("UpdateID", out_UpdateID);
    LOGDEB0("ContentDirectory::actSearch: " << " SearchCriteria " << in_SearchCriteria <<
            " returns " << out_NumberReturned << " results\n");
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

std::string ContentDirectory::getupnpaddr()
{
    return m->upnphost;
}


int ContentDirectory::getupnpport()
{
    return m->upnpport;
}

std::string ContentDirectory::getfname()
{
    return m->msdev->getfname();
}

// Note that this is not needed by ohcredentials (the slave script does not generate URLs in this
// case, and the mhttp servers listens on all addresses).
string ContentDirectory::microhttphost()
{
    string host;
    if (getOptionValue("plgmicrohttphost", host) && !host.empty()) {
        LOGDEB("ContentDirectory::microhttphost: from config:" << host << "\n");
        return host;
    }
    m->maybeInit();
    return m->upnphost;
}

// Static for use needed by ohcredentials
int CDPluginServices::microhttpport()
{
    return getIntOptionValue("plgmicrohttpport", 49149);
}
