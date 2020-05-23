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

//
// This file has a number of mostly uninteresting and badly
// implemented small utility functions. This is a bit ugly, but I am
// not linking to Qt or glib just to get path-concatenating
// functions...

#include "upmpdutils.hxx"

#include <sys/types.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <pwd.h>
#include <grp.h>
#include <regex.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>

#ifndef O_STREAMING
#define O_STREAMING 0
#endif
#include <fstream>
#include <sstream>
#include <utility>
#include <vector>

#include "libupnpp/log.hxx"
#include "libupnpp/soaphelp.hxx"
#include "libupnpp/upnpavutils.hxx"
#include "libupnpp/control/cdircontent.hxx"

#include "mpdcli.hxx"
#include "smallut.h"
#include "pathut.h"
#include "conftree.h"

using namespace std;
using namespace UPnPP;
using namespace UPnPClient;

// Translate 0-100% MPD volume to UPnP VolumeDB: we do db upnp-encoded
// values from -10240 (0%) to 0 (100%)
int percentodbvalue(int value)
{
    int dbvalue;
    if (value == 0) {
        dbvalue = -10240;
    } else {
        float ratio = float(value) * value / 10000.0;
        float db = 10 * log10(ratio);
        dbvalue = int(256 * db);
    }
    return dbvalue;
}

#ifdef __APPLE__
#define exp10 __exp10
#endif
#ifdef __UCLIBC__
/* 10^x = 10^(log e^x) = (e^x)^log10 = e^(x * log 10) */
#define exp10(x) (exp((x) * log(10)))
#endif /* __UCLIBC__ */

// Translate VolumeDB to MPD 0-100
int dbvaluetopercent(int dbvalue)
{
    float db = float(dbvalue) / 256.0;
    float vol = exp10(db / 10);
    int percent = floor(sqrt(vol * 10000.0));
    if (percent < 0) {
        percent = 0;
    }
    if (percent > 100) {
        percent = 100;
    }
    return percent;
}

// Get from ssl unordered_map, return empty string for non-existing
// key (so this only works for data where this behaviour makes sense).
const string& mapget(const unordered_map<string, string>& im, const string& k)
{
    static string ns; // null string
    unordered_map<string, string>::const_iterator it = im.find(k);
    if (it == im.end()) {
        return ns;
    } else {
        return it->second;
    }
}

unordered_map<string, string>
diffmaps(const unordered_map<string, string>& old,
         const unordered_map<string, string>& newer)
{
    unordered_map<string, string>  out;

    for (unordered_map<string, string>::const_iterator it = newer.begin();
         it != newer.end(); it++) {
        unordered_map<string, string>::const_iterator ito = old.find(it->first);
        if (ito == old.end() || ito->second.compare(it->second)) {
            out[it->first] = it->second;
        }
    }
    return out;
}


#define UPNPXML(FLD, TAG)                                               \
    if (!FLD.empty()) {                                                 \
        ss << "<" #TAG ">" << SoapHelp::xmlQuote(FLD) << "</" #TAG ">"; \
    }
#define UPNPXMLD(FLD, TAG, DEF)                                         \
    if (!FLD.empty()) {                                                 \
        ss << "<" #TAG ">" << SoapHelp::xmlQuote(FLD) << "</" #TAG ">"; \
    } else {                                                            \
        ss << "<" #TAG ">" << SoapHelp::xmlQuote(DEF) << "</" #TAG ">"; \
    }

static void didlPrintResource(ostringstream& ss, const UpSong::Res& res) {
    ss << "<res";
    if (res.duration_secs) {
        ss << " duration=\"" << upnpduration(res.duration_secs * 1000) << "\"";
    }
    if (res.size) {
        ss << " size=\"" << lltodecstr(res.size) << "\"";
    }
    if (res.bitrate) {
        ss << " bitrate=\"" << SoapHelp::i2s(res.bitrate) << "\"";
    }
    if (res.samplefreq) {
        ss << " sampleFrequency=\"" << SoapHelp::i2s(res.samplefreq) << "\"";
    }
    if (res.bitsPerSample) {
        ss << " bitsPerSample=\"" << SoapHelp::i2s(res.bitsPerSample) << "\"";
    }            
    if (res.channels) {
        ss << " nrAudioChannels=\"" << SoapHelp::i2s(res.channels) << "\"";
    }
    if (!res.mime.empty()) {
        ss << " protocolInfo=\"http-get:*:" << res.mime << ":* " << "\"";
    }
    ss << ">" << SoapHelp::xmlQuote(res.uri) << "</res>";
}

