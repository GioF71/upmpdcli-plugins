/* Copyright (C) 2016-2023 J.F.Dockes
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
#include <functional>
#include <memory>
#include <mutex>
#include <sstream>

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

class StreamHandle {
public:
    StreamHandle() = default;
    ~StreamHandle() = default;
    void clear() {
        path.clear();
        media_url.clear();
        len = 0;
        opentime = 0;
    }
    
    string path;
    string media_url;
    long long len{0};
    time_t opentime{0};
};

class ContentCacheEntry {
public:
    int toResult(int stidx, int cnt, vector<UpSong>& entries) const;
    time_t m_time{time(0)};
    int m_offset{0};
    int m_total{-1};
    vector<UpSong> m_results;
};

class ContentCache {
public:
    ContentCache(int retention_secs = 300)
        : m_retention_secs(retention_secs) {}
    std::unique_ptr<ContentCacheEntry> get(const string& query);
    ContentCacheEntry& set(const string& query, ContentCacheEntry &entry);

private:
    time_t m_lastpurge{time(0)};
    int m_retention_secs;
    unordered_map<string, ContentCacheEntry> m_cache;

    void purge();
};

// Timeout seconds for reading data from plugins. Be generous because
// streaming services are sometimes slow, but we don't want to be
// stuck forever.
static const int read_timeout(60);

class PlgWithSlave::Internal {
public:
    Internal(PlgWithSlave *_plg)
        : plg(_plg), cmd(read_timeout) {

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

    std::mutex mutex;
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
    // Cache for searches
    ContentCache scache{300};
    // Cache for browsing
    ContentCache bcache{180};
};

// HTTP Proxy/Redirect handler
static StreamProxy *o_proxy;

StreamProxy::UrlTransReturn translateurl(
    CDPluginServices *cdsrv, const std::string& useragent, std::string& url,
    const std::unordered_map<std::string, std::string>& querymap, std::unique_ptr<NetFetch>& fetcher)
{
    LOGDEB("PlgWithSlave::translateurl: url " << url << "\n");

    CDPlugin *plg = cdsrv->getpluginforpath(url);
    if (nullptr == plg) {
        LOGERR("PlgWithSlave::translateurl: no plugin for path ["<< url << "\n");
        return StreamProxy::Error;
    }
    PlgWithSlave *realplg = dynamic_cast<PlgWithSlave*>(plg);
    if (nullptr == realplg) {
        LOGERR("PlgWithSlave::translateurl: bad plugin for path ["<< url << "\n");
        return StreamProxy::Error;
    }

    string path(url);
    // Translate to Tidal/Qobuz etc real temporary URL
    url = realplg->get_media_url(path, useragent);
    if (url.empty()) {
        LOGERR("answer_to_connection: no media_uri for: " << url << "\n");
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
                                  const string& pathpref, string upnphost, int upnpport)
{
    string pythonpath = string("PYTHONPATH=") +
        path_cat(g_datadir, "cdplugins") + ":" +
        path_cat(g_datadir, "cdplugins/pycommon") + ":" +
        path_cat(g_datadir, "cdplugins/" + appname);
    string configname = string("UPMPD_CONFIG=") + g_configfilename;

    // Send the microhttpd host:port and pathprefix strings through the environment. Used by
    // plugins which need to redirect or proxy their URLs (e.g. Qobuz, or, previously, now
    // obsolete Tidal, Spotify...) This allows the plugin to construct appropriate URLs. The
    // pathprefix is used to determine which plugin an URL belongs to.
    // The URLs are like: http://$UPMPD_HTTPHOSTPORT/$UPMPD_PATHPREFIX/...
    
    string hostport = string("UPMPD_HTTPHOSTPORT=") + host + ":" + std::to_string(port);
    string pp = string("UPMPD_PATHPREFIX=") + pathpref;

    std::vector<std::string> env{pythonpath, configname, hostport, pp};

    // Send the UPnP (libnpupnp) HTTP IP address and port. This allows using the internal
    // lib(np)upnp HTTP server to serve local files (if enabled by setting webserverdocumentroot in
    // the config accordingly, see main.hxx).
    if (!g_npupnpwebdocroot.empty()) {
        env.push_back(string("UPMPD_UPNPHOSTPORT=") + upnphost + ":" + std::to_string(upnpport));
        env.push_back(string("UPMPD_UPNPDOCROOT=") + g_npupnpwebdocroot);
    }

    env.push_back(string("UPMPD_PKGDATADIR=") + g_datadir);

    string exepath = path_cat(g_datadir, "cdplugins");
    exepath = path_cat(exepath, appname);
    exepath = path_cat(exepath, appname + "-app.py");
    if (!cmd.startCmd(exepath, {/*args*/}, env)) {
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
        o_proxy = new StreamProxy(port, std::bind(&translateurl, cdsrv, _1, _2, _3, _4));
            
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
                        plg->m_services->getpathprefix(plg->m_name),
                        plg->m_services->getupnpaddr(),
                        plg->m_services->getupnpport()
            )) {
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
        LOGDEB1("PlgWithSlave::maybeStartCmd: segment content [" << data << "]\n");
        ConfSimple credsconf(data, true);
        string user, password;
        if (credsconf.get(plg->m_name + "user", user) &&
            credsconf.get(plg->m_name + "pass", password)) {
            unordered_map<string,string> res;
            if (!cmd.callproc("login", {{"user", user}, {"password", password}}, res)) {
                LOGINF("PlgWithSlave::maybeStartCmd: tried login but failed for " << plg->m_name);
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
string PlgWithSlave::get_media_url(const string& path, const std::string& useragent)
{
    LOGDEB0("PlgWithSlave::get_media_url: " << path << "\n");
    if (!m->maybeStartCmd()) {
        return string();
    }
    time_t now = time(0);
    if (m->laststream.path.compare(path) ||
        (now - m->laststream.opentime > 10)) {
        unordered_map<string, string> res;
        if (!m->cmd.callproc("trackuri", {{"path", path}, {"user-agent", useragent}}, res)) {
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
        dest += string(", ") + s2;
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

#define JSONTOUPS(fld, nm) {catstring(song.fld, decod_i.get(#nm, "").asString());}

static int resultToEntries(const string& encoded, vector<UpSong>& entries,
                           const std::string& classfilter = std::string())
{
    Json::Value decoded;
    istringstream input(encoded);
    input >> decoded;
    LOGDEB0("PlgWithSlave::results: got " << decoded.size() << " entries \n");

    entries.reserve(decoded.size());
    for (unsigned int i = 0; i < decoded.size(); i++) {
        UpSong song;
        Json::Value& decod_i = decoded[i];

        // Possibly extract our vendor extension fields
        for(auto it = decod_i.begin(); it != decod_i.end(); it++) {
            if (beginswith(it.key().asString(), "upmpd:")) {
                if (song.upmpfields == nullptr)
                    song.upmpfields = new std::unordered_map<std::string, std::string>;
                LOGDEB1("resultToEntries: "<<it.key().asString()<<" -> "<<(*it).asString()<<'\n');
                auto& flds(*(song.upmpfields));
                flds[it.key().asString()] = (*it).asString();
            }
        }

        JSONTOUPS(id, id);
        JSONTOUPS(parentid, pid);
        JSONTOUPS(title, tt);
        JSONTOUPS(artUri, upnp:albumArtURI);
        JSONTOUPS(artist, upnp:artist);
        auto cr = decod_i.get("dc:creator", "").asString();
        if (cr != song.artist) {
            catstring(song.artist, cr);
        }
        JSONTOUPS(upnpClass, upnp:class);
        JSONTOUPS(dcdescription, dc:description);
        JSONTOUPS(album, upnp:album);
        JSONTOUPS(dcdate, dc:date);
        JSONTOUPS(genre, upnp:genre);
        song.didlfrag = decod_i.get("didlfrag", "").asString();
    
        // tp is container ("ct") or item ("it")
        string stp = decod_i.get("tp", "").asString();
        if (!stp.compare("ct")) {
            song.iscontainer = true;
            string ss = decod_i.get("searchable", "").asString();
            if (!ss.empty()) {
                song.searchable = stringToBool(ss);
            }
        } else  if (!stp.compare("it")) {
            song.iscontainer = false;
            JSONTOUPS(tracknum, upnp:originalTrackNumber);
            // Decode resource data in base record
            decodeResource(decod_i, song.rsrc);
            // Possibly add resources from resource array if present
            const Json::Value &resources = decod_i["resources"];
            LOGDEB1("decoded['resources'] is type " << resources.type() << "\n");
            if (resources.isArray()) {
                if (nullptr == song.resources) {
                    song.resources = new std::vector<UpSong::Res>;
                }
                for (unsigned int i = 0; i < resources.size(); i++) {
                    song.resources->push_back(UpSong::Res());
                    decodeResource(resources[i], song.resources->back());
                }
            }
        } else {
            LOGERR("PlgWithSlave::result: bad type: <" << stp << "> (titl: " << song.title << ")\n");
            continue;
        }
        if (!classfilter.empty() && song.upnpClass.find(classfilter) != 0) {
            LOGDEB1("PlgWithSlave::resultToEntries: class mismatch " << classfilter << "\n");
            continue;
        }
        LOGDEB1("PlgWithSlave::resultToEntries: pushing: " << song.dump() << "\n");
        entries.push_back(song);
    }
    return decoded.size();
}


int ContentCacheEntry::toResult(int stidx, int cnt, vector<UpSong>& entries) const
{
    LOGDEB0("searchCacheEntryToResult: start " <<
            stidx << " cnt " << cnt << " m_offset " << m_offset <<
            " m_results.size " << m_results.size() << "\n");

    if (stidx < m_offset) {
        // we're missing a part
        LOGERR("ContentCacheEntry::toResult: stidx " << stidx << " < offset " << m_offset << "\n");
        return -1;
    }

    if (cnt > 0)
        entries.reserve(cnt);
    for (int i = stidx - m_offset; i < int(m_results.size()); i++) {
        LOGDEB1("ContentCacheEntry::toResult: pushing class " <<
                m_results[i].upnpClass << " tt " << m_results[i].title << "\n");
        entries.push_back(m_results[i]);
        if (cnt > 0 && int(entries.size()) >= cnt) {
            break;
        }
    }
    // We return the total size. The actual count of entries is
    // communicated through entries.size()
    return m_total == -1 ? m_results.size() : m_total;
}

void ContentCache::purge()
{
    time_t now(time(0));
    if (now - m_lastpurge < 5) {
        return;
    }
    for (auto it = m_cache.begin(); it != m_cache.end(); ) {
        if (now - it->second.m_time > m_retention_secs) {
            LOGDEB0("ContentCache::purge: erasing " << it->first << "\n");
            it = m_cache.erase(it);
        } else {
            it++;
        }
    }
    m_lastpurge = now;
}

std::unique_ptr<ContentCacheEntry> ContentCache::get(const string& key)
{
    purge();
    auto it = m_cache.find(key);
    if (it != m_cache.end()) {
        ContentCacheEntry& entry = it->second;
        LOGDEB0("ContentCache::get: found " << key << " offset " << entry.m_offset <<
                " count " << entry.m_results.size() << "\n");
        // we return a copy of the vector. Make our multi-access life simpler...
        return std::make_unique<ContentCacheEntry>(it->second);
    }
    LOGDEB0("ContentCache::get: not found " << key << "\n");
    return std::unique_ptr<ContentCacheEntry>();
}

ContentCacheEntry& ContentCache::set(const string& key, ContentCacheEntry &entry)
{
    LOGDEB0("ContentCache::set: " << key << " offset " << entry.m_offset <<
            " count " << entry.m_results.size() << "\n");
    m_cache[key] = entry;
    return m_cache[key];
}

// Better return a bogus informative entry than an outright error:
static int errorEntries(const string& pid, vector<UpSong>& entries)
{
    entries.push_back(UpSong::item(pid + "$bogus", pid, "Service login or communication failure"));
    return 1;
}

int PlgWithSlave::browse(const string& objid, int stidx, int cnt, vector<UpSong>& entries,
                         const vector<string>& sortcrits, BrowseFlag flg)
{
    std::unique_lock<std::mutex> lock(m->mutex);
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
        auto cep = m->bcache.get(cachekey);
        if (cep) {
            LOGDEB("PlgWithSlave::browse: found cache entry: offset " << cep->m_offset <<
                   " count " << cep->m_results.size() << " total " << cep->m_total << "\n");
            if (cep->m_total > 0 && cnt + stidx > cep->m_total) {
                cnt = cep->m_total - stidx;
                LOGDEB("PlgWithSlave::browse: adjusted cnt to " << cnt << "\n");
            }
            if (cep->m_offset <= stidx &&
                int(cep->m_results.size()) - (stidx - cep->m_offset) >= cnt) {
                return cep->toResult(stidx, cnt, entries);
            }
        }
    }

    std::string soffs = std::to_string(stidx);
    std::string scnt = std::to_string(cnt);
    unordered_map<string, string> res;
    if (!m->cmd.callproc("browse", {{"objid", objid}, {"flag", sbflg},
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
        ContentCacheEntry& e = nocache ? entry : m->bcache.set(cachekey, entry);
        e.m_offset = resoffs;
        e.m_total = total;
        resultToEntries(ite->second, e.m_results);
        return e.toResult(stidx, cnt, entries);
    } else {
        return resultToEntries(ite->second, entries);
    }
}

// Computing a pre-cooked query for simple-minded plugins.
//
// The plugins also receive the original search string, and, e.g. Uprcl, uses it instead of the
// simplified parameters.
//
// Note that none of the qobuz/gmusic/tidal plugins actually use the slavefield part (defining in
// what field the term should match).
// 
// Ok, so the upnp query language is quite powerful, but most our plugins, not so much. We prepare a
// simplified search by getting rid of parenthesis and then trying to find the first searchExp on a
// field we can handle, pretend the operator is "contains" and just do it. I so don't want to
// implement a parser for the query language when the services don't support anything complicated
// anyway.
static bool eli5(const std::string& searchstr, std::string& slavefield, std::string& value,
                 std::string& classfilter, std::string& objkind)
{
    string ss;
    neutchars(searchstr, ss, "()");
    // The search had better be space-separated. no upnp:artist="beatles" for you
    vector<string> vs;
    stringToStrings(ss, vs);
    // The sequence can now be either [field, op, value], or [field, op, value, and/or, field, op,
    // value,...]. The number of fields is n*4 - 1 (missing last conjunction)
    if ((vs.size() + 1) % 4 != 0) {
        LOGERR("PlgWithSlave::search: bad search string: [" << searchstr << "]\n");
        return false;
    }

    // Note that if we only keep one object kind filtering clause and one content filtering one. If
    // there are more, these will be the last ones.
    for (unsigned int i = 0; i < vs.size()-2; i += 4) {
        const string& upnpproperty = vs[i];
        LOGDEB("PlgWithSlave::search:clause: " << vs[i] << " " << vs[i+1] << " " << vs[i+2] << "\n");
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
        } else if (!upnpproperty.compare("upnp:artist") || !upnpproperty.compare("dc:author")) {
            slavefield = "artist";
            value = vs[i+2];
        } else if (!upnpproperty.compare("upnp:album")) {
            slavefield = "album";
            value = vs[i+2];
        } else if (!upnpproperty.compare("dc:title")) {
            slavefield = "track";
            value = vs[i+2];
        }
    }
    return true;
}


int PlgWithSlave::search(const string& ctid, int stidx, int cnt, const string& searchstr,
                         vector<UpSong>& entries, const vector<string>& sortcrits)
{
    std::unique_lock<std::mutex> lock(m->mutex);
    LOGDEB("PlgWithSlave::search: [" << searchstr << "]\n");
    entries.clear();
    if (!m->maybeStartCmd()) {
        return errorEntries(ctid, entries);
    }

    string slavefield, value, classfilter, objkind;
    if (!eli5(searchstr, slavefield, value, classfilter, objkind)) {
        return errorEntries(ctid, entries);
    }        

    // In cache ?
    string cachekey(m_name + ":" + ctid + ":" + searchstr);
    auto cep = m->scache.get(cachekey);
    if (cep) {
        int total = cep->toResult(stidx, cnt, entries);
        return total;
    }

    // Run query
    std::string soffs = std::to_string(stidx);
    std::string scnt = std::to_string(cnt);
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
    ContentCacheEntry& e = nocache ? entry : m->scache.set(cachekey, entry);
    e.m_offset = resoffs;
    e.m_total = total;
    resultToEntries(ite->second, e.m_results, classfilter);
    return e.toResult(stidx, cnt, entries);
}
