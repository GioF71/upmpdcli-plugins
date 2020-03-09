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
/////////////////////////////////////////////////////////////////////
// Main program
#define UPMPDCLI_NEED_PACKAGE_VERSION
#include "config.h"

#include <errno.h>             
#include <fcntl.h>             
#include <pwd.h>               
#include <signal.h>            
#include <stdio.h>             
#include <stdlib.h>            
#include <sys/param.h>         
#include <unistd.h>            
#include <grp.h>
#include <assert.h>

#include <iostream>            
#include <string>              
#include <unordered_map>       
#include <vector>              

#include "libupnpp/log.hxx"    
#include "libupnpp/upnpplib.hxx"
#include "execmd.h"
#include "conftree.h"
#include "mpdcli.hxx"
#include "upmpd.hxx"
#include "mediaserver/mediaserver.hxx"
#include "mediaserver/contentdirectory.hxx"
#include "upmpdutils.hxx"
#include "pathut.h"
#include "readfile.h"

using namespace std;
using namespace UPnPP;

// Can't remember why it's static in config.h and don't want to try change
const string g_upmpdcli_package_version{UPMPDCLI_PACKAGE_VERSION};

static char *thisprog;

static int op_flags;
#define OPT_MOINS 0x1   
#define OPT_D     0x2   
#define OPT_O     0x4   
#define OPT_P     0x8   
#define OPT_c     0x10  
#define OPT_d     0x20  
#define OPT_f     0x40  
#define OPT_h     0x80  
#define OPT_i     0x100 
#define OPT_l     0x200 
#define OPT_m     0x400 
#define OPT_p     0x800 
#define OPT_q     0x1000
#define OPT_v     0x2000

static const char usage[] = 
    "-c configfile \t configuration file to use\n"
    "-h host    \t specify host MPD is running on\n"
    "-p port     \t specify MPD port\n"
    "-d logfilename\t debug messages to\n"
    "-l loglevel\t  log level (0-6)\n"
    "-D    \t run as a daemon\n"
    "-f friendlyname\t define device displayed name\n"
    "-q 0|1\t if set, we own the mpd queue, else avoid clearing it whenever we feel like it\n"
    "-i iface    \t specify network interface name to be used for UPnP\n"
    "-P upport    \t specify port number to be used for UPnP\n"
    "-O 0|1\t decide if we run and export the OpenHome services\n"
    "-v      \tprint version info\n"
    "-m <0|1|2|3|4> media server mode "
    "(default, forked|only renderer|only media|combined/embedded|combined/multidev)\n"
    "\n"
    ;

// We can implement a Media Server in addition to the Renderer, for
// accessing streaming services. This can happen in several modes. In
// all cases, the Media Server is only created if the configuration
// file does have parameters set for streaming services.
// All this complication is needed because libupnp does not support
// having several root devices in a single process, and because many
// control points are confused by embedded devices.
// 
// - -m 0, default, Forked: this is for the main process, which will
//    implement a Media Renderer device, and, if needed, fork/exec the
//    Media Server (with option -m 2)
// - -m 1, RdrOnly: for the main instance: be a Renderer, do not start the
//    Media Server even if the configuration indicates it is needed
//    (this is not used in normal situations, just edit the config
//    instead!)
// - -m 2, MSOnly Media Server only, this is for the process forked/execed
//    by a main Renderer process, or a standalone Media Server.
// - -m 3, Combined: for the main process: implement the Media Server
//    as an embedded device. This works just fine with, for example,
//    upplay, but confuses most of the other Control Points.
// - -m 4, Combined: for the main process: implement the Media Server
//    as a separate root device. Only works with a modified libupnp.
enum MSMode {Forked, RdrOnly, MSOnly, CombinedEmbedded, CombinedMultiDev};

static void
versionInfo(FILE *fp)
{
    fprintf(fp, "Upmpdcli %s %s\n",
           UPMPDCLI_PACKAGE_VERSION, LibUPnP::versionString().c_str());
}

static void
Usage(FILE *fp = stderr)
{
    fprintf(fp, "%s: usage:\n%s", thisprog, usage);
    versionInfo(fp);
    exit(1);
}


