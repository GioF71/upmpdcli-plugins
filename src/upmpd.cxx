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

#include "upmpd.hxx"

#include "libupnpp/device/device.hxx"   // for UpnpDevice, UpnpService
#include "libupnpp/log.hxx"             // for LOGFAT, LOGERR, Logger, etc
#include "libupnpp/upnpplib.hxx"        // for LibUPnP
#include "libupnpp/control/cdircontent.hxx"

#include "main.hxx"
#include "smallut.h"
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
#include "renderctl.hxx"
#include "upmpdutils.hxx"
#include "execmd.h"
#include "ohsndrcv.hxx"
#include "protocolinfo.hxx"
#include "ohcredentials.hxx"
#include "readfile.h"

using namespace std;
using namespace std::placeholders;
using namespace UPnPP;

static const int minVolumeDelta = 5;

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

bool UpMpd::readLibFile(const string& name, string& contents)
{
    if (!name.empty()) {
        return ::readLibFile(name, contents);
    }
    
    // Empty name: requesting device description
    if (!::readLibFile("description.xml", contents)) {
        return false;
    }
    contents = regsub1("@UUID@", contents, getDeviceId());
    contents = regsub1("@FRIENDLYNAME@", contents, m_friendlyname);
    string versionstring = string("upmpdcli version ") +
        g_upmpdcli_package_version + " " + LibUPnP::versionString();
    contents = regsub1("@UPMPDCLIVERSION@", contents, versionstring);
    string reason, path;
    if (!m_allopts.iconpath.empty()) {
        string icondata;
        if (!file_to_string(m_allopts.iconpath, icondata, &reason)) {
            if (m_allopts.iconpath.compare("/usr/share/upmpdcli/icon.png")) {
                LOGERR("Failed reading " << m_allopts.iconpath << " : " <<
                       reason << endl);
            } else {
                LOGDEB("Failed reading "<< m_allopts.iconpath << " : " <<
                       reason << endl);
            }
        }
        if (!icondata.empty()) {
            addVFile("icon.png", icondata, "image/png", path);
            contents += regsub1("@PATH@", iconDesc, path);
        }
    }

    if (!m_allopts.presentationhtml.empty()) {
        string presdata;
        if (!file_to_string(m_allopts.presentationhtml, presdata, &reason)) {
            LOGERR("Failed reading " << m_allopts.presentationhtml << " : " <<
                   reason << endl);
        }
        if (!presdata.empty()) {
            addVFile("presentation.html", presdata, "text/html", path);
            contents += regsub1("@PATH@", presDesc, path);
        }
    }        
    return true;
}


