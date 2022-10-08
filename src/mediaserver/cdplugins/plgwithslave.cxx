/* Copyright (C) 2016 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU Lesser General Public License as published by
 *   the Free Software Foundation; either version 2.1 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU Lesser General Public License for more details.
 *
 *   You should have received a copy of the GNU Lesser General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#include "config.h"

#include "plgwithslave.hxx"

#include <string>
#include <vector>
#include <sstream>
#include <functional>
#include <memory>

#include <string.h>
#include <fcntl.h>
#include <json/json.h>
#include <libupnpp/log.hxx>

#include "cmdtalk.h"
#include "pathut.h"
#include "smallut.h"
#include "conftree.h"
#include "sysvshm.h"
#include "main.hxx"
#include "streamproxy.h"
#include "netfetch.h"
#include "curlfetch.h"

#ifdef ENABLE_SPOTIFY
#include "spotify/spotiproxy.h"
#endif

using namespace std;
using namespace std::placeholders;
using namespace UPnPProvider;

class StreamHandle {
public:
    StreamHandle(PlgWithSlave::Internal *plg) {
    }
    ~StreamHandle() {
        clear();
    }
    void clear() {
        plg = 0;
        path.clear();
        media_url.clear();
        len = 0;
        opentime = 0;
    }
    
    PlgWithSlave::Internal *plg;
    string path;
    string media_url;
    long long len;
    time_t opentime;
};

// Timeout seconds for reading data from plugins. Be generous because
// streaming services are sometimes slow, but we don't want to be
// stuck forever.
static const int read_timeout(60);

class PlgWithSlave::Internal {
public:
    Internal(PlgWithSlave *_plg)
        : plg(_plg), cmd(read_timeout), laststream(this) {

        string val;
        if (getOptionValue("plgproxymethod", val) && !val.compare("proxy")) {
            doingproxy = true;
        }
#ifdef ENABLE_SPOTIFY
        if (!plg->getname().compare("spotify")) {
            getOptionValue("spotifyuser", user);
            getOptionValue("spotifypass", password);
            string cachedir = path_cat(g_cachedir, "spotify");
            // Make sure doingproxy is set, independantly of the
            // config variable, which is only useful for Qobuz et al
            doingproxy = true;
            SpotiProxy::setParams(user, password, cachedir, cachedir);
        }
#endif
    }

    bool doproxy() {
        return doingproxy;
    }
    bool maybeStartCmd();

    PlgWithSlave *plg;
    CmdTalk cmd;
    bool doingproxy{false};

    // This is only used by spotify (also needs login in the c++
    // streamer in addition to python). We could create a derived
    // class, but seems simpler this way.
    string user;
    string password;
    
    // Cached uri translation
    StreamHandle laststream;
};

// HTTP Proxy/Redirect handler
static StreamProxy *o_proxy;

StreamProxy::UrlTransReturn translateurl(
    CDPluginServices *cdsrv,
    std::string& url,
    const std::unordered_map<std::string, std::string>& querymap,
    std::unique_ptr<NetFetch>& fetcher
    )
{
    LOGDEB("PlgWithSlave::translateurl: url " << url << endl);

    PlgWithSlave *realplg =
        dynamic_cast<PlgWithSlave*>(cdsrv->getpluginforpath(url));
    if (nullptr == realplg) {
        LOGERR("PlgWithSlave::translateurl: no plugin for path ["<<url<< endl);
        return StreamProxy::Error;
    }

    string path(url);

    // The streaming services plugins set a trackId parameter in the
    // URIs. This gets parsed out by mhttpd. We rebuild a full url
    // which we pass to them for translation (they will extract the
    // trackid and use it, the rest of the path is bogus).
    // The uprcl module has a real path and no trackid. Handle both cases
    const auto it = querymap.find("trackId");
    if (it != querymap.end() && !it->second.empty()) {
        path += string("?version=1&trackId=") + it->second;
    }

    // Translate to Tidal/Qobuz etc real temporary URL
    url = realplg->get_media_url(path);
    if (url.empty()) {
        LOGERR("answer_to_connection: no media_uri for: " << url << endl);
        return StreamProxy::Error;
    }
    StreamProxy::UrlTransReturn method = realplg->doproxy() ?
        StreamProxy::Proxy : StreamProxy::Redirect;
    if (method == StreamProxy::Proxy) {
        if (!realplg->getname().compare("spotify")) {
#ifdef ENABLE_SPOTIFY
            fetcher = std::unique_ptr<NetFetch>(new SpotiFetch(url));
#else
            LOGERR("Spotify URL but Spotify not supported by build\n");
            return StreamProxy::Error;
#endif
        } else {
            fetcher = std::unique_ptr<NetFetch>(new CurlFetch(url));
        }
    }
    return method;
}

// Static because it may be used from ohcredentials without a plugin
// object, just to perform a login and retrieve the authentication
// data. The host and port are bogus in this case, as the script will
// not need to generate URLs
bool PlgWithSlave::startPluginCmd(CmdTalk& cmd, const string& appname,
                                  const string& host, unsigned int port,
                                  const string& pathpref)
{
    string pythonpath = string("PYTHONPATH=") +
        path_cat(g_datadir, "cdplugins") + ":" +
        path_cat(g_datadir, "cdplugins/pycommon") + ":" +
        path_cat(g_datadir, "cdplugins/" + appname);
    string configname = string("UPMPD_CONFIG=") + g_configfilename;
    stringstream ss;
    ss << host << ":" << port;
    string hostport = string("UPMPD_HTTPHOSTPORT=") + ss.str();
    string pp = string("UPMPD_PATHPREFIX=") + pathpref;
    string exepath = path_cat(g_datadir, "cdplugins");
    exepath = path_cat(exepath, appname);
    exepath = path_cat(exepath, appname + "-app" + ".py");

    if (!cmd.startCmd(exepath, {/*args*/},
                      /* env */ {pythonpath, configname, hostport, pp})) {
        LOGERR("PlgWithSlave::maybeStartCmd: startCmd failed\n");
        return false;
    }
    return true;
}

