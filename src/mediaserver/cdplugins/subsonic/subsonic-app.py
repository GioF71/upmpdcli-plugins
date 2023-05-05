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
from upmplgutils import uplog, setidprefix, direntry, getOptionValue

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

from item_identifier_key import ItemIdentifierKey
from item_identifier import ItemIdentifier

from codec import Codec

from album_util import sort_song_list
from album_util import get_album_base_path
from album_util import get_dir_from_path
from album_util import get_last_path_element
from album_util import MultiCodecAlbum
from album_util import AlbumTracks
from album_util import SortSongListResult

from item_cache import ItemCache

from genre_artist_cache import GenreArtistCache

import libsonic

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = "0$subsonic$"
setidprefix("subsonic")

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

class ElementType(Enum):
    
    TAG   = 0, "tag"
    ALBUM = 1, "album"
    GENRE_PAGED = 2, "genre_paged"
    GENRE_FLOWING = 3, "genre_flowing"
    GENRE_FLOWING_ARTISTS = 4, "genre_flowing_artists"
    GENRE_FLOWING_ALBUMS = 5, "genre_flowing_albums"
    ARTIST = 6, "artist"
    GENRE_ARTIST = 7, "genre_artist"
    ARTIST_INITIAL = 8, "artist_initial"
    TRACK = 9, "track"
    NEWEST_PAGED_PAGE = 10, "newest_paged_page"
    GENRE_PAGED_PAGE = 11, "genre_page"
    NEXT_PAGE = 12, "next_page"

    def __init__(self, 
            num : int, 
            element_name : str):
        self.num : int = num
        self.element_name : str = element_name

    def getName(self):
        return self.element_name

class TagType(Enum):
    
    NEWEST_FLOWING = 0, "newestflowing", "Newest Albums", "newest"
    NEWEST_PAGED = 1, "newestpaged", "Newest Albums (Paged)", "newest"
    RANDOM_FLOWING = 10, "randomflowing", "Random Albums", "random"
    RANDOM = 11, "random", "Random Albums (Single Page)", "random"
    GENRES_FLOWING = 20, "genresflowing", "Genres", None
    GENRES_PAGED = 21, "genrespaged", "Genres (Paged)", None
    ARTISTS = 30, "artists", "Artists", None
    ARTISTS_INDEXED = 40, "artistsindexed", "Artists (By Initial)", None

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
    
def _is_tag(tag_candidate : str) -> bool:
    for _, member in TagType.__members__.items():
        if member.getTagName() == tag_candidate: return True
    return False

def _getTagTypeByName(tag_name : str) -> TagType:
    #msgproc.log(f"_getTagTypeByName with {tag_name}")
    for _, member in TagType.__members__.items():
        if tag_name == member.getTagName():
            return member
    raise Exception(f"_getTagTypeByName with {tag_name} NOT found")

class UpmpdcliSubsonicConfig(ConfigurationInterface):
    
    def getBaseUrl(self) -> str: return getOptionValue('subsonicbaseurl')
    def getPort(self) -> int: return getOptionValue('subsonicport')
    def getUserName(self) -> str: return getOptionValue('subsonicuser')
    def getPassword(self) -> str: return getOptionValue('subsonicpassword')
    def getApiVersion(self) -> str: return libsonic.API_VERSION
    def getAppName(self) -> str: return "upmpdcli"

__subsonic_max_return_size : int = 500 # hard limit

__items_per_page : int = min(__subsonic_max_return_size, int(getOptionValue("subsonicitemsperpage", "36")))
__max_pages : int = int(getOptionValue("subsonicmaxpages", "36"))
__append_year_to_album : int = int(getOptionValue("subsonicappendyeartoalbum", "1"))
__append_codecs_to_album : int = int(getOptionValue("subsonicappendcodecstoalbum", "1"))
__whitelist_codecs : list[str] = str(getOptionValue("subsonicwhitelistcodecs", "alac,wav,flac,dsf")).split(",")
__allow_blacklisted_codec_in_song : int = int(getOptionValue("subsonicallowblacklistedcodecinsong", "1"))

__tag_enabled_prefix : str = "subsonictagenabled"

__tag_enabled_default : dict[str, bool] = {
    TagType.NEWEST_PAGED.getTagName(): False,
    TagType.RANDOM.getTagName(): False,
    TagType.GENRES_PAGED.getTagName(): False
}

__caches : dict[str, object] = {}

__thing_codec : Codec = Codec()
__item_cache : ItemCache = ItemCache()

__artist_initial_by_id : dict[str, str] = {}

_genre_artist_cache : GenreArtistCache = GenreArtistCache()

def _is_tag_enabled(tag_type : TagType) -> bool:
    enabled_default : bool = __tag_enabled_default[tag_type.getTagName()] if tag_type.getTagName() in __tag_enabled_default else True
    enabled_int : int = int(getOptionValue(f"{__tag_enabled_prefix}{tag_type.getTagName()}", "1" if enabled_default else "0"))
    return enabled_int == 1

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

def _is_element_cached(element_type : ElementType, key : str) -> bool:
    cache : dict = _get_element_cache(element_type)
    return key in cache

