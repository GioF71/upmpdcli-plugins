#!/usr/bin/python3
# Copyright (C) 2023 Giovanni Fulco
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

from codec import Codec
from album_util import sort_song_list
from album_util import get_album_base_path
from album_util import get_dir_from_path
from album_util import MultiCodecAlbum

import libsonic

class ElementType(Enum):
    
    TAG   = 0, "tag"
    ALBUM = 1, "album"
    GENRE = 2, "genre"
    ARTIST = 3, "artist"
    ARTIST_INITIAL = 4, "artist_initial"
    TRACK = 6, "track"
    NEWEST_PAGED_PAGE = 7, "newest_paged_page"
    NEWEST_SINGLE_PAGE = 8, "newest_single_page"
    GENRE_PAGE = 9, "genre_page"
    NEXT_PAGE = 10, "next_page"

    def __init__(self, 
            num : int, 
            element_name : str):
        self.num : int = num
        self.element_name : str = element_name

    def getName(self):
        return self.element_name

class TagType(Enum):
    
    NEWEST_FLOWING = 0, "newest_flowing", "Newest Albums (Flowing)", "newest"
    NEWEST_PAGED = 1, "newest_paged", "Newest Albums (Paged)", "newest"
    NEWEST_SINGLE = 2, "newest_single", "Newest Albums (Single Page)", "newest"
    RANDOM = 10, "random", "Random Albums", "random"
    GENRES = 20, "genres", "Genres", None
    ARTISTS = 30, "artists", "Artists", None
    ARTISTS_INDEXED = 40, "artists_indexed", "Artists (By Initial)", None

    def __init__(self, 
            num : int, 
            tag_name : str, 
            tag_title : str, 
            query_type : str):
        self.num : int = num
        self.tag_name : str = tag_name
        self.tag_title : str = tag_title
        self.query_type : str = query_type

    def getTagName(self) -> str:
        return self.tag_name

    def getTagTitle(self) -> str:
        return self.tag_title

    def getQueryType(self) -> str:
        return self.query_type
    
class ItemIdentifierKey(Enum):
    
    THING_NAME = 0, 'thing_name'
    THING_VALUE = 1, 'thing_value'
    GENRE = 2, 'genre'
    PAGE_NUMBER = 3, 'page_number'
    ALBUM_ID = 4, 'album_id'
    OFFSET = 5, 'offset'
    
    def __init__(self, 
            num : int, 
            key_name : str):
        self.num : int = num
        self.key_name : str = key_name
    
    def getName(self) -> str:
        return self.key_name
    
class ItemIdentifier:
    
    def __init__(self):
        self.__dict = {}

    def has(self, key : ItemIdentifierKey):
        return key.getName() in self.__dict
    
    def get(self, key : ItemIdentifierKey):
        return self.__dict[key.getName()] if key.getName() in self.__dict else None

    def set(self, key : ItemIdentifierKey, value):
        self.__dict[key.getName()] = value
    
def _getTagTypeByName(tag_name : str) -> TagType:
    #msgproc.log(f"_getTagTypeByName with {tag_name}")
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

__items_per_page : int = int(getOptionValue("subsonicitemsperpage", "36"))
__max_pages : int = int(getOptionValue("subsonicmaxpages", "36"))
__append_year_to_album : int = int(getOptionValue("subsonicappendyeartoalbum", "1"))
__append_codecs_to_album : int = int(getOptionValue("subsonicappendcodecstoalbum", "1"))
__whitelist_codecs : list[str] = str(getOptionValue("subsonicwhitelistcodecs", "alac,wav,flac,dsf")).split(",")
__allow_blacklisted_codec_in_song : int = int(getOptionValue("subsonicallowblacklistedcodecinsong", "1"))
__caches : dict[str, object] = {}

__thing_codec : Codec = Codec()
__thing_map : dict[str, ItemIdentifier] = {}

__artist_initial_by_id : dict[str, str] = {}

def _get_element_cache(element_type : ElementType) -> dict:
    if element_type.getName() in __caches:
        return __caches[element_type.getName()]
    cache = {}
    __caches[element_type.getName()] = cache
    return cache

def _cache_element_value(element_type : ElementType, key : str, value : str, force_update : bool = True):
    cache : dict = _get_element_cache(element_type)
    if force_update or (not key in cache):
        #msgproc.log(f"_cache_element_value: caching: {key} to {value} on type {element_type.getName()}")
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

