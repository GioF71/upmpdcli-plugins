/* Copyright (C) 2014-2019 J.F.Dockes
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

#include "avtransport.hxx"

#include <functional>
#include <iostream>
#include <map>
#include <utility>

#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"
#include "libupnpp/upnpavutils.hxx"

#include "mpdcli.hxx"
#include "ohplaylist.hxx"
#include "upmpd.hxx"
#include "upmpdutils.hxx"
#include "smallut.h"
#include "conftree.h"

// For testing upplay with a dumb renderer.
// #define NO_SETNEXT

using namespace std;
using namespace std::placeholders;

static const string sIdTransport("urn:upnp-org:serviceId:AVTransport");
static const string sTpTransport("urn:schemas-upnp-org:service:AVTransport:1");

static bool m_autoplay{false};
static bool keepconsume(false);

UpMpdAVTransport::UpMpdAVTransport(
    UpMpd *dev, UpMpdMediaRenderer *udev, bool noev)
    : UpnpService(sTpTransport, sIdTransport, "AVTransport.xml", udev, noev),
      m_dev(dev), m_udev(udev), m_ohp(0)
{
    udev->addActionMapping(this,"SetAVTransportURI", 
                            bind(&UpMpdAVTransport::setAVTransportURI, 
                                 this,_1,_2, false));
    udev->addActionMapping(this,"SetNextAVTransportURI", 
                            bind(&UpMpdAVTransport::setAVTransportURI, 
                                 this,_1, _2, true));
    udev->addActionMapping(this,"GetPositionInfo", 
                            bind(&UpMpdAVTransport::getPositionInfo, 
                                 this, _1, _2));
    udev->addActionMapping(this,"GetTransportInfo", 
                            bind(&UpMpdAVTransport::getTransportInfo, 
                                 this, _1, _2));
    udev->addActionMapping(this,"GetMediaInfo", 
                            bind(&UpMpdAVTransport::getMediaInfo, 
                                 this, _1, _2));
    udev->addActionMapping(this,"GetDeviceCapabilities", 
                            bind(&UpMpdAVTransport::getDeviceCapabilities, 
                                 this, _1, _2));
    udev->addActionMapping(this,"SetPlayMode", 
                            bind(&UpMpdAVTransport::setPlayMode, this, _1, _2));
    udev->addActionMapping(this,"GetTransportSettings", 
                            bind(&UpMpdAVTransport::getTransportSettings, 
                                 this, _1, _2));
    udev->addActionMapping(this,"GetCurrentTransportActions", 
                            bind(&UpMpdAVTransport::getCurrentTransportActions,
                                 this,_1,_2));
    udev->addActionMapping(this,"Stop", bind(&UpMpdAVTransport::playcontrol, 
                                              this, _1, _2, 0));
    udev->addActionMapping(this,"Play", bind(&UpMpdAVTransport::playcontrol, 
                                              this, _1, _2, 1));
    udev->addActionMapping(this,"Pause", 
                            bind(&UpMpdAVTransport::playcontrol, 
                                 this, _1, _2, 2));
    udev->addActionMapping(this,"Seek", bind(&UpMpdAVTransport::seek, 
                                              this, _1, _2));

    // should we get rid of those ? They don't make sense for us
    udev->addActionMapping(this, "Next", bind(&UpMpdAVTransport::seqcontrol, 
                                               this, _1, _2, 0));
    udev->addActionMapping(this, "Previous", 
                            bind(&UpMpdAVTransport::seqcontrol, 
                                 this, _1, _2, 1));

    // This would make our life easier, but it's incompatible if
    // ohplaylist is also in use, so refrain.
//    dev->m_mpdcli->consume(true);
#ifdef NO_SETNEXT
    // If no setnext, we'd like to fake stopping at each track but
    // this does not work because mpd goes into PAUSED PLAY at the end
    // of track, not STOP.
//    m_dev->getmpdcli()->single(true);
#endif
    m_autoplay = g_config->getBool("avtautoplay", false);
    keepconsume = g_config->getBool("keepconsume", false);
    m_dev->getmpdcli()->subscribe(
        MPDCli::MpdQueueEvt|MPDCli::MpdPlayerEvt|MPDCli::MpdOptsEvt,
        bind(&UpMpdAVTransport::onMpdEvent, this, _1));
}

// AVTransport Errors
enum AVTErrorCode {
    UPNP_AV_AVT_INVALID_TRANSITION                    = 701,
    UPNP_AV_AVT_NO_CONTENTS                           = 702,
    UPNP_AV_AVT_READ_ERROR                            = 703,
    UPNP_AV_AVT_UNSUPPORTED_PLAY_FORMAT               = 704,
    UPNP_AV_AVT_TRANSPORT_LOCKED                      = 705,
    UPNP_AV_AVT_WRITE_ERROR                           = 706,
    UPNP_AV_AVT_PROTECTED_MEDIA                       = 707,
    UPNP_AV_AVT_UNSUPPORTED_REC_FORMAT                = 708,
    UPNP_AV_AVT_FULL_MEDIA                            = 709,
    UPNP_AV_AVT_UNSUPPORTED_SEEK_MODE                 = 710,
    UPNP_AV_AVT_ILLEGAL_SEEK_TARGET                   = 711,
    UPNP_AV_AVT_UNSUPPORTED_PLAY_MODE                 = 712,
    UPNP_AV_AVT_UNSUPPORTED_REC_QUALITY               = 713,
    UPNP_AV_AVT_ILLEGAL_MIME                          = 714,
    UPNP_AV_AVT_CONTENT_BUSY                          = 715,
    UPNP_AV_AVT_RESOURCE_NOT_FOUND                    = 716,
    UPNP_AV_AVT_UNSUPPORTED_PLAY_SPEED                = 717,
    UPNP_AV_AVT_INVALID_INSTANCE_ID                   = 718,
};

const std::string UpMpdAVTransport::serviceErrString(int error) const
{
    switch(error) {
    case UPNP_AV_AVT_INVALID_TRANSITION:
        return "AVTransport Invalid Transition";
    case UPNP_AV_AVT_NO_CONTENTS: return "AVTransport No Contents";
    case UPNP_AV_AVT_READ_ERROR: return "AVTransport Read Error";
    case UPNP_AV_AVT_UNSUPPORTED_PLAY_FORMAT:
        return "AVTransport Unsupported Play Format";
    case UPNP_AV_AVT_TRANSPORT_LOCKED: return "AVTransport Transport Locked";
    case UPNP_AV_AVT_WRITE_ERROR: return "AVTransport Write Error";
    case UPNP_AV_AVT_PROTECTED_MEDIA: return "AVTransport Protected Media";
    case UPNP_AV_AVT_UNSUPPORTED_REC_FORMAT:
        return "AVTransport Unsupported Rec Format";
    case UPNP_AV_AVT_FULL_MEDIA: return "AVTransport Full Media";
    case UPNP_AV_AVT_UNSUPPORTED_SEEK_MODE:
        return "AVTransport Unsupported Seek Mode";
    case UPNP_AV_AVT_ILLEGAL_SEEK_TARGET:
        return "AVTransport Illegal Seek Target";
    case UPNP_AV_AVT_UNSUPPORTED_PLAY_MODE:
        return "AVTransport Unsupported Play Mode";
    case UPNP_AV_AVT_UNSUPPORTED_REC_QUALITY:
        return "AVTransport Unsupported Rec Quality";
    case UPNP_AV_AVT_ILLEGAL_MIME: return "AVTransport Illegal Mime";
    case UPNP_AV_AVT_CONTENT_BUSY: return "AVTransport Content Busy";
    case UPNP_AV_AVT_RESOURCE_NOT_FOUND:
        return "AVTransport Resource Not Found";
    case UPNP_AV_AVT_UNSUPPORTED_PLAY_SPEED:
        return "AVTransport Unsupported Play Speed";
    case UPNP_AV_AVT_INVALID_INSTANCE_ID:
        return "AVTransport Invalid Instance Id";
    default:
        return "AVTRansport Unknown Error";
    }
}

// Translate MPD mode flags to UPnP Play mode
//
// This is only meaningful if the CP is only observing the renderer
// state (e.g. if the renderer is controlled through OHPlaylist). We
// always reset the modes to false in setAvTransport.
//
// Actually, I think that these commands were meant for multi-track
// players (e.g. CD)
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

static string mpdsToTActions(const MpdStatus &mpds)
{
    string tactions("Next,Previous,");
    switch(mpds.state) {
    case MpdStatus::MPDS_PLAY: 
        tactions += "Pause,Stop,Seek";
        break;
    case MpdStatus::MPDS_PAUSE: 
        tactions += "Play,Stop,Seek";
        break;
    default:
        tactions += "Play";
    }
    return tactions;
}

static string mpdsToTState(const MpdStatus &mpds)
{
    string tstate{"STOPPED"};
    switch(mpds.state) {
    case MpdStatus::MPDS_PLAY: tstate = "PLAYING"; break;
    case MpdStatus::MPDS_PAUSE: tstate = "PAUSED_PLAYBACK"; break;
    default: break;
    }
    return tstate;
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
// Note: currentTrackXX could be different from AVTransportURI if the
// latter points to an object with multiple tracks (the currentTrack
// is for the active one). We don't support this at the moment.
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

// Prepare UPnP AVTransport state variables from our and MPD state.
bool UpMpdAVTransport::tpstateMToU(unordered_map<string, string>& status)
{
    const MpdStatus &mpds =  m_dev->getMpdStatus();
    LOGDEB2("UpMpdAVTransport::tpstateMToU: curpos: " << mpds.songpos <<
            " qlen " << mpds.qlen << endl);
    bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
        (mpds.state == MpdStatus::MPDS_PAUSE);
    
    status["TransportState"] = mpdsToTState(mpds);
    status["CurrentTransportActions"] = mpdsToTActions(mpds);
    status["TransportStatus"] = m_dev->getmpdcli()->ok() ?
        "OK" : "ERROR_OCCURRED";
    status["TransportPlaySpeed"] = "1";

    const string& uri = mpds.currentsong.rsrc.uri;

    // MPD may have switched to the next track, or may be playing
    // something else altogether if some other client told it to. 
    // Also the current metadata may come from mpd, or be the bogus
    // unknown entry (will have <orig>mpd</orig> in both cases because
    // null id in the song). In these cases, build meta from the mpd song.
    LOGDEB2("UpMpdAVTransport: curmeta: " << m_curMetadata << endl);
    if (m_dev->radioPlaying() ||
        m_curMetadata.find("<orig>mpd</orig>") != string::npos) {
        m_curMetadata = didlmake(mpds.currentsong);
        LOGDEB2("TPSTATEMTOU: RADIO OR MPD: FROM MPD:\n");
    } else {
        if (!uri.empty() && !uri.compare(m_nextUri)) {
            LOGDEB2("TPSTATEMTOU m_uri is m_nextUri. -> nextMetadata\n");
            m_uri = m_nextUri;
            m_curMetadata = m_nextMetadata;
            m_nextUri.clear();
            m_nextMetadata.clear();
        } else if (!uri.empty() && uri.compare(m_uri)) {
            // Someone else is controlling mpd. Maybe our own ohplaylist.
            m_nextMetadata.clear();
            m_nextUri.clear();
            m_uri = uri;
            if (!m_ohp || !m_ohp->cacheFind(uri, m_curMetadata)) {
                m_curMetadata = is_song ? didlmake(mpds.currentsong) : "";
                LOGDEB2("TPSTATEMTOU: FROM MPDS\n");
            } else {
                LOGDEB2("TPSTATEMTOU: FROM OHCACHE\n");
            }
        }
    }
    
    status["CurrentTrack"] = "1";
    string playmedium("NONE");
    if (is_song)
        playmedium = m_uri.find("http://") == 0 ? "HDD" : "NETWORK";
    status["NumberOfTracks"] = "1";
    status["CurrentMediaDuration"] = is_song?
        upnpduration(mpds.songlenms):"00:00:00";
    status["CurrentTrackDuration"] = is_song?
        upnpduration(mpds.songlenms):"00:00:00";
    status["CurrentTrackURI"] = m_uri;
    status["AVTransportURI"] = m_uri;
    status["AVTransportURIMetaData"] = status["CurrentTrackMetaData"] =
        m_curMetadata;
    status["RelativeTimePosition"] = is_song?
        upnpduration(mpds.songelapsedms):"0:00:00";
    status["AbsoluteTimePosition"] = is_song?
        upnpduration(mpds.songelapsedms) : "0:00:00";

#ifdef NO_SETNEXT
    status["NextAVTransportURI"] = "NOT_IMPLEMENTED";
    status["NextAVTransportURIMetaData"] = "NOT_IMPLEMENTED";
#else
    status["NextAVTransportURI"] = m_nexturi;
    if ((m_dev->getopts().options & UpMpd::upmpdOwnQueue)) {
        status["NextAVTransportURIMetaData"] = m_nextMetadata;
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

void UpMpdAVTransport::onMpdEvent(const MpdStatus*)
{
    LOGDEB0("AVTransport::onMpdEvent()\n");
    std::vector<std::string> names, values;
    getEventData(false, names, values);
    if (!names.empty()) {
        m_udev->notifyEvent(this, names, values);
    }
}

// http://192.168.4.4:8200/MediaItems/246.mp3
int UpMpdAVTransport::setAVTransportURI(const SoapIncoming& sc,
                                        SoapOutgoing& data, bool setnext)
{
#ifdef NO_SETNEXT
    // pretend not to support setnext:
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

    const MpdStatus &mpds = m_dev->getMpdStatus();
    const MpdStatus::State st = mpds.state;

    // Check that we support the audio format for the input uri.
    UpSong metaformpd;
    if (!m_dev->checkContentFormat(uri, metadata, &metaformpd)) {
        LOGERR("set(Next)AVTransportURI: unsupported format: uri " << uri <<
               " metadata [" << metadata << "]\n");
        return UPNP_E_INVALID_PARAM;
    }

    bool is_song = (st == MpdStatus::MPDS_PLAY) || (st == MpdStatus::MPDS_PAUSE);
    UPMPD_UNUSED(is_song);
    int curpos = mpds.songpos;
    LOGDEB1("UpMpdAVTransport::set" << (setnext?"Next":"") << 
            "AVTransportURI: curpos: " <<
            curpos << " is_song " << is_song << " qlen " << mpds.qlen << endl);

    if ((m_dev->getopts().options & UpMpd::upmpdOwnQueue) && !setnext) {
        // If we own the queue, just clear it before setting the
        // track.  Else it's difficult to impossible to prevent it
        // from growing if upmpdcli restarts. If the option is not set, the
        // user prefers to live with the issue.
        m_dev->getmpdcli()->clearQueue();
        // mpds is now invalid!
        curpos = -1;
    }

    // If setAVTransport is called, the Control Point wants to control
    // the playing, so we reset any special mpd playlist
    // mode. Especially, repeat would prevent us from ever seeing the
    // end of the track. Note that always setting repeat to false is
    // one of the ways which we are incompatible with simultaneous
    // mpc or ohplaylist use (there are many others of course).
    m_dev->getmpdcli()->repeat(false);
    m_dev->getmpdcli()->random(false);
    // See comment about single in init
    m_dev->getmpdcli()->single(false);
    if (!keepconsume)
        m_dev->getmpdcli()->consume(false);
    
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
        if ((m_dev->getopts().options & UpMpd::upmpdOwnQueue) && mpds.qlen > 1) {
            // If we own the queue, make sure we only keep 2 songs in it:
            // guard against multiple setnext calls.
            int posend;
            for (posend = curpos + 1;; posend++) {
                UpSong nsong;
                if (!m_dev->getmpdcli()->statSong(nsong, posend))
                    break;
            }
            if (posend > curpos+1)
                m_dev->getmpdcli()->deletePosRange(curpos + 1, posend);
        }
    }

    int songid = m_dev->getmpdcli()->insert(uri, setnext ? curpos + 1 : curpos,
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
        // Have to tell mpd which track to play, else it will keep on
        // the previous despite the insertion.
        // The UPnP AVTransport definition document is very clear on
        // the fact that setAVTransportURI should not change the
        // transport state (pause/stop stay pause/stop)
        // However some control points expect that the track will
        // start playing without having to issue a Play command, which
        // is why the avtautoplay quirk was added for forcing Play after
        // insert
        //  - Audionet: issues a Play
        //  - BubbleUpnp: issues a Play
        //  - MediaHouse: no setnext, Play
        //  - Raumfeld: needs autoplay
        if (m_autoplay) {
            m_dev->getmpdcli()->play(curpos);
        } else {
            switch (st) {
            case MpdStatus::MPDS_PLAY: m_dev->getmpdcli()->play(curpos); break;
            case MpdStatus::MPDS_PAUSE: m_dev->getmpdcli()->pause(true); break;
            case MpdStatus::MPDS_STOP: m_dev->getmpdcli()->stop(); break;
            default: break;
            }
        }
        // Clean up old song ids
        if (!(m_dev->getopts().options & UpMpd::upmpdOwnQueue)) {
            for (auto id : m_songids) {
                // Can't just delete here. If the id does not exist, MPD 
                // gets into an apparently permanent error state, where even 
                // get_status does not work
                if (m_dev->getmpdcli()->statId(id)) {
                    m_dev->getmpdcli()->deleteId(id);
                }
            }
            m_songids.clear();
        }
    }

    if (!(m_dev->getopts().options & UpMpd::upmpdOwnQueue)) {
        m_songids.insert(songid);
    }

    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::getPositionInfo(const SoapIncoming& sc, SoapOutgoing& data)
{
    const MpdStatus &mpds = m_dev->getMpdStatus();
    LOGDEB1("UpMpdAVTransport::getPositionInfo. State: " <<
            mpdsToTState(mpds) << " (" << mpds.state << ")\n");

    bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
        (mpds.state == MpdStatus::MPDS_PAUSE);
    data.addarg("Track", is_song ? "1" : "0");
    data.addarg("TrackDuration",
                is_song ? upnpduration(mpds.songlenms) : "00:00:00");
    data.addarg("TrackMetaData", m_curMetadata);
    data.addarg("TrackURI", SoapHelp::xmlQuote(m_uri));
    data.addarg("RelTime",
                is_song ? upnpduration(mpds.songelapsedms) : "0:00:00");
    data.addarg("AbsTime",
                is_song ? upnpduration(mpds.songelapsedms) : "0:00:00");
    data.addarg("RelCount", "0");
    data.addarg("AbsCount", "0");
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::getTransportInfo(const SoapIncoming& sc,SoapOutgoing& data)
{
    const MpdStatus &mpds = m_dev->getMpdStatus();
    LOGDEB1("UpMpdAVTransport::getTransportInfo. State: " <<
            mpdsToTState(mpds) << endl);

    data.addarg("CurrentTransportState", mpdsToTState(mpds));
    data.addarg("CurrentTransportStatus", m_dev->getmpdcli()->ok() ? "OK" : 
                "ERROR_OCCURRED");
    data.addarg("CurrentSpeed", "1");
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::getDeviceCapabilities(const SoapIncoming& sc,
                                            SoapOutgoing& data)
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
    data.addarg("MediaDuration",
                is_song ? upnpduration(mpds.songlenms) : "00:00:00");

    data.addarg("CurrentURI", SoapHelp::xmlQuote(m_uri));
    data.addarg("CurrentURIMetaData", m_curMetadata);
    if ((m_dev->getopts().options & UpMpd::upmpdOwnQueue)) {
        data.addarg("NextURI", SoapHelp::xmlQuote(m_nextUri));
        data.addarg("NextURIMetaData", m_nextMetadata);
    } else {
        data.addarg("NextURI", SoapHelp::xmlQuote(mpds.nextsong.rsrc.uri));
        data.addarg("NextURIMetaData", is_song ? didlmake(mpds.nextsong) : "");
    }
    string playmedium("NONE");
    if (!m_uri.empty())
        playmedium = m_uri.find("http://") == 0 ? "HDD" : "NETWORK";
    data.addarg("PlayMedium", playmedium);
    data.addarg("RecordMedium", "NOT_IMPLEMENTED");
    data.addarg("WriteStatus", "NOT_IMPLEMENTED");
    return UPNP_E_SUCCESS;
}

int UpMpdAVTransport::playcontrol(
    const SoapIncoming& sc, SoapOutgoing& data, int what)
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
        case 0: ok = m_dev->getmpdcli()->stop(); break;
        case 1: ok = m_dev->getmpdcli()->play();break;
        case 2: ok = m_dev->getmpdcli()->togglePause();break;
        }
        break;
    case MpdStatus::MPDS_PAUSE:
        switch (what) {
        case 0: ok = m_dev->getmpdcli()->stop(); break;
        case 1: ok = m_dev->getmpdcli()->togglePause();break;
        case 2: break;
        }
        break;
    case MpdStatus::MPDS_STOP:
    default:
        switch (what) {
        case 0: break;
        case 1: ok = m_dev->getmpdcli()->play();break;
        case 2: break;
        }
        break;
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int UpMpdAVTransport::seqcontrol(
    const SoapIncoming& sc, SoapOutgoing& data, int what)
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
    case 0: ok = m_dev->getmpdcli()->next();break;
    case 1: ok = m_dev->getmpdcli()->previous();break;
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

/*
 * For the AVTransport service, this only makes sense if we're playing a
 * multi-track media, else we're only dealing with a single track (and
 * possibly the next), and none of the repeat/shuffle modes make
 * sense. If ownqueue is 0, it might still make sense for us to
 * control the mpd play mode though, but any special mode will be reset if
 * set(Next)AVTransport is called.
 */
