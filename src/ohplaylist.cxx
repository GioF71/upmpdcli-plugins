/* Copyright (C) 2014 J.F.Dockes
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

#include "ohplaylist.hxx"

#include <stdlib.h>                     // for atoi

#include <upnp/upnp.h>                  // for UPNP_E_SUCCESS, etc

#include <functional>                   // for _Bind, bind, _1, _2
#include <iostream>                     // for endl, etc
#include <string>                       // for string, allocator, etc
#include <utility>                      // for pair
#include <vector>                       // for vector

#include "libupnpp/base64.hxx"          // for base64_encode
#include "libupnpp/log.hxx"             // for LOGDEB, LOGERR
#include "libupnpp/soaphelp.hxx"        // for SoapIncoming, SoapOutgoing, i2s, etc
#include "libupnpp/upnpavutils.hxx"

#include "ohmetacache.hxx"              // for dmcacheSave
#include "mpdcli.hxx"                   // for MpdStatus, UpSong, MPDCli, etc
#include "upmpd.hxx"                    // for UpMpd, etc
#include "upmpdutils.hxx"               // for didlmake, diffmaps, etc
#include "ohproduct.hxx"

using namespace std;
using namespace std::placeholders;

static const string sTpProduct("urn:av-openhome-org:service:Playlist:1");
static const string sIdProduct("urn:av-openhome-org:serviceId:Playlist");

// Playlist is the default oh service, so it's active when starting up
OHPlaylist::OHPlaylist(UpMpd *dev, unsigned int cssleep)
    : OHService(sTpProduct, sIdProduct, dev),
      m_active(true), m_cachedirty(false), m_mpdqvers(-1)
{
    dev->addActionMapping(this, "Play", 
                          bind(&OHPlaylist::play, this, _1, _2));
    dev->addActionMapping(this, "Pause", 
                          bind(&OHPlaylist::pause, this, _1, _2));
    dev->addActionMapping(this, "Stop", 
                          bind(&OHPlaylist::stop, this, _1, _2));
    dev->addActionMapping(this, "Next", 
                          bind(&OHPlaylist::next, this, _1, _2));
    dev->addActionMapping(this, "Previous", 
                          bind(&OHPlaylist::previous, this, _1, _2));
    dev->addActionMapping(this, "SetRepeat",
                          bind(&OHPlaylist::setRepeat, this, _1, _2));
    dev->addActionMapping(this, "Repeat",
                          bind(&OHPlaylist::repeat, this, _1, _2));
    dev->addActionMapping(this, "SetShuffle",
                          bind(&OHPlaylist::setShuffle, this, _1, _2));
    dev->addActionMapping(this, "Shuffle",
                          bind(&OHPlaylist::shuffle, this, _1, _2));
    dev->addActionMapping(this, "SeekSecondAbsolute",
                          bind(&OHPlaylist::seekSecondAbsolute, this, _1, _2));
    dev->addActionMapping(this, "SeekSecondRelative",
                          bind(&OHPlaylist::seekSecondRelative, this, _1, _2));
    dev->addActionMapping(this, "SeekId",
                          bind(&OHPlaylist::seekId, this, _1, _2));
    dev->addActionMapping(this, "SeekIndex",
                          bind(&OHPlaylist::seekIndex, this, _1, _2));
    dev->addActionMapping(this, "TransportState",
                          bind(&OHPlaylist::transportState, this, _1, _2));
    dev->addActionMapping(this, "Id",
                          bind(&OHPlaylist::id, this, _1, _2));
    dev->addActionMapping(this, "Read",
                          bind(&OHPlaylist::ohread, this, _1, _2));
    dev->addActionMapping(this, "ReadList",
                          bind(&OHPlaylist::readList, this, _1, _2));
    dev->addActionMapping(this, "Insert",
                          bind(&OHPlaylist::insert, this, _1, _2));
    dev->addActionMapping(this, "DeleteId",
                          bind(&OHPlaylist::deleteId, this, _1, _2));
    dev->addActionMapping(this, "DeleteAll",
                          bind(&OHPlaylist::deleteAll, this, _1, _2));
    dev->addActionMapping(this, "TracksMax",
                          bind(&OHPlaylist::tracksMax, this, _1, _2));
    dev->addActionMapping(this, "IdArray",
                          bind(&OHPlaylist::idArray, this, _1, _2));
    dev->addActionMapping(this, "IdArrayChanged",
                          bind(&OHPlaylist::idArrayChanged, this, _1, _2));
    dev->addActionMapping(this, "ProtocolInfo",
                          bind(&OHPlaylist::protocolInfo, this, _1, _2));
    
    if ((dev->m_options & UpMpd::upmpdOhMetaPersist)) {
        dmcacheSetOpts(cssleep);
        if (!dmcacheRestore(dev->getMetaCacheFn(), m_metacache)) {
            LOGERR("ohPlaylist: cache restore failed" << endl);
        } else {
            LOGDEB("ohPlaylist: cache restore done" << endl);
        }
    }
}

static const int tracksmax = 16384;

static string mpdstatusToTransportState(MpdStatus::State st)
{
    string tstate;
    switch(st) {
    case MpdStatus::MPDS_PLAY: 
        tstate = "Playing";
        break;
    case MpdStatus::MPDS_PAUSE: 
        tstate = "Paused";
        break;
    default:
        tstate = "Stopped";
    }
    return tstate;
}

// The data format for id lists is an array of msb 32 bits ints
// encoded in base64...
static string translateIdArray(const vector<UpSong>& in)
{
    string out1;
    string sdeb;
    for (auto us = in.begin(); us != in.end(); us++) {
        unsigned int val = us->mpdid;
        if (val) {
            out1 += (unsigned char) ((val & 0xff000000) >> 24);
            out1 += (unsigned char) ((val & 0x00ff0000) >> 16);
            out1 += (unsigned char) ((val & 0x0000ff00) >> 8);
            out1 += (unsigned char) ((val & 0x000000ff));
        }
        sdeb += SoapHelp::i2s(val) + " ";
    }
    LOGDEB("OHPlaylist::translateIdArray: current ids: " << sdeb << endl);
    return base64_encode(out1);
}

bool OHPlaylist::makeIdArray(string& out)
{
    //LOGDEB1("OHPlaylist::makeIdArray\n");
    const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();

    if (mpds.qvers == m_mpdqvers) {
        out = m_idArrayCached;
        // Mpd queue did not change: no need to look at the metadata cache
        //LOGDEB("OHPlaylist::makeIdArray: mpd queue did not change" << endl);
        // Update the current song anyway: if it's an internet radio,
        // the title may have changed with no indication from the
        // queue. Only do this if the metadata originated from mpd of
        // course...
        if (mpds.songid != -1) {
            auto it = m_metacache.find(mpds.currentsong.uri);
            if (it != m_metacache.end() && 
                it->second.find("<orig>mpd</orig>") != string::npos) {
                m_metacache[mpds.currentsong.uri] = didlmake(mpds.currentsong);
            }
        }
        return true;
    }

    // Retrieve the data for current queue songs from mpd, and make an
    // ohPlaylist id array.
    vector<UpSong> vdata;
    bool ok = m_dev->m_mpdcli->getQueueData(vdata);
    if (!ok) {
        LOGERR("OHPlaylist::makeIdArray: getQueueData failed." 
               "metacache size " << m_metacache.size() << endl);
        return false;
    }

    m_idArrayCached = out = translateIdArray(vdata);
    m_mpdqvers = mpds.qvers;

    // Don't perform metadata cache maintenance if we're not active
    // (the mpd playlist belongs to e.g. the radio service). We would
    // be destroying data which we may need later.
    if (!m_active) {
        return true;
    }

    // Update metadata cache: entries not in the current list are not
    // valid any more. Also there may be entries which were added
    // through an MPD client and which don't know about, record the
    // metadata for these. We don't update the current array, but just
    // build a new cache for data about current entries.
    //
    // The songids are not preserved through mpd restarts (they
    // restart at 0) this means that the ids are not a good cache key,
    // we use the uris instead.
    unordered_map<string, string> nmeta;

    // Walk the playlist data from MPD
    for (auto usong = vdata.begin(); usong != vdata.end(); usong++) {
        auto inold = m_metacache.find(usong->uri);
        if (inold != m_metacache.end()) {
            // Entries already in the metadata array just get
            // transferred to the new array
            nmeta[usong->uri].swap(inold->second);
            m_metacache.erase(inold);
        } else {
            // Entries not in the arrays are translated from the
            // MPD data to our format. They were probably added by
            // another MPD client. 
            if (nmeta.find(usong->uri) == nmeta.end()) {
                nmeta[usong->uri] = didlmake(*usong);
                m_cachedirty = true;
                LOGDEB("OHPlaylist::makeIdArray: using mpd data for " << 
                       usong->mpdid << " uri " << usong->uri << endl);
            }
        }
    }

    for (unordered_map<string, string>::const_iterator it = m_metacache.begin();
         it != m_metacache.end(); it++) {
        LOGDEB("OHPlaylist::makeIdArray: dropping uri " << it->first << endl);
    }

    // If we added entries or there are some stale entries, the new
    // map differs, save it to cache
    if ((m_dev->m_options & UpMpd::upmpdOhMetaPersist) &&
        (!m_metacache.empty() || m_cachedirty)) {
        LOGDEB("OHPlaylist::makeIdArray: saving metacache" << endl);
        dmcacheSave(m_dev->getMetaCacheFn(), nmeta);
        m_cachedirty = false;
    }
    m_metacache = nmeta;

    return true;
}

bool OHPlaylist::makestate(unordered_map<string, string> &st)
{
    st.clear();

    const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();

    st["TransportState"] =  mpdstatusToTransportState(mpds.state);
    st["Repeat"] = SoapHelp::i2s(mpds.rept);
    st["Shuffle"] = SoapHelp::i2s(mpds.random);
    st["Id"] = mpds.songid == -1 ? "0" : SoapHelp::i2s(mpds.songid);
    st["TracksMax"] = SoapHelp::i2s(tracksmax);
    st["ProtocolInfo"] = g_protocolInfo;
    makeIdArray(st["IdArray"]);

    return true;
}

void OHPlaylist::refreshState()
{
    m_mpdqvers = -1;
    unordered_map<string, string> st;
    makestate(st);
}

void OHPlaylist::maybeWakeUp(bool ok)
{
    if (ok && m_dev)
        m_dev->loopWakeup();
}

void OHPlaylist::setActive(bool onoff)
{
    m_active = onoff;
    if (m_active) {
        m_dev->m_mpdcli->clearQueue();
        m_dev->m_mpdcli->restoreState(m_mpdsavedstate);
        refreshState();
        maybeWakeUp(true);
    } else {
        m_dev->m_mpdcli->saveState(m_mpdsavedstate);
        iStop();
    }
}

int OHPlaylist::play(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::play" << endl);
    if (!m_active && m_dev->m_ohpr) {
        m_dev->m_ohpr->iSetSourceIndexByName("Playlist");
    }
    m_dev->m_mpdcli->consume(false);
    m_dev->m_mpdcli->single(false);
    bool ok = m_dev->m_mpdcli->play();
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::pause(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::pause" << endl);
    bool ok = m_dev->m_mpdcli->pause(true);
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::iStop()
{
    bool ok = m_dev->m_mpdcli->stop();
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}
int OHPlaylist::stop(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::stop" << endl);
    return iStop();
}

int OHPlaylist::next(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::next" << endl);
    bool ok = m_dev->m_mpdcli->next();
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::previous(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::previous" << endl);
    bool ok = m_dev->m_mpdcli->previous();
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::setRepeat(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::setRepeat" << endl);
    bool onoff;
    bool ok = sc.get("Value", &onoff);
    if (ok) {
        ok = m_dev->m_mpdcli->repeat(onoff);
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::repeat(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::repeat" << endl);
    const MpdStatus &mpds =  m_dev->getMpdStatusNoUpdate();
    data.addarg("Value", mpds.rept? "1" : "0");
    return UPNP_E_SUCCESS;
}

int OHPlaylist::setShuffle(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::setShuffle" << endl);
    bool onoff;
    bool ok = sc.get("Value", &onoff);
    if (ok) {
        // Note that mpd shuffle shuffles the playlist, which is different
        // from playing at random
        ok = m_dev->m_mpdcli->random(onoff);
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::shuffle(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::shuffle" << endl);
    const MpdStatus &mpds =  m_dev->getMpdStatusNoUpdate();
    data.addarg("Value", mpds.random ? "1" : "0");
    return UPNP_E_SUCCESS;
}

int OHPlaylist::seekSecondAbsolute(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::seekSecondAbsolute" << endl);
    int seconds;
    bool ok = sc.get("Value", &seconds);
    if (ok) {
        ok = m_dev->m_mpdcli->seek(seconds);
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::seekSecondRelative(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::seekSecondRelative" << endl);
    int seconds;
    bool ok = sc.get("Value", &seconds);
    if (ok) {
        const MpdStatus &mpds =  m_dev->getMpdStatusNoUpdate();
        bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
            (mpds.state == MpdStatus::MPDS_PAUSE);
        if (is_song) {
            seconds += mpds.songelapsedms / 1000;
            ok = m_dev->m_mpdcli->seek(seconds);
        } else {
            ok = false;
        }
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::transportState(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::transportState" << endl);
    const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();
    string tstate;
    switch(mpds.state) {
    case MpdStatus::MPDS_PLAY: 
        tstate = "Playing";
        break;
    case MpdStatus::MPDS_PAUSE: 
        tstate = "Paused";
        break;
    default:
        tstate = "Stopped";
    }
    data.addarg("Value", tstate);
    return UPNP_E_SUCCESS;
}

// Skip to track specified by Id
int OHPlaylist::seekId(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::seekId" << endl);
    if (!m_active) {
        // If I'm not active, the ids in the playlist are those of
        // another service (e.g. radio). If I activate myself and
        // restore the playlist, the mpd ids are going to be different
        // from what the caller may have in store. This just can't
        // work as long as we use mpd ids directly.
        LOGERR("OHPlaylist::seekId: not active" << endl);
        return UPNP_E_INTERNAL_ERROR;
    }
    int id;
    bool ok = sc.get("Value", &id);
    if (ok) {
        ok = m_dev->m_mpdcli->playId(id);
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

// Skip to track with specified index 
int OHPlaylist::seekIndex(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::seekIndex" << endl);

    // Unlike seekid, this should work as the indices are restored by
    // mpdcli restorestate
    if (!m_active && m_dev->m_ohpr) {
        m_dev->m_ohpr->iSetSourceIndexByName("Playlist");
    }
    int pos;
    bool ok = sc.get("Value", &pos);
    if (ok) {
        ok = m_dev->m_mpdcli->play(pos);
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

// Return current Id
int OHPlaylist::id(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::id" << endl);
    if (!m_active) {
        LOGERR("OHPlaylist::id: not active" << endl);
        return UPNP_E_INTERNAL_ERROR;
    }

    const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();
    data.addarg("Value", mpds.songid == -1 ? "0" : SoapHelp::i2s(mpds.songid));
    return UPNP_E_SUCCESS;
}

bool OHPlaylist::cacheFind(const string& uri, string& meta)
{
    auto cached = m_metacache.find(uri);
    if (cached != m_metacache.end()) {
        meta = cached->second;
        return true;
    }
    return false;
}

// Report the uri and metadata for a given track id. 
// Returns a 800 fault code if the given id is not in the playlist. 
int OHPlaylist::ohread(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        // See comment in seekId()
        LOGERR("OHPlaylist::read: not active" << endl);
        return UPNP_E_INTERNAL_ERROR;
    }
    int id;
    bool ok = sc.get("Id", &id);
    LOGDEB("OHPlaylist::ohread id " << id << endl);
    UpSong song;
    if (ok) {
        ok = m_dev->m_mpdcli->statSong(song, id, true);
    }
    if (ok) {
        auto cached = m_metacache.find(song.uri);
        string metadata;
        if (cached != m_metacache.end()) {
            metadata = cached->second;
        } else {
            metadata = didlmake(song);
            m_metacache[song.uri] = metadata;
            m_cachedirty = true;
        }
        data.addarg("Uri", song.uri);
        data.addarg("Metadata", metadata);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

// Given a space separated list of track Id's, report their associated
// uri and metadata in the following xml form:
//
//  <TrackList>
//    <Entry>
//      <Id></Id>
//      <Uri></Uri>
//      <Metadata></Metadata>
//    </Entry>
//  </TrackList>
//
// Any ids not in the playlist are ignored. 
int OHPlaylist::readList(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        // See comment in seekId()
        LOGERR("OHPlaylist::readList: not active" << endl);
        return UPNP_E_INTERNAL_ERROR;
    }
    string sids;
    bool ok = sc.get("IdList", &sids);
    LOGDEB("OHPlaylist::readList: [" << sids << "]" << endl);
    vector<string> ids;
    string out("<TrackList>");
    if (ok) {
        stringToTokens(sids, ids);
        for (auto it = ids.begin(); it != ids.end(); it++) {
            int id = atoi(it->c_str());
            if (id == -1) {
                // Lumin does this??
                LOGDEB("OHPlaylist::readlist: request for id -1" << endl);
                continue;
            }
            UpSong song;
            if (!m_dev->m_mpdcli->statSong(song, id, true)) {
                LOGDEB("OHPlaylist::readList:stat failed for " << id << endl);
                continue;
            }
            auto mit = m_metacache.find(song.uri);
            string metadata;
            if (mit != m_metacache.end()) {
                //LOGDEB("OHPlaylist::readList: meta for id " << id << " uri "
                // << song.uri << " found in cache " << endl);
                metadata = SoapHelp::xmlQuote(mit->second);
            } else {
                //LOGDEB("OHPlaylist::readList: meta for id " << id << " uri "
                // << song.uri << " not found " << endl);
                metadata = didlmake(song);
                m_metacache[song.uri] = metadata;
                m_cachedirty = true;
                metadata = SoapHelp::xmlQuote(metadata);
            }
            out += "<Entry><Id>";
            out += SoapHelp::xmlQuote(it->c_str());
            out += "</Id><Uri>";
            out += SoapHelp::xmlQuote(song.uri);
            out += "</Uri><Metadata>";
            out += metadata;
            out += "</Metadata></Entry>";
        }
        out += "</TrackList>";
        //LOGDEB1("OHPlaylist::readList: out: [" << out << "]" << endl);
        data.addarg("TrackList", out);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

bool OHPlaylist::ireadList(const vector<int>& ids, vector<UpSong>& songs)
{
    for (auto it = ids.begin(); it != ids.end(); it++) {
        UpSong song;
        if (!m_dev->m_mpdcli->statSong(song, *it, true)) {
            LOGDEB("OHPlaylist::readList:stat failed for " << *it << endl);
            continue;
        }
        songs.push_back(song);
    }
    return true;
}

// Adds the given uri and metadata as a new track to the playlist. 
// Set the AfterId argument to 0 to insert a track at the start of the
// playlist.
// Reports a 800 fault code if AfterId is not 0 and doesn’t appear in
// the playlist.
// Reports a 801 fault code if the playlist is full (i.e. already
// contains TracksMax tracks).
int OHPlaylist::insert(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::insert" << endl);
    int afterid;
    string uri, metadata;
    bool ok = sc.get("AfterId", &afterid);
    ok = ok && sc.get("Uri", &uri);
    if (ok)
        ok = ok && sc.get("Metadata", &metadata);

    if (!m_active) {
        // See comment in seekId()
        // It's not clear if special-casing afterId == 0 is a good
        // idea because it makes the device appear even more
        // unpredictable. Otoh, it allows Bubble (basic, not DS) to
        // switch to playlist by just adding tracks.
        if (afterid == 0 && m_dev->m_ohpr) {
            m_dev->m_ohpr->iSetSourceIndexByName("Playlist");
        } else {
            LOGERR("OHPlaylist::insert: not active" << endl);
            return UPNP_E_INTERNAL_ERROR;
        }
    }

    LOGDEB("OHPlaylist::insert: afterid " << afterid << " Uri " <<
           uri << " Metadata " << metadata << endl);
    if (ok) {
        int newid;
        ok = insertUri(afterid, uri, metadata, &newid);
        if (ok) {
            data.addarg("NewId", SoapHelp::i2s(newid));
            LOGDEB("OHPlaylist::insert: new id: " << newid << endl);
        }
    }
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

bool OHPlaylist::insertUri(int afterid, const string& uri, 
                           const string& metadata, int *newid)
{
    LOGDEB1("OHPlaylist::insertUri: " << uri << endl);
    if (!m_active) {
        LOGERR("OHPlaylist::insertUri: not active" << endl);
        return UPNP_E_INTERNAL_ERROR;
    }
    UpSong metaformpd;
    if (!uMetaToUpSong(metadata, &metaformpd)) {
        LOGERR("OHPlaylist::insert: failed to parse metadata " << " Uri [" 
               << uri << "] Metadata [" << metadata << "]" << endl);
        return false;
    }
    int id = m_dev->m_mpdcli->insertAfterId(uri, afterid, metaformpd);
    if (id != -1) {
        m_metacache[uri] = metadata;
        m_cachedirty = true;
        m_mpdqvers = -1;
        if (newid)
            *newid = id;
        return true;
    } 
    LOGERR("OHPlaylist::insertUri: mpd error" << endl);
    return false;
}

int OHPlaylist::deleteId(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::deleteId" << endl);
    if (!m_active) {
        // See comment in seekId()
        LOGERR("OHPlaylist::deleteId: not active" << endl);
        return UPNP_E_INTERNAL_ERROR;
    }
    int id;
    bool ok = sc.get("Value", &id);
    if (ok) {
        const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();
        if (mpds.songid == id) {
            // MPD skips to the next track if the current one is removed,
            // but I think it's better to stop in this case
            m_dev->m_mpdcli->stop();
        }
        ok = m_dev->m_mpdcli->deleteId(id);
        m_mpdqvers = -1;
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::deleteAll(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::deleteAll" << endl);
    if (!m_active && m_dev->m_ohpr) {
        m_dev->m_ohpr->iSetSourceIndexByName("Playlist");
    }
    bool ok = m_dev->m_mpdcli->clearQueue();
    m_mpdqvers = -1;
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::tracksMax(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::tracksMax" << endl);
    data.addarg("Value", SoapHelp::i2s(tracksmax));
    return UPNP_E_SUCCESS;
}

// Returns current list of id as array of big endian 32bits integers,
// base-64-encoded. 
int OHPlaylist::idArray(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::idArray" << endl);
    if (!m_active) {
        // See comment in seekId()
        LOGERR("OHPlaylist::idArray: not active" << endl);
        return UPNP_E_INTERNAL_ERROR;
    }
    string idarray;
    int token;
    if (iidArray(idarray, &token)) {
        data.addarg("Token", SoapHelp::i2s(token));
        data.addarg("Array", idarray);
        return UPNP_E_SUCCESS;
    }
    return UPNP_E_INTERNAL_ERROR;
}

bool OHPlaylist::iidArray(string& idarray, int *token)
{
    LOGDEB("OHPlaylist::idArray (internal)" << endl);
    if (makeIdArray(idarray)) {
        const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();
        LOGDEB("OHPlaylist::idArray: qvers " << mpds.qvers << endl);
        if (token)
            *token = mpds.qvers;
        return true;
    }
    return false;
}

bool OHPlaylist::urlMap(unordered_map<int, string>& umap)
{
    //LOGDEB1("OHPlaylist::urlMap\n");
    string sarray; 
    if (iidArray(sarray, 0)) {
        vector<int> ids;
        if (ohplIdArrayToVec(sarray, &ids)) {
            vector<UpSong> songs;
            if (ireadList(ids, songs)) {
                for (auto it = songs.begin(); it != songs.end(); it++) {
                    umap[it->mpdid] = it->uri;
                }
                return true;
            }
        }
    }
    return false;
}

// Check if id array changed since last call (which returned a gen token)
int OHPlaylist::idArrayChanged(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::idArrayChanged" << endl);
    int qvers;
    bool ok = sc.get("Token", &qvers);
    const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();
    
    LOGDEB("OHPlaylist::idArrayChanged: query qvers " << qvers << 
           " mpd qvers " << mpds.qvers << endl);

    // Bool indicating if array changed
    int val = mpds.qvers == qvers;
    data.addarg("Value", SoapHelp::i2s(val));

    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::protocolInfo(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::protocolInfo" << endl);
    data.addarg("Value", g_protocolInfo);
    return UPNP_E_SUCCESS;
}
