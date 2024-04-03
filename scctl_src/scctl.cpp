/* Copyright (C) 2015 J.F.Dockes
 *       This program is free software; you can redistribute it and/or modify
 *       it under the terms of the GNU Lesser General Public License as published by
 *       the Free Software Foundation; either version 2.1 of the License, or
 *       (at your option) any later version.
 *
 *       This program is distributed in the hope that it will be useful,
 *       but WITHOUT ANY WARRANTY; without even the implied warranty of
 *       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *       GNU Lesser General Public License for more details.
 *
 *       You should have received a copy of the GNU Lesser General Public License
 *       along with this program; if not, write to the
 *       Free Software Foundation, Inc.,
 *       59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

/* 
 * Songcast UPnP controller. 
 *
 * This can list the state of all Receivers, tell
 * a Receiver to play the same URI as another one (master/slave),
 * except that the slaves don't really follow the master state, they
 * will just keep playing the same URI), or tell a Receiver to return
 * to Playlist operation.
 * 
 * To avoid encurring a discovery timeout for each op, there is a
 * server mode, in which a permanent process executes the above
 * commands, received on Unix socket, and returns the results. The
 * Unix socket name is based on the uid, so there is one per active
 * user.
 *
 * When executing any of the ops from the command line, the program
 * first tries to contact the server, and does things itself if no
 * server is found (encurring 2-3 S of timeout in the latter case).
 */
#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <getopt.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <signal.h>

#include <string>
#include <iostream>
#include <vector>
#include <algorithm>

#include "libupnpp/upnpplib.hxx"
#include "libupnpp/log.hxx"
#include "libupnpp/control/linnsongcast.hxx"
#include "libupnpp/control/discovery.hxx"

#include "../src/netcon.h"
#include "../src/smallut.h"
#include "../src/upmpdutils.hxx"

using namespace UPnPClient;
using namespace UPnPP;
using namespace std;
using namespace Songcast;

#define OPT_L 0x1
#define OPT_S 0x2
#define OPT_f 0x4
#define OPT_h 0x8
#define OPT_l 0x10
#define OPT_m 0x20
#define OPT_p 0x40
#define OPT_r 0x80
#define OPT_s 0x100
#define OPT_x 0x200
#define OPT_i 0x400
#define OPT_I 0x800
#define OPT_R 0x1000

static const string sep("||");

string showReceivers(int ops)
{
    vector<ReceiverState> vscs;
    listReceivers(vscs);
    ostringstream out;
    string dsep = (ops & OPT_m) ? sep : " ";
    
    for (auto& scs: vscs) {
        switch (scs.state) {
        case ReceiverState::SCRS_GENERROR:    out << "Error " << dsep;break;
        case ReceiverState::SCRS_NOOH:        out << "Nooh  " << dsep;break;
        case ReceiverState::SCRS_NOTRECEIVER: out << "Off   " << dsep;break;
        case ReceiverState::SCRS_STOPPED:     out << "Stop  " << dsep;break;
        case ReceiverState::SCRS_PLAYING:     out << "Play  " << dsep;break;
        }
        out << scs.nm << dsep;
        out << scs.UDN << dsep;
        if (scs.state == ReceiverState::SCRS_PLAYING) {
            out << scs.uri;
        } else if (scs.state == ReceiverState::SCRS_GENERROR) {
            out << scs.reason;
        }
        out << endl;
    }
    return out.str();
}

string showSenders(int ops)
{
    vector<SenderState> vscs;
    listSenders(vscs);
    ostringstream out;
    string dsep = (ops & OPT_m) ? sep : " ";

    for (auto& scs: vscs) {
        out << scs.nm << dsep;
        out << scs.UDN << dsep;
        out << scs.reason << dsep;
        out << scs.uri;
        out << endl;
    }
    return out.str();
}

