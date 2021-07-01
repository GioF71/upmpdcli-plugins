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
#include "mpdcli.hxx"

#include <mpd/client.h>

#include <stddef.h>
#include <unistd.h>
#include <iostream>
#include <sstream>
#include <cstdio>
#include <string>
#include <memory>

#include "libupnpp/log.hxx"

#include "main.hxx"
#include "smallut.h"
#include "conftree.h"
#include "execmd.h"
#include "upmpdutils.hxx"

struct mpd_status;

using namespace std;


MPDCli::MPDCli(const string& host, int port, const string& pass)
    : m_host(host), m_port(port), m_password(pass)
{
    std::unique_lock<std::mutex> lock(m_mutex);

    regcomp(&m_tpuexpr, "^[[:alpha:]]+://.+", REG_EXTENDED|REG_NOSUB);
    g_config->get("onstart", m_onstart);
    g_config->get("onplay", m_onplay);
    g_config->get("onpause", m_onpause);
    g_config->get("onstop", m_onstop);
    string scratch;
    g_config->get("onvolumechange", scratch);
    stringToStrings(scratch,  m_onvolumechange);
    g_config->get("getexternalvolume", scratch);
    stringToStrings(scratch, m_getexternalvolume);
    m_timeoutms = g_config->getInt("mpdtimeoutms", 2000);
    m_externalvolumecontrol = g_config->getBool("externalvolumecontrol", false);

    if (!openconn()) {
        return;
    }
    m_have_addtagid = checkForCommand("addtagid");
    updStatus();
}

MPDCli::~MPDCli()
{
    std::unique_lock<std::mutex> lock(m_mutex);
    stopEventLoop();
    closeconn();
    regfree(&m_tpuexpr);
}

// This is used on the auxiliary songcast mpd in a configuration where
// volume is normally controlled by an external script, but we still
// want to scale the Songcast stream.
void MPDCli::forceInternalVControl()
{
    std::unique_lock<std::mutex> lock(m_mutex);
    m_getexternalvolume.clear();
    if (m_externalvolumecontrol)
        m_onvolumechange.clear();
    m_externalvolumecontrol = false;
}

bool MPDCli::looksLikeTransportURI(const string& path)
{
    return (regexec(&m_tpuexpr, path.c_str(), 0, 0, 0) == 0);
}

// Call with lock held
void MPDCli::closeconn()
{
    if (m_conn) {
        mpd_connection_free(m_conn);
        m_conn = nullptr;
    }
}

// Call with lock held
bool MPDCli::openconn()
{
    closeconn();
    m_conn = mpd_connection_new(m_host.c_str(), m_port, m_timeoutms);
    if (m_conn == nullptr) {
        LOGERR("mpd_connection_new failed." << endl);
        return false;
    }

    if (mpd_connection_get_error(m_conn) != MPD_ERROR_SUCCESS) {
        // Don't call showError() from here it calls us back !
        LOGERR("MPDCli::openconn: mpd_connection_new failed: "
               <<  mpd_connection_get_error_message(m_conn) << "\n");
        closeconn();
        return false;
    }

    if(!m_password.empty()) {
        if (!mpd_run_password(m_conn, m_password.c_str())) {
            LOGERR("Password wrong" << endl);
            closeconn();
            return false;
        }
    }

    const unsigned int *vers = mpd_connection_get_server_version(m_conn);
    m_stat.versmajor = vers[0];
    m_stat.versminor = vers[1];
    m_stat.verspatch = vers[2];
    LOGDEB("MPDCLi::openconn: mpd protocol version: " << m_stat.versmajor
           << "." << m_stat.versminor << "." << m_stat.verspatch << endl);

    startEventLoop();
    return true;
}

bool MPDCli::startEventLoop()
{
    LOGDEB("MPDCli::startEventLoop\n");
    std::lock_guard<std::mutex> lck(m_idlemutex);
    if (nullptr == m_idleconn) {
        if (m_idlethread.joinable()) {
            m_idlethread.join();
        }
        m_idlethread = std::thread(bind(&MPDCli::eventLoop, this));
    } else {
        LOGINF("MPDCli::startEventLoop: already started\n");
    }
    return true;
}

void MPDCli::stopEventLoop()
{
    LOGDEB("MPDCli::stopEventLoop\n");
    std::unique_lock<std::mutex> lck(m_idlemutex);
    if (m_idleconn) {
        m_idleneedstop = true;
        mpd_send_noidle(m_idleconn);
        lck.unlock();
        m_idlethread.join();
        m_idlethread = std::thread{};
        m_idleneedstop = false;
    }
}

bool MPDCli::takeEvents(MPDCli *from)
{
    if (from->m_idleconn) {
        from->stopEventLoop();
        m_subs = from->m_subs;
        return startEventLoop();
    } else {
        return true;
    }
}