def _get_cached_element(element_type : ElementType, key : str) -> str | None:
    cache : dict = _get_element_cache(element_type)
    if key in cache:
        return cache[key]
    return None

connector = Connector(UpmpdcliSubsonicConfig())

def __initial_caching_by_newest():
    sz : int = None
    album_list : list[Album] = None
    offset : int = 0
    first_processed : bool = False
    while not album_list or len(album_list) == __subsonic_max_return_size:
        album_list = _get_albums(TagType.NEWEST_FLOWING.getQueryType(), size = __subsonic_max_return_size, offset = offset)
        msgproc.log(f"loaded {len(album_list)} albums ...")
        album : Album
        for album in album_list:
            if not first_processed:
                # action to do once
                _cache_element_value(ElementType.TAG, TagType.NEWEST_FLOWING.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.NEWEST_PAGED.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.GENRES_PAGED.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.GENRES_FLOWING.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.ARTISTS.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.ARTISTS_INDEXED.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.RANDOM_FLOWING.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.RANDOM.getTagName(), album.getId())
                first_processed = True
            # for every album
            genre : str = album.getGenre()
            if not _is_element_cached(ElementType.GENRE_PAGED, genre):
                _cache_element_value(ElementType.GENRE_PAGED, genre, album.getId())
            if not _is_element_cached(ElementType.GENRE_FLOWING, genre):
                _cache_element_value(ElementType.GENRE_FLOWING, genre, album.getId())
            artist_id : str = album.getArtistId()
            if not _is_element_cached(ElementType.ARTIST, artist_id):
                _cache_element_value(ElementType.ARTIST, artist_id, album.getId())
        offset += len(album_list)

def __initial_caching_by_artist_initials():
    #create art cache for artists by initial
    artists_response : Response[Artists] = connector.getArtists()
    if not artists_response.isOk(): return
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
        __initial_caching_of_artist_initial(current_artists_initial)

def __initial_caching_of_artist_initial(current_artists_initial : ArtistsInitial):
    artist_list_items : list[ArtistListItem] = current_artists_initial.getArtistListItems()
    if len(artist_list_items) == 0: return
    current : ArtistListItem
    for current in artist_list_items:
        artist_id : str = current.getId()
        if _is_element_cached(ElementType.ARTIST, artist_id):
            _cache_element_value(
                ElementType.ARTIST_INITIAL, 
                current_artists_initial.getName(), 
                _get_cached_element(
                    ElementType.ARTIST,
                    artist_id))
            # finished for initial
            return

def __initial_caching_tags():
    tag_type_list : list[TagType] = [
        TagType.GENRES_PAGED, 
        TagType.GENRES_FLOWING,
        TagType.ARTISTS, 
        TagType.ARTISTS_INDEXED, 
        TagType.RANDOM_FLOWING, 
        TagType.RANDOM]
    sz : int = len(tag_type_list)
    album_list : list[Album] = _get_albums(TagType.RANDOM_FLOWING.getQueryType(), sz)
    index : int = 0
    tag_type : TagType
    for tag_type in tag_type_list:
        _cache_element_value(ElementType.TAG, tag_type.getTagName(), album_list[index].getId())
        index += 1

def __initial_caching():
    __initial_caching_by_newest()
    __initial_caching_by_artist_initials()
    __initial_caching_tags()

__subsonic_plugin_release : str = "0.1.2"

# Possible once initialisation. Always called by browse() or search(), should remember if it has
# something to do (e.g. the _g_init thing, but this could be something else).
_g_init = False
def _initsubsonic():
    global _g_init
    if _g_init:
        return True

    # Do whatever is needed here
    msgproc.log(f"Subsonic Plugin Release {__subsonic_plugin_release}")
    msgproc.log(f"Subsonic Initializing ...")
    __initial_caching()
    msgproc.log(f"Subsonic Initialization complete.")
            
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

def _set_album_art_from_uri(album_art_uri : str, target : dict):
    target['upnp:albumArtURI'] = album_art_uri

def _set_album_art_from_album_id(album_id : str, target : dict):
    art_uri : str = connector.buildCoverArtUrl(album_id)
    _set_album_art_from_uri(art_uri, target)

def _set_track_number(track_number : str, target : dict):
    target['upnp:originalTrackNumber'] = track_number

