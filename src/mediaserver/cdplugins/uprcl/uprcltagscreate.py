# Copyright (C) 2017-2022 J.F.Dockes
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
#

import os
import time
import re
from recoll import recoll

from timeit import default_timer as timer
from uprclutils import audiomtypes, docfolder, uplog
import uprclutils
import uprclinit

# Tags for which we may create auxiliary tag tables for facet descent. 
#
# The dict key is the tag name, used as container title in the tags tree,
# except if an a different display value was set by the user
# (_tagdisplaytag). The value is the auxiliary table name, used also
# as base for unique id and join columns (with _id) appended, and is
# also currently the recoll field name (with a provision to differ if
# needed, thanks to the currently empty _coltorclfield dict).
#
# The keys must stay same as what Minim uses as we filter them with
# indexTags from minim config
#
# Note: artist is actually doc["albumartist"] if set, else doc["artist"] and
# is processed separately
#
# This is the base set, with some custom translations (e.g. Group->cgroup). If a minimserver
# configuration is used, Some entries may be filtered out and some may be added.
_alltagtotable = {
    'AlbumArtist' : 'albumartist',
    'All Artists' : 'allartists',
    'Artist' : 'artist',
    'Comment' : 'comment',
    'Composer' : 'composer',
    'Conductor' : 'conductor',
    'Date' : 'date',
    'Genre' : 'genre',
    'Group' : 'cgroup', # can't have a table named group
    'Label' : 'label',
    'Lyricist' : 'lyricist',
    'Orchestra' : 'orchestra',
    'Performer' : 'performer',
    }

# Translations used when fetching fields from the recoll
# record. Most have the same name as the column.
_coltorclfield = {
    'allartists' : 'artist'
    }

# The actual list of tags (e.g. "Genre", "Composer") which will be shown in the tree, after reading
# the local configuration.
g_indextags = []
# The display string for the above tags. Non-identity if there are entries like Composer:Compositeur
# in the indexTags minim config
g_tagdisplaytag = {}
# Same as _alltagtotable, filtered by g_indextags
g_tagtotable = {}

def getIndexTags():
    return g_indextags
def getTagDisplayTag():
    return g_tagdisplaytag
def getTagToTable():
    return g_tagtotable

# Name of the join column for one of the tag tables. Actually, now that we use separate junction
# tables instead of columns inside the tracks table, the column name could be constant. Kept it.
def _clid(table):
    return table + '_id'
# Name of the junction table for a given tag table. Ex for genres.
# rcldocs is not an sqlite table, it's the recoll document list.
#         docidx        docidx                genre_id
# rcldocs<------>tracks<------>tracks_genres<---------->genre
def _junctb(table):
    return "tracks_" + table  + "s"


# Create an empty db.
#
# There is one table for each tag (Artist, Genre, Date, etc.), listing all possible values for the
# particular tag. The table name is the value from the _alltagtotable array, <tagname> and it has 2
# columns: <tagname>_id and value.
# 
# The tracks table is the "main" table, and has a record for each track, with a title column, and an
# album join column (album_id) (because a track can only belong to one album). The unique index into
# this table is the document index in the recoll document list (docidx).
#
# Because a track can have multiple values for a given tag, we use junction tables. These are named
# tracks_<tagname>s (e.g. tracks_genres). The records in these have two columns: docidx (track id)
# and and <tagname>_id (unique id from the <tagname> table)
#
# The Albums table is special because it is built according to, and stores, the file system location
# (the album title is not enough to group tracks, there could be many albums with the same
# title). Also we do tricks with grouping discs into albums etc.
#
# Note: we create all tables even if not all tags are actually used.
def _createsqdb(conn):
    c = conn.cursor()

    # Create the albums table
    try:
        c.execute('''DROP TABLE albums''')
    except:
        pass
    c.execute(
        "CREATE TABLE albums (album_id INTEGER PRIMARY KEY,"
        # artist_id is for an album_artist, either explicit from an albumartist attribute or
        # implicit if all tracks have the same artist attribute
        "artist_id INT,"
        "albtitle TEXT, albfolder TEXT, albdate TEXT, albarturi TEXT,"
        # During creation, albalb is non null only the elements of a merged album, and is the
        # album_id id for the parent. It is set by the album merging pass. When the album merge is
        # done, albalb is set to album_id for all remaining (single-disc, non merged) albums.
        "albalb INT,"
        # albtdisc is set from the tracks DISCNUMBER tag or equivalent, while initially walking the
        # docs. It signals candidates for merging. album/discs with albtdisc set are not selected
        # for display in album lists, as they are supposedly represented by their parent album. The
        # field is reset to null for albums with a discnumber which do not end up being merged.
        "albtdisc INT,"
        # Temp column while creating the table for deciding if we have a uniform artist or not. This
        # is a text version of all the artistid sets for each album track. If we were really
        # concerned about space usage, we could use a parallel temp table and drop it when done...
        "artists TEXT"
        ")")

    # Create the main tracks table, which has a one-to-one relationship with the recoll document
    # array
    try:
        c.execute('''DROP TABLE tracks''')
    except:
        pass
    tracksstmt = '''CREATE TABLE tracks (docidx INT, album_id INT, artist_id INT, 
                    trackno INT, title TEXT, path TEXT)'''
    c.execute(tracksstmt)

    # Create tables for tag values (e.g. all genre values, all composer values, etc.)
    for tb in _alltagtotable.values():
        _createTagTables(c, tb)


