#!/usr/bin/python3
#
# Copyright (C) 2017-2019 J.F.Dockes
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU Lesser General Public License as published by
#   the Free Software Foundation; either version 2.1 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public License
#   along with this program; if not, write to the
#   Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


# This is imported from rclaudio when the audiotagfixerscript variable
# is set in the recoll configuration (uprcl sets it). It then operates
# transformations on audio tag sets, as prescribed in the minimserver
# configuration, which is pointed to by the uprclminimconfig upmpdcli
# configuration variable.

import sys
import os

import conftree
import minimconfig

def uplog(s):
    if not type(s) == type(b''):
        s = ("%s: %s" % ('uprcl:minimtagfixer', s)).encode('utf-8')
    sys.stderr.buffer.write(s + b'\n')
    sys.stderr.flush()


_logfp = None
def _logchange(s):
    if _logfp:
        print("%s" % s, file=_logfp)
        _logfp.flush()
    else:
        uplog(s)


class TagUpdateData(object):
    def __init__(self):
        self.tgupfile = None
        upconfig = conftree.ConfSimple(os.environ["UPMPD_CONFIG"])
        self.tgupfile = None
        self.aliastags = None

        self.minimcnffn = upconfig.get("uprclminimconfig")
        if not self.minimcnffn:
            return

        self.minimconfig = minimconfig.MinimConfig(self.minimcnffn)
        self.tgupfile = self.minimconfig.getsimplevalue("minimserver.tagUpdate")
        #uplog("Minim config read: tagUpdate: %s" % self.tgupfile)
        self.tgupfile = self._makeabs(self.tgupfile)
        if not os.path.exists(self.tgupfile):
            uplog("gettagupdate: %s does not exist" % self.tgupfile)
            return
        wlogfn = self.minimconfig.getsimplevalue("minimserver.writeTagChanges")
        wlogfn = self._makeabs(wlogfn)
        #uplog("gettagupdate: log file: %s" % wlogfn)
        if wlogfn:
            global _logfp
            try:
                _logfp = open(wlogfn, "a")
            except Exception as ex:
                uplog("can't open %s : %s" % (wlogfn, ex))
        self.aliastags = self.minimconfig.getaliastags()
        self.tagvalue = self.minimconfig.gettagvalue()

    # The defs and log files are to be found in the same dir as the
    # logs (see minim doc). So compute minimserver/etc/xx.conf/../../data/fn
    # This probably only works for linux
    def _makeabs(self, fn):
        if not fn: return fn
        if not os.path.isabs(fn):
            dir = os.path.dirname(os.path.dirname(self.minimcnffn))
            fn = os.path.join(os.path.join(dir, "data"), fn)
        return fn


    # https://minimserver.com/ug-other.html#Tag%20update
    # Tag value replacement specs, e.g. "Johann Sebastian Bach" -> "Bach J.S."
    def gettagupdate(self):
        if not self.tgupfile:
            return ()
        try:
            f = open(self.tgupfile, 'rb')
        except Exception as ex:
            uplog("gettagupdate: can't open %s for reading: %s" %
                  (self.tgupfile,ex))
            return

        groups = []
        seltags = []
        filtertags = []
        tagadds = []
        tagdels = []
        seltagsdone = False
        for line in f.readlines():
            line = line.strip().decode('utf-8')
            if not line or line[0] not in \
                   ("@"[0], "&"[0], "="[0], "-"[0], "+"[0]):
                #uplog("gettaupdate: skipping [%s]" % line)
                continue

            if line[0] != "@"[0]:
                seltagsdone = True

            # Regularise:
            if line[0] == "-" and line[-1] != "="[0]:
                line += "="
            # Compute tag and value
            eq = line[1:].find("=")
            tagname = line[1:eq+1].strip().lower()
            tagval = line[eq+2:].strip().encode('utf-8')
            #uplog("gettaupdate: tagname [%s] tagval [%s]"%(tagname,tagval))

            if line[0] == "@"[0]:
                if seltagsdone:
                    # We've already seen @tag(s) and at least one
                    # other directive, this group is done, finalize it
                    # before beginning the next
                    groups.append((seltags, filtertags, tagadds, tagdels))
                    seltags = []
                    filtertags = []
                    tagadds = []
                    tagdels = []
                    seltagsdone = False
                seltags.append((tagname, tagval))
            elif line[0] == "&"[0]:
                filtertags.append((tagname, tagval))
            elif line[0] == "="[0]:
                tagadds.append((tagname, tagval))
            elif line[0] == "-"[0]:
                tagdels.append((tagname,''))
            elif line[0] == "+"[0]:
                tagadds.append((tagname, tagval))
            
        if seltagsdone:
            groups.append((seltags, filtertags, tagadds, tagdels))

        return groups


tud = TagUpdateData()
groups = tud.gettagupdate()
#uplog("minimtagfixer: groups %s" % groups)

def tagupdate(tags):
    for group in groups:
        # Must match at least one element of group[0]
        sel = False
        for tag,val in group[0]:
            if tag in tags and tags[tag] == val:
                sel = True
                break
        if not sel:
            return
        # Must match all in group[1]
        for tag,val in group[1]:
            if not tag in tags or tags[tag] != val:
                sel = False
        if not sel:
            return
        # Apply adds/mods
        for tag,val in group[2]:
            old = tags[tag] if tag in tags else ""
            _logchange("Setting [%s] from [%s] to [%s]" % (tag, old, val))
            tags[tag] = val
        # Apply dels
        for tag,val in group[3]:
            _logchange("Clearing [%s]" % tag)
            del tags[tag]


def tagvalue(tags):
    pass


def aliastags(tags):
    if tud.aliastags:
        for orig, target, rep in tud.aliastags:
            try:
                val = tags[orig]
                #uplog("aliastags: Rep %s tags[%s]=[%s] tags[%s]=[%s]"%
                #      (rep, orig, val, target, tags[target]))
                if val and (rep or not tags[target]):
                    #uplog("tags[%s] -> %s" % (target,val))
                    tags[target] = val
            except:
                pass


def tagfix(tags={}):
    #uplog("tagfix(%s)"%tags)
    tagvalue(tags)
    aliastags(tags)
    tagupdate(tags)
