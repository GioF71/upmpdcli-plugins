/* Copyright (C) 2014 J.F.Dockes
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation; either version 2.1 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program; if not, write to the
 * Free Software Foundation, Inc.,
 * 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#include "config.h"

#include "ohplaylist.hxx"

#include <stdlib.h>

#include <functional>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

#include "libupnpp/base64.hxx"
#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"
#include "libupnpp/upnpavutils.hxx"

#include "ohmetacache.hxx"
#include "mpdcli.hxx"
#include "upmpd.hxx"
#include "upmpdutils.hxx"
#include "smallut.h"
#include "ohproduct.hxx"
#include "protocolinfo.hxx"
#include "pathut.h"
#include "conftree.h"
#include "ohcredentials.hxx"

using namespace std;
using namespace std::placeholders;

static const string sTpProduct("urn:av-openhome-org:service:Playlist:1");
static const string sIdProduct("urn:av-openhome-org:serviceId:Playlist");

// This is an undocumented configuration variable for people who
// really want to keep the mpd playlist 'consume' attribute under
// mpc/mpd control. If set we don't touch it.
static bool keepconsume;

// Playlist is the default oh service, so it's active when starting up
OHPlaylist::OHPlaylist(UpMpd *dev,  UpMpdOpenHome *udev, unsigned int cssleep)
    : OHService(sTpProduct, sIdProduct, "OHPlaylist.xml", dev, udev),
      m_active(true), m_cachedirty(false), m_mpdqvers(-1)
{
    udev->addActionMapping(this, "Play", 
                          bind(&OHPlaylist::play, this, _1, _2));
    udev->addActionMapping(this, "Pause", 
                          bind(&OHPlaylist::pause, this, _1, _2));
    udev->addActionMapping(this, "Stop", 
                          bind(&OHPlaylist::stop, this, _1, _2));
    udev->addActionMapping(this, "Next", 
                          bind(&OHPlaylist::next, this, _1, _2));
    udev->addActionMapping(this, "Previous", 
                          bind(&OHPlaylist::previous, this, _1, _2));
    udev->addActionMapping(this, "SetRepeat",
                          bind(&OHPlaylist::setRepeat, this, _1, _2));
    udev->addActionMapping(this, "Repeat",
                          bind(&OHPlaylist::repeat, this, _1, _2));
    udev->addActionMapping(this, "SetShuffle",
                          bind(&OHPlaylist::setShuffle, this, _1, _2));
    udev->addActionMapping(this, "Shuffle",
                          bind(&OHPlaylist::shuffle, this, _1, _2));
    udev->addActionMapping(this, "SeekSecondAbsolute",
                          bind(&OHPlaylist::seekSecondAbsolute, this, _1, _2));
    udev->addActionMapping(this, "SeekSecondRelative",
                          bind(&OHPlaylist::seekSecondRelative, this, _1, _2));
    udev->addActionMapping(this, "SeekId",
                          bind(&OHPlaylist::seekId, this, _1, _2));
    udev->addActionMapping(this, "SeekIndex",
                          bind(&OHPlaylist::seekIndex, this, _1, _2));
    udev->addActionMapping(this, "TransportState",
                          bind(&OHPlaylist::transportState, this, _1, _2));
    udev->addActionMapping(this, "Id",
                          bind(&OHPlaylist::id, this, _1, _2));
    udev->addActionMapping(this, "Read",
                          bind(&OHPlaylist::ohread, this, _1, _2));
    udev->addActionMapping(this, "ReadList",
                          bind(&OHPlaylist::readList, this, _1, _2));
    udev->addActionMapping(this, "Insert",
                          bind(&OHPlaylist::insert, this, _1, _2));
    udev->addActionMapping(this, "DeleteId",
                          bind(&OHPlaylist::deleteId, this, _1, _2));
    udev->addActionMapping(this, "DeleteAll",
                          bind(&OHPlaylist::deleteAll, this, _1, _2));
    udev->addActionMapping(this, "TracksMax",
                          bind(&OHPlaylist::tracksMax, this, _1, _2));
    udev->addActionMapping(this, "IdArray",
                          bind(&OHPlaylist::idArray, this, _1, _2));
    udev->addActionMapping(this, "IdArrayChanged",
                          bind(&OHPlaylist::idArrayChanged, this, _1, _2));
    udev->addActionMapping(this, "ProtocolInfo",
                          bind(&OHPlaylist::protocolInfo, this, _1, _2));
    
    if ((dev->getopts().options & UpMpd::upmpdOhMetaPersist)) {
        dmcacheSetOpts(cssleep);
        if (!dmcacheRestore(dev->getMetaCacheFn(), m_metacache)) {
            LOGERR("ohPlaylist: cache restore failed" << endl);
        } else {
            LOGDEB("ohPlaylist: cache restore done" << endl);
        }
    }
    keepconsume = g_config->getBool("keepconsume", false);
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
        // Mpd queue did not change, but check the current song
        // anyway: if we are playing a radio stream, the title may
        // have changed with no indication from the queue.
        if (mpds.songid != -1) {
            auto it = m_metacache.find(mpds.currentsong.rsrc.uri);
            // "not found" should not happen: queue should have been
            // saved. Only do something if the metadata originated
            // from mpd (the <orig> tag is inserted by UpSong::didl() if
            // there is no UPnP Id).
            if (it != m_metacache.end() &&
                it->second.find("<orig>mpd</orig>") != string::npos) {
                string nmeta = didlmake(mpds.currentsong);
                if (!metaSameTitle(nmeta, it->second)) {
                    // Metadata changed under us for the same id.
                    // Force the CP to flush its metadata by emitting
                    // an empty idarray. On the next event, with no
                    // title change, we will emit the real idarray,
                    // and the CP will update.
                    LOGDEB2("OHPLaylist:makeIdArray: meta change-under. OLD\n"
                            << it->second << "NEW\n" << nmeta << endl);
                    out = translateIdArray(vector<UpSong>());
                    it->second = nmeta;
                }
            }
        }
        return true;
    }

    // Retrieve the data for current queue songs from mpd, and make an
    // ohPlaylist id array.
    vector<UpSong> vdata;
    bool ok;
    {
        auto lock = m_dev->mpdlock();
        ok = m_dev->getmpdcli()->getQueueData(vdata);
    }
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
    for (const auto& usong : vdata) {
        auto inold = m_metacache.find(usong.rsrc.uri);
        if (inold != m_metacache.end()) {
            // Entries already in the metadata array just get
            // transferred to the new array
            nmeta[usong.rsrc.uri].swap(inold->second);
            m_metacache.erase(inold);
        } else {
            // Entries not in the arrays are translated from the
            // MPD data to our format. They were probably added by
            // another MPD client. 
            if (nmeta.find(usong.rsrc.uri) == nmeta.end()) {
                nmeta[usong.rsrc.uri] = didlmake(usong);
                m_cachedirty = true;
                LOGDEB("OHPlaylist::makeIdArray: using mpd data for " << 
                       usong.mpdid << " uri " << usong.rsrc.uri << endl);
            }
        }
    }

    for (const auto entry : m_metacache) {
        LOGDEB("OHPlaylist::makeIdArray: dropping uri " << entry.first << endl);
    }

    // If we added entries or there are some stale entries, the new
    // map differs, save it to cache
    if ((m_dev->getopts().options & UpMpd::upmpdOhMetaPersist) &&
        (!m_metacache.empty() || m_cachedirty)) {
        LOGDEB("OHPlaylist::makeIdArray: saving metacache" << endl);
        dmcacheSave(m_dev->getMetaCacheFn(), nmeta);
        m_cachedirty = false;
    }
    m_metacache = nmeta;

    return true;
}

// (private)
int OHPlaylist::idFromOldId(int oldid)
{
    string uri;
    for (const auto& entry: m_mpdsavedstate.queue) {
        if (entry.mpdid == oldid) {
            uri = entry.rsrc.uri;
            break;
        }
    }
    if (uri.empty()) {
        LOGERR("OHPlaylist::idFromOldId: " << oldid << " not found\n");
        return -1;
    }
    vector<UpSong> vdata;
    {
        auto lock = m_dev->mpdlock();
        if (!m_dev->getmpdcli()->getQueueData(vdata)) {
            LOGERR("OHPlaylist::idFromUri: getQueueData failed\n");
            return -1;
        }
    }
    for (const auto& entry: vdata) {
        if (!entry.rsrc.uri.compare(uri)) {
            return entry.mpdid;
        }
    }
    LOGERR("OHPlaylist::idFromOldId: uri for " << oldid << " not found\n");
    return -1;
}

bool OHPlaylist::makestate(unordered_map<string, string> &st)
{
    if (m_active) {
        st.clear();

        const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();

        st["TransportState"] =  mpdstatusToTransportState(mpds.state);
        st["Repeat"] = SoapHelp::i2s(mpds.rept);
        st["Shuffle"] = SoapHelp::i2s(mpds.random);
        st["Id"] = mpds.songid == -1 ? "0" : SoapHelp::i2s(mpds.songid);
        st["TracksMax"] = SoapHelp::i2s(tracksmax);
        st["ProtocolInfo"] = Protocolinfo::the()->gettext();
        makeIdArray(st["IdArray"]);
    } else {
        st = m_upnpstate;
        st["TransportState"] =  "Stopped";
    }

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
        m_udev->loopWakeup();
}

void OHPlaylist::setActive(bool onoff)
{
    auto lock = m_dev->mpdlock();
    if (onoff) {
        m_dev->getmpdcli()->clearQueue();
        m_dev->getmpdcli()->restoreState(m_mpdsavedstate);
        if (!keepconsume)
            m_dev->getmpdcli()->consume(false);
        m_dev->getmpdcli()->single(false);
        refreshState();
        maybeWakeUp(true);
        m_active = true;
    } else {
        m_mpdqvers = -1;
        makestate(m_upnpstate);
        m_dev->getmpdcli()->saveState(m_mpdsavedstate);
        iStop();
        m_active = false;
    }
}

int OHPlaylist::play(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::play" << endl);
    if (!m_active && m_udev->getohpr()) {
        m_udev->getohpr()->iSetSourceIndexByName("Playlist");
    }
    bool ok;
    {
        auto lock = m_dev->mpdlock();
        if (!keepconsume) 
            m_dev->getmpdcli()->consume(false);
        m_dev->getmpdcli()->single(false);
        ok = m_dev->getmpdcli()->play();
    }
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UpnpService::UPNP_ACTION_FAILED;
}

int OHPlaylist::pause(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::pause" << endl);
    bool ok;
    {
        auto lock = m_dev->mpdlock();
        ok = m_dev->getmpdcli()->pause(true);
    }
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::iStop()
{
    bool ok;
    {
        auto lock = m_dev->mpdlock();
        ok = m_dev->getmpdcli()->stop();
    }
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
    if (!m_active) {
        LOGERR("OHPlaylist::next: not active\n");
        return 409; // HTTP Conflict
    }
    LOGDEB("OHPlaylist::next" << endl);
    bool ok;
    {
        auto lock = m_dev->mpdlock();
        ok = m_dev->getmpdcli()->next();
    }
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::previous(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        LOGERR("OHPlaylist::previous: not active\n");
        return 409; // HTTP Conflict
    }
    LOGDEB("OHPlaylist::previous" << endl);
    bool ok;
    {
        auto lock = m_dev->mpdlock();
        ok = m_dev->getmpdcli()->previous();
    }
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::setRepeat(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        LOGERR("OHPlaylist::setRepeat: not active\n");
        return 409; // HTTP Conflict
    }
    LOGDEB("OHPlaylist::setRepeat" << endl);
    bool onoff;
    bool ok = sc.get("Value", &onoff);
    if (ok) {
        {
            auto lock = m_dev->mpdlock();
            ok = m_dev->getmpdcli()->repeat(onoff);
        }
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::repeat(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        LOGERR("OHPlaylist::repeat: not active\n");
        return 409; // HTTP Conflict
    }
    LOGDEB("OHPlaylist::repeat" << endl);
    const MpdStatus &mpds =  m_dev->getMpdStatusNoUpdate();
    data.addarg("Value", mpds.rept? "1" : "0");
    return UPNP_E_SUCCESS;
}

int OHPlaylist::setShuffle(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        LOGERR("OHPlaylist::setShuffle: not active\n");
        return 409; // HTTP Conflict
    }
    LOGDEB("OHPlaylist::setShuffle" << endl);
    bool onoff;
    bool ok = sc.get("Value", &onoff);
    if (ok) {
        // Note that mpd shuffle shuffles the playlist, which is different
        // from playing at random
        {
            auto lock = m_dev->mpdlock();
            ok = m_dev->getmpdcli()->random(onoff);
        }
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::shuffle(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        LOGERR("OHPlaylist::shuffle: not active\n");
        return UPNP_E_INTERNAL_ERROR;
    }
    LOGDEB("OHPlaylist::shuffle" << endl);
    const MpdStatus &mpds =  m_dev->getMpdStatusNoUpdate();
    data.addarg("Value", mpds.random ? "1" : "0");
    return UPNP_E_SUCCESS;
}

int OHPlaylist::seekSecondAbsolute(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        LOGERR("OHPlaylist::seekSecond: not active\n");
        return UPNP_E_INTERNAL_ERROR;
    }
    LOGDEB("OHPlaylist::seekSecondAbsolute" << endl);
    int seconds;
    bool ok = sc.get("Value", &seconds);
    if (ok) {
        {
            auto lock = m_dev->mpdlock();
            ok = m_dev->getmpdcli()->seek(seconds);
        }
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::seekSecondRelative(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        LOGERR("OHPlaylist::seekSecond: not active\n");
        return UPNP_E_INTERNAL_ERROR;
    }
    LOGDEB("OHPlaylist::seekSecondRelative" << endl);
    int seconds;
    bool ok = sc.get("Value", &seconds);
    if (ok) {
        const MpdStatus &mpds =  m_dev->getMpdStatusNoUpdate();
        bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
            (mpds.state == MpdStatus::MPDS_PAUSE);
        if (is_song) {
            seconds += mpds.songelapsedms / 1000;
            {
                auto lock = m_dev->mpdlock();
                ok = m_dev->getmpdcli()->seek(seconds);
            }
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
    int id;
    if (!sc.get("Value", &id)) {
        LOGERR("OHPlaylist::seekId: no Id\n");
        return UPNP_E_INVALID_PARAM;
    }
    LOGDEB("OHPlaylist::seekId" << endl);
    if (!m_active) {
        // If I'm not active, the ids in the playlist are those of
        // another service (e.g. radio). After activating myself and
        // restoring the playlist, the input id needs to be mapped.
        m_udev->getohpr()->iSetSourceIndexByName("Playlist");
        id = idFromOldId(id);
        if (id < 0) {
            return UPNP_E_INTERNAL_ERROR;
        }
    }
    bool ok;
    {
        auto lock = m_dev->mpdlock();
        if (!keepconsume)
            m_dev->getmpdcli()->consume(false);
        m_dev->getmpdcli()->single(false);
        ok = m_dev->getmpdcli()->playId(id);
    }
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

// Skip to track with specified index 
int OHPlaylist::seekIndex(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::seekIndex" << endl);

    // Unlike seekid, this should work as the indices are restored by
    // mpdcli restorestate
    if (!m_active && m_udev->getohpr()) {
        m_udev->getohpr()->iSetSourceIndexByName("Playlist");
    }
    int pos;
    bool ok = sc.get("Value", &pos);
    if (ok) {
        {
            auto lock = m_dev->mpdlock();
            if (!keepconsume)
                m_dev->getmpdcli()->consume(false);
            m_dev->getmpdcli()->single(false);
            ok = m_dev->getmpdcli()->play(pos);
        }
        maybeWakeUp(ok);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

// Return current Id
int OHPlaylist::id(const SoapIncoming& sc, SoapOutgoing& data)
{
    if (!m_active) {
        LOGERR("OHPlaylist::id: not active" << endl);
        return 409; // HTTP Conflict
    }
    LOGDEB("OHPlaylist::id" << endl);

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
    int id;
    bool ok = sc.get("Id", &id);
    if (!ok) {
        LOGERR("OHPlaylist::ohread: no Id in params\n");
        return UPNP_E_INVALID_PARAM;
    }
    LOGDEB("OHPlaylist::ohread id " << id << endl);
    UpSong song;
    string metadata;
    if (m_active) {
        {
            auto lock = m_dev->mpdlock();
            if (!m_dev->getmpdcli()->statSong(song, id, true)) {
                LOGERR("OHPlaylist::ohread: statsong failed for " << id << endl);
                return UPNP_E_INTERNAL_ERROR;
            }
        }
        auto cached = m_metacache.find(song.rsrc.uri);
        if (cached != m_metacache.end()) {
            metadata = cached->second;
        } else {
            metadata = didlmake(song);
            m_metacache[song.rsrc.uri] = metadata;
            m_cachedirty = true;
        }
    } else {
        LOGDEB("OHPlaylist::read: not active: using saved queue\n");
        for (const auto& entry : m_mpdsavedstate.queue) {
            if (entry.mpdid == id) {
                song = entry;
                metadata = didlmake(song);
            }
        }
        if (metadata.empty()) {
            LOGDEB("OHPlaylist: id " << id << " not found\n");
            return UPNP_E_INTERNAL_ERROR;
        }
    }
    data.addarg("Uri", SoapHelp::xmlQuote(song.rsrc.uri));
    data.addarg("Metadata", metadata);
    return UPNP_E_SUCCESS;
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
            string metadata;
            UpSong song;
            if (m_active) {
                {
                    auto lock = m_dev->mpdlock();
                    if (!m_dev->getmpdcli()->statSong(song, id, true)) {
                        LOGDEB("OHPlaylist::readList:stat failed for " <<
                               id <<endl);
                        continue;
                    }
                }
                auto mit = m_metacache.find(song.rsrc.uri);
                if (mit != m_metacache.end()) {
                    LOGDEB1("OHPlaylist::readList: meta for id " << id << " uri "
                            << song.rsrc.uri << " found in cache " << endl);
                    metadata = SoapHelp::xmlQuote(mit->second);
                } else {
                    LOGDEB("OHPlaylist::readList: meta for id " << id << " uri "
                           << song.rsrc.uri << " not found " << endl);
                    metadata = didlmake(song);
                    m_metacache[song.rsrc.uri] = metadata;
                    m_cachedirty = true;
                    metadata = SoapHelp::xmlQuote(metadata);
                }
            } else {
                LOGDEB("OHPlaylist::readList: not active: using saved queue\n");
                for (const auto& entry : m_mpdsavedstate.queue) {
                    if (entry.mpdid == id) {
                        song = entry;
                        auto mit = m_metacache.find(song.rsrc.uri);
                        if (mit != m_metacache.end()) {
                            metadata = SoapHelp::xmlQuote(mit->second);
                        } else {
                            metadata = SoapHelp::xmlQuote(didlmake(song));
                        }
                    }
                }
                if (metadata.empty()) {
                    LOGDEB("OHPlaylist: id " << id << " not found\n");
                    continue;
                }
            }
            out += "<Entry><Id>";
            out += SoapHelp::xmlQuote(it->c_str());
            out += "</Id><Uri>";
            out += SoapHelp::xmlQuote(song.rsrc.uri);
            out += "</Uri><Metadata>";
            out += metadata;
            out += "</Metadata></Entry>";
        }
        out += "</TrackList>";
        LOGDEB1("OHPlaylist::readList: out: [" << out << "]" << endl);
        data.addarg("TrackList", out);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

bool OHPlaylist::ireadList(const vector<int>& ids, vector<UpSong>& songs)
{
    for (auto it = ids.begin(); it != ids.end(); it++) {
        UpSong song;
        {
            auto lock = m_dev->mpdlock();
            if (!m_dev->getmpdcli()->statSong(song, *it, true)) {
                LOGDEB("OHPlaylist::readList:stat failed for " << *it << endl);
                continue;
            }
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

    if (!ok) {
        LOGERR("OHPlaylist::insert: no AfterId, Uri or Metadata parameter\n");
        return UPNP_E_INVALID_PARAM;
    }

    // Maybe transform a qobuz:// or tidal:// uri if we're doing this
    // isStreaming is used to disable content format check in this
    // case (there is no valid protocolinfo in general).
    bool isStreaming;
    if (!OHCredsMaybeMorphSpecialUri(uri, isStreaming)) {
        LOGERR("OHPlaylist::insert: bad uri: " << uri << endl);
        return UPNP_E_INVALID_PARAM;
    }
        
    if (!m_active) {
        m_udev->getohpr()->iSetSourceIndexByName("Playlist");
        afterid = idFromOldId(afterid);
        if (afterid < 0) {
            return UPNP_E_INTERNAL_ERROR;
        }
    }

    LOGDEB("OHPlaylist::insert: afterid " << afterid << " Uri " <<
           uri << " Metadata " << metadata << endl);

    int newid;
    ok = insertUri(afterid, uri, metadata, &newid, isStreaming);
    if (ok) {
        data.addarg("NewId", SoapHelp::i2s(newid));
        LOGDEB("OHPlaylist::insert: new id: " << newid << endl);
    }
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

bool OHPlaylist::insertUri(int afterid, const string& uri, 
                           const string& metadata, int *newid, bool nocheck)
{
    LOGDEB1("OHPlaylist::insertUri: " << uri << endl);
    if (!m_active) {
        LOGERR("OHPlaylist::insertUri: not active" << endl);
        m_udev->getohpr()->iSetSourceIndexByName("Playlist");
        return false;
    }

    UpSong metaformpd;
    if (!m_dev->checkContentFormat(uri, metadata, &metaformpd, nocheck)) {
        LOGERR("OHPlaylist::insertUri: unsupported format: uri " << uri <<
               " metadata " << metadata);
        return false;
    }
    int id;
    {
        auto lock = m_dev->mpdlock();
        id = m_dev->getmpdcli()->insertAfterId(uri, afterid, metaformpd);
    }
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
    int id;
    if (!sc.get("Value", &id)) {
        LOGERR("OHPlaylist::deleteId: no Id param\n");
        return UPNP_E_INVALID_PARAM;
    }
    if (!m_active) {
        m_udev->getohpr()->iSetSourceIndexByName("Playlist");
        id = idFromOldId(id);
        if (id < 0) {
            // Error was logged by idFromOldId
            return UPNP_E_INTERNAL_ERROR;
        }
    }
    LOGDEB("OHPlaylist::deleteId: " << id << endl);
    const MpdStatus &mpds = m_dev->getMpdStatus();
    bool ok;
    {
        auto lock = m_dev->mpdlock();
        if (mpds.songid == id) {
            // MPD skips to the next track if the current one is removed,
            // but I think it's better to stop in this case
            m_dev->getmpdcli()->stop();
        }
        ok = m_dev->getmpdcli()->deleteId(id);
    }
    m_mpdqvers = -1;
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHPlaylist::deleteAll(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::deleteAll" << endl);
    if (!m_active && m_udev->getohpr()) {
        m_udev->getohpr()->iSetSourceIndexByName("Playlist");
    }
    bool ok;
    {
        auto lock = m_dev->mpdlock();
        ok = m_dev->getmpdcli()->clearQueue();
    }
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


bool OHPlaylist::iidArray(string& idarray, int *token)
{
    LOGDEB("OHPlaylist::idArray (internal)" << endl);
    unordered_map<string, string> st;
    makestate(st);
    idarray = st["IdArray"];
    if (token) {
        if (m_active) {
            const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();
            LOGDEB("OHPlaylist::idArray: qvers " << mpds.qvers << endl);
            *token = mpds.qvers;
        } else {
            *token = 0;
        }
    }
    return true;
}


// Returns current list of id as array of big endian 32bits integers,
// base-64-encoded. 
int OHPlaylist::idArray(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHPlaylist::idArray" << endl);
    string idarray;
    int token;
    if (iidArray(idarray, &token)) {
        data.addarg("Token", SoapHelp::i2s(token));
        data.addarg("Array", idarray);
        return UPNP_E_SUCCESS;
    }
    return UPNP_E_INTERNAL_ERROR;
}


bool OHPlaylist::urlMap(unordered_map<int, string>& umap)
{
    LOGDEB1("OHPlaylist::urlMap\n");
    string sarray; 
    if (iidArray(sarray, 0)) {
        vector<int> ids;
        if (ohplIdArrayToVec(sarray, &ids)) {
            vector<UpSong> songs;
            if (ireadList(ids, songs)) {
                for (auto it = songs.begin(); it != songs.end(); it++) {
                    umap[it->mpdid] = it->rsrc.uri;
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
    data.addarg("Value", Protocolinfo::the()->gettext());
    return UPNP_E_SUCCESS;
}
