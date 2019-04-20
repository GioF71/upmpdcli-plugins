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

# Manage the tags sections of the tree.
#
# Object Id prefixes:
#     0$uprcl$=[tagname]
#     0$uprcl$albums
#     0$uprcl$items
# Object Ids inside the subsections: complicated

import sys
PY3 = sys.version > '3'
import os
import sqlite3
import time
import tempfile

from upmplgutils import uplog
from uprclutils import g_myprefix, rcldirentry, rcldoctoentry, cmpentries

from uprcltagscreate import recolltosql, _clid, g_tagtotable, \
     g_tagdisplaytag, g_indextags

# The browseable object which defines the tree of tracks organized by tags.
class Tagged(object):
    def __init__(self, rcldocs, httphp, pathprefix):
        self._httphp = httphp
        self._pprefix = pathprefix
        self._conn = None
        self._init_sqconn()
        recolltosql(self._conn, rcldocs)
        

    def _init_sqconn(self):
        # We use a separate thread for building the db to ensure
        # responsiveness during this phase.  :memory: handles normally
        # can't be shared between threads, and different :memory: handles
        # access different dbs. The following would work, but it needs
        # python 3.4
        #self._conn = sqlite3.connect('file:uprcl_db?mode=memory&cache=shared')
        # As we can guarantee that 2 threads will never access the db at
        # the same time (the init thread just goes away when it's done),
        # we just disable the same_thread checking on :memory:
        if self._conn is None:
            self._conn = sqlite3.connect(':memory:', check_same_thread=False)


    # Create our top-level directories, with fixed entries, and stuff
    # from the tags tables. This may be called (indirectly) from the folders
    # hierarchy, with a path restriction
    def rootentries(self, pid, path=''):
        uplog("rootentries: pid %s path %s" % (pid, path))
        entries = []
        nalbs = self._albcntforfolder(path)
        entries.append(rcldirentry(pid + 'albums', pid, nalbs + ' albums'))
        if path:
            where = ' WHERE tracks.path LIKE ? '
            args = (path + '%',)
        else:
            where = ' '
            args = ()
        c = self._conn.cursor()
        stmt = "SELECT COUNT(*) from tracks"
        c.execute(stmt+where, args)
        nitems = str(c.fetchone()[0])
        entries.append(rcldirentry(pid + 'items', pid, nitems + ' items'))
        subqs = self._subtreetags(where, args)
        for tt in subqs:
            entries.append(rcldirentry(pid + '=' + tt , pid,
                                       g_tagdisplaytag[tt]))
        return entries


    # List all tags which still have multiple values inside this selection level
    def _subtreetags(self, where, values):
        c = self._conn.cursor()
        tags = []
        for tt in g_indextags:
            tb = g_tagtotable[tt]
            stmt = '''SELECT COUNT(DISTINCT %s) FROM tracks %s''' % \
                   (_clid(tb), where)
            #uplog("subtreetags: stmt: [%s]" % stmt)
            c.execute(stmt, values)
            cnt = c.fetchone()[0]
            if len(stmt) > 80:
                stmt = stmt[:80] + "..."
            uplog("subtreetags: %d values for %s (%s,%s)"%(cnt,tb,stmt,values))
            if cnt > 1:
                tags.append(tt)
        return tags


    # Build a list of track directory entries for an SQL statement
    # which selects docidxs (SELECT docidx,... FROM tracks WHERE...)
    def _trackentriesforstmt(self, stmt, values, pid):
        rcldocs = uprclinit.g_trees['folders'].rcldocs()
        c = self._conn.cursor()
        c.execute(stmt, values)
        entries = [rcldoctoentry(pid + '$i' + str(r[0]),
                                 pid, self._httphp, self._pprefix,
                                 rcldocs[r[0]]) for r in c]
        if PY3:
            return sorted(entries, key=cmpentries)
        else:
            return sorted(entries, cmp=cmpentries)
    

    # Return a list of trackids as selected by the current
    # path <selwhere> is like: WHERE col1_id = ? AND col2_id = ? [...], and
    # <values> holds the corresponding values
    def _docidsforsel(self, selwhere, values):
        c = self._conn.cursor()
        stmt = 'SELECT docidx FROM tracks ' + selwhere + ' ORDER BY trackno'
        uplog("docidsforsel: executing <%s> values %s" % (stmt, values))
        c.execute(stmt, values)
        return [r[0] for r in c.fetchall()]


    # Expand multiple possibly merged albums to real ones. The tracks
    # always refer to the raw albid, so this is necessary to compute a
    # track list. Multiple albums as input, no sorting.
    def _albids2rawalbids(self, albids):
        c = self._conn.cursor()
        rawalbids = []
        for albid in albids:
            c.execute('''SELECT album_id FROM albums WHERE albalb = ?''',
                      (albid,))
            rows = c.fetchall()
            if len(rows):
                for r in rows:
                    rawalbids.append(r[0])
            else:
                rawalbids.append(albid)
        return rawalbids
    

    # Expand single possibly merged album into list of ids for component discs
    def _albid2rawalbidssorted(self, albid):
        c = self._conn.cursor()
        c.execute('''SELECT album_id FROM albums
          WHERE albalb = ? ORDER BY albtdisc''', (albid,))
        rows = c.fetchall()
        if len(rows) <= 1:
            return (albid,)
        else:
            return [r[0] for r in rows]


    # Translate albids so that the ones which are part of a merged
    # album become the merged id. The returned list is same size or
    # smaller because there maybe duplicate merged ids. Used to show
    # album lists
    def _rawalbids2albids(self, rawalbids):
        albids = set()
        c = self._conn.cursor()
        for rawalbid in rawalbids:
            c.execute('''SELECT album_id, albalb FROM albums
                WHERE album_id = ?''', (rawalbid,))
            alb = c.fetchone()
            if alb[1]:
                albids.add(alb[1])
            else:
                albids.add(alb[0])
        #
        return [id for id in albids]


    # Count albums under file system path. We use albalb because
    # merged albums may come from multiple folders, and have no
    # albfolder. So this returns merged albums for which at least one
    # disk is under this folder path
    def _albcntforfolder(self, path):
        c = self._conn.cursor()
        if path:
            stmt = '''SELECT COUNT(DISTINCT albalb) FROM ALBUMS
            WHERE albfolder LIKE ?'''
            args = (path + "%",)
        else:
            stmt = "SELECT COUNT(*) FROM albums WHERE albtdisc is NULL"
            args = ()
        uplog("_albcntforfolder: stmt %s args %s" % (stmt, args))
        c.execute(stmt, args)
        return str(c.fetchone()[0])


    # Track list for possibly merged album: get tracks from all
    # components, then renumber trackno
    def _trackentriesforalbum(self, albid, pid):
        albids = self._albid2rawalbidssorted(albid)
        uplog("_trackentriesforalbid: %d -> %s" % (albid, albids))
        # I don't see a way to use a select..in statement and get the
        # order right
        tracks = []
        for albid in albids:
            stmt = '''SELECT docidx FROM tracks
            WHERE album_id = ? ORDER BY trackno'''
            tracks += self._trackentriesforstmt(stmt, (albid,), pid)

        tno = None
        for track in tracks:
            tn = 1
            if 'upnp:originalTrackNumber' in track:
                tn = int(track['upnp:originalTrackNumber'])
            if tno:
                if tn <= tno:
                    tn = tno + 1
                tno = tn
            else:
                tno = tn
            track['upnp:originalTrackNumber'] = str(tno)
        return tracks
            

    # Return all albums ids to which any of the selected tracks belong
    def _subtreealbums(self, selwhere, values):
        stmt = 'SELECT DISTINCT album_id FROM tracks ' + selwhere 
        c = self._conn.cursor()
        uplog('subtreealbums: executing %s' % stmt)
        c.execute(stmt, values)
        rawalbids = [r[0] for r in c]
        albids = self._rawalbids2albids(rawalbids)
        uplog('subtreealbums: returning %s' % albids)
        return albids
    

    def _direntriesforalbums(self, pid, where, path=''):
        uplog("_direntriesforalbums. where: %s" % where)
        c = self._conn.cursor()
        args = (path + '%',) if path else ()
        if path:
            if not where:
                where = '''WHERE albfolder LIKE ?'''
            else:
                where += ''' AND albfolder LIKE ?'''
            substmt = '''SELECT DISTINCT albalb FROM ALBUMS %s'''%where
            where = '''WHERE album_id IN (%s)''' % substmt
        else:
            if not where:
                where = '''WHERE albtdisc IS NULL'''
            else:
                where += ''' AND albtdisc IS NULL'''

        stmt = '''SELECT album_id, albtitle, albarturi, albdate, artist.value
        FROM albums LEFT JOIN artist ON artist.artist_id = albums.artist_id
        %s ORDER BY albtitle''' % where

        uplog('direntriesforalbums: %s' % stmt)
        c.execute(stmt, args)
        entries = []
        for r in c:
            id = pid + '$' + str(r[0])
            entries.append(
                rcldirentry(id, pid, r[1], arturi=r[2], date=r[3],artist=r[4],
                            upnpclass='object.container.album.musicAlbum'))
        return entries


    # This is called when an 'albums' element is encountered in the
    # selection path. i is the index of the albums element. The tree under
    # albums has a well defined structure: ql=len(qpath), we have an
    # albums list if i is the last element (i == ql-1), an album track
    # list for i == ql-2 (we then have an albid at ql-1), and a 'Complete
    # album' query if i == ql-3 (...$albums$xxx$showca)
    def _tagsbrowsealbums(self, pid, qpath, i, selwhere, values):
        uplog("_tagsbrowsealbums: pid %s qpath %s i %s selwhere %s values %s" %
              (pid, qpath, i, selwhere, values))
        c = self._conn.cursor()
        entries = []
        if i == len(qpath)-1:
            # List of albums to which belong any track from selection
            albidsl = self._subtreealbums(selwhere, values)
            albids = ','.join([str(a) for a in albidsl])
            where = ' WHERE album_id in (' + albids + ') '
            entries = self._direntriesforalbums(pid, where)
        elif i == len(qpath)-2:
            # Album track list. Maybe a merged album->multiple phys albids
            albid = int(qpath[-1])
            rawalbids = self._albids2rawalbids((albid,))
            uplog("_tagsbrowsealbums: albid %s rawalbids %s"%(albid,rawalbids))
            stmt = '''SELECT COUNT(docidx) FROM tracks
                WHERE album_id IN (%s)''' % ','.join('?'*len(rawalbids))
            c.execute(stmt, rawalbids)
            r = c.fetchone()
            ntracks = int(r[0])
            docidsl = self._docidsforsel(selwhere, values)
            stmt = '''SELECT docidx FROM tracks 
                WHERE album_id IN (%s) AND docidx IN (%s)''' % \
            (','.join('?'*len(rawalbids)), ','.join('?'*len(docidsl)))
            entries = self._trackentriesforstmt(stmt, rawalbids+docidsl, pid)
            if ntracks != len(entries):
                id = pid + '$' + 'showca'
                entries = [rcldirentry(id, pid, '>> Complete Album')] + entries
        elif i == len(qpath)-3:
            # 'Complete album' entry
            # Note that minim has an additional level here, probably to
            # present groups or multiple groups ? The trackids ids are
            # like: 
            #    0$=Composer$17738$albums$2$showca.0$hcalbum$*i13458
            # I don't know what the .0 is for.
            # The 'hcalbum' level usually has 2 entries '>> Hide Content' 
            # and the album title. TBD
            albid = int(qpath[-2])
            entries = self._trackentriesforalbum(albid, pid)
        
        return entries


    # This is called when an 'items' element is encountered in the
    # selection path. 
    def _tagsbrowseitems(self, pid, qpath, i, selwhere, values):
        stmt = 'SELECT docidx FROM tracks ' + selwhere
        c = self._conn.cursor()
        rows = c.execute(stmt, values)
        docids = [r[0] for r in rows]
        albids = self._subtreealbums(selwhere, values)
        entries = []
        displaytracks = True
        if len(albids) == 1:
            # Only display '>> Complete album' if not all tracks
            # already there. If all tracks are there, we display
            # the album entry (with the same id value: show album)
            albid = albids[0]
            tlist = self._trackentriesforalbum(albid, pid)
            # Replace $items with $albums for the album entry
            id = pid.replace('$items', '$albums') + '$' + str(albid) + '$showca'
            if len(tlist) != len(docids):
                entries.append(rcldirentry(id, pid, '>> Complete Album'))
            else:
                displaytracks = False
                el = self._direntriesforalbums(pid, "WHERE album_id = %s"%albid)
                el[0]['id'] = id
                entries.append(el[0])
        if displaytracks:
            rcldocs = uprclinit.g_trees['folders'].rcldocs()
            entries += [rcldoctoentry(pid + '$i' + str(docid),
                                      pid, self._httphp, self._pprefix,
                                      rcldocs[docid]) for docid in docids]
        if PY3:
            return sorted(entries, key=cmpentries)
        else:
            return sorted(entries, cmp=cmpentries)


    # Main browsing routine. Given an objid, translate it into a select
    # statement, plus further processing, and return the corresponding
    # records
    def _tagsbrowse(self, pid, qpath, flag, path=''):
        uplog("tagsbrowse. pid %s qpath %s" % (pid, qpath))

        # Walk the qpath, which was generated from the objid and
        # defines what tracks are selected and what we want to
        # display. E.g =Artist$21$=Date would display all distinct
        # dates for tracks by Artist #21. =Artist$21$=Date$48 the data
        # for date 48 (the numbers are indexes into the aux tables)
        qlen = len(qpath)
        selwhat = ''
        if path:
            selwhere = ' WHERE tracks.path LIKE ? '
            values = [path + '%',]
        else:
            selwhere = ''
            values = []
        i = 0
        while i < qlen:
            elt = qpath[i]

            # Detect the special values: albums items etc. here. Their
            # presence changes how we process the rest (showing tracks and
            # albums and not dealing with other tags any more)
            if elt == 'albums':
                return self._tagsbrowsealbums(pid, qpath, i, selwhere, values)
            elif elt == 'items':
                return self._tagsbrowseitems(pid, qpath, i, selwhere, values)
            
            # '=colname'. Set the current column name, which will be used
            # in different ways depending if this is the last element or
            # not.
            if elt.startswith('='):
                col = g_tagtotable[elt[1:]] 

            selwhere = selwhere + ' AND ' if selwhere else ' WHERE '
            if i == qlen - 1:
                # We can only get here if the qpath ends with '=colname'
                # (otherwise the else branch below fetches the 2 last
                # elements and breaks the loop). We want to fetch all
                # unique values for the column inside the current selection.

                # e.g. artist.artist_id, artist.value
                selwhat = '%s.%s, %s.value' % (col, _clid(col), col)
                # e.g. tracks.artist_id = artist.artist_id
                selwhere += 'tracks.%s = %s.%s' % (_clid(col), col, _clid(col))
            else:
                # Look at the value specified for the =xx column. The
                # selwhat value is only used as a flag
                selwhat = 'tracks.docidx'
                selwhere += 'tracks.%s =  ?' % _clid(col)
                i += 1
                values.append(int(qpath[i]))
            i += 1

        entries = []
        if selwhat == 'tracks.docidx':
            # We are displaying content for a given value of a given tag
            docids = self._docidsforsel(selwhere, values)
            albids = self._subtreealbums(selwhere, values)
            subqs = self._subtreetags(selwhere, values)
            displaytracks = True
            if len(albids) > 1:
                id = pid + '$albums'
                label = '%d albums'
                entries.append(rcldirentry(id, pid, label % len(albids)))
            elif len(albids) == 1 and not subqs:
                # Only display '>> Complete album' if not all tracks
                # already there. If all tracks are there, we display
                # the album entry (with the same id value: show album)
                albid = albids[0]
                tlist = self._trackentriesforalbum(albid, pid)
                id = pid + '$albums$' + str(albid) + '$showca'
                if len(tlist) != len(docids):
                    entries.append(rcldirentry(id, pid, '>> Complete Album'))
                else:
                    displaytracks = False
                    el = self._direntriesforalbums(pid,
                                                   "WHERE album_id = %s"%albid)
                    el[0]['id'] = id
                    entries.append(el[0])

            if subqs:
                id = pid + '$items'
                label = '%d items'
                entries.append(rcldirentry(id, pid, label % len(docids)))
                for tt in subqs:
                    id = pid + '$=' + tt
                    entries.append(rcldirentry(id, pid, g_tagdisplaytag[tt]))
            elif displaytracks:
                rcldocs = uprclinit.g_trees['folders'].rcldocs()
                for docidx in docids:
                    id = pid + '$*i' + str(docidx)
                    entries.append(rcldoctoentry(id, pid, self._httphp,
                                                 self._pprefix,
                                                 rcldocs[docidx]))
                    if PY3:
                        entries = sorted(entries, key=cmpentries)
                    else:
                        entries = sorted(entries, cmp=cmpentries)
        else:
            # SELECT col.col_id, col.value FROM tracks, col
            # WHERE tracks.col_id = col.col_id
            # GROUP BY tracks.col_id
            # ORDER BY col.value
            stmt = "SELECT " + selwhat + " FROM tracks, " + col + \
                   selwhere + \
                   " GROUP BY tracks." + _clid(col) + \
                   " ORDER BY value"
            uplog("tagsbrowse: executing <%s> values %s" % (stmt,values))
            c = self._conn.cursor()
            c.execute(stmt, values)
            for r in c:
                id = pid + '$' + str(r[0])
                entries.append(rcldirentry(id, pid, r[1]))
        return entries


    # Browse the top-level tree named like 'xxx albums'. There are just 2
    # levels: the whole albums list, then for each entry the specified
    # albums track list
    def _albumsbrowse(self, pid, qpath, flag, path=''):
        c = self._conn.cursor()
        entries = []
        if len(qpath) == 1:
            entries = self._direntriesforalbums(pid, '', path)
        elif len(qpath) == 2:
            e1 = qpath[1]
            album_id = int(e1)
            entries = self._trackentriesforalbum(album_id, pid)
        else:
            raise Exception("Bad path in album tree (too deep): <%s>" % qpath)

        return entries


    # Implement the common part of browse() and browseFolder()
    def _dobrowse(self, pid, flag, qpath, folder=''):
        uplog("Tags:browsFolder: qpath %s"%qpath)
        if qpath[0] == 'items':
            args = (folder + '%',) if folder else ()
            folderwhere = ' WHERE tracks.path LIKE ? ' if folder else ' '
            stmt = 'SELECT docidx FROM tracks' + folderwhere
            entries = self._trackentriesforstmt(stmt, args, pid)
        elif qpath[0] == 'albums':
            entries = self._albumsbrowse(pid, qpath, flag, folder)
        elif qpath[0].startswith('='):
            entries = self._tagsbrowse(pid, qpath, flag, folder)
        else:
            raise Exception('Bad path in tags tree (start): <%s>' % qpath)
        return entries
        

    # Call from the folders tree when Tag View is selected.
    def browseFolder(self, pid, flag, pthremain, folder):
        uplog("Tags:browseFolder: pid %s pth %s fld %s"%(pid,pthremain,folder))
        l = pthremain.split('$')
        # 1st elt in list is empty because pthremain begins with $. so
        # len(l)==2 is the root of tags from this folder
        if len(l) == 2:
            return self.rootentries(pid + '$', folder)
        else:
            qpath = l[2:]
            return self._dobrowse(pid, flag, qpath, folder)

        
    # Top level browse routine. Handle the special cases and call the
    # appropriate worker routine.
    def browse(self, pid, flag):
        idpath = pid.replace(g_myprefix, '', 1)
        uplog('tags:browse: idpath <%s>' % idpath)
        entries = []
        qpath = idpath.split('$')
        return self._dobrowse(pid, flag, qpath)