def _create_objid_simple(objid, id : str) -> str:
    return objid + "/" + _escape_objid(id)

def _create_objid_for(objid, element_type : ElementType, id : str) -> str:
    return objid + "/" + _escape_objid(element_type.getName() + "-" + id)

def _escape_objid(value : str) -> str:
    return htmlescape(value, quote = True)

def _get_album_id(source : dict):
    return source['album_id'] if 'album_id' in source else None

def _set_album_id(album_id : str, target : dict):
    target['album_id'] = album_id

def _set_album_art_uri(album_art_uri : str, target : dict):
    target['upnp:albumArtURI'] = album_art_uri

def _set_track_number(track_number : str, target : dict):
    target['upnp:originalTrackNumber'] = track_number

def _set_album_art_uri(album_art_uri : str, target : dict):
    target['upnp:albumArtURI'] = album_art_uri

def _album_to_entry(objid, current_album : Album) -> direntry:
    thing_id : str = "{}-{}".format(ElementType.ALBUM.getName(), current_album.getId())
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    title : str = current_album.getTitle()
    if __append_year_to_album == 1 and current_album.getYear() is not None:
        title = "{} [{}]".format(title, current_album.getYear())
    if __append_codecs_to_album == 1:
        song_list : list[Song] = current_album.getSongs()
        # load album
        song_list, _, _ = _get_album_tracks(current_album.getId())
        codecs : list[str] = []
        whitelist_count : int = 0
        blacklist_count : int = 0
        song : Song
        for song in song_list:
            if not song.getSuffix() in codecs:
                codecs.append(song.getSuffix())
                if not song.getSuffix() in __whitelist_codecs:
                    blacklist_count += 1
                else:
                    whitelist_count += 1
        # show or not?
        all_whitelisted : bool = len(codecs) == whitelist_count
        if len(codecs) > 1 or not all_whitelisted:
            codecs.sort()
            codecs_str = ",".join(codecs)
            title = "{} [{}]".format(title, codecs_str)
    artist = current_album.getArtist()
    _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
    _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
    if current_album.getArtistId() in __artist_initial_by_id:
        _cache_element_value(ElementType.ARTIST_INITIAL, __artist_initial_by_id[current_album.getArtistId()], current_album.getId())
    arturi = connector.buildCoverArtUrl(current_album.getId())
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist,
        arturi = arturi)
    _set_album_id(current_album.getId(), entry)
    #msgproc.log(f"_album_to_entry creating album_identifier for album_id {current_album.getId()}")
    album_identifier : ItemIdentifier = _create_thing_identifier(ElementType.ALBUM.getName(), current_album.getId())
    #msgproc.log(f"_album_to_entry storing with thing_key {thing_key} id {id}")
    __thing_map[thing_key] = album_identifier
    return entry

def _genre_to_entry(objid, current_genre : Genre) -> direntry:
    thing_id : str = "{}-{}".format(ElementType.GENRE.getName(), current_genre.getName())
    thing_key : str = __thing_codec.encode(thing_id)
    #id : str = _create_objid_for(objid, ElementType.GENRE, __genre_codec.encode(current_genre.getName()))
    id : str = _create_objid_simple(objid, thing_key)
    name : str = current_genre.getName()
    #msgproc.log(f"_genre_to_entry for {name}")
    genre_art_uri = None
    genre_art : str = _get_cached_element(ElementType.GENRE, current_genre.getName())
    if genre_art:
        #msgproc.log(f"_genre_to_entry cache entry hit for {current_genre.getName()}")
        genre_art_uri = connector.buildCoverArtUrl(genre_art)
    #else:
    #    msgproc.log(f"_genre_to_entry cache entry miss for {current_genre.getName()}")
    entry = direntry(id, 
        objid, 
        name,
        arturi = genre_art_uri)
    genre_identifier : ItemIdentifier = _create_thing_identifier(
        ElementType.GENRE.getName(), 
        current_genre.getName())
    #msgproc.log(f"_genre_to_entry storing with thing_key {thing_key} id {id}")
    __thing_map[thing_key] = genre_identifier
    return entry

