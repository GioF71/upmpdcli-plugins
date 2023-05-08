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

from tag_type import TagType
from element_type import ElementType

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

import libsonic

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = "0$subsonic$"
setidprefix("subsonic")

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

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
__append_year_to_album : int = int(getOptionValue("subsonicappendyeartoalbum", "1"))
__append_codecs_to_album : int = int(getOptionValue("subsonicappendcodecstoalbum", "1"))
__whitelist_codecs : list[str] = str(getOptionValue("subsonicwhitelistcodecs", "alac,wav,flac,dsf")).split(",")
__allow_blacklisted_codec_in_song : int = int(getOptionValue("subsonicallowblacklistedcodecinsong", "1"))

__tag_enabled_prefix : str = "subsonictagenabled"

__tag_enabled_default : dict[str, bool] = {
    TagType.RANDOM.getTagName(): True, # example
}

__caches : dict[str, object] = {}

__thing_codec : Codec = Codec()

__artist_initial_by_id : dict[str, str] = {}

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
    total_albums : int = 0
    first_processed : bool = False
    while not album_list or len(album_list) == __subsonic_max_return_size:
        album_list = _get_albums(TagType.NEWEST.getQueryType(), size = __subsonic_max_return_size, offset = offset)
        total_albums += len(album_list)
        msgproc.log(f"loaded {total_albums} albums ...")
        album : Album
        for album in album_list:
            if not first_processed:
                # action to do once
                _cache_element_value(ElementType.TAG, TagType.NEWEST.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.GENRES.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.ARTISTS_ALL.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.ARTISTS_INDEXED.getTagName(), album.getId())
                _cache_element_value(ElementType.TAG, TagType.RANDOM.getTagName(), album.getId())
                first_processed = True
            # for every album
            genre : str = album.getGenre()
            if not _is_element_cached(ElementType.GENRE, genre):
                _cache_element_value(ElementType.GENRE, genre, album.getId())
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
        TagType.GENRES,
        TagType.ARTISTS_ALL, 
        TagType.ARTISTS_INDEXED, 
        TagType.RANDOM]
    sz : int = len(tag_type_list)
    album_list : list[Album] = _get_albums(TagType.RANDOM.getQueryType(), sz)
    index : int = 0
    tag_type : TagType
    for tag_type in tag_type_list:
        _cache_element_value(ElementType.TAG, tag_type.getTagName(), album_list[index].getId())
        index += 1

def __initial_caching():
    __initial_caching_by_newest()
    __initial_caching_by_artist_initials()
    __initial_caching_tags()

__subsonic_plugin_release : str = "0.1.4"

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

def _escape_objid(value : str) -> str:
    return htmlescape(value, quote = True)

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
    #msgproc.log(f"_album_version_to_entry creating identifier for album_id {current_album.getId()}")
    identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), current_album.getId())
    avp_encoded : str = __thing_codec.encode(album_version_path)
    #msgproc.log(f"_album_version_to_entry storing path [{album_version_path}] as [{avp_encoded}]")
    identifier.set(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, avp_encoded)
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    #msgproc.log(f"_album_version_to_entry caching artist_id {current_album.getArtistId()} to genre {current_album.getGenre()} [{cached}]")
    title : str = f"Version #{version_number}"
    if __append_year_to_album == 1 and current_album.getYear() is not None:
        title = "{} [{}]".format(title, current_album.getYear())
    codecs_str : str = ",".join(codec_set)
    title = "{} [{}]".format(title, codecs_str)
    last_path : str = get_last_path_element(album_version_path)
    title = "{} [{}]".format(title, last_path)
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
    return entry

def _album_to_entry(objid, current_album : Album) -> direntry:
    #msgproc.log(f"_album_to_entry caching artist_id {current_album.getArtistId()} to genre {current_album.getGenre()} [{cached}]")
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
    _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
    _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
    if current_album.getArtistId() in __artist_initial_by_id:
        _cache_element_value(ElementType.ARTIST_INITIAL, __artist_initial_by_id[current_album.getArtistId()], current_album.getId())
    arturi = connector.buildCoverArtUrl(current_album.getId())
    #msgproc.log(f"_album_to_entry creating identifier for album_id {current_album.getId()}")
    identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), current_album.getId())
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist,
        arturi = arturi)
    _set_album_id(current_album.getId(), entry)
    return entry

