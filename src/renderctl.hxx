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
#ifndef _RENDERING_H_X_INCLUDED_
#define _RENDERING_H_X_INCLUDED_

#include <string>                       // for string
#include <vector>                       // for vector
#include <unordered_map>                // for unordered_map

#include "libupnpp/device/device.hxx"   // for UpnpService
#include "libupnpp/soaphelp.hxx"        // for SoapIncoming, SoapOutgoing

class UpMpd;

using namespace UPnPP;

class UpMpdRenderCtl : public UPnPProvider::UpnpService {
public:
    UpMpdRenderCtl(UpMpd *dev, bool noev);

    virtual bool getEventData(bool all, std::vector<std::string>& names, 
                              std::vector<std::string>& values);
    int getvolume_i();
    void setvolume_i(int volume);
    void setmute_i(bool onoff);
private:
    bool rdstateMToU(std::unordered_map<std::string, std::string>& status);
    int setMute(const SoapIncoming& sc, SoapOutgoing& data);
    int getMute(const SoapIncoming& sc, SoapOutgoing& data);
    int setVolume(const SoapIncoming& sc, SoapOutgoing& data, bool isDb);
    int getVolume(const SoapIncoming& sc, SoapOutgoing& data, bool isDb);
    int listPresets(const SoapIncoming& sc, SoapOutgoing& data);
    int selectPreset(const SoapIncoming& sc, SoapOutgoing& data);

    UpMpd *m_dev;
    // Desired volume target. We may delay executing small volume
    // changes to avoid saturating with small requests.
    int m_desiredvolume;
    // State variable storage
    std::unordered_map<std::string, std::string> m_rdstate;
};

#endif /* _RENDERING_H_X_INCLUDED_ */