def _newest_page_to_entry(objid, p_0_based : int, low : int) -> direntry:
    # need a unique key
    thing_id : str = "{}-{}".format(TagType.NEWEST_PAGED.getTagName(), p_0_based)
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    name : str = "Page {}".format(p_0_based + 1)
    entry = direntry(id, 
        objid, 
        name)
    art_uri = None
    art_id : str = _get_cached_element(ElementType.NEWEST_PAGED_PAGE, thing_key)
    if art_id:
        art_uri = connector.buildCoverArtUrl(art_id)
        _set_album_art_uri(art_uri, entry)
    newest_page_identifier : ItemIdentifier = _create_thing_identifier(
        ElementType.NEWEST_PAGED_PAGE.getName(), 
        p_0_based)
    __thing_map[thing_key] = newest_page_identifier
    return entry

def _genre_page_to_entry(objid, genre : str, p_0_based : int, low : int) -> direntry:
    # need a unique key
    thing_id : str = "{}-{}-{}".format(ElementType.GENRE_PAGE.getName(), low, genre)
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    
    item_identifier : ItemIdentifier = ItemIdentifier()
    item_identifier.set(ItemIdentifierKey.GENRE, genre)
    item_identifier.set(ItemIdentifierKey.PAGE_NUMBER, p_0_based)

    #item_id : str = __genre_page_codec.encode(thing_id)
    #__genre_page_map[item_id] = item_identifier
    
    #id : str = _create_objid_for(objid, ElementType.GENRE_PAGE, item_id)
    name : str = "Page {}".format(p_0_based + 1)
    entry = direntry(id, 
        objid, 
        name)
    art_uri = None
    art_id : str = _get_cached_element(ElementType.GENRE_PAGE, thing_key)
    if art_id:
        art_uri = connector.buildCoverArtUrl(art_id)
        _set_album_art_uri(art_uri, entry)
    genre_page_identifier : ItemIdentifier = _create_thing_identifier(
        ElementType.GENRE_PAGE.getName(), 
        genre)
    # no ambiguity as the value does not fully describe the item
    genre_page_identifier.set(ItemIdentifierKey.GENRE, genre)
    genre_page_identifier.set(ItemIdentifierKey.PAGE_NUMBER, p_0_based)
    __thing_map[thing_key] = genre_page_identifier
    return entry

def _artist_to_entry(
        objid, 
        artist_id : str,
        artist_name : str) -> direntry:
    thing_id: str = "{}-{}".format(ElementType.ARTIST.getName(), artist_id)
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    #msgproc.log(f"_artist_to_entry for {artist_name}")
    artist_art_uri = None
    artist_art : str = _get_cached_element(ElementType.ARTIST, artist_id)
    if artist_art:
        #msgproc.log(f"_artist_to_entry cache entry hit for {artist_id}")
        artist_art_uri = connector.buildCoverArtUrl(artist_art)
    #else:
    #    msgproc.log(f"_artist_to_entry cache entry miss for {artist_id}")
    entry = direntry(id, 
        objid, 
        artist_name,
        arturi = artist_art_uri)
    artist_identifier : ItemIdentifier = _create_thing_identifier(
        ElementType.ARTIST.getName(), 
        artist_id)
    __thing_map[thing_key] = artist_identifier
    return entry

def _next_to_entry(
        objid, 
        element_type : ElementType,
        next_page_type : str,
        offset : int) -> direntry:
    #msgproc.log(f"_next_to_entry for type: {element_type.getName()} offset: {offset}")
    thing_id: str = "{}-{}-{}".format(element_type.getName(), next_page_type, offset)
    thing_key : str = __thing_codec.encode(thing_id)
    msgproc.log(f"_next_to_entry for type: {element_type.getName()} thing_id {thing_id} thing_key {thing_key}")
    id : str = _create_objid_simple(objid, thing_key)
    # no art for this item
    entry = direntry(id, 
        objid, 
        "Next")
    next_identifier : ItemIdentifier = _create_thing_identifier(
        ElementType.NEXT_PAGE.getName(), 
        next_page_type)
    next_identifier.set(ItemIdentifierKey.OFFSET, offset)
    __thing_map[thing_key] = next_identifier
    return entry


def _artist_list_item_to_entry(
        objid, 
        artist_initial : str) -> direntry:
    thing_id: str = "{}-{}".format(ElementType.ARTIST_INITIAL.getName(), artist_initial)
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    #msgproc.log(f"_artist_list_item_to_entry initial {artist_initial}")
    artist_art_uri = None
    artist_art : str = _get_cached_element(ElementType.ARTIST_INITIAL, artist_initial)
    if artist_art:
        artist_art_uri = connector.buildCoverArtUrl(artist_art)
    entry = direntry(id, 
        objid, 
        artist_initial,
        arturi = artist_art_uri)
    artist_identifier : ItemIdentifier = _create_thing_identifier(
        ElementType.ARTIST_INITIAL.getName(), 
        artist_initial)
    __thing_map[thing_key] = artist_identifier
    return entry

