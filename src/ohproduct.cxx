/* Copyright (C) 2014-2020 J.F.Dockes
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
#include "config.h"

#include "ohproduct.hxx"

#include <unistd.h>

#include <functional>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>
#include <utility>

#include "libupnpp/device/device.hxx"
#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"

#include "upmpd.hxx"
#include "upmpdutils.hxx"
#include "pathut.h"
#include "ohplaylist.hxx"
#include "ohradio.hxx"
#include "ohreceiver.hxx"
#include "ohsndrcv.hxx"
#include "ohinfo.hxx"
#include "conftree.h"

using namespace std;
using namespace std::placeholders;

static void listScripts(vector<pair<string, string> >& sources);

static const string sTpProduct("urn:av-openhome-org:service:Product:");
static const string sIdProduct("urn:av-openhome-org:serviceId:Product");

static const string cstr_stsrcnmkey("ohproduct.sourceName");

static string csxml("<SourceList>");
static string csattrs("Info Time Volume");

// This can be replaced by config data in listScripts()
static string scripts_dir("/usr/share/upmpdcli/src_scripts");

// (Type, Name) list
static vector<pair<string, string> > o_sources;

static const string SndRcvPLName("PL-to-Songcast");
static const string SndRcvRDName("RD-to-Songcast");

const std::string OHPlaylistSourceName{"Playlist"};
const std::string OHPlaylistSourceType{"Playlist"};
const std::string OHReceiverSourceName{"Songcast"};
const std::string OHReceiverSourceType{"Receiver"};
const std::string OHRadioSourceName{"Radio"};
const std::string OHRadioSourceType{"Radio"};

OHProduct::OHProduct(UpMpd *dev, UpMpdOpenHome *udev, ohProductDesc_t& ohProductDesc, int version)
    : OHService(sTpProduct + SoapHelp::i2s(version), sIdProduct, "OHProduct.xml", dev, udev),
      m_ohProductDesc(ohProductDesc), m_sourceIndex(0), m_standby(false)
{
    // Playlist must stay first.
    o_sources.push_back(pair<string,string>(OHPlaylistSourceType, OHPlaylistSourceName));
    if (m_udev->getohrd()) {
        o_sources.push_back(pair<string, string>(OHRadioSourceType, OHRadioSourceName));
    }
    // version == 1 is for lumin compat, see upmpd.cxx
    if (version != 1) {
        csattrs.append(" Credentials");
    }
    if (m_udev->getohrcv()) {
        o_sources.push_back(pair<string,string>(OHReceiverSourceType, OHReceiverSourceName));
        csattrs.append(" Receiver");        
        if (m_udev->getsndrcv() &&
            m_udev->getohrcv()->playMethod() == OHReceiverParams::OHRP_ALSA) {
            if (!(m_dev->getopts().options & UpMpd::upmpdNoSongcastSource)) {
                // It might be possible to make things work with the MPD
                // play method but this would be complicated (the mpd we
                // want to get playing from sc2mpd HTTP is the
                // original/saved one, not the current one, which is doing
                // the playing and sending to the fifo, so we'd need to
                // tell ohreceiver about using the right one.
                o_sources.push_back(pair<string,string>(OHPlaylistSourceType, SndRcvPLName));
                if (m_udev->getohrd()) {
                    o_sources.push_back(pair<string,string>(OHRadioSourceType, SndRcvRDName));
                }
            }
            listScripts(o_sources);
        }
    }


    for (const auto& entry : o_sources) {
        // Receiver needs to be visible for Kazoo to use it. As a
        // consequence, Receiver appears in older upplay versions
        // source lists. Newer versions filters it out because you
        // can't do anything useful by selecting the receiver source
        // (no way to specify the sender), so it is confusing
        // Note: only the UPNP/AV source has visible==false in Linn ohplayer
        string visible = "true";
        csxml += string("<Source>") +
            "<Name>" + entry.second + "</Name>" +
            "<Type>" + entry.first + "</Type>" +
            "<Visible>" + visible + "</Visible>" +
            "<SystemName>" + entry.second + "</SystemName>" +
            "</Source>";
    }
    csxml += string("</SourceList>");
    LOGDEB0("OHProduct::OHProduct: sources: " << csxml << endl);

    g_config->get("onstandby", m_standbycmd);
    if (!m_standbycmd.empty()) {
        string out;
        if (ExecCmd::backtick(vector<string>{m_standbycmd}, out)) {
            m_standby = atoi(out.c_str());
            LOGDEB("OHProduct: standby is " << m_standby << endl);
        }
    }
    
    udev->addActionMapping(this, "Manufacturer", bind(&OHProduct::manufacturer, this, _1, _2));
    udev->addActionMapping(this, "Model", bind(&OHProduct::model, this, _1, _2));
    udev->addActionMapping(this, "Product", bind(&OHProduct::product, this, _1, _2));
    udev->addActionMapping(this, "Standby", bind(&OHProduct::standby, this, _1, _2));
    udev->addActionMapping(this, "SetStandby", bind(&OHProduct::setStandby, this, _1, _2));
    udev->addActionMapping(this, "SourceCount", bind(&OHProduct::sourceCount, this, _1, _2));
    udev->addActionMapping(this, "SourceXml", bind(&OHProduct::sourceXML, this, _1, _2));
    udev->addActionMapping(this, "SourceIndex", bind(&OHProduct::sourceIndex, this, _1, _2));
    udev->addActionMapping(this, "SetSourceIndex", bind(&OHProduct::setSourceIndex, this, _1, _2));
    udev->addActionMapping(this, "SetSourceIndexByName",
                           bind(&OHProduct::setSourceIndexByName, this, _1, _2));
    udev->addActionMapping(this, "SetSourceBySystemName", 
                          bind(&OHProduct::setSourceBySystemName,this, _1, _2));
    udev->addActionMapping(this, "Source", bind(&OHProduct::source, this, _1, _2));
    udev->addActionMapping(this, "Attributes", bind(&OHProduct::attributes, this, _1, _2));
    udev->addActionMapping(this, "SourceXmlChangeCount",
                           bind(&OHProduct::sourceXMLChangeCount, this, _1, _2));

    if (g_state) {
        string savedsrc;
        if (!g_state->get(cstr_stsrcnmkey, savedsrc)) {
            savedsrc = OHPlaylistSourceName;
        }
        if (savedsrc.compare(OHPlaylistSourceName)) {
            if (iSetSourceIndexByName(savedsrc) != UPNP_E_SUCCESS) {
                g_state->set(cstr_stsrcnmkey, OHPlaylistSourceName);
            }
        }
    }
}

bool OHProduct::makestate(unordered_map<string, string> &st)
{
    st.clear();

    st["ManufacturerName"] = m_ohProductDesc.manufacturer.name;
    st["ManufacturerInfo"] = m_ohProductDesc.manufacturer.info;
    st["ManufacturerUrl"] = m_ohProductDesc.manufacturer.url;
    st["ManufacturerImageUri"] = m_ohProductDesc.manufacturer.imageUri;
    st["ModelName"] = m_ohProductDesc.model.name;
    st["ModelInfo"] = m_ohProductDesc.model.info;
    st["ModelUrl"] = m_ohProductDesc.model.url;
    st["ModelImageUri"] = m_ohProductDesc.model.imageUri;
    st["ProductRoom"] = m_ohProductDesc.room;
    st["ProductName"] = m_ohProductDesc.product.name;
    st["ProductInfo"] = m_ohProductDesc.product.info;
    st["ProductUrl"] = m_ohProductDesc.product.url;
    st["ProductImageUri"] = m_ohProductDesc.product.imageUri;
    st["Standby"] = m_standby ? "1" : "0";
    st["SourceCount"] = SoapHelp::i2s(o_sources.size());
    st["SourceXml"] = csxml;
    st["SourceIndex"] = SoapHelp::i2s(m_sourceIndex);
    st["Attributes"] = csattrs;

    return true;
}

int OHProduct::manufacturer(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::manufacturer" << endl);
    data.addarg("Name", m_ohProductDesc.manufacturer.name);
    data.addarg("Info", m_ohProductDesc.manufacturer.info);
    data.addarg("Url", m_ohProductDesc.manufacturer.url);
    data.addarg("ImageUri", m_ohProductDesc.manufacturer.imageUri);
    return UPNP_E_SUCCESS;
}

int OHProduct::model(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::model" << endl);
    data.addarg("Name", m_ohProductDesc.model.name);
    data.addarg("Info", m_ohProductDesc.model.info);
    data.addarg("Url", m_ohProductDesc.model.url);
    data.addarg("ImageUri", m_ohProductDesc.model.imageUri);
    return UPNP_E_SUCCESS;
}

int OHProduct::product(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::product" << endl);
    data.addarg("Room", m_ohProductDesc.room);
    data.addarg("Name", m_ohProductDesc.product.name);
    data.addarg("Info", m_ohProductDesc.product.info);
    data.addarg("Url", m_ohProductDesc.product.url);
    data.addarg("ImageUri", m_ohProductDesc.product.imageUri);
    return UPNP_E_SUCCESS;
}

int OHProduct::standby(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::standby" << endl);
    data.addarg("Value", SoapHelp::i2s(m_standby));
    return UPNP_E_SUCCESS;
}

int OHProduct::setStandby(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::setStandby" << endl);
    if (!sc.get("Value", &m_standby)) {
        return UPNP_E_INVALID_PARAM;
    }
    if (!m_standbycmd.empty()) {
        string out;
        if (ExecCmd::backtick(vector<string>{m_standbycmd,
                        SoapHelp::i2s(m_standby)}, out)) {
            m_standby = atoi(out.c_str());
            LOGDEB("OHProduct: standby is " << m_standby << endl);
        }
    }
    onEvent(nullptr);
    return UPNP_E_SUCCESS;
}

int OHProduct::sourceCount(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::sourceCount" << endl);
    data.addarg("Value", SoapHelp::i2s(o_sources.size()));
    return UPNP_E_SUCCESS;
}

int OHProduct::sourceXML(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::sourceXML" << endl);
    data.addarg("Value", csxml);
    return UPNP_E_SUCCESS;
}

int OHProduct::sourceIndex(const SoapIncoming& sc, SoapOutgoing& data)
{
    data.addarg("Value", SoapHelp::i2s(m_sourceIndex));
    LOGDEB("OHProduct::sourceIndex: " << m_sourceIndex << endl);
    return UPNP_E_SUCCESS;
}

int OHProduct::iSrcNameToIndex(const string& nm)
{
    for (unsigned int i = 0; i < o_sources.size(); i++) {
        if (!nm.compare(o_sources[i].second)) {
            return int(i);
        }
    }
    return -1;
}

int OHProduct::iSetSourceIndex(int sindex)
{
    LOGDEB("OHProduct::iSetSourceIndex: current " << m_sourceIndex <<
           " new " << sindex << endl);
    if (sindex < 0 || sindex >= int(o_sources.size())) {
        LOGERR("OHProduct::setSourceIndex: bad index: " << sindex << endl);
        return UPNP_E_INVALID_PARAM;
    }

    if (m_sourceIndex == sindex) {
        return UPNP_E_SUCCESS;
    }

    m_udev->getohif()->resetMetadata();

    bool ok = true;
    string curtp = o_sources[m_sourceIndex].first;
    string curnm = o_sources[m_sourceIndex].second;
    if (m_udev->getohpl() && !curtp.compare(OHPlaylistSourceType) &&
        !curnm.compare(OHPlaylistSourceName)) {
        m_udev->getohpl()->setActive(false);
    } else if (m_udev->getohrcv() && !curtp.compare(OHReceiverSourceType) &&
               !curnm.compare(OHReceiverSourceName)) {
        m_udev->getohrcv()->setActive(false);
    } else if (m_udev->getohrd() && !curtp.compare(OHRadioSourceType) &&
               !curnm.compare(OHRadioSourceName)) {
        m_dev->setRadio(false);
        m_udev->getohrd()->setActive(false);
    } else if (m_udev->getsndrcv() && m_udev->getohpl() &&
               !curtp.compare(OHPlaylistSourceType) && !curnm.compare(SndRcvPLName)) {
        m_udev->getohpl()->setActive(false);
        ok = m_udev->getsndrcv()->stop();
    } else if (m_udev->getsndrcv() && m_udev->getohrd() &&
               !curtp.compare(OHRadioSourceType) && !curnm.compare(SndRcvRDName)) {
        m_dev->setRadio(false);
        m_udev->getohrd()->setActive(false);
        ok = m_udev->getsndrcv()->stop();
    } else {
        // External inputs managed by scripts Analog/Digital/Hdmi etc.
        ok = m_udev->getsndrcv()->stop();
    }

    if (!ok)
        return UPNP_E_INTERNAL_ERROR;

    string newtp = o_sources[sindex].first;
    string newnm = o_sources[sindex].second;
    if (m_udev->getohpl() && !newnm.compare(OHPlaylistSourceName)) {
        m_udev->getohpl()->setActive(true);
    } else if (m_udev->getohrcv() && !newnm.compare(OHReceiverSourceName)) {
        m_udev->getohrcv()->setActive(true);
    } else if (m_udev->getohrd() && !newnm.compare(OHRadioSourceName)) {
        m_dev->setRadio(true);
        m_udev->getohrd()->setActive(true);
    } else if (m_udev->getohpl() && m_udev->getsndrcv() &&
               !newnm.compare(SndRcvPLName)) {
        ok = m_udev->getsndrcv()->start(string(), 0 /*savedms*/);
        m_udev->getohpl()->setActive(true);
    } else if (m_udev->getohrd() && m_udev->getsndrcv() &&
               !newnm.compare(SndRcvRDName)) {
        ok = m_udev->getsndrcv()->start(string());
        m_udev->getohrd()->setActive(true);
    } else {
        string sname = newtp + "-" + newnm;
        string spath = path_cat(scripts_dir, sname);
        ok = m_udev->getsndrcv()->start(spath);
    }
    m_sourceIndex = sindex;

    if (g_state) {
        g_state->set(cstr_stsrcnmkey, newnm);
    }
    onEvent(nullptr);

    return ok ? UPNP_E_SUCCESS : UPNP_E_INTERNAL_ERROR;
}