static const string dfltFriendlyName("UpMpd");

ohProductDesc_t ohProductDesc = {
    // Manufacturer
    {
        "UpMPDCli heavy industries Co.",            // name
        "Such nice guys and gals",                  // info
        "http://www.lesbonscomptes.com/upmpdcli",   // url
        ""                                          // imageUri
    },
    // Model
    {
        "UpMPDCli UPnP-MPD gateway",                // name
        "",                                         // info
        "http://www.lesbonscomptes.com/upmpdcli",   // url
        ""                                          // imageUri
    },
    // Product
    {
        "Upmpdcli",                                 // name
        UPMPDCLI_PACKAGE_VERSION,                   // info
        "",                                         // url
        ""                                          // imageUri
    }
};

// Ad-hoc struct to hold the input identification parameters for the device(s)
struct UDevIds {
    std::string fname;
    std::string uuid;
    std::string fnameMS;
    std::string uuidMS;
};

// Static for cleanup in sig handler.
static vector<UpnpDevice *> devs;

string g_datadir(DATADIR "/");
string g_cachedir("/var/cache/upmpdcli");

// Global
string g_configfilename;
ConfSimple *g_config;
ConfSimple *g_state;
bool g_enableL16 = false;
bool g_lumincompat = false;

static void onsig(int)
{
    LOGDEB("Got sig" << endl);
    for (auto& dev : devs) {
        dev->shouldExit();
    }
}

static const int catchedSigs[] = {SIGINT, SIGQUIT, SIGTERM};
static void setupsigs()
{
    struct sigaction action;
    action.sa_handler = onsig;
    action.sa_flags = 0;
    sigemptyset(&action.sa_mask);
    for (unsigned int i = 0; i < sizeof(catchedSigs) / sizeof(int); i++)
        if (signal(catchedSigs[i], SIG_IGN) != SIG_IGN) {
            if (sigaction(catchedSigs[i], &action, 0) < 0) {
                perror("Sigaction failed");
            }
        }
}

static vector<string> savedargs;

// See comment in main.hxx
bool startMsOnlyProcess()
{
    static ExecCmd cmd;
    if (cmd.getChildPid() > 0) {
        return true;
    }
    // Fork process for media server, replacing whatever -m option
    // was given with -m 2 (ms only)
    vector<string> args{"-m", "2"};
    string cmdpath(savedargs[0]);
    for (unsigned int i = 1; i < savedargs.size(); i++) {
        string sa(savedargs[i]);
        if (sa[sa.length() - 1] == 'm') {
            sa = sa.substr(0, sa.length()-1);
            if (i == savedargs.size() - 1)
                Usage();
            i++;
        }
        if (!sa.empty() && sa.compare("-")) {
            args.push_back(sa);
        }
    }
    return cmd.startExec(cmdpath, args, false, false) >= 0;
}