def _song_to_entry(
        objid, 
        song: Song, 
        albumArtURI : str = None,
        multi_codec_album : MultiCodecAlbum = MultiCodecAlbum.NO,
        track_num : int = None) -> dict:
    entry = {}
    id : str = _create_objid_for(objid, ElementType.TRACK, song.getId())
    entry['id'] = id
    entry['pid'] = song.getId()
    entry['upnp:class'] = 'object.item.audioItem.musicTrack'
    entry['uri'] = connector.buildSongUrlBySong(song)
    title : str = song.getTitle()
    if MultiCodecAlbum.YES == multi_codec_album and __allow_blacklisted_codec_in_song == 1 and (not song.getSuffix() in __whitelist_codecs):
        title = "{} [{}]".format(title, song.getSuffix())
    entry['tt'] = title
    entry['tp']= 'it'
    entry['discnumber'] = song.getDiscNumber()
    track_num : str = str(track_num) if track_num is not None else song.getTrack()
    _set_track_number(track_num, entry)
    entry['upnp:artist'] = song.getArtist()
    entry['upnp:album'] = song.getAlbum()
    entry['upnp:genre'] = song.getGenre()
    entry['res:mime'] = song.getContentType()
    if not albumArtURI:
        albumArtURI = connector.buildCoverArtUrl(song.getId())
    _set_album_art_uri(albumArtURI, entry)
    entry['duration'] = str(song.getDuration())
    return entry

def _get_thing_type(lastvalue : str) -> bool:
    lpath = lastvalue.split("-")
    if lpath and len(lpath) > 1:
        last = lpath[0]
        return last
    return False

def _create_thing_identifier(name : str, value : str) -> ItemIdentifier:
    id : ItemIdentifier = ItemIdentifier()
    id.set(ItemIdentifierKey.THING_NAME, name)
    id.set(ItemIdentifierKey.THING_VALUE, value)
    return id    

def _is_thing(value : str, thing_name : str) -> bool:
    id : ItemIdentifier = __thing_map[value] if value in __thing_map else None
    if not id or not id.has(ItemIdentifierKey.THING_NAME): return False
    return thing_name == id.get(ItemIdentifierKey.THING_NAME)

def _get_thing(value : str, thing_name : str) -> str:
    id : ItemIdentifier = __thing_map[value] if value in __thing_map else None
    if not id or not id.has(ItemIdentifierKey.THING_NAME): return None
    if not thing_name == id.get(ItemIdentifierKey.THING_NAME): return None
    return id.get(ItemIdentifierKey.THING_VALUE)

def _get_albums(query_type : str, size : int = __items_per_page, offset : int = 0) -> list[Album]:
    albumListResponse : Response[AlbumList]
    if TagType.NEWEST_PAGED.getQueryType() == query_type:
        albumListResponse  = connector.getNewestAlbumList(size = size, offset = offset)
    elif TagType.RANDOM.getQueryType() == query_type:
        albumListResponse = connector.getRandomAlbumList(size = size, offset = offset)
    if albumListResponse.isOk():
        return albumListResponse.getObj().getAlbums()
    return None        

def _get_album_tracks(album_id : str) -> tuple[list[Song], str, MultiCodecAlbum]:
    result : list[Song] = []
    albumResponse : Response[Album] = connector.getAlbum(album_id)
    if albumResponse.isOk():
        current_song : Song
        albumArtURI : str = connector.buildCoverArtUrl(albumResponse.getObj().getId())
        song_list : list[Song] = albumResponse.getObj().getSongs()
        multi_codec_album : MultiCodecAlbum
        song_list, multi_codec_album = sort_song_list(song_list)
        for current_song in song_list:
            result.append(current_song)
    albumArtURI : str = connector.buildCoverArtUrl(albumResponse.getObj().getId())
    return result, albumArtURI, multi_codec_album