void MPDCli::pollerCtl(MpdStatus::State st)
{
    if (st == MpdStatus::MPDS_PLAY) {
        LOGDEB("MPDCli::pollerCtl: mpd is playing\n");
        std::unique_lock<std::mutex> lock(m_pollmutex);
        if (!m_dopoll) {
            LOGDEB("MPDCli::eventloop: start polling thread\n");
            m_dopoll = true;
            m_pollerthread = std::thread(bind(&MPDCli::timepoller, this));
        }
    } else {
        LOGDEB("MPDCli::pollerCtl: mpd is not playing\n");
        std::unique_lock<std::mutex> lock(m_pollmutex);
        m_dopoll = false;
        m_pollcv.notify_all();
    }
    if (!m_dopoll && m_pollerthread.joinable()) {
        m_pollerthread.join();
    }
}

static int o_idle_mask =
    MPD_IDLE_QUEUE | /* the queue has been modified */
    MPD_IDLE_PLAYER | /* the player state has changed: play, stop, ... */
    MPD_IDLE_MIXER | /* the volume has been modified */
    MPD_IDLE_OPTIONS; /* options have changed: crossfade, random, repeat, ... */

bool MPDCli::eventLoop()
{
top:
    for (;;) {
        std::lock_guard<std::mutex> lck(m_idlemutex);
        m_idleconn = mpd_connection_new(m_host.c_str(), m_port, m_timeoutms);
        if (nullptr == m_idleconn) {
            LOGINF("MPDCli::eventloop: could not open connection\n");
            std::this_thread::sleep_for(std::chrono::milliseconds(2000));
            continue;
        }
        if (!m_password.empty()) {
            if (!mpd_run_password(m_idleconn, m_password.c_str())) {
                LOGERR("MPDCli::eventloop: password wrong ?\n");
                mpd_connection_free(m_idleconn);
                m_idleconn = nullptr;
                return false;
            }
        }
        break;
    }
    MpdStatus::State st;
    {
        std::unique_lock<std::mutex> lock(m_mutex);
        updStatus();
        st = m_stat.state;
    }
    pollerCtl(st);
    for (;;) {
        enum mpd_idle mask = 
            mpd_run_idle_mask(m_idleconn, (enum mpd_idle)o_idle_mask);
        if (mask == 0) {
            LOGERR("MPDCli::eventloop: mpd_run_idle_mask returned 0\n");
            // This can happen if mpd went awol, or if we're asked to
            // stop. In the first case, try to reconnect, else exit
            // the loop
            if (m_idleneedstop) {
                m_idleneedstop = false;
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(2000));
            goto top;
        }
        LOGDEB0("MPDCli::eventloop: mpd_run_idle_mask returned " << std::hex <<
                mask << std::dec << "\n");
        {
            std::unique_lock<std::mutex> lock(m_mutex);
            updStatus();
            st = m_stat.state;
        }
        pollerCtl(st);

        {
            std::lock_guard<std::mutex> lock(m_callbackmutex);
            for (auto& sub : m_subs) {
                if (sub.first & mask) {
                    sub.second(&m_stat);
                }
            }
        }
        // Rate-limiting the events we trigger improves big list
        // insertion performance a lot because it decreases the number
        // of times we have to update the list
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    }
    
    pollerCtl(MpdStatus::MPDS_STOP);

    std::lock_guard<std::mutex> lck(m_idlemutex);
    mpd_connection_free(m_idleconn);
    m_idleconn = nullptr;
    return false;
}

void MPDCli::timepoller()
{
    for (;;) {
        LOGDEB1("MPDCli::timepoller\n");
        {
            std::unique_lock<std::mutex> lock(m_mutex);
            updStatus();
        }
        {
            std::lock_guard<std::mutex> lock(m_callbackmutex);
            for (auto& sub : m_subs) {
                if (sub.first & MpdPlayerEvt) {
                    sub.second(&m_stat);
                }
            }
        }

        std::unique_lock<std::mutex> lock(m_pollmutex);
        m_pollcv.wait_for(lock, std::chrono::seconds(1));
        if (!m_dopoll) {
            LOGDEB("MPDCli::timepoller: returning\n");
            return;
        }
    }
}

void MPDCli::shouldExit()
{
    LOGDEB("MPDCli::shouldExit\n");
    stopEventLoop();
}

bool MPDCli::subscribe(int mask, evtFunc func)
{
    std::lock_guard<std::mutex> lock(m_callbackmutex);
    m_subs.push_back({mask, func});
    return true;
}

// Call with lock held
bool MPDCli::showError(const string& who)
{
    if (!ok()) {
        LOGERR("MPDCli::showError: bad state" << endl);
        return false;
    }

    int error = mpd_connection_get_error(m_conn);
    if (error == MPD_ERROR_SUCCESS) {
        //LOGDEB("MPDCli::showError: " << who << " success !" << endl);
        return false;
    }
    LOGERR(who << " failed: " <<  mpd_connection_get_error_message(m_conn) 
           << endl);
    if (error == MPD_ERROR_SERVER) {
        LOGERR(who << " server error: " << 
               mpd_connection_get_server_error(m_conn) << endl);
    }
    if (error == MPD_ERROR_CLOSED)
        if (openconn())
            return true;

    if (!mpd_connection_clear_error(m_conn))
        openconn();
    return false;
}

