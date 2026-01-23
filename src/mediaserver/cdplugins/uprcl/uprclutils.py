#
# Copyright (C) 2017-2019 J.F.Dockes
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import print_function

import sys
from urllib.parse import quote as urlquote, unquote_to_bytes as urlunquotetobytes
import functools
import glob
import io
import locale
import mutagen
import os
import re
import traceback
import xml.sax.saxutils

from recoll import recoll
from upmplgutils import uplog

_g_fse = sys.getfilesystemencoding()

audiomtypes = frozenset(
    [
        "audio/mpeg",
        "audio/flac",
        "application/flac",
        "audio/x-dsf",
        "audio/x-dff",
        "audio/x-aiff",
        "audio/x-flac",
        "application/x-flac",
        "application/ogg",
        "audio/aac",
        "audio/mp4",
        "video/mp4",
        "audio/x-aiff",
        "audio/x-musepack",
        "audio/ape",
        "audio/x-wav",
        "audio/x-wavpack",
        "inode/directory",
        "audio/x-mpegurl",
    ]
)

# Correspondance between Recoll field names (on the right), defined by rclaudio and the Recoll
# configuration 'fields' file, and what plgwithslave.cxx expects, which is less than consistent.
# Some tags have no predefined fields in upmpdcli (e.g. composer, conductor), and we output them as
# a didl fragment (see below). They are still listed here because the data is also used to define
# the fields actually extracted in the results of the initial recoll listing (resultstore)
upnp2rclfields = {
    "upnp:album": "album",
    "upnp:albumArtURI": "albumarturi",
    "upnp:artist": "artist",
    "dc:description": "comment",
    "composer": "composer",
    "conductor": "conductor",
    "dc:date": "date",
    "upnp:genre": "genre",
    "duration": "duration",  # should be res:
    "res:bitrate": "bitrate",
    "res:bitsPerSample": "bits_per_sample",
    "res:channels": "channels",
    "res:mime": "mtype",
    "res:samplefreq": "sample_rate",
    "res:size": "fbytes",
    "tt": "title",
    "dc:title": "title",
    "upnp:originalTrackNumber": "tracknumber",
}


def _httpurl(httphp, path, query=""):
    return "http://%s%s%s" % (httphp, urlquote(path), query)


def rcldoctoentry(id, pid, httphp, pathprefix, doc):
    """
    Transform a Doc object into the format expected by the parent

    Args:
        id (str): objid for the entry
        pid (str):  objid for the browsed object (the parent container)
        httphp: the hostport part of the generated track urls
        pathprefix: is provided by our parent process (it's used to
          what plugin an url belongs too when needed for
          translating the internal into the real url (for plugins
          based on external-services)
        doc is the Doc object to be translated

    Returns:
        A dict representing an UPnP item, with the
        keys as expected in the plgwithslave.cxx resultToEntries() function.
    """
    # uplog("rcldoctoentry:  pid %s id %s mtype %s" % (pid, id, doc["mtype"]))

    li = {}
    if doc["mtype"] not in audiomtypes:
        return li

    li["pid"] = pid
    li["id"] = id
    if doc["mtype"] == "inode/directory":
        li["tp"] = "ct"
        li["upnp:class"] = "object.container"
    else:
        li["tp"] = "it"
        # TBD
        li["upnp:class"] = "object.item.audioItem.musicTrack"

    for oname, dname in upnp2rclfields.items():
        val = doc[dname]
        if val:
            li[oname] = val

    if "upnp:albumArtURI" not in li:
        arturi = docarturi(doc, httphp, pathprefix)
        if arturi:
            li["upnp:albumArtURI"] = arturi

    if "upnp:artist" not in li and doc["albumartist"]:
        li["upnp:artist"] = doc["albumartist"]

    # TBD Date format ?
    # discnumber=
    # genre=
    # lyricist=
    # lyrics=

    # Some properties are not directly supported by the upmpdcli internal UpSong object, which only
    # manages basic UPnP props. We send them directly as a DIDL fragment which will be incorporated
    # in the final XML
    didlfrag = ""
    if doc["composer"]:
        didlfrag += (
            '<upnp:artist role="Composer">'
            + xml.sax.saxutils.escape(doc["composer"])
            + "</upnp:artist>"
        )
    if doc["conductor"]:
        didlfrag += (
            '<upnp:artist role="Conductor">'
            + xml.sax.saxutils.escape(doc["conductor"])
            + "</upnp:artist>"
        )
    if doc["albumartist"]:
        didlfrag += (
            '<upnp:artist role="AlbumArtist">'
            + xml.sax.saxutils.escape(doc["albumartist"])
            + "</upnp:artist>"
        )
    if didlfrag:
        li["didlfrag"] = didlfrag

    try:
        val = li["upnp:originalTrackNumber"]
        l = val.split("/")
        li["upnp:originalTrackNumber"] = l[0]
    except:
        pass

    # Compute the url. We use the URL from recoll, stripped of file://
    # and with the pathprefix prepended (the pathprefix is used by our
    # parent process to match urls to plugins)
    path = doc["url"]
    ssidx = path.find("//")
    if path.find("file://") == 0:
        bpath = docpath(doc)
        li["uri"] = _httpurl(httphp, bpath)
    else:
        li["uri"] = path[: ssidx + 2] + urlquote(path[ssidx + 2 :])
    # uplog("rcldoctoentry: uri: %s" % li['uri'])

    if "tt" not in li:
        li["tt"] = os.path.basename(path[ssidx + 2 :])

    return li


