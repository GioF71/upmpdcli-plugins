/* Copyright (C) 2014 J.F.Dockes
 *	 This program is free software; you can redistribute it and/or modify
 *	 it under the terms of the GNU Lesser General Public License as published by
 *	 the Free Software Foundation; either version 2.1 of the License, or
 *	 (at your option) any later version.
 *
 *	 This program is distributed in the hope that it will be useful,
 *	 but WITHOUT ANY WARRANTY; without even the implied warranty of
 *	 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *	 GNU Lesser General Public License for more details.
 *
 *	 You should have received a copy of the GNU Lesser General Public License
 *	 along with this program; if not, write to the
 *	 Free Software Foundation, Inc.,
 *	 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#ifndef _OHINFO_H_X_INCLUDED_
#define _OHINFO_H_X_INCLUDED_

#include <string>                       // for string
#include <unordered_map>                // for unordered_map
#include <vector>                       // for vector

#include "libupnpp/device/device.hxx"   // for UpnpService
#include "libupnpp/soaphelp.hxx"        // for SoapIncoming, SoapOutgoing

#include "ohservice.hxx"

using namespace UPnPP;

class OHPlaylist;

class OHInfo : public OHService {
public:
    // updstatus is set if we are the first service (avt not
    // running). We actually fetch the MPD status instead of using the
    // cached data.
    OHInfo(UpMpd *dev, bool updstatus);

    void setMetatext(const std::string& metatext);

    void setOHPL(OHPlaylist *ohp) {
        m_ohpl = ohp;
    }

protected:
    virtual bool makestate(std::unordered_map<std::string, std::string>& state);

private:
    int counters(const SoapIncoming& sc, SoapOutgoing& data);
    int track(const SoapIncoming& sc, SoapOutgoing& data);
    int details(const SoapIncoming& sc, SoapOutgoing& data);
    int metatext(const SoapIncoming& sc, SoapOutgoing& data);

    void urimetadata(std::string& uri, std::string& metadata);
    void makedetails(std::string &duration, std::string& bitrate,
                     std::string& bitdepth, std::string& samplerate);

    std::string m_metatext;
    int m_metatextcnt{0};
    bool m_updstatus{false};
    OHPlaylist *m_ohpl{0};
};

#endif /* _OHINFO_H_X_INCLUDED_ */
