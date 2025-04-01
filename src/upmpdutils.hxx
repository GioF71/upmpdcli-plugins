/* Copyright (C) 2014-2022 J.F.Dockes
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

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include <unistd.h>

namespace UPnPClient {
    class UPnPDirObject;
};

// This base class exists just that we can implement a copy constructor without listing all the
// copyable fields (just use the base class constructor instead).
class UpSongBase {
public:
    UpSongBase() {}
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
    // Date as iso string YYYY-MM-dd. dc:date in UPnP data.
    std::string dcdate;
    std::string dcdescription;

    // A raw didl fragment to be added to the output when converting to DIDL. For Media Server
    // modules which know more than we do (e.g. uprcl)
    std::string didlfrag;

    // The entries in the following struct have misc uses, but as a
    // group, they describe an UPnP resource (for converting to DIDL
    // for sending to CP).
    struct Res {
        std::string uri;
        std::string mime;
        int64_t size{0};
        uint32_t duration_secs{0};
        uint32_t bitrate{0};
        uint32_t samplefreq{0};
        uint16_t bitsPerSample{0};
        uint16_t channels{0};
    };
    // Base data: all track upsongs have data in there
    Res rsrc;
    
    int mpdid{0};
    bool iscontainer{false};
    bool searchable{false};
};

class UpSong : public UpSongBase {
public:
    // Our vendor metadata extension fields (contentDirectory v1 2.8.11). They must all be prefixed
    // with "upmp:"
    // Using a derived class for easy copy const and assign op. Would be simpler to just use
    // shared_ptr...
    std::unordered_map<std::string, std::string> *upmpfields{nullptr};
    // Additional resources for other formats etc. for the same
    // track. Only used by the media server, and usually empty.
    std::vector<Res> *resources{nullptr};

    UpSong() {}

    ~UpSong() {
        delete upmpfields;
        delete resources;
    }

    UpSong& operator=(UpSong const& rhs) {
        if (this != &rhs) {
            UpSongBase::operator=(rhs);
            if (rhs.upmpfields) {
                upmpfields = new std::unordered_map<std::string, std::string>(*rhs.upmpfields);
            } else {
                upmpfields = nullptr;
            }
            if (rhs.resources) {
                resources = new std::vector<Res>(*rhs.resources);
            } else {
                resources = nullptr;
            }
        }
        return *this;
    }

    UpSong(UpSong const& l)
        : UpSongBase(l) {
        if (l.upmpfields) {
            upmpfields = new std::unordered_map<std::string, std::string>(*l.upmpfields);
        } else {
            upmpfields = nullptr;
        }
        if (l.resources) {
            resources = new std::vector<Res>(*l.resources);
        } else {
            resources = nullptr;
        }
    }
    void clear() {
        delete upmpfields;
        delete resources;
        *this = UpSong();
    }
    
    std::string dump() const {
        return std::string("class [" + upnpClass + "] Artist [" + artist +
                           "] Album [" +  album + " Title [" + title +
                           "] Tno [" + tracknum + "] Uri [" + rsrc.uri + "]");
    }
    // Format to DIDL fragment 
    std::string didl(bool nobitrate = false) const;

    static UpSong container(const std::string& id, const std::string& pid,
                            const std::string& title, bool searchable = true) {
        UpSong song;
        song.iscontainer = true;
        song.id = id;
        song.parentid = pid;
        song.title = title;
        song.searchable = searchable;
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

// Return mapvalue or null strings, for maps where absent entry and null data are equivalent
extern const std::string& mapget(
    const std::unordered_map<std::string, std::string>& im, const std::string& k);

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

extern bool ensureconfreadable(const char *fn, const char *user, uid_t uid, gid_t gid);

// printf-like %xx substitutions in friendlynames. Only hostname (%h) at this point
extern std::string fnameSetup(const std::string in);

extern std::string upmpdcliVersionInfo();

extern bool mimeToCodec(const std::string& mime, std::string& codec, bool *lossless);

#endif /* _UPMPDUTILS_H_X_INCLUDED_ */