# Bogus entry for the top directory while the index/db is updating
def waitentry(id, pid, httphp, msg="Initializing..."):
    li = {}
    li["tp"] = "it"
    li["id"] = id
    li["pid"] = pid
    li["upnp:class"] = "object.item.audioItem.musicTrack"
    li["tt"] = msg
    li["uri"] = "http://%s%s" % (httphp, "/waiting")
    li["res.mime"] = "audio/mpeg"
    return li


# dirname and basename which returns the last element, not null, when
# the path ends in '/'
def dirname(path):
    if path[-1] == "/"[0] and path != "/":
        return os.path.dirname(path[0:-1])
    else:
        return os.path.dirname(path)


def basename(path):
    if path[-1] == "/"[0] and path != "/":
        return os.path.basename(path[0:-1])
    else:
        return os.path.basename(path)


# Compute binary fs path for URL. All Recoll URLs are like file://xx
def docpath(doc):
    # Versions of recoll from 1.43.11 decode the binary URL to UTF-8 with the surrogateescape error
    # handler. We don't support older version any more. Not sure how we do with non-utf-8 paths
    # (TBD) For reference, minim does not process them at all.
    return doc["url"][7:].encode(_g_fse, "surrogateescape")


def docfolder(doc):
    path = docpath(doc)
    if doc["mtype"] != "inode/directory":
        path = os.path.dirname(path)
    if path[-1] != b"/"[0]:
        path += b"/"
    return path


def embdimgurl(doc, httphp, binpathprefix):
    if doc["embdimg"] == "jpg":
        ext = b".jpg"
    elif doc["embdimg"] == "png":
        ext = b".png"
    else:
        return None
    path = docpath(doc)
    path = os.path.join(binpathprefix, path + ext)
    query = "?embed=1"
    return _httpurl(httphp, path, query)


def printable(s):
    if type(s) != type(""):
        return s.decode("utf-8", errors="replace") if s else ""
    else:
        return s


# Transform a string so that it can be used as a file name, using
# minimserver rules: just remove any of: " * / : < > ? \ |
def tag2fn(s):
    if type(s) == type(""):
        s = s.encode(locale.getpreferredencoding())

    return (
        s.replace(b'"', b"")
        .replace(b"*", b"")
        .replace(b"/", b"")
        .replace(b":", b"")
        .replace(b"<", b"")
        .replace(b">", b"")
        .replace(b"?", b"")
        .replace(b"\\", b"")
        .replace(b"|", b"")
    )


##########################
# Find cover art for doc
#
# We return a special uri if the file has embedded image data, else an
# uri for for the directory cover art (if any).

# We are usually called repeatedly for the same directory, so we cache
# one result.
#
# The doc can come from recoll (track or directory), or be virtual (playlist)
_foldercache = {}

# All standard cover art file names:
_artexts = (b".jpg", b".png")


def _artnamegen(base):
    for ext in _artexts:
        yield base + ext


_folderartbases = (b"cover", b"folder")
_folderartnames = []
for base in _folderartbases:
    for path in _artnamegen(base):
        _folderartnames.append(path)


