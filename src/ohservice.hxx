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

    // This is called from the mpd event loop when something
    // changes. It in turn calls getEventData() and sends the result
    // to libupnpp::notifyEvent()
    virtual void onEvent(const MpdStatus*);

    // Retrieve the service changed state data. This now normally
    // called from onEvent(), bit it is kept as a separate entry,
    // because, we could still also decide not to start the mpd idle
    // loop and rely instead on polling from libupnpp.
    virtual bool getEventData(bool all, std::vector<std::string>& names, 
                              std::vector<std::string>& values);

    // Translate mpd play/stop... state into openhome transportstate.
    static std::string mpdstatusToTransportState(MpdStatus::State st);
    
protected:

    // This is implemented by each service to return the current state
    // of its variables.
    virtual bool makestate(std::unordered_map<std::string, std::string> &) = 0;

    // Storage for the state from the last makestate() call. Used by
    // the services when reporting current state from actions, and for
    // diffing with next makestate() values.
    std::unordered_map<std::string, std::string> m_state;

    // Local state protection mutex. Held when calling makestate() from
    // getEventData(), should also be held by the service code as
    // appropriate.
    std::mutex m_statemutex;

    UpMpd *m_dev;
    UpMpdOpenHome *m_udev;
    std::string m_tpname;
};

extern const std::string OHPlaylistSourceName;
extern const std::string OHPlaylistSourceType;
extern const std::string OHReceiverSourceName;
extern const std::string OHReceiverSourceType;
extern const std::string OHRadioSourceName;
extern const std::string OHRadioSourceType;

#endif /* _OHSERVICE_H_X_INCLUDED_ */