#define RETRY_CMD_NOLOCK(CMD, ERROR) {          \
        if (!ok()) {                            \
            return ERROR;                       \
        }                                       \
        for (int i = 0; i < 2; i++) {           \
            if ((CMD))                          \
                break;                          \
            if (i == 1 || !showError(#CMD))     \
                return ERROR;                   \
        }                                       \
    }

#define RETRY_CMD(CMD, ERROR) do {                     \
        std::unique_lock<std::mutex> lock(m_connmutex); \
        RETRY_CMD_NOLOCK(CMD, ERROR);                  \
    } while (false);

#define RETRY_CMD_WITH_SLEEP(CMD, ERROR) do {             \
        std::unique_lock<std::mutex> lock(m_connmutex);    \
        if (!ok()) {                                      \
            return ERROR;                                 \
        }                                                 \
        for (int i = 0; i < 2; i++) {                     \
            if ((CMD))                                    \
                break;                                    \
            sleep(1);                                     \
            if (i == 1 || !showError(#CMD))               \
                return ERROR;                             \
        }                                                 \
    } while (false);

// Call with lock held
bool MPDCli::updStatus()
{
    mpd_status *mpds = 0;
    {
        std::unique_lock<std::mutex> lock(m_connmutex);
        if (!ok() && !openconn()) {
            LOGERR("MPDCli::updStatus: no connection" << endl);
            return false;
        }

        mpds = mpd_run_status(m_conn);
        if (mpds == 0) {
            if (!openconn()) {
                LOGERR("MPDCli::updStatus: connection failed\n");
                return false;
            }
            mpds = mpd_run_status(m_conn);
            if (mpds == 0) {
                LOGERR("MPDCli::updStatus: can't get status" << endl);
                showError("MPDCli::updStatus");
                return false;
            }
        }
    }
    
    if (m_externalvolumecontrol && !m_getexternalvolume.empty()) {
        string result;
        if (ExecCmd::backtick(m_getexternalvolume, result)) {
            //LOGDEB("MPDCli::volume retrieved: " << result << endl);
            m_stat.volume = atoi(result.c_str());
        } else {
            LOGERR("MPDCli::updStatus: error retrieving volume: " <<
                   m_getexternalvolume[0] << " failed\n");
        }
    } else {
        m_stat.volume = mpd_status_get_volume(mpds);
    }
    if (m_stat.volume >= 0) {
        m_cachedvolume = m_stat.volume;
    } else {
        m_stat.volume = m_cachedvolume;
    }

    m_stat.rept = mpd_status_get_repeat(mpds);
    m_stat.random = mpd_status_get_random(mpds);
    m_stat.single = mpd_status_get_single(mpds);
    m_stat.consume = mpd_status_get_consume(mpds);
    m_stat.qlen = mpd_status_get_queue_length(mpds);
    m_stat.qvers = mpd_status_get_queue_version(mpds);

    switch (mpd_status_get_state(mpds)) {
    case MPD_STATE_STOP:
        // Only execute onstop command if mpd was playing or paused
        if (!m_onstop.empty() && (m_stat.state == MpdStatus::MPDS_PLAY ||
                                  m_stat.state == MpdStatus::MPDS_PAUSE)) {
            if (system(m_onstop.c_str())) {
                LOGERR("MPDCli::updStatus: " << m_onstop << " failed "<< endl);
            }
        }
        m_stat.state = MpdStatus::MPDS_STOP;
        break;
    case MPD_STATE_PLAY:
        // Only execute onplay command if mpd was stopped or paused
        if (!m_onplay.empty() && (m_stat.state == MpdStatus::MPDS_UNK ||
                                  m_stat.state == MpdStatus::MPDS_STOP ||
                                  m_stat.state == MpdStatus::MPDS_PAUSE)) {
            if (system(m_onplay.c_str())) {
                LOGERR("MPDCli::updStatus: " << m_onplay << " failed "<< endl);
            }
        }
        m_stat.state = MpdStatus::MPDS_PLAY;
        break;
    case MPD_STATE_PAUSE:
        // Only execute onpause command if mpd was playing
        if (!m_onpause.empty() && (m_stat.state == MpdStatus::MPDS_PLAY)) {
            if (system(m_onpause.c_str())) {
                LOGERR("MPDCli::updStatus: " << m_onpause << " failed "<< endl);
            }
        } 
        m_stat.state = MpdStatus::MPDS_PAUSE;
        break;
    case MPD_STATE_UNKNOWN: 
    default:
        m_stat.state = MpdStatus::MPDS_UNK;
        break;
    }

    m_stat.crossfade = mpd_status_get_crossfade(mpds);
    m_stat.mixrampdb = mpd_status_get_mixrampdb(mpds);
    m_stat.mixrampdelay = mpd_status_get_mixrampdelay(mpds);
    m_stat.songpos = mpd_status_get_song_pos(mpds);
    m_stat.songid = mpd_status_get_song_id(mpds);
    if (m_stat.songpos >= 0) {
        string prevuri = m_stat.currentsong.rsrc.uri;
        statSong_i(m_stat.currentsong);
        if (m_stat.currentsong.rsrc.uri.compare(prevuri)) {
            m_stat.trackcounter++;
            m_stat.detailscounter = 0;
        }
        statSong_i(m_stat.nextsong, m_stat.songpos + 1);
    } else {
        m_stat.currentsong.clear();
        m_stat.nextsong.clear();
    }

    m_stat.songelapsedms = mpd_status_get_elapsed_ms(mpds);
    m_stat.songlenms = mpd_status_get_total_time(mpds) * 1000;
    m_stat.kbrate = mpd_status_get_kbit_rate(mpds);
    const struct mpd_audio_format *maf =
        mpd_status_get_audio_format(mpds);
    if (maf) {
        m_stat.bitdepth = maf->bits;
        m_stat.sample_rate = maf->sample_rate;
        m_stat.channels = maf->channels;
        // For radios, we don't get the didl resource info from the
        // media server, so fill in the details from mpd data if we
        // can.
        m_stat.currentsong.rsrc.bitrate = m_stat.kbrate * 1000;
        m_stat.currentsong.rsrc.samplefreq = m_stat.sample_rate;
        m_stat.currentsong.rsrc.bitsPerSample = m_stat.bitdepth;
        m_stat.currentsong.rsrc.channels = m_stat.channels;

        LOGDEB1("MPD AUDIO FORMAT: " <<  int(maf->sample_rate) << " samps/S " <<
                m_stat.kbrate << " kbits/S " << int(maf->bits) << " bits " <<
                int(maf->channels) << " channels\n");
    } else {
        m_stat.bitdepth = m_stat.channels = m_stat.sample_rate = 0;
    }

    const char *err = mpd_status_get_error(mpds);
    if (err != 0)
        m_stat.errormessage.assign(err);

    mpd_status_free(mpds);
    return true;
}

// Call with lock held
bool MPDCli::checkForCommand(const string& cmdname)
{
    LOGDEB1("MPDCli::checkForCommand: " << cmdname << endl);
    bool found = false;
    std::unique_lock<std::mutex> lock(m_connmutex);
    RETRY_CMD_NOLOCK(mpd_send_allowed_commands(m_conn), false);
    struct mpd_pair *rep;
    do {
        rep = mpd_recv_command_pair(m_conn);
        if (rep) {
            //LOGDEB("MPDCli::checkForCommand: name " <<  rep->name << 
            //       " value " << rep->value << endl);
            found = !cmdname.compare(rep->value);
            mpd_return_pair(m_conn, rep);
            if (found)
                break;
        }
    } while (rep);

    if (!mpd_response_finish(m_conn)) {
        LOGERR("MPDCli::checkForCommand: mpd_response_finish failed" << endl);
    }

    return found;
}

MpdStatus MPDCli::getStatus()
{
    std::unique_lock<std::mutex> lock(m_mutex);
    // We used to updstatus() here, but the status should now be
    // always up to date because of the idle loop.
    // We have to return a copy, as we are going to release the lock.
    return m_stat;
}

bool MPDCli::saveState(MpdState& st, int seekms)
{
    LOGDEB("MPDCli::saveState: seekms " << seekms << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    if (!updStatus()) {
        LOGERR("MPDCli::saveState: can't retrieve current status\n");
        return false;
    }
    st.status = m_stat;
    if (seekms > 0) {
        st.status.songelapsedms = seekms;
    }
    st.queue.clear();
    if (!getQueueData_i(st.queue)) {
        LOGERR("MPDCli::saveState: can't retrieve current playlist\n");
        return false;
    }
    return true;
}

bool MPDCli::restoreState(const MpdState& st)
{
    LOGDEB("MPDCli::restoreState: seekms " << st.status.songelapsedms << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    // Reset connection in case we already are in error.
    openconn();
    if (!ok()) {
        return false;
    }
    clearQueue_i();
    for (unsigned int i = 0; i < st.queue.size(); i++) {
        if (insert_i(st.queue[i].rsrc.uri, i, st.queue[i]) < 0) {
            LOGERR("MPDCli::restoreState: insert failed\n");
            return false;
        }
    }
    repeat_i(st.status.rept);
    random_i(st.status.random);
    single_i(st.status.single);
    consume_i(st.status.consume);

    m_cachedvolume = st.status.volume;
    //no need to set volume if it is controlled external
    if (!m_externalvolumecontrol)
        mpd_run_set_volume(m_conn, st.status.volume);
    
    if (st.status.state == MpdStatus::MPDS_PAUSE ||
        st.status.state == MpdStatus::MPDS_PLAY) {
        // I think that the play is necessary and we can't just do
        // pause/seek from stop state. To be verified.
        play_i(st.status.songpos);
        if (st.status.songelapsedms > 0)
            seek_i(st.status.songelapsedms/1000);
        if (st.status.state == MpdStatus::MPDS_PAUSE)
            pause_i(true);
    }
    openconn();
    return true;
}

bool MPDCli::statSong(UpSong& upsong, int pos, bool isid)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return statSong_i(upsong, pos, isid);
}
bool MPDCli::statSong_i(UpSong& upsong, int pos, bool isid)
{
    //LOGDEB1("MPDCli::statSong. isid " << isid << " id/pos " << pos << endl);
    struct mpd_song *song;
    if (isid == false) {
        if (pos == -1) {
            RETRY_CMD(song = mpd_run_current_song(m_conn), false);
        } else {
            RETRY_CMD(
                song = mpd_run_get_queue_song_pos(m_conn, (unsigned int)pos),
                false);
        }
    } else {
        RETRY_CMD(song = mpd_run_get_queue_song_id(m_conn, (unsigned int)pos),
                  false);
    }
    if (song == 0) {
        LOGERR("mpd_run_current_song failed" << endl);
        return false;
    }
    mapSong(upsong, song);
    mpd_song_free(song);
    return true;
}    

// No need for locking here, only local accesses to the local song object
UpSong&  MPDCli::mapSong(UpSong& upsong, struct mpd_song *song)
{
    //LOGDEB1("MPDCli::mapSong" << endl);
    const char *cp;

    cp = mpd_song_get_uri(song);
    if (cp != 0)
        upsong.rsrc.uri = cp;
    else 
        upsong.rsrc.uri.clear();
    // If the URI looks like a local file
    // name, replace with a bogus http uri. This is to fool
    // Bubble UPnP into accepting to play them (it does not
    // actually need an URI as it's going to use seekid, but
    // it believes it does).
    if (!looksLikeTransportURI(upsong.rsrc.uri)) {
        //LOGDEB("MPDCli::mapSong: id " << upsong.mpdid << 
        // " replacing [" << upsong.rsrc.uri << "]" << endl);
        upsong.rsrc.uri = "http://127.0.0.1/" + upsong.rsrc.uri;
    }
    cp = mpd_song_get_tag(song, MPD_TAG_NAME, 0);
    if (cp != 0)
        upsong.name = cp;
    else
        upsong.name.clear();
    cp = mpd_song_get_tag(song, MPD_TAG_ARTIST, 0);
    if (cp != 0)
        upsong.artist = cp;
    else
        upsong.artist.clear();
    if (upsong.artist.empty())
        upsong.artist = upsong.name;
    cp = mpd_song_get_tag(song, MPD_TAG_ALBUM, 0);
    if (cp != 0)
        upsong.album = cp;
    else
        upsong.album.clear();
    cp = mpd_song_get_tag(song, MPD_TAG_TITLE, 0);
    if (cp != 0) 
        upsong.title = cp;
    else
        upsong.title.clear();
    cp = mpd_song_get_tag(song, MPD_TAG_TRACK, 0);
    if (cp != 0)
        upsong.tracknum = cp;
    else 
        upsong.tracknum.clear();
    // MPD may return something like xx/yy
    string::size_type spos = upsong.tracknum.find("/");
    if (spos != string::npos) {
        upsong.tracknum = upsong.tracknum.substr(0, spos);
    }
    cp = mpd_song_get_tag(song, MPD_TAG_GENRE, 0);
    if (cp != 0)
        upsong.genre = cp;
    else
        upsong.genre.clear();

    upsong.rsrc.duration_secs = mpd_song_get_duration(song);
    upsong.mpdid = mpd_song_get_id(song);

    LOGDEB1("MPDCli::mapSong: got mpdid " << upsong.mpdid << " " << upsong.dump() << endl);
    return upsong;
}

// All the nutty stuff about mute is due to the fact that MPD does not
// have such a function (they say that pause is good enough).
bool MPDCli::setVolume(int volume, bool isMute)
{
    LOGDEB("MPDCli::setVolume. extvc " << m_externalvolumecontrol << endl);
    std::unique_lock<std::mutex> lock(m_mutex);

    // ??MPD does not want to set the volume if not active.??
    // This does not seem to be the case with recent MPD versions
    if (!(m_stat.state == MpdStatus::MPDS_PLAY) &&
        !(m_stat.state == MpdStatus::MPDS_PAUSE)) {
        LOGDEB1("MPDCli::setVolume: not active" << endl);
    }

    LOGDEB("MPDCli::setVolume: vol " << volume << " isMute " << isMute << endl);

    if (isMute) {
        if (volume) {
            // volume 1, isMute true means that unmute is required
            // Restore premute volume if it is set, else volume will
            // be restored to 1 (ensuring that the user can increase
            // it because we are out of the mute state).
            if (m_premutevolume != 0) {
                LOGDEB("MPDCli::setVolume: restoring premute " <<
                       m_premutevolume << endl);
                volume = m_stat.volume = m_premutevolume;
            }
            m_premutevolume = 0;
        } else {
            // volume 0, isMute true: mute request
            // If we're already muted, do nothing
            if (m_premutevolume > 0) {
                return true;
            }
            if (m_cachedvolume > 0) {
                m_premutevolume = m_cachedvolume;
            } else {
                // Never mute with a saved volume of 0, we get into
                // trouble with some CPs
                m_premutevolume = 1;
            }
        }
    }
        
    if (volume < 0)
        volume = 0;
    else if (volume > 100)
        volume = 100;
    
    if (!(m_externalvolumecontrol)) {
        LOGDEB2("MPDCli::setVolume: setting mpd volume " << volume << endl);
        RETRY_CMD(mpd_run_set_volume(m_conn, volume), false);
    }
    if (!m_onvolumechange.empty()) {
        ExecCmd ecmd;
        vector<string> args = m_onvolumechange;
        stringstream ss;
        ss << volume;
        args.push_back(ss.str());
        if (ecmd.doexec1(args)) {
            // doexec returns the exit status, should be zero
            LOGDEB("MPDCli::setVolume: " << m_onvolumechange[0] <<
                   " failed " << volume << endl);
        }
    }
    m_stat.volume = volume;
    m_cachedvolume = volume;
    return true;
}

int MPDCli::getVolume()
{
    //LOGDEB1("MPDCli::getVolume" << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    return m_stat.volume >= 0 ? m_stat.volume : m_cachedvolume;
}

bool MPDCli::togglePause()
{
    LOGDEB("MPDCli::togglePause" << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    RETRY_CMD(mpd_run_toggle_pause(m_conn), false);
    return true;
}

bool MPDCli::pause(bool onoff)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return pause_i(onoff);
}
bool MPDCli::pause_i(bool onoff)
{
    LOGDEB("MPDCli::pause" << endl);
    RETRY_CMD(mpd_run_pause(m_conn, onoff), false);
    return true;
}

bool MPDCli::play(int pos)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return play_i(pos);
}
bool MPDCli::play_i(int pos)
{
    LOGDEB("MPDCli::play(pos=" << pos << ")" << endl);
    if (!ok())
        return false;
    if (!m_onstart.empty() && system(m_onstart.c_str())) {
        LOGERR("MPDCli::play: " << m_onstart << " failed "<< endl);
    }
    if (pos >= 0) {
        RETRY_CMD(mpd_run_play_pos(m_conn, (unsigned int)pos), false);
    } else {
        RETRY_CMD(mpd_run_play(m_conn), false);
    }
    return updStatus();
}

bool MPDCli::playId(int id)
{
    LOGDEB("MPDCli::playId(id=" << id << ")" << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    if (!ok())
        return false;
    if (!m_onstart.empty() && system(m_onstart.c_str())) {
        LOGERR("MPDCli::playId: " << m_onstart << " failed "<< endl);
    }
    RETRY_CMD(mpd_run_play_id(m_conn, (unsigned int)id), false);
    return updStatus();
}

bool MPDCli::stop()
{
    LOGDEB("MPDCli::stop" << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    RETRY_CMD(mpd_run_stop(m_conn), false);
    return true;
}

bool MPDCli::seek(int seconds)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return seek_i(seconds);
}
bool MPDCli::seek_i(int seconds)
{
    if (!updStatus() || m_stat.songpos < 0)
        return false;
    LOGDEB("MPDCli::seek: pos:"<<m_stat.songpos<<" seconds: "<< seconds<<endl);
    RETRY_CMD(mpd_run_seek_pos(m_conn, m_stat.songpos, (unsigned int)seconds),
              false);
    return true;
}

bool MPDCli::next()
{
    LOGDEB("MPDCli::next" << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    RETRY_CMD(mpd_run_next(m_conn), false);
    return true;
}

bool MPDCli::previous()
{
    LOGDEB("MPDCli::previous" << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    RETRY_CMD(mpd_run_previous(m_conn), false);
    return true;
}

bool MPDCli::repeat(bool on)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return repeat_i(on);
}
bool MPDCli::repeat_i(bool on)
{
    LOGDEB("MPDCli::repeat:" << on << endl);
    RETRY_CMD(mpd_run_repeat(m_conn, on), false);
    return true;
}

bool MPDCli::consume(bool on)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return consume_i(on);
}
bool MPDCli::consume_i(bool on)
{
    LOGDEB("MPDCli::consume:" << on << endl);
    RETRY_CMD(mpd_run_consume(m_conn, on), false);
    return true;
}

bool MPDCli::random(bool on)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return random_i(on);
}
bool MPDCli::random_i(bool on)
{
    LOGDEB("MPDCli::random:" << on << endl);
    RETRY_CMD(mpd_run_random(m_conn, on), false);
    return true;
}

bool MPDCli::single(bool on)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return single_i(on);
}
bool MPDCli::single_i(bool on)
{
    LOGDEB("MPDCli::single:" << on << endl);
    RETRY_CMD(mpd_run_single(m_conn, on), false);
    return true;
}

