# Copyright (C) 2026 J.F.Dockes
#
# License: GPL 2.1
#
# This program is free software; you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation; either version 2.1 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# Auxiliary functions for the folders tree, mostly dealing with building it
import time
import shlex
import os

from recoll import recoll
from recoll import qresultstore
from recoll import rclconfig
from upmplgutils import uplog, direntry, getOptionValue
import uprclutils
import uprclinit

# All Doc fields which we may want to access (reserve slots in the
# resultstore). We use an inclusion list, and end up with a smaller
# store than by using an exclusion list, but it's a bit more difficult
# to manage.
#
# +  possibly 'xdocid' and/or 'rcludi' if/when needed?
#
_otherneededfields = [
    "albumartist",
    "allartists",
    "comment",
    "composer",
    "conductor",
    "contentgroup",
    "date",
    "dmtime",
    "discnumber",
    "embdimg",
    "filename",
    "genre",
    "group",
    "label",
    "lyricist",
    "orchestra",
    "performer",
]

# Fetch all the docs by querying Recoll with an empty query (needs recoll 1.43.10, else use
# [mime:*]), which is guaranteed to match every doc.
# This creates the main doc array, which is then used by all modules.
#
# Because we are using the resultstore, the records are not modifyable and the aliastags
# processing is performed at indexing time by rclaudio. Cf. minimtagfixer.py
def _fetchalldocs(confdir):
    start = time.time()

    rcldb = recoll.connect(confdir=confdir)
    rclq = rcldb.query()
    rclq.execute("", stemming=0)
    # rclq.execute('album:a* OR album:b* OR album:c*', stemming=0)
    uplog("Estimated alldocs query results: %d" % (rclq.rowcount))

    fields = [r[1] for r in uprclutils.upnp2rclfields.items()]
    fields += _otherneededfields
    fields += uprclinit.allMinimTags()
    fields = list(set(fields))
    #uplog(f"_fetchalldocs: store fields: {fields}")
    rcldocs = qresultstore.QResultStore()
    rcldocs.storeQuery(rclq, fieldspec=fields, isinc=True)

    end = time.time()
    uplog("Retrieved %d docs in %.2f Seconds" % (len(rcldocs), end - start))
    return rcldocs

# Create new directory entry: insert in father and append dirvec slot
# (with ".." entry)
def _createdir(dirvec, fathidx, docidx, nm):
    dirvec.append({})
    thisidx = len(dirvec) - 1
    dirvec[fathidx][nm] = (thisidx, docidx)
    dirvec[-1][".."] = (fathidx, -1)
    dirvec[-1]["."] = (thisidx, docidx)
    return len(dirvec) - 1


# Create directory for playlist. Create + populate. The docs which are pointed by the playlist
# entries may not be in the tree yet, so we don't know how to find them (can't walk the tree yet).
# Just store the diridx and populate all playlists at the end
def _createpldir(dirvec, playlists, fathidx, docidx, doc, nm):
    myidx = _createdir(dirvec, fathidx, docidx, nm)
    # We need a "." entry
    dirvec[myidx]["."] = (myidx, docidx)
    playlists.append(myidx)
    return myidx


# Compute and return the index in root of the topdir we're a child and the rest of the path
# split as a list.
# The root entry (diridx 0) is special because its keys are the
# topdirs paths, not simple names. We look with what topdir path
# this doc belongs to, then return the appropriate diridx and the
# split remainder of the path
def _splitpath(dirvec, doc):
    path = doc["url"][7:].rstrip("/")

    # Determine the root entry (topdirs element). Special because its path is not a simple
    # name. Fathidx is its index in _dirvec
    firstdiridx = -1
    for rootpath, idx in dirvec[0].items():
        if path.startswith(rootpath):
            firstdiridx = idx[0]
            break
    if firstdiridx == -1:
        # Note: this is actually common because of the recoll documents created so that artist
        # searches work (_artiststorecoll in uprcltagscreate). These don't have real existence in
        # the file system.
        #uplog(f"No parent in topdirs: {path}")
        return None, None

    # Compute rest of path. If there is none, we're not interested.
    path1 = path[len(rootpath) :]
    if len(path1) == 0:
        return None, None

    # If there is a Group field, just add it as a virtual
    # directory in the path. This only affects the visible tree,
    # not the 'real' PATHs of course.
    try:
        if doc["group"]:
            a = os.path.dirname(path1)
            b = os.path.basename(path1)
            path1 = os.path.join(a, doc["group"], b)
    except:
        pass

    # Split path. The caller will walk the list (possibly creating
    # directory entries as needed, or doing something else).
    path = path1.split("/")[1:]
    return firstdiridx, path


