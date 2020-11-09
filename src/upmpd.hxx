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

#ifndef _UPMPD_H_X_INCLUDED_
#define _UPMPD_H_X_INCLUDED_

#include <string>
#include <unordered_map>
#include <vector>

#include "libupnpp/device/device.hxx"

#include "main.hxx"
#include "chrono.h"

class MPDCli;
class MpdStatus;

using namespace UPnPProvider;

class UpSong;
class UpMpdAVTransport;
class OHInfo;
class OHPlaylist;
class OHProduct;
class OHReceiver;
class SenderReceiver;
class OHRadio;
class UpMpd;

class UpMpdDevice : public UpnpDevice {
public:
    UpMpdDevice(UpMpd *upmpd, const std::string& deviceid,
                const std::string &friendlyname, const std::string& devicetype)
        : UpnpDevice(deviceid), m_upmpd(upmpd), m_friendlyname(friendlyname),
          m_devicetype(devicetype) {
    }
    bool readLibFile(const std::string& name, std::string& contents) override;
    const std::string& getfriendlyname() const {return m_friendlyname;}
    
protected:
    UpMpd *m_upmpd{nullptr};
    std::string m_friendlyname;
    std::string m_devicetype;
    std::vector<UpnpService*> m_services;
};

class UpMpdMediaRenderer : public UpMpdDevice {
public:
    UpMpdMediaRenderer(UpMpd *upmpd, const std::string& deviceid,
                       const std::string &friendlyname);
    void setOHP(OHPlaylist *ohpl);
private:
    UpMpdAVTransport *m_avt{0};
};

class UpMpdOpenHome : public UpMpdDevice {
public:
    UpMpdOpenHome(UpMpd *upmpd, const std::string& deviceid,
                  const std::string &friendlyname,
                  ohProductDesc_t& ohProductDesc);

    OHInfo *getohif() {return m_ohif;}
    OHPlaylist *getohpl() {return m_ohpl;}
    OHProduct *getohpr() {return m_ohpr;}
    OHRadio *getohrd() {return m_ohrd;}
    OHReceiver *getohrcv() {return m_ohrcv;}
    SenderReceiver *getsndrcv() {return m_sndrcv;}

private:
    OHProduct *m_ohpr{0};
    OHPlaylist *m_ohpl{0};
    OHRadio *m_ohrd{0};
    OHInfo *m_ohif{0};
    OHReceiver *m_ohrcv{0};
    SenderReceiver *m_sndrcv{0};
};


// The UPnP MPD frontend device with its services
class UpMpd {
public:
    enum OptFlags {
        upmpdNone = 0,
        // If set, the MPD queue belongs to us, we shall clear
        // it as we like.
        upmpdOwnQueue = 1,
        // Export OpenHome services
        upmpdDoOH = 2,
        // Save queue metadata to disk for persistence across restarts
        // (mpd does it)
        upmpdOhMetaPersist = 4,
        // sc2mpd was found: advertise songcast receiver
        upmpdOhReceiver = 8,
        // Do not publish UPnP AV services (avtransport and renderer).
        upmpdNoAV = 16,
        // mpd2sc et al were found: advertise songcast sender/receiver mode
        upmpdOhSenderReceiver = 32,
        // Do not check content format from input metadata against protocol info
        upmpdNoContentFormatCheck = 64,
        // Do not add the "PL-to-Songcast" (playlist) and "RD-to-Songcast"
        // (radio) sources to the source XML.
        upmpdNoSongcastSource = 128,
    };
    struct Options {
        unsigned int options{upmpdNone};
        std::string  cachedir;
        std::string  cachefn;
        std::string  radioconf;
        std::string  iconpath;
        std::string  presentationhtml;
        unsigned int ohmetasleep{0};
        int schttpport{0};
        std::string scplaymethod;
        std::string sc2mpdpath;
        std::string screceiverstatefile;
        std::string senderpath;
        int sendermpdport{0};
    };
    UpMpd(const std::string& hwaddr, const std::string& friendlyname,
          ohProductDesc_t& ohProductDesc, MPDCli *mpdcli, Options opts);
    ~UpMpd();

    UpMpdOpenHome *getoh() {return m_oh;}
    UpMpdMediaRenderer *getav() {return m_av;}
    const Options& getopts() const {return m_allopts;};
    MPDCli *getmpdcli() {return m_mpdcli;}
    void setmpdcli(MPDCli* mpdcli) {m_mpdcli = mpdcli;}
    
    void setohpl(OHPlaylist *ohpl) {
        if (m_av) {
            m_av->setOHP(ohpl);
        }
    }

    void startloops();
    void startnoloops();
    
    const MpdStatus& getMpdStatus();
    const MpdStatus& getMpdStatusNoUpdate();

    const std::string& getMetaCacheFn() const {
        return m_mcachefn;
    }

    // Check that the metadata resource element matching the uri is
    // present in the input set. Convert the metadata to an mpdcli song
    // while we are at it.
    bool checkContentFormat(
        const std::string& uri, const std::string& didl,
        UpSong *ups, bool nocheck = false);

    // Help avtransport report correct metadata for radios (for which
    // the uri, normally used to detect track transitions, does not
    // change). This is called by ohproduct when setting the source.
    void setRadio(bool on) {
        m_radioplaying = on;
    }
    bool radioPlaying() const {
        return m_radioplaying;
    }

    // Common implementations used by ohvolume and renderctl
    int getvolume();
    bool setvolume(int volume);
    bool setmute(bool onoff);
    bool flushvolume();

private:
    MPDCli *m_mpdcli{0};
    const MpdStatus *m_mpds{0};
    Chrono m_mpdchron;
    Options m_allopts;
    std::string m_mcachefn;
    bool m_radioplaying{false};
    // Desired volume target. We may delay executing small volume
    // changes to avoid saturating with small requests.
    int m_desiredvolume{-1};
    UpMpdOpenHome *m_oh{nullptr};
    UpMpdMediaRenderer *m_av{nullptr};
};

#endif /* _UPMPD_H_X_INCLUDED_ */
