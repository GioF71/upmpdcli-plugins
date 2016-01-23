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

#include "avtransport.hxx"

#include <upnp/upnp.h>                  // for UPNP_E_SUCCESS, etc

#include <functional>                   // for _Bind, bind, _1, _2
#include <iostream>                     // for operator<<, etc
#include <map>                          // for map, map<>::const_iterator
#include <utility>                      // for pair

#include "libupnpp/log.hxx"             // for LOGDEB, LOGDEB1, LOGERR
#include "libupnpp/soaphelp.hxx"        // for SoapOutgoing, SoapIncoming, etc
#include "libupnpp/upnpavutils.hxx"     // for upnpduration, etc

#include "mpdcli.hxx"                   // for MpdStatus, MPDCli, etc
#include "ohplaylist.hxx"               // for OHPlaylist
#include "upmpd.hxx"                    // for UpMpd, etc
#include "upmpdutils.hxx"               // for didlmake, mapget

// For testing upplay with a dumb renderer.
// #define NO_SETNEXT

using namespace std;
using namespace std::placeholders;

static const string sIdTransport("urn:upnp-org:serviceId:AVTransport");
static const string sTpTransport("urn:schemas-upnp-org:service:AVTransport:1");

UpMpdAVTransport::UpMpdAVTransport(UpMpd *dev, bool noev)
    : UpnpService(sTpTransport, sIdTransport, dev, noev), m_dev(dev), m_ohp(0)
{
    m_dev->addActionMapping(this,"SetAVTransportURI", 
                            bind(&UpMpdAVTransport::setAVTransportURI, 
                                 this,_1,_2, false));
    m_dev->addActionMapping(this,"SetNextAVTransportURI", 
                            bind(&UpMpdAVTransport::setAVTransportURI, 
                                 this,_1, _2, true));
    m_dev->addActionMapping(this,"GetPositionInfo", 
                            bind(&UpMpdAVTransport::getPositionInfo, 
                                 this, _1, _2));
    m_dev->addActionMapping(this,"GetTransportInfo", 
                            bind(&UpMpdAVTransport::getTransportInfo, 
                                 this, _1, _2));
    m_dev->addActionMapping(this,"GetMediaInfo", 
                            bind(&UpMpdAVTransport::getMediaInfo, 
                                 this, _1, _2));
    m_dev->addActionMapping(this,"GetDeviceCapabilities", 
                            bind(&UpMpdAVTransport::getDeviceCapabilities, 
                                 this, _1, _2));
    m_dev->addActionMapping(this,"SetPlayMode", 
                            bind(&UpMpdAVTransport::setPlayMode, this, _1, _2));
    m_dev->addActionMapping(this,"GetTransportSettings", 
                            bind(&UpMpdAVTransport::getTransportSettings, 
                                 this, _1, _2));
    m_dev->addActionMapping(this,"GetCurrentTransportActions", 
                            bind(&UpMpdAVTransport::getCurrentTransportActions,
                                 this,_1,_2));
    m_dev->addActionMapping(this,"Stop", bind(&UpMpdAVTransport::playcontrol, 
                                         this, _1, _2, 0));
    m_dev->addActionMapping(this,"Play", bind(&UpMpdAVTransport::playcontrol, 
                                         this, _1, _2, 1));
    m_dev->addActionMapping(this,"Pause", 
                            bind(&UpMpdAVTransport::playcontrol, 
                                 this, _1, _2, 2));
    m_dev->addActionMapping(this,"Seek", bind(&UpMpdAVTransport::seek, 
                                         this, _1, _2));

    // should we get rid of those ? They don't make sense for us
    m_dev->addActionMapping(this, "Next", bind(&UpMpdAVTransport::seqcontrol, 
                                               this, _1, _2, 0));
    m_dev->addActionMapping(this, "Previous", 
                            bind(&UpMpdAVTransport::seqcontrol, 
                                 this, _1, _2, 1));

//    dev->m_mpdcli->consume(true);
#ifdef NO_SETNEXT
    // If no setnext, fake stopping at each track
    m_dev->m_mpdcli->single(true);
#endif
}

