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

# Manage the 'untagged' section of the tree.  Our selection is made of
# all tracks without a 'title' field. This is different from what
# Minimserver does (I think that more or less any field present makes
# a track not untagged for minim).
#
# Initialization filters the untagged tracks and creates a vector of
# indexes into the global doc vector.
#
# Object Id prefix: 0$uprcl$untagged
# 
# Obect id inside the section: $u<idx> where <idx> is the document index
#  inside the global document vector.

import os
import shlex
import sys

from upmplgutils import uplog, direntry
from uprclutils import rcldoctoentry
import uprclinit

class Untagged(object):
    def __init__(self, rcldocs, httphp, pathprefix):
        self._idprefix = '0$uprcl$untagged'
        self._httphp = httphp
        self._pprefix = pathprefix
        self.recoll2untagged(rcldocs)
        
    # Create the untagged entries static vector by filtering the global
    # doc vector, storing the indexes of all tracks without a title
    # field. We keep a reference to the doc vector.
    def recoll2untagged(self, rcldocs):
        # The -1 entry is because we use index 0 for our root.
        self.utidx = [-1]
    
        for docidx in range(len(rcldocs)):
            doc = rcldocs[docidx]
            if doc["mtype"] == 'inode/directory' or \
               doc["mtype"] == 'audio/x-mpegurl':
                continue
            if not doc["title"]:
                self.utidx.append(docidx)

    # Compute index into our entries vector by 'parsing' the objid.
    def _objidtoidx(self, pid):
        if not pid.startswith(self._idprefix):
            raise Exception("untagged:browse: bad pid %s" % pid)

        idx = pid[len(self._idprefix):]
        if not idx:
            # Browsing the root.
            idx = 0
        else:
            if idx[1] != 'u':
                raise Exception("untagged:browse: called on bad objid %s" % pid)
            idx = int(idx[2:])
    
        if idx >= len(self.utidx):
            raise Exception("untagged:browse: bad pid %s" % pid)

        return idx

    # Return entry to be created in the top-level directory ([untagged]).
    def rootentries(self, pid):
        return [direntry(pid + 'untagged', pid, '[untagged]'),]


    # Browse method
    # objid is like untagged$u<index>
    # flag is meta or children.
    def browse(self, pid, flag, offset, count):
        idx = self._objidtoidx(pid)

        entries = []
        rcldocs = uprclinit.getTree('folders').rcldocs()
        if idx == 0:
            # Browsing root
            for i in range(len(self.utidx))[1:]:
                doc = rcldocs[self.utidx[i]]
                id = self._idprefix + '$u' + str(i)
                e = rcldoctoentry(id, pid, self._httphp, self._pprefix, doc)
                if e:
                    entries.append(e)
        else:
            # Non root: only items in there. flag needs to be 'meta'
            doc = rcldocs[idx]
            id = self._idprefix + '$u' + str(idx)
            e = rcldoctoentry(id, pid, self._httphp, self._pprefix, doc)
            if e:
                entries.append(e)

        return sorted(entries, key=lambda entry: entry['tt'].lower())