void parseToOutput(bool ok, const vector<string>& reasons, string& out)
{
    ostringstream oss;
    vector<string> error_reasons;
    if (!reasons.empty()) {
        for (string reason : reasons) {
            if (!reason.empty()) {
                ok = false;
                error_reasons.push_back(reason);
            }
        }
    }
    if (ok) {
        oss << "Ok\n";
    } else {
        for (string error_reason : error_reasons) {
            oss << "Error: " << error_reason << "\n";
        }
    }
    out = oss.str();
    LOGDEB("out: " << out << endl);
}

int dosomething(int opflags, const vector<string>& args, string& out)
{
    if (opflags & OPT_l) {
        out = showReceivers(opflags);
    } else if (opflags & OPT_L) {
        out = showSenders(opflags);
    } else if (opflags & OPT_r) {
        if (args.size() < 2)
            return 1;
#ifdef HAVE_WITHSTATUS_IN_LINN
        vector<string> reasons;
        bool ok = setReceiversFromSenderWithStatus(args[0],
                                vector<string>(args.begin() + 1, args.end()),
                                reasons);
        parseToOutput(ok, reasons, out);
#else
        setReceiversFromSender(args[0], vector<string>(args.begin() + 1,
                                                       args.end()));
#endif
    } else if (opflags & OPT_s) {
        if (args.size() < 2)
            return 1;
#ifdef HAVE_WITHSTATUS_IN_LINN
        vector<string> reasons;
        bool ok = setReceiversFromReceiverWithStatus(args[0],
                                vector<string>(args.begin() + 1, args.end()),
                                reasons);
        parseToOutput(ok, reasons, out);
#else
        setReceiversFromReceiver(args[0], vector<string>(args.begin() + 1,
                                                         args.end()));
#endif
    } else if (opflags & OPT_x) {
        if (args.size() < 1)
            return 1;
#ifdef HAVE_WITHSTATUS_IN_LINN
        vector<string> reasons;
        bool ok = stopReceiversWithStatus(args, reasons);
        parseToOutput(ok, reasons, out);
#else
        stopReceivers(args);
#endif
#ifdef HAVE_SETSOURCEINDEX_IN_LINN
    } else if ((opflags & OPT_i)) {
        if (args.size() < 2)
            return 1;
        bool ok = setSourceIndex(args[0], std::stoi(args[1]));
        vector<string> reasons;
        parseToOutput(ok, reasons, out);
    } else if ((opflags & OPT_I)) {
        if (args.size() < 2)
            return 1;
        bool ok = setSourceIndexByName(args[0], args[1]);
        vector<string> reasons;
        parseToOutput(ok, reasons, out);
#endif /* HAVE_SETRECEIVERSPLAYING_IN_LINN */
#ifdef HAVE_SETRECEIVERSPLAYING_IN_LINN
    } else if (opflags & OPT_R) {
        if (args.size() < 1)
            return 1;
#ifdef HAVE_WITHSTATUS_IN_LINN
        vector<string> reasons;
        bool ok = setReceiversPlayingWithStatus(args, reasons);
        parseToOutput(ok, reasons, out);
#else
        setReceiversPlaying(args);
#endif /* HAVE_WITHSTATUS_IN_LINN */
#endif /* HAVE_SETRECEIVERSPLAYING_IN_LINN */
    }
    return 0;
}

static char *thisprog;
static char usage [] =
" -l List renderers with Songcast Receiver capability\n"
" -L List Songcast Senders\n"
"   -m : for above modes: use parseable format\n"
"For the following options the renderers can be designated by their \n"
"uid (safer) or friendly name\n"
#ifdef HAVE_SETSOURCEINDEX_IN_LINN
" -i <renderer> i : set source index\n"
" -I <renderer> name : set source index by name\n"
#endif
" -s <master> <slave> [slave ...] : Set up the slaves renderers as Songcast\n"
"    Receivers and make them play from the same uri as the master receiver\n"
" -x <renderer> [renderer ...] Reset renderers from Songcast to Playlist\n"
" -r <sender> <renderer> <renderer> : set up the renderers in Receiver mode\n"
"    playing data from the sender. This is like -s but we get the uri from \n"
"    the sender instead of a sibling receiver\n"
#ifdef HAVE_SETRECEIVERSPLAYING_IN_LINN
" -R <renderer> [renderer ...] Set renderers to Songcast receiver source\n"
"    without looking for the Songcast sender first (requires usage of\n"
"    screceiverstatefile in the configfile).\n"
#endif
" -S Run as server\n"
" -f If no server is found, scctl will fork one after performing the\n"
"    requested command, so that the next execution will not have to wait for\n"
"    the discovery timeout.\n"
" -h This help.\n"
"\n"
"Renderers may be designated by friendly name or UUID\n"
"\n"
;

