#!/usr/bin/env python3
#
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

from __future__ import print_function
import sys
import os
import json
import re
import cmdtalkplugin

import uprclsearch
import uprclindex

from upmplgutils import uplog, setidprefix
from uprclutils import waitentry
import uprclinit

setidprefix("uprcl")

#####
# Initialize communication with our parent process: pipe and method
# call dispatch

# Some of the modules we use write garbage to stdout, which messes the communication with our
# parent. Why can't people understand that this is verboten ? So we dup stdout and close it, then
# pass the right file to cmdtalk.  (hoping that none of the imports above print anything, else we'll
# have to move this code up)
_outfile = os.fdopen(os.dup(1), "w")
os.close(1)
fd = os.open("/dev/null", os.O_WRONLY)
# print("UPRCL-APP: got fd %d for /dev/null" % fd, file=sys.stderr)


# The normal system exit gets stuck on waiting for the bottle
# thread. We have nothing to really cleanup, so set up forced exit
# handler
def doexit(val):
    os._exit(val)


# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher, outfile=_outfile, exitfunc=doexit)


@dispatcher.record("trackuri")
def trackuri(a):
    # This is used for plugins which generate temporary local urls
    # pointing to the microhttpd instance. The microhttpd
    # answer_to_connection() routine in plgwithslave calls 'trackuri'
    # to get a real URI to redirect to. We generate URIs which
    # directly point to our python http server, so this method should
    # never be called.
    msgproc.log("trackuri: [%s]" % a)
    raise Exception("trackuri: should not be called for uprcl!")


# objid prefix to module map
rootmap = {}


def _rootentries():
    # Build up root directory. This is our top internal structure. We
    # let the different modules return their stuff, and we take note
    # of the objid prefixes for later dispatching
    entries = []
    for treename in uprclinit.getTreesOrder():
        nents = uprclinit.getTree(treename).rootentries(uprclinit.getObjPrefix())
        for e in nents:
            rootmap[e["id"]] = treename
        entries += nents
    uplog("Browse root: rootmap now %s" % rootmap)
    return entries


def _browsedispatch(objid, bflg, offset, count):
    for id, treename in rootmap.items():
        # uplog("Testing %s against %s" % (objid, id))
        if objid.startswith(id):
            return uprclinit.getTree(treename).browse(objid, bflg, offset, count)
    raise Exception("Browse: dispatch: bad objid not in rootmap: [%s]" % objid)


def _checkobjid(a):
    if "objid" not in a:
        raise Exception("No objid in args")
    objid = a["objid"]
    if not objid.startswith(uprclinit.getObjPrefix()):
        raise Exception(f"Bad objid <{objid}>")
    return objid

@dispatcher.record("browse")
def browse(a):
    msgproc.log(f"browse: httphp [{uprclinit.getHttphp()}]   ARGS {a}")
    objid = _checkobjid(a)

    bflg = a["flag"] if "flag" in a else "children"

    offset = 0
    if "offset" in a:
        offset = int(a["offset"])
    count = 0
    if "count" in a:
        count = int(a["count"])


    idpath = objid.replace(uprclinit.getObjPrefix(), "", 1)

    entries = []

    # 2026-08: cache used to be disabled (2018, c8031a0d) with comment "we're fast enough"
    # However this does not hold true in the case where the client is reading small slices of a
    # big result which we end up calculating each time, because we don't heed offset and count
    # at the moment: none of the submodules (folders, tags, etc.) uses slices. It's not obvious
    # anyway what performance gain we could obtain.
    # So reenable caching in our c++ parent.
    nocache = "0"
    try:
        if not uprclinit.initdone():
            # initdone() acquires the readlock
            entries = [
                waitentry(objid + "notready", objid, uprclinit.getHttphp()),
            ]
        else:
            initstatus, initmessage = uprclinit.initstatus()
            if not initstatus:
                entries = [
                    waitentry(
                        objid + "notready",
                        objid,
                        uprclinit.getHttphp(),
                        "Uprcl init error: " + initmessage,
                    ),
                ]
            else:
                if not idpath:
                    entries = _rootentries()
                else:
                    if len(rootmap) == 0:
                        _rootentries()
                    entries = _browsedispatch(objid, bflg, offset, count)
    finally:
        uprclinit.g_dblock.release_read()

    # Note (2026-08): the provision for a partial list is not used (by
    # any submodule) at the moment.
    if type(entries) == type(()):
        resoffs = entries[0]
        total = entries[1]
        entries = entries[2]
    else:
        resoffs = 0
        total = len(entries)
    # msgproc.log("%s" % entries)
    encoded = json.dumps(entries)
    return {"entries": encoded, "nocache": nocache, "offset": str(resoffs), "total": str(total)}


@dispatcher.record("search")
def search(a):
    msgproc.log("search: [%s]" % a)
    objid = _checkobjid(a)

    upnps = a["origsearch"]

    # 08/26: See comment in browse.
    nocache = "0"

    try:
        if not uprclinit.initdone():
            entries = [
                waitentry(objid + "notready", objid, uprclinit.getHttphp()),
            ]
        else:
            initstatus, initmessage = uprclinit.initstatus()
            if not initstatus:
                entries = [
                    waitentry(
                        objid + "notready",
                        objid,
                        uprclinit.getHttphp(),
                        "Uprcl init error: " + initmessage,
                    ),
                ]
            else:
                entries = uprclsearch.search(
                    uprclinit.getTree("folders"),
                    uprclinit.getRclConfdir(),
                    objid,
                    upnps,
                    uprclinit.getObjPrefix(),
                    uprclinit.getHttphp(),
                    uprclinit.getPathPrefix(),
                )
    finally:
        uprclinit.g_dblock.release_read()

    encoded = json.dumps(entries)
    return {"entries": encoded, "nocache": nocache, "offset": "0", "total": str(len(entries))}


uprclinit.uprcl_init()
msgproc.log("Uprcl running")
msgproc.mainloop()
