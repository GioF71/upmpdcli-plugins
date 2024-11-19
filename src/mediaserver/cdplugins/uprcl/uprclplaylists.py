#
# Copyright (C) 2019-2022 J.F.Dockes
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

# Manage the playlists section of the tree
#
# Object Id prefix: 0$uprcl$playlists
#
# Obect id inside the section: $p<idx> where <idx> is the document index
#  inside the global document vector.

import os, sys, subprocess

from upmplgutils import uplog, direntry, getOptionValue, getConfigObject
from uprclutils import rcldoctoentry, cmpentries
import uprclutils
import uprclinit
from recoll import recoll
import conftree
import upradioconf


class Playlists(object):
    def __init__(self, rclconfdir, rcldocs, httphp, pathprefix):
        self.rclconfdir = rclconfdir
        self._idprefix = "0$uprcl$playlists"
        self._pprefix = pathprefix
        uplog(f"PLAYLISTS pprefix {self._pprefix} idprefix {self._idprefix}")
        self._httphp = httphp
        self._rcldocs = rcldocs
        self.recoll2playlists()
        self._radios = []
        radiolistid = self._idprefix + "$p" + str(len(self._pldocsidx))
        if not conftree.valToBool(getOptionValue("uprclnoradioconf")):
            radios = upradioconf.UpmpdcliRadios(getConfigObject())
            for radio in radios:
                self._radios.append(upradioconf.radioToEntry(radiolistid, None, radio))

    # Return entry to be created in the top-level directory ([playlists]).
    def rootentries(self, pid):
        return [
            direntry(pid + "playlists", pid, str(len(self._pldocsidx)) + " playlists"),
        ]

    # Create the playlists static vector by filtering the global doc vector, storing the indexes of
    # the playlists.
    def recoll2playlists(self):
        # The -1 entry is because we use index 0 for our root.
        self._pldocsidx = [
            -1,
        ]
        for docidx in range(len(self._rcldocs)):
            doc = self._rcldocs[docidx]
            if doc["mtype"] == "audio/x-mpegurl":
                self._pldocsidx.append(docidx)

    # Compute index into our entries vector by 'parsing' the objid which is like
    # {_idprefix}$pPn[$e]En Pn and En are idx0 and idx1
    # idx0==0 -> our root. idx0 == len(ourlist) is valid too and does not point to an rcldoc built
    # from an actual playlist file, but to our internal radio playlist
    def _objidtoidx(self, objid):
        # uplog("playlists:objidtoidx: %s" % objid)
        if not objid.startswith(self._idprefix):
            raise Exception(f"playlists:browse: bad objid prefix in {objid}")
        # path is like $p{idx0} or $p{idx0}$e{idx1}
        path = objid[len(self._idprefix) :]
        idx1 = -1
        if not path:
            # Browsing the root.
            idx0 = 0
        else:
            if path[1] != "p":
                raise Exception(f"playlists:browse: bad objid {objid} path {path} no $p")
            epos = path.find("$e")
            if epos != -1:
                idx0 = int(path[2:epos])
                idx1 = int(path[epos + 2 :])
            else:
                idx0 = int(path[2:])
        if idx0 > len(self._pldocsidx):
            raise Exception(f"playlists:browse: bad objid {objid} idx0 {idx0} not in range")
        return idx0, idx1

    def _idxtoentry(self, idx):
        upnpclass = "object.container.playlistContainer"
        id = self._idprefix + "$p" + str(idx)
        if idx == len(self._pldocsidx):
            title = "*Upmpdcli Radios*"
        elif idx >= 1 and idx < len(self._pldocsidx):
            doc = self._rcldocs[self._pldocsidx[idx]]
            title = doc["title"] if doc["title"] else doc["filename"]
        else:
            return None
        return direntry(id, self._idprefix, title, upnpclass=upnpclass)

    # Return the contents of the playlist at index idx
    def _playlistatidx(self, idx):
        # uplog(f"playlistatidx: idx {idx}")
        rcldb = recoll.connect(confdir=self.rclconfdir)
        pldoc = self._rcldocs[self._pldocsidx[idx]]
        plpath = uprclutils.docpath(pldoc)
        folders = uprclinit.getTree("folders")
        # uplog("playlists: plpath %s" % plpath)
        entries = []
        try:
            m3u = uprclutils.M3u(plpath)
        except Exception as ex:
            uplog("M3u open failed: %s %s" % (plpath, ex))
            return entries
        cnt = 1
        for url in m3u:
            if m3u.urlRE.match(url):
                # Actual URL (usually http). Create bogus doc
                doc = folders.docforurl(rcldb, url)
            else:
                docidx = folders.statpath(rcldb, plpath, url)
                if not docidx:
                    continue
                doc = self._rcldocs[docidx]

            pid = self._idprefix + "$p" + str(idx)
            id = pid + "$e" + str(len(entries))
            e = rcldoctoentry(id, pid, self._httphp, self._pprefix, doc)
            if e:
                entries.append(e)
        # uplog(f"playlistatidx: idx {idx} -> {entries}")
        return entries

    # Browse method
    # objid is like {_idprefix}$p<idx0> or {_idprefix}$p<idx0>$e<idx1> (meta only)
    # flag is meta or children.
    def browse(self, pid, flag, offset, count):
        uplog(f"uprclplaylists: browse: pid {pid} flag {flag}")
        idx0, idx1 = self._objidtoidx(pid)

        if flag == "meta":
            if idx0 == 0:
                return self.rootentries(self, self._idprefix)
            elif idx0 < len(self._pldocsidx):
                if idx1 == -1:
                    return [
                        self._idxtoentry(idx0),
                    ]
                else:
                    entries = self._playlistatidx(idx0)
                    if idx1 >= 0 and idx1 < len(entries):
                        return [
                            entries[idx1],
                        ]
            elif idx0 == len(self._pldocsidx):
                if idx1 == -1:
                    return [
                        self._idxtoentry(idx0),
                    ]
                else:
                    if idx1 > 0 and idx1 < len(self._radios):
                        return [
                            self._radios[idx1],
                        ]
            return []

        # Browsing children
        entries = []
        if idx0 == 0:
            # Browsing root. Return contents
            # Regular playlist entries, from our doc list.
            for i in range(len(self._pldocsidx))[1:]:
                entries.append(self._idxtoentry(i))
            # Special entry for our radio list. The id is 1 beyond valid playlist ids
            entries.append(self._idxtoentry(len(self._pldocsidx)))
        elif idx0 == len(self._pldocsidx):
            # Browsing the radio list
            entries = self._radios
        else:
            entries = self._playlistatidx(idx0)

        return entries
