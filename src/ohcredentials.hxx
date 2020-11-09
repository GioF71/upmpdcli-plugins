/* Copyright (C) 2016-2020 J.F.Dockes
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
#ifndef _OHCREDENTIALS_H_INCLUDED_
#define _OHCREDENTIALS_H_INCLUDED_

#include <string>
#include <vector>

#include "libupnpp/device/device.hxx"
#include "libupnpp/soaphelp.hxx"

#include "ohservice.hxx"

using namespace UPnPP;

class OHCredentials : public OHService {
public:
    OHCredentials(UpMpd *dev, UpMpdOpenHome *udev, const std::string& cachedir);
    virtual ~OHCredentials();

protected:
    virtual bool makestate(std::unordered_map<std::string, std::string> &st);

    class Internal;
private:
    int actSet(const SoapIncoming& sc, SoapOutgoing& data);
    int actClear(const SoapIncoming& sc, SoapOutgoing& data);
    int actSetEnabled(const SoapIncoming& sc, SoapOutgoing& data);
    int actGet(const SoapIncoming& sc, SoapOutgoing& data);
    int actLogin(const SoapIncoming& sc, SoapOutgoing& data);
    int actReLogin(const SoapIncoming& sc, SoapOutgoing& data);
    int actGetIds(const SoapIncoming& sc, SoapOutgoing& data);
    int actGetPublicKey(const SoapIncoming& sc, SoapOutgoing& data);
    int actGetSequenceNumber(const SoapIncoming& sc, SoapOutgoing& data);

    Internal *m{0};
};

// Check uri for special qobuz/tidal scheme and transform it to point
// to our proxy in this case.
// @param[out] isStreaming will be true if the uri was transformed, else false.
// @return false for error, uri should not be used
extern bool OHCredsMaybeMorphSpecialUri(std::string& uri, bool& isStreaming);

#endif

