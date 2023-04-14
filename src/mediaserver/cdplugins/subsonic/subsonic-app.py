#!/usr/bin/python3

import cmdtalkplugin
import conftree
import json
from html import escape as htmlescape, unescape as htmlunescape
from upmplgutils import *
from enum import Enum

from subsonic_connector.configuration import ConfigurationInterface
from subsonic_connector.connector import Connector
from subsonic_connector.response import Response
from subsonic_connector.album_list import AlbumList
from subsonic_connector.album import Album
from subsonic_connector.album_list import AlbumList
from subsonic_connector.song import Song
from subsonic_connector.genres import Genres
from subsonic_connector.genre import Genre
from subsonic_connector.list_type import ListType
from subsonic_connector.search_result import SearchResult
from subsonic_connector.artists import Artists
from subsonic_connector.artists_initial import ArtistsInitial
from subsonic_connector.artist import Artist
from subsonic_connector.artist_list_item import ArtistListItem

import libsonic

class ElementType(Enum):
    
    TAG   = 0, "tag"
    ALBUM = 1, "album"
    GENRE = 2, "genre"
    ARTIST = 3, "artist"
    TRACK = 4, "track"

    def __init__(self, 
            num : int, 
            element_name : str):
        self.num : int = num
        self.element_name : str = element_name

    def getName(self):
        return self.element_name

class TagType(Enum):
    
    NEWEST = 0, "newest", ElementType.ALBUM.getName(), "Newest Albums"
    RANDOM = 1, "random", ElementType.ALBUM.getName(), "Random Albums"
    GENRES = 2, "genres", ElementType.GENRE.getName(), "Genres"
    ARTISTS = 3, "artists", ElementType.ARTIST.getName(), "Artists"

    def __init__(self, 
            num : int, 
            tag_name : str, 
            tag_translation : str,
            tag_title : str):
        self.num : int = num
        self.tag_name : str = tag_name
        self.tag_translation : str = tag_translation
        self.tag_title : str = tag_title

    def getTagName(self):
        return self.tag_name

    def getTagTranslation(self):
        return self.tag_translation

    def getTagTitle(self):
        return self.tag_title
    
def _getTagTypeByName(tag_name : str) -> TagType:
    msgproc.log(f"_getTagTypeByName with {tag_name}")
    for _, member in TagType.__members__.items():
        if tag_name == member.getTagName():
            return member

from upmplgutils import uplog, setidprefix, direntry, getOptionValue

class UpmpdcliSubsonicConfig(ConfigurationInterface):
    
    def getBaseUrl(self) -> str: return getOptionValue('subsonicbaseurl')
    def getPort(self) -> int: return getOptionValue('subsonicport')
    def getUserName(self) -> str: return getOptionValue('subsonicuser')
    def getPassword(self) -> str: return getOptionValue('subsonicpassword')
    def getApiVersion(self) -> str: return libsonic.API_VERSION
    def getAppName(self) -> str: return "upmpdcli"

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = "0$subsonic$"
setidprefix("subsonic")

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

__items_per_page : int = int(getOptionValue("subsonicitemsperpage", "100"))
__enable_next : bool = False

__caches : dict[str, object] = {}

def _get_element_cache(element_type : ElementType) -> dict:
    if element_type.getName() in __caches:
        return __caches[element_type.getName()]
    cache = {}
    __caches[element_type.getName()] = cache
    return cache

def _cache_element_value(element_type : ElementType, key : str, value : str):
    cache : dict = _get_element_cache(element_type)
    if not key in cache:
        msgproc.log(f"_cache_element_value: caching: {key} to {value} on type {element_type.getName()}")
        cache[key] = value

def _get_cached_element(element_type : ElementType, key : str) -> str | None:
    cache : dict = _get_element_cache(element_type)
    if key in cache:
        return cache[key]
    return None

connector = Connector(UpmpdcliSubsonicConfig())
# Possible once initialisation. Always called by browse() or search(), should remember if it has
# something to do (e.g. the _g_init thing, but this could be something else).
_g_init = False
def _initsubsonic():
    global _g_init
    if _g_init:
        return True

    # Do whatever is needed here
    msgproc.log(f"browse: base_url: --{getOptionValue('subsonicbaseurl')}--")
    
    _g_init = True
    return True