def _load_album_tracks(objid, album_id : str, entries : list):
    song_list : list[Song]
    albumArtURI : str
    multi_codec_album : MultiCodecAlbum
    song_list, albumArtURI, multi_codec_album = _get_album_tracks(album_id)
    current_base_path : str = None
    track_num : int = 0
    for current_song in song_list:
        new_base_path = get_album_base_path(get_dir_from_path(current_song.getPath()))
        if not current_base_path:
            track_num = 1
        elif current_base_path == new_base_path:
            track_num += 1
        # maybe incorporate this in first condition in or
        # Wait for a test case to make suie it still works...
        elif not (current_base_path == new_base_path):
            track_num = 1
        #msgproc.log(f"_load_album_tracks current_base_path {current_base_path} new_base_path {new_base_path} track_num {track_num}")
        current_base_path = new_base_path
        entry = _song_to_entry(
            objid = objid, 
            song = current_song, 
            albumArtURI = albumArtURI, 
            multi_codec_album = multi_codec_album,
            track_num = str(track_num))
        entries.append(entry)

def _load_albums_from_album_list(
        objid, 
        album_list : list[Album],
        entries : list) -> list:
    sz : int = len(album_list)
    current_album : Album
    for current_album in album_list:
        entries.append(_album_to_entry(objid, current_album))
        # cache genre art
        current_genre : str = current_album.getGenre()
        _cache_element_value(ElementType.GENRE, current_genre, current_album.getId())
    return entries

# TODO maybe rebuild using _load_albums_from_album_list (?)
def _load_albums_by_type(
        objid, 
        entries : list, 
        tagType : TagType,
        offset : int = 0,
        size : int = __items_per_page) -> list:
    #offset : str = str(offset)
    albumList : list[Album] = _get_albums(tagType.getQueryType(), size = size, offset = str(offset))
    sz : int = len(albumList)
    current_album : Album
    tag_cached : bool = False
    for current_album in albumList:
        if tagType and (not tag_cached) and (offset == 0):
            _cache_element_value(ElementType.TAG, tagType.getTagName(), current_album.getId())
            tag_cached = True
        entries.append(_album_to_entry(objid, current_album))
        # cache genre art
        current_genre : str = current_album.getGenre()
        _cache_element_value(ElementType.GENRE, current_genre, current_album.getId())
    return entries

def __load_albums_by_artist(objid, artist_id : str, entries : list) -> list:
    artist_response : Response[Artist] = connector.getArtist(artist_id)
    if not artist_response.isOk(): return entries
    album_list : list[Album] = artist_response.getObj().getAlbumList()
    current_album : Album
    artist_tag_cached : bool = False
    for current_album in album_list:
        if not artist_tag_cached:
            _cache_element_value(ElementType.TAG, TagType.ARTISTS.getTagName(), current_album.getId())
            artist_tag_cached = True
        _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
        _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
        entries.append(_album_to_entry(objid, current_album))
    return entries

def __load_artists_by_initial(objid, artist_initial : str, entries : list) -> list:
    artists_response : Response[Artists] = connector.getArtists()
    if not artists_response.isOk(): return entries
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
        if current_artists_initial.getName() == artist_initial:
            current_artist : ArtistListItem
            for current_artist in current_artists_initial.getArtistListItems():
                if not current_artist.getId() in __artist_initial_by_id:
                    __artist_initial_by_id[current_artist.getId()] = current_artists_initial.getName()
                entry : dict = _artist_to_entry(
                    objid, 
                    current_artist.getId(), 
                    current_artist.getName())
                # if artist has art, set that art for initials
                artist_art : str = _get_cached_element(ElementType.ARTIST, current_artist.getId())
                if artist_art:
                    _cache_element_value(ElementType.TAG, TagType.ARTISTS_INDEXED.getTagName(), artist_art)
                entries.append(entry)
    return entries

def _create_newest_pages(objid, entries : list) -> list:
    low : int = 1
    for p in range(0, __max_pages):
        upper = low + __items_per_page
        entries.append(_newest_page_to_entry(objid, p, low))
        low = upper
    return entries    

def _create_genre_pages(objid, genre : str, entries : list) -> list:
    low : int = 1
    for p in range(0, __max_pages):
        upper = low + __items_per_page
        #msgproc.log(f"will add {low} to {upper - 1}")
        entries.append(_genre_page_to_entry(objid, genre, p, low))
        low = upper
    return entries

