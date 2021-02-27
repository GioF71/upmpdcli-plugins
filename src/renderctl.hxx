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
#ifndef _RENDERING_H_X_INCLUDED_
#define _RENDERING_H_X_INCLUDED_

#include <string>
#include <vector>
#include <unordered_map>

#include "libupnpp/device/device.hxx"
#include "libupnpp/soaphelp.hxx"

class UpMpd;
class UpMpdMediaRenderer;
class MpdStatus;

using namespace UPnPP;

class RenderingControl : public UPnPProvider::UpnpService {
public:
    RenderingControl(UpMpd *dev, UpMpdMediaRenderer*udev, bool noev);

    virtual bool getEventData(bool all, std::vector<std::string>& names, 
                              std::vector<std::string>& values);
    virtual const std::string serviceErrString(int) const;
    void onMpdEvent(const MpdStatus*);

private:
    virtual bool getEventDataNoFlush(bool all, std::vector<std::string>& names, 
                                     std::vector<std::string>& values);
    bool rdstateMToU(std::unordered_map<std::string, std::string>& status);
    int setMute(const SoapIncoming& sc, SoapOutgoing& data);
    int getMute(const SoapIncoming& sc, SoapOutgoing& data);
    int setVolume(const SoapIncoming& sc, SoapOutgoing& data, bool isDb);
    int getVolume(const SoapIncoming& sc, SoapOutgoing& data, bool isDb);
    int listPresets(const SoapIncoming& sc, SoapOutgoing& data);
    int selectPreset(const SoapIncoming& sc, SoapOutgoing& data);

    UpMpd *m_dev;
    UpMpdMediaRenderer *m_udev;
    // State variable storage
    std::unordered_map<std::string, std::string> m_rdstate;
};

#endif /* _RENDERING_H_X_INCLUDED_ */