// Static, because it can be called from ohcredentials, indirectly
// through contentdirectory. The proxy may be needed for access from
// the CP even if no plugin is enabled.
bool PlgWithSlave::maybeStartProxy(CDPluginServices *cdsrv)
{
    if (nullptr == o_proxy) {
        int port = CDPluginServices::microhttpport();
        o_proxy = new StreamProxy(
            port,
            std::bind(&translateurl, cdsrv, _1, _2, _3));
            
        if (nullptr == o_proxy) {
            LOGERR("PlgWithSlave: Proxy creation failed\n");
            return false;
        }
    }
    return true;
}

// Called once for starting the Python program and do other initialization.
bool PlgWithSlave::Internal::maybeStartCmd()
{
    if (cmd.running()) {
        LOGDEB1("PlgWithSlave::maybeStartCmd: already running\n");
        return true;
    }
    if (!maybeStartProxy(plg->m_services)) {
        LOGDEB1("PlgWithSlave::maybeStartCmd: maybeStartMHD failed\n");
        return false;
    }
    if (!startPluginCmd(cmd, plg->m_name,
                        plg->m_services->microhttphost(),
                        plg->m_services->microhttpport(),
                        plg->m_services->getpathprefix(plg))) {
        LOGDEB1("PlgWithSlave::maybeStartCmd: startPluginCmd failed\n");
        return false;
    }

    // If the creds have been set in shared mem, login at once, else
    // the plugin will try later from file config data
    LockableShmSeg seg(ohcreds_segpath, ohcreds_segid, ohcreds_segsize);
    if (seg.ok()) {
        LockableShmSeg::Accessor access(seg);
        char *cp = (char *)(access.getseg());
        string data(cp);
        LOGDEB1("PlgWithSlave::maybeStartCmd: segment content [" << data <<
                "]\n");
        ConfSimple credsconf(data, true);
        string user, password;
        if (credsconf.get(plg->m_name + "user", user) &&
            credsconf.get(plg->m_name + "pass", password)) {
            unordered_map<string,string> res;
            if (!cmd.callproc("login", {{"user", user}, {"password", password}},
                              res)) {
                LOGINF("PlgWithSlave::maybeStartCmd: tried login but failed for "
                       << plg->m_name);
            }
        }
    } else {
        LOGDEB0("PlgWithSlave::maybeStartCmd: shm attach error (probably ok)\n");
    }
    return true;
}