# Main folders build method: walk the recoll docs array and split the URLs paths to build the
# [folders] data structure
def _rcl2folders(confdir, rcldocs):
    dirvec = []
    playlists = []
    
    # We initially thought that we needed a data structure lor linking item search results to the
    # main array. Deactivated for now as it does not seem to be needed (and we would need to add
    # xdocid to the resultstore fields).
    # self._xid2idx[doc["xdocid"]] = docidx

    start = time.time()

    rclconf = rclconfig.RclConfig(confdir)
    topdirs = [os.path.expanduser(d) for d in shlex.split(rclconf.getConfParam("topdirs"))]
    topdirs = [d.rstrip("/") for d in topdirs]

    # Create the 1st entry. This is special because it holds the
    # recoll topdirs, which are paths instead of simple names. There
    # does not seem any need to build the tree between a topdir and /
    dirvec.append({})
    dirvec[0][".."] = (0, -1)
    for d in topdirs:
        dirvec.append({})
        dirvec[0][d] = (len(dirvec) - 1, -1)
        dirvec[-1][".."] = (0, -1)

    # Walk the doc list and update the directory tree according to the url: create intermediary
    # directories if needed, create leaf entry.
    for docidx in range(len(rcldocs)):
        doc = rcldocs[docidx]

        fathidx, path = _splitpath(dirvec, doc)
        if not fathidx:
            continue

        # uplog("%s"%path, file=sys.stderr)
        for idx in range(len(path)):
            elt = path[idx]
            if elt in dirvec[fathidx]:
                # This path element was already seen
                # If this is the last entry in the path, maybe update
                # the doc idx (previous entries were created for
                # intermediate elements without a Doc).
                if idx == len(path) - 1:
                    dirvec[fathidx][elt] = (dirvec[fathidx][elt][0], docidx)
                # Update fathidx for next iteration
                fathidx = dirvec[fathidx][elt][0]
            else:
                # Element has no entry in father directory (hence no
                # dirvec entry either).
                if idx != len(path) - 1:
                    # This is an intermediate element. Create a
                    # Doc-less directory
                    fathidx = _createdir(dirvec, fathidx, -1, elt)
                else:
                    # Last element. If directory, needs a dirvec entry
                    if doc["mtype"] == "inode/directory":
                        fathidx = _createdir(dirvec, fathidx, docidx, elt)
                    elif doc["mtype"] == "audio/x-mpegurl":
                        fathidx = _createpldir(dirvec, playlists, fathidx, docidx, doc, elt)
                    else:
                        dirvec[fathidx][elt] = (-1, docidx)

    if False:
        for ent in dirvec:
            uplog("%s" % ent)

    end = time.time()
    uplog("_rcl2folders took %.2f Seconds" % (end - start))
    return dirvec, playlists


# Initialize all playlists after the tree is otherwise complete
def _initplaylists(slf, confdir, rcldocs, dirvec, playlists):
    moredocs = []
    # We use a recoll db connection for creating bogus rcl docs
    rcldb = recoll.connect(confdir=confdir)
    for diridx in playlists:
        pldocidx = dirvec[diridx]["."][1]
        pldoc = rcldocs[pldocidx]
        plpath = uprclutils.docpath(pldoc)
        try:
            m3u = uprclutils.M3u(plpath)
        except Exception as ex:
            uplog(f"M3u open failed: plpath [{plpath}] : {ex}")
            continue
        for urlorpath in m3u:
            if m3u.urlRE.match(urlorpath):
                # Actual URL (usually http). Create bogus doc
                doc = uprclutils.docforurl(rcldb, urlorpath)
                moredocs.append(doc)
                docidx = len(rcldocs) + len(moredocs) - 1
                tt = doc["title"]
                dirvec[diridx][tt] = (-1, docidx)
            else:
                if not os.path.isabs(urlorpath):
                    urlorpath = os.path.join(os.path.dirname(plpath), urlorpath)
                docidx = slf.statpath(urlorpath)
                if docidx >= 0:
                    #uplog(f"Track OK for playlist [{plpath}] entry [{urlorpath}]")
                    elt = os.path.split(urlorpath)[1]
                    dirvec[diridx][elt] = (-1, docidx)
                else:
                    uplog(f"No track for playlist [{plpath}] entry [{urlorpath}]")
                    #self.statpath(urlorpath, verbose=True)
    return moredocs
