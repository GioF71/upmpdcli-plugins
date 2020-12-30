/* Copyright (C) 2016-2020 J.F.Dockes
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
#include "ohservice.hxx"

#include <string>         
#include <unordered_map>  
#include <vector>         
#include <functional>
#include <mutex>

#include "libupnpp/device/device.hxx"
#include "libupnpp/log.h"
#include "upmpdutils.hxx"
#include "upmpd.hxx"
#include "mpdcli.hxx"
#include "smallut.h"

using namespace UPnPP;

OHService::OHService(const std::string& servtp, const std::string &servid,
                     const std::string& xmlfn, UpMpd *dev, UpMpdOpenHome *udev)
    : UpnpService(servtp, servid, xmlfn, udev), m_dev(dev), m_udev(udev)
{
    std::vector<std::string> toks;
    stringToTokens(servtp, toks, ":");
    m_tpname = toks[toks.size()-2];
}

void OHService::onEvent(const MpdStatus*)
{
    LOGDEB1("OHService::onEvent()\n");
    std::vector<std::string> names, values;
    getEventData(false, names, values);
    if (!names.empty()) {
        m_udev->notifyEvent(this, names, values);
    }
}

bool OHService::getEventData(bool all, std::vector<std::string>& names, 
                             std::vector<std::string>& values)
{
    std::unique_lock<std::mutex> lock(m_statemutex);
    LOGDEB1("OHService::getEventData" << "\n");
            
    std::unordered_map<std::string, std::string> state, changed;
    makestate(state);
    if (all) {
        changed = state;
    } else {
        changed = diffmaps(m_state, state);
    }
    m_state = state;

    for (auto& it : changed) {
        LOGDEB0(m_tpname << ": change: " << it.first << " -> "<<it.second<<"\n");
        names.push_back(it.first);
        values.push_back(it.second);
    }

    return true;
}

std::string OHService::mpdstatusToTransportState(MpdStatus::State st)
{
    switch (st) {
    case MpdStatus::MPDS_PLAY:
        return "Playing";
    case MpdStatus::MPDS_PAUSE:
        return "Paused";
    default:
        return "Stopped";
    }
}