@dispatcher.record('trackuri')
def trackuri(a):
    # We generate URIs which directly point to the stream, so this method should never be called.
    raise Exception("trackuri: should not be called for subsonic!")

def _returnentries(entries):
    """Helper function: build plugin browse or search return value from items list"""
    return {"entries" : json.dumps(entries), "nocache" : "0"}

def _create_objid_for(objid, element_type : ElementType, id : str) -> str:
    return objid + "/" + _escape_objid(element_type.getName() + "-" + id)

def _escape_objid(value : str) -> str:
    return htmlescape(value, quote = True)

def _album_to_entry(objid, current_album : Album) -> direntry:
    id : str = _create_objid_for(objid, ElementType.ALBUM, current_album.getId())
    title = current_album.getTitle()
    artist = current_album.getArtist()
    _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
    _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
    arturi = connector.buildCoverArtUrl(current_album.getId())
    return direntry(id, 
        objid, 
        title = title, 
        artist = artist,
        arturi = arturi)

def _genre_to_entry(objid, current_genre : Genre) -> direntry:
    id : str = _create_objid_for(objid, ElementType.GENRE, current_genre.getName())
    name : str = current_genre.getName()
    msgproc.log(f"_genre_to_entry for {name}")
    genre_art_uri = None
    genre_art : str = _get_cached_element(ElementType.GENRE, current_genre.getName())
    if genre_art:
        msgproc.log(f"_genre_to_entry cache entry hit for {current_genre.getName()}")
        genre_art_uri = connector.buildCoverArtUrl(genre_art)
    else:
        msgproc.log(f"_genre_to_entry cache entry miss for {current_genre.getName()}")
    entry = direntry(id, 
        objid, 
        name,
        arturi = genre_art_uri)
    return entry

def _artist_to_entry(objid, current_artist_list_item : ArtistListItem) -> direntry:
    id : str = _create_objid_for(objid, ElementType.ARTIST, current_artist_list_item.getId())
    name : str = current_artist_list_item.getName()
    msgproc.log(f"_artist_to_entry for {name}")
    artist_art_uri = None
    artist_art : str = _get_cached_element(ElementType.ARTIST, current_artist_list_item.getId())
    if artist_art:
        msgproc.log(f"_artist_to_entry cache entry hit for {current_artist_list_item.getId()}")
        artist_art_uri = connector.buildCoverArtUrl(artist_art)
    else:
        msgproc.log(f"_artist_to_entry cache entry miss for {current_artist_list_item.getId()}")
    entry = direntry(id, 
        objid, 
        name,
        arturi = artist_art_uri)
    return entry

def _song_to_entry(objid, current_song: Song, albumArtURI : str = None) -> dict:
    entry = {}
    id : str = _create_objid_for(objid, ElementType.TRACK, current_song.getId())
    entry['id'] = id
    entry['pid'] = current_song.getId()
    entry['upnp:class'] = 'object.item.audioItem.musicTrack'
    entry['uri'] = connector.buildSongUrlBySong(current_song)
    entry['tt'] = current_song.getTitle()
    entry['tp']= 'it'
    entry['discnumber'] = current_song.getDiscNumber()
    entry['upnp:originalTrackNumber'] = current_song.getTrack()
    entry['upnp:artist'] = current_song.getArtist()
    entry['upnp:album'] = current_song.getAlbum()
    entry['upnp:genre'] = current_song.getGenre()
    entry['res:mime'] = current_song.getContentType()
    if not albumArtURI:
        albumArtURI = connector.buildCoverArtUrl(current_song.getId())
    entry['upnp:albumArtURI'] = albumArtURI
    entry['duration'] = str(current_song.getDuration())
    #msgproc.log(f"_song_to_entry album_id {current_song.getId()} genre {current_song.getGenre()}")
    return entry

def _get_thing_type(lastvalue : str) -> bool:
    lpath = lastvalue.split("-")
    if lpath and len(lpath) > 1:
        last = lpath[0]
        return last
    return False

