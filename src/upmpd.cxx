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

#include "upmpd.hxx"

#include "libupnpp/device/device.hxx"
#include "libupnpp/log.hxx"
#include "libupnpp/upnpplib.hxx"
#include "libupnpp/control/cdircontent.hxx"

#include "main.hxx"
#include "smallut.h"
#include "conftree.h"
#include "avtransport.hxx"
#include "conman.hxx"
#include "mpdcli.hxx"
#include "ohinfo.hxx"
#include "ohplaylist.hxx"
#include "ohradio.hxx"
#include "ohproduct.hxx"
#include "ohreceiver.hxx"
#include "ohtime.hxx"
#include "ohvolume.hxx"
#include "ohsndrcv.hxx"
#include "ohcredentials.hxx"
#include "renderctl.hxx"
#include "upmpdutils.hxx"
#include "execmd.h"
#include "protocolinfo.hxx"
#include "readfile.h"

using namespace std;
using namespace UPnPP;

static const string iconDesc(
    "<iconList>"
    "  <icon>"
    "    <mimetype>image/png</mimetype>"
    "    <width>64</width>"
    "    <height>64</height>"
    "    <depth>32</depth>"
    "    <url>@PATH@</url>"
    "  </icon>"
    "</iconList>"
    );
static const string presDesc(
    "<presentationURL>@PATH@</presentationURL>"
    );

static std::string g_full_upmpdcli_lib_mpd_version;

UpMpdMediaRenderer::UpMpdMediaRenderer(
    UpMpd *upmpd, const std::string& deviceid, const std::string& friendlyname)
    : UpMpdDevice(upmpd, deviceid, friendlyname,
                  "urn:schemas-upnp-org:device:MediaRenderer:1")
{
    bool noavt = (0 != (m_upmpd->getopts().options & UpMpd::upmpdNoAV));
    m_avt = new AVTransport(upmpd, this, noavt);
    m_services.push_back(m_avt);
    m_services.push_back(new RenderingControl(upmpd, this, noavt));
    m_services.push_back(new UpMpdConMan(this));
}

void UpMpdMediaRenderer::setOHP(OHPlaylist *ohpl) {
    if (m_avt) {
        m_avt->setOHP(ohpl);
    }
}

bool UpMpdDevice::readLibFile(const string& name, string& contents)
{
    if (!name.empty()) {
        return ::readLibFile(name, contents);
    }
    
    // Empty name: requesting device description. This requires
    // further processing
    if (!::readLibFile("description.xml", contents)) {
        return false;
    }
    contents = regsub1("@DEVICETYPE@", contents, m_devicetype);
    contents = regsub1("@UUID@", contents, getDeviceId());
    contents = regsub1("@FRIENDLYNAME@", contents, m_friendlyname);
    contents = regsub1("@UPMPDCLIVERSION@", contents, g_full_upmpdcli_lib_mpd_version);
    string reason, path;
    const UpMpd::Options& opts = m_upmpd->getopts();
    
    if (!opts.iconpath.empty()) {
        string icondata;
        if (!file_to_string(opts.iconpath, icondata, &reason)) {
            if (opts.iconpath.compare("/usr/share/upmpdcli/icon.png")) {
                LOGERR("Failed reading " << opts.iconpath << " : " <<
                       reason << endl);
            } else {
                LOGDEB("Failed reading "<< opts.iconpath << " : " <<
                       reason << endl);
            }
        }
        if (!icondata.empty()) {
            addVFile("icon.png", icondata, "image/png", path);
            contents += regsub1("@PATH@", iconDesc, path);
        }
    }

    if (!opts.presentationhtml.empty()) {
        string presdata;
        if (!file_to_string(opts.presentationhtml, presdata, &reason)) {
            LOGERR("Failed reading " << opts.presentationhtml << " : " <<
                   reason << endl);
        }
        if (!presdata.empty()) {
            addVFile("presentation.html", presdata, "text/html", path);
            contents += regsub1("@PATH@", presDesc, path);
        }
    }        
    return true;
}