string UpSong::didl() const
{
    ostringstream ss;
    string typetag;
    if (iscontainer) {
        typetag = "container";
    } else {
        typetag = "item";
    }
    ss << "<" << typetag;
    if (!id.empty()) {
        ss << " id=\"" << id;
    }
    if (!parentid.empty()) {
        ss << "\" parentID=\"" << parentid << "\"";
    }
    ss << " restricted=\"1\" searchable=\"" <<
        (searchable ? string("1") : string("0")) << "\">" <<
        "<dc:title>" << SoapHelp::xmlQuote(title) << "</dc:title>";

    if (id.empty()) {
        ss << "<orig>mpd</orig>";
    }

    if (iscontainer) {
        UPNPXMLD(upnpClass, upnp:class, "object.container");
        // tracknum is reused for annotations for containers
        ss << (tracknum.empty() ? string() :
               string("<upnp:userAnnotation>" + SoapHelp::xmlQuote(tracknum) +
                      "</upnp:userAnnotation>"));
        
    } else {
        UPNPXMLD(upnpClass, upnp:class, "object.item.audioItem.musicTrack");
        UPNPXML(album, upnp:album);
        UPNPXML(tracknum, upnp:originalTrackNumber);
        didlPrintResource(ss, rsrc);
        for (const auto& res : resources) {
            didlPrintResource(ss, res);
        }
    }
    UPNPXML(genre, upnp:genre);
    UPNPXML(artist, dc:creator);
    UPNPXML(artist, upnp:artist);
    UPNPXML(date, dc:date);
    UPNPXML(artUri, upnp:albumArtURI);
    ss << "</" << typetag << ">";
    LOGDEB1("UpSong::didl(): " << ss.str() << endl);
    return ss.str();
}

const string& headDIDL()
{
    static const string head(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
        "<DIDL-Lite xmlns:dc=\"http://purl.org/dc/elements/1.1/\" "
        "xmlns:upnp=\"urn:schemas-upnp-org:metadata-1-0/upnp/\" "
        "xmlns=\"urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/\" "
        "xmlns:dlna=\"urn:schemas-dlna-org:metadata-1-0/\">");
    return head;
}

const string& tailDIDL()
{
    static const string tail("</DIDL-Lite>");
    return tail;
}
    
string wrapDIDL(const std::string& data)
{
    return headDIDL() + data + tailDIDL();
}

string didlmake(const UpSong& song)
{
    return wrapDIDL(song.didl());
}

bool dirObjToUpSong(const UPnPDirObject& dobj, UpSong *ups)
{
    ups->artist = dobj.getprop("upnp:artist");
    ups->album = dobj.getprop("upnp:album");
    ups->title = dobj.m_title;
    string stmp;
    dobj.getrprop(0, "duration", stmp);
    if (!stmp.empty()) {
        ups->rsrc.duration_secs = upnpdurationtos(stmp);
    } else {
        ups->rsrc.duration_secs = 0;
    }
    ups->tracknum = dobj.getprop("upnp:originalTrackNumber");
    return true;
}

void noMetaUpSong(UpSong *ups)
{
    ups->artist = "Unknown";
    ups->album = "Unknown";
    ups->title = "Unknown (streaming?)";
    ups->rsrc.duration_secs = 0;
    ups->tracknum = "0";
    return;
}

bool metaSameTitle(const string& meta1, const string& meta2)
{
    UPnPDirContent dirc1, dirc2;
    if (!dirc1.parse(meta1) || dirc1.m_items.size() == 0) {
        LOGDEB0("metaSameTitle: could not parse meta1 [" << meta1 << "]\n");
        return false;
    }
    if (!dirc2.parse(meta2) || dirc2.m_items.size() == 0) {
        LOGDEB0("metaSameTitle: could not parse meta2 [" << meta2 << "]\n");
        return false;
    }
    const string& tit1(dirc1.m_items[0].m_title);
    const string& tit2(dirc2.m_items[0].m_title);
    if (tit1.compare(tit2)) {
        LOGDEB0("metaSameTitle: not same title [" << tit1 << "] [" <<
                tit2 << "]\n");
        return false;
    }
    LOGDEB2("metaSameTitle: same\n");
    return true;
}

bool uMetaToUpSong(const string& metadata, UpSong *ups)
{
    if (ups == 0) {
        return false;
    }

    UPnPDirContent dirc;
    if (!dirc.parse(metadata) || dirc.m_items.size() == 0) {
        return false;
    }
    return dirObjToUpSong(*dirc.m_items.begin(), ups);
}
    
