/* Copyright (C) 2014-2023 J.F.Dockes
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

// This file has a number of mostly uninteresting and badly implemented small utility
// functions. This is a bit ugly, but I am not linking to Qt or glib just to get path-concatenating
// functions...

#include "config.h"

#include "upmpdutils.hxx"

#include <sys/types.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <math.h>
#include <pwd.h>
#include <grp.h>
#include <regex.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>

#ifndef O_STREAMING
#define O_STREAMING 0
#endif
#include <map>
#include <sstream>
#include <utility>
#include <vector>

#include "libupnpp/log.hxx"
#include "libupnpp/upnpplib.hxx"
#include "libupnpp/soaphelp.hxx"
#include "libupnpp/upnpavutils.hxx"
#include "libupnpp/control/cdircontent.hxx"

#include "smallut.h"
#include "main.hxx"

using namespace std;
using namespace UPnPP;
using namespace UPnPClient;

const string g_upmpdcli_package_version{UPMPDCLI_VERSION};

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

// Translate VolumeDB to MPD 0-100
int dbvaluetopercent(int dbvalue)
{
    float db = float(dbvalue) / 256.0;
    /* exp10 is not always available */
    /* 10^x = 10^(log e^x) = (e^x)^log10 = e^(x * log 10) */
    float vol = exp((db / 10) * log(10));
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
    auto it = im.find(k);
    if (it == im.end()) {
        return ns;
    } else {
        return it->second;
    }
}