bool PlgWithSlave::startInit()
{
    return m && m->maybeStartCmd();
}

// Translate the slave-generated HTTP URL (based on the trackid), to
// an actual temporary service (e.g. tidal one), which will be an HTTP
// URL pointing to either an AAC or a FLAC stream.
// Older versions of this module handled AAC FLV transported over
// RTMP, apparently because of the use of a different API key. Look up
// the git history if you need this again.
// The Python code calls the service to translate the trackid to a temp
// URL. We cache the result for a few seconds to avoid multiple calls
// to tidal.
string PlgWithSlave::get_media_url(const string& path)
{
    LOGDEB0("PlgWithSlave::get_media_url: " << path << endl);
    if (!m->maybeStartCmd()) {
        return string();
    }
    time_t now = time(0);
    if (m->laststream.path.compare(path) ||
        (now - m->laststream.opentime > 10)) {
        unordered_map<string, string> res;
        if (!m->cmd.callproc("trackuri", {{"path", path}}, res)) {
            LOGERR("PlgWithSlave::get_media_url: slave failure\n");
            return string();
        }

        auto it = res.find("media_url");
        if (it == res.end()) {
            LOGERR("PlgWithSlave::get_media_url: no media url in result\n");
            return string();
        }
        m->laststream.clear();
        m->laststream.path = path;
        m->laststream.media_url = it->second;
        m->laststream.opentime = now;
    }

    LOGDEB("PlgWithSlave: media url [" << m->laststream.media_url << "]\n");
    return m->laststream.media_url;
}


PlgWithSlave::PlgWithSlave(const string& name, CDPluginServices *services)
    : CDPlugin(name, services)
{
    m = new Internal(this);
}

PlgWithSlave::~PlgWithSlave()
{
    delete m;
}

bool PlgWithSlave::doproxy()
{
    return m->doproxy();
}

static void catstring(string& dest, const string& s2)
{
    if (s2.empty()) {
        return;
    }
    if (dest.empty()) {
        dest = s2;
    } else {
        dest += string(" ") + s2;
    }
}

static void decodeResource(const Json::Value entry, UpSong::Res &res)
{
    res.uri = entry.get("uri", "").asString();
    res.mime = entry.get("res:mime", "").asString();
    string ss = entry.get("duration", "").asString();
    if (!ss.empty()) {
        res.duration_secs = atoi(ss.c_str());
    }
    ss = entry.get("res:size", "").asString();
    if (!ss.empty()) {
        res.size = atoll(ss.c_str());
    }
    ss = entry.get("res:bitrate", "").asString();
    if (!ss.empty()) {
        res.bitrate = atoi(ss.c_str());
    }
    ss = entry.get("res:samplefreq", "").asString();
    if (!ss.empty()) {
        res.samplefreq = atoi(ss.c_str());
    }
    ss = entry.get("res:bitsPerSample", "").asString();
    if (!ss.empty()) {
        res.bitsPerSample = atoi(ss.c_str());
    }
    ss = entry.get("res:channels", "").asString();
    if (!ss.empty()) {
        res.channels = atoi(ss.c_str());
    }
}