def _is_thing(lastvalue : str, thing_name : str) -> bool:
    if "-" in lastvalue:
        lpath = lastvalue.split("-")
        if lpath and len(lpath) > 1:
            last = lpath[0]
            return last == thing_name
    return False

def _get_thing(lastvalue : str, thing_name : str, join : bool = False) -> str:
    lpath = lastvalue.split("-")
    if lpath and len(lpath) > 1:
        last = lpath[0]
        if last == thing_name:
            return "-".join(lpath[1:])
    return None

def _get_albums(request_type : str, size : int = __items_per_page, offset : int = 0) -> list[Album]:
    albumListResponse : Response[AlbumList]
    if TagType.NEWEST.getTagName() == request_type:
        albumListResponse  = connector.getNewestAlbumList(size = size, offset = offset)
    elif TagType.RANDOM.getTagName() == request_type:
        albumListResponse = connector.getRandomAlbumList(size = size, offset = offset)
    if albumListResponse.isOk():
        return albumListResponse.getObj().getAlbums()
    return None        

def _load_album_tracks(objid, album_id : str, entries : list):
    albumResponse : Response[Album] = connector.getAlbum(album_id)
    if albumResponse.isOk():
        current_song : Song
        albumArtURI : str = connector.buildCoverArtUrl(albumResponse.getObj().getId())
        for current_song in albumResponse.getObj().getSongs():
            entry = _song_to_entry(objid, current_song, albumArtURI)
            entries.append(entry)

def _load_albums_by_type(objid, query_type : str, entries : list, tagType : TagType):
    offset : str = 0
    albumList : list[Album] = _get_albums(query_type, size = __items_per_page, offset = int(offset) * __items_per_page)
    sz : int = len(albumList)
    current_album : Album
    tag_cached : bool = False
    for current_album in albumList:
        if not tag_cached and tagType:
            _cache_element_value(ElementType.TAG, tagType.getTagName(), current_album.getId())
            tag_cached = True
        entries.append(_album_to_entry(objid, current_album))
        # cache genre art
        current_genre : str = current_album.getGenre()
        _cache_element_value(ElementType.GENRE, current_genre, current_album.getId())