static int   op_flags;

static void
Usage(FILE *fp = stderr)
{
    fprintf(fp, "%s: usage:\n%s", thisprog, usage);
    exit(1);
}

int runserver();
bool tryserver(int flags, int argc, char *argv[]);

int main(int argc, char *argv[])
{
    thisprog = argv[0];

    int ret;
    while ((ret = getopt(argc, argv, "fhmLlrRsSxiI")) != -1) {
        switch (ret) {
        case 'f': op_flags |= OPT_f; break;
        case 'h': Usage(stdout); break;
        case 'l': op_flags |= OPT_l; break;
        case 'L': op_flags |= OPT_L; break;
        case 'm': op_flags |= OPT_m; break;
        case 'r': op_flags |= OPT_r; break;
        case 'R': op_flags |= OPT_R; break;
        case 's': op_flags |= OPT_s; break;
        case 'S': op_flags |= OPT_S; break;
        case 'x': op_flags |= OPT_x; break;
        case 'i': op_flags |= OPT_i; break;
        case 'I': op_flags |= OPT_I; break;
        default: Usage();
        }
    }

    // If we're not to become a server, try to contact one to avoid
    // the discovery timeout
    if (!(op_flags & OPT_S) && tryserver(op_flags, argc - optind, 
                                         &argv[optind])) {
        exit(0);
    }

    // At least one action needed. 
    if ((op_flags & ~(OPT_f|OPT_m)) == 0)
        Usage();

    // Logger::getTheLog("stderr")->setLogLevel(Logger::LLDEB0);

    LibUPnP *mylib = LibUPnP::getLibUPnP();
    if (!mylib) {
        cerr << "Can't get LibUPnP" << endl;
        return 1;
    }
    if (!mylib->ok()) {
        cerr << "Lib init failed: " <<
            mylib->errAsString("main", mylib->getInitError()) << endl;
        return 1;
    }
    // mylib->setLogFileName("/tmp/libupnp.log");

    vector<string> args;
    while (optind < argc) {
        args.push_back(argv[optind++]);
    }

    ret = 0;
    if ((op_flags & OPT_S)) {
        ret = runserver();
        goto exitprog;
    } else {
        string out;
        if (dosomething(op_flags, args, out)) {
            Usage();
        }
        cout << out;
    }

    // If we get here, we have executed a local command. If -f is set,
    // fork and run the server code so that a next execution will use
    // this instead (and not incur the discovery timeout)
    if ((op_flags & OPT_f)) {
        // Father exits, son process becomes server
        if (daemon(0, 0) == 0)
            runserver();
    }
exitprog:
    UPnPDeviceDirectory *dir = UPnPDeviceDirectory::getTheDir();
    if (dir) {
        dir->terminate();
    }
    return ret;
}


// The Unix socket path which we use for client-server operation
bool sockname(string& nm)
{
    char buf[80];
    sprintf(buf, "/tmp/scctl%d", int(getuid()));
    if (access(buf, 0) < 0) {
        if (mkdir(buf, 0700)) {
            perror("mkdir");
            return false;
        }
    }
    sprintf(buf, "/tmp/scctl%d/sock", int(getuid()));
    nm = buf;
    return true;
}


