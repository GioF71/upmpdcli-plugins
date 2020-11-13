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

#include "ohtime.hxx"

#include <functional>
#include <iostream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
#include <thread>
#include <chrono>

#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"

#include "mpdcli.hxx"
#include "upmpd.hxx"
#include "upmpdutils.hxx"
#include "smallut.h"

using namespace std;
using namespace std::placeholders;

static const string sTpProduct("urn:av-openhome-org:service:Time:1");
static const string sIdProduct("urn:av-openhome-org:serviceId:Time");

OHTime::OHTime(UpMpd *dev, UpMpdOpenHome *udev)
    : OHService(sTpProduct, sIdProduct, "OHTime.xml", dev, udev)
{
    udev->addActionMapping(this, "Time", bind(&OHTime::ohtime, this, _1, _2));

    m_dev->getmpdcli()->subscribe(
        MPDCli::MpdPlayerEvt, std::bind(&OHService::onEvent, this, _1));
}

void OHTime::getdata(string& trackcount, string &duration, 
                     string& seconds)
{
    // We're relying on AVTransport to have updated the status for us
    const MpdStatus& mpds =  m_dev->getMpdStatus();

    trackcount = SoapHelp::i2s(mpds.trackcounter);

    bool is_song = (mpds.state == MpdStatus::MPDS_PLAY) || 
        (mpds.state == MpdStatus::MPDS_PAUSE);
    if (is_song) {
        duration = SoapHelp::i2s(mpds.songlenms / 1000);
        seconds = SoapHelp::i2s(mpds.songelapsedms / 1000);
    } else {
        duration = "0";
        seconds = "0";
    }
}

bool OHTime::makestate(unordered_map<string, string> &st)
{
    st.clear();
    getdata(st["TrackCount"], st["Duration"], st["Seconds"]);
    return true;
}

int OHTime::ohtime(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHTime::ohtime" << endl);
    string trackcount, duration, seconds;
    getdata(trackcount, duration, seconds);
    data.addarg("TrackCount", trackcount);
    data.addarg("Duration", duration);
    data.addarg("Seconds", seconds);
    return UPNP_E_SUCCESS;
}