def _genre_flowing_to_entry(objid, current_genre : Genre) -> direntry:
    name : str = current_genre.getName()
    #msgproc.log(f"_genre_flowing_to_entry for {name}")
    genre_art_uri = None
    genre_art : str = _get_cached_element(ElementType.GENRE, current_genre.getName())
    if genre_art:
        #msgproc.log(f"_genre_flowing_to_entry cache entry hit for {current_genre.getName()}")
        genre_art_uri = connector.buildCoverArtUrl(genre_art)
    #else:
    #    msgproc.log(f"_genre_flowing_to_entry cache entry miss for {current_genre.getName()}")
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE.getName(), 
        current_genre.getName())
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    entry = direntry(id, 
        objid, 
        name,
        arturi = genre_art_uri)
    #msgproc.log(f"_genre_flowing_to_entry storing with thing_key {thing_key} id {id}")
    return entry

def _genre_artist_to_entry(
        objid, 
        artist_id : str,
        genre : str,
        artist_name : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ARTIST.getName(), 
        artist_id)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    #msgproc.log(f"_genre_artist_to_entry for {artist_name}")
    artist_art_uri = None
    artist_art : str = _get_cached_element(ElementType.GENRE_ARTIST, artist_id)
    if not artist_art:
        # try art for artist in general
        artist_art : str = _get_cached_element(ElementType.ARTIST, artist_id)
    if artist_art:
        #msgproc.log(f"_genre_artist_to_entry cache entry hit for {artist_id}")
        artist_art_uri = connector.buildCoverArtUrl(artist_art)
    #else:
    #    msgproc.log(f"_genre_artist_to_entry cache entry miss for {artist_id}")
    entry = direntry(id, 
        objid, 
        artist_name,
        arturi = artist_art_uri)
    return entry

def _artist_to_entry(
        objid, 
        artist_id : str,
        artist_name : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(), 
        artist_id)
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
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
    return entry

def _artist_list_item_to_entry(
        objid, 
        artist_initial : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_INITIAL.getName(), 
        artist_initial)
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    #msgproc.log(f"_artist_list_item_to_entry initial {artist_initial}")
    artist_art_uri = None
    artist_art : str = _get_cached_element(ElementType.ARTIST_INITIAL, artist_initial)
    if artist_art:
        artist_art_uri = connector.buildCoverArtUrl(artist_art)
    entry = direntry(id, 
        objid, 
        artist_initial,
        arturi = artist_art_uri)
    return entry

def _song_data_to_entry(objid, entry_id : str, song : Song) -> dict:
    entry : dict = {}
    entry['id'] = entry_id
    entry['pid'] = song.getId()
    entry['upnp:class'] = 'object.item.audioItem.musicTrack'
    entry['uri'] = connector.buildSongUrlBySong(song)
    title : str = song.getTitle()
    entry['tt'] = title
    entry['tp']= 'it'
    entry['discnumber'] = song.getDiscNumber()
    _set_track_number(song.getTrack(), entry)
    entry['upnp:artist'] = song.getArtist()
    entry['upnp:album'] = song.getAlbum()
    entry['upnp:genre'] = song.getGenre()
    entry['res:mime'] = song.getContentType()
    albumArtURI : str = connector.buildCoverArtUrl(song.getId())
    _set_album_art_from_uri(albumArtURI, entry)
    entry['duration'] = str(song.getDuration())
    return entry

