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

# Manage the [folders] section of the tree.
#
# Object Id prefix: 0$uprcl$folders
# 
# Data structure:
#
# The _rcldocs list has one entry for each document in the index (mime:* search)
#
# The _dirvec list has one entry for each directory. Directories are
# created as needed by splitting the paths/urls from _rcldocs (and
# possibly adding some for groupings defined by the Group
# tag). Directories have no direct relation with the index objects,
# they are identified by their _dirvec index
#
# Obect ids inside the section:
#    Container: $d<diridx> where <diridx> indexes into _dirvec
#    Item: $i<docidx> where <docidx> indexes into _rcldocs
#
# Note: this is very different from what Minim does. Minim uses actual
#   objid paths as objids. E.g. 0$folders$f1589$f1593$f1604$*i11609
#   Must make pwd and any walk up the tree much easier.
#
# Each _dirvec entry is a Python dict, mapping the directory entries'
# names to a pair (diridx,docidx), where:
#
#  - diridx is an index into _dirvec if the name is a directory, else -1
#  - docidx is an index into _rcldocs, or -1 if:
#     - There is no _rcldocs entry, which could possibly happen if
#       there is no result for an intermediary element in a path,
#       because of some recoll issue, or because this is a synthetic
#       'Group' entry.
#     - Or, while we build the structure, temporarily, if the doc was
#       not yet seen. The value will then be updated when we see it.
#
# Note: docidx is usually set in the pair for a directory, but I don't
# think that it is ever used. The Recoll doc for a directory has
# nothing very interesting in it.
#
# Note: We could probably use a single value, with a convention
# saying, e.g., that > 0 is for docs and < -1 for folders. Check if
# this saves a significant amount of memory.
#
# Each directory has a special ".." entry with a diridx pointing to
# the parent directory. This allows building a path from a container
# id (aka pwd).
#
# Only playlists have a "." entry (needed during init)
# 
# Entry 0 in _dirvec is special: it holds the 'topdirs' from the recoll
# configuration. The entries are paths instead of simple names, and
# the docidx is 0. The diridx points to a dirvec entry.
#
# We also build an _xid2idx xdocid->objidx map to allow a Recoll
# item search result to be connected back to the folders tree.
# I'm not sure that this is at all useful (bogus objids for items in
# search results are quite probably ok). Also quite probably, this
# could also be done using the URL, as it is what we use to build the
# folders tree in the first place.
# _xid2idx is currently desactivated (see comment)

import os
import shlex
import sys
import time
from timeit import default_timer as timer

from upmplgutils import uplog, direntry, getOptionValue
from uprclutils import audiomtypes, rcldoctoentry, cmpentries
import uprclutils
from recoll import recoll
try:
    from recoll import qresultstore
    _has_resultstore = True
except:
    _has_resultstore = False
uprclutils.sethasresultstore(_has_resultstore)

from recoll import rclconfig
import uprclinit

# All Doc fields which we may want to access (reserve slots in the
# resultstore). We use an inclusion list, and end up with a smaller
# store than by using an exclusion list, but it's a bit more difficult
# to manage.
#
# +  possibly 'xdocid' and/or 'rcludi' if/when needed?
#
_otherneededfields = [
    'albumartist', 'allartists', 'comment', 'composer', 'conductor',
    'contentgroup', 'date', 'dmtime', 'discnumber', 'embdimg', 'filename',
    'genre', 'group', 'label', 'lyricist', 'orchestra', 'performer',
]