// Note: if we ever need this to work without cxx11, there is this:
// http://www.tutok.sk/fastgl/callback.html
UpMpd::UpMpd(const string& deviceid, const string& friendlyname,
             ohProductDesc_t& ohProductDesc,
             MPDCli *mpdcli, Options opts)
    : UpnpDevice(deviceid), m_mpdcli(mpdcli),
      m_options(opts.options),
      m_allopts(opts),
      m_mcachefn(opts.cachefn),
      m_friendlyname(friendlyname)
{
    bool noavt = (m_options & upmpdNoAV) != 0; 
    // Note: the order is significant here as it will be used when
    // calling the getStatus() methods, and we want AVTransport to
    // update the mpd status for everybody
    if (!noavt) {
        m_avt = new UpMpdAVTransport(this, noavt);
        m_services.push_back(m_avt);
        m_services.push_back(new UpMpdRenderCtl(this, noavt));
        m_services.push_back(new UpMpdConMan(this));
    }

    if (m_options & upmpdDoOH) {
        m_ohif = new OHInfo(this, noavt);
        m_services.push_back(m_ohif);
        m_services.push_back(new OHTime(this));
        m_services.push_back(new OHVolume(this));
        if (!g_lumincompat) {
            m_services.push_back(new OHCredentials(this, opts.cachedir));
        }
        m_ohpl = new OHPlaylist(this, opts.ohmetasleep);
        m_services.push_back(m_ohpl);
        if (m_avt)
            m_avt->setOHP(m_ohpl);
        if (m_ohif)
            m_ohif->setOHPL(m_ohpl);
        m_ohrd = new OHRadio(this);
        if (m_ohrd && !m_ohrd->ok()) {
            delete m_ohrd;
            m_ohrd = 0;
        }
        if (m_ohrd)
            m_services.push_back(m_ohrd);
        if (m_options & upmpdOhReceiver) {
            struct OHReceiverParams parms;
            if (opts.schttpport)
                parms.httpport = opts.schttpport;
            if (!opts.scplaymethod.empty()) {
                if (!opts.scplaymethod.compare("alsa")) {
                    parms.pm = OHReceiverParams::OHRP_ALSA;
                } else if (!opts.scplaymethod.compare("mpd")) {
                    parms.pm = OHReceiverParams::OHRP_MPD;
                }
            }
            parms.sc2mpdpath = opts.sc2mpdpath;
            parms.screceiverstatefile = opts.screceiverstatefile;
            m_ohrcv = new OHReceiver(this, parms);
            m_services.push_back(m_ohrcv);
        }
        if (m_options& upmpdOhSenderReceiver) {
            // Note: this is not an UPnP service
            m_sndrcv = new SenderReceiver(this, opts.senderpath,
                                          opts.sendermpdport);
        }
        // Create ohpr last, so that it can ask questions to other services
        //
        // We set the service version to 1 if credentials are
        // hidden. The 2 are actually unrelated, but both are needed
        // for Lumin 1.10 to discover upmpdcli (without the credentials
        // service of course). I could not find what Lumin does not
        // like when either Product:2 or ohcreds is enabled. Maybe
        // this will go away at some point.
        m_ohpr = new OHProduct(this, ohProductDesc, g_lumincompat ? 1 : 2);
        m_services.push_back(m_ohpr);
    }
}

UpMpd::~UpMpd()
{
    delete m_sndrcv;
    for (vector<UpnpService*>::iterator it = m_services.begin();
         it != m_services.end(); it++) {
        delete(*it);
    }
}

const MpdStatus& UpMpd::getMpdStatus()
{
    m_mpds = &m_mpdcli->getStatus();
    return *m_mpds;
}

int UpMpd::getvolume()
{
    return m_desiredvolume >= 0 ? m_desiredvolume : 
        m_mpdcli->getVolume();
}

bool UpMpd::setvolume(int volume)
{
    int previous_volume = m_mpdcli->getVolume();
    int delta = previous_volume - volume;
    if (delta < 0)
        delta = -delta;
    LOGDEB("UpMpd::setVolume: volume " << volume << " delta " << 
           delta << endl);
    bool ret{false};
    if (delta >= minVolumeDelta) {
        ret = m_mpdcli->setVolume(volume);
        m_desiredvolume = -1;
    } else {
        m_desiredvolume = volume;
    }
    return ret;
}

bool UpMpd::flushvolume()
{
    bool ret{false};
    if (m_desiredvolume >= 0) {
        ret = m_mpdcli->setVolume(m_desiredvolume);
        m_desiredvolume = -1;
    }
    return ret;
}

bool UpMpd::setmute(bool onoff)
{
    bool ret{false};
    if (onoff) {
        if (m_desiredvolume >= 0) {
            m_mpdcli->setVolume(m_desiredvolume);
            m_desiredvolume = -1;
        }
        ret = m_mpdcli->setVolume(0, true);
    } else {
        // Restore pre-mute
        ret = m_mpdcli->setVolume(1, true);
    }
    return ret;
}

bool UpMpd::checkContentFormat(const string& uri, const string& didl,
                               UpSong *ups, bool p_nocheck)
{
    bool nocheck = (m_options & upmpdNoContentFormatCheck) || p_nocheck;
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

    for (vector<UPnPClient::UPnPResource>::const_iterator it =
             dobj.m_resources.begin(); it != dobj.m_resources.end(); it++) {
        if (!it->m_uri.compare(uri)) {
            ProtocolinfoEntry e;
            if (!it->protoInfo(e)) {
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
