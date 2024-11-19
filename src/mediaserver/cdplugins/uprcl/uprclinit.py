# Copyright (C) 2017 J.F.Dockes
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

import sys
import os
import conftree
import threading
import subprocess
import time
import traceback
from timeit import default_timer as timer

from rwlock import ReadWriteLock

from uprclfolders import Folders
from uprcluntagged import Untagged
from uprclplaylists import Playlists
from uprcltags import Tagged
import uprclsearch
import uprclindex
from uprclhttp import runbottle
import minimconfig

from upmplgutils import uplog, getcachedir, getOptionValue
from conftree import stringToStrings

### Configuration stuff
_g_rclconfdir = ""
_g_pathprefix = ""
_g_httphp = ""
_g_friendlyname = "UpMpd-mediaserver"
# Prefix for object Ids. This must be consistent with what
# contentdirectory.cxx does
_g_myprefix = "0$uprcl$"
g_minimconfig = None

### Index update status
# Running state: ""/"Updating"/"Rebuilding"
g_initrunning = ""
# Completion status: ok/notok
g_initstatus = False
# Possible error message if not ok
g_initmessage = ""

### Data created during initialisation
_g_trees = {}
_g_trees_order = ["folders", "playlists", "tags", "untagged"]

g_dblock = ReadWriteLock()


def getObjPrefix():
    return _g_myprefix


def getPathPrefix():
    return _g_pathprefix


def getHttphp():
    return _g_httphp


def getRclConfdir():
    return _g_rclconfdir


def getFriendlyname():
    return _g_friendlyname


def getTree(treename):
    return _g_trees[treename]


def getTreesOrder():
    return _g_trees_order


def _reset_index():
    _update_index(True)


def initdone():
    g_dblock.acquire_read()
    if g_initrunning:
        return False
    else:
        return True


def initstatus():
    return (g_initstatus, g_initmessage)


def updaterunning():
    return g_initrunning


# Create or update Recoll index, then read and process the data. This runs in a separate thread, and
# signals startup/completion by setting/unsetting the g_initrunning flag.
#
# While this is running, or after a failure any access to the root container from a Control Point
# will display either an "Initializing" or error message.
def _update_index(rebuild=False):
    uplog("Creating/updating index in %s for %s" % (_g_rclconfdir, g_rcltopdirs))

    # We take the writer lock, making sure that no browse/search thread are active, then set the
    # busy flag and release the lock. This allows future browse operations to signal the condition
    # to the user instead of blocking (if we kept the write lock).
    global g_initrunning, _g_trees, g_initstatus, g_initmessage
    g_dblock.acquire_write()
    g_initrunning = "Rebuilding" if rebuild else "Updating"
    g_dblock.release_write()
    uplog("_update_index: initrunning set")

    try:
        start = timer()
        uprclindex.runindexer(_g_rclconfdir, g_rcltopdirs, rebuild=rebuild)
        # Wait for indexer
        while not uprclindex.indexerdone():
            time.sleep(0.5)
        fin = timer()
        uplog("Indexing took %.2f Seconds" % (fin - start))

        folders = Folders(_g_rclconfdir, _g_httphp, _g_pathprefix)
        untagged = Untagged(folders.rcldocs(), _g_httphp, _g_pathprefix)
        playlists = Playlists(_g_rclconfdir, folders.rcldocs(), _g_httphp, _g_pathprefix)
        tagged = Tagged(folders.rcldocs(), _g_httphp, _g_pathprefix)
        newtrees = {}
        newtrees["folders"] = folders
        newtrees["untagged"] = untagged
        newtrees["playlists"] = playlists
        newtrees["tags"] = tagged
        _g_trees = newtrees
        g_initstatus = True
        uplog("Init done")
    except Exception as ex:
        traceback.print_exc()
        g_initstatus = False
        g_initmessage = str(ex)
        uplog(f"Initialisation failed with: {g_initmessage}")
    finally:
        g_dblock.acquire_write()
        g_initrunning = ""
        g_dblock.release_write()


