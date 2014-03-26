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
#ifndef _DEVICE_H_X_INCLUDED_
#define _DEVICE_H_X_INCLUDED_

#include <unordered_map>
#include <functional>

#include "soaphelp.hxx"

class UpnpDevice;

typedef function<int (const SoapArgs&, SoapData&)> soapfun;

/** Define a virtual interface to link libupnp operations to a device 
 * implementation 
 */
class UpnpDevice {
public:
    UpnpDevice(const std::string& deviceId, 
               const std::unordered_map<std::string, std::string>& xmlfiles);
    void addServiceType(const std::string& serviceId, 
                        const std::string& serviceType);
    void addActionMapping(const std::string& actName, soapfun fun);

    /** To be implemented by the derived class.
        Called by the library when a control point subscribes, to
        retrieve eventable data. Return name/value pairs in the data array 
    */
    virtual bool getEventData(bool all, const std::string& serviceid,
                              std::vector<std::string>& names, 
                              std::vector<std::string>& values) = 0;

    /** To be called by the device layer when data changes and an
     * event should happen. */
    void notifyEvent(const std::string& serviceId,
                     const std::vector<std::string>& names, 
                     const std::vector<std::string>& values);

    /** This loop polls getEventData and generates an UPnP event if
     * there is anything to broadcast. To be called by main() when
     * done with initialization. */
    void eventloop();

    /** Called from a callback to Wakeup the event loop early if we
     * need to broadcast something quickly. Will only do something if
     * the previous event is not too recent.
     */
    void loopWakeup(); // To trigger an early event

    bool ok() {return m_lib != 0;}

private:
    const std::string& serviceType(const std::string& serviceId);
            
    LibUPnP *m_lib;
    std::string m_deviceId;
    std::unordered_map<std::string, std::string> m_serviceTypes;
    std::unordered_map<std::string, soapfun> m_calls;

    static unordered_map<std::string, UpnpDevice *> o_devices;
    static int sCallBack(Upnp_EventType et, void* evp, void*);
    int callBack(Upnp_EventType et, void* evp);
};


#endif /* _DEVICE_H_X_INCLUDED_ */