def _album_version_to_entry(
        objid, 
        current_album : Album, 
        version_number : int, 
        album_version_path : str,
        codec_set : set[str]) -> direntry:
    thing_id : str = "{}-version-{}-{}".format(
        ElementType.ALBUM.getName(), 
        version_number,
        current_album.getId())
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    title : str = f"Version #{version_number}"
    if __append_year_to_album == 1 and current_album.getYear() is not None:
        title = "{} [{}]".format(title, current_album.getYear())
    codecs_str : str = ",".join(codec_set)
    title = "{} [{}]".format(title, codecs_str)
    last_path : str = get_last_path_element(album_version_path)
    title = "{} [{}]".format(title, last_path)
    artist = current_album.getArtist()
    _cache_element_value(ElementType.GENRE_PAGED, current_album.getGenre(), current_album.getId())
    _cache_element_value(ElementType.GENRE_FLOWING, current_album.getGenre(), current_album.getId())
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
    album_identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), current_album.getId())
    album_identifier.set(ItemIdentifierKey.ALBUM_VERSION_PATH, album_version_path)
    #msgproc.log(f"_album_to_entry storing with thing_key {thing_key} id {id}")
    __item_cache.add(thing_key, album_identifier)
    #msgproc.log(f"_album_to_entry caching artist_id {current_album.getArtistId()} to genre {current_album.getGenre()} [{cached}]")
    return entry

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
        album_tracks : AlbumTracks = _get_album_tracks(current_album.getId())
        song_list : list[Song] = album_tracks.getSongList()
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
        # show version count if count > 1
        if album_tracks.getAlbumVersionCount() > 1:
            title = "{} [{} versions]".format(title, album_tracks.getAlbumVersionCount())
        # show or not?
        all_whitelisted : bool = len(codecs) == whitelist_count
        if len(codecs) > 1 or not all_whitelisted:
            codecs.sort()
            codecs_str : str = ",".join(codecs)
            title = "{} [{}]".format(title, codecs_str)
    artist = current_album.getArtist()
    _cache_element_value(ElementType.GENRE_PAGED, current_album.getGenre(), current_album.getId())
    _cache_element_value(ElementType.GENRE_FLOWING, current_album.getGenre(), current_album.getId())
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
    album_identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), current_album.getId())
    album_identifier.set(ItemIdentifierKey.ALBUM_TRACKS, album_tracks)
    #msgproc.log(f"_album_to_entry storing with thing_key {thing_key} id {id}")
    __item_cache.add(thing_key, album_identifier)
    #msgproc.log(f"_album_to_entry caching artist_id {current_album.getArtistId()} to genre {current_album.getGenre()} [{cached}]")
    return entry

def _genre_flowing_to_entry(objid, current_genre : Genre) -> direntry:
    thing_id : str = "{}-{}".format(ElementType.GENRE_FLOWING.getName(), current_genre.getName())
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    name : str = current_genre.getName()
    #msgproc.log(f"_genre_flowing_to_entry for {name}")
    genre_art_uri = None
    genre_art : str = _get_cached_element(ElementType.GENRE_FLOWING, current_genre.getName())
    if genre_art:
        #msgproc.log(f"_genre_flowing_to_entry cache entry hit for {current_genre.getName()}")
        genre_art_uri = connector.buildCoverArtUrl(genre_art)
    #else:
    #    msgproc.log(f"_genre_flowing_to_entry cache entry miss for {current_genre.getName()}")
    entry = direntry(id, 
        objid, 
        name,
        arturi = genre_art_uri)
    genre_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_FLOWING.getName(), 
        current_genre.getName())
    #msgproc.log(f"_genre_paged_to_entry storing with thing_key {thing_key} id {id}")
    __item_cache.add(thing_key, genre_identifier)
    return entry

def _genre_paged_to_entry(objid, current_genre : Genre) -> direntry:
    thing_id : str = "{}-{}".format(ElementType.GENRE_PAGED.getName(), current_genre.getName())
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    name : str = current_genre.getName()
    #msgproc.log(f"_genre_paged_to_entry for {name}")
    genre_art_uri = None
    genre_art : str = _get_cached_element(ElementType.GENRE_PAGED, current_genre.getName())
    if genre_art:
        #msgproc.log(f"_genre_paged_to_entry cache entry hit for {current_genre.getName()}")
        genre_art_uri = connector.buildCoverArtUrl(genre_art)
    #else:
    #    msgproc.log(f"_genre_paged_to_entry cache entry miss for {current_genre.getName()}")
    entry = direntry(id, 
        objid, 
        name,
        arturi = genre_art_uri)
    genre_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_PAGED.getName(), 
        current_genre.getName())
    #msgproc.log(f"_genre_paged_to_entry storing with thing_key {thing_key} id {id}")
    __item_cache.add(thing_key, genre_identifier)
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
        _set_album_art_from_album_id(art_id, entry)
    newest_page_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.NEWEST_PAGED_PAGE.getName(), 
        p_0_based)
    newest_page_identifier.set(ItemIdentifierKey.PAGE_NUMBER, p_0_based)
    __item_cache.add(thing_key, newest_page_identifier)
    return entry

def _genre_page_to_entry(objid, genre : str, p_0_based : int, low : int) -> direntry:
    # need a unique key
    thing_id : str = "{}-{}-{}".format(ElementType.GENRE_PAGED_PAGE.getName(), low, genre)
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    name : str = "Page {}".format(p_0_based + 1)
    entry = direntry(id, 
        objid, 
        name)
    art_uri = None
    art_id : str = _get_cached_element(ElementType.GENRE_PAGED_PAGE, thing_key)
    if art_id:
        _set_album_art_from_album_id(art_id, entry)
    genre_page_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_PAGED_PAGE.getName(), 
        genre)
    # no ambiguity as the value does not fully describe the item
    genre_page_identifier.set(ItemIdentifierKey.GENRE, genre)
    genre_page_identifier.set(ItemIdentifierKey.PAGE_NUMBER, p_0_based)
    __item_cache.add(thing_key, genre_page_identifier)
    return entry