// Try to have an op run in server process (to avoid the discovery
// timeout).
bool tryserver(const string& cmd)
{
    fflush(stdout);

    NetconCli *clicon = new NetconCli();
    NetconP con(clicon);
    if (!con) {
        cerr << "tryserver: new NetconCli failed\n";
        return false;
    }
    
    string snm;
    if (!sockname(snm)) {
        return false;
    }
    if (clicon->openconn(snm.c_str(), (unsigned int)0) < 0) {
        // Server not running case, no big deal
        LOGDEB("openconn(" << snm << ") failed (ok: server not running)\n");
        return false;
    }

    if (clicon->send(cmd.c_str(), cmd.size() + 1) < 0) {
        cerr << "Send failed\n";
        return false;
    }
    char buf[1024];
    for (;;) {
        int cnt = clicon->receive(buf, 1024);
        if (cnt < 0) {
            perror("receive:");
            return false;
        }
        if (cnt == 0)
            break;
        if (write(1, buf, cnt) != cnt) {
            perror("write");
            return false;
        }
    }
    return true;
}

static vector<string> argvtov(char *argv[])
{
    vector<string> out;
    while (argv && *argv) {
        out.push_back(*argv++);
    }
    return out;
}

bool tryserver(int opflags, int argc, char *argv[])
{
    char opts[30];
    sprintf(opts, "0x%x", opflags);
    string cmd(opts);
    cmd += " ";
    vector<string> va = argvtov(argv);
    cmd += stringsToString(va);
    cmd += "\n";
    return tryserver(cmd);
}


// Listening endpoint for the server. For each connection, one request
// is served immediately and the connection is closed.
class MyNetconServLis : public NetconServLis {
public:
protected:
    int cando(Netcon::Event reason);
};

// Server worker method. Called for each connection, does one thing
// and returns.
int MyNetconServLis::cando(Netcon::Event reason)
{
    NetconServCon *con = accept();
    if (con == 0) {
        LOGERR("scctl server: accept() failed\n");
        return 1;
    }
    std::unique_ptr<Netcon> conhold(con);

    // Get command
    string line;
    {
        const int LL(10240);
        char buf[LL];
        if  (con->getline(buf, LL, 2) <= 0) {
            LOGERR("scctl: server: getline() failed\n");
            return 1;
        }
        line = buf;
    }
    trimstring(line, " \n");
    LOGDEB1("scctl: server: got cmd: " << line << endl);

    vector<string> args;
    stringToStrings(line, args);
    if (args.empty()) {
        return 1;
    }

    int opflags = strtoul(args[0].c_str(), 0, 0);
    args.erase(args.begin());
    string out;
    if (opflags & OPT_p) {
        // ping
        out = "Ok\n";
    } else {
        dosomething(opflags, args, out);
    }

    if (con->send(out.c_str(), out.size(), 0) < 0) {
        LOGERR("scctl: server: send() failed\n");
        return 1;
    }

    return 1;
}

// Server init routine

int runserver()
{
    string snm;
    if (!sockname(snm)) {
        return 1;
    }

    // Check if already running, else clean up socket
    if (access(snm.c_str(), 0) == 0) {
        
        if(tryserver("-p\n")) {
            // Already running
            return 0;
        }
        if (unlink(snm.c_str()) < 0) {
            perror("unlink");
            return 1;
        }
    }

    // Run
    signal(SIGCHLD, SIG_IGN);
    signal(SIGPIPE, SIG_IGN);

    // Initialize lib at once, will be ready when we need it
    showReceivers(0);

    MyNetconServLis *servlis = new MyNetconServLis();
    if (servlis == 0) {
        LOGERR("scctl: server: new NetconServLis failed\n");
        return 1;
    }
    if (servlis->openservice(snm.c_str()) < 0) {
        LOGERR("scctl: server: openservice(" << snm << ") failed\n");
        return 1;
    }

    SelectLoop myloop;
    myloop.addselcon(NetconP(servlis), Netcon::NETCONPOLL_READ);

    LOGDEB("scctl: server: openservice(" << snm << ") Ok\n");

    if (myloop.doLoop() < 0) {
        LOGERR("scctl: server: selectloop failed\n");
        return 1;
    }
    return 0;
}
