/* Copyright (C) 2014-2020 J.F.Dockes
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU Lesser General Public License as published by
 *  the Free Software Foundation; either version 2.1 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU Lesser General Public License for more details.
 *
 *  You should have received a copy of the GNU Lesser General Public License
 *  along with this program; if not, write to the
 *  Free Software Foundation, Inc.,
 *  59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#include "config.h"

#include "ohinfo.hxx"

#include <functional>
#include <iostream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"

#include "mpdcli.hxx"
#include "upmpd.hxx"
#include "upmpdutils.hxx"
#include "ohplaylist.hxx"

using namespace std;
using namespace std::placeholders;

static const string sTpProduct("urn:av-openhome-org:service:Info:1");
static const string sIdProduct("urn:av-openhome-org:serviceId:Info");

OHInfo::OHInfo(UpMpd *dev, UpMpdOpenHome *udev, bool updstatus)
    : OHService(sTpProduct, sIdProduct, "OHInfo.xml", dev, udev),
      m_updstatus(updstatus)
{
    udev->addActionMapping(this, "Counters", 
                           bind(&OHInfo::counters, this, _1, _2));
    udev->addActionMapping(this, "Track", 
                           bind(&OHInfo::track, this, _1, _2));
    udev->addActionMapping(this, "Details", 
                           bind(&OHInfo::details, this, _1, _2));
    udev->addActionMapping(this, "Metatext", 
                           bind(&OHInfo::metatext, this, _1, _2));
    m_dev->getmpdcli()->subscribe(
        MPDCli::MpdQueueEvt|MPDCli::MpdPlayerEvt,
        std::bind(&OHService::onEvent, this, _1));
}

void OHInfo::urimetadata(string& uri, string& metadata)
{
    const MpdStatus &mpds =  m_dev->getMpdStatus();
    bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
        (mpds.state == MpdStatus::MPDS_PAUSE);

    // If somebody (e.g. ohradio) took care to set the metadata, use it.
    // Metadata is reset by OHProduct::setSourceIndex.
    if (!m_metadata.empty()) {
        metadata = m_metadata;
    } else {
        if (is_song) {
            uri = mpds.currentsong.rsrc.uri;
            // Playlist or AVTransport playing, probably.
            // Prefer metadata from cache (copy from media server) to
            // whatever comes from mpd.
            if (m_ohpl && m_ohpl->cacheFind(uri, metadata)) {
                return;
            }
            metadata = didlmake(mpds.currentsong);
        } else {
            uri.clear();
            metadata.clear();
        }
    }
}

void OHInfo::makedetails(string &duration, string& bitrate, 
                         string& bitdepth, string& samplerate)
{
    const MpdStatus mpds =  m_dev->getMpdStatus();

    bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
        (mpds.state == MpdStatus::MPDS_PAUSE);

    if (is_song) {
        duration = SoapHelp::i2s(mpds.songlenms / 1000);
        bitrate = SoapHelp::i2s(mpds.kbrate * 1000);
        bitdepth = SoapHelp::i2s(mpds.bitdepth);
        samplerate = SoapHelp::i2s(mpds.sample_rate);
    } else {
        duration = bitrate = bitdepth = samplerate = "0";
    }
}

// For radios: Metadata is for the static channel name. Metatext is
// for the current song. Both are didl.
bool OHInfo::makestate(unordered_map<string, string> &st)
{
    st.clear();
    st["TrackCount"] = SoapHelp::i2s(m_dev->getMpdStatus().trackcounter);
    st["DetailsCount"] = SoapHelp::i2s(m_dev->getMpdStatus().detailscounter);
    st["MetatextCount"] = SoapHelp::i2s(m_metatextcnt);
    string uri, metadata;
    urimetadata(uri, metadata);
    st["Uri"] = uri;
    st["Metadata"] = metadata;
    st["Metatext"] = m_metatext;
    makedetails(st["Duration"], st["BitRate"], st["BitDepth"],st["SampleRate"]);
    st["Lossless"] = "0";
    st["CodecName"] = "";
    return true;
}

int OHInfo::counters(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHInfo::counters" << endl);
    
    data.addarg("TrackCount",
                SoapHelp::i2s(m_dev->getMpdStatus().trackcounter));
    data.addarg("DetailsCount", SoapHelp::i2s(
                    m_dev->getMpdStatus().detailscounter));
    data.addarg("MetatextCount", SoapHelp::i2s(m_metatextcnt));
    return UPNP_E_SUCCESS;
}

int OHInfo::track(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHInfo::track" << endl);

    string uri, metadata;
    urimetadata(uri, metadata);
    data.addarg("Uri", uri);
    data.addarg("Metadata", metadata);
    return UPNP_E_SUCCESS;
}

int OHInfo::details(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHInfo::details" << endl);

    string duration, bitrate, bitdepth, samplerate;
    makedetails(duration, bitrate, bitdepth, samplerate);
    data.addarg("Duration", duration);
    data.addarg("BitRate", bitrate);
    data.addarg("BitDepth", bitdepth);
    data.addarg("SampleRate", samplerate);
    data.addarg("Lossless", "0");
    data.addarg("CodecName", "");
    return UPNP_E_SUCCESS;
}

// See note above about metatext/metadata, this is wrong.
int OHInfo::metatext(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHInfo::metatext" << endl);
    data.addarg("Value", m_state["Metatext"]);
    return UPNP_E_SUCCESS;
}

// Called from ohradio only at the moment. Should we call it from playlist?
void OHInfo::setMetadata(const string& metadata, const string& metatext)
{
    LOGDEB1("OHInfo::setMetadata: " << metadata << endl);
    m_metadata = metadata;
    if (metatext != m_metatext) {
        m_metatext = metatext;
        m_metatextcnt++;
    }
}