# Create the value and junction table for a given tag
def _createTagTables(cursor, tgnm):
    # Create a table for this tag values and value ids
    try:
        cursor.execute('DROP TABLE ' + tgnm)
    except:
        pass
    stmt = "CREATE TABLE " + tgnm + " (" + _clid(tgnm) + " INTEGER PRIMARY KEY, value TEXT)"
    cursor.execute(stmt)
    # Create a junction table between the tracks table and the tag values table, with docidx and
    # valueid columns, allowing multiple tag values for a given track (e.g. several
    # genres). Using a table-specific name for the id column would not be necessary, it's a
    # remnant of the time where these columns were integral to the tracks table. Still, does not
    # hurt.
    try:
        cursor.execute('DROP TABLE ' + _junctb(tgnm))
    except:
        pass
    stmt = "CREATE TABLE " + _junctb(tgnm) + " (docidx INT, " + _clid(tgnm) + " INT)"
    cursor.execute(stmt)
    

# Augment indextag dict and create tables for a custom field, not part of our predefined set
def _addCustomTable(conn, indextag):
    c = conn.cursor()
    tb = indextag.lower()
    _alltagtotable[indextag] = tb
    _createTagTables(c, tb)


# Peruse the configuration to decide what tags will actually show up
# in the tree and how they will be displayed.
def _prepareTags(conn):
    global g_tagdisplaytag
    global g_tagtotable
    global g_indextags

    g_indextags = []
    g_tagdisplaytag = {}
    g_tagtotable = {}
    
    indextagsp = uprclinit.g_minimconfig.getindextags()
    itemtags = uprclinit.g_minimconfig.getitemtags()
    if not indextagsp:
        # Our default list of index tags (showing up as containers in the tree)
        indextagsp = [('Artist',''), ('Date',''), ('Genre',''), ('Composer','')]

    # Compute the actual list of index tags:
    for v,d in indextagsp:
        if v.lower() == 'none':
            g_indextags = []
            g_tagdisplaytag = {}
            break
        g_indextags.append(v)
        g_tagdisplaytag[v] = d if d else v
    uplog("prepareTags: g_indextags: %s g_tagdisplaytag %s" % (g_indextags, g_tagdisplaytag))
    
    # Compute an array of (table name, recoll field) translations for the tags we need to process,
    # as determined by the indexTags property. Most often they are identical. This also determines
    # what fields we create tables for.
    tabtorclfield = []
    for nm in g_indextags:
        if nm not in _alltagtotable:
            _addCustomTable(conn, nm)
        tb = _alltagtotable[nm]
        g_tagtotable[nm] = tb
        rclfld = _coltorclfield[tb] if tb in _coltorclfield else tb
        uplog(f"recolltosql: using rclfield [{rclfld}] for sql [{tb}]")
        tabtorclfield.append((tb, rclfld))

    for nm in itemtags:
        if nm not in _alltagtotable:
            _addCustomTable(conn, nm)
        tb = _alltagtotable[nm]
        rclfld = _coltorclfield[tb] if tb in _coltorclfield else tb
        uplog(f"recolltosql: using rclfield [{rclfld}] for sql [{tb}]")
        tabtorclfield.append((tb, rclfld))

    return tabtorclfield