#define JSONTOUPS(fld, nm) {catstring(song.fld, \
                                      decoded[i].get(#nm, "").asString());}

static int resultToEntries(const string& encoded, vector<UpSong>& entries)
{
    Json::Value decoded;
    istringstream input(encoded);
    input >> decoded;
    LOGDEB0("PlgWithSlave::results: got " << decoded.size() << " entries \n");
    LOGDEB1("PlgWithSlave::results: undecoded: " << decoded.dump() << endl);

    entries.reserve(decoded.size());
    for (unsigned int i = 0; i < decoded.size(); i++) {
        entries.emplace_back();
        UpSong& song = entries.back();
        JSONTOUPS(id, id);
        JSONTOUPS(parentid, pid);
        JSONTOUPS(title, tt);
        JSONTOUPS(artUri, upnp:albumArtURI);
        JSONTOUPS(artist, upnp:artist);
        JSONTOUPS(upnpClass, upnp:class);
        JSONTOUPS(dcdescription, dc:description);
        JSONTOUPS(date, dc:date)
        JSONTOUPS(date, releasedate)
        // tp is container ("ct") or item ("it")
        string stp = decoded[i].get("tp", "").asString();
        if (!stp.compare("ct")) {
            song.iscontainer = true;
            string ss = decoded[i].get("searchable", "").asString();
            if (!ss.empty()) {
                song.searchable = stringToBool(ss);
            }
        } else  if (!stp.compare("it")) {
            song.iscontainer = false;
            JSONTOUPS(artist, dc:creator);
            JSONTOUPS(genre, upnp:genre);
            JSONTOUPS(album, upnp:album);
            JSONTOUPS(tracknum, upnp:originalTrackNumber);
            // Decode resource data in base record
            decodeResource(decoded[i], song.rsrc);
            // Possibly add resources from resource array if present
            const Json::Value &resources = decoded[i]["resources"];
            LOGDEB1("decoded['resources'] is type " << resources.type() << endl);
            if (resources.isArray()) {
                for (unsigned int i = 0; i < resources.size(); i++) {
                    song.resources.push_back(UpSong::Res());
                    decodeResource(resources[i], song.resources.back());
                }
            }
        } else {
            LOGERR("PlgWithSlave::result: bad type in entry: " << stp <<
                   "(title: " << song.title << ")\n");
            continue;
        }
        LOGDEB1("PlgWitSlave::result: pushing: " << song.dump() << endl);
    }
    return decoded.size();
}


class ContentCacheEntry {
public:
    int toResult(const string& classfilter, int stidx, int cnt,
                 vector<UpSong>& entries) const;
    time_t m_time{time(0)};
    int m_offset{0};
    int m_total{-1};
    vector<UpSong> m_results;
};

int ContentCacheEntry::toResult(const string& classfilter, int stidx, int cnt,
                                vector<UpSong>& entries) const
{
    LOGDEB0("searchCacheEntryToResult: filter " << classfilter << " start " <<
            stidx << " cnt " << cnt << " m_offset " << m_offset <<
            " m_results.size " << m_results.size() << "\n");

    if (stidx < m_offset) {
        // we're missing a part
        LOGERR("ContentCacheEntry::toResult: stidx " << stidx << " < offset " <<
               m_offset << "\n");
        return -1;
    }

    if (cnt > 0)
        entries.reserve(cnt);
    for (int i = stidx - m_offset; i < int(m_results.size()); i++) {
        if (!classfilter.empty() &&
            m_results[i].upnpClass.find(classfilter) != 0) {
            continue;
        }
        LOGDEB1("ContentCacheEntry::toResult: pushing class " <<
                m_results[i].upnpClass << " tt " << m_results[i].title << endl);
        entries.push_back(m_results[i]);
        if (cnt > 0 && int(entries.size()) >= cnt) {
            break;
        }
    }
    // We return the total size. The actual count of entries is
    // communicated through entries.size()
    return m_total == -1 ? m_results.size() : m_total;
}

class ContentCache {
public:
    ContentCache(int retention_secs = 300)
        : m_retention_secs(retention_secs) {}
    std::shared_ptr<ContentCacheEntry> get(const string& query);
    ContentCacheEntry& set(const string& query, ContentCacheEntry &entry);
    void purge();
private:
    time_t m_lastpurge{time(0)};
    int m_retention_secs;
    unordered_map<string, ContentCacheEntry> m_cache;
};

void ContentCache::purge()
{
    time_t now(time(0));
    if (now - m_lastpurge < 5) {
        return;
    }
    for (auto it = m_cache.begin(); it != m_cache.end(); ) {
        if (now - it->second.m_time > m_retention_secs) {
            LOGDEB0("ContentCache::purge: erasing " << it->first << endl);
            it = m_cache.erase(it);
        } else {
            it++;
        }
    }
    m_lastpurge = now;
}

std::shared_ptr<ContentCacheEntry> ContentCache::get(const string& key)
{
    purge();
    auto it = m_cache.find(key);
    if (it != m_cache.end()) {
        ContentCacheEntry& entry = it->second;
        LOGDEB0("ContentCache::get: found " << key << " offset " << entry.m_offset <<
            " count " << entry.m_results.size() << "\n");
        // we return a copy of the vector. Make our multi-access life simpler...
        return std::make_shared<ContentCacheEntry>(it->second);
    }
    LOGDEB0("ContentCache::get: not found " << key << endl);
    return std::shared_ptr<ContentCacheEntry>();
}

ContentCacheEntry& ContentCache::set(const string& key, ContentCacheEntry &entry)
{
    LOGDEB0("ContentCache::set: " << key << " offset " << entry.m_offset <<
            " count " << entry.m_results.size() << "\n");
    m_cache[key] = entry;
    return m_cache[key];
}

// Cache for searches
static ContentCache o_scache(300);
// Cache for browsing
static ContentCache o_bcache(180);

// Better return a bogus informative entry than an outright error:
static int errorEntries(const string& pid, vector<UpSong>& entries)
{
    entries.push_back(
        UpSong::item(pid + "$bogus", pid,
                     "Service login or communication failure"));
    return 1;
}

int PlgWithSlave::browse(const string& objid, int stidx, int cnt,
                         vector<UpSong>& entries,
                         const vector<string>& sortcrits,
                         BrowseFlag flg)
{
    LOGDEB("PlgWithSlave::browse: offset " << stidx << " cnt " << cnt << "\n");
    entries.clear();
    if (!m->maybeStartCmd()) {
        return errorEntries(objid, entries);
    }
    string sbflg;
    switch (flg) {
    case CDPlugin::BFMeta:
        sbflg = "meta";
        break;
    case CDPlugin::BFChildren:
    default:
        sbflg = "children";
        break;
    }

    string cachekey(m_name + ":" + objid);
    if (flg == CDPlugin::BFChildren) {
        // Check cache
        auto cep = o_bcache.get(cachekey);
        if (cep) {
            LOGDEB("PlgWithSlave::browse: found cache entry: offset " <<
                   cep->m_offset << " count " << cep->m_results.size() <<
                   " total " << cep->m_total << "\n");
            if (cep->m_total > 0 && cnt + stidx > cep->m_total) {
                cnt = cep->m_total - stidx;
                LOGDEB("PlgWithSlave::browse: adjusted cnt to " << cnt << "\n");
            }
            if (cep->m_offset <= stidx &&
                int(cep->m_results.size()) - (stidx - cep->m_offset) >= cnt) {
                return cep->toResult("", stidx, cnt, entries);
            }
        }
    }

    std::string soffs = lltodecstr(stidx);
    std::string scnt = lltodecstr(cnt);
    unordered_map<string, string> res;
    if (!m->cmd.callproc(
            "browse", {{"objid", objid}, {"flag", sbflg},
                       {"offset", soffs}, {"count", scnt}}, res)) {
        LOGERR("PlgWithSlave::browse: slave failure\n");
        return errorEntries(objid, entries);
    }

    auto ite = res.find("entries");
    if (ite == res.end()) {
        LOGERR("PlgWithSlave::browse: no entries returned\n");
        return errorEntries(objid, entries);
    }
    bool nocache = false;
    auto itc = res.find("nocache");
    if (itc != res.end()) {
        nocache = stringToBool(itc->second);
    }
    int resoffs{0};
    itc = res.find("offset");
    if (itc != res.end()) {
        resoffs = atoi(itc->second.c_str());
        LOGDEB("PlgWithSlave::browse: got result offset " << resoffs << "\n");
    }
    int total = -1;
    itc = res.find("total");
    if (itc != res.end()) {
        total = atoi(itc->second.c_str());
        LOGDEB("PlgWithSlave::browse: got result total " << total << "\n");
    }
    
    if (flg == CDPlugin::BFChildren) {
        ContentCacheEntry entry;
        ContentCacheEntry& e = nocache ? entry : o_bcache.set(cachekey, entry);
        e.m_offset = resoffs;
        e.m_total = total;
        resultToEntries(ite->second, e.m_results);
        return e.toResult("", stidx, cnt, entries);
    } else {
        return resultToEntries(ite->second, entries);
    }
}

int PlgWithSlave::search(const string& ctid, int stidx, int cnt,
                         const string& searchstr,
                         vector<UpSong>& entries,
                         const vector<string>& sortcrits)
{
    LOGDEB("PlgWithSlave::search: [" << searchstr << "]\n");
    entries.clear();
    if (!m->maybeStartCmd()) {
        return errorEntries(ctid, entries);
    }

    // Computing a pre-cooked query. For simple-minded plugins.
    // Note that none of the qobuz/gmusic/tidal plugins actually use
    // the slavefield part (defining in what field the term should
    // match).
    // 
    // Ok, so the upnp query language is quite powerful, but us, not
    // so much. We get rid of parenthesis and then try to find the
    // first searchExp on a field we can handle, pretend the operator
    // is "contains" and just do it. I so don't want to implement a
    // parser for the query language when the services don't support
    // anything complicated anyway, and the users don't even want it...
    string ss;
    neutchars(searchstr, ss, "()");

    // The search had better be space-separated. no
    // upnp:artist="beatles" for you
    vector<string> vs;
    stringToStrings(ss, vs);

    // The sequence can now be either [field, op, value], or
    // [field, op, value, and/or, field, op, value,...]
    if ((vs.size() + 1) % 4 != 0) {
        LOGERR("PlgWithSlave::search: bad search string: [" << searchstr <<
               "]\n");
        return errorEntries(ctid, entries);
    }
    string slavefield;
    string value;
    string classfilter;
    string objkind;
    for (unsigned int i = 0; i < vs.size()-2; i += 4) {
        const string& upnpproperty = vs[i];
        LOGDEB("PlgWithSlave::search:clause: " << vs[i] << " " << vs[i+1] <<
               " " << vs[i+2] << endl);
        if (!upnpproperty.compare("upnp:class")) {
            // This defines -what- we are looking for (track/album/artist)
            const string& what(vs[i+2]);
            if (beginswith(what, "object.item")) {
                objkind = "track";
            } else if (beginswith(what, "object.container.person")) {
                objkind = "artist";
            } else if (beginswith(what, "object.container.musicAlbum") ||
                       beginswith(what, "object.container.album")) {
                objkind = "album";
            } else if (beginswith(what, "object.container.playlistContainer")
                       || beginswith(what, "object.container.playlist")) {
                objkind = "playlist";
            }
            classfilter = what;
        } else if (!upnpproperty.compare("upnp:artist") ||
                   !upnpproperty.compare("dc:author")) {
            slavefield = "artist";
            value = vs[i+2];
            break;
        } else if (!upnpproperty.compare("upnp:album")) {
            slavefield = "album";
            value = vs[i+2];
            break;
        } else if (!upnpproperty.compare("dc:title")) {
            slavefield = "track";
            value = vs[i+2];
            break;
        }
    }

    // In cache ?
    string cachekey(m_name + ":" + ctid + ":" + searchstr);
    auto cep = o_scache.get(cachekey);
    if (cep) {
        int total = cep->toResult(classfilter, stidx, cnt, entries);
        return total;
    }

    // Run query
    std::string soffs = lltodecstr(stidx);
    std::string scnt = lltodecstr(cnt);
    unordered_map<string, string> res;
    if (!m->cmd.callproc("search", {
                {"objid", ctid},
                {"objkind", objkind},
                {"origsearch", searchstr},
                {"field", slavefield},
                {"value", value},
                {"offset", soffs}, {"count", scnt} },  res)) {
        LOGERR("PlgWithSlave::search: slave failure\n");
        return errorEntries(ctid, entries);
    }

    auto ite = res.find("entries");
    if (ite == res.end()) {
        LOGERR("PlgWithSlave::search: no entries returned\n");
        return errorEntries(ctid, entries);
    }
    bool nocache = false;
    auto itc = res.find("nocache");
    if (itc != res.end()) {
        nocache = stringToBool(itc->second);
    }
    int resoffs{0};
    itc = res.find("offset");
    if (itc != res.end()) {
        resoffs = atoi(itc->second.c_str());
        LOGDEB("PlgWithSlave::search: got result offset " << resoffs << "\n");
    }
    int total = -1;
    itc = res.find("total");
    if (itc != res.end()) {
        total = atoi(itc->second.c_str());
        LOGDEB("PlgWithSlave::search: got result total " << total << "\n");
    }
    // Convert the whole set and store in cache
    ContentCacheEntry entry;
    ContentCacheEntry& e = nocache ? entry : o_scache.set(cachekey, entry);
    e.m_offset = resoffs;
    e.m_total = total;
    resultToEntries(ite->second, e.m_results);
    return e.toResult(classfilter, stidx, cnt, entries);
}
