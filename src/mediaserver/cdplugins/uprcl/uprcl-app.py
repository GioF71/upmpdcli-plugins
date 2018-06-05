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
from uprclutils import uplog, g_myprefix, rcldirentry, waitentry
import uprclinit

setidprefix("uprcl")

#####
# Initialize communication with our parent process: pipe and method
# call dispatch

# Some of the modules we use write garbage to stdout, which messes the
# communication with our parent. Why can't people understand that this
# is verboten ? Get off my lawn ! So we dup stdout and close it, then
# pass the right file to cmdtalk.  (hoping that none of the imports
# above print anything, else we'll have to move this code up)
_outfile = os.fdopen(os.dup(1), "w")
os.close(1)
fd = os.open("/dev/null", os.O_WRONLY)
# print("UPRCL-APP: got fd %d for /dev/null" % fd, file=sys.stderr)

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher, outfile=_outfile)

@dispatcher.record('trackuri')
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
    for treename in uprclinit.g_trees_order:
        nents = uprclinit.g_trees[treename].rootentries(g_myprefix)
        for e in nents:
            rootmap[e['id']] = treename
        entries += nents
    uplog("Browse root: rootmap now %s" % rootmap)
    return entries


def _browsedispatch(objid, bflg):
    for id,treename in rootmap.items():
        #uplog("Testing %s against %s" % (objid, id))
        if objid.startswith(id):
            return uprclinit.g_trees[treename].browse(objid, bflg)
    raise Exception("Browse: dispatch: bad objid not in rootmap: " + objid)


@dispatcher.record('browse')
def browse(a):
    msgproc.log("browse: %s. g_httphp [%s]" % (a, uprclinit.g_httphp))
    if 'objid' not in a:
        raise Exception("No objid in args")

    objid = a['objid']
    bflg = a['flag'] if 'flag' in a else 'children'
    
    if not objid.startswith(g_myprefix):
        raise Exception("bad objid <%s>" % objid)

    idpath = objid.replace(g_myprefix, '', 1)
    msgproc.log("browse: idpath: <%s>" % idpath)


    entries = []
    nocache = "0"
    if bflg == 'meta':
        raise Exception("uprcl-app: browse: can't browse meta for now")
    else:
        try:
            if not uprclinit.ready():
                entries = [waitentry(objid + 'notready', objid,
                                     uprclinit.g_httphp),]
                nocache = "1"
            elif not idpath:
                entries = _rootentries()
            else:
                entries = _browsedispatch(objid, bflg)
        finally:
            uprclinit.g_dblock.release_read()

    #msgproc.log("%s" % entries)
    encoded = json.dumps(entries)
    return {"entries" : encoded, "nocache":nocache}


@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    objid = a['objid']
    if re.match('0\$uprcl\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)

    upnps = a['origsearch']
    nocache = "0"

    try:
        if not uprclinit.ready():
            entries = [waitentry(objid + 'notready', objid,
                                 uprclinit.g_httphp),]
            nocache = "1"
        else:
            entries = uprclsearch.search(
                uprclinit.g_trees['folders'], uprclinit.g_rclconfdir, objid,
                upnps, g_myprefix, uprclinit.g_httphp, uprclinit.g_pathprefix)
    finally:
        uprclinit.g_dblock.release_read()

    encoded = json.dumps(entries)
    return {"entries" : encoded, "nocache":nocache}


uprclinit.uprcl_init()
msgproc.log("Uprcl running")
msgproc.mainloop()
