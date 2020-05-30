/* Copyright (C) 2014 J.F.Dockes
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
#ifndef _OHTIME_H_X_INCLUDED_
#define _OHTIME_H_X_INCLUDED_

#include <string>                       // for string
#include <unordered_map>                // for unordered_map
#include <vector>                       // for vector

#include "libupnpp/device/device.hxx"   // for UpnpService
#include "libupnpp/soaphelp.hxx"        // for SoapIncoming, SoapOutgoing

#include "ohservice.hxx"
class UpMpd;

using namespace UPnPP;

class OHTime : public OHService {
public:
    OHTime(UpMpd *dev);

protected:
    virtual bool makestate(std::unordered_map<std::string, std::string> &st);

private:
    int ohtime(const SoapIncoming& sc, SoapOutgoing& data);

    void getdata(std::string& trackcount, std::string &duration,
                 std::string& seconds);
};

#endif /* _OHTIME_H_X_INCLUDED_ */