// Substitute regular expression
// The c++11 regex package does not seem really ready from prime time
// (Tried on gcc + libstdc++ 4.7.2-5 on Debian, with little
// joy). So...:
string regsub1(const string& sexp, const string& input, const string& repl)
{
    regex_t expr;
    int err;
    const int ERRSIZE = 200;
    char errbuf[ERRSIZE + 1];
    regmatch_t pmatch[10];

    if ((err = regcomp(&expr, sexp.c_str(), REG_EXTENDED))) {
        regerror(err, &expr, errbuf, ERRSIZE);
        LOGERR("upmpd: regsub1: regcomp() failed: " << errbuf << endl);
        return string();
    }

    if ((err = regexec(&expr, input.c_str(), 10, pmatch, 0))) {
        // regerror(err, &expr, errbuf, ERRSIZE);
        //LOGDEB("upmpd: regsub1: regexec(" << sexp << ") failed: "
        //<<  errbuf << endl);
        regfree(&expr);
        return input;
    }
    if (pmatch[0].rm_so == -1) {
        // No match
        regfree(&expr);
        return input;
    }
    string out = input.substr(0, pmatch[0].rm_so);
    out += repl;
    out += input.substr(pmatch[0].rm_eo);
    regfree(&expr);
    return out;
}

// Make sure that the configuration file is readable by user upmpdcli.
// This is only called if we are started as root, before switching
// users.  We do the minimum change: set the user read bit if the
// file belongs to it, else set the group read bit if it belongs to
// one of the user groups, else, have to chrgp it.
bool ensureconfreadable(const char *fn, const char *user, uid_t uid,
                        gid_t gid)
{
    LOGDEB1("ensureconfreadable: fn " << fn << " user " << user << " uid " <<
            uid << " gid " << gid << endl);

    struct stat st;
    if (stat(fn, &st) < 0) {
        LOGERR("ensureconfreadable: can't stat " << fn << " errno " <<
               errno << endl);
        return false;
    }
    if ((st.st_mode & S_IROTH)) {
        // World-readable, we're done
        LOGDEB1("ensureconfreadable: file is world-readable\n");
        return true;
    }

    if (st.st_uid == uid) {
        LOGDEB1("ensureconfreadable: file belongs to user\n");
        // File belongs to user. Make sure that "owner read" is
        // set. Don't complicate things. "no owner read" does not make
        // sense anyway (can always chmod).
        if (!(st.st_mode & S_IRUSR)) {
            if (chmod(fn, st.st_mode|S_IRUSR) < 0) {
                LOGERR("ensureconfreadable: chmod(st.st_mode|S_IRUSR) failed."
                       " errno " << errno << endl);
                return false;
            }
        }
        return true;
    }

#ifndef __APPLE__
    // Deal with groups.
    // Note that 1000 is arbitrary, we should call with 0 to retrieve
    // the actual size and allocate accordingly then recall
    int ngroups{1000};
    gid_t groups[1000];
    if (getgrouplist(user, gid, groups, &ngroups) < 0) {
        LOGERR("ensureconfreadable: getgrouplist failed for " << user << endl);
        return false;
    }

    // Check if file belongs to one of our groups. Make it
    // group-readable if so. Determine our lowest group while we're at
    // it.
    unsigned int mingroup{UINT_MAX};
    for (int i = 0;i < ngroups; i++) {
        if (groups[i] < mingroup) {
            mingroup = groups[i];
        }
        if (st.st_gid == groups[i]) {
            if (!(st.st_mode & S_IRGRP)) {
                if (chmod(fn, st.st_mode|S_IRGRP) < 0) {
                    LOGERR("ensureconfreadable: chmod(st.st_mode|S_IRGRP) "
                           "failed.  errno " << errno << endl);
                    return false;
                }
            }
            return true;
        }
    }
    
    // File does not belong to any of our groups. We already checked
    // that "other read" was not set. Have to change the file
    // group. Note that we could also add the file group to our group
    // list, but this seems like a worse idea (making us a setgid
    // executable in practise).
    if (chown(fn, (uid_t)-1, mingroup) < 0) {
        LOGERR("ensureconfreadable: chown(" << fn << "-1, " << mingroup <<") "
               "failed. errno " << errno << endl);
        return false;
    }
    if (!(st.st_mode & S_IRGRP)) {
        if (chmod(fn, st.st_mode|S_IRGRP) < 0) {
            LOGERR("ensureconfreadable: chmod(st.st_mode|S_IRGRP) "
                   "failed.  errno " << errno << endl);
            return false;
        }
    }
#endif
    return true;
}
