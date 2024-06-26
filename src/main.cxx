/* Copyright (C) 2015-2022 J.F.Dockes
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
#include "smallut.h"

using namespace std;
using namespace UPnPP;

const string g_upmpdcli_package_version{UPMPDCLI_VERSION};

static char *thisprog;

static int op_flags;
#define OPT_MOINS 0x1
#define OPT_D     0x2
#define OPT_c     0x4
#define OPT_m     0x8

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
    "(default, multidev|only renderer|only media|embedded|multidev)\n"
    "\n"
    ;

// We can implement a Media Server in addition to the Renderer, for
// accessing streaming services. This can happen in several modes. In
// all cases, the Media Server is only created if the configuration
// file does have parameters set for streaming services.
// - -m 0, -m 4 combined/multidev: implement the Media Server and
//   Media Renderers, as enabled by the configuration, as separate
//   root devices.
// - -m 1, RdrOnly: for the main instance: be a Renderer, do not start the
//    Media Server even if the configuration indicates it is needed
//    (this is not used in normal situations, just edit the config
//    instead!)
// - -m 2, MSOnly Media Server only.
// - -m 3, combined/embedded: implement the Media Server
//    as an embedded device. This works just fine with, for example,
//    upplay, but confuses most of the other Control Points.

enum MSMode {Default, RdrOnly, MSOnly, CombinedEmbedded, CombinedMultiDev};

static void
Usage(FILE *fp = stderr)
{
    fprintf(fp, "%s: usage:\n%s", thisprog, usage);
    fprintf(fp, "%s\n", upmpdcliVersionInfo().c_str());
    exit(1);
}


static const string dfltFriendlyName("UpMpd-%h");

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
        g_upmpdcli_package_version,                   // info
        "",                                         // url
        ""                                          // imageUri
    }
};

// Static for cleanup in sig handler.
static vector<UpnpDevice *> devs;
static MPDCli *mpdclip{nullptr};

string g_datadir;
string g_cachedir("/var/cache/upmpdcli");

// Global
string g_configfilename;
ConfSimple *g_state;
bool g_enableL16 = true;
bool g_lumincompat = false;
bool g_mainShouldExit{false};

static void onsig(int)
{
    LOGDEB("Got sig" << endl);
    g_mainShouldExit = true;
    for (auto& dev : devs) {
        // delete has a tendancy to crash (it works most of the time
        // though). Anyway, we're exiting, so just call shouldExit()
        // which will send the byebyes.
        //delete dev;
        dev->shouldExit();
    }
    if (mpdclip) {
        mpdclip->shouldExit();
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

static UpnpDevice *rootdevice{nullptr};
static MediaServer *mediaserver{nullptr};
static std::string uuidMS;
static std::string fnameMS;
static bool msroot{false};
bool startMediaServer(bool enable)
{
    if (mediaserver) {
        return true;
    }
    mediaserver = new MediaServer(
        msroot ? nullptr : rootdevice, string("uuid:")+ uuidMS, fnameMS, enable);
    if (nullptr == mediaserver)
        return false;
    auto lib = LibUPnP::getLibUPnP();

    std::string documentroot;
    if (getOptionValue("webserverdocumentroot", documentroot)) {
        if (!documentroot.empty() && path_isabsolute(documentroot)) {
            lib->setWebServerDocumentRoot(documentroot);
        }
    }
    
    devs.push_back(mediaserver);
    LOGDEB("Media server event loop" << endl);
    // msonly && !enableMediaServer is possible if we're just using
    // the "mediaserver" to redirect URLs for ohcredentials/Kazoo
    if (enable) {
        mediaserver->startloop();
    }
    return true;
}

// Configuration/option values. Command line have precedence, then configuration file, then
// environment. Command line option set values in the g_lineconfig object. g_config comes from the
// configuration file or is empty (both are non-null).
static ConfSimple *g_config;
static ConfSimple *g_lineconfig;
bool getOptionValue(const std::string& nm, std::string& value, const std::string& dflt)
{
    if (g_lineconfig->get(nm, value))
        return true;
    if (g_config->get(nm, value))
        return true;
    std::string envar = std::string("UPMPD_") + stringtoupper(nm);
    const char *cp = getenv(envar.c_str());
    if (cp) {
        value = cp;
        return true;
    }
    value = dflt;
    return false;
}
bool getBoolOptionValue(const std::string& nm, bool dflt)
{
    std::string value;
    if (!getOptionValue(nm, value) || value.empty()) {
        return dflt;
    }
    return stringToBool(value);
}
int getIntOptionValue(const std::string& nm, int dflt)
{
    std::string value;
    if (!getOptionValue(nm, value) || value.empty()) {
        return dflt;
    }
    return atoi(value.c_str());
}

int main(int argc, char *argv[])
{
    int msm = 0;
    const char *cp;

    if ((cp = getenv("UPMPD_CONFIG")))
        g_configfilename = cp;

    // Old environment variable names, this are also looked up as UPMPD_MPDHOST and UPMPD_MPDPORT
    // Kept here for compatibility, they have the lowest priority level (overriden by command line,
    // configuration file and new environment name)
    string mpdhost;
    if ((cp = getenv("UPMPD_HOST")))
        mpdhost = cp;
    int mpdport{6600};
    if ((cp = getenv("UPMPD_PORT")))
        mpdport = atoi(cp);

    g_lineconfig = new ConfSimple(0, true);
    thisprog = argv[0];
    argc--; argv++;
    while (argc > 0 && **argv == '-') {
        (*argv)++;
        if (!(**argv))
            Usage();
        while (**argv)
            switch (*(*argv)++) {
                // Options without a configuration or environment equivalent
            case 'c':   op_flags |= OPT_c; if (argc < 2)  Usage();
                g_configfilename = *(++argv); argc--; goto b1;
            case 'D':   op_flags |= OPT_D; break;
            case 'm':   op_flags |= OPT_m; if (argc < 2)  Usage();
                msm = atoi(*(++argv)); argc--; goto b1;
            case 'v': std::cout << upmpdcliVersionInfo() << "\n"; return 0;
                
                // Options superceding config and env
            case 'd': if (argc < 2)  Usage();
                g_lineconfig->set("logfilename", *(++argv)); argc--; goto b1;
            case 'f': if (argc < 2)  Usage();
                g_lineconfig->set("friendlyname", *(++argv)); argc--; goto b1;
            case 'h': if (argc < 2)  Usage();
                g_lineconfig->set("mpdhost", *(++argv)); argc--; goto b1;
            case 'i': if (argc < 2)  Usage();
                g_lineconfig->set("upnpiface",  *(++argv)); argc--; goto b1;
            case 'l': if (argc < 2)  Usage();
                g_lineconfig->set("loglevel", *(++argv)); argc--; goto b1;
            case 'O': if (argc < 2)  Usage();
                g_lineconfig->set("openhome", *(++argv)); argc--; goto b1;
            case 'P': if (argc < 2)  Usage();
                g_lineconfig->set("upnpport", *(++argv)); argc--; goto b1;
            case 'p': if (argc < 2)  Usage();
                g_lineconfig->set("mpdport", *(++argv)); argc--; goto b1;
            case 'q': if (argc < 2)  Usage();
                g_lineconfig->set("ownqueue", *(++argv)); argc--; goto b1;

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
        g_config = new ConfSimple(
            ConfSimple::CFSF_NOCASE|ConfSimple::CFSF_RO|ConfSimple::CFSF_TILDEXP, g_configfilename);
        if (!g_config || !g_config->ok()) {
            cerr << "Could not open config: " << g_configfilename << endl;
            return 1;
        }
    }  else {
        // g_configfilename is empty. Create an empty config anyway
        g_config = new ConfSimple(string(), 1, true);
        if (!g_config || !g_config->ok()) {
            cerr << "Could not create empty config\n";
            return 1;
        }
    }
        
    string value;

    string logfilename;
    getOptionValue("logfilename", logfilename);
    string friendlyname;
    getOptionValue("friendlyname", friendlyname, dfltFriendlyName);
    getOptionValue("mpdhost", mpdhost, "localhost");
    string iface;
    getOptionValue("upnpiface", iface);
    string upnpip;
    if (iface.empty()) {
        getOptionValue("upnpip", upnpip);
    }
    int loglevel = getIntOptionValue("loglevel", Logger::LLINF);
    bool enableOH = getBoolOptionValue("openhome", true);
    bool enableAV = getBoolOptionValue("upnpav", true);
    unsigned short upport = getIntOptionValue("upnpport", 0);
    if (getOptionValue("mpdport", value) && !value.empty()) {
        mpdport = atoi(value.c_str());
    }
    bool ownqueue = getBoolOptionValue("ownqueue", true);
    string mpdpassword;
    getOptionValue("mpdpassword", mpdpassword);
    opts.options |= UpMpd::upmpdNoContentFormatCheck;
    if (getOptionValue("checkcontentformat", value) && !value.empty() && stringToBool(value)) {
        // If option is specified and 1, unset nocheck flag
        opts.options &= ~UpMpd::upmpdNoContentFormatCheck;
    }
    bool ohmetapersist = getBoolOptionValue("ohmetapersist", true);

    getOptionValue("pkgdatadir", g_datadir, DATADIR);
    if (g_datadir.empty()) {
        // Built as portable install. Use the executable name to compute a likely location
        auto bindir = path_thisexecdir();
        g_datadir = path_cat(path_getfather(bindir), {"share", "upmpdcli"});
    }
    path_catslash(g_datadir);
    string iconpath = path_cat(g_datadir, "icon.png");
    if (!path_exists(iconpath)) {
        iconpath.clear();
    }
    string presentationhtml = path_cat(g_datadir, "presentation.html");

    getOptionValue("iconpath", iconpath);
    getOptionValue("presentationhtml", presentationhtml);
    getOptionValue("cachedir", opts.cachedir);
    string pidfilename;
    getOptionValue("pidfile", pidfilename, "/var/run/upmpdcli.pid");

    opts.schttpport = getIntOptionValue("schttpport", 0);
    getOptionValue("scplaymethod", opts.scplaymethod);
    // Path for the sc2mpd command, or empty
    string sc2mpdpath;
    getOptionValue("sc2mpd", sc2mpdpath);
    string screceiverstatefile;
    getOptionValue("screceiverstatefile", screceiverstatefile);
    if (getOptionValue("scnosongcastsource", value) && !value.empty() && stringToBool(value)) {
        // If option is specified and 1, set flag
        opts.options |= UpMpd::upmpdNoSongcastSource;
    }
    opts.ohmetasleep = getIntOptionValue("ohmetasleep", 0);
    getOptionValue("ohmanufacturername", ohProductDesc.manufacturer.name);
    getOptionValue("ohmanufacturerinfo", ohProductDesc.manufacturer.info);
    getOptionValue("ohmanufacturerurl", ohProductDesc.manufacturer.url);
    getOptionValue("ohmanufacturerimageuri", ohProductDesc.manufacturer.imageUri);
    getOptionValue("ohmodelname", ohProductDesc.model.name);
    getOptionValue("ohmodelinfo", ohProductDesc.model.info);
    getOptionValue("ohmodelurl", ohProductDesc.model.url);
    // imageUri was mistake, keep compat and override with imageuri if set
    getOptionValue("ohmodelimageUri", ohProductDesc.model.imageUri);
    getOptionValue("ohmodelimageuri", ohProductDesc.model.imageUri);
    getOptionValue("ohproductname", ohProductDesc.product.name);
    getOptionValue("ohproductinfo", ohProductDesc.product.info);
    getOptionValue("ohproducturl", ohProductDesc.product.url);
    getOptionValue("ohproductimageuri", ohProductDesc.product.imageUri);
    getOptionValue("ohproductroom", ohProductDesc.room);
    // ProductName is set to ModelName by default
    if (ohProductDesc.product.name.empty()) {
        ohProductDesc.product.name = ohProductDesc.model.name;
    }
    // ProductRoom is set to "Main Room" by default
    if (ohProductDesc.room.empty()) {
        ohProductDesc.room = "Main Room";
    }
    // Sender mode: path for the command creating the mpd and mpd2sc
    // processes, and port for the auxiliary mpd.
    string senderpath;
    getOptionValue("scsenderpath", senderpath);
    int sendermpdport = getIntOptionValue("scsendermpdport", 6700);
    g_lumincompat = getBoolOptionValue("lumincompat", false);


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
    bool inprocessms{false};
    bool msonly{false};
    bool enableMediaServer = ContentDirectory::mediaServerNeeded();
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
    case RdrOnly:
        inprocessms = false;
        msonly = false;
        break;
    case CombinedMultiDev:
    case Default:
    default:
        inprocessms = true;
        msonly = false;
        msroot = true;
        break;
    }

    // If neither OH nor AV are enabled, run as pure media server. This
    // is another way to do it besides the -m option
    if (!enableOH && !enableAV) {
        msonly = true;
        inprocessms = true;
    }
    
    Pidfile pidfile(pidfilename);

    // If started by root, we use the pidfile and we will change the
    // uid (later). First part follows
    string upmpdcliuser("upmpdcli");
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
                LOGERR("chown("<< opts.cachefn << ") : errno : " << errno << endl);
            }
        }
        if (!g_configfilename.empty()) {
            ensureconfreadable(g_configfilename.c_str(), upmpdcliuser.c_str(), runas, runasg);
        }

        if (initgroups(upmpdcliuser.c_str(), runasg) < 0) {
            LOGERR("initgroup failed. Errno: " << errno << endl);
        }

        if (setgid(runasg) < 0) {
            LOGSYSERR("main", "setgid", runasg);
            LOGERR("Current gid: " << getegid() << "\n");
        }
        if (setuid(runas) < 0) {
            LOGFAT("Can't set my uid to " << runas << " current: " << geteuid() << "\n");
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
            LOGERR("Specified path for sc2mpd: " << sc2mpdpath <<  " is not executable\n");
            sc2mpdpath.clear();
        }
    }

    if (!senderpath.empty()) {
        // Check that both the starter script and the mpd2sc sender
        // command are executable. We'll assume that mpd is ok
        if (access(senderpath.c_str(), X_OK|R_OK) != 0) {
            LOGERR("The specified path for the sender starter script: ["
                   << senderpath << "] is not executable, disabling the sender mode.\n");
            senderpath.clear();
        } else {
            string path;
            if (!ExecCmd::which("mpd2sc", path)) {
                LOGERR("Sender starter was specified and found but the mpd2sc "
                       "command is not found (or executable). Disabling the sender mode.\n");
                senderpath.clear();
            }
        }
    }

    // Initialise lower upnp lib logging. Static so can be done before the rest of init.
    {
        std::string upnplogfilename;
        if (getOptionValue("upnplogfilename", upnplogfilename)) {
            int upnploglevel = getIntOptionValue("upnploglevel", LibUPnP::LogLevelError);
            if (upnploglevel != LibUPnP::LogLevelNone) {
                LibUPnP::setLogFileName(upnplogfilename, LibUPnP::LogLevel(upnploglevel));
            }
        }
    }

    // Initialize libupnpp, and check health
    LibUPnP *mylib = 0;
    string hwaddr;
    int libretrysecs = 10;
    int flags = LibUPnP::UPNPPINIT_FLAG_SERVERONLY;;
    if (!g_config->getBool("useipv6", false)) {
        flags |= LibUPnP::UPNPPINIT_FLAG_NOIPV6;
    }
    for (;;) {
        // Libupnp init fails if we're started at boot and the network
        // is not ready yet. So retry this forever
        if (LibUPnP::init(flags,
                          LibUPnP::UPNPPINIT_OPTION_IFNAMES, &iface,
                          LibUPnP::UPNPPINIT_OPTION_IPV4, &upnpip,
                          LibUPnP::UPNPPINIT_OPTION_PORT, upport,
                          LibUPnP::UPNPPINIT_OPTION_END)) {
            break;
        }
        if (g_mainShouldExit) {
            return 1;
        }
        sleep(libretrysecs);
        libretrysecs = MIN(2*libretrysecs, 120);
    }
    mylib = LibUPnP::getLibUPnP();
    if (!mylib || !mylib->ok()) {
        LOGFAT("Lib init failed: " << mylib->errAsString("main", mylib->getInitError()) << endl);
        return 1;
    }
    hwaddr = mylib->hwaddr();

    friendlyname = fnameSetup(friendlyname);
    // Create unique IDs for renderer and possible media server
    if (getOptionValue("msfriendlyname", fnameMS)) {
        fnameMS = fnameSetup(fnameMS);
    } else {
        fnameMS = friendlyname + "-mediaserver";
    }
    uuidMS = LibUPnP::makeDevUUID(fnameMS, hwaddr);

    // If running as mediaserver only, make sure we don't conflict
    // with a possible renderer
    if (msonly) {
        pidfilename = pidfilename + "-ms";
    }

    setupsigs();

    if (inprocessms && !startMediaServer(enableMediaServer)) {
        LOGERR("Could not start media server\n");
        std::cerr << "Could not start media server\n";
        return 0;
    }

    UpMpd *mediarenderer{nullptr};
    if (!msonly) {
        // Initialize MPD client object. Retry until it works or power fail.
        int mpdretrysecs = 2;
        for (;;) {
            mpdclip = new MPDCli(mpdhost, mpdport, mpdpassword);
            if (mpdclip == 0) {
                LOGFAT("Can't allocate MPD client object" << endl);
                return 1;
            }
            if (!mpdclip->ok()) {
                if (g_mainShouldExit) {
                    return 1;
                }
                LOGERR("MPD connection failed" << "\n");
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
        g_enableL16 = mpdstat.versmajor >= 1 || mpdstat.versminor >= 20 || mpdstat.verspatch >= 16;
        // It appeared in the past that L16 is a major source of issues when
        // playing with win10 'cast to device', inciting it to transcode for
        // some reason, with very bad results. Can't reproduce this now. So
        // change config default to true.
        bool confl16 = getBoolOptionValue("enablel16", true);
        g_enableL16 = g_enableL16 && confl16;

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
            if ((fd = open(opts.screceiverstatefile.c_str(), O_CREAT|O_RDWR, 0644)) < 0) {
                LOGSYSERR("main", "open/create", opts.screceiverstatefile);
            } else {
                close(fd);
                if (geteuid() == 0 && chown(opts.screceiverstatefile.c_str(), runas, -1) != 0) {
                    LOGSYSERR("main", "chown", opts.screceiverstatefile);
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
        mediarenderer = new UpMpd(hwaddr, friendlyname, ohProductDesc, mpdclip, opts);
        UpMpdOpenHome *oh = mediarenderer->getoh();
        // rootdevice is only used if we implement the media server as
        // an embedded device, which is mostly for testing purposes
        // and not done by default
        if (nullptr != oh) {
            rootdevice = oh;
            devs.push_back(oh);
        }
        UpMpdMediaRenderer *av = mediarenderer->getav();
        if (nullptr != av) {
            rootdevice = av;
            devs.push_back(av);
        }
        LOGDEB("Renderer event loop" << endl);
        mediarenderer->startnoloops();
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