def _song_to_entry(
        objid, 
        song: Song, 
        albumArtURI : str = None,
        multi_codec_album : MultiCodecAlbum = MultiCodecAlbum.NO,
        track_num : int = None) -> dict:
    entry = {}
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), song.getId())
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    entry['id'] = id
    entry['pid'] = song.getId()
    entry['upnp:class'] = 'object.item.audioItem.musicTrack'
    song_uri : str = connector.buildSongUrlBySong(song)
    entry['uri'] = song_uri
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
    if TagType.NEWEST.getQueryType() == query_type:
        albumListResponse = connector.getNewestAlbumList(size = size, offset = offset)
    elif TagType.RANDOM.getQueryType() == query_type:
        albumListResponse = connector.getRandomAlbumList(size = size, offset = offset)
    if not albumListResponse.isOk(): raise Exception(f"Cannot execute query {query_type} for size {size} offset {offset}")
    return albumListResponse.getObj().getAlbums()

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
        entries : list) -> list:
    #msgproc.log(f"_load_album_tracks with album_version_path [{album_version_path}]")
    album_tracks : AlbumTracks = _get_album_tracks(album_id)
    album : Album = album_tracks.getAlbum()
    song_list : list[Song] = album_tracks.getSongList()
    albumArtURI : str = album_tracks.getArtUri()
    multi_codec_album : MultiCodecAlbum = album_tracks.getMultiCodecAlbum()
    _cache_element_value(ElementType.GENRE_ALBUM_LIST, album.getGenre(), album.getId())
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
    return entries

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
            _cache_element_value(ElementType.TAG, TagType.ARTISTS_ALL.getTagName(), current_album.getId())
            artist_tag_cached = True
        _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
        _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
        entries.append(_album_to_entry(objid, current_album))
    return entries

def __load_albums_by_genre_artist(
        objid, 
        artist_id : str, 
        genre : str,
        entries : list) -> list:
    artist_response : Response[Artist] = connector.getArtist(artist_id)
    if not artist_response.isOk(): return entries
    album_list : list[Album] = artist_response.getObj().getAlbumList()
    current_album : Album
    artist_tag_cached : bool = False
    for current_album in album_list:
        if genre in current_album.getGenre():
            if not artist_tag_cached:
                _cache_element_value(ElementType.TAG, TagType.ARTISTS_ALL.getTagName(), current_album.getId())
                artist_tag_cached = True
            _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
            #msgproc.log(f"__load_albums_by_genre_artist caching for {ElementType.GENRE_ARTIST_LIST.getName()} {genre} to album_id:{current_album.getId()}")
            _cache_element_value(ElementType.GENRE_ARTIST_LIST, genre, current_album.getId())
            #msgproc.log(f"__load_albums_by_genre_artist caching for {ElementType.GENRE_ARTIST_LIST.getName()} {current_album.getGenre()} album_id:{current_album.getId()}")
            _cache_element_value(ElementType.GENRE_ARTIST_LIST, current_album.getGenre(), current_album.getId())
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

def _present_album(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album_version_path : str = None
    if item_identifier.has(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64):
        #msgproc.log(f"item_identifier has [{ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64.getName()}] set to [{item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64)}]")
        avp_encoded : str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64)
        album_version_path = __thing_codec.decode(avp_encoded)
        #msgproc.log(f"_present_album decoding path [{avp_encoded}] to [{album_version_path}]")
    return _load_album_tracks(objid, album_id, album_version_path, entries)

def _create_tag_next_entry(
        objid, 
        tag : TagType, 
        offset : int) -> dict:
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TAG.getName(), tag.getTagName())
    identifier.set(ItemIdentifierKey.OFFSET, offset)
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    tag_entry : dict = direntry(
        id = id, 
        pid = objid, 
        title = "Next")
    return tag_entry

def _show_tags(objid, entries : list) -> list:
    for tag in TagType:
        if _is_tag_enabled(tag):
            tagname : str = tag.getTagName()
            identifier : ItemIdentifier = ItemIdentifier(ElementType.TAG.getName(), tagname)
            id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
            entry : dict = direntry(
                id = id, 
                pid = objid, 
                title = _getTagTypeByName(tag.getTagName()).getTagTitle())
            art_id = _get_cached_element(ElementType.TAG, tag.getTagName())
            if art_id:
                _set_album_art_from_album_id(art_id, entry)
            entries.append(entry)
    return entries

