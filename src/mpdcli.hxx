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
#ifndef _MPDCLI_H_X_INCLUDED_
#define _MPDCLI_H_X_INCLUDED_

#include <regex.h>
#include <string>
#include <cstdio>
#include <vector>
#include <memory>
#include <utility>
#include <functional>
#include <thread>
#include <mutex>
#include <condition_variable>

#include "upmpdutils.hxx"

struct mpd_song;
struct mpd_connection;

class MpdStatus {
public:
    MpdStatus() : state(MPDS_UNK), trackcounter(0), detailscounter(0) {}

    enum State {MPDS_UNK, MPDS_STOP, MPDS_PLAY, MPDS_PAUSE};

    unsigned int versmajor;
    unsigned int versminor;
    unsigned int verspatch;
    int volume;
    bool rept;
    bool random;
    bool single;
    bool consume;
    int qlen;
    int qvers;
    State state;
    unsigned int crossfade;
    float mixrampdb;
    float mixrampdelay;
    int songpos;
    int songid;
    unsigned int songelapsedms; //current ms
    unsigned int songlenms; // song millis
    unsigned int kbrate;
    unsigned int sample_rate;
    unsigned int bitdepth;
    unsigned int channels;
    std::string errormessage;
    UpSong currentsong;
    UpSong nextsong;

    // Synthetized fields
    int trackcounter;
    int detailscounter;
};

// Complete Mpd State
struct MpdState {
    MpdStatus status;
    std::vector<UpSong> queue;
};

class MPDCli {
public:
    MPDCli(const std::string& host, int port = 6600, const std::string& pss="");
    ~MPDCli();
    bool ok() {return m_conn != nullptr;}
    bool setVolume(int ivol, bool isMute = false);
    int  getVolume();
    void forceInternalVControl();
    bool togglePause();
    bool pause(bool onoff);
    bool play(int pos = -1);
    bool playId(int id = -1);
    bool stop();
    bool next();
    bool previous();
    bool repeat(bool on);
    bool random(bool on);
    bool single(bool on);
    bool consume(bool on);
    bool seek(int seconds);
    bool clearQueue();
    // Insert. use pos==-1 for just adding to the queue
    int insert(const std::string& uri, int pos, const UpSong& meta);
    // Insert after given id. Returns new id or -1
    int insertAfterId(const std::string& uri, int id, const UpSong& meta);
    bool deleteId(int id);
    // start included, end excluded
    bool deletePosRange(unsigned int start, unsigned int end);
    bool statId(int id);
    int curpos();
    bool getQueueData(std::vector<UpSong>& vdata);
    bool statSong(UpSong& usong, int pos = -1, bool isId = false);
    UpSong& mapSong(UpSong& usong, struct mpd_song *song);
    const MpdStatus& getStatus();
    // Copy complete mpd state. If seekms is > 0, this is the value to
    // save (sometimes useful if mpd was stopped)
    bool saveState(MpdState& st, int seekms = 0);
    bool restoreState(const MpdState& st);

    // Event loop. Allows running without polling from libupnpp (no
    // call to the device eventloop()). We collect events from MPD
    // instead and call the event generating chain when appropriate.
    bool eventLoop();
    bool startEventLoop();
    void stopEventLoop();
    bool takeEvents(MPDCli *from);
    void shouldExit();
    // Event selection mask.
    enum SubsSelect {
        // Lazy us are using the values from mpd/idle.h. Could translate instead.
        MpdQueueEvt = 0x4, /* Queue modified */
        MpdPlayerEvt = 0x8, /* Play, stop, etc. + play time, locally generated*/
        MpdMixerEvt = 0x10, /* Volume */
        MpdOptsEvt = 0x40, /* random, repeat, etc. */
    };
    // Type of subscription callback 
    typedef std::function<void (const MpdStatus*)> evtFunc;
    // Subscribe to event mask. Called by the services during initialization.
    bool subscribe(int mask, evtFunc);
    
private:
    std::mutex m_mutex;
    // Main connection for sending commands
    std::mutex m_connmutex;
    struct mpd_connection *m_conn{nullptr};
    // Connection for the event loop
    struct mpd_connection *m_idleconn{nullptr};
    // thread to listen to MPD events.
    std::thread m_idlethread;
    // MPD does not report idle events for play time change. We poll
    // it every second while playing to report the current time
    // (needed for OHTime events for example)
    std::thread m_pollerthread;
    std::mutex m_pollmutex;
    std::condition_variable m_pollcv;
    bool m_dopoll{false};
    // Event subscriptions
    std::vector<std::pair<int, evtFunc>> m_subs;

    MpdStatus m_stat;
    // Saved volume while muted.
    int m_premutevolume{0};
    // Volume that we use when MPD is stopped (does not return a
    // volume in the status)
    int m_cachedvolume{50}; 
    std::string m_host;
    int m_port;
    int m_timeoutms{2000};
    std::string m_password;
    std::string m_onstart;
    std::string m_onplay;
    std::string m_onpause;
    std::string m_onstop;
    bool m_externalvolumecontrol{false};
    std::vector<std::string> m_onvolumechange;
    std::vector<std::string> m_getexternalvolume;
    regex_t m_tpuexpr;
    // addtagid command only exists for mpd 0.19 and later.
    bool m_have_addtagid{false};
    // Position and id of last insertion: if the new request is to
    // insert after this id, and the queue did not change, we compute
    // the new position from the last one instead of re-reading the
    // queue for looking up the id position. This saves a huge amount
    // of time.
    int m_lastinsertid{-1};
    int m_lastinsertpos{-1};
    int m_lastinsertqvers{-1};

    bool openconn();
    void closeconn();
    bool updStatus();
    bool getQueueSongs(std::vector<mpd_song*>& songs);
    void freeSongs(std::vector<mpd_song*>& songs);
    bool showError(const std::string& who);
    bool looksLikeTransportURI(const std::string& path);
    bool checkForCommand(const std::string& cmdname);
    bool send_tag(const char *cid, int tag, const std::string& data);
    bool send_tag_data(int id, const UpSong& meta);
    // Non-locking versions of public calls.
    bool clearQueue_i();
    bool consume_i(bool on);
    bool getQueueData_i(std::vector<UpSong>& vdata);
    int insert_i(const std::string& uri, int pos, const UpSong& meta);
    bool pause_i(bool onoff);
    bool play_i(int pos);
    bool random_i(bool on);
    bool repeat_i(bool on);
    bool seek_i(int seconds);
    bool single_i(bool on);
    bool statSong_i(UpSong& usong, int pos = -1, bool isId = false);
    // thread routine for polling play time while playing.
    void timepoller();
    void pollerCtl(MpdStatus::State st);
};

#endif /* _MPDCLI_H_X_INCLUDED_ */