############ Misc test/trial code, not used by uprcl ########################

def misctries():
    c = self._conn.cursor()
    c.execute('''SELECT COUNT(*) FROM tracks''')
    uplog("Count(*) %d" % (c.fetchone()[0],))
    
    #for row in c.execute('''SELECT album
    #                        FROM tracks where artist LIKE "%Gould%"
    #                        GROUP BY album'''):
    #    uplog("%s" % (row,))

    # For some strange reason it appears that GROUP BY is faster than SELECT
    # DISTINCT
    stmt = '''SELECT album FROM tracks GROUP BY album ORDER BY album'''
    start = timer()
    for row in c.execute(stmt):
        #uplog("%s" % (row[0].encode('UTF-8')))
        pass
    end = timer()
    uplog("Select took %.2f Seconds" % (end - start))
    for row in c.execute('''SELECT COUNT(DISTINCT album) from tracks'''):
        uplog("Album count %d" % row[0])


if __name__ == '__main__':
    confdir = "/home/dockes/.recoll-mp3"
    from recoll import recoll

    def fetchalldocs(confdir):
        allthedocs = []
        rcldb = recoll.connect(confdir=confdir)
        rclq = rcldb.query()
        rclq.execute("mime:*", stemming=0)
        uplog("Estimated alldocs query results: %d" % (rclq.rowcount))
        maxcnt = 1000
        totcnt = 0
        while True:
            docs = rclq.fetchmany()
            for doc in docs:
                allthedocs.append(doc)
                totcnt += 1
            if (maxcnt > 0 and totcnt >= maxcnt) or \
                   len(docs) != rclq.arraysize:
                break
        uplog("Retrieved %d docs" % (totcnt,))
        return allthedocs
    
    start = timer()
    docs = fetchalldocs(confdir)
    end = timer()
    uplog("Recoll extract took %.2f Seconds" % (end - start))
    start = timer()
    recolltosql(docs)
    end = timer()
    uplog("SQL db create took %.2f Seconds" % (end - start))
    