def _genre_artist_to_entry(
        objid, 
        artist_id : str,
        genre : str,
        artist_name : str) -> direntry:
    thing_id: str = "{}-{}-{}-{}".format(
        ElementType.ARTIST.getName(), 
        artist_id,
        ElementType.GENRE_FLOWING.getName(),
        genre)
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    #msgproc.log(f"_artist_to_entry for {artist_name}")
    artist_art_uri = None
    artist_art : str = _get_cached_element(ElementType.GENRE_ARTIST, thing_key)
    if not artist_art:
        # try art for artist in general
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
    artist_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ARTIST.getName(), 
        artist_id)
    artist_identifier.set(ItemIdentifierKey.GENRE, genre)
    __item_cache.add(thing_key, artist_identifier)
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
    artist_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(), 
        artist_id)
    __item_cache.add(thing_key, artist_identifier)
    return entry

def _next_to_entry(
        objid, 
        element_type : ElementType,
        next_page_type : TagType,
        offset : int) -> direntry:
    #msgproc.log(f"_next_to_entry for type: {element_type.getName()} offset: {offset}")
    thing_id: str = "{}-{}-{}".format(element_type.getName(), next_page_type.getTagName(), offset)
    thing_key : str = __thing_codec.encode(thing_id)
    msgproc.log(f"_next_to_entry for type: {element_type.getName()} thing_id {thing_id} thing_key {thing_key}")
    id : str = _create_objid_simple(objid, thing_key)
    # no art for this item
    entry = direntry(id, 
        objid, 
        "Next")
    next_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.NEXT_PAGE.getName(), 
        next_page_type.getTagName())
    next_identifier.set(ItemIdentifierKey.TAG_TYPE, next_page_type)
    next_identifier.set(ItemIdentifierKey.OFFSET, offset)
    __item_cache.add(thing_key, next_identifier)
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
    artist_initial_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_INITIAL.getName(), 
        artist_initial)
    __item_cache.add(thing_key, artist_initial_identifier)
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
    _set_album_art_from_uri(albumArtURI, entry)
    entry['duration'] = str(song.getDuration())
    return entry

def _get_albums(query_type : str, size : int = __items_per_page, offset : int = 0) -> list[Album]:
    albumListResponse : Response[AlbumList]
    if TagType.NEWEST_PAGED.getQueryType() == query_type:
        albumListResponse  = connector.getNewestAlbumList(size = size, offset = offset)
    elif TagType.RANDOM.getQueryType() == query_type:
        albumListResponse = connector.getRandomAlbumList(size = size, offset = offset)
    if albumListResponse.isOk():
        return albumListResponse.getObj().getAlbums()
    return None        

def _get_album_tracks(album_id : str) -> AlbumTracks:
    result : list[Song] = []
    albumResponse : Response[Album] = connector.getAlbum(album_id)
    if not albumResponse.isOk(): raise Exception(f"Album with id {album_id} not found")
    album : Album = albumResponse.getObj()
    albumArtURI : str = connector.buildCoverArtUrl(album.getId())
    song_list : list[Song] = album.getSongs()
    sort_song_list_result : SortSongListResult = sort_song_list(song_list)
    current_song : Song
    for current_song in sort_song_list_result.getSongList():
        result.append(current_song)
    albumArtURI : str = connector.buildCoverArtUrl(album.getId())
    return AlbumTracks(
        codec_set_by_path = sort_song_list_result.getCodecSetByPath(),
        album = album, 
        song_list = result, 
        art_uri = albumArtURI,
        multi_codec_album = sort_song_list_result.getMultiCodecAlbum())

def _load_album_tracks(
        objid, 
        album_id : str, 
        album_version_path : str,
        entries : list):
    #msgproc.log(f"_load_album_tracks with album_version_path [{album_version_path}]")
    album_tracks : AlbumTracks = _get_album_tracks(album_id)
    album : Album = album_tracks.getAlbum()
    song_list : list[Song] = album_tracks.getSongList()
    albumArtURI : str = album_tracks.getArtUri()
    multi_codec_album : MultiCodecAlbum = album_tracks.getMultiCodecAlbum()
    _cache_element_value(ElementType.GENRE_FLOWING_ALBUMS, album.getGenre(), album.getId())
    current_base_path : str = None
    track_num : int = 0
    for current_song in song_list:
        song_path : str = get_dir_from_path(current_song.getPath())
        song_path = get_album_base_path(song_path)
        #msgproc.log(f"_load_album_tracks song path is [{song_path}]")
        if album_version_path is None or album_version_path == song_path:
            new_base_path : str = get_album_base_path(get_dir_from_path(current_song.getPath()))
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
        _cache_element_value(ElementType.GENRE_PAGED, current_genre, current_album.getId())
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
        _cache_element_value(ElementType.GENRE_PAGED, current_genre, current_album.getId())
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
        _cache_element_value(ElementType.GENRE_PAGED, current_album.getGenre(), current_album.getId())
        entries.append(_album_to_entry(objid, current_album))
    return entries

