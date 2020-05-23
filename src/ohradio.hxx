/* Copyright (C) 2014 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU Lesser General Public License as published by
 *   the Free Software Foundation; either version 2.1 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU Lesser General Public License for more details.
 *
 *   You should have received a copy of the GNU Lesser General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#ifndef _OHRADIO_H_X_INCLUDED_
#define _OHRADIO_H_X_INCLUDED_

#include <string>
#include <unordered_map>
#include <vector>

#include "libupnpp/device/device.hxx"
#include "libupnpp/soaphelp.hxx"
#include "mpdcli.hxx"
#include "ohservice.hxx"

class UpMpd;

using namespace UPnPP;

struct RadioMeta;
class MpdStatus;

class OHRadio : public OHService {
public:
    OHRadio(UpMpd *dev);

    // We can only offer this if Python is available because of the
    // stream uri fetching script. This is checked during construction.
    bool ok() {return m_ok;}
    
    int iStop();
    int iPlay();

    // Source active ?
    void setActive(bool onoff);

protected:
    bool makestate(std::unordered_map<std::string, std::string>& st);
    
private:
    int channel(const SoapIncoming& sc, SoapOutgoing& data);
    int channelsMax(const SoapIncoming& sc, SoapOutgoing& data);
    int id(const SoapIncoming& sc, SoapOutgoing& data);
    int idArray(const SoapIncoming& sc, SoapOutgoing& data);
    int idArrayChanged(const SoapIncoming& sc, SoapOutgoing& data);
    int pause(const SoapIncoming& sc, SoapOutgoing& data);
    int play(const SoapIncoming& sc, SoapOutgoing& data);
    int protocolInfo(const SoapIncoming& sc, SoapOutgoing& data);
    int ohread(const SoapIncoming& sc, SoapOutgoing& data);
    int readList(const SoapIncoming& sc, SoapOutgoing& data);
    int seekSecondAbsolute(const SoapIncoming& sc, SoapOutgoing& data);
    int seekSecondRelative(const SoapIncoming& sc, SoapOutgoing& data);
    int setChannel(const SoapIncoming& sc, SoapOutgoing& data);
    int setId(const SoapIncoming& sc, SoapOutgoing& data);
    int stop(const SoapIncoming& sc, SoapOutgoing& data);
    int transportState(const SoapIncoming& sc, SoapOutgoing& data);

    std::string metaForId(unsigned int id);
    bool readRadios();
    int setPlaying();
    bool makeIdArray(std::string&);
    void maybeWakeUp(bool ok);
    void maybeExecMetaScript(RadioMeta& radio, MpdStatus &);

    bool m_active{false};
    // Play requested, but waiting for the metascript to return an uri.
    bool m_playpending{false};
    MpdState m_mpdsavedstate;
    // Current channel id set by setId
    unsigned int m_id{0}; 
    // Current track data (title+artist_. Used for detecting changes,
    // only for executing possible configured art uri fetch script
    std::string m_currentsong;
    bool m_ok{false};
};

#endif /* _OHRADIO_H_X_INCLUDED_ */