// Call with lock held
bool MPDCli::send_tag(const char *cid, int tag, const string& _data)
{
    if (!ok())
        return false;
    string data;
    neutchars(_data, data, "\r\n", ' ');
    std::unique_lock<std::mutex> lock(m_connmutex);
    if (!mpd_send_command(m_conn, "addtagid", cid, 
                          mpd_tag_name(mpd_tag_type(tag)),
                          data.c_str(), NULL)) {
        LOGERR("MPDCli::send_tag: mpd_send_command failed" << endl);
        return false;
    }

    if (!mpd_response_finish(m_conn)) {
        LOGERR("MPDCli::send_tag: mpd_response_finish failed for tag " << tag <<
               " data [" << data << "]\n");
        showError("MPDCli::send_tag");
        return false;
    }
    return true;
}

static const string upmpdcli_comment("client=upmpdcli;");

// Call with lock held
bool MPDCli::send_tag_data(int id, const UpSong& meta)
{
    LOGDEB1("MPDCli::send_tag_data" << endl);
    if (!m_have_addtagid || !ok())
        return false;

    char cid[30];
    sprintf(cid, "%d", id);

    if (!send_tag(cid, MPD_TAG_ARTIST, meta.artist))
        return false;
    if (!send_tag(cid, MPD_TAG_ALBUM, meta.album))
        return false;
    if (!send_tag(cid, MPD_TAG_TITLE, meta.title))
        return false;
    if (!send_tag(cid, MPD_TAG_TRACK, meta.tracknum))
        return false;
    if (!send_tag(cid, MPD_TAG_COMMENT, upmpdcli_comment))
        return false;
    return true;
}