def _handler_tag_newest_flowing(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    entries = _load_albums_by_type(
        objid = objid, 
        entries = entries, 
        tagType = TagType.NEWEST, 
        offset = offset)
    # offset is: current offset + the entries length
    if (len(entries) == __items_per_page):
        next_page : dict = _create_tag_next_entry(
            objid = objid, 
            tag = TagType.NEWEST, 
            offset = offset + len(entries))
        entries.append(next_page)
    return entries

def _handler_tag_random_flowing(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    entries = _load_albums_by_type(
        objid = objid, 
        entries = entries, 
        tagType = TagType.RANDOM,
        offset = offset)
    # current offset is 0, next is current + items per page
    if (len(entries) == __items_per_page):
        next_page : dict = _create_tag_next_entry(
            objid = objid, 
            tag = TagType.RANDOM, 
            offset = offset + len(entries))
        entries.append(next_page)
    return entries

def _handler_tag_genres_flowing(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_genres_flowing(objid, entries)

def _genre_flowing_add_artists_node(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    genre : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_genre_flowing_add_artists_node genre {genre}")
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ARTIST_LIST.getName(), 
        genre)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    name : str = "Artists" # TODO parametrize maybe?
    artists_entry = direntry(id, 
        objid, 
        name)
    art_id : str = _get_cached_element(ElementType.GENRE_ARTIST_LIST, genre)
    if not art_id: 
        # try with genre
        art_id : str = _get_cached_element(ElementType.GENRE, genre)
    if art_id:
        _set_album_art_from_album_id(art_id, artists_entry)
    else:
        msgproc.log(f"_genre_flowing_add_artists_node art not found for {ElementType.GENRE_ARTIST_LIST.getName()} genre {genre}")
    entries.append(artists_entry)
    return entries

def _genre_flowing_add_albums_node(
        objid, 
        item_identifier : ItemIdentifier, 
        offset : int,
        entries : list) -> list:
    genre : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_genre_flowing_add_albums_node genre {genre}")
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ALBUM_LIST.getName(), 
        genre)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    identifier.set(ItemIdentifierKey.OFFSET, offset)
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    name : str = "Albums" if offset == 0 else "Next" # TODO parametrize maybe?
    artists_entry = direntry(id, 
        objid, 
        name)
    if offset == 0:
        art_id : str = None
        if _is_element_cached(ElementType.GENRE_ALBUM_LIST, genre):
            art_id : str = _get_cached_element(ElementType.GENRE_ALBUM_LIST, genre)
        if not art_id: 
            # try with genre
            art_id : str = _get_cached_element(ElementType.GENRE, genre)
        if art_id:
            _set_album_art_from_album_id(art_id, artists_entry)
    entries.append(artists_entry)
    return entries

def _handler_element_genre_flowing(objid, item_identifier : ItemIdentifier, entries : list) -> list:
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
                    _cache_element_value(ElementType.GENRE_ARTIST_LIST, genre, album.getId())
                    cached = True
                #msgproc.log(f"_load_all_artists_by_genre adding {album.getArtist()}")
        offset += len(album_list)
    return artist_id_set

def _handler_element_genre_flowing_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_genre_flowing_artists")
    genre : str = item_identifier.get(ItemIdentifierKey.GENRE_NAME)
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

def _handler_element_genre_album_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_genre_album_list")
    genre : str = item_identifier.get(ItemIdentifierKey.GENRE_NAME)
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET)
    msgproc.log(f"_handler_element_genre_album_list genre {genre} offset {offset}")
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
            _cache_element_value(ElementType.TAG, TagType.GENRES.getTagName(), current_album.getId())    
            once = True
        _cache_element_value(ElementType.GENRE_ALBUM_LIST, genre, current_album.getId())
        _cache_element_value(ElementType.GENRE_ALBUM_LIST, current_album.getGenre(), current_album.getId())
        entries.append(_album_to_entry(objid, current_album))
    if len(album_list) == __items_per_page:
        # create next button
        entries = _genre_flowing_add_albums_node(
            objid = objid,
            item_identifier = item_identifier,
            offset = offset + __items_per_page,
            entries = entries)
    return entries

def _handler_tag_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_artists(objid, entries)

def _handler_tag_artists_indexed(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_artist_initials(objid, entries)

def _handler_element_artist_initial(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_initial : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    entries = __load_artists_by_initial(objid, artist_initial, entries)
    return entries

def _handler_element_artist(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    entries = __load_albums_by_artist(objid, artist, entries)
    return entries

def _handler_element_genre_artist(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    genre : str = item_identifier.get(ItemIdentifierKey.GENRE_NAME)
    msgproc.log(f"_handler_element_genre_artist artist_id {artist_id} genre {genre}")
    entries = __load_albums_by_genre_artist(
        objid, 
        artist_id = artist_id, 
        genre = genre, 
        entries = entries)
    return entries

def _handler_element_album(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    avp_enc : str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, None)
    msgproc.log(f"_handler_element_album for album_id {album_id} avp_enc {avp_enc}")
    album_version_path : str = __thing_codec.decode(avp_enc) if avp_enc else None
    album_tracks : AlbumTracks = _get_album_tracks(album_id) if not album_version_path else None
    if album_tracks and album_tracks.getAlbumVersionCount() > 1:
        #msgproc.log(f"_handler_element_album we should now present the {album_tracks.getAlbumVersionCount()} versions")    
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

def _handler_element_track(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    #msgproc.log(f"_handler_element_track start")
    song_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_track should serve song_id {song_id}")
    song_response : Response[Song] = connector.getSong(song_id)
    if not song_response.isOk(): raise Exception(f"Cannot find song with id {song_id}")
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), song_id)
    id : str = _create_objid_simple(objid, __thing_codec.encode(json.dumps(identifier.getDictionary())))
    song_entry : dict = _song_data_to_entry(objid, id, song_response.getObj())
    entries.append(song_entry)
    return entries

__tag_action_dict : dict = {
    TagType.NEWEST.getTagName(): _handler_tag_newest_flowing,
    TagType.RANDOM.getTagName(): _handler_tag_random_flowing,
    TagType.GENRES.getTagName(): _handler_tag_genres_flowing,
    TagType.ARTISTS_ALL.getTagName(): _handler_tag_artists,
    TagType.ARTISTS_INDEXED.getTagName(): _handler_tag_artists_indexed
}

__elem_action_dict : dict = {
    ElementType.GENRE.getName(): _handler_element_genre_flowing,
    ElementType.ARTIST_INITIAL.getName(): _handler_element_artist_initial,
    ElementType.ARTIST.getName(): _handler_element_artist,
    ElementType.GENRE_ARTIST.getName(): _handler_element_genre_artist,
    ElementType.ALBUM.getName(): _handler_element_album,
    ElementType.GENRE_ARTIST_LIST.getName(): _handler_element_genre_flowing_artists,
    ElementType.GENRE_ALBUM_LIST.getName(): _handler_element_genre_album_list,
    ElementType.TRACK.getName(): _handler_element_track
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
    curr_path : str
    for curr_path in path_list:
        if not _g_myprefix == curr_path:
            #msgproc.log(f"browse: path: [{curr_path}] not found, should be recreated")
            msgproc.log(f"browse: path: [{curr_path}] decodes to {__thing_codec.decode(curr_path)}")
    last_path_item : str = path_list[len(path_list) - 1] if path_list and len(path_list) > 0 else None
    msgproc.log(f"browse: path_list: --{path_list}-- last: --{last_path_item}--")
    entries = []
    if len(path_list) == 1 and _g_myprefix == last_path_item:
        # show tags
        entries = _show_tags(objid, entries)
    else:
        # decode
        decoded_path : str = __thing_codec.decode(last_path_item)
        item_dict : dict[str, any] = json.loads(decoded_path)
        item_identifier : ItemIdentifier = ItemIdentifier.from_dict(item_dict)
        thing_name : str = item_identifier.get(ItemIdentifierKey.THING_NAME)
        thing_value : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
        msgproc.log(f"browse: item_identifier name: --{thing_name}-- value: --{thing_value}--")
        if ElementType.TAG.getName() == thing_name:
            msgproc.log(f"browse: should serve tag: --{thing_value}--")
            tag_handler = __tag_action_dict[thing_value] if thing_value in __tag_action_dict else None
            if tag_handler:
                msgproc.log(f"browse: found tag handler for: --{thing_value}--")
                entries = tag_handler(objid, item_identifier, entries)
                return _returnentries(entries)
            else:
                msgproc.log(f"browse: tag handler for: --{thing_value}-- not found")
        else: # it's an element
            msgproc.log(f"browse: should serve element: --{thing_name}-- [{thing_value}]")
            elem_handler = __elem_action_dict[thing_name] if thing_name in __elem_action_dict else None
            if elem_handler:
                msgproc.log(f"browse: found elem handler for: --{thing_name}--")
                entries = elem_handler(objid, item_identifier, entries)
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
            _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
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