# Insert new value if not existing, return rowid of new or existing row
def _auxtableinsert(conn, tb, value):
    #uplog("_auxtableinsert [%s] -> [%s]" % (tb, value))
    c = conn.cursor()
    stmt = f"SELECT {_clid(tb)} FROM  {tb} WHERE value = ?"
    c.execute(stmt, (value,))
    r = c.fetchone()
    if r:
        rowid = r[0]
    else:
        stmt = f"INSERT INTO {tb}(value) VALUES(?)"
        c.execute(stmt, (value,))
        rowid = c.lastrowid
    return rowid


# tracknos like n/max are now supposedly processed by rclaudio and
# should not arrive here, but let's play it safe.
def _tracknofordoc(doc):
    try:
        return int(doc["tracknumber"].split('/')[0])
    except:
        #uplog("_tracknofordoc: doc["tracknumber"] %s title %s url %s" %
        #      (doc["tracknumber"], doc["title"], doc["url"]))
        return 1


# Detect '[disc N]' or '(disc N)' or ' disc N' at the end of an album title
# Groups         1   2       3                 4                      5
_albtitdnumre = "(.*)(\[disc ([0-9]+)\]|\(disc ([0-9]+)\)|[ ]+disc[ ]+([0-9]+))[ ]*$"
_albtitdnumexp = re.compile(_albtitdnumre, flags=re.IGNORECASE)
_folderdnumre = "(cd|disc)[ ]*([0-9]+)(.*)"
_folderdnumexp = re.compile(_folderdnumre, flags=re.IGNORECASE)

# Create album record for track if needed (not already there).
# The albums table is special, can't use auxtableinsert()
def _maybecreatealbum(conn, doc):
    c = conn.cursor()
    folder = docfolder(doc).decode('utf-8', errors = 'replace')

    album = doc["album"]
    if not album:
        album = uprclutils.basename(folder)
        #uplog("Using %s for alb MIME %s title %s" % (album,doc["mtype"],doc["url"]))

    #uplog(f"_maybecreatealbum: album: [{album}] folder [{folder}]")

    if doc["albumartist"]:
        albartist_id = _auxtableinsert(conn, 'artist', doc["albumartist"])
    else:
        albartist_id = None

    # See if there is a discnum, either explicit or from album
    # title
    discnum = None
    if doc["discnumber"]:
        try:
            discnum = int(doc["discnumber"])
            #uplog(f"discnumber {discnum} folder {folder}")
        except:
            pass

    # Look for a disc number at the end of the album title. If it's
    # there and it's the same as the discnumber attribute, we fix the
    # title, else we leave it alone (and the merge will later fail for
    # differing titles)
    m = _albtitdnumexp.search(album)
    if m:
        #uplog("Disc number found at end of album title")
        for i in (3,4,5):
            if m.group(i):
                adiscnum = int(m.group(i))
                #uplog(f"Match is in group {i} adiscnum {adiscnum} discnum {discnum}")
                if not discnum:
                    discnum = adiscnum
                if adiscnum == discnum:
                    album = m.group(1)
                    #uplog(f"album title changed to [{album}]")
                break
            
    if not discnum:
        m = _folderdnumexp.search(uprclutils.basename(folder))
        if m:
            discnum = int(m.group(2))
        
    # See if this albumdisc already exists (created for a previous track)
    stmt = "SELECT album_id, artist_id FROM albums WHERE albtitle = ? AND albfolder = ?"
    wcols = [album, folder]
    if discnum:
        stmt += ' AND albtdisc = ?'
        wcols.append(discnum)
    #uplog(f"maybecreatealbum: {stmt} {wcols}")
    c.execute(stmt, wcols)
    r = c.fetchone()
    if r:
        #uplog("maybecreatealbum: album found")
        album_id = r[0]
    else:
        c.execute('''INSERT INTO 
        albums(albtitle, albfolder, artist_id, albdate, albtdisc, artists) 
        VALUES (?,?,?,?,?,?)''',
                  (album, folder, albartist_id, doc["date"], discnum, ""))
        album_id = c.lastrowid
        #uplog(f"New album {album_id} {album} disc {discnum} artist {albartist_id} folder {folder}")

    return album_id


