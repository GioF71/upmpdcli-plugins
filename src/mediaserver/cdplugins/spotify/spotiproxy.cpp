/* Copyright (C) 2017-2018 J.F.Dockes
 *   This program is free software; you can redistribute it and/or modify
 *   it under the terms of the GNU General Public License as published by
 *   the Free Software Foundation; either version 2 of the License, or
 *   (at your option) any later version.
 *
 *   This program is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *   GNU General Public License for more details.
 *
 *   You should have received a copy of the GNU General Public License
 *   along with this program; if not, write to the
 *   Free Software Foundation, Inc.,
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
#include "spotiproxy.h"

#include <stdint.h>
#include <stdlib.h>
#include <unistd.h>
#include <dlfcn.h>

#include <mutex>

#include "../spotify/libspotify/api.h"

#include "log.h"
#include "smallut.h"

using namespace std;
using namespace std::placeholders;

/* mopidy appkey from mopidy_spotify/spotify_appkey.key */
/* No idea how to get a new one now that the lib is deprecated, sorry */
const vector<uint8_t> g_appkey {
0x01,0xCF,0x89,0x0F,0xDE,0x9F,0xD6,0x21,0x50,0x16,0x8E,0xD4,0x33,0x7F,0x73,0x82,
0xC1,0x52,0xC7,0x4E,0x85,0x47,0x20,0x8D,0x53,0xB9,0x22,0x5E,0x3D,0xC5,0x2B,0x09,
0xE9,0xCF,0x64,0x2F,0x64,0x85,0xCF,0xC3,0x4B,0x7E,0xEB,0x38,0x06,0x28,0x25,0x6E,
0xD1,0xD5,0xFE,0x47,0xF7,0x7E,0x4C,0x90,0x0E,0x9F,0xB8,0x0B,0x98,0x1A,0x14,0x2E,
0x24,0xBF,0xDD,0x71,0x73,0x6D,0xC5,0xBD,0xF3,0xB2,0x81,0x9E,0x10,0x79,0x7C,0x33,
0x13,0xAC,0x30,0x03,0x97,0x3E,0x74,0x87,0xB6,0x95,0x7C,0xC1,0xEA,0x64,0x89,0xE2,
0x0D,0xDE,0xA2,0xDA,0xB7,0xBC,0xF9,0x2B,0xBB,0xDF,0xB2,0x97,0x34,0xCE,0xBB,0x79,
0xEC,0x2F,0xA2,0xEE,0xF1,0x21,0xF7,0xCC,0xF3,0xC9,0x75,0x90,0x15,0x3F,0xBB,0xAA,
0xC2,0xC9,0x64,0x39,0x07,0xD8,0x57,0x0F,0x09,0x28,0x71,0x47,0x04,0x48,0xF0,0x54,
0x8E,0x4D,0xD3,0x2B,0xC3,0xA3,0xF8,0x2B,0x22,0xC1,0xC2,0x86,0xB3,0x67,0xB9,0xBE,
0x16,0x70,0xE2,0xAB,0x17,0x76,0xE9,0xAD,0x08,0x50,0xCF,0xD8,0x0B,0x32,0xC6,0x34,
0x64,0x4B,0x6F,0xC4,0x20,0x62,0xBD,0x48,0xD1,0xFB,0x57,0x5D,0x29,0xBC,0x10,0x89,
0xC3,0xB5,0x9F,0x57,0xFB,0x74,0x4E,0x01,0x59,0xEB,0xAC,0x99,0xB7,0x95,0x70,0x2C,
0x12,0xE8,0x60,0xE0,0x5F,0x3E,0x56,0xEB,0x74,0x28,0xC0,0x5D,0x2C,0x45,0x09,0x0F,
0x1F,0x96,0x6F,0x99,0x60,0x25,0x08,0x89,0xD0,0xB3,0xFA,0xAD,0x86,0x17,0xE7,0x30,
0xA9,0x5B,0xE7,0x61,0xAC,0x3A,0xFB,0xCD,0xC6,0xFB,0x8A,0xD0,0x19,0xC8,0xBE,0xD8,
0xD5,0xA7,0xBB,0x04,0xE5,0x1D,0xA4,0x00,0x45,0xBD,0x84,0x7B,0xE2,0x7B,0x26,0x5D,
0x6E,0x4C,0x42,0xEF,0xC2,0x72,0x49,0x69,0x9F,0x7D,0x66,0x9E,0x95,0xAA,0x94,0xCF,
0x89,0xC8,0x4C,0xFD,0xD5,0x41,0xE7,0x64,0xA1,0xE8,0xEE,0xA7,0x98,0xD6,0xCF,0x1A,
0x9B,0x03,0x9D,0x93,0xB7,0x5F,0x3C,0xA4,0x36,0xE1,0xF3,0x07,0x4D,0xEA,0x01,0x1D,
0x3D};


