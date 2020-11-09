/* Copyright (C) 2015 J.F.Dockes
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

#include "ohsndrcv.hxx"

#include "libupnpp/log.hxx"
#include "libupnpp/base64.hxx"

#include "execmd.h"
#include "upmpd.hxx"
#include "mpdcli.hxx"
#include "smallut.h"
#include "upmpdutils.hxx"
#include "ohreceiver.hxx"
#include "conftree.h"

using namespace std;
using namespace std::placeholders;
using namespace UPnPP;

#ifndef deleteZ
#define deleteZ(X) {delete (X); X = 0;}
#endif

class SenderReceiver::Internal {
public:
    // isender is the process we use for internal sources:
    //   internal source -> local mpd -> fifo -> isender->Songcast
    // ssender is an arbitrary script probably reading from an audio
    // driver input and managing a sender. Our local source or mpd are
    // uninvolved
    Internal(UpMpd *dv, UpMpdOpenHome *udv,
             const string& starterpath, int port)
        : dev(dv), udev(udv), makeisendercmd(starterpath), mpdport(port) {
        // Stream volume control ? This decides if the aux mpd has
        // mixer "software" or "none"
        scalestream = g_config->getBool("scstreamscaled", true);
        graceperiodms = g_config->getInt("scscriptgracesecs", 0) * 1000;
        g_config->get("scstreamcodec", streamcodec);
    }
    ~Internal() {
        clear();
    }
    void clear() {
        if (dev && origmpd) {
            dev->setmpdcli(origmpd);
            origmpd = 0;
        }
        if (dev && udev->getohrcv()) {
            udev->getohrcv()->iStop();
        }
        deleteZ(mpd);
        deleteZ(isender);
        deleteZ(ssender);
    }
    UpMpd *dev;
    UpMpdOpenHome *udev;
    MPDCli *mpd{nullptr};
    MPDCli *origmpd{nullptr};
    ExecCmd *isender{nullptr};
    ExecCmd *ssender{nullptr};
    string iuri;
    string imeta;
    string makeisendercmd;
    string streamcodec;
    int mpdport;
    bool scalestream{true};
    int graceperiodms{0};
};


SenderReceiver::SenderReceiver(UpMpd *dev, UpMpdOpenHome *udev,
                               const string& starterpath, int port)
{
    m = new Internal(dev, udev, starterpath, port);
}

SenderReceiver::~SenderReceiver()
{
    if (m)
        delete m;
}

static bool copyMpd(MPDCli *src, MPDCli *dest, int seekms)
{
    if (!src || !dest) {
        LOGERR("copyMpd: src or dest is null\n");
        return false;
    }
    MpdState st;
    return src->saveState(st, seekms) && dest->restoreState(st);
}

// If script is empty, we are using an internal source and aux mpd +
// script. Which we reuse across start/stop/start.
// If script is non-empty, it's an external source, and we restart it
// each time.
bool SenderReceiver::start(const string& script, int seekms)
{
    LOGDEB("SenderReceiver::start. script [" << script <<
           "] seekms " << seekms << endl);
    
    if (!m->dev || !m->dev->getmpdcli() || !m->udev->getohrcv()) {
        LOGERR("SenderReceiver::start: no dev or absent service??\n");
        return false;
    }
    
    // Stop MPD Play (normally already done)
    m->dev->getmpdcli()->stop();

    // sndcmd will non empty if we actually started a script instead
    // of reusing an old one (then need to read the initial data).
    ExecCmd *sndcmd = nullptr;

    if (script.empty() && !m->isender) {
        // Internal source, first time: Start fifo MPD and Sender
        m->isender = sndcmd = new ExecCmd();
        if (m->graceperiodms) {
            sndcmd->setKillTimeout(m->graceperiodms);
        }
        vector<string> args;
        args.push_back("-p");
        args.push_back(SoapHelp::i2s(m->mpdport));
        args.push_back("-f");
        args.push_back(m->udev->getfriendlyname());
    if (!m->scalestream)
            args.push_back("-e");
        if (!m->streamcodec.empty() &&
            stringicmp(m->streamcodec, "PCM")) {
            args.push_back("-C");
            args.push_back(m->streamcodec);
        }
        m->isender->startExec(m->makeisendercmd, args, false, true);
    } else if (!script.empty()) {
        // External source. ssender should already be zero, we delete
        // it just in case
        deleteZ(m->ssender);
        m->ssender = sndcmd = new ExecCmd();
        if (m->graceperiodms) {
            sndcmd->setKillTimeout(m->graceperiodms);
        }
        vector<string> args;
        args.push_back("-f");
        args.push_back(m->udev->getfriendlyname());
        // This does nothing, just for consistence.
        if (!m->scalestream)
            args.push_back("-e");
        m->ssender->startExec(script, args, false, true);
    }

    string meta, uri;
    if (sndcmd) {
        // Just started internal or external sender script, need to read the
        // details
        string output;
        if (sndcmd->getline(output) <= 0) {
            LOGERR("SenderReceiver::start: makesender command failed\n");
            m->clear();
            return false;
        }
        LOGDEB("SenderReceiver::start got [" << output << "] from script\n");

        // Output is like [Ok mpdport URI base64-encoded-uri METADATA b64-meta]
        // mpdport is bogus, but present, for ext scripts
        vector<string> toks;
        stringToTokens(output, toks);
        if (toks.size() != 6 || toks[0].compare("Ok")) {
            LOGERR("SenderReceiver::start: bad output from script: " << output
                   << endl);
            m->clear();
            return false;
        }
        uri = base64_decode(toks[3]);
        meta = base64_decode(toks[5]);
        if (script.empty()) {
            m->iuri = uri;
            m->imeta = meta;
        }
    } else {
        // Reusing internal source
        uri = m->iuri;
        meta = m->imeta;
    }
    
    if (sndcmd && script.empty()) {
        // Just started the internal source script, connect to the new MPD
        deleteZ(m->mpd);
        m->mpd = new MPDCli("localhost", m->mpdport);
        if (!m->mpd || !m->mpd->ok()) {
            LOGERR("SenderReceiver::start: can't connect to new MPD\n");
            m->clear();
            return false;
        }
    }
    
    // Start our receiver
    if (!m->udev->getohrcv()->iSetSender(uri, meta) ||
        !m->udev->getohrcv()->iPlay()) {
        m->clear();
        return false;
    }

    if (script.empty()) {
        // Internal source: copy mpd state
        copyMpd(m->dev->getmpdcli(), m->mpd, seekms);
        if (m->scalestream) {
            m->mpd->forceInternalVControl();
        }
        m->origmpd = m->dev->getmpdcli();
        m->dev->setmpdcli(m->mpd);
        if (m->scalestream) {
            // Stream is scaled, set the main mixer to 100 to allow
            // full scale. Else we are compositing the two volumes.
            m->origmpd->setVolume(100);
         }
        m->dev->getmpdcli()->takeEvents(m->origmpd);
    } else {
        m->origmpd = 0;
    }

    return true;
}

bool SenderReceiver::stop()
{
    LOGDEB("SenderReceiver::stop()\n");
    if (!m->dev || !m->udev->getohrcv()) {
        LOGERR("SenderReceiver::stop: bad state: dev/rcv null\n");
        return false;
    }
    m->udev->getohrcv()->iStop();

    if (m->origmpd && m->mpd) {
        // Do we want to transfer the playlist back ? Probably we do.
        copyMpd(m->mpd, m->origmpd, -1);
        m->mpd->stop();
        m->dev->setmpdcli(m->origmpd);
        m->dev->getmpdcli()->takeEvents(m->mpd);
        m->origmpd = 0;
    }

    // We don't reuse external source processes
    deleteZ(m->ssender);
    // Neither internal ones any more actually (used to).
    deleteZ(m->isender);
    deleteZ(m->mpd);
    return true;
}
