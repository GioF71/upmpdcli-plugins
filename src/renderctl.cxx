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

#include "config.h"

#include "renderctl.hxx"

#include <stdlib.h>

#include <functional>
#include <iostream>
#include <map>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"

#include "mpdcli.hxx"
#include "upmpd.hxx"
#include "upmpdutils.hxx"

using namespace std;
using namespace std::placeholders;
using namespace UPnPP;

static const string 
sTpRender("urn:schemas-upnp-org:service:RenderingControl:1");
static const string sIdRender("urn:upnp-org:serviceId:RenderingControl");

RenderingControl::RenderingControl(UpMpd *dev, UpMpdMediaRenderer* udev, bool noev)
    : UpnpService(sTpRender, sIdRender, "RenderingControl.xml", udev, noev),
      m_dev(dev), m_udev(udev)
{
    m_udev->addActionMapping(this, "SetMute", 
                            bind(&RenderingControl::setMute, this, _1, _2));
    m_udev->addActionMapping(this, "GetMute", 
                            bind(&RenderingControl::getMute, this, _1, _2));
    m_udev->addActionMapping(this, "SetVolume", bind(&RenderingControl::setVolume, 
                                              this, _1, _2, false));
    m_udev->addActionMapping(this, "GetVolume", bind(&RenderingControl::getVolume, 
                                              this, _1, _2, false));
    m_udev->addActionMapping(this, "ListPresets", 
                            bind(&RenderingControl::listPresets, this, _1, _2));
    m_udev->addActionMapping(this, "SelectPreset", 
                            bind(&RenderingControl::selectPreset, this, _1, _2));

    m_dev->getmpdcli()->subscribe(MPDCli::MpdMixerEvt,
                               bind(&RenderingControl::onMpdEvent, this, _1));
}

// Rendering Control errors
enum RDCErrorCode {
  UPNP_AV_RC_INVALID_PRESET_NAME                    = 701,
  UPNP_AV_RC_INVALID_INSTANCE_ID                    = 702,
};

const std::string RenderingControl::serviceErrString(int error) const
{
    switch(error) {
    case UPNP_AV_RC_INVALID_PRESET_NAME:
        return "Rendering Control Invalid Preset Name";
    case UPNP_AV_RC_INVALID_INSTANCE_ID:
        return "Rendering Control Invalid Instance ID";
    default:
        return "Rendering Control Unknown Error";
    }
}

////////////////////////////////////////////////////
/// RenderingControl methods

// State variables for the RenderingControl. All evented through LastChange
//  PresetNameList
//  Mute
//  Volume
//  VolumeDB
// LastChange contains all the variables that were changed since the last
// event. For us that's at most Mute, Volume, VolumeDB
// <Event xmlns=”urn:schemas-upnp-org:metadata-1-0/AVT_RCS">
//   <InstanceID val=”0”>
//     <Mute channel=”Master” val=”0”/>
//     <Volume channel=”Master” val=”24”/>
//     <VolumeDB channel=”Master” val=”24”/>
//   </InstanceID>
// </Event>

bool RenderingControl::rdstateMToU(unordered_map<string, string>& status)
{
    int volume = m_dev->getvolume();
    if (volume < 0)
        volume = 0;
    status["Volume"] = SoapHelp::i2s(volume);
    //status["VolumeDB"] =  SoapHelp::i2s(percentodbvalue(volume));
    status["Mute"] =  volume == 0 ? "1" : "0";
    return true;
}

bool RenderingControl::getEventData(bool all, std::vector<std::string>& names, 
                                  std::vector<std::string>& values)
{
    m_dev->flushvolume();
    return getEventDataNoFlush(all, names, values);
}

bool RenderingControl::getEventDataNoFlush(
    bool all, std::vector<std::string>& names, std::vector<std::string>& values)
{
    unordered_map<string, string> newstate;
    rdstateMToU(newstate);
    if (all)
        m_rdstate.clear();

    string 
        chgdata("<Event xmlns=\"urn:schemas-upnp-org:metadata-1-0/AVT_RCS\">\n"
                "<InstanceID val=\"0\">\n");

    bool changefound = false;
    for (unordered_map<string, string>::const_iterator it = newstate.begin();
         it != newstate.end(); it++) {

        const string& oldvalue = mapget(m_rdstate, it->first);
        if (!it->second.compare(oldvalue))
            continue;

        changefound = true;

        chgdata += "<";
        chgdata += it->first;
        if (!it->first.compare("Volume") || !it->first.compare("Mute")) {
            chgdata += " channel=\"Master\"";
        }
        chgdata += " val=\"";
        chgdata += SoapHelp::xmlQuote(it->second);
        chgdata += "\"/>\n";
    }
    chgdata += "</InstanceID>\n</Event>\n";

    if (!changefound) {
        return true;
    }

    names.push_back("LastChange");
    values.push_back(chgdata);

    m_rdstate = newstate;

    return true;
}

