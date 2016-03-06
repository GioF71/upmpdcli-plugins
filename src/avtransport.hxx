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
#ifndef _AVTRANSPORT_H_X_INCLUDED_
#define _AVTRANSPORT_H_X_INCLUDED_

#include <set>                          // for set
#include <string>                       // for string
#include <unordered_map>                // for unordered_map
#include <vector>                       // for vector

#include "libupnpp/device/device.hxx"   // for UpnpService
#include "libupnpp/soaphelp.hxx"        // for SoapIncoming, SoapOutgoing

class OHPlaylist;
class UpMpd;

using namespace UPnPP;

class UpMpdAVTransport : public UPnPProvider::UpnpService {
public:
    UpMpdAVTransport(UpMpd *dev, bool noev);

    virtual bool getEventData(bool all, std::vector<std::string>& names, 
                              std::vector<std::string>& values);

    void setOHP(OHPlaylist *ohp) {
        m_ohp = ohp;
    }

private:
    int setAVTransportURI(const SoapIncoming& sc, SoapOutgoing& data, bool setnext);
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
