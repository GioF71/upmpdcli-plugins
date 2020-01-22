/* Copyright (C) 2014 J.F.Dockes
 *	 This program is free software; you can redistribute it and/or modify
 *	 it under the terms of the GNU Lesser General Public License as published by
 *	 the Free Software Foundation; either version 2.1 of the License, or
 *	 (at your option) any later version.
 *
 *	 This program is distributed in the hope that it will be useful,
 *	 but WITHOUT ANY WARRANTY; without even the implied warranty of
 *	 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *	 GNU Lesser General Public License for more details.
 *
 *	 You should have received a copy of the GNU Lesser General Public License
 *	 along with this program; if not, write to the
 *	 Free Software Foundation, Inc.,
 *	 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#include "config.h"

#include "ohreceiver.hxx"

#include <stdlib.h>                     // for atoi

#include <functional>                   // for _Bind, bind, _1, _2
#include <iostream>                     // for endl, etc
#include <string>                       // for string, allocator, etc
#include <utility>                      // for pair
#include <vector>                       // for vector

#include "libupnpp/log.hxx"             // for LOGDEB, LOGERR
#include "libupnpp/soaphelp.hxx"        // for SoapIncoming, SoapOutgoing, i2s, etc

#include "conftree.h"
#include "mpdcli.hxx"                   // for MpdStatus, UpSong, MPDCli, etc
#include "upmpd.hxx"                    // for UpMpd, etc
#include "upmpdutils.hxx"               // for didlmake, diffmaps, etc
#include "ohplaylist.hxx"
#include "ohproduct.hxx"

using namespace std;
using namespace std::placeholders;

static const string sTpProduct("urn:av-openhome-org:service:Receiver:1");
static const string sIdProduct("urn:av-openhome-org:serviceId:Receiver");

OHReceiver::OHReceiver(UpMpd *dev, const OHReceiverParams& parms)
    : OHService(sTpProduct, sIdProduct, "OHReceiver.xml", dev), m_active(false),
      m_httpport(parms.httpport), m_sc2mpdpath(parms.sc2mpdpath), m_pm(parms.pm)
{
    dev->addActionMapping(this, "Play", 
                          bind(&OHReceiver::play, this, _1, _2));
    dev->addActionMapping(this, "Stop", 
                          bind(&OHReceiver::stop, this, _1, _2));
    dev->addActionMapping(this, "SetSender",
                          bind(&OHReceiver::setSender, this, _1, _2));
    dev->addActionMapping(this, "Sender", 
                          bind(&OHReceiver::sender, this, _1, _2));
    dev->addActionMapping(this, "ProtocolInfo",
                          bind(&OHReceiver::protocolInfo, this, _1, _2));
    dev->addActionMapping(this, "TransportState",
                          bind(&OHReceiver::transportState, this, _1, _2));

    m_httpuri = "http://localhost:"+ SoapHelp::i2s(m_httpport) + 
        "/Songcast.wav";

    if (!parms.screceiverstatefile.empty()) {
        m_conf = new ConfSimple(parms.screceiverstatefile.c_str());
        if (!m_conf->ok()) {
            LOGERR("OHReceiver: failed initializing from " <<
                   parms.screceiverstatefile << endl);
        } else {
            setSenderFromConf();
        }
    }
}

void OHReceiver::setSenderFromConf()
{
    m_conf->get("scsenderuri", m_uri);
    m_conf->get("scsendermetadata", m_metadata);
    LOGDEB("OHReceiver: scsenderuri: " << m_uri << endl);
    LOGDEB("OHReceiver: scsendermetadata: " << m_metadata << endl);
}

void OHReceiver::writeSenderToConf()
{
    bool ok;
    ok = m_conf->set("scsenderuri", m_uri);
    if (!ok)
        LOGERR("OHReceiver: failed writing uri to conf." << endl);
    ok = m_conf->set("scsendermetadata", m_metadata);
    if (!ok)
        LOGERR("OHReceiver: failed writing metadata to conf." << endl);
}

static const string o_protocolinfo("ohz:*:*:*,ohm:*:*:*,ohu:*.*.*");

bool OHReceiver::makestate(unordered_map<string, string> &st)
{
    if (m_pm == OHReceiverParams::OHRP_MPD) {
        const MpdStatus &mpds = m_dev->getMpdStatusNoUpdate();
        if (m_cmd && mpds.state != MpdStatus::MPDS_PLAY && 
            mpds.state != MpdStatus::MPDS_PAUSE) {
            // playing was stopped through ohplaylist or
            // avtransport. I'm not sure we're supposed to let this
            // happen, but we do. Stop too.
            iStop();
        }
    } else {
        if (m_cmd) {
            int status;
            if (m_cmd->maybereap(&status)) {
                LOGDEB("OHReceiver: sc2cmd exited with status " << status
                       << endl);
                m_cmd = shared_ptr<ExecCmd>(new ExecCmd());
            }
        }
    }

    st.clear();

    st["Uri"] = m_uri;
    st["Metadata"] = m_metadata;
    // Allowed states: Stopped, Playing,Waiting, Buffering
    // We won't receive a Stop action if we are not Playing. So we
    // are playing as long as we have a subprocess
    if (m_cmd)
        st["TransportState"] = "Playing";
    else 
        st["TransportState"] = "Stopped";
    st["ProtocolInfo"] = o_protocolinfo;
    return true;
}

void OHReceiver::maybeWakeUp(bool ok)
{
    if (ok && m_dev)
        m_dev->loopWakeup();
}

void OHReceiver::setActive(bool onoff)
{
    m_active = onoff;
    if (!m_active)
        iStop();
}

bool OHReceiver::iPlay()
{
    bool ok = false;

    if (!m_dev->m_ohpl) {
        LOGERR("OHReceiver::play: no playlist service" << endl);
        return false;
    }
    if (m_uri.empty()) {
        LOGERR("OHReceiver::play: no uri" << endl);
        return false;
    }
    if (m_metadata.empty()) {
        LOGERR("OHReceiver::play: no metadata" << endl);
        return false;
    }

    int id = -1;
    unordered_map<int, string> urlmap;
    string line;
        
    // We start the songcast command to receive the audio flux and either
    // export it as HTTP (then insert http URI at the front of the
    // queue and execute next/play), or play it directly to the sound card
    if (m_cmd)
        m_cmd->zapChild();
    m_cmd = shared_ptr<ExecCmd>(new ExecCmd());
    vector<string> args;
    if (m_pm == OHReceiverParams::OHRP_ALSA) {
        args.push_back("-d");
    }
    args.push_back("-u");
    args.push_back(m_uri);
    if (!g_configfilename.empty()) {
        args.push_back("-c");
        args.push_back(g_configfilename);
    }
        
    LOGDEB("OHReceiver::play: executing " << m_sc2mpdpath << endl);
    ok = m_cmd->startExec(m_sc2mpdpath, args, false, true) >= 0;
    if (!ok) {
        LOGERR("OHReceiver::play: executing " << m_sc2mpdpath << " failed" 
               << endl);
        goto out;
    } else {
        LOGDEB("OHReceiver::play: sc2mpd pid "<< m_cmd->getChildPid()<< endl);
    }

    if (m_pm == OHReceiverParams::OHRP_MPD) {
        m_dev->m_mpdcli->stop();

        // Wait for sc2mpd to signal ready, then play.
        // sc2mpd writes a single line to stdout "CONNECTED" when
        // it gets there, which should be more or less instantaneous
        int timeo = 15;
        if (m_cmd->getline(line, timeo) < 0) {
            LOGERR("OHReceiver: mpd mode: sc2mpd still not ready to play after "
                   << timeo << " seconds\n");
            goto out;
        }
        LOGDEB("OHReceiver: sc2mpd sent: " << line);
        // And insert the appropriate uri in the mpd playlist
        if (!m_dev->m_ohpl->urlMap(urlmap)) {
            LOGERR("OHReceiver::play: urlMap() failed" <<endl);
            goto out;
        }
        for (auto it = urlmap.begin(); it != urlmap.end(); it++) {
            if (it->second == m_httpuri) {
                id = it->first;
            }
        }
        if (id == -1) {
            UpSong metaformpd;
            string metadata(SoapHelp::xmlUnquote(m_metadata));
            if (!uMetaToUpSong(metadata, &metaformpd)) {
                LOGERR("OHReceiver::play: failed to parse metadata " << " Uri [" 
                       << m_httpuri << "] Metadata [" << metadata << "]"
                       << endl);
                goto out;
            }
            id = m_dev->m_mpdcli->insertAfterId(m_httpuri, 0, metaformpd);
            if (id == -1) {
                LOGERR("OHReceiver::play: insertAfterId() failed\n");
                goto out;
            }
        }

        ok = m_dev->m_mpdcli->playId(id);
        if (!ok) {
            LOGERR("OHReceiver::play: play() failed\n");
            goto out;
        }
    }

out:
    if (!ok) {
        iStop();
    }
    return ok;
}

int OHReceiver::play(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHReceiver::play" << endl);
    if (!m_active && m_dev->m_ohpr)
        m_dev->m_ohpr->iSetSourceIndexByName("Receiver");
    bool ok = iPlay();
    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

bool OHReceiver::iStop()
{
    LOGDEB("OHReceiver::iStop()\n");
    if (m_cmd) {
        m_cmd->zapChild();
        m_cmd = shared_ptr<ExecCmd>();
    }

    if (m_pm == OHReceiverParams::OHRP_MPD) {
        m_dev->m_mpdcli->stop();
        unordered_map<int, string> urlmap;
        // Remove our bogus URi from the playlist
        if (!m_dev->m_ohpl->urlMap(urlmap)) {
            LOGERR("OHReceiver::stop: urlMap() failed" <<endl);
        }
        for (auto it = urlmap.begin(); it != urlmap.end(); it++) {
            if (it->second == m_httpuri) {
                m_dev->m_mpdcli->deleteId(it->first);
            }
        }
    }
    
    return true;
}

int OHReceiver::stop(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHReceiver::stop" << endl);
    iStop();

    // At least the songcast windows driver never resets the source
    // index (it does call stop when it deconnects).
    // I guess that there is no reason to reset the source, and
    // another CP could just set it to what it wants, but Bubble at
    // least won't do a thing with the renderer as long as the source
    // is set to receiver.
    if (m_dev->m_ohpr)
        m_dev->m_ohpr->iSetSourceIndexByName("Playlist");

    maybeWakeUp(true);
    return UPNP_E_SUCCESS;
}

bool OHReceiver::iSetSender(const string& uri, const string& metadata)
{
    // Only do something if data changes, and then first stop any
    // current playing. We probably should not receive this if we're
    // not in the stopped state, but just in case...
    if (m_uri.compare(uri) || m_metadata.compare(metadata)) {
        if (m_cmd)
            iStop();
        m_uri = uri;
        m_metadata = metadata;
        if (m_conf && m_conf->ok())
            writeSenderToConf();
        LOGDEB("OHReceiver::setSender: uri [" << m_uri << "] meta [" << 
               m_metadata << "]" << endl);
    }
    return true;
}

int OHReceiver::setSender(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHReceiver::setSender" << endl);
    string uri, metadata;
    bool ok = sc.get("Uri", &uri) && sc.get("Metadata", &metadata);
    if (ok) {
        ok = iSetSender(uri, metadata);
    }

    maybeWakeUp(ok);
    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHReceiver::sender(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHReceiver::sender" << endl);
    data.addarg("Uri", m_uri);
    data.addarg("Metadata", m_metadata);
    return UPNP_E_SUCCESS;
}

int OHReceiver::transportState(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHReceiver::transportState" << endl);

    // Allowed states: Stopped, Playing,Waiting, Buffering
    // We won't receive a Stop action if we are not Playing. So we
    // are playing as long as we have a subprocess
    string tstate = m_cmd ? "Playing" : "Stopped";
    data.addarg("Value", tstate);
    LOGDEB("OHReceiver::transportState: " << tstate << endl);
    return UPNP_E_SUCCESS;
}

int OHReceiver::protocolInfo(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHReceiver::protocolInfo" << endl);
    data.addarg("Value", o_protocolinfo);
    return UPNP_E_SUCCESS;
}