int main(int argc, char *argv[])
{
    for (int i = 0; i < argc; i++) {
        savedargs.push_back(argv[i]);
    }
    
    // Path for the sc2mpd command, or empty
    string sc2mpdpath;
    string screceiverstatefile;

    // Sender mode: path for the command creating the mpd and mpd2sc
    // processes, and port for the auxiliary mpd.
    string senderpath;
    int sendermpdport = 6700;

    // Main MPD parameters
    string mpdhost("localhost");
    int mpdport = 6600;
    string mpdpassword;

    string logfilename;
    int loglevel(Logger::LLINF);
    string friendlyname(dfltFriendlyName);
    bool ownqueue = true;
    bool enableAV = true;
    bool enableOH = true;
    bool enableMediaServer = false;
    bool ohmetapersist = true;
    string upmpdcliuser("upmpdcli");
    string pidfilename("/var/run/upmpdcli.pid");
    string iconpath(DATADIR "/icon.png");
    string presentationhtml(DATADIR "/presentation.html");
    string iface;
    unsigned short upport = 0;
    string upnpip;
    int msm = 0;
    bool inprocessms{false};
    bool msonly{false};
    bool msroot{false};
    
    const char *cp;
    if ((cp = getenv("UPMPD_HOST")))
        mpdhost = cp;
    if ((cp = getenv("UPMPD_PORT")))
        mpdport = atoi(cp);
    if ((cp = getenv("UPMPD_FRIENDLYNAME")))
        friendlyname = atoi(cp);
    if ((cp = getenv("UPMPD_CONFIG")))
        g_configfilename = cp;
    if ((cp = getenv("UPMPD_UPNPIFACE")))
        iface = cp;
    if ((cp = getenv("UPMPD_UPNPPORT")))
        upport = atoi(cp);

    thisprog = argv[0];
    argc--; argv++;
    while (argc > 0 && **argv == '-') {
        (*argv)++;
        if (!(**argv))
            Usage();
        while (**argv)
            switch (*(*argv)++) {
            case 'c':   op_flags |= OPT_c; if (argc < 2)  Usage();
                g_configfilename = *(++argv); argc--; goto b1;
            case 'D':   op_flags |= OPT_D; break;
            case 'd':   op_flags |= OPT_d; if (argc < 2)  Usage();
                logfilename = *(++argv); argc--; goto b1;
            case 'f':   op_flags |= OPT_f; if (argc < 2)  Usage();
                friendlyname = *(++argv); argc--; goto b1;
            case 'h':   op_flags |= OPT_h; if (argc < 2)  Usage();
                mpdhost = *(++argv); argc--; goto b1;
            case 'i':   op_flags |= OPT_i; if (argc < 2)  Usage();
                iface = *(++argv); argc--; goto b1;
            case 'l':   op_flags |= OPT_l; if (argc < 2)  Usage();
                loglevel = atoi(*(++argv)); argc--; goto b1;
            case 'm':   op_flags |= OPT_m; if (argc < 2)  Usage();
                msm = atoi(*(++argv)); argc--; goto b1;
            case 'O': {
                op_flags |= OPT_O; 
                if (argc < 2)  Usage();
                const char *cp =  *(++argv);
                if (*cp == '1' || *cp == 't' || *cp == 'T' || *cp == 'y' || 
                    *cp == 'Y')
                    enableOH = true;
                argc--; goto b1;
            }
            case 'P':   op_flags |= OPT_P; if (argc < 2)  Usage();
                upport = atoi(*(++argv)); argc--; goto b1;
            case 'p':   op_flags |= OPT_p; if (argc < 2)  Usage();
                mpdport = atoi(*(++argv)); argc--; goto b1;
            case 'q':   op_flags |= OPT_q; if (argc < 2)  Usage();
                ownqueue = atoi(*(++argv)) != 0; argc--; goto b1;
            case 'v': versionInfo(stdout); exit(0); break;
            default: Usage();   break;
            }
    b1: argc--; argv++;
    }

    if (argc != 0 || msm < 0 || msm > 4) {
        Usage();
    }
    MSMode arg_msmode = MSMode(msm);
    
    UpMpd::Options opts;

    if (!g_configfilename.empty()) {
        g_config = new ConfSimple(g_configfilename.c_str(), 1, true);
        if (!g_config || !g_config->ok()) {
            cerr << "Could not open config: " << g_configfilename << endl;
            return 1;
        }

        string value;
        if (!(op_flags & OPT_d))
            g_config->get("logfilename", logfilename);
        if (!(op_flags & OPT_f))
            g_config->get("friendlyname", friendlyname);
        if (!(op_flags & OPT_l)) {
            loglevel = g_config->getInt("loglevel", Logger::LLINF);
        }
        if (!(op_flags & OPT_h)) {
            g_config->get("mpdhost", mpdhost);
        }
        if (!(op_flags & OPT_p)) {
            mpdport =  g_config->getInt("mpdport", 6600);
        }
        g_config->get("mpdpassword", mpdpassword);
        if (!(op_flags & OPT_q)) {
            ownqueue = g_config->getBool("ownqueue", true);
        }
        enableOH = g_config->getBool("openhome", true);
        enableAV = g_config->getBool("upnpav", true);

        if (!g_config->getBool("checkcontentformat", true)) {
            // If option is specified and 0, set nocheck flag
            opts.options |= UpMpd::upmpdNoContentFormatCheck;
        }
        ohmetapersist = g_config->getBool("ohmetapersist", true);
        if (g_config->get("pkgdatadir", g_datadir)) {
            path_catslash(g_datadir);
            iconpath = path_cat(g_datadir, "icon.png");
            if (!path_exists(iconpath)) {
                iconpath.clear();
            }
            presentationhtml = path_cat(g_datadir, "presentation.html");
        }
        g_config->get("iconpath", iconpath);
        g_config->get("presentationhtml", presentationhtml);
        g_config->get("cachedir", opts.cachedir);
        g_config->get("pidfile", pidfilename);
        if (!(op_flags & OPT_i)) {
            g_config->get("upnpiface", iface);
            if (iface.empty()) {
                g_config->get("upnpip", upnpip);
            }
        }
        if (!(op_flags & OPT_P)) {
            upport = g_config->getInt("upnpport", 0);
        }
        opts.schttpport = g_config->getInt("schttpport", 0);
        g_config->get("scplaymethod", opts.scplaymethod);
        g_config->get("sc2mpd", sc2mpdpath);
        g_config->get("screceiverstatefile", screceiverstatefile);
        if (g_config->getBool("scnosongcastsource", false)) {
            // If option is specified and 1, set nocheck flag
            opts.options |= UpMpd::upmpdNoSongcastSource;
        }
        opts.ohmetasleep = g_config->getInt("ohmetasleep", 0);
        g_config->get("ohmanufacturername", ohProductDesc.manufacturer.name);
        g_config->get("ohmanufacturerinfo", ohProductDesc.manufacturer.info);
        g_config->get("ohmanufacturerurl", ohProductDesc.manufacturer.url);
        g_config->get("ohmanufacturerimageuri", ohProductDesc.manufacturer.imageUri);
        g_config->get("ohmodelname", ohProductDesc.model.name);
        g_config->get("ohmodelinfo", ohProductDesc.model.info);
        g_config->get("ohmodelurl", ohProductDesc.model.url);
        g_config->get("ohmodelimageUri", ohProductDesc.model.imageUri);
        g_config->get("ohproductname", ohProductDesc.product.name);
        g_config->get("ohproductinfo", ohProductDesc.product.info);
        g_config->get("ohproducturl", ohProductDesc.product.url);
        g_config->get("ohproductimageuri", ohProductDesc.product.imageUri);
        g_config->get("ohproductroom", ohProductDesc.room);
        // ProductName is set to ModelName by default
        if (ohProductDesc.product.name.empty()) {
          ohProductDesc.product.name = ohProductDesc.model.name;
        }
        // ProductRoom is set to "Main Room" by default
        if (ohProductDesc.room.empty()) {
          ohProductDesc.room = "Main Room";
        }

        g_config->get("scsenderpath", senderpath);
        if (g_config->get("scsendermpdport", value))
            sendermpdport = atoi(value.c_str());

        g_lumincompat = g_config->getBool("lumincompat", false);
    } else {
        // g_configfilename is empty. Create an empty config anyway
        g_config = new ConfSimple(string(), 1, true);
        if (!g_config || !g_config->ok()) {
            cerr << "Could not create empty config\n";
            return 1;
        }
    }

    if (Logger::getTheLog(logfilename) == 0) {
        cerr << "Can't initialize log" << endl;
        return 1;
    }
    Logger::getTheLog("")->reopen(logfilename);
    Logger::getTheLog("")->setLogLevel(Logger::LogLevel(loglevel));

    // If a streaming service is enabled, we need a Media
    // Server. We let a static ContentDirectory method decide this
    // for us. The way we then implement it depends on the command
    // line option (see the enum comments near the top of the file):
    enableMediaServer = ContentDirectory::mediaServerNeeded();
    switch (arg_msmode) {
    case MSOnly:
        inprocessms = true;
        msonly = true;
        break;
    case CombinedEmbedded:
        inprocessms = true;
        msonly = false;
        msroot = false;
        break;
    case CombinedMultiDev:
        inprocessms = true;
        msonly = false;
        msroot = true;
        break;
    case RdrOnly:
    case Forked:
    default:
        inprocessms = false;
        msonly = false;
        break;
    }

    // If neither OH nor AV are enable, run as pure media server. This
    // is another way to do it besides the -m option
    if (!enableOH && !enableAV) {
        msonly = true;
        // Set inprocessms in this case ! No need to fork
        inprocessms = true;
    }
    
    if (msonly && !enableMediaServer) {
        // We used to forbid this, but it's actually ok if we're just using
        // the "mediaserver" to redirect URLs for ohcredentials/Kazoo
        ;
    }

    Pidfile pidfile(pidfilename);

    // If started by root, we use the pidfile and we will change the
    // uid (later). First part follows
    uid_t runas(0);
    gid_t runasg(0);
    struct passwd *pass = getpwnam(upmpdcliuser.c_str());
    if (pass) {
        runas = pass->pw_uid;
        runasg = pass->pw_gid;
    }
    if (geteuid() == 0) {
        if (runas == 0) {
            LOGFAT("upmpdcli won't run as root and user " << upmpdcliuser << 
                   " does not exist " << endl);
            return 1;
        }
        runas = pass->pw_uid;
        runasg = pass->pw_gid;

        pid_t pid;
        if ((pid = pidfile.open()) != 0) {
            LOGFAT("Can't open pidfile: " << pidfile.getreason() << 
                   ". Return (other pid?): " << pid << endl);
            return 1;
        }
        if (pidfile.write_pid() != 0) {
            LOGFAT("Can't write pidfile: " << pidfile.getreason() << endl);
            return 1;
        }
	if (opts.cachedir.empty())
            opts.cachedir = "/var/cache/upmpdcli";
    } else if (runas == geteuid()) {
        // Already running as upmpdcli user. There are actually 2
        // possibilities: either we were initially started as
        // upmpdcli, and we should be using ~upmpdcli/.cache as work
        // directory, or we were exec'd by a master process started as
        // root, and we should be using /var/cache/upmpdcli. We have
        // no way to decide actually, another command line option
        // would be needed. For now, behave as if exec'd by a master
        // process, because this is what happens if the default
        // package was installed. One way to fix this if this if it is
        // wrong is to set cachedir in the configuration file
        // (opts.cachedir will be non-empty then).
	if (opts.cachedir.empty())
            opts.cachedir = "/var/cache/upmpdcli";
    } else {
	if (opts.cachedir.empty())
            opts.cachedir = path_cat(path_tildexpand("~") , "/.cache/upmpdcli");
    }

    g_cachedir = opts.cachedir;
    if (!path_makepath(opts.cachedir, 0755)) {
        LOGERR("makepath("<< opts.cachedir << ") : errno : " << errno << endl);
        cerr << "Can't create " << opts.cachedir << endl;
        return 1;
    }

    string statefn = path_cat(opts.cachedir, "/upmstate");
    g_state = new ConfSimple(statefn.c_str());
    
    opts.cachefn.clear();
    if (!msonly && ohmetapersist) {
        opts.cachefn = path_cat(opts.cachedir, "/metacache");
        int fd;
        if ((fd = open(opts.cachefn.c_str(), O_CREAT|O_RDWR, 0644)) < 0) {
            LOGERR("creat("<< opts.cachefn << ") : errno : " << errno << endl);
        } else {
            close(fd);
        }
    }
    
    if ((op_flags & OPT_D)) {
        if (daemon(1, 0)) {
            LOGFAT("Daemon failed: errno " << errno << endl);
            return 1;
        }
    }

    if (geteuid() == 0) {
        // Need to rewrite pid, it may have changed with the daemon call. Also
        // adjust file ownership and access.
        pidfile.write_pid();
        if (!logfilename.empty() && logfilename.compare("stderr")) {
            if (chown(logfilename.c_str(), runas, -1) < 0 && errno != ENOENT) {
                LOGERR("chown("<<logfilename<<") : errno : " << errno << endl);
            }
        }
        if (chown(opts.cachedir.c_str(), runas, -1) != 0) {
            LOGERR("chown("<< opts.cachedir << ") : errno : " << errno << endl);
        }
        if (chown(statefn.c_str(), runas, -1) != 0) {
            LOGERR("chown("<< statefn << ") : errno : " << errno << endl);
        }
        if (!opts.cachefn.empty()) {
            if (chown(opts.cachefn.c_str(), runas, -1) != 0) {
                LOGERR("chown("<< opts.cachefn << ") : errno : " <<
                       errno << endl);
            }
        }
        if (!g_configfilename.empty()) {
            ensureconfreadable(g_configfilename.c_str(), upmpdcliuser.c_str(),
                               runas, runasg);
        }
        if (initgroups(upmpdcliuser.c_str(), runasg) < 0) {
            LOGERR("initgroup failed. Errno: " << errno << endl);
        }
        if (setuid(runas) < 0) {
            LOGFAT("Can't set my uid to " << runas << " current: " << geteuid()
                   << endl);
            return 1;
        }
#if 0
        gid_t list[100];
        int ng = getgroups(100, list);
        cerr << "GROUPS: ";
        for (int i = 0; i < ng; i++) {
            cerr << int(list[i]) << " ";
        }
        cerr << endl;
#endif
    }


/////////////////////////// Dropped root /////////////////////////////

    if (sc2mpdpath.empty()) {
        // Do we have an sc2mpd command installed (for songcast)?
        if (!ExecCmd::which("sc2mpd", sc2mpdpath))
            sc2mpdpath.clear();
    }
    if (senderpath.empty()) {
        // Do we have an scmakempdsender command installed (for
        // starting the songcast sender and its auxiliary mpd)?
        if (!ExecCmd::which("scmakempdsender", senderpath))
            senderpath.clear();
    }
    
    if (!sc2mpdpath.empty()) {
        // Check if sc2mpd is actually there
        if (access(sc2mpdpath.c_str(), X_OK|R_OK) != 0) {
            LOGERR("Specified path for sc2mpd: " << sc2mpdpath << 
                   " is not executable" << endl);
            sc2mpdpath.clear();
        }
    }

    if (!senderpath.empty()) {
        // Check that both the starter script and the mpd2sc sender
        // command are executable. We'll assume that mpd is ok
        if (access(senderpath.c_str(), X_OK|R_OK) != 0) {
            LOGERR("The specified path for the sender starter script: ["
                   << senderpath <<
                   "] is not executable, disabling the sender mode.\n");
            senderpath.clear();
        } else {
            string path;
            if (!ExecCmd::which("mpd2sc", path)) {
                LOGERR("Sender starter was specified and found but the mpd2sc "
                       "command is not found (or executable). Disabling "
                       "the sender mode.\n");
                senderpath.clear();
            }
        }
    }


    // Initialize MPD client object. Retry until it works or power fail.
    MPDCli *mpdclip = 0;
    if (!msonly) {
        int mpdretrysecs = 2;
        for (;;) {
            mpdclip = new MPDCli(mpdhost, mpdport, mpdpassword);
            if (mpdclip == 0) {
                LOGFAT("Can't allocate MPD client object" << endl);
                return 1;
            }
            if (!mpdclip->ok()) {
                LOGERR("MPD connection failed" << endl);
                delete mpdclip;
                mpdclip = 0;
                sleep(mpdretrysecs);
                mpdretrysecs = MIN(2*mpdretrysecs, 120);
            } else {
                break;
            }
        }
        const MpdStatus& mpdstat = mpdclip->getStatus();
        // Only the "special" upmpdcli 0.19.16 version has patch != 0
        g_enableL16 = mpdstat.versmajor >= 1 || mpdstat.versminor >= 20 ||
            mpdstat.verspatch >= 16; 
    }
    
        
    // Initialize libupnpp, and check health
    LibUPnP *mylib = 0;
    string hwaddr;
    int libretrysecs = 10;
    for (;;) {
        // Libupnp init fails if we're started at boot and the network
        // is not ready yet. So retry this forever
        mylib = LibUPnP::getLibUPnP(true, &hwaddr, iface, upnpip, upport);
        if (mylib) {
            break;
        }
        sleep(libretrysecs);
        libretrysecs = MIN(2*libretrysecs, 120);
    }

    if (!mylib->ok()) {
        LOGFAT("Lib init failed: " <<
               mylib->errAsString("main", mylib->getInitError()) << endl);
        return 1;
    }

    if ((cp = getenv("UPMPDCLI_UPNPLOGFILENAME"))) {
        char *cp1 = getenv("UPMPDCLI_UPNPLOGLEVEL");
        int loglevel = LibUPnP::LogLevelNone;
        if (cp1) {
            loglevel = atoi(cp1);
        }
        loglevel = loglevel < 0 ? 0: loglevel;
        if (loglevel != LibUPnP::LogLevelNone) {
            mylib->setLogFileName(cp, LibUPnP::LogLevel(loglevel));
        }
    }

    // Create unique IDs for renderer and possible media server
    UDevIds ids;
    ids.fname = friendlyname;
    ids.uuid =  LibUPnP::makeDevUUID(ids.fname, hwaddr);
    if (!g_config || !g_config->get("msfriendlyname", ids.fnameMS)) {
        ids.fnameMS = ids.fname + "-mediaserver";
    }
    ids.uuidMS = LibUPnP::makeDevUUID(ids.fnameMS, hwaddr);


    // If running as mediaserver only, make sure we don't conflict
    // with a possible renderer
    if (msonly) {
        pidfilename = pidfilename + "-ms";
    }

    opts.iconpath = iconpath;
    opts.presentationhtml = presentationhtml;
    if (ownqueue)
        opts.options |= UpMpd::upmpdOwnQueue;
    if (enableOH)
        opts.options |= UpMpd::upmpdDoOH;
    if (ohmetapersist)
        opts.options |= UpMpd::upmpdOhMetaPersist;
    if (!sc2mpdpath.empty()) {
        opts.sc2mpdpath = sc2mpdpath;
        opts.options |= UpMpd::upmpdOhReceiver;
    }
    if (!screceiverstatefile.empty()) {
        opts.screceiverstatefile = screceiverstatefile;
        int fd;
        if ((fd = open(opts.screceiverstatefile.c_str(),
                       O_CREAT|O_RDWR, 0644)) < 0) {
            LOGERR("creat(" << opts.screceiverstatefile << ") : errno : "
                   << errno << endl);
        } else {
            close(fd);
            if (geteuid() == 0 && chown(opts.screceiverstatefile.c_str(),
                                        runas, -1) != 0) {
                LOGERR("chown(" << opts.screceiverstatefile << ") : errno : "
                       << errno << endl);
            }
        }
    }
    if (!senderpath.empty()) {
        opts.options |= UpMpd::upmpdOhSenderReceiver;
        opts.senderpath = senderpath;
        opts.sendermpdport = sendermpdport;
    }

    if (!enableAV)
        opts.options |= UpMpd::upmpdNoAV;

    setupsigs();

    UpMpd *mediarenderer{nullptr};
    if (!msonly) {
        mediarenderer = new UpMpd(string("uuid:") + ids.uuid, ids.fname,
                                  ohProductDesc, mpdclip, opts);
        devs.push_back(mediarenderer);
    }

    MediaServer *mediaserver{nullptr};
    
    if (inprocessms) {
	// Create the Media Server device. If msonly is set, both
	// branches do the same thing and create a root device
	// (mediarenderer is null).
        // The multidev modified libupnp is needed for using 2 root devices
        mediaserver = new MediaServer(msroot?nullptr:mediarenderer, string("uuid:") +
                                      ids.uuidMS,ids.fnameMS, enableMediaServer);
        devs.push_back(mediaserver);
        LOGDEB("Media server event loop" << endl);
    } else if (enableMediaServer) {
        startMsOnlyProcess();
    }
    if (!msonly) {
        LOGDEB("Renderer event loop" << endl);
        mediarenderer->startloop();
    }
    if (inprocessms && enableMediaServer) {
        mediaserver->startloop();
    }
    pause();
    LOGDEB("Event loop returned" << endl);
    return 0;
}

// Read file from datadir
bool readLibFile(const std::string& name, std::string& contents)
{
    string path = path_cat(g_datadir, name);
    string reason;
    if (!file_to_string(path, contents, &reason)) {
        LOGERR("readLibFile: error reading " << name << " : " << reason << endl);
        return false;
    }
    return true;
}
