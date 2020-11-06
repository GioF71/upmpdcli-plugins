/* Copyright (C) 2016 J.F.Dockes
 *     This program is free software; you can redistribute it and/or modify
 *     it under the terms of the GNU Lesser General Public License as published by
 *     the Free Software Foundation; either version 2.1 of the License, or
 *     (at your option) any later version.
 *
 *     This program is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU Lesser General Public License for more details.
 *
 *     You should have received a copy of the GNU Lesser General Public License
 *     along with this program; if not, write to the
 *     Free Software Foundation, Inc.,
 *     59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#ifndef _OHSERVICE_H_X_INCLUDED_
#define _OHSERVICE_H_X_INCLUDED_

#include <string>         
#include <unordered_map>  
#include <vector>         

#include "libupnpp/device/device.hxx"
#include "upmpdutils.hxx"
#include "upmpd.hxx"
#include "mpdcli.hxx"

using namespace UPnPP;

// A parent class for all openhome service, to share a bit of state
// variable and event management code.
class OHService : public UPnPProvider::UpnpService {
public:
    OHService(const std::string& servtp, const std::string &servid,
              const std::string& xmlfn, UpMpd *dev, UpMpdOpenHome *udev)
        : UpnpService(servtp, servid, xmlfn, udev), m_dev(dev), m_udev(udev) {
    }
    virtual ~OHService() { }

    virtual bool getEventData(bool all, std::vector<std::string>& names, 
                              std::vector<std::string>& values) {
        //LOGDEB("OHService::getEventData" << std::endl);

        std::unordered_map<std::string, std::string> state, changed;
        makestate(state);
        if (all) {
            changed = state;
        } else {
            changed = diffmaps(m_state, state);
        }
        m_state = state;

        for (auto& it : changed) {
            //LOGDEB("OHService: state change: " << it.first << " -> "
            // << it.second << endl);
            names.push_back(it.first);
            values.push_back(it.second);
        }

        return true;
    }

    static std::string mpdstatusToTransportState(MpdStatus::State st) {
        switch (st) {
        case MpdStatus::MPDS_PLAY:
            return "Playing";
        case MpdStatus::MPDS_PAUSE:
            return "Paused";
        default:
            return "Stopped";
        }
    }
    
protected:
    virtual bool makestate(std::unordered_map<std::string, std::string> &) = 0;
    // State variable storage
    std::unordered_map<std::string, std::string> m_state;
    UpMpd *m_dev;
    UpMpdOpenHome *m_udev;
};

#endif /* _OHSERVICE_H_X_INCLUDED_ */
