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

#include "config.h"

#include "ohvolume.hxx"

#include <functional>
#include <iostream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"

#include "upmpd.hxx"
#include "upmpdutils.hxx"
#include "renderctl.hxx"

using namespace std;
using namespace std::placeholders;

static const string millidbperstep("500");

static const string sTpProduct("urn:av-openhome-org:service:Volume:1");
static const string sIdProduct("urn:av-openhome-org:serviceId:Volume");

OHVolume::OHVolume(UpMpd *dev)
    : OHService(sTpProduct, sIdProduct, "OHVolume.xml", dev)
{
    dev->addActionMapping(this,"Characteristics", 
                          bind(&OHVolume::characteristics, this, _1, _2));
    dev->addActionMapping(this,"SetVolume", 
                          bind(&OHVolume::setVolume, this, _1, _2));
    dev->addActionMapping(this,"Volume", 
                          bind(&OHVolume::volume, this, _1, _2));
    dev->addActionMapping(this,"VolumeInc", 
                          bind(&OHVolume::volumeInc, this, _1, _2));
    dev->addActionMapping(this,"VolumeDec", 
                          bind(&OHVolume::volumeDec, this, _1, _2));
    dev->addActionMapping(this,"VolumeLimit", 
                          bind(&OHVolume::volumeLimit, this, _1, _2));
    dev->addActionMapping(this,"Mute", 
                          bind(&OHVolume::mute, this, _1, _2));
    dev->addActionMapping(this,"SetMute", 
                          bind(&OHVolume::setMute, this, _1, _2));
    dev->addActionMapping(this,"SetBalance", 
                          bind(&OHVolume::setBalance, this, _1, _2));
    dev->addActionMapping(this,"Balance", 
                          bind(&OHVolume::balance, this, _1, _2));
    dev->addActionMapping(this,"BalanceInc", 
                          bind(&OHVolume::balanceInc, this, _1, _2));
    dev->addActionMapping(this,"BalanceDec", 
                          bind(&OHVolume::balanceDec, this, _1, _2));
    dev->addActionMapping(this,"SetFade", 
                          bind(&OHVolume::setFade, this, _1, _2));
    dev->addActionMapping(this,"Fade", 
                          bind(&OHVolume::fade, this, _1, _2));
    dev->addActionMapping(this,"FadeInc", 
                          bind(&OHVolume::fadeInc, this, _1, _2));
    dev->addActionMapping(this,"FadeDec", 
                          bind(&OHVolume::fadeDec, this, _1, _2));

}

bool OHVolume::makestate(unordered_map<string, string> &st)
{
    st.clear();

    st["VolumeMax"] = "100";
    st["VolumeLimit"] = "100";
    st["VolumeUnity"] = "100";
    st["VolumeSteps"] = "100";
    st["VolumeMilliDbPerStep"] = millidbperstep;
    st["Balance"] = "0";
    st["BalanceMax"] = "0";
    st["Fade"] = "0";
    st["FadeMax"] = "0";
    int volume = m_dev->getvolume();
    st["Volume"] = SoapHelp::i2s(volume);
    st["Mute"] = volume == 0 ? "1" : "0";
    return true;
}

int OHVolume::characteristics(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::charact." << endl);
    data.addarg("VolumeMax", "100");
    data.addarg("VolumeUnity", "100");
    data.addarg("VolumeSteps", "100");
    data.addarg("VolumeMilliDbPerStep", millidbperstep);
    data.addarg("BalanceMax", "0");
    data.addarg("FadeMax", "0");
    return UPNP_E_SUCCESS;
}

int OHVolume::setVolume(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::setVolume" << endl);
    int volume;
    if (!sc.get("Value", &volume)) {
        return UPNP_E_INVALID_PARAM;
    }
    m_dev->setvolume(volume);
    m_dev->loopWakeup();
    return UPNP_E_SUCCESS;
}

int OHVolume::setMute(const SoapIncoming& sc, SoapOutgoing& data)
{
    bool mute;
    if (!sc.get("Value", &mute)) {
        LOGERR("OHVolume::setMute: no mute value\n");
        return UPNP_E_INVALID_PARAM;
    }
    LOGDEB("OHVolume::setMute: " << mute << endl);
    m_dev->setmute(mute);
    return UPNP_E_SUCCESS;
}

int OHVolume::volumeInc(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::volumeInc" << endl);
    int newvol = m_dev->getvolume() + 1;
    if (newvol > 100)
        newvol = 100;
    m_dev->setvolume(newvol);
    m_dev->loopWakeup();
    return UPNP_E_SUCCESS;
}

int OHVolume::volumeDec(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::volumeDec" << endl);
    int newvol = m_dev->getvolume() - 1;
    if (newvol < 0)
        newvol = 0;
    m_dev->setvolume(newvol);
    m_dev->loopWakeup();
    return UPNP_E_SUCCESS;
}

int OHVolume::volume(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::volume" << endl);
    data.addarg("Value", SoapHelp::i2s(m_dev->getvolume()));
    return UPNP_E_SUCCESS;
}

int OHVolume::mute(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::mute" << endl);
    bool mute = m_dev->getvolume() == 0;
    data.addarg("Value", mute ? "1" : "0");
    return UPNP_E_SUCCESS;
}

int OHVolume::volumeLimit(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::volumeLimit" << endl);
    data.addarg("Value", "100");
    return UPNP_E_SUCCESS;
}

int OHVolume::balance(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::balance" << endl);
    data.addarg("Value", SoapHelp::i2s(0));
    return UPNP_E_SUCCESS;
}

int OHVolume::setBalance(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::setBalance" << endl);
    int balance;
    if (!sc.get("Value", &balance) || balance != 0) {
        return UPNP_E_INVALID_PARAM;
    }
    return UPNP_E_SUCCESS;
}

int OHVolume::balanceInc(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::balanceInc" << endl);
    return UPNP_E_SUCCESS;
}

int OHVolume::balanceDec(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::balanceDec" << endl);
    return UPNP_E_SUCCESS;
}


int OHVolume::fade(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::fade" << endl);
    data.addarg("Value", SoapHelp::i2s(0));
    return UPNP_E_SUCCESS;
}

int OHVolume::setFade(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::setFade" << endl);
    int fade;
    if (!sc.get("Value", &fade) || fade != 0) {
        return UPNP_E_INVALID_PARAM;
    }
    return UPNP_E_SUCCESS;
}

int OHVolume::fadeInc(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::fadeInc" << endl);
    return UPNP_E_SUCCESS;
}

int OHVolume::fadeDec(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHVolume::fadeDec" << endl);
    return UPNP_E_SUCCESS;
}
