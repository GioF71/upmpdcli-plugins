#
# Copyright (C) 2017-2026 J.F.Dockes
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

# [folders] section of the tree. This is the first part constructed and it is in charge of the
# initial fetching of data from recoll.
#
# Object Id prefix: 0$uprcl$folders
#
# Data structure:
#
# The _rcldocs list has one entry for each document in the index (mime:* search), it is the result
# of a 'mime:*' recoll query. Each entry is, or is similar to, a recoll.Doc(), a kind of dict.
#
# The _dirvec list has one entry for each directory. Each entry is a Python dict, mapping the
# directory entries' names to a pair (diridx,docidx), where:
#
#  - diridx is an index into _dirvec if the name is a directory, else -1
#  - docidx is an index into _rcldocs, or -1 if:
#     - There is no _rcldocs entry, which happens if there is no corresponding recoll doc for an
#       intermediary element in a path, or because this is a synthetic 'Group' entry.
#     - Or, while we build the structure, temporarily, if the doc was not yet seen. The value will
#       then be updated when we see it.
#
# Directories are created as needed by splitting the paths/urls from _rcldocs (and possibly adding
# some for groupings defined by the Group tag). Directories have no direct relation to their
# possible recoll index objects (if any), they are identified by their _dirvec index
#
# Note: docidx is usually set in the pair for a directory, if there is a Doc entry, but I don't
# think that it is ever used. The Recoll Doc for a directory has nothing very interesting in it.
#
# Note: We could probably use a single value, with a convention saying, e.g., that > 0 is for docs
# and < -1 for folders. Check if this saves a significant amount of memory.
#
# Each directory has a special ".." entry with a diridx pointing to the parent directory. This
# allows building a path from a container id (aka pwd).
#
# Only playlists have a "." entry (needed during init)
#
# Entry 0 in _dirvec is special: it holds the 'topdirs' from the recoll configuration. The entries
# are paths instead of simple names, and their docidx is 0. The diridx points to a regular dirvec
# entry.
#
# Object ids inside the section:
#    Container: $d<diridx> where <diridx> indexes into _dirvec
#    Item: $i<docidx> where <docidx> indexes into _rcldocs
# Note: this is very different from what Minim does. Minim uses actual objid paths as objids.
# E.g. 0$folders$f1589$f1593$f1604$*i11609. Must make pwd and any walk up the tree much easier.
# 
# We used to build an _xid2idx xdocid->objidx map to allow a Recoll item search result to be
# connected back to the folders tree, but this was not actually useful (bogus objids for items in
# search results are quite probably ok). Also quite probably, this could also be done using the URL,
# as it is what we use to build the folders tree in the first place. _xid2idx is currently
# desactivated (see comment). See objidfordoc() in this file for how we compute objids for
# search results which are actual directories (which need to be browsable).
#


import os
import sys
import time

from upmplgutils import uplog, direntry, getOptionValue
from uprclutils import audiomtypes, rcldoctoentry, cmpentries
import uprclutils
import uprclinit
import uprclfolderscreate


# All standard cover art file names:
_artexts = (".jpg", ".png")
def _artnamegen(base):
    for ext in _artexts:
        yield base + ext
_folderartbases = ("cover", "folder")
_folderartnames = []
for base in _folderartbases:
    for path in _artnamegen(base):
        _folderartnames.append(path)


# Create bogus "doc" for a path
def _docforpath(path, isdir=False):
    doc = {"url" : "file://" + path, "group": None, "embdimg" : None}
    if isdir:
        doc["mtype"] = "inode/directory"
    return doc