void RenderingControl::onMpdEvent(const MpdStatus*)
{
    LOGDEB0("RenderCtl::onMpdEvent()\n");
    std::vector<std::string> names, values;
    getEventDataNoFlush(false, names, values);
    if (!names.empty()) {
        m_udev->notifyEvent(this, names, values);
    }
}

// Actions:
// Note: we need to return all out arguments defined by the SOAP call even if
// they don't make sense (because there is no song playing). Ref upnp arch p.51:
//
//   argumentName: Required if and only if action has out
//   arguments. Value returned from action. Repeat once for each out
//   argument. If action has an argument marked as retval, this
//   argument must be the first element. (Element name not qualified
//   by a namespace; element nesting context is sufficient.) Case
//   sensitive. Single data type as defined by UPnP service
//   description. Every “out” argument in the definition of the action
//   in the service description must be included, in the same order as
//   specified in the service description (SCPD) available from the
//   device.

#if 0
int RenderingControl::getVolumeDBRange(const SoapIncoming& sc, SoapOutgoing& data)
{
    string channel;
    
    if (!sc.get("Channel", &channel) || channel.compare("Master")) {
        return UPNP_E_INVALID_PARAM;
    }
    data.addarg("MinValue", "-10240");
    data.addarg("MaxValue", "0");

    return UPNP_E_SUCCESS;
}
#endif


int RenderingControl::setMute(const SoapIncoming& sc, SoapOutgoing& data)
{
    string channel;
    if (!sc.get("Channel", &channel) || channel.compare("Master")) {
        return UPNP_E_INVALID_PARAM;
    }
    string desired;
    if (!sc.get("DesiredMute", &desired)) {
        return UPNP_E_INVALID_PARAM;
    }
    if (desired[0] == 'F' || desired[0] == '0') {
        m_dev->setmute(false);
    } else if (desired[0] == 'T' || desired[0] == '1') {
        m_dev->setmute(true);
    } else {
        return UPNP_E_INVALID_PARAM;
    }
    return UPNP_E_SUCCESS;
}

int RenderingControl::getMute(const SoapIncoming& sc, SoapOutgoing& data)
{
    string channel;
    if (!sc.get("Channel", &channel) || channel.compare("Master")) {
        return UPNP_E_INVALID_PARAM;
    }

    int volume = m_dev->getvolume();
    data.addarg("CurrentMute", volume == 0 ? "1" : "0");
    return UPNP_E_SUCCESS;
}

int RenderingControl::setVolume(const SoapIncoming& sc, SoapOutgoing& data,
                              bool isDb)
{
    string channel;
    if (!sc.get("Channel", &channel) || channel.compare("Master")) {
        return UPNP_E_INVALID_PARAM;
    }

    string desired;
    
    if (!sc.get("DesiredVolume", &desired)) {
        return UPNP_E_INVALID_PARAM;
    }
    int volume = atoi(desired.c_str());
    if (isDb) {
        volume = dbvaluetopercent(volume);
    } 
    if (volume < 0 || volume > 100) {
        return UPNP_E_INVALID_PARAM;
    }
    
    m_dev->setvolume(volume);
    return UPNP_E_SUCCESS;
}

int RenderingControl::getVolume(const SoapIncoming& sc, SoapOutgoing& data,
                              bool isDb)
{
    // LOGDEB("RenderingControl::getVolume" << endl);
    string channel;
    if (!sc.get("Channel", &channel) || channel.compare("Master")) {
        return UPNP_E_INVALID_PARAM;
    }
    
    int volume = m_dev->getvolume();
    if (isDb) {
        volume = percentodbvalue(volume);
    }
    data.addarg("CurrentVolume", SoapHelp::i2s(volume));
    return UPNP_E_SUCCESS;
}

int RenderingControl::listPresets(const SoapIncoming& sc, SoapOutgoing& data)
{
    // The 2nd arg is a comma-separated list of preset names
    data.addarg("CurrentPresetNameList", "FactoryDefaults");
    return UPNP_E_SUCCESS;
}

int RenderingControl::selectPreset(const SoapIncoming& sc, SoapOutgoing& data)
{
    string presetnm;
    
    if (!sc.get("PresetName", &presetnm)) {
        return UPNP_E_INVALID_PARAM;
    }
    if (presetnm.compare("FactoryDefaults")) {
        return UPNP_E_INVALID_PARAM;
    }

    // Well there is only the volume actually...
    int volume = 50;
    m_dev->setvolume(volume);

    return UPNP_E_SUCCESS;
}