# Track-specific art. This is sometimes called for multiple files in the same directory.
# Tried to read/cache the directory contents on first access: not faster.
def _trackarturi(doc, objpath, httphp, bpp):
    # Check for an image specific to the track file
    base, ext = os.path.splitext(objpath)
    for artpath in _artnamegen(base):
        #uplog(f"_trackarturi: Calling os.path.exist({artpath})")
        if os.path.exists(artpath):
            return _httpurl(httphp, os.path.join(bpp, artpath))

    # Else try to use an embedded img
    if doc["embdimg"]:
        arturi = embdimgurl(doc, httphp, bpp)
        if arturi:
            # uplog("docarturi: embedded: %s"%printable(arturi))
            return arturi
    return None


# Return folder-level art uri (e.g. /path/to/folder.jpg) if it exists
def _folderart(doc, httphp, bpp, albtitle=None):
    global _foldercache

    # If doc is a directory, this returns itself, else the father dir.
    folder = docfolder(doc)

    # If albtitle is set check for an image of the same name
    if albtitle:
        albtitle = albtitle.encode("UTF-8")
        for fsimple in _artnamegen(albtitle):
            path = os.path.join(folder, fsimple)
            #uplog(f"_folderart: calling os.path.exist({path})")
            if os.path.exists(path):
                return _httpurl(httphp, path)

    # Look for an appropriate image in the file folder. Generating the charcase combinations would
    # be complicated so we list the folder and look for a case-insensitive match. As this is slow,
    # we cache the result.
    # TBD: if we support dynamic updates at some point, the caching will have to look at the folder
    # mtime, or to be reset at each update.
    if folder not in _foldercache:
        # uplog(f"_folderart: looking at {folder}")
        _foldercache[folder] = None
        artnm = None
        try:
            for f in sorted(os.listdir(folder)):
                try:
                    fsimple = os.path.basename(f)
                    flowersimple = fsimple.lower()
                except:
                    # traceback.print_exc()
                    continue
                if flowersimple in _folderartnames:
                    path = os.path.join(bpp, folder, fsimple)
                    _foldercache[folder] = _httpurl(httphp, path)
                    break
        except:
            # traceback.print_exc()
            pass

    arturi = _foldercache[folder]
    if arturi:
        # uplog("folder %s arturi %s"% (printable(folder), arturi))
        if doc["mtype"] == "inode/directory":
            # uplog("docarturi: external: %s->%s" % (printable(folder), printable(arturi)))
            pass

    return arturi


def docarturi(doc, httphp, pathprefix, preferfolder=False, albtitle=None):
    bpp = pathprefix.encode("utf-8")
    objpath = docpath(doc)
    #uplog(f"docarturi: preferfolder {preferfolder} docpath {objpath}")

    if not preferfolder:
        arturi = _trackarturi(doc, objpath, httphp, bpp)
        if arturi:
            return arturi

    # won't work for the virtual group directory itself: it has no doc
    if doc["group"]:
        base = os.path.join(os.path.dirname(objpath), tag2fn(doc["group"]))
        for artpath in _artnamegen(base):
            #uplog(f"docarturi:calling os.path.exist({artpath})")
            if os.path.exists(artpath):
                return _httpurl(httphp, os.path.join(bpp, artpath))

    # TBD Here minimserver would look for album disc before album art (which is taken care of by
    # _folderart() with albtitle set)
    # Look for folder level image file (e.g. cover.jpg)
    arturi = _folderart(doc, httphp, bpp, albtitle)
    if arturi:
        return arturi

    # If preferfolder is set, we did not look at the track-specific art, do it last.
    if preferfolder:
        arturi = _trackarturi(doc, objpath, httphp, bpp)

    return arturi


def _keyvalornull(a, k):
    return a[k] if k in a else "NULL"


def _logentry(nm, e1):
    tp = _keyvalornull(e1, "tp")
    al = _keyvalornull(e1, "upnp:album")
    dr = os.path.dirname(_keyvalornull(e1, "uri"))
    tn = _keyvalornull(e1, "upnp:originalTrackNumber")
    uplog("%s tp %s alb %s dir %s tno %s" % (nm, tp, al, dr, tn))