// Translate MPD mode flags to UPnP Play mode
static string mpdsToPlaymode(const MpdStatus& mpds)
{
    string playmode = "NORMAL";
    if (!mpds.rept && mpds.random && !mpds.single)
        playmode = "SHUFFLE";
    else if (mpds.rept && !mpds.random && mpds.single)
        playmode = "REPEAT_ONE";
    else if (mpds.rept && !mpds.random && !mpds.single)
        playmode = "REPEAT_ALL";
    else if (mpds.rept && mpds.random && !mpds.single)
        playmode = "RANDOM";
    else if (!mpds.rept && !mpds.random && mpds.single)
        playmode = "DIRECT_1";
    return playmode;
}

// AVTransport eventing
// 
// Some state variables do not generate events and must be polled by
// the control point: RelativeTimePosition AbsoluteTimePosition
// RelativeCounterPosition AbsoluteCounterPosition.
// This leaves us with:
//    TransportState
//    TransportStatus
//    PlaybackStorageMedium
//    PossiblePlaybackStorageMedia
//    RecordStorageMedium
//    PossibleRecordStorageMedia
//    CurrentPlayMode
//    TransportPlaySpeed
//    RecordMediumWriteStatus
//    CurrentRecordQualityMode
//    PossibleRecordQualityModes
//    NumberOfTracks
//    CurrentTrack
//    CurrentTrackDuration
//    CurrentMediaDuration
//    CurrentTrackMetaData
//    CurrentTrackURI
//    AVTransportURI
//    AVTransportURIMetaData
//    NextAVTransportURI
//    NextAVTransportURIMetaData
//    RelativeTimePosition
//    AbsoluteTimePosition
//    RelativeCounterPosition
//    AbsoluteCounterPosition
//    CurrentTransportActions
//
// To be all bundled inside:    LastChange