def __load_albums_by_genre_artist(
        objid, 
        artist_id : str, 
        genre : str,
        item_key : str,
        entries : list) -> list:
    artist_response : Response[Artist] = connector.getArtist(artist_id)
    if not artist_response.isOk(): return entries
    album_list : list[Album] = artist_response.getObj().getAlbumList()
    current_album : Album
    artist_tag_cached : bool = False
    for current_album in album_list:
        if genre in current_album.getGenre():
            if not artist_tag_cached:
                _cache_element_value(ElementType.TAG, TagType.ARTISTS.getTagName(), current_album.getId())
                artist_tag_cached = True
            _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
            #msgproc.log(f"__load_albums_by_genre_artist caching for {ElementType.GENRE_FLOWING_ARTISTS.getName()} {genre} to album_id:{current_album.getId()}")
            _cache_element_value(ElementType.GENRE_FLOWING_ARTISTS, genre, current_album.getId())
            #msgproc.log(f"__load_albums_by_genre_artist caching for {ElementType.GENRE_FLOWING_ARTISTS.getName()} {current_album.getGenre()} album_id:{current_album.getId()}")
            _cache_element_value(ElementType.GENRE_FLOWING_ARTISTS, current_album.getGenre(), current_album.getId())
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

def _create_genre_pages(objid, genre : str, entries : list) -> list:
    low : int = 1
    for p in range(0, __max_pages):
        upper = low + __items_per_page
        msgproc.log(f"will add {low} to {upper - 1} for genre {genre}")
        entries.append(_genre_page_to_entry(objid, genre, p, low))
        low = upper
    return entries

def _create_list_of_genres_flowing(objid, entries : list) -> list:
    genres_response : Response[Genres] = connector.getGenres()
    if not genres_response.isOk(): return entries
    genre_list = genres_response.getObj().getGenres()
    genre_list.sort(key = lambda x: x.getName())
    current_genre : Genre
    for current_genre in genre_list:
        #msgproc.log(f"genre {current_genre.getName()} albumCount {current_genre.getAlbumCount()}")
        if current_genre.getAlbumCount() > 0:
            entry : dict = _genre_flowing_to_entry(objid, current_genre)
            entries.append(entry)
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
            entry : dict = _genre_paged_to_entry(objid, current_genre)
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
            _set_album_art_from_album_id(art_id, entry)
        current_artist : ArtistListItem
        # populate cache of artist by initial
        for current_artist in current_artists_initial.getArtistListItems():
            __artist_initial_by_id[current_artist.getId()] = current_artists_initial.getName()
    return entries

def _create_genre_page(objid, genre, offset : int, genre_page_id : str, entries : list) -> list:
    msgproc.log(f"_create_genre_page genre {genre} offset {offset} genre_page_id {genre_page_id}")
    album_list_response : Response[AlbumList] = connector.getAlbumList(
        ltype = ListType.BY_GENRE, 
        genre = genre,
        offset = offset,
        size = __items_per_page)
    once : bool = False
    if not album_list_response.isOk(): return entries
    album_list : list[Album] = album_list_response.getObj().getAlbums()
    msgproc.log(f"got {len(album_list)} albums for genre {genre}")
    current_album : Album
    for current_album in album_list:
        if not once:
            _cache_element_value(ElementType.TAG, TagType.GENRES_PAGED.getTagName(), current_album.getId())    
            _cache_element_value(ElementType.GENRE_PAGED_PAGE, genre_page_id, current_album.getId())
            once = True
        _cache_element_value(ElementType.GENRE_PAGED, genre, current_album.getId())
        _cache_element_value(ElementType.GENRE_PAGED, current_album.getGenre(), current_album.getId())
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
        _cache_element_value(ElementType.TAG, TagType.NEWEST_PAGED.getTagName(), art_id)
        if offset == 0:
            _cache_element_value(ElementType.TAG, TagType.NEWEST_PAGED.getTagName(), art_id)
    return entries

def _process_next_page_flowing(objid, item_identifier : ItemIdentifier, tag_type : TagType, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET)
    msgproc.log(f"_process_next_page_flowing tag_type {tag_type} offset {offset}")
    album_list : list[Album] = _get_albums(tag_type.getQueryType(), offset = offset)
    entries = _load_albums_from_album_list(objid, album_list, entries)
    if (len(album_list) == __items_per_page):
        entries.append(_next_to_entry(
            objid,
            ElementType.NEXT_PAGE,
            tag_type,
            offset + __items_per_page))
    # image for tag
    if len(album_list) > 0:
        msgproc.log(f"_process_next_page_flowing tag_type _cache_element_value for tag_type {tag_type.getTagName()} with album_id {album_list[0].getId()}")
        _cache_element_value(ElementType.TAG, tag_type.getTagName(), album_list[0].getId())
    return entries

def _present_album(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album_version_path : str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH)
    _load_album_tracks(objid, album_id, album_version_path, entries)
    return entries

def _show_tags(objid, entries : list) -> list:
    for tag in TagType:
        if _is_tag_enabled(tag):
            tagname : str = tag.getTagName()
            thing_id : str = "{}-{}".format(ElementType.TAG.getName(), tagname)
            thing_key : str = __thing_codec.encode(thing_id)
            tag_identifier : ItemIdentifier = ItemIdentifier(ElementType.TAG.getName(), tagname)
            __item_cache.add(thing_key, tag_identifier)
            id : str = _create_objid_simple(objid, thing_key)
            #id = objid + "/" + _escape_objid(tagname)
            entry : dict = direntry(
                id = id, 
                pid = objid, 
                title = _getTagTypeByName(tagname).getTagTitle())
            art_id = _get_cached_element(ElementType.TAG, tagname)
            if art_id:
                _set_album_art_from_album_id(art_id, entry)
            entries.append(entry)
    return entries