def _create_list_of_genres(objid, entries : list) -> list:
    genres_response : Response[Genres] = connector.getGenres()
    if not genres_response.isOk(): return entries
    genre_list = genres_response.getObj().getGenres()
    genre_list.sort(key = lambda x: x.getName())
    current_genre : Genre
    for current_genre in genre_list:
        #msgproc.log(f"genre {current_genre.getName()} albumCount {current_genre.getAlbumCount()}")
        if current_genre.getAlbumCount() > 0:
            entry : dict = _genre_to_entry(objid, current_genre)
            entries.append(entry)
    return entries

def _create_list_of_artists(objid, entries : list) -> list:
    artists_response : Response[Artists] = connector.getArtists()
    if not artists_response.isOk(): return entries
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
        current_artist : ArtistListItem
        for current_artist in current_artists_initial.getArtistListItems():
            entries.append(_artist_to_entry(
                objid, 
                current_artist.getId(), 
                current_artist.getName()))
            __artist_initial_by_id[current_artist.getId()] = current_artists_initial.getName()
    return entries

def _create_list_of_artist_initials(objid, entries : list) -> list:
    artists_response : Response[Artists] = connector.getArtists()
    if not artists_response.isOk(): return entries
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
        entry : dict = _artist_list_item_to_entry(
            objid, 
            current_artists_initial.getName())
        entries.append(entry)
        art_id = _get_cached_element(ElementType.ARTIST_INITIAL, current_artists_initial.getName())
        if art_id:
            art_uri : str = connector.buildCoverArtUrl(art_id)
            _set_album_art_uri(art_uri, entry)
        current_artist : ArtistListItem
        # populate cache of artist by initial
        for current_artist in current_artists_initial.getArtistListItems():
            __artist_initial_by_id[current_artist.getId()] = current_artists_initial.getName()
    return entries

def _create_genre_page(objid, genre, offset : int, genre_page_id : str, entries : list) -> list:
    album_list_response : Response[AlbumList] = connector.getAlbumList(
        ltype = ListType.BY_GENRE, 
        genre = genre,
        offset = offset,
        size = __items_per_page)
    once : bool = False
    if not album_list_response.isOk(): return entries
    album_list : list[Album] = album_list_response.getObj().getAlbums()
    #msgproc.log(f"got {len(album_list)} albums for genre {genre}")
    current_album : Album
    for current_album in album_list:
        if not once:
            _cache_element_value(ElementType.TAG, TagType.GENRES.getTagName(), current_album.getId())    
            _cache_element_value(ElementType.GENRE_PAGE, genre_page_id, current_album.getId())
            once = True
        _cache_element_value(ElementType.GENRE, genre, current_album.getId())
        _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
        entries.append(_album_to_entry(objid, current_album))
    return entries    

def _create_newest_page(objid, offset : int, newest_page_id : str, entries : list) -> list:
    _load_albums_by_type(
        objid, 
        entries, 
        TagType.NEWEST_PAGED, 
        offset = offset)
    #cache
    if len(entries) > 0:
        # grab first
        first : dict = entries[0]
        art_id = _get_album_id(first)
        _cache_element_value(ElementType.NEWEST_PAGED_PAGE, newest_page_id, art_id)
        if offset == 0:
            _cache_element_value(ElementType.TAG, TagType.NEWEST_PAGED.getTagName(), art_id)
    return entries