unordered_map<string, string>
diffmaps(const unordered_map<string, string>& old, const unordered_map<string, string>& newer)
{
    unordered_map<string, string>  out;

    for (auto it = newer.begin(); it != newer.end(); it++) {
        auto ito = old.find(it->first);
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
        ss << " size=\"" << std::to_string(res.size) << "\"";
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

string UpSong::didl(bool noresource) const
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
    } else {
        ss << " id=\"" << "mpdid:" << mpdid;
    }
    if (!parentid.empty()) {
        ss << "\" parentID=\"" << parentid << "\"";
    } else {
        ss << "\" parentID=\"" << "0" << "\"";
    }
    ss << " restricted=\"1\" searchable=\"" <<
        (searchable ? string("1") : string("0")) << "\">" <<
        "<dc:title>" << SoapHelp::xmlQuote(title) << "</dc:title>";

    if (id.empty()) {
        ss << "<orig>mpd</orig>";
    }

    if (iscontainer) {
        UPNPXMLD(upnpClass, upnp:class, "object.container");
    } else {
        UPNPXMLD(upnpClass, upnp:class, "object.item.audioItem.musicTrack");
        UPNPXML(album, upnp:album);
        UPNPXML(tracknum, upnp:originalTrackNumber);
        if (!noresource) {
            didlPrintResource(ss, rsrc);
            if (resources) {
                for (const auto& res : *resources) {
                    didlPrintResource(ss, res);
                }
            }
        }
    }
    UPNPXML(genre, upnp:genre);
    UPNPXML(artist, dc:creator);
    UPNPXML(artist, upnp:artist);
    UPNPXML(dcdate, dc:date);
    UPNPXML(dcdescription, dc:description);
    UPNPXML(artUri, upnp:albumArtURI);

    // Raw didl emitted by whoever created us
    ss << didlfrag;

    // Our vendor stuff
    if (upmpfields && !upmpfields->empty()) {
        ss << R"(<desc nameSpace="urn:schemas-upmpdcli-com:upnpdesc" )"
            R"(xmlns:upmpd="urn:schemas-upmpdcli-com:upnpdesc">)";
        for (const auto& [key,value] : *upmpfields) {
            if (!beginswith(key, "upmpd:")) {
                LOGERR("Bad key in upmpdcli vendor block: [" << key << "]\n");
                continue;
            }
            ss << "<" << key << ">" << SoapHelp::xmlQuote(value) << "</" << key << ">";
        }
        ss << "</desc>";
    }

    ss << "</" << typetag << ">";
    LOGDEB1("UpSong::didl(): " << ss.str() << '\n');
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

string didlmake(const UpSong& song, bool noresource)
{
    return wrapDIDL(song.didl(noresource));
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
        LOGDEB0("metaSameTitle: not same title [" << tit1 << "] [" << tit2 << "]\n");
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
    
string regsub1(const string& sexp, const string& input, const string& repl)
{
    SimpleRegexp re(sexp, SimpleRegexp::SRE_NONE, 1);
    return re.simpleSub(input, repl);
}

// Make sure that the configuration file is readable by a process running as user uid group gid This
// is only called if we are started as root, before switching users. We do the minimum change: set
// the user read bit if the file belongs to upmpdcli, else change the file group to
// upmpdcli's base group and set the group read bit.
// We used to look at the upmpdcli group list and set the group read bit if the file group was part
// of the list, but this was, I now think, stupid in addition to complicated as this could end up
// setting the read permission for a wide group.
bool ensureconfreadable(const char *fn, const char *user, uid_t uid, gid_t gid)
{
    LOGDEB1("ensureconfreadable: fn " << fn << " user " << user << " uid " <<
            uid << " gid " << gid << "\n");

    struct stat st;
    if (stat(fn, &st) < 0) {
        LOGSYSERR("ensureconfreadable", "stat", fn);
        return false;
    }
    if ((st.st_mode & S_IROTH)) {
        // World-readable, we're done
        LOGDEB1("ensureconfreadable: file is world-readable\n");
        return true;
    }

    if (st.st_uid == uid) {
        LOGDEB1("ensureconfreadable: file belongs to user\n");
        // File belongs to user. Make sure that "owner read" is set. Don't complicate things. "no
        // owner read" does not make sense anyway (can always chmod).
        if (!(st.st_mode & S_IRUSR)) {
            if (chmod(fn, st.st_mode|S_IRUSR) < 0) {
                LOGSYSERR("ensureconfreadable", "chmod(st.st_mode|S_IRUSR)", fn);
                return false;
            }
        }
        return true;
    }

#ifndef __APPLE__
    // Change the file group, then make it group-readable.
    if (chown(fn, (uid_t)-1, gid) < 0) {
        LOGSYSERR("ensureconfreadable", "chown", fn);
        return false;
    }
    if (!(st.st_mode & S_IRGRP)) {
        if (chmod(fn, st.st_mode|S_IRGRP) < 0) {
            LOGSYSERR("ensureconfreadable", "chmod(st.st_mode|S_IRGRP)", fn);
            return false;
        }
    }
#endif
    return true;
}

std::string upmpdcliVersionInfo()
{
    return std::string("Upmpdcli ") + g_upmpdcli_package_version + " " + LibUPnP::versionString();
}

static std::string fnameSubst(const std::string& key)
{
    if (key == "h" || key == "H") {
        char hostname[256];
        if (gethostname(hostname, 256) < 0) {
            LOGSYSERR("fnameSetup", "gethostname", "256");
            strcpy(hostname, "unknown");
        }
        if (key == "H" && hostname[0]) {
            hostname[0] = std::toupper(hostname[0]);
        }
        return hostname;
    } else if (key == "v") {
        return upmpdcliVersionInfo();
    }
    return std::string();
}

std::string fnameSetup(const std::string in)
{
    std::string out;
    pcSubst(in, out, fnameSubst);
    return out;
}


static const std::map<std::string, std::string> lossless_mimes {
    {"audio/x-flac", "FLAC"},
    {"audio/l16", "L16"},
    {"application/flac", "FLAC"},
    {"application/x-flac", "FLAC"},
    {"audio/flac", "FLAC"},
    {"audio/x-flac", "FLAC"},
    {"audio/x-aiff", "AIFF"},
    {"audio/aif", "AIFF"},
    {"audio/aiff", "AIFF"},
    {"audio/dff", "DSD"},
    {"audio/x-dff", "DSD"},
    {"audio/dsd", "DSD"},
    {"audio/x-dsd", "DSD"},
    {"audio/dsf", "DSD"},
    {"audio/x-dsf", "DSD"},
    {"audio/wav", "WAV"},
    {"audio/x-wav", "WAV"},
    {"audio/wave", "WAV"},
    {"audio/x-monkeys-audio", "APE"},
    {"audio/x-ape", "APE"},
    {"audio/ape", "APE"},
};

static const std::map<std::string, std::string> lossy_mimes {
    {"audio/mpeg", "MP3"},
    {"application/ogg", "VORBIS"},
    {"audio/aac", "AAC"},
    {"audio/m4a", "MP4"},
    {"audio/x-m4a", "MP4"},
    {"audio/matroska", "MATROSKA"},
    {"audio/x-matroska", "MATROSKA"},
    {"audio/mp1", "MP1"},
    {"audio/mp3", "MP3"},
    {"audio/mp4", "MP4"},
    {"audio/mpeg", "MP3"},
    {"audio/x-mpeg", "MP3"},
    {"audio/ogg", "VORBIS"},
    {"audio/vorbis", "VORBIS"},
    {"audio/x-ms-wma", "WMA"},
    {"audio/x-ogg", "VORBIS"},
    {"audio/x-vorbis+ogg", "VORBIS"},
    {"audio/x-vorbis", "VORBIS"},
    {"audio/x-wavpack", "WAVPACK"},
    {"video/mp4", "MP4"},
};

bool mimeToCodec(const std::string& mime, std::string& codec, bool *lossless)
{
    int ret = true;
    auto it = lossless_mimes.find(stringtolower(mime));
    if (it != lossless_mimes.end()) {
        codec = it->second;
        *lossless = true;
        goto out;
    }
    it = lossy_mimes.find(stringtolower(mime));
    if (it != lossy_mimes.end()) {
        codec = it->second;
        *lossless = false;
        goto out;
    }

    ret = false;
    codec = "UNKNOWN";
    *lossless = false;
out:
    LOGDEB1("mimeToCodec: name " << codec << " lossless " << *lossless << "\n");
    return ret;
}