# Add a track's artists set to the album auxiliary "artists" column, used in the end to determine an
# album artist if none was explicitely set
def _updatealbartistlist(conn, album_id, rowids):
    if not rowids:
        return
    c = conn.cursor()
    addstr = repr(rowids)
    stmt = f"UPDATE albums SET artists = artists || '|' || ? WHERE album_id = ?"
    values = (addstr, album_id)
    c.execute(stmt, values)
        

# Setting album covers needs to wait until we have scanned all tracks so that we can select
# a consistant embedded art (first track in path order), as recoll scanning is in unsorted
# directory order.
def _setalbumcovers(conn, rcldocs):
    c = conn.cursor()
    c.execute('''SELECT album_id,albtitle FROM albums''')
    for r in c:
        albid = r[0]
        albtitle = r[1]
        c1 = conn.cursor()
        stmt = '''SELECT docidx FROM tracks WHERE album_id = ? ORDER BY path'''
        c1.execute(stmt,  (albid,))
        for r1 in c1:
            docidx = r1[0]
            doc = rcldocs[docidx]
            arturi = uprclutils.docarturi(doc, uprclinit.getHttphp(), uprclinit.getPathPrefix(),
                                          preferfolder=True, albtitle=albtitle)
            if arturi:
                cupd = conn.cursor()
                #uplog(f"Setting albid {albid} albarturi to {arturi}")
                cupd.execute("UPDATE albums SET albarturi = ?  WHERE album_id = ?", (arturi, albid))
                break


# After the pass on tracks, look for all albums where the album artist is not set but all the tracks
# have the same artist, and set the album artist.
def _setalbumartists(conn):
    c = conn.cursor()
    # Get all albums without an albumartist where the same_track_artist flag is on
    c.execute("SELECT album_id, artists, albtitle FROM albums WHERE artist_id IS NULL")
    # For all albumartist-less albums
    for r in c:
        # Default to various artist
        albumartist = variousartistsid
        if r[1]:
            # Eval the string back to list of artist sets, and intersect to see if we have a common
            # artist
            s = r[1].lstrip("|")
            artsets = s.split("|")
            artsets = [eval(artset) for artset in artsets]
            if artsets:
                intersect = artsets[0]
                for artset in artsets[1:]:
                    intersect = intersect.intersection(artset)
                #uplog(f"_setalbumartists: INTERSECT for [{r[2]}]: {intersect}")
                if intersect:
                    # if multiple values, have to chose one...
                    albumartist = [v for v in intersect][0]
                    #uplog(f"Using albumartist {albumartist} for {r[2]}")

        if albumartist == variousartistsid:
            #uplog(f"Using albumartist Various Artists for {r[2]}")
            pass
        c1 = conn.cursor()
        c1.execute("UPDATE albums SET artist_id = ? WHERE album_id = ?", (albumartist, r[0]))


# Add albums to the recoll index so they can be searched for
def _albumstorecoll(conn):
    rcldb = recoll.connect(confdir=uprclinit.getRclConfdir(), writable=True)
    c = conn.cursor()
    #                 0        1          2          3         4         5
    stmt = '''SELECT album_id, albfolder, albtitle, albarturi, albdate, artist.value
      FROM albums LEFT JOIN artist ON artist.artist_id = albums.artist_id
      WHERE albtdisc is NULL'''
    c.execute(stmt, ())
    for r in c:
        udi = "albid" + str(r[0])
        doc = recoll.Doc()
        doc["album"] = r[2]
        doc["title"] = r[2]
        doc["mtype"] = "inode/directory"
        if r[5]:
            doc["albumartist"] = r[5]
            doc["artist"] = r[5]
        doc["url"] = "file://" + r[1]
        # uplog(f"_albumstorecoll: indexing album {doc['album']}")
        rcldb.addOrUpdate(udi, doc)
    