void UpMpd::startloops()
{
    if (m_av) {
        m_av->startloop();
    }
    if (m_oh) {
        m_oh->startloop();
    }
}

void UpMpd::startnoloops()
{
    if (m_av) {
        m_av->start();
    }
    if (m_oh) {
        m_oh->start();
    }
}


UpMpdOpenHome::UpMpdOpenHome(
    UpMpd *upmpd, const std::string& deviceid, const std::string& friendlyname,
    ohProductDesc_t& ohProductDesc)
    : UpMpdDevice(upmpd, deviceid, friendlyname,
                  "urn:av-openhome-org:device:Source:1")
{
    bool noavt = (0 != (m_upmpd->getopts().options & UpMpd::upmpdNoAV));

    m_services.push_back(new OHTime(m_upmpd, this));
    m_services.push_back(new OHVolume(m_upmpd, this));
    
    if (!g_lumincompat) {
        m_services.push_back(new OHCredentials(m_upmpd, this,
                                               m_upmpd->getopts().cachedir));
    }

    m_ohpl = new OHPlaylist(m_upmpd, this, m_upmpd->getopts().ohmetasleep);
    m_services.push_back(m_ohpl);
    m_upmpd->setohpl(m_ohpl);

    m_ohrd = new OHRadio(m_upmpd, this);
    if (m_ohrd && !m_ohrd->ok()) {
        delete m_ohrd;
        m_ohrd = 0;
    }
    if (m_ohrd)
        m_services.push_back(m_ohrd);

    m_ohif = new OHInfo(m_upmpd, this, noavt);
    m_ohif->setOHPL(m_ohpl);
    m_services.push_back(m_ohif);

    if (m_upmpd->getopts().options & UpMpd::upmpdOhReceiver) {
        struct OHReceiverParams parms;
        if (m_upmpd->getopts().schttpport)
            parms.httpport = m_upmpd->getopts().schttpport;
        if (!m_upmpd->getopts().scplaymethod.empty()) {
            if (!m_upmpd->getopts().scplaymethod.compare("alsa")) {
                parms.pm = OHReceiverParams::OHRP_ALSA;
            } else if (!m_upmpd->getopts().scplaymethod.compare("mpd")) {
                parms.pm = OHReceiverParams::OHRP_MPD;
            }
        }
        parms.sc2mpdpath = m_upmpd->getopts().sc2mpdpath;
        parms.screceiverstatefile = m_upmpd->getopts().screceiverstatefile;
        m_ohrcv = new OHReceiver(m_upmpd, this, parms);
        m_services.push_back(m_ohrcv);
    }
    if (m_upmpd->getopts().options & UpMpd::upmpdOhSenderReceiver) {
        // Note: this is not an UPnP service
        m_sndrcv = new SenderReceiver(m_upmpd,this,m_upmpd->getopts().senderpath,
                                      m_upmpd->getopts().sendermpdport);
    }
    // Create ohpr last, so that it can ask questions to other services
    //
    // We set the service version to 1 if credentials are
    // hidden. The 2 are actually unrelated, but both are needed
    // for Lumin 1.10 to discover upmpdcli (without the credentials
    // service of course). I could not find what Lumin does not
    // like when either Product:2 or ohcreds is enabled. Maybe
    // this will go away at some point.
    m_ohpr = new OHProduct(m_upmpd, this, ohProductDesc, g_lumincompat ? 1 : 2);
    m_services.push_back(m_ohpr);
}