def _process_next_page_newest_flowing(objid, value : str, entries : list) -> list:
    next_page_identifier : ItemIdentifier = __thing_map[value]
    offset : int = next_page_identifier.get(ItemIdentifierKey.OFFSET)
    msgproc.log(f"_process_next_page_newest_flowing offset {offset}")
    album_list : list[Album] = _get_albums(TagType.NEWEST_FLOWING.getQueryType(), offset = offset)
    entries = _load_albums_from_album_list(objid, album_list, entries)
    if (len(album_list) == __items_per_page):
        entries.append(_next_to_entry(
            objid,
            ElementType.NEXT_PAGE,
            TagType.NEWEST_FLOWING.getTagName(),
            offset + __items_per_page))
    # image for tag
    if len(album_list) > 0:
        _cache_element_value(ElementType.TAG, TagType.NEWEST_FLOWING.getTagName(), album_list[0].getId())
    return entries

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
            msgproc.log(f"match 0c (album) with lastcrit --{lastcrit}--")
            album_id : str = _get_thing(lastcrit, ElementType.ALBUM.getName())
            _load_album_tracks(objid, album_id, entries)
            return _returnentries(entries)

    if (TagType.NEWEST_PAGED.getTagName() == lastcrit 
        or TagType.NEWEST_FLOWING.getTagName() == lastcrit 
        or TagType.NEWEST_SINGLE.getTagName() == lastcrit 
        or TagType.RANDOM.getTagName() == lastcrit):
        msgproc.log(f"match 1 with lastcrit: {lastcrit}")
        # reply with the list
        if lastvalue:
            #return selected page
            if _is_thing(lastvalue, ElementType.NEWEST_PAGED_PAGE.getName()):
                msgproc.log(f"match 1d (NEWEST_PAGED_PAGE) with lastvalue: {lastvalue}")
                page_key : int = _get_thing(lastvalue, ElementType.NEWEST_PAGED_PAGE.getName())
                newest_page_offset : int = page_key * __items_per_page
                #msgproc.log(f"match 1d (NEWEST_PAGED_PAGE) page_key: {page_key} offset {newest_page_offset}")
                _create_newest_page(
                    objid, 
                    offset = newest_page_offset, 
                    newest_page_id = lastvalue, 
                    entries = entries)
                return _returnentries(entries)
            elif _is_thing(lastvalue, ElementType.NEXT_PAGE.getName()):
                msgproc.log(f"match 1e (ElementType.NEXT_PAGE) with lastvalue: {lastvalue}")
                _process_next_page_newest_flowing(objid, lastvalue, entries)
                return _returnentries(entries)
        else:
            if TagType.NEWEST_PAGED.getTagName() == lastcrit:
                entries = _create_newest_pages(objid, entries)
                return _returnentries(entries)
            elif TagType.NEWEST_FLOWING.getTagName() == lastcrit:
                entries = _load_albums_by_type(objid, entries, _getTagTypeByName(lastcrit))
                # current offset is 0, next is current + items per page
                if (len(entries) == __items_per_page):
                    next_page : dict = _next_to_entry(
                        objid,
                        ElementType.NEXT_PAGE,
                        TagType.NEWEST_FLOWING.getTagName(),
                        __items_per_page)
                    entries.append(next_page)
                return _returnentries(entries)
            else:
                _load_albums_by_type(objid, entries, _getTagTypeByName(lastcrit))
                return _returnentries(entries)
    
    if TagType.GENRES.getTagName() == lastcrit:
        msgproc.log(f"match 2 with lastcrit: {lastcrit}")
        # reply with the list
        if lastvalue:
            if _is_thing(lastvalue, ElementType.GENRE.getName()):
                genre : str = _get_thing(lastvalue, ElementType.GENRE.getName())
                entries = _create_genre_pages(objid, genre, entries)
            return _returnentries(entries)
        else:
            # reply with list of genres
            entries = _create_list_of_genres(objid, entries)
            return _returnentries(entries)

    if TagType.ARTISTS.getTagName() == lastcrit:
        msgproc.log(f"match 4 with lastcrit: {lastcrit}")
        # reply with the list by artist
        if lastvalue and _is_thing(lastvalue, ElementType.ARTIST.getName()):
            #return albums by artist
            entries = __load_albums_by_artist(objid, _get_thing(lastvalue, ElementType.ARTIST.getName()), entries)
            return _returnentries(entries)    
        else:
            entries = _create_list_of_artists(objid, entries)
            return _returnentries(entries)
        
    if TagType.ARTISTS_INDEXED.getTagName() == lastcrit:
        msgproc.log(f"match 4 with lastcrit: {lastcrit}")
        # reply with the list by artist
        if lastvalue and _is_thing(lastvalue, ElementType.ARTIST_INITIAL.getName()):
            #return artists by initial
            msgproc.log(f"match 4 (album-initial) with lastcrit: {lastcrit}")
            artist_initial : str = _get_thing(lastvalue, ElementType.ARTIST_INITIAL.getName())
            entries = __load_artists_by_initial(objid, artist_initial, entries)
            return _returnentries(entries)    
        else:
            entries = _create_list_of_artist_initials(objid, entries)
            return _returnentries(entries)
        
    if lastvalue is None and lastcrit is not None:
        msgproc.log(f"match 3 with lastcrit: {lastcrit}")
        # process selection
        if _is_thing(lastcrit, ElementType.NEXT_PAGE.getName()):
            msgproc.log(f"match 3n (next) with lastcrit --{lastcrit}--")
            # process next page. of what?
            item_identifier : ItemIdentifier = __thing_map[lastcrit]
            if item_identifier:
                next_page_type : str = _get_thing(lastcrit, ElementType.NEXT_PAGE.getName())
                msgproc.log(f"match 3n (next) with next_page_type {next_page_type} lastcrit --{lastcrit}--")
                offset : int = item_identifier.get(ItemIdentifierKey.OFFSET)
                album_list : list[Album] = _get_albums(TagType.NEWEST_FLOWING.getQueryType(), offset = offset)
                entries = _load_albums_from_album_list(objid, album_list, entries)
                if (len(album_list) == __items_per_page):
                    entries.append(_next_to_entry(
                        objid,
                        ElementType.NEXT_PAGE,
                        TagType.NEWEST_FLOWING.getTagName(),
                        offset + __items_per_page))
            return _returnentries(entries)

        if _is_thing(lastcrit, ElementType.ALBUM.getName()):
            msgproc.log(f"match 3a (album) with lastcrit --{lastcrit}--")
            # process album
            album_id : str = _get_thing(lastcrit, ElementType.ALBUM.getName())
            _load_album_tracks(objid, album_id, entries)
            return _returnentries(entries)
    
        if _is_thing(lastcrit, ElementType.ARTIST.getName()):
            msgproc.log(f"match 3a (artist) with lastcrit --{lastcrit}--")
            # load albums from the selected artist
            artist_id : str = _get_thing(lastcrit, ElementType.ARTIST.getName())
            entries = __load_albums_by_artist(objid, artist_id, entries)
            return _returnentries(entries)
        
        if _is_thing(lastcrit, ElementType.GENRE_PAGE.getName()):
            msgproc.log(f"match 3a (genre_page) with lastcrit --{lastcrit}--")
            #return genre list page by genre for requested genre and offset
            genre_identifier : ItemIdentifier = __thing_map[lastcrit]
            #genre : str = _get_thing(lastcrit, ElementType.GENRE_PAGE.getName())
            genre : str = genre_identifier.get(ItemIdentifierKey.GENRE)
            page_number : int = genre_identifier.get(ItemIdentifierKey.PAGE_NUMBER)
            offset : int = page_number * __items_per_page
            entries = _create_genre_page(objid, 
                genre = genre, 
                offset = offset, 
                genre_page_id = lastcrit, 
                entries = entries)
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
                    _set_album_art_uri(connector.buildCoverArtUrl(art_id), entry)
                entries.append(entry)
        else:
            msgproc.log("match 0b")
            if lastvalue:
                if _is_thing(lastvalue, ElementType.ALBUM.getName()):
                    album_id : str = _get_thing(lastvalue, ElementType.ALBUM.getName())
                    _load_album_tracks(objid, album_id, entries)
                elif _is_thing(lastvalue, ElementType.NEXT_PAGE.getName()):
                    msgproc.log(f"match 0b (next_page) with lastvalue --{lastcrit}--")
                    next_page_type : str = _get_thing(lastvalue, ElementType.NEXT_PAGE.getName())
                    if TagType.NEWEST_FLOWING.getTagName() == next_page_type:
                        entries = _process_next_page_newest_flowing(objid, lastvalue, entries)
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
    
    msgproc.log(f"Search for [{value}] as {field}")
    
    if ElementType.ALBUM.getName() == field:
        # search albums by specified value
        search_result : SearchResult = connector.search(value, 
            artistCount = 0, 
            songCount = 0,
            albumCount = __items_per_page)
        album_list : list[Album] = search_result.getAlbums()
        current_album : Album
        filters : dict[str, str] = {}
        msgproc.log(f"search: filters = {filters}")
        for current_album in album_list:
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
            entries.append(_song_to_entry(
                objid = objid, 
                song = current_song))
        return _returnentries(entries)
    
    if ElementType.ARTIST.getName() == field:
        # search artists
        search_result : SearchResult = connector.search(value, 
            artistCount = __items_per_page, 
            songCount = 0,
            albumCount = 0)
        artist_list : list[Artist] = search_result.getArtists()
        current_artist : Artist
        for current_artist in artist_list:
            msgproc.log(f"found artist {current_artist.getName()}")
            entries.append(_artist_to_entry(
                objid, 
                current_artist.getId(),
                current_artist.getName()))
        return _returnentries(entries)

    # msgproc.log(f"browse: returning --{entries}--")
    return _returnentries(entries)

def _crittotitle(crit):
    """Translate filtering field name to displayed title"""
    return _getTagTypeByName(crit).getTagTitle()

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

