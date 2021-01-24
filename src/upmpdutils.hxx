/* Copyright (C) 2014-2020 J.F.Dockes
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
#ifndef _UPMPDUTILS_H_X_INCLUDED_
#define _UPMPDUTILS_H_X_INCLUDED_

#include <string>
#include <unordered_map>
#include <vector>

#include <unistd.h>

namespace UPnPClient {
    class UPnPDirObject;
};

// This was originally purely a translation of data from mpd. Extended
// to general purpose track/container descriptor
class UpSong {
public:
    UpSong() {}
    void clear() {
        *this = UpSong();
    }
    std::string id;
    std::string parentid;
    std::string name; // only set for radios apparently. 
    std::string artist; 
    std::string album;
    std::string title;
    std::string tracknum; // Reused as annot for containers
    std::string genre;
    std::string artUri;
    std::string upnpClass;
    std::string date;

    // The entries in the following struct have misc uses, but as a
    // group, they describe an UPnP resource (for converting to DIDL
    // for sending to CP).
    struct Res {
        std::string uri;
        int duration_secs{0};
        int64_t size{0};
        int bitrate{0};
        int samplefreq{0};
        int bitsPerSample{0};
        int channels{0};
        std::string mime;
    };
    // Base data: all track upsongs have data in there
    Res rsrc;
    // Additional resources for other formats etc. for the same
    // track. Only used by the media server, and usually empty.
    std::vector<Res> resources;
    
    int mpdid{0};
    bool iscontainer{false};
    bool searchable{false};

    std::string dump() const {
        return std::string("class [" + upnpClass + "] Artist [" + artist +
                           "] Album [" +  album + " Title [" + title +
                           "] Tno [" + tracknum + "] Uri [" + rsrc.uri + "]");
    }
    // Format to DIDL fragment 
    std::string didl(bool nobitrate = false) const;

    static UpSong container(const std::string& id, const std::string& pid,
                            const std::string& title, bool sable = true,
                            const std::string& annot = std::string()) {
        UpSong song;
        song.iscontainer = true;
        song.id = id;
        song.parentid = pid;
        song.title = title;
        song.searchable = sable;
        song.tracknum = annot;
        return song;
    }
    static UpSong item(const std::string& id, const std::string& parentid,
                       const std::string& title) {
        UpSong song;
        song.iscontainer = false;
        song.id = id;
        song.parentid = parentid;
        song.title = title;
        return song;
    }
};

// Stupid string comparison of the dc:title part
bool metaSameTitle(const std::string& meta1, const std::string& meta2);

// Convert between db value to percent values (Get/Set Volume and VolumeDb)
extern int percentodbvalue(int value);
extern int dbvaluetopercent(int dbvalue);

// Return mapvalue or null strings, for maps where absent entry and
// null data are equivalent
extern const std::string& mapget(
    const std::unordered_map<std::string, std::string>& im, 
    const std::string& k);

// Format a didl fragment from MPD status data. Used by the renderer
extern std::string didlmake(const UpSong& song, bool noresource = false);

// Wrap DIDL entries in header / trailer
extern const std::string& headDIDL();
extern const std::string& tailDIDL();
extern std::string wrapDIDL(const std::string& data);

// Convert UPnP metadata to UpSong for mpdcli to use. Parse string as
// didl fragment, and use dirObjToUpSong() to convert the first item.
extern bool uMetaToUpSong(const std::string&, UpSong *ups);
// Convert UPnP content directory entry object to UpSong
bool dirObjToUpSong(const UPnPClient::UPnPDirObject& dobj, UpSong *ups);
// upsong with "Unknown" or such everywhere for when we get no metadata
void noMetaUpSong(UpSong *ups);

// Replace the first occurrence of regexp. cxx11 regex does not work
// that well yet...
extern std::string regsub1(const std::string& sexp, const std::string& input, 
                           const std::string& repl);

// Return map with "newer" elements which differ from "old".  Old may
// have fewer elts than "newer" (e.g. may be empty), we use the
// "newer" entries for diffing. This is used to compute state changes.
extern std::unordered_map<std::string, std::string> 
diffmaps(const std::unordered_map<std::string, std::string>& old,
         const std::unordered_map<std::string, std::string>& newer);

#define UPMPD_UNUSED(X) (void)(X)

extern bool ensureconfreadable(const char *fn, const char *user, uid_t uid,
                               gid_t gid);

#endif /* _UPMPDUTILS_H_X_INCLUDED_ */