# Add artists to the recoll index so they can be searched for
def _artiststorecoll(conn):
    rcldb = recoll.connect(confdir=uprclinit.getRclConfdir(), writable=True)
    c = conn.cursor()
    #                 0         1
    stmt = "SELECT artist_id, value    FROM artist"
    c.execute(stmt, ())
    for r in c:
        udi = "artid" + str(r[0])
        doc = recoll.Doc()
        doc["title"] = r[1]
        doc["mtype"] = "inode/directory"
        doc["url"] = "file://artists/" + r[1] # Not used ever
        # uplog(f"_artiststorecoll: indexing artist {doc['title']}")
        rcldb.addOrUpdate(udi, doc)
    

# Check that the numbers are sequential
def _checkseq(seq):
    num = seq[0]
    if not num:
        return False
    for e in seq[1:]:
        if e != num + 1:
            return False
        num = e
    return True


def _membertotopalbum(conn, memberalbid):
    c = conn.cursor()
    c.execute('''SELECT * FROM albums WHERE album_id = ?''', (memberalbid,))
    cols = [desc[0] for desc in c.description]
    # Get array of column values, and set primary key and albtdisc to
    # None before inserting the copy
    tdiscindex = cols.index('albtdisc')
    v = [e for e in c.fetchone()]
    v[0] = None
    v[tdiscindex] = None
    c.execute('''INSERT INTO albums VALUES (%s)''' % ','.join('?'*len(v)),  v)
    return c.lastrowid


# Only keep albums in the same folder or in a sibling folder
def _mergealbumsfilterfolders(folder, rows, colidx):
    parent = uprclutils.dirname(folder)
    rows1 = []
    for row in rows:
        if row[colidx] == folder or uprclutils.dirname(row[colidx]) == parent:
            rows1.append(row)
    return rows1


## TBD: folder match filter
def _createmergedalbums(conn):
    c = conn.cursor()

    # Remember already merged
    merged = set()

    # All candidates for merging: albums with a disc number not yet
    # merged (albalb is null)
    c.execute('''SELECT album_id, albtitle, artist_id, albfolder FROM albums
      WHERE albalb IS NULL AND albtdisc IS NOT NULL''')
    c1 = conn.cursor()
    for r in c:
        albid = r[0]
        if albid in merged:
            continue
        albtitle = r[1]
        artist = r[2]
        folder = r[3]

        #uplog(f"_createmergedalbums: albid {albid} artist_id {artist} albtitle {albtitle}")

        # Look for albums not already in a group, with the same title and artist
        if artist:
            c1.execute('''SELECT album_id, albtdisc, albfolder FROM albums
                WHERE albtitle = ? AND artist_id = ?
                AND albalb is NULL AND albtdisc IS NOT NULL''',
                       (albtitle, artist))
        else:
            c1.execute('''SELECT album_id, albtdisc, albfolder FROM albums
                WHERE albtitle = ? AND artist_id IS NULL
                AND albalb is NULL AND albtdisc IS NOT NULL''',
                       (albtitle,))

        rows = c1.fetchall()
        rows1 = _mergealbumsfilterfolders(folder, rows, 2)

        #uplog(f"_createmergedalbums: got {len(rows1)} possible(s) title {albtitle}")

        if len(rows1) > 1:
            albids = [row[0] for row in rows1]
            dnos = sorted([row[1] for row in rows1])
            if not _checkseq(dnos):
                uplog(f"mergealbums: not merging bad seq {dnos} for albtitle {albtitle}")
                c1.execute(f"UPDATE albums SET albtdisc = NULL " \
                           f"WHERE album_id in ({','.join('?'*len(albids))})", albids)
                continue

            # Create record for whole album by copying the first
            # record, setting its album_id and albtdisc to NULL
            topalbid = _membertotopalbum(conn, albids[0])

            # Update all album disc members with the top album id
            values = [topalbid,] + albids
            c1.execute(f"UPDATE albums SET albalb = ? " \
                       f"WHERE album_id in ({','.join('?'*len(albids))})", values)
            merged.update(albids)
            #uplog("_createmergedalbums: merged: %s" % albids)
            
        elif len(rows1) == 1:
            # Album with a single disc having a discnumber. Just unset
            # the discnumber, we won't use it and its presence would
            # prevent the album from showing up. Alternatively we
            # could set albalb = album_id?
            #uplog("Setting albtdisc to NULL albid %d" % albid)
            c1.execute("UPDATE albums SET albtdisc = NULL WHERE album_id= ?", (albid,))

    # finally, set albalb to albid for all single-disc albums
    c.execute("UPDATE albums SET albalb = album_id WHERE albtdisc IS NULL")