// Translate MPD state to UPnP AVTransport state variables
bool UpMpdAVTransport::tpstateMToU(unordered_map<string, string>& status)
{
    const MpdStatus &mpds =  m_dev->getMpdStatus();
    //DEBOUT << "UpMpdAVTransport::tpstateMToU: curpos: " << mpds.songpos <<
    //   " qlen " << mpds.qlen << endl;
    bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
        (mpds.state == MpdStatus::MPDS_PAUSE);

    string tstate("STOPPED");
    string tactions("Next,Previous");
    switch(mpds.state) {
    case MpdStatus::MPDS_PLAY: 
        tstate = "PLAYING"; 
        tactions += ",Pause,Stop,Seek";
        break;
    case MpdStatus::MPDS_PAUSE: 
        tstate = "PAUSED_PLAYBACK"; 
        tactions += ",Play,Stop,Seek";
        break;
    default:
        tactions += ",Play";
    }
    status["TransportState"] = tstate;
    status["CurrentTransportActions"] = tactions;
    status["TransportStatus"] = m_dev->m_mpdcli->ok() ? "OK" : "ERROR_OCCURRED";
    status["TransportPlaySpeed"] = "1";

    const string& uri = mpds.currentsong.uri;

    // MPD may have switched to the next track, or may be playing
    // something else altogether if some other client told it to
    if (!uri.compare(m_nextUri)) {
        m_uri = m_nextUri;
        m_curMetadata = m_nextMetadata;
        m_nextUri.clear();
        m_nextMetadata.clear();
    } else if (uri.compare(m_uri)) {
        // Someone else is controlling mpd. Maybe our own ohplaylist.
        m_nextMetadata.clear();
        m_nextUri.clear();
        m_uri = uri;
        if (!m_ohp || !m_ohp->cacheFind(uri, m_curMetadata)) {
            m_curMetadata = didlmake(mpds.currentsong);
        }
    }

    status["CurrentTrack"] = "1";
    status["CurrentTrackURI"] = uri;

    // If we own the queue, just use the metadata from the content directory.
    // else, try to make up something from mpd status.
    if ((m_dev->m_options & UpMpd::upmpdOwnQueue)) {
        status["CurrentTrackMetaData"] = is_song ? m_curMetadata : "";
    } else {
        status["CurrentTrackMetaData"] = is_song ?
            didlmake(mpds.currentsong) : "";
    }

    string playmedium("NONE");
    if (is_song)
        playmedium = uri.find("http://") == 0 ?	"HDD" : "NETWORK";
    status["NumberOfTracks"] = "1";
    status["CurrentMediaDuration"] = is_song?
        upnpduration(mpds.songlenms):"00:00:00";
    status["CurrentTrackDuration"] = is_song?
        upnpduration(mpds.songlenms):"00:00:00";
    status["AVTransportURI"] = uri;
    if ((m_dev->m_options & UpMpd::upmpdOwnQueue)) {
        status["AVTransportURIMetaData"] = is_song ? m_curMetadata : "";
    } else {
        status["AVTransportURIMetaData"] = is_song ?
            didlmake(mpds.currentsong) : "";
    }
    status["RelativeTimePosition"] = is_song?
        upnpduration(mpds.songelapsedms):"0:00:00";
    status["AbsoluteTimePosition"] = is_song?
        upnpduration(mpds.songelapsedms) : "0:00:00";

#ifdef NO_SETNEXT
    status["NextAVTransportURI"] = "NOT_IMPLEMENTED";
    status["NextAVTransportURIMetaData"] = "NOT_IMPLEMENTED";
#else
    status["NextAVTransportURI"] = mpds.nextsong.uri;
    if ((m_dev->m_options & UpMpd::upmpdOwnQueue)) {
        status["NextAVTransportURIMetaData"] = is_song ? m_nextMetadata : "";
    } else {
        status["NextAVTransportURIMetaData"] = is_song ?
            didlmake(mpds.nextsong) : "";
    }
#endif

    status["PlaybackStorageMedium"] = playmedium;
    status["PossiblePlaybackStorageMedia"] = "HDD,NETWORK";
    status["RecordStorageMedium"] = "NOT_IMPLEMENTED";
    status["RelativeCounterPosition"] = "0";
    status["AbsoluteCounterPosition"] = "0";
    status["CurrentPlayMode"] = mpdsToPlaymode(mpds);

    status["PossibleRecordStorageMedia"] = "NOT_IMPLEMENTED";
    status["RecordMediumWriteStatus"] = "NOT_IMPLEMENTED";
    status["CurrentRecordQualityMode"] = "NOT_IMPLEMENTED";
    status["PossibleRecordQualityModes"] = "NOT_IMPLEMENTED";
    return true;
}

bool UpMpdAVTransport::getEventData(bool all, std::vector<std::string>& names, 
                                    std::vector<std::string>& values)
{
    unordered_map<string, string> newtpstate;
    tpstateMToU(newtpstate);
    if (all)
        m_tpstate.clear();

    bool changefound = false;

    string 
        chgdata("<Event xmlns=\"urn:schemas-upnp-org:metadata-1-0/AVT_RCS\">\n"
                "<InstanceID val=\"0\">\n");
    for (unordered_map<string, string>::const_iterator it = newtpstate.begin();
         it != newtpstate.end(); it++) {

        const string& oldvalue = mapget(m_tpstate, it->first);
        if (!it->second.compare(oldvalue))
            continue;

        if (it->first.compare("RelativeTimePosition") && 
            it->first.compare("AbsoluteTimePosition")) {
            //LOGDEB("AVTransport: state update for " << it->first << 
            // " oldvalue [" << oldvalue << "] -> [" << it->second << endl);
            changefound = true;
        }

        chgdata += "<";
        chgdata += it->first;
        chgdata += " val=\"";
        chgdata += SoapHelp::xmlQuote(it->second);
        chgdata += "\"/>\n";
    }
    chgdata += "</InstanceID>\n</Event>\n";

    if (!changefound) {
        //LOGDEB1("UpMpdAVTransport::getEventDataTransport: no updates" << endl);
        return true;
    }

    names.push_back("LastChange");
    values.push_back(chgdata);

    m_tpstate = newtpstate;
    LOGDEB1("UpMpdAVTransport::getEventDataTransport: " << chgdata << endl);
    return true;
}

