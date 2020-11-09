/* Copyright (C) 2014-2020 J.F.Dockes
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
#ifndef _CONMAN_H_X_INCLUDED_
#define _CONMAN_H_X_INCLUDED_

#include <string>
#include <vector>

#include "libupnpp/device/device.hxx"
#include "libupnpp/soaphelp.hxx"

using namespace UPnPP;

class UpMpdConMan : public UPnPProvider::UpnpService {
public:
    UpMpdConMan(UPnPProvider::UpnpDevice *dev);

    virtual bool getEventData(bool all, std::vector<std::string>& names, 
                              std::vector<std::string>& values);
private:
    int getCurrentConnectionIDs(const SoapIncoming& sc, SoapOutgoing& data);
    int getCurrentConnectionInfo(const SoapIncoming& sc, SoapOutgoing& data);
    int getProtocolInfo(const SoapIncoming& sc, SoapOutgoing& data);
};

#endif /* _CONMAN_H_X_INCLUDED_ */
