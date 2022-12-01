#!/usr/bin/python3
#
# Copyright (C) 2021 J.F.Dockes
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

from upmplgutils import uplog, setidprefix
import upradioconf

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = "0$upradios$"
setidprefix("upradios")

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

def _initradios():
    if "UPMPD_CONFIG" not in os.environ:
        raise Exception("No UPMPD_CONFIG in environment")
    config = conftree.ConfSimple(os.environ["UPMPD_CONFIG"], casesensitive=False)
    global _g_radios
    _g_radios = upradioconf.UpmpdcliRadios(config)
    
@dispatcher.record('trackuri')
def trackuri(a):
    # We generate URIs which directly point to the radio, so this
    # method should never be called.
    raise Exception("trackuri: should not be called for upradios!")


@dispatcher.record('browse')
def browse(a):
    #msgproc.log(f"browse: args: --{a}--")
    if 'objid' not in a:
        raise Exception("No objid in args")
    # Note: objid should either be our root or a radio id, which we don't check.
    objid = a['objid']
    
    entries = []
    bflg = a['flag'] if 'flag' in a else 'children'
    if bflg == 'meta':
        try:
            pid = _g_myprefix
            idx = upradioconf.radioIndexFromId(objid)
            entries.append(upradioconf.radioToEntry(pid, objid, _g_radios.get_radio(idx)))
        except:
            pass
    else:
        for radio in _g_radios:
            entries.append(upradioconf.radioToEntry(objid, None, radio))

    encoded = json.dumps(entries)
    # msgproc.log(f"browse: returning --{entries}--")
    return {"entries" : encoded, "nocache" : "0"}


@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    return {"entries" : [], "nocache" : "0"}


_initradios()

msgproc.mainloop()