@dispatcher.record('browse')
def browse(a):
    msgproc.log(f"browse: args: --{a}--")
    _initsubsonic()
    if 'objid' not in a:
        raise Exception("No objid in args")

    objid = a['objid']
    path = _objidtopath(objid)

    entries = []

    lastcrit, lastvalue, setcrits, filterargs = _pathtocrits(path)
    msgproc.log(f"browse: lastcrit: --{lastcrit}--")
    msgproc.log(f"browse: lastvalue: --{lastvalue}--")
    msgproc.log(f"browse: setcrits: --{setcrits}--")
    msgproc.log(f"browse: filterargs: --{filterargs}--")

    # Build a list of entries in the expected format. See for example ../radio-browser/radiotoentry
    # for an example
    
    if lastcrit:
        msgproc.log(f"match 0c lastcrit: {lastcrit}")
        if _is_thing(lastcrit, ElementType.ALBUM.getName()):
            album_id : str = _get_thing(lastcrit, ElementType.ALBUM.getName())
            _load_album_tracks(objid, album_id, entries)
            return _returnentries(entries)
    
    if TagType.NEWEST.getTagName() == lastcrit or TagType.RANDOM.getTagName() == lastcrit:
        msgproc.log(f"match 1 with lastcrit: {lastcrit}")
        # reply with the list
        if lastvalue:
            #return selected album
            if _is_thing(lastvalue, ElementType.ALBUM.getName()):
                album_id : str = _get_thing(lastvalue, ElementType.ALBUM.getName())
                _load_album_tracks(objid, album_id, entries)
                return _returnentries(entries)
        else:
            _load_albums_by_type(objid, lastcrit, entries, _getTagTypeByName(lastcrit))
            return _returnentries(entries)
    
    if TagType.GENRES.getTagName() == lastcrit:
        msgproc.log(f"match 2 with lastcrit: {lastcrit}")
        # reply with the list
        if lastvalue and _is_thing(lastvalue, ElementType.GENRE.getName()):
            #return list by genre
            select_genre : str = _get_thing(lastvalue, ElementType.GENRE.getName(), join = True)
            albumListResponse : Response[AlbumList] = connector.getAlbumList(
                ltype = ListType.BY_GENRE, 
                genre = select_genre,
                size = __items_per_page)
            genres_tag_cached : bool = False
            if albumListResponse.isOk():
                albumList : list[Album] = albumListResponse.getObj().getAlbums()
                msgproc.log(f"got {len(albumList)} albums for genre {select_genre}")
                current_album : Album
                for current_album in albumList:
                    if not genres_tag_cached:
                        _cache_element_value(ElementType.TAG, TagType.GENRES.getTagName(), current_album.getId())    
                        genres_tag_cached = True
                    _cache_element_value(ElementType.GENRE, select_genre, current_album.getId())
                    _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
                    entries.append(_album_to_entry(objid, current_album))
            return _returnentries(entries)
        else:
            genres_response : Response[Genres] = connector.getGenres()
            if genres_response.isOk():
                genre_list = genres_response.getObj().getGenres()
                genre_list.sort(key = lambda x: x.getName())
                current_genre : Genre
                for current_genre in genre_list:
                    #msgproc.log(f"genre {current_genre.getName()} albumCount {current_genre.getAlbumCount()}")
                    if current_genre.getAlbumCount() > 0:
                        entry : dict = _genre_to_entry(objid, current_genre)
                        entries.append(entry)
            return _returnentries(entries)

    if TagType.ARTISTS.getTagName() == lastcrit:
        msgproc.log(f"match 4 with lastcrit: {lastcrit}")
        # reply with the list
        if lastvalue and _is_thing(lastvalue, ElementType.ARTIST.getName()):
            #return albums by artist
            artist_tag_cached : bool = False
            select_artist_id : str = _get_thing(lastvalue, ElementType.ARTIST.getName())
            artist_response : Response[Artist] = connector.getArtist(select_artist_id)
            if artist_response.isOk():
                album_list : list[Album] = artist_response.getObj().getAlbumList()
                current_album : Album
                for current_album in album_list:
                    if not artist_tag_cached:
                        _cache_element_value(ElementType.TAG, TagType.ARTISTS.getTagName(), current_album.getId())    
                        artist_tag_cached = True
                    _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
                    _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
                    entries.append(_album_to_entry(objid, current_album))
            return _returnentries(entries)    
        else:
            artists_response : Response[Artists] = connector.getArtists()
            if artists_response.isOk():
                artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
                current_artists_initial : ArtistsInitial
                for current_artists_initial in artists_initial:
                    msgproc.log(f"current artists initial = {current_artists_initial.getName()}")
                    current_artist : ArtistListItem
                    for current_artist in current_artists_initial.getArtistListItems():
                        msgproc.log(f"current artist name = {current_artist.getName()}")
                        entries.append(_artist_to_entry(objid, current_artist))
            return _returnentries(entries)

    if lastvalue is None and lastcrit is not None:
        msgproc.log(f"match 3 with lastcrit: {lastcrit}")
        # process selection
        if _is_thing(lastcrit, ElementType.ALBUM.getName()):
            msgproc.log(f"match 3a (album) with lastcrit --{lastcrit}--")
            # process album
            album_id : str = _get_thing(lastcrit, ElementType.ALBUM.getName())
            _load_album_tracks(objid, album_id, entries)
            return _returnentries(entries)
    else:
        msgproc.log("match 0")
        # Path is root or ends with tag value. List the remaining tagnames if any.
        if not lastcrit:
            msgproc.log("match 0a")
            for tag in TagType:
                tagname : str = tag.getTagName()
                id = objid + "/" + _escape_objid(tagname)
                art_id = _get_cached_element(ElementType.TAG, tagname)
                entry : dict = direntry(
                    id = id, 
                    pid = objid, 
                    title = _crittotitle(tagname))
                if art_id:
                    entry['upnp:albumArtURI'] = connector.buildCoverArtUrl(art_id)
                entries.append(entry)
        else:
            msgproc.log("match 0b")
            if lastvalue:
                if _is_thing(lastvalue, ElementType.ALBUM.getName()):
                    album_id : str = _get_thing(lastvalue, ElementType.ALBUM.getName())
                    _load_album_tracks(objid, album_id, entries)
                    return _returnentries(entries)
                    
    #msgproc.log(f"browse: returning --{entries}--")
    return _returnentries(entries)