int OHProduct::setSourceIndex(const SoapIncoming& sc, SoapOutgoing&)
{
    LOGDEB("OHProduct::setSourceIndex" << endl);
    int sindex;
    if (!sc.get("Value", &sindex)) {
        return UPNP_E_INVALID_PARAM;
    }
    return iSetSourceIndex(sindex);
}

int OHProduct::iSetSourceIndexByName(const string& name)
{
    LOGDEB("OHProduct::iSetSourceIndexByName: " << name << endl);
    int i = iSrcNameToIndex(name);
    if (i >= 0) {
        return iSetSourceIndex(i);
    } 
    LOGERR("OHProduct::iSetSourceIndexByName: no such name: " << name << endl);
    return UPNP_E_INVALID_PARAM;
}

int OHProduct::setSourceIndexByName(const SoapIncoming& sc, SoapOutgoing& data)
{
    string name;
    if (!sc.get("Value", &name)) {
        LOGERR("OHProduct::setSourceIndexByName: no Value" << endl);
        return UPNP_E_INVALID_PARAM;
    }
    return iSetSourceIndexByName(name);
}

int OHProduct::setSourceBySystemName(const SoapIncoming& sc,
                                     SoapOutgoing& data)
{
    string name;
    if (!sc.get("Value", &name)) {
        LOGERR("OHProduct::setSourceBySystemName: no Value" << endl);
        return UPNP_E_INVALID_PARAM;
    }
    return iSetSourceIndexByName(name);
}

