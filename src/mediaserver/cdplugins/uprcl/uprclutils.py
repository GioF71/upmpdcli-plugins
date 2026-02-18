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

_g_folders = None
def importfolders(folders):
    global _g_folders
    _g_folders = folders

def httpurl(httphp, path, query=""):
    """Compose an http URL from host path (http://xxx/) path and query.
    path can be either str or bytes and will be url-encoded"""
    return f"http://{httphp}{urlquote(path)}{query}"


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
        arturi = _g_folders.docarturi(doc, False, doc["album"])
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
    url = doc["url"]
    ssidx = url.find("//")
    if url.find("file://") == 0:
        bpath = docbinpath(doc)
        li["uri"] = httpurl(httphp, bpath)
    else:
        # hopefully an ok http url
        li["uri"] = url
    # uplog("rcldoctoentry: uri: %s" % li['uri'])

    if "tt" not in li:
        li["tt"] = os.path.basename(url[ssidx + 2 :])

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
def docbinpath(doc):
    # Versions of recoll from 1.43.11 decode the binary URL to UTF-8 with the surrogateescape error
    # handler. We don't support older version any more. Not sure how we do with non-utf-8 paths
    # (TBD) For reference, minim does not process them at all.
    return doc["url"][7:].encode(_g_fse, "surrogateescape")
def docpath(doc):
    # Versions of recoll from 1.43.11 decode the binary URL to UTF-8 with the surrogateescape error
    # handler. We don't support older version any more. Not sure how we do with non-utf-8 paths
    # (TBD) For reference, minim does not process them at all.
    return doc["url"][7:]


def docfolder(doc):
    path = doc["url"][7:]
    if doc["mtype"] != "inode/directory":
        path = os.path.dirname(path)
    if path[-1] != "/"[0]:
        path += "/"
    return path


def embdimgurl(doc, httphp, pathprefix):
    if isinstance(pathprefix, str):
        pathprefix = pathprefix.encode("UTF-8")
    if doc["embdimg"] == "jpg":
        ext = b".jpg"
    elif doc["embdimg"] == "png":
        ext = b".png"
    else:
        return None
    path = docbinpath(doc)
    path = os.path.join(pathprefix, path + ext)
    query = "?embed=1"
    return httpurl(httphp, path, query)


def printable(s):
    if type(s) != type(""):
        return s.decode("utf-8", errors="replace") if s else ""
    else:
        return s


# Transform a string so that it can be used as a file name, using
# minimserver rules: just remove any of: " * / : < > ? \ |
def tag2fn(s):
    return (
        s.replace('"', "")
        .replace("*", "")
        .replace("/", "")
        .replace(":", "")
        .replace("<", "")
        .replace(">", "")
        .replace("?", "")
        .replace("\\", "")
        .replace("|", "")
    )


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
    urlRE = re.compile(r"[a-zA-Z]+://")

    def __init__(self, fn):
        data = open(fn, "rb").read()
        try:
            data = data.decode(_g_fse, errors="surrogatescape")
        except:
            pass
        self.urls = []
        dn = os.path.dirname(os.path.abspath(fn))
        for line in data.split("\n"):
            line = line.strip(" \r")
            if not line or line[0] == "#"[0]:
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

        
# Create bogus doc for external (http) url. This is for playlists.
def docforurl(rcldb, url):
    doc = rcldb.doc()
    doc.url = url
    doc.title = os.path.split(url)[1]
    doc.mtype = "audio/mpeg"
    return doc

        
