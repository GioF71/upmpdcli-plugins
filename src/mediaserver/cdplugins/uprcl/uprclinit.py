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

from upmplgutils import uplog, findmyip
from conftree import stringToStrings

# Once initialization (not on imports)
try:
    _s = g_httphp
except:
    # The recoll documents
    g_pathprefix = ""
    g_httphp = ""
    g_dblock = ReadWriteLock()
    g_rclconfdir = ""
    g_friendlyname = "UpMpd-mediaserver"
    g_trees = {}
    g_trees_order = ['folders', 'playlists', 'tags', 'untagged']
    g_minimconfig = None

def _reset_index():
    _update_index(True)
    
# Create or update Recoll index, then read and process the data.  This
# runs in the separate uprcl_init_worker thread, and signals
# startup/completion by setting/unsetting the g_initrunning flag
def _update_index(rebuild=False):
    uplog("Creating/updating index in %s for %s" % (g_rclconfdir, g_rcltopdirs))

    # We take the writer lock, making sure that no browse/search
    # thread are active, then set the busy flag and release the
    # lock. This allows future browse operations to signal the
    # condition to the user instead of blocking (if we kept the write
    # lock).
    global g_initrunning, g_trees
    g_dblock.acquire_write()
    g_initrunning = "Rebuilding" if rebuild else "Updating"
    g_dblock.release_write()
    uplog("_update_index: initrunning set")

    try:
        start = timer()
        uprclindex.runindexer(g_rclconfdir, g_rcltopdirs, rebuild=rebuild)
        # Wait for indexer
        while not uprclindex.indexerdone():
            time.sleep(.5)
        fin = timer()
        uplog("Indexing took %.2f Seconds" % (fin - start))

        folders = Folders(g_rclconfdir, g_httphp, g_pathprefix)
        untagged = Untagged(folders.rcldocs(), g_httphp, g_pathprefix)
        playlists = Playlists(folders.rcldocs(), g_httphp, g_pathprefix)
        tagged = Tagged(folders.rcldocs(), g_httphp, g_pathprefix)
        newtrees = {}
        newtrees['folders'] = folders
        newtrees['untagged'] = untagged
        newtrees['playlists'] = playlists
        newtrees['tags'] = tagged
        g_trees = newtrees
    finally:
        g_dblock.acquire_write()
        g_initrunning = False
        g_dblock.release_write()


# Initialisation runs in a thread because of the possibly long index
# initialization, during which the main thread can answer
# "initializing..." to the clients.
def _uprcl_init_worker():

    #######
    # Acquire configuration data.
    
    global g_pathprefix
    # pathprefix would typically be something like "/uprcl". It's used
    # for dispatching URLs to the right plugin for processing. We
    # strip it whenever we need a real file path
    if "UPMPD_PATHPREFIX" not in os.environ:
        raise Exception("No UPMPD_PATHPREFIX in environment")
    g_pathprefix = os.environ["UPMPD_PATHPREFIX"]
    if "UPMPD_CONFIG" not in os.environ:
        raise Exception("No UPMPD_CONFIG in environment")
    global g_friendlyname
    if "UPMPD_FNAME" in os.environ:
        g_friendlyname = os.environ["UPMPD_FNAME"]

    global g_upconfig
    g_upconfig = conftree.ConfSimple(os.environ["UPMPD_CONFIG"])

    global g_minimconfig
    minimcfn = g_upconfig.get("uprclminimconfig")
    g_minimconfig = minimconfig.MinimConfig(minimcfn)

    global g_httphp
    g_httphp = g_upconfig.get("uprclhostport")
    if g_httphp is None:
        ip = findmyip()
        g_httphp = ip + ":" + "9090"
        uplog("uprclhostport not in config, using %s" % g_httphp)

    global g_rclconfdir
    g_rclconfdir = g_upconfig.get("uprclconfdir")
    if g_rclconfdir is None:
        uplog("uprclconfdir not in config, using /var/cache/upmpdcli/uprcl")
        g_rclconfdir = "/var/cache/upmpdcli/uprcl"

    global g_rcltopdirs
    g_rcltopdirs = g_upconfig.get("uprclmediadirs")
    if not g_rcltopdirs:
        g_rcltopdirs = g_minimconfig.getcontentdirs()
        if g_rcltopdirs:
            g_rcltopdirs = conftree.stringsToString(g_rcltopdirs)
    if not g_rcltopdirs:
        raise Exception("uprclmediadirs not in config")

    pthstr = g_upconfig.get("uprclpaths")
    if pthstr is None:
        uplog("uprclpaths not in config, using topdirs: [%s]" % g_rcltopdirs)
        pthlist = stringToStrings(g_rcltopdirs)
        pthstr = ""
        for p in pthlist:
            pthstr += p + ":" + p + ","
        pthstr = pthstr.rstrip(",")
    uplog("Path translation: pthstr: %s" % pthstr)
    lpth = pthstr.split(',')
    pathmap = {}
    for ptt in lpth:
        l = ptt.split(':')
        pathmap[l[0]] = l[1]
        
    host,port = g_httphp.split(':')

    # Start the bottle app. Its' both the control/config interface and
    # the file streamer
    httpthread = threading.Thread(target=runbottle,
                                 kwargs = {'host':host ,
                                           'port':int(port),
                                           'pthstr':pthstr,
                                           'pathprefix':g_pathprefix})
    httpthread.daemon = True 
    httpthread.start()

    _update_index()

    uplog("Init done")


def uprcl_init():
    global g_initrunning
    g_initrunning = True
    initthread = threading.Thread(target=_uprcl_init_worker)
    initthread.daemon = True 
    initthread.start()

def ready():
    g_dblock.acquire_read()
    if g_initrunning:
        return False
    else:
        return True

def updaterunning():
    return g_initrunning

def start_update(rebuild=False):
    try:
        if not ready():
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