def _objidtopath(objid):
    if objid.find(_g_myprefix) != 0:
        raise Exception(f"subsonic: bad objid {objid}: bad prefix")
    return objid[len(_g_myprefix):].lstrip("/")

@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    _initsubsonic()
    objid = a["objid"]
    entries = []

    # Run the search and build a list of entries in the expected format. See for example
    # ../radio-browser/radiotoentry for an example
    value : str = a["value"]
    field : str = a["field"]
    
    msgproc.log(f"search for {value} as {field}")
    
    if ElementType.ALBUM.getName() == field:
        # search albums by specified value
        search_result : SearchResult = connector.search(value, 
            artistCount = 0, 
            songCount = 0,
            albumCount = __items_per_page)
        album_list : list[Album] = search_result.getAlbums()
        current_album : Album
        path_elem : list[str] = objid.split("/")
        path_len : int = len(path_elem)
        filters : dict[str, str] = {}
        if path_len > 1 and path_len % 2: # odd and > 1
            msgproc.log(f"search: filters = {path_elem}")
            sub : list[str] = path_elem[1:]
            for x in range(int(len(sub) / 2)):
                filters[sub[x]] = sub[x + 1]
        msgproc.log(f"search: filters = {filters}")
        for current_album in album_list:
            match : bool = True
            #for k, v in filters.items():
            #    if TagType.GENRES.getTagName() == k:
            #        # filter by genre
            #        current_genre : str = current_album.getGenre()
            #        msgproc.log(f"search: filters = {filters} current album genre {current_genre}")
            #        if not v in current_album.getGenre():
            #            match = False
            if match:
                _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
                entries.append(_album_to_entry(objid, current_album))
        return _returnentries(entries)
    
    if ElementType.TRACK.getName() == field:
        # search tracks by specified value
        search_result : SearchResult = connector.search(value, 
            artistCount = 0, 
            songCount = __items_per_page,
            albumCount = 0)
        song_list : list[Song] = search_result.getSongs()
        current_song : Song
        for current_song in song_list:
            entries.append(_song_to_entry(objid, current_song))
        return _returnentries(entries)
    
    # msgproc.log(f"browse: returning --{entries}--")
    return _returnentries(entries)

_crittotitle_a = {
    TagType.NEWEST.getTagName(): TagType.NEWEST.getTagTitle(), 
    TagType.RANDOM.getTagName(): TagType.RANDOM.getTagTitle(), 
    TagType.GENRES.getTagName(): TagType.GENRES.getTagTitle(),
    TagType.ARTISTS.getTagName(): TagType.ARTISTS.getTagTitle()
}
def _crittotitle(crit):
    """Translate filtering field name to displayed title"""
    return _crittotitle_a[crit]

def _pathtocrits(path):
    if path:
        lpath = path.split("/")
    else:
        lpath = []

    # Compute the filtering criteria from the path
    # All field names we see: used to restrict those displayed at next step
    setcrits = []
    # Arguments to the facets filtering object: tagname,value pairs
    filterargs = {}
    # Final values after walking the path. Decide how/what to display next
    crit = None
    value = None
    for idx in range(len(lpath)):
        if idx & 1:
            continue
        crit = lpath[idx]
        if idx < len(lpath)-1:
            value = htmlunescape(lpath[idx+1])
            setcrits.append(crit)
            if crit:
                tagType : TagType = _getTagTypeByName(crit)
                if tagType:
                    filterargs[_getTagTypeByName(crit).getTagName()] = value
        else:
            value = None
            break
    return crit, value, setcrits, filterargs

msgproc.mainloop()