int MPDCli::insert(const string& uri, int pos, const UpSong& meta)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return insert_i(uri, pos, meta);
}
int MPDCli::insert_i(const string& uri, int pos, const UpSong& meta)
{
    LOGDEB("MPDCli::insert at :" << pos << " uri " << uri << endl);
    if (pos == -1) {
        RETRY_CMD((m_lastinsertid = 
                   mpd_run_add_id(m_conn, uri.c_str())) != -1, -1);
    } else {        
        RETRY_CMD(
            (m_lastinsertid = 
             mpd_run_add_id_to(m_conn, uri.c_str(), (unsigned)pos)) != -1, -1);
    }
    
    if (m_have_addtagid)
        send_tag_data(m_lastinsertid, meta);

    m_lastinsertpos = pos;
    updStatus();
    m_lastinsertqvers = m_stat.qvers;
    return m_lastinsertid;
}

int MPDCli::insertAfterId(const string& uri, int id, const UpSong& meta)
{
    LOGDEB("MPDCli::insertAfterId: id " << id << " uri " << uri << endl);
    std::unique_lock<std::mutex> lock(m_mutex);

    // id == 0 means insert at start
    if (id == 0) {
        return insert_i(uri, 0, meta);
    }

    updStatus();

    int newpos = 0;
    if (m_lastinsertid == id && m_lastinsertpos >= 0 &&
        m_lastinsertqvers == m_stat.qvers) {
        newpos = m_lastinsertpos + 1;
    } else {
        // Translate input id to insert position
        vector<mpd_song*> songs;
        if (!getQueueSongs(songs)) {
            return false;
        }
        for (unsigned int pos = 0; pos < songs.size(); pos++) {
            unsigned int qid = mpd_song_get_id(songs[pos]);
            if (qid == (unsigned int)id || pos == songs.size() -1) {
                newpos = pos + 1;
                break;
            }
        }
        freeSongs(songs);
    }
    return insert_i(uri, newpos, meta);
}