# General container sort items comparison method
def _cmpentries_func(e1, e2):
    # uplog("cmpentries");_logentry("e1", e1);_logentry("e2", e2)
    tp1 = e1["tp"]
    tp2 = e2["tp"]
    isct1 = tp1 == "ct"
    isct2 = tp2 == "ct"

    # Containers come before items, and are sorted in alphabetic order
    ret = -2
    if isct1 and not isct2:
        ret = -1
    elif not isct1 and isct2:
        ret = 1
    elif isct1 and isct2:
        tt1 = e1["tt"]
        tt2 = e2["tt"]
        if tt1.lower() < tt2.lower():
            ret = -1
        elif tt1.lower() > tt2.lower():
            ret = 1
        else:
            ret = 0
    if ret != -2:
        # uplog("cmpentries tp1 %s tp2 %s, returning %d"%(tp1,tp2,ret))
        return ret

    # Tracks. Sort by album then directory then track number then file name
    k = "upnp:album"
    a1 = e1[k] if k in e1 else ""
    a2 = e2[k] if k in e2 else ""
    if a1 < a2:
        return -1
    elif a1 > a2:
        return 1

    a1 = os.path.dirname(e1["uri"])
    a2 = os.path.dirname(e2["uri"])
    if a1 < a2:
        return -1
    elif a1 > a2:
        return 1

    k = "upnp:originalTrackNumber"
    try:
        a1 = int(e1[k])
    except:
        a1 = 0
    try:
        a2 = int(e2[k])
    except:
        a2 = 0
    if a1 < a2:
        return -1
    elif a1 > a2:
        return 1

    # Finally: compare file names
    a1 = os.path.basename(e1["uri"])
    a2 = os.path.basename(e2["uri"])
    if a1 < a2:
        return -1
    elif a1 > a2:
        return 1

    return 0


cmpentries = functools.cmp_to_key(_cmpentries_func)


# Special comparison method for items lists: we don't want to sort by album but by title instead
def _cmpitems_func(e1, e2):

    # Tracks. Sort by title then album
    k = "tt"
    a1 = e1[k] if k in e1 else ""
    a2 = e2[k] if k in e2 else ""
    if a1 < a2:
        return -1
    elif a1 > a2:
        return 1

    k = "upnp:album"
    a1 = e1[k] if k in e1 else ""
    a2 = e2[k] if k in e2 else ""
    if a1 < a2:
        return -1
    elif a1 > a2:
        return 1

    return 0


cmpitems = functools.cmp_to_key(_cmpitems_func)


# Open embedded image. Returns mtype, size, f
def embedded_open(path):
    try:
        mutf = mutagen.File(path)
    except Exception as err:
        raise err

    f = None
    size = 0

    # First pretend that this is an ID3. These can come inside multiple file formats, don't try to
    # select on MIME, just try it.
    for tagname in mutf.keys():
        if tagname.startswith("APIC:"):
            # self.em.rclog("mp3 img: %s" % mutf[tagname].mime)
            mtype = mutf[tagname].mime
            s = mutf[tagname].data
            size = len(s)
            f = io.BytesIO(s)

    if not f:
        if "audio/flac" in mutf.mime:
            if mutf.pictures:
                mtype = mutf.pictures[0].mime
                size = len(mutf.pictures[0].data)
                f = io.BytesIO(mutf.pictures[0].data)
        elif "audio/mp4" in mutf.mime:
            if "covr" in mutf.keys():
                format = mutf["covr"][0].imageformat
                if format == mutagen.mp4.AtomDataType.JPEG:
                    mtype = "image/jpeg"
                else:
                    mtype = "image/png"
                size = len(mutf["covr"][0])
                f = io.BytesIO(mutf["covr"][0])

    if f is None:
        raise Exception(f"can't open embedded image for {path}")
    else:
        return mtype, size, f


class M3u(object):
    urlRE = re.compile(rb"[a-zA-Z]+://")

    def __init__(self, fn):
        data = open(fn, "rb").read()
        try:
            data = data.decode("utf-8-sig")
            data = data.encode("utf-8")
        except:
            pass
        self.urls = []
        dn = os.path.dirname(os.path.abspath(fn))
        for line in data.split(b"\n"):
            line = line.strip(b" \r")
            if not line or line[0] == b"#"[0]:
                continue
            if self.urlRE.match(line):
                self.urls.append(line)
            else:
                if os.path.isabs(line):
                    self.urls.append(os.path.normpath(line))
                else:
                    self.urls.append(os.path.normpath(os.path.join(dn, line)))
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.urls):
            raise StopIteration
        else:
            self.index += 1
            return self.urls[self.index - 1]
