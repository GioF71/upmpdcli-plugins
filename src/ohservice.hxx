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
#ifndef _OHSERVICE_H_X_INCLUDED_
#define _OHSERVICE_H_X_INCLUDED_

#include <string>         
#include <unordered_map>  
#include <vector>         
#include <mutex>

#include "libupnpp/device/device.hxx"
#include "mpdcli.hxx"

using namespace UPnPP;

class MpdStatus;
class UpMpdOpenHome;
class UpMpd;

// A parent class for all openhome service, to share a bit of state
// variable and event management code.
class OHService : public UPnPProvider::UpnpService {
public:
    OHService(const std::string& servtp, const std::string &servid,
              const std::string& xmlfn, UpMpd *dev, UpMpdOpenHome *udev);
    virtual ~OHService() = default;

    virtual void onEvent(const MpdStatus*);

    virtual bool getEventData(bool all, std::vector<std::string>& names, 
                              std::vector<std::string>& values);
    static std::string mpdstatusToTransportState(MpdStatus::State st);
    
protected:
    virtual bool makestate(std::unordered_map<std::string, std::string> &) = 0;
    // State variable storage
    std::unordered_map<std::string, std::string> m_state;
    UpMpd *m_dev;
    UpMpdOpenHome *m_udev;
    std::mutex m_statemutex;
    std::string m_tpname;
};

#endif /* _OHSERVICE_H_X_INCLUDED_ */