// We dlopen libspotify to avoid a hard link dependancy. The entry
// points are resolved into the following struct, which just exists
// for tidyness.
struct SpotifyAPI {
    const char* (*sp_error_message)(sp_error error);
    sp_track * (*sp_link_as_track)(sp_link *link);
    sp_link * (*sp_link_create_from_string)(const char *link);
    sp_error (*sp_link_release)(sp_link *link);
    sp_error (*sp_session_create)(const sp_session_config *, sp_session **sess);
    sp_error (*sp_session_login)(sp_session *, const char *, const char *,
                                 bool, const char *);
    sp_error (*sp_session_logout)(sp_session *session);
    sp_error (*sp_session_player_load)(sp_session *session, sp_track *track);
    sp_error (*sp_session_player_play)(sp_session *session, bool play);
    sp_error (*sp_session_player_seek)(sp_session *session, int offset);
    sp_error (*sp_session_player_unload)(sp_session *session);
    sp_error (*sp_session_process_events)(sp_session *session, int *next_timeo);
    sp_error (*sp_session_set_cache_size)(sp_session *session, size_t size);
    sp_error (*sp_link_add_ref)(sp_link *link);
    int (*sp_track_duration)(sp_track *track);
    sp_error (*sp_track_add_ref)(sp_track *track);
    sp_error (*sp_track_error)(sp_track *track);
    const char * (*sp_track_name)(sp_track *track);
    sp_error (*sp_track_release)(sp_track *track);
};
static SpotifyAPI api;


static SpotiProxy *theSpotiProxy;
static SpotiProxy::Internal *theSPP;
// Lock for the spotiproxy object itself. Because the libspotify
// methods are not reentrant, most SpotiProxy methods take this
// exclusive lock.
static mutex objmutex;

static int g_notify_do;
static sp_session_callbacks session_callbacks;
static sp_session_config spconfig;

// Forward decls
static void login_cb(sp_session *sess, sp_error error);
static void log_message(sp_session *session, const char *msg);
static void notify_main_thread(sp_session *sess);
static void metadata_updated(sp_session *sess);
static int music_delivery(sp_session *sess, const sp_audioformat *format,
                          const void *frames, int num_frames);
static void end_of_track(sp_session *sess);
static void play_token_lost(sp_session *sess);

class SpotiProxy::Internal {
public:

    /* The constructor logs us in, so that "logged_in" is also a general
     * health test. */
    Internal(const string& u, const string& p,
             const string& cd, const string& sd)
        : user(u), pass(p), cachedir(cd), confdir(sd) {
        theSPP = this;
        session_callbacks.logged_in = login_cb;
        session_callbacks.log_message = log_message;
        session_callbacks.notify_main_thread = notify_main_thread;
        session_callbacks.metadata_updated = metadata_updated;
	session_callbacks.music_delivery = music_delivery;
        session_callbacks.play_token_lost = play_token_lost;
	session_callbacks.end_of_track = end_of_track,

        spconfig.api_version = SPOTIFY_API_VERSION;
        spconfig.application_key = &g_appkey[0];
        spconfig.application_key_size = g_appkey.size();
        spconfig.user_agent = "upmpdcli-spotiproxy";
        spconfig.callbacks = &session_callbacks;
        spconfig.cache_location = cachedir.c_str();
        spconfig.settings_location = confdir.c_str();

        if (!init_spotify_api()) {
            cerr << "Error loading spotify library: " << reason << endl; 
            LOGERR("Error loading spotify library: " << reason << endl);
            return;
        }
        sperror = api.sp_session_create(&spconfig, &sp);
        if (SP_ERROR_OK != sperror) {
            registerError(sperror);
            return;
        }
        api.sp_session_login(sp, user.c_str(), pass.c_str(), 1, NULL);
        wait_for("Login", [] (SpotiProxy::Internal *o) {return o->logged_in;});
        if (logged_in) {
            LOGDEB("Spotify: " << user << " logged in ok\n");
        } else {
            LOGERR("Spotify: " << user << " log in failed\n");
        }
        // Max cache size 50 MB
        api.sp_session_set_cache_size(sp, 50);
    }