# This is called from uprcl-app when starting up, before doing anything else. We read configuration
# data, then start two threads: the permanent HTTP server and the index update thread.
def uprcl_init():

    global _g_pathprefix, g_initstatus, g_initmessage

    #######
    # Acquire configuration data.

    # We get the path prefix from an environment variable set by our parent upmpdcli. It would
    # typically be something like "/uprcl". It's used for dispatching URLs to the right plugin for
    # processing. We strip it whenever we need a real file path.
    if "UPMPD_PATHPREFIX" not in os.environ:
        raise Exception("No UPMPD_PATHPREFIX in environment")
    _g_pathprefix = os.environ["UPMPD_PATHPREFIX"]
    if "UPMPD_CONFIG" not in os.environ:
        raise Exception("No UPMPD_CONFIG in environment")
    global _g_friendlyname
    if "UPMPD_FNAME" in os.environ:
        _g_friendlyname = os.environ["UPMPD_FNAME"]

    global g_minimconfig
    minimcfn = getOptionValue("uprclminimconfig")
    g_minimconfig = minimconfig.MinimConfig(minimcfn)

    global _g_httphp
    _g_httphp = getOptionValue("uprclhostport")
    if _g_httphp is None:
        if "UPMPD_HTTPHOSTPORT" not in os.environ:
            raise Exception("No UPMPD_HTTPHOSTPORT in environment")
        upmpdhttphp = os.environ["UPMPD_HTTPHOSTPORT"]
        ip = upmpdhttphp.split(":")[0]
        port = getOptionValue("uprclport")
        if port is None:
            port = "9090"
        _g_httphp = ip + ":" + port
    uplog("uprcl: serving files on %s" % _g_httphp)

    global _g_rclconfdir
    _g_rclconfdir = getOptionValue("uprclconfdir")
    _g_rclconfdir = getcachedir("uprcl", forcedpath=_g_rclconfdir)
    uplog("uprcl: cachedir: %s" % _g_rclconfdir)

    global g_rcltopdirs
    g_rcltopdirs = getOptionValue("uprclmediadirs")
    if g_rcltopdirs:
        g_rcltopdirs = conftree.stringToStrings(g_rcltopdirs)
    else:
        g_rcltopdirs = g_minimconfig.getcontentdirs()
    if not g_rcltopdirs:
        g_initstatus = False
        g_initmessage = "No media directories were set in configuration"
        return

    # g_rcltopdirs is now a list, check the elements
    goodpthlist = []
    for dir in g_rcltopdirs:
        if not os.path.isdir(dir):
            uplog(f"uprcl: [{dir}] is not accessible")
        else:
            goodpthlist.append(dir)
    if not goodpthlist:
        g_initstatus = False
        g_initmessage = "No accessible media directories in configuration"
        return

    pthstr = getOptionValue("uprclpaths")
    if pthstr is None:
        uplog("uprclpaths not in config, using topdirs: [%s]" % g_rcltopdirs)
        pthstr = ""
        for p in g_rcltopdirs:
            pthstr += p + ":" + p + ","
        pthstr = pthstr.rstrip(",")
    uplog("Path translation: pthstr: %s" % pthstr)

    host, port = _g_httphp.split(":")

    # Turn g_rcltopdirs back into a string, that's how it's used by runindexer
    g_rcltopdirs = conftree.stringsToString(goodpthlist)

    start_index_update()

    # Start the bottle app. It's both the control/config interface and the file streamer
    httpthread = threading.Thread(
        target=runbottle,
        kwargs={"host": host, "port": int(port), "pthstr": pthstr, "pathprefix": _g_pathprefix},
    )
    httpthread.daemon = True
    httpthread.start()

    uplog("Init started")


# This is called from the Bottle Web UI interface for requesting an index update or rebuild
def start_index_update(rebuild=False):
    try:
        # initdone() acquires the reader lock
        if not initdone():
            return
        targ = _reset_index if rebuild else _update_index
        idxthread = threading.Thread(target=targ)
        idxthread.daemon = True
    finally:
        # We need to release the reader lock before starting the index
        # update operation (which needs a writer lock), so there is a
        # small window for mischief. I would be concerned if this was
        # a highly concurrent or critical app, but here, not so
        # much...
        g_dblock.release_read()
    idxthread.start()


# Return list of tags from minim indexTags settings. These can contain custom tags,
# not part of our predefined lists, which need to be stored in the resultstore.
def allMinimTags():
    fields = []
    try:
        storedtags = g_minimconfig.getindextags()
        for f in g_minimconfig.getitemtags():
            storedtags[f] = ""
        for v, d in storedtags:
            if v.lower() == "none":
                break
            fields.append(v.lower())
    except:
        pass
    return fields