class Folders(object):

    # Initialize (read recoll data and build tree).
    def __init__(self, confdir, httphp, pathprefix):
        self._idprefix = "0$uprcl$folders"
        self._httphp = httphp
        self._pprefix = pathprefix
        self._rcldocs = uprclfolderscreate._fetchalldocs(confdir)
        # _playlists is used to store the diridx for the playlists during the initial walk, for
        # initialization when the tree is complete.
        self._dirvec, self._playlists = uprclfolderscreate._rcl2folders(confdir, self._rcldocs)
        # _moredocs is overflow storage for synthetic records created for playlists url
        # entries. Uses docidx values starting at len(_rcldocs), with index into moredocs
        # (value - len(_rcldocs))
        self._moredocs = uprclfolderscreate._initplaylists(self, 
            confdir, self._rcldocs, self._dirvec, self._playlists)
        self._enabletags = uprclinit.g_minimconfig.getboolvalue("showExtras", True)
        self._notagview = getOptionValue("uprclnotagview", False)


    def rcldocs(self):
        return self._rcldocs


    # Tell the top module what entries we define in the root
    def rootentries(self, pid):
        return [
            direntry(pid + "folders", pid, "[folders]"),
        ]


    # Given a doc, walk its url down from the part in root to find its directory entry, and
    # return the entry's_dirvec and _rcldocs indices, either of which can be -1
    def _stat(self, doc, verbose=False):
        # _splitpath returns the _dirvec index of the topdirs entry in root that we start from and
        # the split rest of path.  That is if the doc url has /av/mp3/classique/bach/ and the root
        # entry is /av/mp3, we get the _dirvec entry index for /av/mp3 and [classique, bach]
        # _splitpath is in the creation module because it is used before our _dirvec variable is
        # set.
        fathidx, pathl = uprclfolderscreate._splitpath(self._dirvec, doc)
        if verbose:
            uplog(f"_stat: pbtd returns fathidx {fathidx} pathl {pathl}")
        if not fathidx:
            return -1, -1
        docidx = -1
        for elt in pathl:
            if not elt in self._dirvec[fathidx]:
                if verbose:
                    uplog(f"_stat: element [{elt}] has no entry in {fathidx} "
                          "[{self._dirvec[fathidx]}.keys()]")
                return -1, -1
            if verbose:
                uplog(f"_stat: element [{elt}] entry in {fathidx} [{self._dirvec[fathidx][elt]}]")
            fathidx, docidx = self._dirvec[fathidx][elt]

        return fathidx, docidx


    # Find the doc index for a filesystem path.
    # We use a temporary doc to call _stat()
    def statpath(self, path, verbose=False):
        doc = _docforpath(path)
        fathidx, docidx = self._stat(doc, verbose)
        if docidx >= 0 and docidx < len(self._rcldocs):
            return docidx
        return -1


    # Extract diridx and further path (leading to tags) from objid.
    def _objidtoidx(self, pid):
        if not pid.startswith(self._idprefix):
            raise Exception(f"folders.browse: bad pid [{pid}]")

        if len(self._rcldocs) == 0:
            raise Exception("folders:browse: no docs")

        isitem = False
        dirpth = pid[len(self._idprefix) :]
        if not dirpth:
            idx = 0
            pathremain = ""
        else:
            if dirpth[0:2] == "$d":
                isitem = False
            elif dirpth[0:2] == "$i":
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
            if idx >= len(self._rcldocs):
                raise Exception(f"folders:browse: bad pid exceeds rcldocs size [{pid}]")
        else:
            if idx >= len(self._dirvec):
                raise Exception(f"folders:browse: bad pid exceeds dirvec size [{pid}]")

        return (isitem, idx, pathremain)


    def _docforidx(self, docidx):
        if docidx < len(self._rcldocs):
            return self._rcldocs[docidx]
        else:
            idx = docidx - len(self._rcldocs)
            if idx < len(self._moredocs):
                return self._moredocs[idx]
        return None


    # Look all non-directory docs inside directory, and return the cover art we find.
    # 
    # TBD:
    # - In the case where this is a Group directory, we'd need to go look into the file system for a
    #   group.xxx image.  As it is, things work if the tracks rely on the group pic (instead of
    #   having an embedded pic or track pic)
    # - playlists: need to look at the physical dir for a e.g. playlistname.jpg.
    #
    # We used to only look for art for direct children tracks, but we now also look at
    # subdirs. This will yield an image from the first subdir which has an image file in
    # it, so somewhat random, but nice anyway.
    def _arturifordironedoc(self, diridx, docidx):
        # Look for art for one object, track or directory.
        # Directories only have doc entries if they are also albums. Else we fake a doc.
        if docidx >= 0 and docidx < len(self._rcldocs):
            doc = self._rcldocs[docidx]
        else:
            doc = _docforpath(self.dirpath("", diridx), True)
        return self.docarturi(doc, preferfolder=True)

    # Look for art for the directory itself, then its children.
    def _arturifordir(self, thisdiridx, thisdocidx=-1):
        # First look at the directory itself.
        arturi = self._arturifordironedoc(thisdiridx, thisdocidx)
        if arturi:
            return arturi
        # Then look at children.
        for nm, ids in self._dirvec[thisdiridx].items():
            diridx = ids[0]
            docidx = ids[1]
            arturi = self._arturifordironedoc(diridx, docidx)
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
            id = self._idprefix + "$i" + str(docidx)
            e = rcldoctoentry(id, pid, self._httphp, self._pprefix, doc)
            return [e,]


    ##############
    # Browsing the initialized [folders] hierarchy
    # @param pid objid is like folders$index
    # @param flag: "meta" or "children".
    def browse(self, pid, flag, offset, count):

        isitem, idx, pthremain = self._objidtoidx(pid)

        # If pthremain is set, this is pointing to 'Tag View'. Pass
        # the request along to the tags browser.
        if pthremain:
            if not pthremain.find("$tagview.0") == 0:
                raise Exception(f"uprclfolders:browse: pid [{pid}]. bad pthremain")
            return uprclinit.getTree("tags").browseFolder(pid, flag, pthremain, self.dirpath(pid))

        # If there is only one entry in root, skip it. This means that 0 and 1 point to the same
        # dir, but this does not seem to be an issue
        if not isitem and idx == 0 and len(self._dirvec[0]) == 2:
            idx = 1

        if flag == "meta":
            if not isitem:
                raise Exception(f"uprclfolders:browse: browsemeta on non-item pid [{pid}]")
            return self._browsemeta(pid, isitem, idx)

        # uplog(f"Folders browse: idx [{idx}] content: [{self._dirvec[idx]}]")
        entries = []
        showtopart = True
        # The basename call is just for diridx==0 (topdirs). Remove it if
        # this proves a performance issue
        
        for nm, ids in self._dirvec[idx].items():
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
                id = self._idprefix + "$d" + str(thisdiridx)
                arturi = self._arturifordir(thisdiridx, thisdocidx)
                entries.append(direntry(id, pid, os.path.basename(nm), arturi=arturi))
            else:
                # Not a directory. docidx had better been set
                if thisdocidx == -1:
                    uplog("folders:docidx -1 for non-dir entry %s" % nm)
                    continue
                doc = self._docforidx(thisdocidx)

                id = self._idprefix + "$i" + str(thisdocidx)
                e = rcldoctoentry(id, pid, self._httphp, self._pprefix, doc)
                if e:
                    entries.append(e)

        if idx not in self._playlists:
            entries.sort(key=cmpentries)

        # Add "Browse subtree by tags" entry
        if (not self._notagview) and pid != self._idprefix and self._enabletags:
            arturi = None
            if showtopart:
                arturi = self._arturifordir(idx)
            id = pid + "$tagview.0"
            entries.insert(0, direntry(id, pid, ">> Tag View", arturi=arturi))

        return entries


    # Return path for objid, which has to be a container.This is good old
    # pwd... It is called from the search module for generating a 'dir:'
    # recoll filtering directive.
    def dirpath(self, objid, diridx=None):
        # We may get called from search, on the top dir (above [folders]). Return empty in this case
        if not diridx:
            try:
                isitem, diridx, pthremain = self._objidtoidx(objid)
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
                uplog(f"uprclfolders: pwd failed for {objid} (father not found), returning /")
                return "/"
            if len(lpath) > 200:
                uplog(f"uprclfolders: pwd failed for {objid} (looping), returning /")
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


    # Compute an UPnP object ID for a document produced by a recoll search
    def objidfordoc(self, doc):
        id = None
        if doc["mtype"] == "inode/directory":
            fathidx, docidx = self._stat(doc)
            return self._idprefix + "$d" + str(fathidx)
        else:
            # Note: we thought we should have something like objidforxdocid for using consistent
            # objids, but it does not seem to be actually necessary. Use a unique but different id
            # instead.
            id = self._idprefix + "$xdocid" + doc.xdocid
        # uplog(f"objidfordoc: returning {id}")
        return id


    # Track-specific cover art. Based on either the file name or embedded data
    def _trackarturi(self, doc, objpath):
        # Check for an image specific to the track file
        base, ext = os.path.splitext(objpath)
        for artpath in _artnamegen(base):
            #uplog(f"_trackarturi: checking existence:[{artpath}]")
            artdoc = _docforpath(artpath)
            fathidx, docidx = self._stat(artdoc)
            if docidx >= 0:
                return uprclutils.httpurl(self._httphp, os.path.join(self._pprefix, artpath))

        # Else try to use an embedded img
        if doc["embdimg"]:
            arturi = uprclutils.embdimgurl(doc, self._httphp, self._pprefix)
            if arturi:
                # uplog("docarturi: embedded: %s"%printable(arturi))
                return arturi
        return None


    # Return folder-level art uri (e.g. /path/to/folder.jpg) if it exists
    def _folderart(self, doc, albtitle=None):
        # If doc is a directory, this returns it own path, else the father path
        folderpath = uprclutils.docfolder(doc)
        dirdoc = _docforpath(folderpath, True)
        folderidx, _ = self._stat(dirdoc)
        if folderidx < 0:
            uplog(f"_folderart: folder not found: {folderpath}")
            return None

        foldercontents = self._dirvec[folderidx].keys()
        #uplog(f"_folderart: path [{folderpath}] idx {folderidx} contents [{foldercontents}]")

        # If albtitle is set check for an image of the same name
        if albtitle:
            for fsimple in _artnamegen(albtitle):
                if fsimple in foldercontents:
                    return uprclutils.httpurl(self._httphp, os.path.join(folderpath, fsimple))

        # Look for an appropriate image in the file folder. We list the folder and look for a
        # case-insensitive match for all the possible cover art conventional names
        arturi = None
        for f in foldercontents:
            flowersimple = f.lower()
            if flowersimple in _folderartnames:
                path = os.path.join(self._pprefix, folderpath, f)
                arturi = uprclutils.httpurl(self._httphp, path)
                break

        #uplog(f"folderart: returning {arturi}")
        return arturi


    # Find cover art for doc which may be a folder or track. We can look for both a
    # track-specific image or a folder-level one
    #
    # We return a special uri if the file has embedded image data
    def docarturi(self, doc, preferfolder=False, albtitle=None):
        objpath = doc["url"][7:]
        #uplog(f"docarturi: preferfolder {preferfolder} docpath {objpath}")
        
        if not preferfolder:
            arturi = self._trackarturi(doc, objpath)
            if arturi:
                return arturi
        
        # won't work for the virtual group directory itself: it has no doc
        if doc["group"]:
            base = os.path.join(os.path.dirname(objpath), uprclutils.tag2fn(doc["group"]))
            for artpath in _artnamegen(base):
                #uplog(f"docarturi:calling os.path.exist({artpath})")
                if os.path.exists(artpath):
                    return uprclutils.httpurl(self._httphp, os.path.join(self._pprefix, artpath))
        
        # TBD Here minimserver would look for album disc before album art (which is taken care of by
        # _folderart() with albtitle set)
        # Look for folder level image file (e.g. cover.jpg)
        arturi = self._folderart(doc, albtitle)
        if arturi:
            return arturi
        
        # If preferfolder is set, we did not look at the track-specific art, do it last.
        if preferfolder:
            arturi = self._trackarturi(doc, objpath)
        
        return arturi