    // Wait for a state change, tested by a function parameter.
    bool wait_for(const string& who,
                  std::function<bool(SpotiProxy::Internal *)> testit) {
        int next_timeout = 0;
        for (;;) {
            if (!g_notify_do) {
                unique_lock<mutex> lock(spmutex);
                if (testit(this) || sperror != SP_ERROR_OK) {
                    return sperror == SP_ERROR_OK;
                }
                if (next_timeout == 0) {
                    LOGDEB1(who << " Waiting\n");
                    spcv.wait(lock);
                } else {
                    LOGDEB1(who << " waiting " << next_timeout << " mS\n");
                    spcv.wait_for(
                        lock, std::chrono::milliseconds(next_timeout));
                }
            }
            do {
                g_notify_do = 0;
                LOGDEB1(who << " Calling process_events\n");
                api.sp_session_process_events(sp, &next_timeout);
                LOGDEB1(who << " After process_event, next_timeout " <<
                        next_timeout << " notify_do " << g_notify_do << endl);
            } while (next_timeout == 0);
        }
    }        

    void unloadTrack() {
        LOGDEB0("unloadTrack\n");
        unique_lock<mutex> lock(spmutex);
        LOGDEB1("unloadTrack: got lock\n");
        reason.clear();
        sperror = SP_ERROR_OK;
        track_playing = false;
        track_duration = 0;
        if (sp && curtrack) {
            api.sp_track_release(curtrack);
            api.sp_session_player_unload(sp);
        }
        curtrack = nullptr;
        spcv.notify_all();
        LOGDEB1("unloadTrack: done\n");
    }
    
    ~Internal() {
        if (libhandle) {
            unloadTrack();
            if (sp && logged_in) {
                LOGDEB("Logging out\n");
                api.sp_session_logout(sp);
            }
            dlclose(libhandle);
        }
    }

    void registerError(sp_error error) {
        reason += string(api.sp_error_message(error)) + " ";
        sperror = error;
    }
    bool init_spotify_api();

    void  *libhandle{nullptr};

    string user;
    string pass;
    string cachedir;
    string confdir;
    sp_session *sp{nullptr};
    bool logged_in{false};

    // sync for waiting for libspotify events.
    condition_variable spcv;
    mutex spmutex;

    
    string reason;
    sp_error sperror{SP_ERROR_OK};
    sp_track *curtrack{nullptr};
    bool track_playing{false};
    bool sent_0buf{false};
    int track_duration{0};
    AudioSink sink{nullptr};
};

