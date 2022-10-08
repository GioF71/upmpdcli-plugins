/* Copyright (C) 2016-2020 J.F.Dockes
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
#include "protocolinfo.hxx"

#include "libupnpp/log.hxx"
#include "libupnpp/upnpavutils.hxx"

#include "main.hxx"
#include "smallut.h"
#include "pathut.h"
#include "upmpdutils.hxx"

#include <string>

#include <stdlib.h>
#include <time.h>
#include <sys/stat.h>

using namespace std;

class Protocolinfo::Internal {
public:
    string prototext;
    unordered_set<string> supportedformats;
    bool ok{false};
    time_t mtime{0};
    int64_t  sz{0};
    
    bool maybeUpdate();
};

static Protocolinfo *theProto;

Protocolinfo *Protocolinfo::the()
{
    if (theProto == 0)
        theProto = new Protocolinfo();
    if (theProto && !theProto->ok()) {
        delete theProto;
        theProto = 0;
        return 0;
    }
    return theProto;
}

Protocolinfo::Protocolinfo()
{
    m = new Internal();
    if (!m) {
        LOGFAT("Protocolinfo: out of mem\n");
        abort();
    }
    m->maybeUpdate();
}

bool Protocolinfo::ok()
{
    return m && m->ok;
}

const string& Protocolinfo::gettext()
{
    m->maybeUpdate();
    return m->prototext;
}

const std::unordered_set<std::string>& Protocolinfo::getsupportedformats()
{
    m->maybeUpdate();
    return m->supportedformats;
}

/** 
 * Read protocol info file. This contains the connection manager
 * protocol info data
 *
 * We strip white-space from beginning/ends of lines, and allow
 * #-started comments (on a line alone only, comments after data not allowed).
 */
static bool read_protocolinfo(const string& fn, bool enableL16, string& out)
{
    LOGDEB1("read_protocolinfo: fn " << fn << "\n");
    out.clear();
    ifstream input;
    input.open(fn, ios::in);
    if (!input.is_open()) {
        LOGERR("read_protocolinfo: open failed: " << fn << "\n");
        return false;
    }        
    bool eof = false;
    for (;;) {
        string line;
        getline(input, line);
        if (!input.good()) {
            if (input.bad()) {
                LOGERR("read_protocolinfo: read error: " << fn << "\n");
                return false;
            }
            // Must be eof ? But maybe we have a partial line which
            // must be processed. This happens if the last line before
            // eof ends with a backslash, or there is no final \n
            eof = true;
        }
        trimstring(line, " \t\n\r,");
        if (!line.empty()) {
            if (enableL16 && line[0] == '@') {
                line = regsub1("@ENABLEL16@", line, "");
            } else {
                line = regsub1("@ENABLEL16@", line, "#");
            }
            if (line[0] == '#')
                continue;

            out += line + ',';
        }
        if (eof) 
            break;
    }
    trimstring(out, ",");
    LOGDEB0("read_protocolinfo data: [" << out << "]\n");
    return true;
}

bool Protocolinfo::Internal::maybeUpdate()
{
    string protofile(path_cat(g_datadir, "protocolinfo.txt"));
    struct stat st;
    if (::stat(protofile.c_str(), &st) != 0) {
        LOGFAT("protocolinfo: stat() failed for " << protofile << endl);
        return ok=false;
    }
    if (mtime == st.st_mtime && sz == st.st_size) {
        return true;
    }
    if (!read_protocolinfo(protofile, g_enableL16, prototext)) {
        LOGFAT("Failed reading protocol info from " << protofile << endl);
        return ok=false;
    }

    vector<UPnPP::ProtocolinfoEntry> vpe;
    parseProtocolInfo(prototext, vpe);
    for (const auto& it : vpe) {
        supportedformats.insert(it.contentFormat);
    }
    mtime = st.st_mtime;
    sz = st.st_size;
    return ok=true;
}