class Folders(object):

    # Initialize (read recoll data and build tree).
    def __init__(self, confdir, httphp, pathprefix):
        self._idprefix = '0$uprcl$folders'
        self._httphp = httphp
        self._pprefix = pathprefix
        # Debug : limit processed recoll entries for speed
        self._maxrclcnt = 0
        # Overflow storage for synthetic records created for playlists
        # url entries. Uses docidx values starting at len(_rcldocs),
        # with actual index value - len(_rcldocs)
        self._moredocs = []
        self._fetchalldocs(confdir)
        self._rcl2folders(confdir)
        self._enabletags = uprclinit.g_minimconfig.getboolvalue("showExtras", True)
        self._notagview = getOptionValue("uprclnotagview", False)
        
    def rcldocs(self):
        return self._rcldocs
    

    # Create new directory entry: insert in father and append dirvec slot
    # (with ".." entry)
    def _createdir(self, fathidx, docidx, nm):
        self._dirvec.append({})
        thisidx = len(self._dirvec) - 1
        self._dirvec[fathidx][nm] = (thisidx, docidx)
        self._dirvec[-1][".."] = (fathidx, -1)
        self._dirvec[-1]["."] = (thisidx, docidx)
        return len(self._dirvec) - 1


    # Create directory for playlist. Create + populate. The docs which
    # are pointed by the playlist entries may not be in the tree yet,
    # so we don't know how to find them (can't walk the tree yet).
    # Just store the diridx and populate all playlists at the end
    def _createpldir(self, fathidx, docidx, doc, nm):
        myidx = self._createdir(fathidx, docidx, nm)
        # We need a "." entry
        self._dirvec[myidx]["."] = (myidx, docidx)
        self._playlists.append(myidx)
        return myidx
    

    # Find the doc index for a filesystem path.
    # We use a temporary doc to call _stat()
    def statpath(self, plpath, path):
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(plpath), path)
        doc = recoll.Doc()
        if _has_resultstore:
            doc["url"] = b'file://' + path
        else:
            doc.setbinurl(bytearray(b'file://' + path))
        fathidx, docidx = self._stat(doc)
        if docidx >= 0 and docidx < len(self._rcldocs):
            return docidx
        uplog("No track found for playlist %s entry %s" % (plpath, path))
        return None


    # Create bogus doc for external (http) url. This is for playlists.
    def docforurl(self, url):
        doc = recoll.Doc()
        doc.url = url
        elt = os.path.split(url)[1]
        tt = elt.decode('utf-8', errors='ignore')
        doc.title = tt
        # Temp workaround for recoll 1.28.2 not setting values in meta
        doc.text = tt
        doc.mtype = "audio/mpeg"
        return doc
    

    # Initialize all playlists after the tree is otherwise complete
    def _initplaylists(self):
        for diridx in self._playlists:
            pldocidx = self._dirvec[diridx]["."][1]
            pldoc = self._rcldocs[pldocidx]
            plpath = uprclutils.docpath(pldoc)
            try:
                m3u = uprclutils.M3u(plpath)
            except Exception as ex:
                uplog("M3u open failed: %s %s" % (plpath,ex))
                continue
            for url in m3u:
                if m3u.urlRE.match(url):
                    # Actual URL (usually http). Create bogus doc
                    doc = self.docforurl(url)
                    self._moredocs.append(doc)
                    docidx = len(self._rcldocs) + len(self._moredocs) - 1
                    tt = doc["title"]
                    if not tt:
                        # Temp workaround for recoll 1.28.2 not
                        # setting values in meta
                        tt = doc["text"]
                    self._dirvec[diridx][tt] = (-1, docidx)
                else:
                    docidx = self.statpath(plpath, url)
                    if docidx:
                        elt = os.path.split(url)[1]
                        self._dirvec[diridx][elt] = (-1, docidx)


    # The root entry (diridx 0) is special because its keys are the
    # topdirs paths, not simple names. We look with what topdir path
    # this doc belongs to, then return the appropriate diridx and the
    # split remainder of the path
    def _pathbeyondtopdirs(self, doc):
        url = uprclutils.docpath(doc).decode('utf-8', errors='replace')
        # Determine the root entry (topdirs element). Special because
        # its path is not a simple name. Fathidx is its index in _dirvec
        firstdiridx = -1
        for rtpath,idx in self._dirvec[0].items():
            #uplog("type(url) %s type(rtpath) %s rtpath %s url %s" %
            # (type(url),type(rtpath),rtpath, url))
            if url.startswith(rtpath):
                firstdiridx = idx[0]
                break
        if firstdiridx == -1:
            # uplog("No parent in topdirs: %s" % url)
            return None,None

        # Compute rest of path. If there is none, we're not interested.
        url1 = url[len(rtpath):]
        if len(url1) == 0:
            return None,None

        # If there is a Group field, just add it as a virtual
        # directory in the path. This only affects the visible tree,
        # not the 'real' URLs of course.
        if doc["group"]:
            a = os.path.dirname(url1)
            b = os.path.basename(url1)
            url1 = os.path.join(a, doc["group"], b)
            
        # Split path. The caller will walk the list (possibly creating
        # directory entries as needed, or doing something else).
        path = url1.split('/')[1:]
        return firstdiridx, path
    

    # Main folders build method: walk the recoll docs array and split
    # the URLs paths to build the [folders] data structure
    def _rcl2folders(self, confdir):
        self._dirvec = []
        self._xid2idx = {}
        # This is used to store the diridx for the playlists during
        # the initial walk, for initialization when the tree is
        # complete.
        self._playlists = []

        start = timer()

        rclconf = rclconfig.RclConfig(confdir)
        topdirs = [os.path.expanduser(d) for d in
                   shlex.split(rclconf.getConfParam('topdirs'))]
        topdirs = [d.rstrip('/') for d in topdirs]

        # Create the 1st entry. This is special because it holds the
        # recoll topdirs, which are paths instead of simple names. There
        # does not seem any need to build the tree between a topdir and /
        self._dirvec.append({})
        self._dirvec[0][".."] = (0, -1)
        for d in topdirs:
            self._dirvec.append({})
            self._dirvec[0][d] = (len(self._dirvec)-1, -1)
            self._dirvec[-1][".."] = (0, -1)

        # Walk the doc list and update the directory tree according to the
        # url: create intermediary directories if needed, create leaf
        # entry.
        #
        # Binary path issue: at the moment the python rclconfig can't
        # handle binary (the underlying conftree.py can, we'd need a
        # binary stringToStrings). So the topdirs entries have to be
        # strings, and so we decode the binurl too. This probably
        # could be changed we wanted to support binary, (non utf-8)
        # paths. For now, for python3 all dir/file names in the tree
        # are str
        for docidx in range(len(self._rcldocs)):
            doc = self._rcldocs[docidx]
            
            # Only include selected mtypes: tracks, playlists,
            # directories etc.
            if doc["mtype"] not in audiomtypes:
                continue

            # For linking item search results to the main
            # array. Deactivated for now as it does not seem to be
            # needed (and we would need to add xdocid to the
            # resultstore fields).
            #self._xid2idx[doc["xdocid"]] = docidx
            
            fathidx, path = self._pathbeyondtopdirs(doc)
            if not fathidx:
                continue
            
            #uplog("%s"%path, file=sys.stderr)
            for idx in range(len(path)):
                elt = path[idx]
                if elt in self._dirvec[fathidx]:
                    # This path element was already seen
                    # If this is the last entry in the path, maybe update
                    # the doc idx (previous entries were created for
                    # intermediate elements without a Doc).
                    if idx == len(path) -1:
                        self._dirvec[fathidx][elt] = \
                                   (self._dirvec[fathidx][elt][0], docidx)
                    # Update fathidx for next iteration
                    fathidx = self._dirvec[fathidx][elt][0]
                else:
                    # Element has no entry in father directory (hence no
                    # self._dirvec entry either).
                    if idx != len(path) -1:
                        # This is an intermediate element. Create a
                        # Doc-less directory
                        fathidx = self._createdir(fathidx, -1, elt)
                    else:
                        # Last element. If directory, needs a self._dirvec entry
                        if doc["mtype"] == 'inode/directory':
                            fathidx = self._createdir(fathidx, docidx, elt)
                        elif doc["mtype"] == 'audio/x-mpegurl':
                            fathidx = self._createpldir(fathidx, docidx,doc,elt)
                        else:
                            self._dirvec[fathidx][elt] = (-1, docidx)

        if False:
            for ent in self._dirvec:
                uplog("%s" % ent)

        self._initplaylists()
                    
        end = timer()
        uplog("_rcl2folders took %.2f Seconds" % (end - start))


    # Fetch all the docs by querying Recoll with [mime:*], which is guaranteed to match every doc
    # without overflowing the query size (because the number of mime types is limited). Something
    # like title:* would overflow. This creates the main doc array, which is then used by all
    # modules.
    #
    # Depending on the recoll version, we use a Python list of Recoll Docs or the more compact but
    # immutable QResultStore
    #
    # When using the resultstore, the records are not modifyable and the aliastags processing is
    # performed at indexing time by rclaudio. Cf. minimtagfixer.py
    def _fetchalldocs(self, confdir):
        #uplog("_fetchalldocs: has_resultstore: %s" % _has_resultstore)
        start = timer()

        rcldb = recoll.connect(confdir=confdir)
        rclq = rcldb.query()
        rclq.execute("mime:*", stemming=0)
        #rclq.execute('album:a* OR album:b* OR album:c*', stemming=0)
        uplog("Estimated alldocs query results: %d" % (rclq.rowcount))

        if _has_resultstore:
            fields = [r[1] for r in uprclutils.upnp2rclfields.items()]
            fields += _otherneededfields
            fields += uprclinit.allMinimTags()
            fields = list(set(fields))
            #uplog("_fetchalldocs: store fields: %s" % fields)
            self._rcldocs = qresultstore.QResultStore()
            self._rcldocs.storeQuery(rclq, fieldspec=fields, isinc = True)
        else:
            tagaliases = None
            if uprclinit.g_minimconfig:
                tagaliases = uprclinit.g_minimconfig.getaliastags()
            self._rcldocs = []
            for doc in rclq:
                if tagaliases:
                    for orig, target, rep in tagaliases:
                        val = doc[orig]
                        #uplog("Rep %s doc[%s]=[%s] doc[%s]=[%s]"%
                        #      (rep, orig, val, target, doc[target]))
                        if val and (rep or not doc[target]):
                            setattr(doc, target, val)

                self._rcldocs.append(doc)
                if self._maxrclcnt > 0 and len(self._rcldocs) >= self._maxrclcnt:
                    break
                time.sleep(0)

        end = timer()
        uplog("Retrieved %d docs in %.2f Seconds" % (len(self._rcldocs), end - start))


    ##############
    # Browsing the initialized [folders] hierarchy

    # Extract diridx and further path (leading to tags) from objid,
    # according to the way we generate them.
    def _objidtoidx(self, pid):
        if not pid.startswith(self._idprefix):
            raise Exception("folders.browse: bad pid %s" % pid)

        if len(self._rcldocs) == 0:
            raise Exception("folders:browse: no docs")

        isitem = False
        dirpth = pid[len(self._idprefix):]
        if not dirpth:
            idx = 0
            pathremain = ''
        else:
            if dirpth[0:2] == '$d':
                isitem = False
            elif dirpth[0:2] == '$i':
                isitem = True
            else:
                raise Exception("folders:browse: called on non dir objid %s" % pid)
            # Other $sign?
            nextdol = dirpth.find("$", 1)
            if nextdol > 0:
                idx = int(dirpth[2:nextdol])
            else:
                idx = int(dirpth[2:])
            pathremain = None
            if nextdol > 0:
                pathremain = dirpth[nextdol:]

        if isitem:
            if  idx >= len(self._rcldocs):
                raise Exception(f"folders:browse: bad pid exceeds rcldocs size [{pid}]")
        else:
            if  idx >= len(self._dirvec):
                raise Exception(f"folders:browse: bad pid exceeds dirvec size [{pid}]")

        return (isitem, idx, pathremain)


    # Tell the top module what entries we define in the root
    def rootentries(self, pid):
        return [direntry(pid + 'folders', pid, '[folders]'),]

    def _docforidx(self, docidx):
        if docidx < len(self._rcldocs):
            return self._rcldocs[docidx]
        else:
            return self._moredocs[docidx - len(self._rcldocs)]        

    # Look all non-directory docs inside directory, and return the
    # cover art we find. 
    #
    # TBD In the case where this is a Group directory, we'd
    # need to go look into the file system for a group.xxx image.  As
    # it is, things work if the tracks rely on the group pic (instead
    # of having an embedded pic or track pic) Also: playlists: need to
    # look at the physical dir for a e.g. playlistname.jpg.  And also:
    # currently, we won't look at possible art for a folder with no
    # music (e.g. top folder of a multi-cd). We'd need to look at the
    # fs directory, but we don't have the path at this point. We'd
    # need a '.' entry with a doc record containing the
    # path. Currently this works if one of the subdirs has an audio
    # file with an external cover.
    def _arturifordir(self, diridx):
        for nm,ids in self._dirvec[diridx].items():
            docidx = ids[1]
            if docidx >= 0 and docidx < len(self._rcldocs):
                doc = self._rcldocs[docidx]
                # We used to only look for art for direct children
                # tracks, but we now also look at subdirs. This will
                # yield an image from the first subdir which has an
                # image file in it, so somewhat random, but nice
                # anyway. The condition is kept around to show how to
                # change our minds or make it optional.
                if True or doc["mtype"] != 'inode/directory':
                    arturi = uprclutils.docarturi(doc,self._httphp,self._pprefix,preferfolder=True)
                    if arturi:
                        return arturi

    def _browsemeta(self, pid, isitem, idx):
        docidx = -1
        if isitem:
            docidx = idx
        else:
            try:
                ids = self._dirvec[idx]
                docidx = ids[1]
            except:
                pass
        if docidx != -1:
            doc = self._docforidx(docidx)
            id = self._idprefix + '$i' + str(docidx)
            e = rcldoctoentry(id, pid, self._httphp, self._pprefix, doc)
            return [e,]

    # Folder hierarchy browse method.
    # objid is like folders$index
    # flag is meta or children.
    def browse(self, pid, flag, offset, count):
        
        isitem,idx,pthremain = self._objidtoidx(pid)

        # If pthremain is set, this is pointing to 'Tag View'. Pass
        # the request along to the tags browser.
        if pthremain:
            if not pthremain.find('$tagview.0') == 0:
                raise Exception(f"uprclfolders:browse: pid [{pid}]. bad pthremain")
            return uprclinit.getTree('tags').browseFolder(pid, flag, pthremain, self.dirpath(pid))
        
        # If there is only one entry in root, skip it. This means that 0
        # and 1 point to the same dir, but this does not seem to be an
        # issue
        if not isitem and idx == 0 and len(self._dirvec[0]) == 2:
            idx = 1

        if flag == "meta":
            if not isitem:
                raise Exception(f"uprclfolders:browse: browsemeta on non-item pid [{pid}]")
            return self._browsemeta(pid, isitem, idx)

        #uplog(f"Folders browse: idx [{idx}] content: [{self._dirvec[idx]}]")
        entries = []
        showtopart = True
        # The basename call is just for diridx==0 (topdirs). Remove it if
        # this proves a performance issue
        for nm,ids in self._dirvec[idx].items():
            if nm == ".." or nm == ".":
                continue
            thisdiridx = ids[0]
            thisdocidx = ids[1]
            if thisdiridx >= 0:
                # Skip empty directories
                if len(self._dirvec[thisdiridx]) == 1:
                    continue
                # If there are directories, don't show art for the Tags top entries, this would
                # show one of the subdir's art and looks weird
                showtopart = False
                id = self._idprefix + '$d' + str(thisdiridx)
                arturi = self._arturifordir(thisdiridx)
                entries.append(direntry(id, pid, os.path.basename(nm), arturi=arturi))
            else:
                # Not a directory. docidx had better been set
                if thisdocidx == -1:
                    uplog("folders:docidx -1 for non-dir entry %s"%nm)
                    continue
                doc = self._docforidx(thisdocidx)

                id = self._idprefix + '$i' + str(thisdocidx)
                e = rcldoctoentry(id, pid, self._httphp, self._pprefix, doc)
                if e:
                    entries.append(e)

        if idx not in self._playlists:
            entries.sort(key=cmpentries)

        # Add "Browse subtree by tags" entry
        if not self._notagview and pid != self._idprefix and self._enabletags:
            arturi = None
            if showtopart:
                arturi=self._arturifordir(idx)
            id = pid + '$tagview.0'
            entries.insert(0, direntry(id, pid, ">> Tag View", arturi=arturi))

        return entries

    # Return path for objid, which has to be a container.This is good old
    # pwd... It is called from the search module for generating a 'dir:'
    # recoll filtering directive.
    def dirpath(self, objid):
        # We may get called from search, on the top dir (above
        # [folders]). Return empty in this case
        try:
            isitem,diridx,pthremain = self._objidtoidx(objid)
        except:
            return ""
        if isitem:
            raise Exception(f"uprclfolders:dirpath: called on item pid [{pid}]")
            
        if diridx == 0:
            return "/"
    
        lpath = []
        while True:
            fathidx = self._dirvec[diridx][".."][0]
            found = False
            for nm, ids in self._dirvec[fathidx].items():
                if ids[0] == diridx:
                    lpath.append(nm)
                    found = True
                    break
            # End for
            if not found:
                uplog("uprclfolders: pwd failed for %s \
                (father not found), returning /" % objid)
                return "/"
            if len(lpath) > 200:
                uplog("uprclfolders: pwd failed for %s \
                (looping), returning /" % objid)
                return "/"
                
            diridx = fathidx
            if diridx == 0:
                break

        if not lpath:
            path = "/"
        else:
            path = ""
        for elt in reversed(lpath):
            path += elt + "/"

        return path


    # Compute object id for doc out of recoll search. Not used at the
    # moment, and _xid2idx is not built.
    def _objidforxdocid(self, doc):
        if doc["xdocid"] not in self._xid2idx:
            return None
        return self._idprefix + '$i' + str(self._xid2idx[doc["xdocid"]])


    # Given a doc, we walk its url down from the part in root to find
    # its directory entry, and return the _dirvec and _rcldocs indices
    # it holds, either of which can be -1
    def _stat(self, doc):
        # _pathbeyond... returns the _dirvec index of the root entry
        # we start from (root is special), and the split rest of path.
        # That is if the doc url has /av/mp3/classique/bach/ and the root entry is /av/mp3,
        # we get the _dirvec entry index for /av/mp3 and [classique, bach]
        fathidx, pathl = self._pathbeyondtopdirs(doc)
        if not fathidx:
            return -1,-1
        docidx = -1
        for elt in pathl:
            if not elt in self._dirvec[fathidx]:
                #uplog("_stat: element %s has no entry in %s" %
                #      (elt, self._dirvec[fathidx]))
                return -1,-1
            fathidx, docidx = self._dirvec[fathidx][elt]

        return fathidx, docidx
        

    # Only works for directories but we do not check. Caller beware.
    def _objidforpath(self, doc):
        fathidx, docidx = self._stat(doc)
        return self._idprefix + '$d' + str(fathidx)


    def objidfordoc(self, doc):
        id=None
        if doc["mtype"] == 'inode/directory':
            id = self._objidforpath(doc)
        #else:
        #    # Note: not currently doing anything, see method comments
        #    id = self._objidforxdocid(doc)

        if not id:
            id = self._idprefix + '$' + 'seeyoulater'
        return id