int UpMpdAVTransport::setPlayMode(const SoapIncoming& sc, SoapOutgoing& data)
{
    string playmode;
    if (!sc.get("NewPlayMode", &playmode)) {
        return UPNP_E_INVALID_PARAM;
    }
    LOGDEB("UpMpdAVTransport::setPlayMode: " << playmode << endl);

    if ((m_dev->getopts().options & UpMpd::upmpdOwnQueue)) {
        // If we own the queue then none of this makes sense, we're
        // only keeping 1 or 2 entries on the queue and controlling
        // everything.
        LOGDEB("AVTRansport::setPlayMode: ownqueue is set, doing nothing\n");
        return 0;
    }

    bool ok;
    if (!playmode.compare("NORMAL")) {
        ok = m_dev->getmpdcli()->repeat(false) &&
            m_dev->getmpdcli()->random(false) &&
            m_dev->getmpdcli()->single(false);
    } else if (!playmode.compare("SHUFFLE")) {
        ok = m_dev->getmpdcli()->repeat(false) &&
            m_dev->getmpdcli()->random(true) &&
            m_dev->getmpdcli()->single(false);
    } else if (!playmode.compare("REPEAT_ONE")) {
        ok = m_dev->getmpdcli()->repeat(true) &&
            m_dev->getmpdcli()->random(false) &&
            m_dev->getmpdcli()->single(true);
    } else if (!playmode.compare("REPEAT_ALL")) {
        ok = m_dev->getmpdcli()->repeat(true) &&
            m_dev->getmpdcli()->random(false) &&
            m_dev->getmpdcli()->single(false);
    } else if (!playmode.compare("RANDOM")) {
        ok = m_dev->getmpdcli()->repeat(true) &&
            m_dev->getmpdcli()->random(true) &&
            m_dev->getmpdcli()->single(false);
    } else if (!playmode.compare("DIRECT_1")) {
        ok = m_dev->getmpdcli()->repeat(false) &&
            m_dev->getmpdcli()->random(false) &&
            m_dev->getmpdcli()->single(true);
    } else {
        return UPNP_E_INVALID_PARAM;
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int UpMpdAVTransport::getTransportSettings(const SoapIncoming& sc,
                                           SoapOutgoing& data)
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
    data.addarg("Actions", mpdsToTActions(mpds));
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
    //       " current posisition " << mpds.songelapsedms / 1000 << 
    //       " seconds" << endl);

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

    return m_dev->getmpdcli()->seek(abs_seconds) ? 
        UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}