#define NMTOPTR(NM, TP)                                                 \
    if ((api.NM = TP dlsym(libhandle, #NM)) == 0) {                     \
	badnames += #NM + string(" ");					\
    }

static vector<string> lib_suffixes{".so.12", ".so"};

bool SpotiProxy::Internal::init_spotify_api()
{
    reason = "Could not open shared library ";
    string libbase("libspotify");
    for (const auto suff : lib_suffixes) {
        string lib = libbase + suff;
        reason += string("[") + lib + "] ";
        if ((libhandle = dlopen(lib.c_str(), RTLD_LAZY)) != 0) {
            reason.erase();
            goto found;
        }
    }
    
 found:
    if (nullptr == libhandle) {
        reason += string(" : ") + dlerror();
        return false;
    }

    string badnames;
    
    NMTOPTR(sp_error_message, (const char* (*)(sp_error error)));
    NMTOPTR(sp_link_as_track, (sp_track * (*)(sp_link *link)));
    NMTOPTR(sp_link_create_from_string, (sp_link * (*)(const char *link)));
    NMTOPTR(sp_link_release, (sp_error (*)(sp_link *link)));
    NMTOPTR(sp_session_create, (sp_error (*)(const sp_session_config *config,
                                             sp_session **sess)));;
    NMTOPTR(sp_session_login, (sp_error (*)(
        sp_session *session, const char *username, const char *password,
        bool remember_me, const char *blob)));
    NMTOPTR(sp_session_logout, (sp_error (*)(sp_session *session)));
    NMTOPTR(sp_session_player_load, (sp_error (*)(sp_session *session,
                                                  sp_track *track)));
    NMTOPTR(sp_session_player_play, (sp_error (*)(sp_session *session,
                                                  bool play)));
    NMTOPTR(sp_session_player_seek, (sp_error (*)(sp_session *session,
                                                  int offset)));
    NMTOPTR(sp_session_player_unload, (sp_error (*)(sp_session *session)));
    NMTOPTR(sp_session_process_events, (sp_error (*)(sp_session *session,
                                                     int *next_timeout)));
    NMTOPTR(sp_session_set_cache_size, (sp_error (*)(sp_session *session,
                                                     size_t size)));
    NMTOPTR(sp_link_add_ref, (sp_error (*)(sp_link *link)));
    NMTOPTR(sp_track_duration, (int (*)(sp_track *track)));
    NMTOPTR(sp_track_add_ref, (sp_error (*)(sp_track *track)));
    NMTOPTR(sp_track_error, (sp_error (*)(sp_track *track)));
    NMTOPTR(sp_track_name, (const char * (*)(sp_track *track)));
    NMTOPTR(sp_track_release, (sp_error (*)(sp_track *track)));
    if (!badnames.empty()) {
	reason = string("init_libspotify: symbols not found:") + badnames;
	return false;
    }
    return true;
}

class Cleaner {
public:
    ~Cleaner() {
        delete theSpotiProxy;
    }
};
static Cleaner cleaner;

static void login_cb(sp_session *sess, sp_error error)
{
    const char *me = "login_cb";
    LOGDEB1(me << " error " << error << "\n");
    if (nullptr == theSPP) {
        LOGERR(me << " no SPP ??\n");
        // ??
        return;
    }
    unique_lock<mutex> lock(theSPP->spmutex);

    if (SP_ERROR_OK == error) {
        theSPP->logged_in = true;
    } else {
        theSPP->registerError(error);
    }
    theSPP->spcv.notify_all();
}

static void log_message(sp_session *session, const char *msg)
{
    LOGDEB(msg);
}

static void metadata_updated(sp_session *sess)
{
    const char *me = "metadata_updated";
    LOGDEB1(me << "\n");
    if (nullptr == theSPP) {
        LOGERR(me << " no SPP ??\n");
        return;
    }
    unique_lock<mutex> lock(theSPP->spmutex);
    theSPP->spcv.notify_all();
}

static int music_delivery(sp_session *sess, const sp_audioformat *format,
                          const void *frames, int num_frames)
{
    const char *me = "music_delivery";
    static int counter;
    if ((counter++ %100) == 0) {
        LOGDEB1(me << ": " << num_frames << " frames " <<
                " samplerate " << format->sample_rate << " channels " <<
                format->channels << endl);
    }

    if (num_frames == 0) {
        LOGDEB("music_delivery: called with 0 frames\n");
        return 0;
    }
    if (nullptr == theSPP) {
        return -1;
    }
    if (num_frames > 4096) {
        // Declare eot when we see a silence buffer Not too sure why
        // these silence buffers are generated before the
        // notify_main_thread/end_of_track is called. At some point,
        // we called unload from here (see the git hist). It happens
        // that notify_main thread is not called at all after we get a
        // silence buffer (probable libspotify bug ? Just do it here
        // for safety.
        LOGDEB(me << ": got silence buffer\n");
        // Silence buffer: end of real track
        if (!theSPP->sent_0buf) {
            theSPP->sent_0buf = true;
            theSPP->sink(frames, 0, format->channels, format->sample_rate);
        }
        g_notify_do = true;
        theSPP->spcv.notify_all();
        return num_frames;
    }

    return theSPP->sink(frames, num_frames, format->channels,
                        format->sample_rate);
}

#if 0
// Spotify probably does this to adjust its send rate, but it's not
// clear how to implement it in general, nor does it seems to be
// needed. Would need another function callback to work (in addition
// to sink())
static void get_audio_buffer_stats(sp_session *sess,
                                   sp_audio_buffer_stats *stats)
{
    const char *me = "get_audio_buffer_stats";
    LOGDEB(me << "\n");
    if (nullptr == theSPP) {
        LOGERR(me << " no SPP ??\n");
        // ??
        return;
    }

    stats->samples = 0;
    stats->stutter = 0;
}
#endif

static void end_of_track(sp_session *sess)
{
    const char *me = "end_of_track";
    LOGDEB(me << "\n");
    if (nullptr == theSPP) {
        LOGERR(me << " no SPP ??\n");
        // ??
        return;
    }
    unique_lock<mutex> lock(theSPP->spmutex);

    theSPP->track_playing = false;
    theSPP->track_duration = 0;
    theSPP->spcv.notify_all();
}

static void play_token_lost(sp_session *sess)
{
    const char *me = "play_token_lost";
    LOGDEB(me << "\n");
    if (nullptr == theSPP) {
        LOGERR(me << " no SPP ??\n");
        // ??
        return;
    }
    api.sp_session_player_play(theSPP->sp, 0);
}

static void notify_main_thread(sp_session *sess)
{
    const char *me = "notify_main_thread";
    LOGDEB(me << "\n");
    if (nullptr == theSPP) {
        LOGERR(me << " no SPP ??\n");
        // ??
        return;
    }
    unique_lock<mutex> lock(theSPP->spmutex);
    g_notify_do = 1;
    theSPP->spcv.notify_all();
}

static string o_user, o_password, o_cachedir, o_settingsdir;
void SpotiProxy::setParams(
        const std::string& user, const std::string& pass,
        const std::string& cachedir, const std::string& settingsdir)
{
    o_user = user;
    o_password = pass;
    o_cachedir = cachedir;
    o_settingsdir = settingsdir;
}

SpotiProxy *SpotiProxy::getSpotiProxy(
    const string& u, const string& p, const string& cached, const string& confd)
{
    LOGDEB1("getSpotiProxy\n");
    unique_lock<mutex> lock(objmutex);
    if (theSpotiProxy) {
        LOGDEB1("getSpotiProxy: already created\n");
        if ((u.empty() && p.empty()) ||
            (theSpotiProxy->m->user == u && theSpotiProxy->m->pass == p)) {
            return theSpotiProxy;
        } else {
            return nullptr;
        }
    } else {
        string user{u.empty() ? o_user : u};
        string pass{p.empty() ? o_password : p};
        string cachedir{cached.empty() ? o_cachedir : cached};
        string confdir{confd.empty() ? o_settingsdir : confd};
        LOGDEB("getSpotiProxy: creating for user " << user <<
               " cachedir " << cachedir << " confdir " <<confdir<<"\n");
        theSpotiProxy = new SpotiProxy(user, pass, cachedir, confdir);
        return theSpotiProxy;
    }
}


SpotiProxy::SpotiProxy(const string& user, const string& password,
                       const string& cd, const string& sd)
    : m(std::unique_ptr<Internal>(new Internal(user, password, cd, sd)))
{
}

SpotiProxy::~SpotiProxy() {}

bool SpotiProxy::playTrack(const string& trackid, AudioSink sink,
                           int seekmsecs)
{
    if (!startPlay(trackid, sink, seekmsecs)) {
        return false;
    }
    return waitForEndOfPlay();
}

bool SpotiProxy::startPlay(const string& trackid, AudioSink sink,
                             int seekmsecs)
{
    LOGDEB("SpotiProxy::startPlay: id " << trackid << " at " <<
           seekmsecs / 1000 << " S\n");
    unique_lock<mutex> lock(objmutex);
    if (!m || !m->logged_in) {
        LOGERR("SpotiProxy::startPlay: init failed.\n");
        return false;
    }
    string trackref("spotify:track:");
    trackref += trackid;
    sp_link *link = api.sp_link_create_from_string(trackref.c_str());
    if (!link) {
        LOGERR("SpotiProxy:startPlay: link creation failed\n");
        return false;
    }
    m->curtrack = api.sp_link_as_track(link);
    api.sp_track_add_ref(m->curtrack);
    api.sp_link_release(link);

    m->sink = sink;

    if (!m->wait_for("startPlay", [](SpotiProxy::Internal *o) {
                return api.sp_track_error(o->curtrack) == SP_ERROR_OK;})) {
        LOGERR("playTrackId: error waiting for track metadata ready\n");
        return false;
    }

    theSPP->track_duration = api.sp_track_duration(m->curtrack);
    api.sp_session_player_load(m->sp, m->curtrack);
    if (seekmsecs) {
        api.sp_session_player_seek(m->sp, seekmsecs);
    }
    api.sp_session_player_play(m->sp, 1);
    m->track_playing = true;
    m->sent_0buf = false;
    LOGDEB("SpotiProxy::startPlay: NOW PLAYING "<<
           api.sp_track_name(m->curtrack) <<
           ". Duration: " << theSPP->track_duration << endl);
    return true;
}

bool SpotiProxy::waitForEndOfPlay()
{
    LOGDEB("SpotiProxy::waitForEndOfPlay\n");
    unique_lock<mutex> lock(objmutex);
    if (!m || !m->logged_in) {
        LOGERR("SpotiProxy::waitForEndOfPlay: init failed.\n");
        return false;
    }
    if (!m->wait_for("waitForEndOfPlay", [](SpotiProxy::Internal *o) {
                return o->track_playing == false;})) {
        LOGERR("playTrackId: error waiting for end of track play\n");
        return false;
    }
    return true;
}

bool SpotiProxy::isPlaying()
{
    if (!m || !m->logged_in) {
        LOGERR("SpotiProxy::isPlaying: init failed.\n");
        return false;
    }
    return m->track_playing;
}

int SpotiProxy::durationMs()
{
    if (!m || !m->logged_in) {
        LOGERR("SpotiProxy::durationMs: init failed.\n");
        return 0;
    }
    return m->track_duration;
}

void SpotiProxy::stop()
{
    LOGDEB("SpotiProxy:stop()\n");
    unique_lock<mutex> lock(objmutex);
    if (!m || !m->logged_in) {
        LOGERR("SpotiProxy::stop: init failed.\n");
        return;
    }
    m->unloadTrack();
}

bool SpotiProxy::loginOk()
{
    return m && m->logged_in;
}

const string& SpotiProxy::getReason()
{
    static string nobuild("Constructor failed");
    return m ? m->reason : nobuild;
}


////////// NetFetch wrapper ////////////////////////////////////////////

inline int inttoichar4(unsigned char *cdb, unsigned int addr)
{
    cdb[3] = (addr & 0xff000000) >> 24;
    cdb[2] = (addr & 0x00ff0000) >> 16;
    cdb[1] = (addr & 0x0000ff00) >> 8;
    cdb[0] =  addr & 0x000000ff;
    return 4;
}

inline int inttoichar2(unsigned char *cdb, unsigned int cnt)
{
    cdb[1] = (cnt & 0x0000ff00) >> 8;
    cdb[0] =  cnt & 0x000000ff;
    return 2;
}


#if 0
// For reference: definition of a wav header
// Les valeurs en commentaires sont donnees pour du son 44100/16/2
struct wav_header {
    /*0 */char  riff[4];     /* = 'RIFF' */
    /*4 */int32 rifflen;     /* longueur des infos qui suivent= datalen+36 */
    /*8 */char  wave[4];     /* = 'WAVE' */

    /*12*/char  fmt[4];      /* = 'fmt ' */
    /*16*/int32 fmtlen;      /* = 16 */
    /*20*/int16 formtag;     /* = 1 : PCM */
    /*22*/int16 nchan;       /* = 2 : nombre de canaux */
    /*24*/int32 sampspersec; /* = 44100 : Nbr d'echantillons par seconde */
    /*28*/int32 avgbytpersec;/* = 176400 : Nbr moyen octets par seconde */
    /*32*/int16 blockalign;  /* = 4 : nombre d'octets par echantillon */
    /*34*/int16 bitspersamp; /* = 16 : bits par echantillon */

    /*36*/char  data[4];     /* = 'data' */
    /*40*/int32 datalen;     /* Nombre d'octets de son qui suivent */
    /*44*/char data[];
};
#endif /* if 0 */

#define WAVHSIZE 44
#define RIFFTOWAVCNT 36

// Format header. Note the use of intel format integers. Input buffer must 
// be of size >= 44
int makewavheader(char *buf, int maxsize, int freq, int bits, 
                  int chans, unsigned int databytecnt)
{
    if (maxsize < WAVHSIZE)
        return -1;

    unsigned char *cp = (unsigned char *)buf;
    memcpy(cp, "RIFF", 4);
    cp += 4;
    inttoichar4(cp, databytecnt + RIFFTOWAVCNT);
    cp += 4;
    memcpy(cp, "WAVE", 4);
    cp += 4;

    memcpy(cp, "fmt ", 4);
    cp += 4;
    inttoichar4(cp, 16);
    cp += 4;
    inttoichar2(cp, 1);
    cp += 2;
    inttoichar2(cp, chans);
    cp += 2;
    inttoichar4(cp, freq);
    cp += 4;
    inttoichar4(cp, freq * chans * (bits / 8));
    cp += 4;
    inttoichar2(cp, chans * bits / 8);
    cp += 2;
    inttoichar2(cp, bits);
    cp += 2;

    memcpy(cp, "data", 4);
    cp += 4;
    inttoichar4(cp, databytecnt);
    cp += 4;

    return WAVHSIZE;
}

class SpotiFetch::Internal {
    static const int SAMPLES_BUF_SIZE = 16 * 1024;
public:

    Internal(SpotiFetch *parent)
        : p(parent) {
        LOGDEB("SpotiFetch::SpotiFetch:\n");
        spp = SpotiProxy::getSpotiProxy();
        if (nullptr == spp) {
            LOGERR("SpotiFetch::start: getSpotiProxy returned null\n");
        }
        _sink = std::bind(&Internal::framesink, this, _1, _2, _3, _4);

    }

    ~Internal() {
        LOGDEB("SpotiFetch::~SpotiFetch: clen " << _contentlen <<
               " total sent " << _totalsent << endl);
        if (spp) {
            spp->stop();
        }
    }
    
    // Write callback receiving data from Spotify.
    int framesink(const void *frames, int num_frames, int chans, int rate) {
        LOGDEB1("SpotiFefch::framesink. dryrun " << _dryrun << " num_frames " <<
                num_frames<< " channels " << chans << " rate " << rate << endl);

        
        // Need samplerate, so can only be done on first data call
        if (_streamneedinit) {
            {unique_lock<mutex> lock(_mutex);
                // First pass, compute what's needed, discard data
                LOGDEB("SpotiFetch: sample rate " << rate << " chans " <<
                       chans << endl);
                _samplerate = rate;
                _channels = chans;
                _streamneedinit = false;
                // We fake a slightly longer song. This is ok with
                // mpd, but the actual transfer will be shorter than
                // what the wav header and content-length say, which
                // may be an issue with some renderers, and will
                // not work at all with, e.g. wget or curl.
                //
                // Adding silence in this case, would break gapless
                // with mpd, so we don't do it. This might be a
                // settable option.
                //
                // In the case where 200 mS is < actual diff, the long
                // transfer will be truncated to content-length by mhd
                // anyway, only the header will be wrong in this case.
                _durationms = spp->durationMs() + 300;
                _contentlen = (_noheader? 0 : 44) +
                    ((_durationms - _initseekmsecs) / 10) *
                    (rate/100) * 2 * chans;
                LOGDEB0("framesink: contentlen: " << _contentlen << endl);
                _dryruncv.notify_all();
                if (!_dryrun) {
                    _cv.notify_all();
                }
            }
            if (!_dryrun && !_noheader) {
                char buf[100];
                LOGDEB("Sending wav header. content-length " << _contentlen <<
                       "\n");
                int cnt = makewavheader(
                    buf, 100, rate, 16, chans, _contentlen - 44);
                _totalsent += cnt;
                p->databufToQ(buf, cnt);
            }
        }

        if (_dryrun) {
            return num_frames;
        }

        // A call with num_frames == 0 signals the end of stream
        if (num_frames == 0) {
            LOGDEB("SpotiFetch: empty buf: EOS. clen: " << _contentlen <<
                   " total sent: " << _totalsent << endl);

            // Padding with a silence buffer avoids curl errors, but
            // it creates a gap. OTOH curl errors often cause the last
            // buffer to be dropped so that gapless is broken too (in
            // a different way). No good solution here. Avoiding curl
            // (and wav header) errors is probably better all in all).
            size_t resid = _contentlen - _totalsent;
            if (resid > 0 && resid < 5000000) {
                LOGDEB("SpotiFetch: padding track with " << resid <<
                       " bytes (" << (resid*10)/(2*chans*rate/100) << " mS)\n");
                char *buf = (char *)malloc(resid);
                if (buf) {
                    memset(buf, 0, resid);
                    p->databufToQ(buf, resid);
                }
            }

            // Enqueue empty buffer.
            p->databufToQ(frames, 0);
            return 0;
        }

        int bytes = num_frames * chans * 2;
        if (_totalsent + bytes > _contentlen) {
            bytes = _contentlen - _totalsent;
            if (bytes <= 0) {
                return num_frames;
            }
        }
        _totalsent += bytes;
        p->databufToQ(frames, bytes);
        return num_frames;
    }

    bool dodryrun(const string& url) {
        _dryrun = true;
        if (!spp->startPlay(url, _sink, 0)) {
            LOGERR("dodryrun: startplay failed\n");
            _dryrun = false;
            _streamneedinit = true;
            return false;
        }
        bool ret = waitForHeadersInternal(0, true);
        spp->stop();
        _streamneedinit = true;
        return ret;
    }

    bool waitForHeadersInternal(int maxSecs, bool isfordry) {
        unique_lock<mutex> lock(_mutex);
        LOGDEB("waitForHeaders: rate " << _samplerate << " isfordry " <<
               isfordry << " dryrun " << _dryrun << "\n");
        while (_samplerate == 0 || (!isfordry && _dryrun)) {
            LOGDEB1("waitForHeaders: waiting for sample rate. rate " <<
                   _samplerate << " isfordry " << isfordry << " dryrun " <<
                   _dryrun << "\n");
            if (isfordry) {
                _dryruncv.wait(lock);
            } else {
                _cv.wait(lock);
            }
        }
        LOGDEB("SpotiFetch::waitForHeaders: isfordry " << isfordry <<
               " dryrun " << _dryrun<<" returning "<< spp->isPlaying() << endl);
        return spp->isPlaying();
    }
    void resetStreamFields() {
        _dryrun = false;
        _streamneedinit = true;
        _durationms = 0;
        _initseekmsecs = 0;
        _noheader = false;
        _samplerate = 0;
        _channels = 0;
        _contentlen = 0;
        _totalsent = 0;
    }
    SpotiFetch *p;
    SpotiProxy *spp{nullptr};
    SpotiProxy::AudioSink _sink;

    bool _dryrun{false};
    bool _streamneedinit{true};
    int _initseekmsecs{0};
    // This is for the case where the offset is non-zero (most often
    // 44 in practise), but small enough that _initseekmsecs is 0.
    bool _noheader{false};
    int _samplerate{0};
    int _channels{0};
    int _durationms{0};
    uint64_t _contentlen{0};
    uint64_t _totalsent{0};

    condition_variable _cv;
    condition_variable _dryruncv;
    mutex _mutex;
};

bool SpotiFetch::reset()
{
    LOGDEB("SpotiFetch::reset\n");
    m->spp->stop();
    m->spp->waitForEndOfPlay();

    m->resetStreamFields();
    return true;
}

SpotiFetch:: SpotiFetch(const std::string& url)
    : NetFetch(url), m(new Internal(this)) {}

SpotiFetch::~SpotiFetch() {}

bool SpotiFetch::start(BufXChange<ABuffer*> *queue, uint64_t offset)
{
    LOGDEB("SpotiFetch::start: Offset: " << offset << " queue " <<
           (queue? queue->getname() : "null") << endl);

    // Flush current queue if any
    if (outqueue) {
        outqueue->waitIdle();
    }
    outqueue = queue;

    reset();
    
    uint64_t v = 0;
    if (offset) {
        m->dodryrun(_url);
        if (m->_samplerate == 0 || m->_channels == 0) {
            LOGERR("SpotiFetch::start: rate or chans 0 after dryrun\n");
            return false;
        } else {
            LOGDEB("SpotiFetch::start: after dryrun rate " << m->_samplerate <<
                   " chans " << m->_channels << endl);
        }
        v = (10 * offset) / (m->_channels * 2 * (m->_samplerate/100));
        LOGDEB("SpotiFetch::start: computed seek ms: " << v << " duration " <<
               m->_durationms << endl);
        if (v > uint64_t(m->_durationms)) {
            v = m->_durationms;
        }
    }
    LOGDEB("SpotiFetch::start: seek msecs: " << v << endl);
    m->_initseekmsecs = v;
    
    m->_dryrun = false;
    // Reset samplerate so that the external waitForHeaders will only
    // return after we get the first frame and the actual contentlen
    // is computed (and samplerate set again).
    m->_samplerate = 0;
    if (offset) {
        m->_noheader = true;
    }
    return m->spp->startPlay(_url, m->_sink, m->_initseekmsecs);
}

bool SpotiFetch::waitForHeaders(int maxSecs)
{
    return m->waitForHeadersInternal(maxSecs, false);
}

bool SpotiFetch::headerValue(const std::string& nm, std::string& val)
{
    if (!stringlowercmp("content-type", nm)) {
        val = "audio/wav";
        LOGDEB1("SpotiFetch::headerValue: content-type: " << val << "\n");
        return true;
    } else if (!stringlowercmp("content-length", nm)) {
        ulltodecstr(m->_contentlen, val);
        LOGDEB("SpotiFetch::headerValue: content-length: " << val << "\n");
        return true;
    }
    return false;
}

bool SpotiFetch::fetchDone(FetchStatus *code, int *http_code)
{
    bool ret= !m->spp->isPlaying();
    if (ret && code) {
        *code = m->spp->getReason().empty() ? FETCH_OK : FETCH_FATAL;
    }
    if (http_code) {
        *http_code = 0;
    }
    LOGDEB0("SpotiFetch::fetchDone: returning " << ret << endl);
    return ret;
}
