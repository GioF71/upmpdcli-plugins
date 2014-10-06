/* Copyright (C) 2013 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; either version 2 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#ifndef _UPNPDEV_HXX_INCLUDED_
#define _UPNPDEV_HXX_INCLUDED_

/**
 * UPnP Description phase: interpreting the device description which we
 * downloaded from the URL obtained by the discovery phase.
 */

#include <vector>
#include <unordered_map>
#include <string>
#include <sstream>

namespace UPnPClient {

/**
 * Data holder for a UPnP service, parsed from the XML description
 * downloaded after discovery yielded its URL.
 */
class UPnPServiceDesc {
public:
    // e.g. urn:schemas-upnp-org:service:ConnectionManager:1
    std::string serviceType;
    // Unique Id inside device: e.g here THE ConnectionManager
    std::string serviceId; // e.g. urn:upnp-org:serviceId:ConnectionManager
    std::string SCPDURL; // Service description URL. e.g.: cm.xml
    std::string controlURL; // e.g.: /upnp/control/cm
    std::string eventSubURL; // e.g.: /upnp/event/cm

    void clear()
    {
        serviceType.clear();
        serviceId.clear();
        SCPDURL.clear();
        controlURL.clear();
        eventSubURL.clear();
    }

    std::string dump() const
    {
        std::ostringstream os;
        os << "SERVICE {serviceType [" << serviceType <<
            "] serviceId [" << serviceId <<
            "] SCPDURL [" << SCPDURL <<
            "] controlURL [" << controlURL <<
            "] eventSubURL [" << eventSubURL <<
            "] }" << std::endl;
        return os.str();
    }

    struct Argument {
        std::string name;
        bool todevice;
        std::string relatedVariable;
        void clear() {
            name.clear();
            todevice = true;
            relatedVariable.clear();
        }
    };
    struct Action {
        std::string name;
        std::vector<Argument> argList;
        void clear() {
            name.clear();
            argList.clear();
        }
    };
    struct StateVariable {
        std::string name;
        bool sendEvents;
        std::string dataType;
        bool hasValueRange;
        int minimum;
        int maximum;
        int step;
        void clear() {
            name.clear();
            sendEvents = false;
            dataType.clear();
            hasValueRange = false;
        }
    };
    struct Parsed {
        std::unordered_map<std::string, Action> actionList;
        std::unordered_map<std::string, StateVariable> stateTable;
    };
    
    bool fetchAndParseDesc(const std::string&, Parsed& parsed) const;
};

/**
 * Data holder for a UPnP device, parsed from the XML description obtained
 * during discovery.
 * A device may include several services. To be of interest to us,
 * one of them must be a ContentDirectory.
 */
class UPnPDeviceDesc {
public:
    /** Build device from xml description downloaded from discovery
     * @param url where the description came from
     * @param description the xml device description
     */
    UPnPDeviceDesc(const std::string& url, const std::string& description);

    UPnPDeviceDesc() : ok(false) {}

    bool ok;
    // e.g. urn:schemas-upnp-org:device:MediaServer:1
    std::string deviceType;
    // e.g. MediaTomb
    std::string friendlyName;
    // Unique device number. This should match the deviceID in the
    // discovery message. e.g. uuid:a7bdcd12-e6c1-4c7e-b588-3bbc959eda8d
    std::string UDN;
    // Base for all relative URLs. e.g. http://192.168.4.4:49152/
    std::string URLBase;
    // Manufacturer: e.g. D-Link, PacketVideo ("manufacturer")
    std::string manufacturer;
    // Model name: e.g. MediaTomb, DNS-327L ("modelName")
    std::string modelName;

    // Services provided by this device.
    std::vector<UPnPServiceDesc> services;

    std::string dump() const
    {
        std::ostringstream os;
        os << "DEVICE " << " {deviceType [" << deviceType <<
            "] friendlyName [" << friendlyName <<
            "] UDN [" << UDN <<
            "] URLBase [" << URLBase << "] Services:" << std::endl;
        for (auto it = services.begin(); it != services.end(); it++) {
            os << "    " << it->dump();
        }
        os << "}" << std::endl;
        return os.str();
    }
};

typedef std::vector<UPnPServiceDesc>::iterator DevServIt;

} // namespace

#endif /* _UPNPDEV_HXX_INCLUDED_ */
