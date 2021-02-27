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
#ifndef _AVTRANSPORT_H_X_INCLUDED_
#define _AVTRANSPORT_H_X_INCLUDED_

#include <set>
#include <string>
#include <unordered_map>
#include <vector>

#include "libupnpp/device/device.hxx"
#include "libupnpp/soaphelp.hxx"

class OHPlaylist;
class UpMpdMediaRenderer;
class UpMpd;
class MpdStatus;

using namespace UPnPP;

class AVTransport : public UPnPProvider::UpnpService {
public:
    AVTransport(UpMpd *dev, UpMpdMediaRenderer *udev, bool noev);

    virtual bool getEventData(bool all, std::vector<std::string>& names, 
                              std::vector<std::string>& values);

    virtual const std::string serviceErrString(int) const;
    void onMpdEvent(const MpdStatus*);

    void setOHP(OHPlaylist *ohp) {
        m_ohp = ohp;
    }

private:
    int setAVTransportURI(const SoapIncoming& sc, SoapOutgoing& data,
                          bool setnext);
    int getPositionInfo(const SoapIncoming& sc, SoapOutgoing& data);
    int getTransportInfo(const SoapIncoming& sc, SoapOutgoing& data);
    int getMediaInfo(const SoapIncoming& sc, SoapOutgoing& data);
    int getDeviceCapabilities(const SoapIncoming& sc, SoapOutgoing& data);
    int setPlayMode(const SoapIncoming& sc, SoapOutgoing& data);
    int getTransportSettings(const SoapIncoming& sc, SoapOutgoing& data);
    int getCurrentTransportActions(const SoapIncoming& sc, SoapOutgoing& data);
    int playcontrol(const SoapIncoming& sc, SoapOutgoing& data, int what);
    int seek(const SoapIncoming& sc, SoapOutgoing& data);
    int seqcontrol(const SoapIncoming& sc, SoapOutgoing& data, int what);
    // Translate MPD state to AVTransport state variables.
    bool tpstateMToU(std::unordered_map<std::string, std::string>& state);

    UpMpd *m_dev;
    UpMpdMediaRenderer *m_udev;
    OHPlaylist *m_ohp;

    // State variable storage
    std::unordered_map<std::string, std::string> m_tpstate;
    std::string m_uri;
    std::string m_curMetadata;
    std::string m_nextUri;
    std::string m_nextMetadata;
    // My track identifiers (for cleaning up)
    std::set<int> m_songids;
};

#endif /* _AVTRANSPORT_H_X_INCLUDED_ */
