/* Copyright (C) 2014-2020 J.F.Dockes
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

#include "ohradio.hxx"

#include <stdlib.h>

#include <functional>
#include <iostream>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
#include <json/json.h>

#include "libupnpp/base64.hxx"
#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"
#include "libupnpp/upnpavutils.hxx"

#include "main.hxx"
#include "mpdcli.hxx"
#include "upmpd.hxx"
#include "smallut.h"
#include "pathut.h"
#include "upmpdutils.hxx"
#include "conftree.h"
#include "execmd.h"
#include "ohproduct.hxx"
#include "ohinfo.hxx"
#include "protocolinfo.hxx"

using namespace std;
using namespace std::placeholders;

static const string sTpProduct("urn:av-openhome-org:service:Radio:1");
static const string sIdProduct("urn:av-openhome-org:serviceId:Radio");

static const string cstr_sturlkey("ohradio.url");
static bool keepconsume;

static string find_script(const string& icmd)
{
    if (path_isabsolute(icmd))
        return icmd;

    // Append the radio scripts dir to the PATH. Put at the end so
    // that the user can easily override a script by putting the
    // modified version in the PATH env variable
    const char *cp = getenv("PATH");
    if (!cp) //??
        cp = "";
    string PATH(cp);
    PATH = PATH + path_PATHsep() + path_cat(g_datadir, "radio_scripts");
    string cmd;
    if (ExecCmd::which(icmd, cmd, PATH.c_str())) {
        return cmd;
    } else {
        // Let the shell try to find it...
        return icmd;
    }
}

struct RadioMeta {
    RadioMeta(const string& t, const string& u, const string& au,
              const string& as, const string& ms, const string& ps)
        : title(t), uri(u), artUri(au), dynArtUri(au) {
        if (!as.empty()) {
            stringToStrings(as, artScript);
            artScript[0] = find_script(artScript[0]);
        }
        if (!ms.empty()) {
            stringToStrings(ms, metaScript);
            metaScript[0] = find_script(metaScript[0]);
        }
        preferScript = stringToBool(ps);
    }

    // The static title, URI and icon (from the radios configuration or
    // setChannel) are always used in the ohradio interface. The
    // dynamic currently playing title and metadata are only sent to
    // OHInfo and obtainable from there.
    string title;
    string uri;
    string artUri;
    
    // Script to retrieve current art
    vector<string> artScript; 
    // Script to retrieve all metadata
    vector<string> metaScript;
    // Dynamic audio URI, fetched by the metadata script (overrides
    // uri, which will normally be empty if the metascript is used for
    // audio).
    string currentAudioUri;
    // Keep values from script over mpd's (from icy)
    bool preferScript{true};
    // Time after which we should re-fire the metadata script
    time_t nextMetaScriptExecTime{0}; 
    string dynArtUri;
    string dynTitle;
    string dynArtist;
};


// Our radio channels. The Id is an index is this. Channel 0 is
// reserved for externally set Uri/Metadata from SetChannel. Our
// preset channels (from the config) begin at 1
static vector<RadioMeta> o_radios;

OHRadio::OHRadio(UpMpd *dev, UpMpdOpenHome *udev)
    : OHService(sTpProduct, sIdProduct, "OHRadio.xml", dev, udev)
{
    // Need Python for the radiopl playlist-to-audio-url script
    string pypath;
    if (!ExecCmd::which("python3", pypath)) {
        LOGINF("OHRadio: python3 not found, radio service will not work\n");
        return;
    }
    if (!readRadios()) {
        LOGINF("OHRadio: readRadios() failed, radio service will not work\n");
        return;
    }

    // Try to restore the channel if this was memorized.
    string refstr;
    if (g_state && g_state->get(cstr_sturlkey, refstr)) {
        for (unsigned int i = 0; i < o_radios.size(); i++) {
            string sms = stringsToString(o_radios[i].metaScript);
            const string& uri = o_radios[i].uri;
            if ((!uri.empty() && !uri.compare(refstr)) ||
                (uri.empty() && !sms.compare(refstr))) {
                m_id = i;
                break;
            }
        }
    }
    
    m_ok = true;
    
    udev->addActionMapping(this, "Channel",
                          bind(&OHRadio::channel, this, _1, _2));
    udev->addActionMapping(this, "ChannelsMax",
                          bind(&OHRadio::channelsMax, this, _1, _2));
    udev->addActionMapping(this, "Id",
                          bind(&OHRadio::id, this, _1, _2));
    udev->addActionMapping(this, "IdArray",
                          bind(&OHRadio::idArray, this, _1, _2));
    udev->addActionMapping(this, "IdArrayChanged",
                          bind(&OHRadio::idArrayChanged, this, _1, _2));
    udev->addActionMapping(this, "Pause",
                          bind(&OHRadio::pause, this, _1, _2));
    udev->addActionMapping(this, "Play",
                          bind(&OHRadio::play, this, _1, _2));
    udev->addActionMapping(this, "ProtocolInfo",
                          bind(&OHRadio::protocolInfo, this, _1, _2));
    udev->addActionMapping(this, "Read",
                          bind(&OHRadio::ohread, this, _1, _2));
    udev->addActionMapping(this, "ReadList",
                          bind(&OHRadio::readList, this, _1, _2));
    udev->addActionMapping(this, "SeekSecondAbsolute",
                          bind(&OHRadio::seekSecondAbsolute, this, _1, _2));
    udev->addActionMapping(this, "SeekSecondRelative",
                          bind(&OHRadio::seekSecondRelative, this, _1, _2));
    udev->addActionMapping(this, "SetChannel",
                          bind(&OHRadio::setChannel, this, _1, _2));
    udev->addActionMapping(this, "SetId",
                          bind(&OHRadio::setId, this, _1, _2));
    udev->addActionMapping(this, "Stop",
                          bind(&OHRadio::stop, this, _1, _2));
    udev->addActionMapping(this, "TransportState",
                          bind(&OHRadio::transportState, this, _1, _2));
    keepconsume = g_config->getBool("keepconsume", false);

    m_dev->getmpdcli()->subscribe(
        MPDCli::MpdQueueEvt|MPDCli::MpdPlayerEvt|MPDCli::MpdOptsEvt,
        std::bind(&OHService::onEvent, this, _1));
}

static void getRadiosFromConf(ConfSimple* conf)
{
    vector<string> allsubk = conf->getSubKeys_unsorted();
    for (auto it = allsubk.begin(); it != allsubk.end(); it++) {
        if (it->find("radio ") == 0) {
            string uri, artUri, artScript, metaScript, preferScript;
            string title = it->substr(6);
            conf->get("url", uri, *it);
            conf->get("artUrl", artUri, *it);
            conf->get("artScript", artScript, *it);
            trimstring(artScript, " \t\n\r");
            conf->get("metaScript", metaScript, *it);
            trimstring(metaScript, " \t\n\r");
            conf->get("preferScript", preferScript, *it);
            trimstring(preferScript, " \t\n\r");
            if (!uri.empty() || !metaScript.empty()) {
                o_radios.push_back(RadioMeta(title, uri, artUri, artScript,
                                             metaScript, preferScript));
                LOGDEB1("OHRadio::readRadios:RADIO: [" << title << "] uri ["
                        << uri << "] artUri [" << artUri << "] metaScript [" <<
                        metaScript << "] preferScript " << preferScript << endl);
            }
        }
    }
}

bool OHRadio::readRadios()
{
    // Id 0 means no selection /  externally set channel from setChannel()
    o_radios.push_back(RadioMeta("Unknown radio", "", "", "", "", ""));
    
    getRadiosFromConf(g_config);
    // Also if radiolist is defined, get from there
    string radiolistfn;
    if (g_config->get("radiolist", radiolistfn)) {
        ConfSimple rdconf(radiolistfn.c_str(), 1);
        if (!rdconf.ok()) {
            LOGERR("OHRadio::readRadios: failed initializing from " <<
                   radiolistfn << endl);
        } else {
            getRadiosFromConf(&rdconf);
        }
    }
    return true;
}

// The data format for id lists is an array of msb 32 bits ints
// encoded in base64. The values could be anything, but, for us, they
// are just the indices into o_radios(), beginning at 1 because 0 is
// special (it's reserved in o_radios too).
bool OHRadio::makeIdArray(string& out)
{
    //LOGDEB1("OHRadio::makeIdArray\n");
    string out1;
    for (unsigned int val = 1; val < o_radios.size(); val++) {
        out1 += (unsigned char) ((val & 0xff000000) >> 24);
        out1 += (unsigned char) ((val & 0x00ff0000) >> 16);
        out1 += (unsigned char) ((val & 0x0000ff00) >> 8);
        out1 += (unsigned char) ((val & 0x000000ff));
    }
    out = base64_encode(out1);
    return true;
}

void OHRadio::maybeExecMetaScript(RadioMeta& radio, MpdStatus &mpds)
{
    if (time(0) < radio.nextMetaScriptExecTime) {
        LOGDEB0("OHRadio::maybeExecMetaScript: next in " <<
                radio.nextMetaScriptExecTime - time(0) << endl);
        return;
    }

    string elapsedms("-1");
    if (mpds.state == MpdStatus::MPDS_PLAY) {
        elapsedms = SoapHelp::i2s(mpds.songelapsedms);
    }
    
    vector<string> args{radio.metaScript};
    args.push_back("elapsedms");
    args.push_back(elapsedms);
    string data;
    if (!ExecCmd::backtick(args, data)) {
        LOGERR("OHRadio::makestate: radio metascript failed\n");
        return;
    }
    LOGDEB0("OHRadio::makestate: metaScript got: [" << data << "]\n");

    // The data is in JSON format
    Json::Value decoded;
    try {
        istringstream input(data);
        input >> decoded;
    } catch (std::exception& e) {
        LOGERR("OHRadio::makestate: Json decode failed: " << e.what() <<
               " for [" << data << "]\n");
        radio.nextMetaScriptExecTime = time(0) + 10;
        return;
    }

    radio.dynTitle = decoded.get("title", "").asString();
    radio.dynArtist = decoded.get("artist", "").asString();
    radio.dynArtUri = decoded.get("artUrl", "").asString();
    int reload = decoded.get("reload", 10).asInt();
    if (reload < 2) {
        reload = 2;
    }
    radio.nextMetaScriptExecTime = time(0) + reload;
    
    // If the script returns an audio uri, queue it to mpd. Don't do
    // this while stopped
    string audioUri= decoded.get("audioUrl", "").asString();
    if (!audioUri.empty() &&
        (m_playpending || mpds.state == MpdStatus::MPDS_PLAY)) {
        vector<UpSong> queue;
        m_dev->getmpdcli()->getQueueData(queue);

        bool found = false;
        for (const auto& entry : queue) {
            if (entry.rsrc.uri == audioUri) {
                found = true;
                break;
            }
        }
        if (!found) {
            UpSong song;
            song.album = radio.title;
            song.rsrc.uri = audioUri;
            LOGDEB0("ohRadio:execmetascript: inserting: " << song.rsrc.uri <<
                    endl);
            m_dev->getmpdcli()->single(false);
            if (!keepconsume) {
                m_dev->getmpdcli()->consume(true);
            }
            if (m_dev->getmpdcli()->insert(audioUri, -1, song) < 0) {
                LOGERR("OHRadio::mkstate: mpd insert failed."<< " pos " <<
                       mpds.songpos << " uri " << audioUri << endl);
                return;
            }
        }

        // Start things up if needed.
        if (m_playpending && mpds.state != MpdStatus::MPDS_PLAY &&
            !m_dev->getmpdcli()->play(0)) {
            LOGERR("OHRadio::mkstate: mpd play failed\n");
            return;
        }
        radio.currentAudioUri = audioUri;
    }
}

bool OHRadio::makestate(unordered_map<string, string>& st)
{
    LOGDEB1("OHRadio::makestate\n");
    st.clear();

    MpdStatus mpds = m_dev->getMpdStatus();

    st["ChannelsMax"] = SoapHelp::i2s(o_radios.size());
    st["Id"] = SoapHelp::i2s(m_id);
    makeIdArray(st["IdArray"]);
    st["ProtocolInfo"] = Protocolinfo::the()->gettext();
    st["TransportState"] =  mpdstatusToTransportState(mpds.state);
    st["Metadata"] =  "";
    st["Uri"] = "";

    if (!m_active) {
        st["TransportState"] =  "Stopped";
        return true;
    }

    if (m_id < 0 || m_id >= o_radios.size()) {
        // ??
        LOGERR("OHRadio::makestate: bad m_id " << m_id << endl);
        return true;
    }
        
    RadioMeta& radio = o_radios[m_id];

    // In any case, Uri and Metadata are fixed and come from the channel.
    // The dynamic data is sent to ohinfo.
    st["Metadata"] = metaForId(m_id);
    // We used to set this to mpds.currentsong.rsrc.uri. From
    // re-reading the spec, using the radio uri seems more appropriate
    st["Uri"] = radio.uri.empty() ? radio.currentAudioUri:radio.uri;

    /////////////
    // Compute dynamic metadata for ohinfo

    if (mpds.currentsong.album.empty()) {
        mpds.currentsong.album = radio.title;
    }

    // Some radios do not insert icy metadata in the stream, but rather
    // provide a script to retrieve it.
    bool nompddata = mpds.currentsong.title.empty() &&
        mpds.currentsong.artist.empty();
    if ((m_playpending || mpds.state == MpdStatus::MPDS_PLAY) &&
        (radio.preferScript || nompddata) && radio.metaScript.size()) {
        maybeExecMetaScript(radio, mpds);
        mpds.currentsong.title = radio.dynTitle;
        mpds.currentsong.artist = radio.dynArtist;
    }
    if (mpds.currentsong.title.empty()) {
        mpds.currentsong.title = radio.title;
    }
        
    // Some radios provide a url to the art for the current song. 
    // Execute script to retrieve it if the current title+artist changed
    if (radio.artScript.size()) {
        string nsong(mpds.currentsong.title + mpds.currentsong.artist);
        if (nsong.compare(m_currentsong)) {
            m_currentsong = nsong;
            string uri;
            radio.dynArtUri.clear();
            if (ExecCmd::backtick(radio.artScript, uri)) {
                trimstring(uri, " \t\r\n");
                LOGDEB0("OHRadio::makestate: artScript got: [" << uri <<
                        "]\n");
                radio.dynArtUri = uri;
            }
        }
    }
    mpds.currentsong.artUri = radio.dynArtUri.empty() ? radio.artUri :
        radio.dynArtUri;

    // Don't report the ever changing bitrate, this causes unnecessary
    // events. CPs interested in bitrate changes can get them from the
    // Info service Details state variable
    if (st["TransportState"] == "Stopped") {
        m_udev->getohif()->setMetadata(st["Metadata"], st["Metadata"]);
    } else {
        string metatext = didlmake(mpds.currentsong, true);
        m_udev->getohif()->setMetadata(st["Metadata"], metatext);
    }
    return true;
}

int OHRadio::setPlaying()
{
    if (m_id >= o_radios.size()) {
        LOGERR("OHRadio::setPlaying: called with bad id (" << m_id << ")\n");
        return UPNP_E_INTERNAL_ERROR;
    }

    RadioMeta& radio = o_radios[m_id];
    radio.nextMetaScriptExecTime = 0;

    if (radio.uri.empty() && radio.metaScript.empty()) {
        LOGERR("OHRadio::setPlaying: both URI and metascript are empty !\n");
        return UPNP_E_INVALID_PARAM;
    }

    if (radio.uri.empty()) {
        // We count on the metascript to also return an audio URI,
        // which will be sent to MPD during makestate().
        radio.currentAudioUri.clear();
        m_playpending = true;
        m_dev->getmpdcli()->clearQueue();
        return UPNP_E_SUCCESS;
    }
    
    string cmdpath = path_cat(g_datadir, "rdpl2stream");
    cmdpath = path_cat(cmdpath, "fetchStream.py");

    // Execute the playlist parser
    ExecCmd cmd;
    vector<string> args;
    args.push_back(radio.uri);
    LOGDEB("OHRadio::setPlaying: exec: " << cmdpath << " " << args[0] << endl);
    if (cmd.startExec(cmdpath, args, false, true) < 0) {
        LOGDEB("OHRadio::setPlaying: startExec failed for " <<
               cmdpath << " " << args[0] << endl);
        return UPNP_E_INTERNAL_ERROR;
    }

    // Read actual audio stream url
    string audiourl;
    if (cmd.getline(audiourl, 10) < 0) {
        LOGDEB("OHRadio::setPlaying: could not get audio url\n");
        return UPNP_E_INTERNAL_ERROR;
    }
    trimstring(audiourl, "\r\n");
    if (audiourl.empty()) {
        LOGDEB("OHRadio::setPlaying: audio url empty\n");
        return UPNP_E_INTERNAL_ERROR;
    }

    // Send url to mpd
    m_dev->getmpdcli()->clearQueue();
    UpSong song;
    song.album = radio.title;
    song.rsrc.uri = radio.uri;
    if (m_dev->getmpdcli()->insert(audiourl, 0, song) < 0) {
        LOGDEB("OHRadio::setPlaying: mpd insert failed\n");
        return UPNP_E_INTERNAL_ERROR;
    }
    m_dev->getmpdcli()->single(true);
    if (!m_dev->getmpdcli()->play(0)) {
        LOGDEB("OHRadio::setPlaying: mpd play failed\n");
        return UPNP_E_INTERNAL_ERROR;
    }
    return UPNP_E_SUCCESS;
}

void OHRadio::setActive(bool onoff)
{
    LOGDEB0("OHRadio::setActive: " << onoff << endl);
    m_active = onoff;
    if (m_active) {
        if (m_id) {
            // Only restore state if it was saved
            if (m_mpdsavedstate.status.state != MpdStatus::MPDS_UNK) {
                m_dev->getmpdcli()->restoreState(m_mpdsavedstate);
            }
        }
        onEvent(nullptr);
    } else {
        m_dev->getmpdcli()->saveState(m_mpdsavedstate);
        m_dev->getmpdcli()->clearQueue();
        iStop();
    }
}

int OHRadio::iPlay()
{
    int ret = setPlaying();
    return ret;
}

int OHRadio::play(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::play" << endl);
    if (!m_active && m_udev->getohpr()) {
        m_udev->getohpr()->iSetSourceIndexByName("Radio");
    }
    return iPlay();
}

int OHRadio::pause(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::pause" << endl);
    bool ok = m_dev->getmpdcli()->pause(true);
    m_playpending = false;
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHRadio::iStop()
{
    bool ok = m_dev->getmpdcli()->stop();
    m_playpending = false;
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}
int OHRadio::stop(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::stop" << endl);
    return iStop();
}

int OHRadio::channel(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::channel" << endl);
    data.addarg("Uri", m_state["Uri"]);
    data.addarg("Metadata", m_state["Metadata"]);
    return UPNP_E_SUCCESS;
}

int OHRadio::setChannel(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::setChannel" << endl);
    string uri, metadata;
    bool ok = sc.get("Uri", &uri) && sc.get("Metadata", &metadata);
    if (ok) {
        iStop();
        m_id = 0;
        o_radios[0].uri = uri;
        UpSong ups;
        uMetaToUpSong(metadata, &ups);
        o_radios[0].title = ups.album + " " + ups.title;
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHRadio::setId(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::setId" << endl);
    int id;
    if (!sc.get("Value", &id)) {
        LOGDEB("OHRadio::setId: no value ??\n");
        return UPNP_E_INTERNAL_ERROR;
    }
    if (id <= 0 || id > int(o_radios.size())) {
        LOGDEB("OHRadio::setId: bad value " << id << endl);
        return UPNP_E_INTERNAL_ERROR;
    }
    iStop();
    m_id = id;

    // Memorize the current radio (for restart).  We use either the
    // static uri or the metaScript to identify the radio
    if (g_state) {
        string refstr = o_radios[m_id].uri.empty() ?
            stringsToString(o_radios[m_id].metaScript) : o_radios[m_id].uri;
        g_state->set(cstr_sturlkey, refstr);
    }
    
    return UPNP_E_SUCCESS;
}

// Return current channel Id. 
int OHRadio::id(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::id" << endl);
    data.addarg("Value", SoapHelp::i2s(m_id));
    return UPNP_E_SUCCESS;
}

// This is called from read, and readlist. Don't send current metadata
// (including dynamic art and song title) for the current channel,
// else the radio logo AND name are replaced by the song's in channel
// selection interfaces. Only send the song metadata from the Info
// service metatext variable
string OHRadio::metaForId(unsigned int id)
{
    LOGDEB1("OHRadio::metaForId: id " << id << " m_id " << m_id << endl);
    if (id  >= o_radios.size()) {
        return string();
    }
    UpSong usong;
    usong.title = o_radios[id].title;
    // Kazoo absolutely does not want uri to be empty, else it
    // does not display anything in the radio list (not even the
    // entries with uris). So fill up with bogus value. This is
    // not used anyway because setId/setPlaying use the value from
    // the radio array or from the metascript
    usong.rsrc.uri = o_radios[id].uri.empty() ?
        "http://www.bogus.com/bogus.mp3" : o_radios[id].uri;
    usong.artUri = o_radios[id].artUri;
    return didlmake(usong);
}

// Report the metadata for a given channel id.
int OHRadio::ohread(const SoapIncoming& sc, SoapOutgoing& data)
{
    int id;
    bool ok = sc.get("Id", &id);
    if (ok) {
        LOGDEB("OHRadio::read id " << id << endl);
        if (id >= 0 && id  < int(o_radios.size())) {
            string meta = metaForId(id);
            data.addarg("Metadata", meta);
        } else {
            ok = false;
        }
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

// Given a space separated list of track Id's, report their associated
// metadata in the following xml form:
//
//  <TrackList>
//    <Entry>
//      <Id></Id>
//      <Metadata></Metadata>
//    </Entry>
//  </TrackList>
//
// Any ids not in the radio are ignored.
int OHRadio::readList(const SoapIncoming& sc, SoapOutgoing& data)
{
    string sids;

    bool ok = sc.get("IdList", &sids);
    LOGDEB("OHRadio::readList: [" << sids << "]" << endl);

    vector<string> ids;
    string out("<ChannelList>");
    if (ok) {
        stringToTokens(sids, ids);
        for (auto strid : ids) {
            int id = atoi(strid.c_str());
            if (id <= 0 || id >= int(o_radios.size())) {
                LOGDEB("OHRadio::readlist: bad id " << id << endl);
                continue;
            }
            string meta = metaForId(id);
            out += "<Entry><Id>";
            out += strid;
            out += "</Id><Metadata>";
            out += SoapHelp::xmlQuote(meta);
            out += "</Metadata></Entry>";
        }
        out += "</ChannelList>";
        LOGDEB0("OHRadio::readList: out: [" << out << "]" << endl);
        data.addarg("ChannelList", out);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

// Returns current list of id as array of big endian 32bits integers,
// base-64-encoded.
int OHRadio::idArray(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::idArray" << endl);
    string idarray;
    if (makeIdArray(idarray)) {
        data.addarg("Token", SoapHelp::i2s(1));
        data.addarg("Array", idarray);
        return UPNP_E_SUCCESS;
    }
    return UPNP_E_INTERNAL_ERROR;
}

int OHRadio::seekSecondAbsolute(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::seekSecondAbsolute" << endl);
    int seconds;
    bool ok = sc.get("Value", &seconds);
    if (ok) {
        ok = m_dev->getmpdcli()->seek(seconds);
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHRadio::seekSecondRelative(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::seekSecondRelative" << endl);
    int seconds;
    bool ok = sc.get("Value", &seconds);
    if (ok) {
        const MpdStatus& mpds =  m_dev->getMpdStatus();
        bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) ||
            (mpds.state == MpdStatus::MPDS_PAUSE);
        if (is_song) {
            seconds += mpds.songelapsedms / 1000;
            ok = m_dev->getmpdcli()->seek(seconds);
        } else {
            ok = false;
        }
    }
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHRadio::transportState(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::transportState" << endl);
    const MpdStatus& mpds = m_dev->getMpdStatus();
    string tstate;
    switch (mpds.state) {
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

// Check if id array changed since last call (which returned a gen
// token). Our array never changes
int OHRadio::idArrayChanged(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::idArrayChanged" << endl);
    data.addarg("Value", SoapHelp::i2s(0));
    return UPNP_E_SUCCESS;
}

int OHRadio::channelsMax(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::channelsMax" << endl);
    data.addarg("Value", SoapHelp::i2s(o_radios.size()));
    return UPNP_E_SUCCESS;
}

int OHRadio::protocolInfo(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHRadio::protocolInfo" << endl);
    data.addarg("Value", Protocolinfo::the()->gettext());
    return UPNP_E_SUCCESS;
}