// http://192.168.4.4:8200/MediaItems/246.mp3
int UpMpdAVTransport::setAVTransportURI(const SoapIncoming& sc, SoapOutgoing& data, 
                                        bool setnext)
{
    // pretend not to support setnext:
#ifdef NO_SETNEXT
    if (setnext) {
        LOGERR("SetNextAVTransportURI: faking error\n");
        return UPNP_E_INVALID_PARAM;
    }
#endif

    string uri;
    bool found = setnext? sc.get("NextURI", &uri) : sc.get("CurrentURI", &uri);
    if (!found) {
        return UPNP_E_INVALID_PARAM;
    }
    string metadata;
    found = setnext ? sc.get("NextURIMetaData", &metadata) :
        sc.get("CurrentURIMetaData", &metadata);
    LOGDEB("Set(next)AVTransportURI: next " << setnext <<  " uri " << uri <<
           " metadata[" << metadata << "]" << endl);

    if ((m_dev->m_options & UpMpd::upmpdOwnQueue) && !setnext) {
        // If we own the queue, just clear it before setting the
        // track.  Else it's difficult to impossible to prevent it
        // from growing if upmpdcli restarts. If the option is not set, the
        // user prefers to live with the issue.
        m_dev->m_mpdcli->clearQueue();
    }

    const MpdStatus &mpds = m_dev->getMpdStatus();
    bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
        (mpds.state == MpdStatus::MPDS_PAUSE);
    int curpos = mpds.songpos;
    LOGDEB1("UpMpdAVTransport::set" << (setnext?"Next":"") << 
            "AVTransportURI: curpos: " <<
            curpos << " is_song " << is_song << " qlen " << mpds.qlen << endl);

    // curpos == -1 means that the playlist was cleared or we just started. A
    // play will use position 0, so it's actually equivalent to curpos == 0
    if (curpos == -1) {
        curpos = 0;
    }

    if (setnext) {
        if (mpds.qlen == 0) {
            LOGDEB("setNextAVTransportURI invoked but empty queue!" << endl);
            return UPNP_E_INVALID_PARAM;
        }
        if ((m_dev->m_options & UpMpd::upmpdOwnQueue) && mpds.qlen > 1) {
            // If we own the queue, make sure we only keep 2 songs in it:
            // guard against multiple setnext calls.
            int posend;
            for (posend = curpos + 1;; posend++) {
                UpSong nsong;
                if (!m_dev->m_mpdcli->statSong(nsong, posend))
                    break;
            }
            if (posend > curpos+1)
                m_dev->m_mpdcli->deletePosRange(curpos + 1, posend);
        }
    }

    UpSong metaformpd;
    uMetaToUpSong(metadata, &metaformpd);

    int songid = m_dev->m_mpdcli->insert(uri, setnext ? curpos + 1 : curpos,
                                         metaformpd);
    if (songid < 0) {
        return UPNP_E_INTERNAL_ERROR;
    }

    if (setnext) {
        m_nextUri = uri;
        m_nextMetadata = metadata;
    } else {
        m_uri = uri;
        m_curMetadata = metadata;
        m_nextUri.clear();
        m_nextMetadata.clear();
    }

    if (!setnext) {
        MpdStatus::State st = mpds.state;
        // Have to tell mpd which track to play, else it will keep on
        // the previous despite the insertion. The UPnP docs say
        // that setAVTransportURI should not change the transport
        // state (pause/stop stay pause/stop) but it seems that some clients
        // expect that the track will start playing.
        // Needs to be revisited after seeing more clients. For now try to 
        // preserve state as per standard.
        // Audionet: issues a Play
        // BubbleUpnp: issues a Play
        // MediaHouse: no setnext, Play
        m_dev->m_mpdcli->play(curpos);
#if 1 || defined(upmpd_do_restore_play_state_after_add)
        switch (st) {
        case MpdStatus::MPDS_PAUSE: m_dev->m_mpdcli->togglePause(); break;
        case MpdStatus::MPDS_STOP: m_dev->m_mpdcli->stop(); break;
        default: break;
        }
#endif
        // Clean up old song ids
        if (!(m_dev->m_options & UpMpd::upmpdOwnQueue)) {
            for (set<int>::iterator it = m_songids.begin();
                 it != m_songids.end(); it++) {
                // Can't just delete here. If the id does not exist, MPD 
                // gets into an apparently permanent error state, where even 
                // get_status does not work
                if (m_dev->m_mpdcli->statId(*it)) {
                    m_dev->m_mpdcli->deleteId(*it);
                }
            }
            m_songids.clear();
        }
    }

    if (!(m_dev->m_options & UpMpd::upmpdOwnQueue)) {
        m_songids.insert(songid);
    }

    m_dev->loopWakeup();
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::getPositionInfo(const SoapIncoming& sc, SoapOutgoing& data)
{
    const MpdStatus &mpds = m_dev->getMpdStatus();
    //LOGDEB("UpMpdAVTransport::getPositionInfo. State: " << mpds.state <<endl);

    bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
        (mpds.state == MpdStatus::MPDS_PAUSE);

    if (is_song) {
        data.addarg("Track", "1");
    } else {
        data.addarg("Track", "0");
    }

    if (is_song) {
        data.addarg("TrackDuration", upnpduration(mpds.songlenms));
    } else {
        data.addarg("TrackDuration", "00:00:00");
    }

    if (is_song) {
        if ((m_dev->m_options & UpMpd::upmpdOwnQueue)) {
            data.addarg("TrackMetaData", m_curMetadata);
        } else {
            data.addarg("TrackMetaData", didlmake(mpds.currentsong));
        }
    } else {
        data.addarg("TrackMetaData", "");
    }

    const string& uri = mpds.currentsong.uri;
    if (is_song && !uri.empty()) {
        data.addarg("TrackURI", SoapHelp::xmlQuote(uri));
    } else {
        data.addarg("TrackURI", "");
    }
    if (is_song) {
        data.addarg("RelTime", upnpduration(mpds.songelapsedms));
    } else {
        data.addarg("RelTime", "0:00:00");
    }

    if (is_song) {
        data.addarg("AbsTime", upnpduration(mpds.songelapsedms));
    } else {
        data.addarg("AbsTime", "0:00:00");
    }

    data.addarg("RelCount", "0");
    data.addarg("AbsCount", "0");
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::getTransportInfo(const SoapIncoming& sc, SoapOutgoing& data)
{
    const MpdStatus &mpds = m_dev->getMpdStatus();
    //LOGDEB("UpMpdAVTransport::getTransportInfo. State: " << mpds.state<<endl);

    string tstate("STOPPED");
    switch(mpds.state) {
    case MpdStatus::MPDS_PLAY: tstate = "PLAYING"; break;
    case MpdStatus::MPDS_PAUSE: tstate = "PAUSED_PLAYBACK"; break;
    default: break;
    }
    data.addarg("CurrentTransportState", tstate);
    data.addarg("CurrentTransportStatus", m_dev->m_mpdcli->ok() ? "OK" : 
                "ERROR_OCCURRED");
    data.addarg("CurrentSpeed", "1");
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::getDeviceCapabilities(const SoapIncoming& sc, SoapOutgoing& data)
{
    data.addarg("PlayMedia", "NETWORK,HDD");
    data.addarg("RecMedia", "NOT_IMPLEMENTED");
    data.addarg("RecQualityModes", "NOT_IMPLEMENTED");
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::getMediaInfo(const SoapIncoming& sc, SoapOutgoing& data)
{
    const MpdStatus &mpds = m_dev->getMpdStatus();
    LOGDEB("UpMpdAVTransport::getMediaInfo. State: " << mpds.state << endl);

    bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
        (mpds.state == MpdStatus::MPDS_PAUSE);

    data.addarg("NrTracks", "1");
    if (is_song) {
        data.addarg("MediaDuration", upnpduration(mpds.songlenms));
    } else {
        data.addarg("MediaDuration", "00:00:00");
    }

    const string& thisuri = mpds.currentsong.uri;
    if (is_song && !thisuri.empty()) {
        data.addarg("CurrentURI", SoapHelp::xmlQuote(thisuri));
    } else {
        data.addarg("CurrentURI", "");
    }
    if (is_song) {
        if ((m_dev->m_options & UpMpd::upmpdOwnQueue)) {
            data.addarg("CurrentURIMetaData", m_curMetadata);
        } else {
            data.addarg("CurrentURIMetaData", didlmake(mpds.currentsong));
        }
    } else {
        data.addarg("CurrentURIMetaData", "");
    }
    if ((m_dev->m_options & UpMpd::upmpdOwnQueue)) {
        data.addarg("NextURI", m_nextUri);
        data.addarg("NextURIMetaData", is_song ? m_nextMetadata : "");
    } else {
        data.addarg("NextURI", mpds.nextsong.uri);
        data.addarg("NextURIMetaData", is_song ? didlmake(mpds.nextsong) : "");
    }
    string playmedium("NONE");
    if (is_song)
        playmedium = thisuri.find("http://") == 0 ?	"HDD" : "NETWORK";
    data.addarg("PlayMedium", playmedium);

    data.addarg("RecordMedium", "NOT_IMPLEMENTED");
    data.addarg("WriteStatus", "NOT_IMPLEMENTED");
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::playcontrol(const SoapIncoming& sc, SoapOutgoing& data, int what)
{
    const MpdStatus &mpds = m_dev->getMpdStatus();
    LOGDEB("UpMpdAVTransport::playcontrol State: " << mpds.state <<
           " what "<<what<< endl);

    if ((what & ~0x3)) {
        LOGERR("UpMPd::playcontrol: bad control " << what << endl);
        return UPNP_E_INVALID_PARAM;
    }

    bool ok = true;
    switch (mpds.state) {
    case MpdStatus::MPDS_PLAY: 
        switch (what) {
        case 0:	ok = m_dev->m_mpdcli->stop(); break;
        case 1: ok = m_dev->m_mpdcli->play();break;
        case 2: ok = m_dev->m_mpdcli->togglePause();break;
        }
        break;
    case MpdStatus::MPDS_PAUSE:
        switch (what) {
        case 0:	ok = m_dev->m_mpdcli->stop(); break;
        case 1: ok = m_dev->m_mpdcli->togglePause();break;
        case 2: break;
        }
        break;
    case MpdStatus::MPDS_STOP:
    default:
        switch (what) {
        case 0:	break;
        case 1: ok = m_dev->m_mpdcli->play();break;
        case 2: break;
        }
        break;
    }
	
    m_dev->loopWakeup();
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int UpMpdAVTransport::seqcontrol(const SoapIncoming& sc, SoapOutgoing& data, int what)
{
    const MpdStatus &mpds = m_dev->getMpdStatus();
    LOGDEB("UpMpdAVTransport::seqcontrol State: " << mpds.state << " what "
           <<what<< endl);

    if ((what & ~0x1)) {
        LOGERR("UpMPd::seqcontrol: bad control " << what << endl);
        return UPNP_E_INVALID_PARAM;
    }

    bool ok = true;
    switch (what) {
    case 0: ok = m_dev->m_mpdcli->next();break;
    case 1: ok = m_dev->m_mpdcli->previous();break;
    }

    m_dev->loopWakeup();
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}
	
int UpMpdAVTransport::setPlayMode(const SoapIncoming& sc, SoapOutgoing& data)
{
    string playmode;
    if (!sc.get("NewPlayMode", &playmode)) {
        return UPNP_E_INVALID_PARAM;
    }
    LOGDEB("UpMpdAVTransport::setPlayMode: " << playmode << endl);

    bool ok;
    if (!playmode.compare("NORMAL")) {
        ok = m_dev->m_mpdcli->repeat(false) && m_dev->m_mpdcli->random(false) &&
            m_dev->m_mpdcli->single(false);
    } else if (!playmode.compare("SHUFFLE")) {
        ok = m_dev->m_mpdcli->repeat(false) && m_dev->m_mpdcli->random(true) &&
            m_dev->m_mpdcli->single(false);
    } else if (!playmode.compare("REPEAT_ONE")) {
        ok = m_dev->m_mpdcli->repeat(true) && m_dev->m_mpdcli->random(false) &&
            m_dev->m_mpdcli->single(true);
    } else if (!playmode.compare("REPEAT_ALL")) {
        ok = m_dev->m_mpdcli->repeat(true) && m_dev->m_mpdcli->random(false) &&
            m_dev->m_mpdcli->single(false);
    } else if (!playmode.compare("RANDOM")) {
        ok = m_dev->m_mpdcli->repeat(true) && m_dev->m_mpdcli->random(true) &&
            m_dev->m_mpdcli->single(false);
    } else if (!playmode.compare("DIRECT_1")) {
        ok = m_dev->m_mpdcli->repeat(false) && m_dev->m_mpdcli->random(false) &&
            m_dev->m_mpdcli->single(true);
    } else {
        return UPNP_E_INVALID_PARAM;
    }
    m_dev->loopWakeup();
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int UpMpdAVTransport::getTransportSettings(const SoapIncoming& sc, SoapOutgoing& data)
{
    const MpdStatus &mpds = m_dev->getMpdStatus();
    string playmode = mpdsToPlaymode(mpds);
    data.addarg("PlayMode", playmode);
    data.addarg("RecQualityMode", "NOT_IMPLEMENTED");
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::getCurrentTransportActions(const SoapIncoming& sc, 
                                                 SoapOutgoing& data)
{
    const MpdStatus &mpds = m_dev->getMpdStatus();
    string tactions("Next,Previous");
    switch(mpds.state) {
    case MpdStatus::MPDS_PLAY: 
        tactions += ",Pause,Stop,Seek";
        break;
    case MpdStatus::MPDS_PAUSE: 
        tactions += ",Play,Stop,Seek";
        break;
    default:
        tactions += ",Play";
    }
    data.addarg("Actions", tactions);
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::seek(const SoapIncoming& sc, SoapOutgoing& data)
{
    string unit;
    if (!sc.get("Unit", &unit)) {
        return UPNP_E_INVALID_PARAM;
    }
    
    string target;
    if (!sc.get("Target", &target)) {
        return UPNP_E_INVALID_PARAM;
    }

    //LOGDEB("UpMpdAVTransport::seek: unit " << unit << " target " << target << 
    //	   " current posisition " << mpds.songelapsedms / 1000 << 
    //	   " seconds" << endl);

    int abs_seconds;
    // Note that ABS_TIME and REL_TIME don't mean what you'd think
    // they mean.  REL_TIME means relative to the current track,
    // ABS_TIME to the whole media (ie for a multitrack tape). So
    // take both ABS and REL as absolute position in the current song
    if (!unit.compare("REL_TIME") || !unit.compare("ABS_TIME")) {
        abs_seconds = upnpdurationtos(target);
    } else {
        return UPNP_E_INVALID_PARAM;
    }
    LOGDEB("UpMpdAVTransport::seek: seeking to " << abs_seconds << 
           " seconds (" << upnpduration(abs_seconds * 1000) << ")" << endl);

    m_dev->loopWakeup();
    return m_dev->m_mpdcli->seek(abs_seconds) ? 
        UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}