int OHProduct::source(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::source" << endl);
    int sindex;
    if (!sc.get("Index", &sindex)) {
        return UPNP_E_INVALID_PARAM;
    }
    LOGDEB("OHProduct::source: " << sindex << endl);
    if (sindex < 0 || sindex >= int(o_sources.size())) {
        LOGERR("OHProduct::source: bad index: " << sindex << endl);
        return UPNP_E_INVALID_PARAM;
    }
    data.addarg("SystemName", o_sources[sindex].second);
    data.addarg("Type", o_sources[sindex].first);
    data.addarg("Name", o_sources[sindex].second);
    string visible = "true";
    data.addarg("Visible", visible);
    return UPNP_E_SUCCESS;
}

int OHProduct::attributes(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::attributes. csattrs: " << csattrs << endl);
    data.addarg("Value", csattrs);
    return UPNP_E_SUCCESS;
}

int OHProduct::sourceXMLChangeCount(const SoapIncoming& sc, SoapOutgoing& data)
{
    LOGDEB("OHProduct::sourceXMLChangeCount" << endl);
    data.addarg("Value", "0");
    return UPNP_E_SUCCESS;
}

#include <sys/types.h>
#include <dirent.h>

// Script names are like Type-Name
// Type may be Analog or Digital or Hdmi and is not specially
// distinguished on value (but must be one of the three).
//
// Name is arbitrary
static void listScripts(vector<pair<string, string> >& sources)
{
    if (!g_config)
        return;

    g_config->get("ohsrc_scripts_dir", scripts_dir);

    DIR *dirp = opendir(scripts_dir.c_str());
    if (dirp == 0) {
        LOGERR("Error opening scripts dir " << scripts_dir << " errno " <<
               errno << endl);
        return;
    }

    struct dirent *ent;
    while ((ent = readdir(dirp)) != 0) {
        string tpnm(ent->d_name);
        if (tpnm.size() == 0 || tpnm[0] == '.') {
            continue;
        }
        string::size_type dash = tpnm.find_first_of("-");
        if (dash == string::npos)
            continue;


        string tp(tpnm.substr(0, dash));
        string nm(tpnm.substr(dash+1));
        if (tp.compare("Analog") && tp.compare("Digital") &&
            tp.compare("Hdmi")) {
            if (tp.compare("device") && tp.compare("prescript") &&
                tp.compare("postscript"))
                LOGERR("listScripts: bad source type: " << tp << endl);
            continue;
        }

        if (access(path_cat(scripts_dir, tpnm).c_str(), X_OK) != 0) {
            LOGERR("listScripts: script " << tpnm << " is not executable" <<
                   endl);
            continue;
        }

        sources.push_back(pair<string, string>(tp, nm));
    }
    closedir(dirp);
    return;
}