# Parse date: partly duplicated from rclaudio, see comments about date formats there.  The date
# field is a bit of a mess because up to some point recoll had an alias from date to dmtime, which
# resulted in no date field and a calendar date (instead of uxtime) in dmtime. So we take the date
# value from 'date' if set, else 'dmtime', and then process it here. All reasonable date formats
# begin with YYYY[-MM[-DD]] and this is the part we keep.
def parsedate(dt):
    if len(dt) > 10:
        dt = dt[0:10]
    l = dt.split('-')
    if len(l) > 3 or len(l) == 2 or len(l[0]) != 4 or l[0] == '0000':
        return None
    #uplog("parsedate: -> %s" % dt)
    return dt


# Create the db and fill it up with the values we need, taken out of
# the recoll records list
def recolltosql(conn, rcldocs):
    start = timer()

    _createsqdb(conn)
    tabtorclfield = _prepareTags(conn)
    #uplog("Tagscreate: tabtorclfield: %s"%tabtorclfield)

    maxcnt = 0
    totcnt = 0
    c = conn.cursor()

    # Set this as global, no need to query for it every time it's needed
    global variousartistsid
    variousartistsid = _auxtableinsert(conn, "artist", "Various Artists")    

    for docidx in range(len(rcldocs)):
        doc = rcldocs[docidx]
        totcnt += 1

        if totcnt % 1000 == 0:
            time.sleep(0)
        
        # No need to include non-audio or non-tagged types
        if doc["mtype"] not in audiomtypes or doc["mtype"] == 'inode/directory' \
               or doc["mtype"] == 'audio/x-mpegurl':
            continue

        # Album creation ?
        album_id = _maybecreatealbum(conn, doc)
        
        trackno = _tracknofordoc(doc)

        if doc["url"].find('file://') == 0:
            path = doc["url"][7:]
        else:
            path = ''

        # Misc tag values:            
        # Set base values for column names, values list, placeholders. Done this way because we used
        # to add to the lists for the tag values (which now use separate junction tables).
        columns = ['docidx','album_id','trackno','title',      'path']
        values =  [ docidx,  album_id,  trackno,  doc["title"], path]
        placehold = ['?',    '?',       '?',      '?',          '?']
        for tb, rclfld in tabtorclfield:
            value = doc[rclfld]
            # See comment in parsedate
            if rclfld == 'date':
                if not value:
                    value = doc['dmtime']
                if value:
                    value = parsedate(value)
            if not value:
                continue
            # rclaudio.py concatenates multiple values, using " | " as separator.
            valuelist = value.split(" | ")
            rowids = set()
            for value in valuelist:
                # Possibly insert in appropriate table (if value not already there), and
                # insert record in junction table for the corresponding field.
                rowid = _auxtableinsert(conn, tb, value)
                rowids.add(rowid)
                stmt = f"INSERT INTO {_junctb(tb)}(docidx, {_clid(tb)}) VALUES (?, ?)"
                jvals = [docidx, rowid]
                # uplog(f"EXECUTING {stmt} values {jvals}")
                c.execute(stmt, jvals)
            if tb == 'artist' and rowids:
                _updatealbartistlist(conn, album_id, rowids)
        # Create the main record in the tracks table.
        stmt = "INSERT INTO tracks(" + ",".join(columns) + ") VALUES(" + ",".join(placehold) + ")"
        c.execute(stmt, values)

    ## End Big doc loop

    _setalbumartists(conn)
    _setalbumcovers(conn, rcldocs)
    _createmergedalbums(conn)
    conn.commit()
    end = timer()
    _albumstorecoll(conn)
    _artiststorecoll(conn)
    uplog(f"recolltosql: processed {totcnt} docs in {end-start:.1f} Seconds")
 
