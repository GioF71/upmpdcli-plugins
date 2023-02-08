#!/usr/bin/python3
#
# Copyright (C) 2023 J.F.Dockes
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
import json
import re
import cmdtalkplugin
import conftree

import pyradios
from pyradios import facets

from upmplgutils import uplog, setidprefix, direntry

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = "0$radio-browser$"
setidprefix("radio-browser")

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

_g_rb = None
def _initradios():
    global _g_rb
    if not _g_rb:
        _g_rb = pyradios.RadioBrowser()


def _radiotoentry(pid, id, radio):
    #uplog(f"radioToEntry: pid {pid} id {id} radio {radio}")
    # if this comes from a 'browse meta', the id is set, else compute it
    if id is None:
        objid = pid
        if objid[-1] != "$":
            objid += "$"
        objid += str(radio["stationuuid"])
    else:
        objid = id

    mime = "audio/mpeg"
    if "codec" in radio:
        if radio["codec"].lower() == "flac":
            mime = "audio/flac"
        elif radio["codec"].lower().find("aac") == 0:
            mime = "audio/aac"
        elif radio["codec"].lower() == "ogg":
            mime = "audio/ogg"
    else:
        mime = "audio/mpeg"
    entry = {
        'pid': pid,
        'id': objid,
        'uri': radio["url_resolved"],
        'tp': 'it',
        'res:mime': mime,
        'upnp:class': 'object.item.audioItem.audioBroadcast',
        'upnp:album': radio["codec"] if "codec" in radio else "Unknown",
        'tt': radio["name"],
        # This is for Kodi mostly, to avoid displaying a big "Unknown" placeholder
        'upnp:artist': "Internet Radio"
    }
    if "favicon" in radio:
        entry["upnp:albumArtURI"] = radio["favicon"]
    return entry


@dispatcher.record('trackuri')
def trackuri(a):
    # We generate URIs which directly point to the radio, so this
    # method should never be called.
    raise Exception("trackuri: should not be called for radio-browser!")


def _returnentries(entries):
    return {"entries" : json.dumps(entries), "nocache" : "0"}

@dispatcher.record('browse')
def browse(a):
    msgproc.log(f"browse: args: --{a}--")
    _initradios()
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']

    if objid.find(_g_myprefix) != 0:
        raise Exception(f"radio-browser: bad objid {objid}: bad prefix")
    path = objid[len(_g_myprefix):].lstrip("/")
    #uplog(f"path: [{path}]")

    entries = []
    bflg = a['flag'] if 'flag' in a else 'children'
    if bflg == 'meta':
        # not for now. Only Kodi does this.
        if path.find("$"):
            entries = [_radiotoentry({"name": "name", "url_resolved": "http://google.com"}),]
        else:
            entries = [direntry(id, objid, "forkodi"),]
        return _returnentries(entries)


    if path:
        lpath = path.split("/")
    else:
        lpath = []

    # Compute the filtering criteria from the path
    crits = {}
    filterargs = {}
    crit = None
    value = None
    argtrans = {"tags": "tag", "countrycodes": "countrycode", "languages": "language"}
    for idx in range(len(lpath)):
        if idx & 1:
            continue
        crit = lpath[idx]
        if idx < len(lpath)-1:
            value = lpath[idx+1]
            crits[crit] = value
            filterargs[argtrans[crit]] = value
        else:
            value = None
            break
 
    # At this point we have a possibly empty dict of tagname->value filters (crits) and a possibly
    # None value for the last tagname (the latter indicating that we want a list of possible
    # values).
    #uplog(f"crits [{crits}] crit [{crit}] value [{value}]")
    if crit:
        filter = facets.RadioFacets(_g_rb, **filterargs)
    else:
        filter = None

    if value is None:
        # Get the list of possible values for the tagname
        if crit is None:
            # Top level: path was empty. Just show tagnames
            values = ("countrycodes", "languages", "tags")
        elif crit == "countrycodes":
            values = filter.countrycodes
            values = [entry["name"] for entry in values]
        elif crit == "languages":
            values = filter.languages
            values = [entry["name"] for entry in values]
        elif crit == "tags":
            values = filter.tags
            values = [entry["name"] for entry in values]
        elif crit == "radios":
            # Path ending with "radios" means that we want the list of possible radios matching the
            # filter.
            for radio in filter.result:
                entries.append(_radiotoentry(objid, None, radio))
            return _returnentries(entries)
        else:
            raise(Exception(f"Bad objid {objid} (bad tagname [{crit}])"))
        for value in values:
            if value:
                id = objid + "/" + value
                entries.append(direntry(id, objid, value))
    else:
        # Path ends with tag value. List the remaining tagnamescriteria.
        for tagname in ("countrycodes", "languages", "tags"):
            if not tagname in crits:
                id = objid + "/" + tagname
                entries.append(direntry(id, objid, tagname))
    # Link to the available radios at this stage. We don't build the filter, so don't 
    # have data here at the top level (don't want to show 30k radios).
    if filter:
        entries.append(direntry(objid + "/radios", objid, f"{len(filter.result)} radios"))

    # msgproc.log(f"browse: returning --{entries}--")
    return _returnentries(entries)


@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    pid = a["objid"]
    _initradios()
    sstr = a["value"]
    result = _g_rb.search(name=sstr)
    #uplog(f"SEARCH RESULT for [{sstr}]: {result}")
    entries = []
    for radio in result:
        entries.append(_radiotoentry(pid, None, radio))
    return _returnentries(entries)


msgproc.mainloop()