def _handler_tag_newest_paged(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    low : int = 1
    for p in range(0, __max_pages):
        upper = low + __items_per_page
        entries.append(_newest_page_to_entry(objid, p, low))
        low = upper
    return entries    

def _handler_tag_newest_flowing(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    entries = _load_albums_by_type(objid, entries, TagType.NEWEST_FLOWING)
    # current offset is 0, next is current + items per page
    if (len(entries) == __items_per_page):
        next_page : dict = _next_to_entry(
            objid,
            ElementType.NEXT_PAGE,
            TagType.NEWEST_FLOWING,
            __items_per_page)
        entries.append(next_page)
    return entries

def _handler_tag_random_flowing(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    entries = _load_albums_by_type(objid, entries, TagType.RANDOM_FLOWING)
    # current offset is 0, next is current + items per page
    if (len(entries) == __items_per_page):
        next_page : dict = _next_to_entry(
            objid,
            ElementType.NEXT_PAGE,
            TagType.RANDOM_FLOWING,
            __items_per_page)
        entries.append(next_page)
    return entries

def _handler_random(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    return _load_albums_by_type(objid, entries, TagType.RANDOM)

def _handler_tag_genres_paged(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_genres(objid, entries)

def _handler_tag_genres_flowing(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_genres_flowing(objid, entries)

def _handler_element_genre_paged(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_genre_pages(
        objid = objid, 
        genre = item_identifier.get(ItemIdentifierKey.THING_VALUE), 
        entries = entries)

def _genre_flowing_add_artists_node(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    genre : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_genre_flowing_add_artists_node genre {genre}")
    thing_id : str = "{}-{}".format(ElementType.GENRE_FLOWING_ARTISTS.getName(), genre)
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    name : str = "Artists" # TODO parametrize maybe?
    artists_entry = direntry(id, 
        objid, 
        name)
    art_id : str = _get_cached_element(ElementType.GENRE_FLOWING_ARTISTS, genre)
    if not art_id: 
        # try with genre
        art_id : str = _get_cached_element(ElementType.GENRE_FLOWING, genre)
    if art_id:
        _set_album_art_from_album_id(art_id, artists_entry)
    else:
        msgproc.log(f"_genre_flowing_add_artists_node art not found for {ElementType.GENRE_FLOWING_ARTISTS.getName()} genre {genre}")
    entries.append(artists_entry)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_FLOWING_ARTISTS.getName(), 
        genre)
    identifier.set(ItemIdentifierKey.GENRE, genre)
    __item_cache.add(thing_key, identifier)
    return entries

def _genre_flowing_add_albums_node(
        objid, 
        item_identifier : ItemIdentifier, 
        offset : int,
        entries : list) -> list:
    genre : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_genre_flowing_add_albums_node genre {genre}")
    thing_id : str = "{}-{}-{}".format(ElementType.GENRE_FLOWING_ALBUMS.getName(), offset, genre)
    thing_key : str = __thing_codec.encode(thing_id)
    id : str = _create_objid_simple(objid, thing_key)
    name : str = "Albums" if offset == 0 else "Next" # TODO parametrize maybe?
    artists_entry = direntry(id, 
        objid, 
        name)
    if offset == 0:
        art_id : str = None
        if _is_element_cached(ElementType.GENRE_FLOWING_ALBUMS, genre):
            art_id : str = _get_cached_element(ElementType.GENRE_FLOWING_ALBUMS, genre)
        if not art_id: 
            # try with genre
            art_id : str = _get_cached_element(ElementType.GENRE_FLOWING, genre)
        if art_id:
            _set_album_art_from_album_id(art_id, artists_entry)
    entries.append(artists_entry)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_FLOWING_ALBUMS.getName(), 
        genre)
    identifier.set(ItemIdentifierKey.GENRE, genre)
    identifier.set(ItemIdentifierKey.OFFSET, offset)
    __item_cache.add(thing_key, identifier)
    return entries

def _handler_element_genre_flowing(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    # add nodes for flowing albums by genre
    msgproc.log(f"_handler_element_genre_flowing")
    entries = _genre_flowing_add_artists_node(objid, item_identifier, entries)
    entries = _genre_flowing_add_albums_node(
        objid = objid, 
        item_identifier = item_identifier, 
        offset = 0,
        entries = entries)
    return entries

def _load_all_artists_by_genre(genre : str) -> set[str]:
    artist_id_set : set[str] = set()
    album_list : list[Album] = None
    offset : int = 0
    while not album_list or len(album_list) == __subsonic_max_return_size:
        album_list_response : Response[AlbumList] = connector.getAlbumList(
            ltype = ListType.BY_GENRE, 
            genre = genre,
            offset = offset,
            size = __subsonic_max_return_size)
        if not album_list_response.isOk(): return set()
        album_list : list[Album] = album_list_response.getObj().getAlbums()
        cached : bool = False
        album : Album
        for album in album_list:
            artist_id : str = album.getArtistId()
            if not artist_id in artist_id_set:
                artist_id_set.add(artist_id)
                if not cached:
                    _cache_element_value(ElementType.GENRE_FLOWING_ARTISTS, genre, album.getId())
                    cached = True
                #msgproc.log(f"_load_all_artists_by_genre adding {album.getArtist()}")
        offset += len(album_list)
    return artist_id_set

def _handler_element_genre_flowing_artists(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_genre_flowing_artists")
    genre : str = item_identifier.get(ItemIdentifierKey.GENRE)
    msgproc.log(f"_handler_element_genre_flowing_artists genre {genre}")
    # get all albums by genre and collect a set of artists
    artist_id_set : set[str] = _load_all_artists_by_genre(genre)
    # present the list of artists
    artists_response : Response[Artists] = connector.getArtists()
    if not artists_response.isOk(): return entries
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
        #msgproc.log(f"_handler_element_genre_flowing_artists genre {genre} current_initial {current_artists_initial.getName()}")
        artist_list_items : list[ArtistListItem] = current_artists_initial.getArtistListItems()
        current : ArtistListItem  
        for current in artist_list_items:
            artist_id : str = current.getId()
            if artist_id in artist_id_set:
                # can add
                entries.append(_genre_artist_to_entry(
                    objid, 
                    artist_id, 
                    genre,
                    current.getName()))
    return entries

def _handler_element_genre_flowing_albums(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_genre_flowing_albums")
    genre : str = item_identifier.get(ItemIdentifierKey.GENRE)
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET)
    msgproc.log(f"_handler_element_genre_flowing_albums genre {genre} offset {offset}")
    album_list_response : Response[AlbumList] = connector.getAlbumList(
        ltype = ListType.BY_GENRE, 
        genre = genre,
        offset = offset,
        size = __items_per_page)
    if not album_list_response.isOk(): return entries
    album_list : list[Album] = album_list_response.getObj().getAlbums()
    msgproc.log(f"got {len(album_list)} albums for genre {genre} from offset {offset}")
    once : bool = False
    current_album : Album
    for current_album in album_list:
        if not once:
            _cache_element_value(ElementType.TAG, TagType.GENRES_FLOWING.getTagName(), current_album.getId())    
            _cache_element_value(ElementType.GENRE_FLOWING_ALBUMS, item_key, current_album.getId())
            once = True
        _cache_element_value(ElementType.GENRE_FLOWING_ALBUMS, genre, current_album.getId())
        _cache_element_value(ElementType.GENRE_FLOWING_ALBUMS, current_album.getGenre(), current_album.getId())
        entries.append(_album_to_entry(objid, current_album))
    if len(album_list) == __items_per_page:
        # create next button
        entries = _genre_flowing_add_albums_node(
            objid = objid,
            item_identifier = item_identifier,
            offset = offset + __items_per_page,
            entries = entries)
    return entries

def _handler_tag_artists(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_artists(objid, entries)

def _handler_tag_artists_indexed(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_artist_initials(objid, entries)

def _handler_element_newest_paged_page(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_newest_paged_page item_key {item_key} value {item_identifier.get(ItemIdentifierKey.THING_VALUE)}")
    page_key : int = item_identifier.get(ItemIdentifierKey.PAGE_NUMBER)
    newest_page_offset : int = page_key * __items_per_page
    msgproc.log(f"match 1d (NEWEST_PAGED_PAGE) page_key: {page_key} offset {newest_page_offset}")
    _create_newest_page(
        objid, 
        offset = newest_page_offset, 
        newest_page_id = item_key, 
        entries = entries)
    return entries

def _handler_element_next_page(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    tag_type : TagType = item_identifier.get(ItemIdentifierKey.TAG_TYPE)
    if not tag_type: raise Exception(f"_handler_element_next_page --Invalid tag--")
    _process_next_page_flowing(objid, item_identifier, tag_type, entries)
    return entries

def _handler_element_artist_initial(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_artist_initial item_key {item_key}")
    artist_initial : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_artist_initial item_key {item_key} artist_initial {artist_initial}")
    entries = __load_artists_by_initial(objid, artist_initial, entries)
    return entries

def _handler_element_artist(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    artist : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    entries = __load_albums_by_artist(objid, artist, entries)
    return entries

def _handler_element_genre_artist(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    genre : str = item_identifier.get(ItemIdentifierKey.GENRE)
    msgproc.log(f"_handler_element_genre_artist artist_id {artist_id} genre {genre}")
    entries = __load_albums_by_genre_artist(
        objid, 
        artist_id = artist_id, 
        genre = genre, 
        item_key = item_key, 
        entries = entries)
    return entries

def _handler_element_genre_paged_page(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_genre_paged_page item_key {item_key}")
    genre : str = item_identifier.get(ItemIdentifierKey.GENRE)
    msgproc.log(f"_handler_element_genre_paged_page item_key {item_key} genre {genre}")
    page_number : int = item_identifier.get(ItemIdentifierKey.PAGE_NUMBER)
    msgproc.log(f"_handler_element_genre_paged_page item_key {item_key} genre {genre} page_number {page_number}")
    offset : int = page_number * __items_per_page
    entries = _create_genre_page(objid, 
        genre = genre, 
        offset = offset, 
        genre_page_id = item_key, 
        entries = entries)
    return entries

def _handler_element_album(objid, item_key : str, item_identifier : ItemIdentifier, entries : list) -> list:
    album_tracks : AlbumTracks = item_identifier.get(ItemIdentifierKey.ALBUM_TRACKS)
    if album_tracks and album_tracks.getAlbumVersionCount() > 1:
        msgproc.log(f"_handler_element_album we should now present the {album_tracks.getAlbumVersionCount()} versions")    
        version_counter : int = 0
        album_version_path : str
        codec_set : set[str]
        for album_version_path in album_tracks.getCodecSetByPath().keys():
            codec_set : set[str] = album_tracks.getCodecSetByPath()[album_version_path]
            album_version_entry : dict = _album_version_to_entry(
                objid = objid,
                current_album = album_tracks.getAlbum(),
                version_number = version_counter + 1,
                album_version_path = album_version_path,
                codec_set = codec_set)
            entries.append(album_version_entry)
            version_counter += 1
        return entries
    return _present_album(objid, item_identifier, entries)

__tag_action_dict : dict = {
    TagType.NEWEST_PAGED.getTagName(): _handler_tag_newest_paged,
    TagType.NEWEST_FLOWING.getTagName(): _handler_tag_newest_flowing,
    TagType.RANDOM_FLOWING.getTagName(): _handler_tag_random_flowing,
    TagType.RANDOM.getTagName(): _handler_random,
    TagType.GENRES_PAGED.getTagName(): _handler_tag_genres_paged,
    TagType.GENRES_FLOWING.getTagName(): _handler_tag_genres_flowing,
    TagType.ARTISTS.getTagName(): _handler_tag_artists,
    TagType.ARTISTS_INDEXED.getTagName(): _handler_tag_artists_indexed
}

__elem_action_dict : dict = {
    ElementType.GENRE_PAGED.getName(): _handler_element_genre_paged,
    ElementType.GENRE_FLOWING.getName(): _handler_element_genre_flowing,
    ElementType.NEWEST_PAGED_PAGE.getName(): _handler_element_newest_paged_page,
    ElementType.NEXT_PAGE.getName(): _handler_element_next_page,
    ElementType.ARTIST_INITIAL.getName(): _handler_element_artist_initial,
    ElementType.ARTIST.getName(): _handler_element_artist,
    ElementType.GENRE_ARTIST.getName(): _handler_element_genre_artist,
    ElementType.GENRE_PAGED_PAGE.getName(): _handler_element_genre_paged_page,
    ElementType.ALBUM.getName(): _handler_element_album,
    ElementType.GENRE_FLOWING_ARTISTS.getName(): _handler_element_genre_flowing_artists,
    ElementType.GENRE_FLOWING_ALBUMS.getName(): _handler_element_genre_flowing_albums
}

@dispatcher.record('browse')
def browse(a):
    msgproc.log(f"browse: args: --{a}--")
    _initsubsonic()
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    path = _objidtopath(objid)
    msgproc.log(f"browse: path: --{path}--")
    path_list : list[str] = objid.split("/")
    last_path_item : str = path_list[len(path_list) - 1] if path_list and len(path_list) > 0 else None
    msgproc.log(f"browse: path_list: --{path_list}-- last: --{last_path_item}--")
    entries = []
    if len(path_list) == 1 and _g_myprefix == last_path_item:
        # show tags
        entries = _show_tags(objid, entries)
        return _returnentries(entries)
    elif __item_cache.has(last_path_item):
        # decode
        item_identifier : ItemIdentifier = __item_cache.get(last_path_item)
        thing_name : str = item_identifier.get(ItemIdentifierKey.THING_NAME)
        thing_value : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
        msgproc.log(f"browse: item_identifier name: --{thing_name}-- value: --{thing_value}--")
        if ElementType.TAG.getName() == thing_name:
            msgproc.log(f"browse: should serve tag: --{thing_value}--")
            tag_handler = __tag_action_dict[thing_value] if thing_value in __tag_action_dict else None
            if tag_handler:
                msgproc.log(f"browse: found tag handler for: --{thing_value}--")
                entries = tag_handler(objid, last_path_item, item_identifier, entries)
                return _returnentries(entries)
            else:
                msgproc.log(f"browse: tag handler for: --{thing_value}-- not found")
        else: # it's an element
            msgproc.log(f"browse: should serve element: --{thing_name}-- [{thing_value}]")
            elem_handler = __elem_action_dict[thing_name] if thing_name in __elem_action_dict else None
            if elem_handler:
                msgproc.log(f"browse: found elem handler for: --{thing_name}--")
                entries = elem_handler(objid, last_path_item, item_identifier, entries)
            else:
                msgproc.log(f"browse: element handler for: --{thing_name}-- not found")
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
            _cache_element_value(ElementType.GENRE_PAGED, current_album.getGenre(), current_album.getId())
            entries.append(_album_to_entry(objid, current_album))
    elif ElementType.TRACK.getName() == field:
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
    elif ElementType.ARTIST.getName() == field:
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

    #msgproc.log(f"browse: returning --{entries}--")
    return _returnentries(entries)

msgproc.mainloop()