bool MPDCli::clearQueue()
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return clearQueue_i();
}
bool MPDCli::clearQueue_i()
{
    LOGDEB("MPDCli::clearQueue " << endl);
    RETRY_CMD(mpd_run_clear(m_conn), false);
    return true;
}

bool MPDCli::deleteId(int id)
{
    LOGDEB("MPDCli::deleteId " << id << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    // It seems that mpd will sometimes get in a funny state, esp.
    // after failed statsongs. The exact mechanism is a mystery, but
    // retrying the failed deletes with a bit of wait seems to help a
    // lot, and this happens seldom enough that this is not a
    // significant performance issue
    RETRY_CMD_WITH_SLEEP(mpd_run_delete_id(m_conn, (unsigned)id), false);
    return true;
}

bool MPDCli::deletePosRange(unsigned int start, unsigned int end)
{
    LOGDEB("MPDCli::deletePosRange [" << start << ", " << end << "[" << endl);
    std::unique_lock<std::mutex> lock(m_mutex);
    RETRY_CMD(mpd_run_delete_range(m_conn, start, end), false);
    return true;
}


bool MPDCli::statId(int id)
{
    LOGDEB("MPDCli::statId " << id << endl);
    if (!ok())
        return false;

    std::unique_lock<std::mutex> clock(m_connmutex);
    mpd_song *song = mpd_run_get_queue_song_id(m_conn, (unsigned)id);
    if (song) {
        mpd_song_free(song);
        return true;
    }
    return false;
}

// Call with lock held
bool MPDCli::getQueueSongs(vector<mpd_song*>& songs)
{
    //LOGDEB1("MPDCli::getQueueSongs" << endl);
    songs.clear();

    std::unique_lock<std::mutex> lock(m_connmutex);
    RETRY_CMD_NOLOCK(mpd_send_list_queue_meta(m_conn), false);

    struct mpd_song *song;
    while ((song = mpd_recv_song(m_conn)) != NULL) {
        songs.push_back(song);
    }
    
    if (!mpd_response_finish(m_conn)) {
        showError("MPDCli::getQueueSongs: mpd_list_queue_meta:finish");
        freeSongs(songs);
        return false;
    }
    LOGDEB("MPDCli::getQueueSongs: " << songs.size() << " songs " << endl);
    return true;
}

// Call with lock held
void MPDCli::freeSongs(vector<mpd_song*>& songs)
{
    LOGDEB1("MPDCli::freeSongs" << endl);
    for (auto& songp : songs) {
        mpd_song_free(songp);
    }
}

bool MPDCli::getQueueData(std::vector<UpSong>& vdata)
{
    std::unique_lock<std::mutex> lock(m_mutex);
    return getQueueData_i(vdata);
}
bool MPDCli::getQueueData_i(std::vector<UpSong>& vdata)
{
    LOGDEB("MPDCli::getQueueData" << endl);
    vector<mpd_song*> songs;
    if (!getQueueSongs(songs)) {
        return false;
    }
    vdata.reserve(songs.size());
    UpSong usong;
    for (unsigned int pos = 0; pos < songs.size(); pos++) {
        vdata.push_back(mapSong(usong, songs[pos]));
    }
    freeSongs(songs);
    return true;
}

int MPDCli::curpos()
{
    std::unique_lock<std::mutex> lock(m_mutex);
    if (!updStatus())
        return -1;
    LOGDEB("MPDCli::curpos: pos: " << m_stat.songpos << " id " 
           << m_stat.songid << endl);
    return m_stat.songpos;
}

std::string MpdStatus::dump() const
{
    static const std::vector<CharFlags> stf {
        CHARFLAGENTRY(MPDS_UNK),
            CHARFLAGENTRY(MPDS_STOP),
            CHARFLAGENTRY(MPDS_PLAY),
            CHARFLAGENTRY(MPDS_PAUSE),
            };
    std::ostringstream str;
    
    enum State {MPDS_UNK, MPDS_STOP, MPDS_PLAY, MPDS_PAUSE};
    str << "V. " << versmajor << "." << versminor << "." << verspatch << "\n";
    str << "vol " << volume << " rept|random|single|consume " << 
        rept << "|" << random << "|" << single << "|" << consume << "\n";
    str << "qlen " << qlen << " qvers " << qvers << "\n";
    str << "state: " << valToString(stf, state) << "\n";
    str << "cf/rampdb/rampdelay " << crossfade << "/" << mixrampdb << "/" <<
        mixrampdelay  << "\n";
    str << "songpos " << songpos << " songid " << songid << " elpsed " << 
        songelapsedms << " len " << songlenms << "\n";
    str << "kbrate " << kbrate << " samprate " << sample_rate << " depth " <<
        bitdepth << " chans " << channels << "\n";
    str << "error: " << errormessage << "\n";
    str << "cursong " << currentsong.dump() << "\n";
    str << "nextsong " << nextsong.dump() << "\n";
    return str.str();
}

#ifdef MPDCLI_TEST


// c++ -o trmpdcli -DMPDCLI_TEST /path/to/upmpdcli/src/mpdcli.cxx src/closefrom.o src/conftree.o src/pathut.o src/smallut.o src/execmd.o src/netcon.o -lupnpp -lmpdclient -lpthread

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

#include <string>
#include <iostream>
using namespace std;

#include "mpdcli.hxx"

static char *thisprog;

static char usage [] =
              "  \n\n"
              ;
static void
Usage(void)
{
    fprintf(stderr, "Usage: %s <configfile>\n%s", thisprog, usage);
    exit(1);
}

ConfSimple *g_config;
std::string g_configfilename;

static int     op_flags;
#define OPT_MOINS 0x1
#define OPT_s     0x2 
#define OPT_b     0x4 

int main(int argc, char **argv)
{
    int count = 10;
    
    thisprog = argv[0];
    argc--; argv++;

    while (argc > 0 && **argv == '-') {
        (*argv)++;
        if (!(**argv))
            /* Cas du "adb - core" */
            Usage();
        while (**argv)
            switch (*(*argv)++) {
            case 's': op_flags |= OPT_s; break;
            case 'b': op_flags |= OPT_b; if (argc < 2)  Usage();
                if ((sscanf(*(++argv), "%d", &count)) != 1) 
                    Usage(); 
                argc--; 
                goto b1;
            default: Usage(); break;
            }
    b1: argc--; argv++;
    }

    if (argc != 1)
        Usage();
    g_configfilename = *argv++;argc--;
    g_config = new ConfSimple(g_configfilename.c_str(), 1, true);
    MPDCli cli("localhost");
    if (!cli.ok()) {
        cerr << "Cli connection failed" << endl;
        return 1;
    }
    const MpdStatus& status = cli.getStatus();

    std::cout << status.dump();

#if 0
    if (status.state != MpdStatus::MPDS_PLAY) {
        cerr << "Not playing" << endl;
        return 1;
    }
    unsigned int seektarget = (status.songlenms - 4500)/1000;
    cerr << "songpos " << status.songpos << " songid " << status.songid <<
        " seeking to " << seektarget << " seconds" << endl;

    if (!cli.seek(seektarget)) {
        cerr << "Seek failed" << endl;
        return 1;
    }
#endif
    return 0;
}

#endif
