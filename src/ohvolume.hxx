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
#ifndef _OHVOLUME_H_X_INCLUDED_
#define _OHVOLUME_H_X_INCLUDED_

#include <string>
#include <unordered_map>
#include <vector>

#include "libupnpp/device/device.hxx"
#include "libupnpp/soaphelp.hxx"

#include "ohservice.hxx"

class OHVolume : public OHService {
public:
    OHVolume(UpMpd *dev, UpMpdOpenHome *udev);

protected:
    int characteristics(const SoapIncoming& sc, SoapOutgoing& data);
    int setVolume(const SoapIncoming& sc, SoapOutgoing& data);
    int volume(const SoapIncoming& sc, SoapOutgoing& data);
    int volumeInc(const SoapIncoming& sc, SoapOutgoing& data);
    int volumeDec(const SoapIncoming& sc, SoapOutgoing& data);
    int volumeLimit(const SoapIncoming& sc, SoapOutgoing& data);
    int mute(const SoapIncoming& sc, SoapOutgoing& data);
    int setMute(const SoapIncoming& sc, SoapOutgoing& data);
    int balance(const SoapIncoming& sc, SoapOutgoing& data);
    int setBalance(const SoapIncoming& sc, SoapOutgoing& data);
    int balanceInc(const SoapIncoming& sc, SoapOutgoing& data);
    int balanceDec(const SoapIncoming& sc, SoapOutgoing& data);
    int fade(const SoapIncoming& sc, SoapOutgoing& data);
    int setFade(const SoapIncoming& sc, SoapOutgoing& data);
    int fadeInc(const SoapIncoming& sc, SoapOutgoing& data);
    int fadeDec(const SoapIncoming& sc, SoapOutgoing& data);

    virtual bool makestate(std::unordered_map<std::string, std::string> &st);
};

#endif /* _OHVOLUME_H_X_INCLUDED_ */