UpMpd::UpMpd(const string& hwaddr, const string& friendlyname,
             ohProductDesc_t& ohProductDesc, MPDCli *mpdcli, Options opts)
    : m_mpdcli(mpdcli),
      m_allopts(opts),
      m_mcachefn(opts.cachefn)
{

    string mpdversion = "0.0.0";
    if (nullptr != mpdcli) {
        MpdStatus st = mpdcli->getStatus();
        mpdversion = lltodecstr(st.versmajor) + "." + lltodecstr(st.versminor) +
            "." + lltodecstr(st.verspatch);
    }
    g_full_upmpdcli_lib_mpd_version = string("upmpdcli version ") + g_upmpdcli_package_version +
        " " + LibUPnP::versionString() + " " + "mpd " + mpdversion;
    
    if (0 == (opts.options & upmpdNoAV)) {
        std::string avfname{friendlyname + "-UPnP/AV"};
        if (getOptionValue("avfriendlyname", avfname, avfname)) {
            avfname = fnameSetup(avfname);
        }
        // UUID: add bogus string to avfname in case user set it same as fname
        std::string deviceid =  std::string("uuid:") +
            LibUPnP::makeDevUUID(avfname + "xy3vhst39", hwaddr);
        m_av = new UpMpdMediaRenderer(this, deviceid, avfname);
#if LIBUPNPP_AT_LEAST(0,21,0)
        m_av->setProductVersion("Upmpdcli", g_upmpdcli_package_version.c_str());
#endif
    }
    if (opts.options & upmpdDoOH) {
        std::string deviceid =  std::string("uuid:") +
            LibUPnP::makeDevUUID(friendlyname, hwaddr);
        m_oh = new UpMpdOpenHome(this, deviceid, friendlyname, ohProductDesc);
#if LIBUPNPP_AT_LEAST(0,21,0)
        m_oh->setProductVersion("Upmpdcli", g_upmpdcli_package_version.c_str());
#endif
    }
}

UpMpd::~UpMpd()
{
//    delete m_sndrcv;
//    for (auto servicep& : m_services) {
//        delete servicep;
//    }
}

MpdStatus UpMpd::getMpdStatus()
{
    return m_mpdcli->getStatus();
}

int UpMpd::getvolume()
{
    return m_mpdcli->getVolume();
}

bool UpMpd::setvolume(int volume)
{
    return m_mpdcli->setVolume(volume);
}

bool UpMpd::flushvolume()
{
    return true;
}

bool UpMpd::setmute(bool onoff)
{
    // See mpdcli.cxx for the special processing when the 2nd arg is true
    return onoff ? m_mpdcli->setVolume(0, true) :
        m_mpdcli->setVolume(1, true);
}

bool UpMpd::checkContentFormat(const string& uri, const string& didl,
                               UpSong *ups, bool p_nocheck)
{
    bool nocheck = (m_allopts.options & upmpdNoContentFormatCheck) || p_nocheck;
    UPnPClient::UPnPDirContent dirc;
    if (!dirc.parse(didl) || dirc.m_items.size() == 0) {
        if (!didl.empty()) {
            LOGERR("checkContentFormat: didl parse failed\n");
        }
        if (nocheck) {
            noMetaUpSong(ups);
            return true;
        } else {
            return false;
        }
    }
    UPnPClient::UPnPDirObject& dobj = *dirc.m_items.begin();

    if (nocheck) {
        LOGINFO("checkContentFormat: format check disabled\n");
        return dirObjToUpSong(dobj, ups);
    }
    
    const std::unordered_set<std::string>& supportedformats =
        Protocolinfo::the()->getsupportedformats();
    auto decoded_uri = pc_decode(uri);
    for (const auto& resource : dobj.m_resources) {
        if (pc_decode(resource.m_uri) == decoded_uri) {
            ProtocolinfoEntry e;
            if (!resource.protoInfo(e)) {
                LOGERR("checkContentFormat: resource has no protocolinfo\n");
                return false;
            }
            string cf = e.contentFormat;
            if (supportedformats.find(cf) == supportedformats.end()) { // 
                LOGERR("checkContentFormat: unsupported:: " << cf << endl);
                return false;
            } else {
                LOGDEB("checkContentFormat: supported: " << cf << endl);
                if (ups) {
                    return dirObjToUpSong(dobj, ups);
                } else {
                    return true;
                }
            }
        }
    }
    LOGERR("checkContentFormat: uri not found in metadata resource list\n");
    return false;
}
