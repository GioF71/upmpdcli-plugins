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
    TRACK = 4, "track"
    NEWEST_PAGED_PAGE = 5, "newest_paged_page"
    NEWEST_SINGLE_PAGE = 6, "newest_single_page"
    GENRE_PAGE = 7, "genre_page"

    def __init__(self, 
            num : int, 
            element_name : str):
        self.num : int = num
        self.element_name : str = element_name

    def getName(self):
        return self.element_name

class TagType(Enum):
    
    NEWEST_PAGED = 0, "newest_paged", ElementType.NEWEST_PAGED_PAGE.getName(), "Newest Albums (Paged)", "newest"
    NEWEST_SINGLE = 1, "newest_single", ElementType.NEWEST_SINGLE_PAGE.getName(), "Newest Albums (Single Page)", "newest"
    RANDOM = 10, "random", ElementType.ALBUM.getName(), "Random Albums", "random"
    GENRES = 20, "genres", ElementType.GENRE.getName(), "Genres", None
    ARTISTS = 30, "artists", ElementType.ARTIST.getName(), "Artists", None

    def __init__(self, 
            num : int, 
            tag_name : str, 
            tag_translation : str,
            tag_title : str, 
            query_type : str):
        self.num : int = num
        self.tag_name : str = tag_name
        self.tag_translation : str = tag_translation
        self.tag_title : str = tag_title
        self.query_type : str = query_type

    def getTagName(self) -> str:
        return self.tag_name

    def getTagTranslation(self) -> str:
        return self.tag_translation

    def getTagTitle(self) -> str:
        return self.tag_title

    def getQueryType(self) -> str:
        return self.query_type
    
class ItemDictKey(Enum):
    
    GENRE = 0, 'genre'
    PAGE = 1, 'page'
    
    def __init__(self, 
            num : int, 
            key_name : str):
        self.num : int = num
        self.key_name : str = key_name
    
    def getName(self) -> str:
        return self.key_name
    
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

__items_per_page : int = int(getOptionValue("subsonicitemsperpage", "36"))
__max_pages : int = int(getOptionValue("subsonicmaxpages", "36"))
__append_year_to_album : int = int(getOptionValue("subsonicappendyeartoalbum", "1"))
__append_codecs_to_album : int = int(getOptionValue("subsonicappendcodecstoalbum", "1"))
__whitelist_codecs : list[str] = str(getOptionValue("subsonicwhitelistcodecs", "alac,wav,flac,dsf")).split(",")
__allow_blacklisted_codec_in_song : int = int(getOptionValue("subsonicallowblacklistedcodecinsong", "1"))
__caches : dict[str, object] = {}

__genre_codec : Codec = Codec()
__newest_page_codec : Codec = Codec()
__genre_page_codec : Codec = Codec()
__genre_page_map : dict[str, object] = {}

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
    id : str = _create_objid_for(objid, ElementType.ALBUM, current_album.getId())
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
    arturi = connector.buildCoverArtUrl(current_album.getId())
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist,
        arturi = arturi)
    _set_album_id(current_album.getId(), entry)
    return entry

def _genre_to_entry(objid, current_genre : Genre) -> direntry:
    id : str = _create_objid_for(objid, ElementType.GENRE, __genre_codec.encode(current_genre.getName()))
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
    return entry

def _newest_page_to_entry(objid, p_0_based : int, low : int) -> direntry:
    name : str = "Page {}".format(p_0_based + 1)
    item_id : str = "{}-{}".format(TagType.NEWEST_PAGED.getTagName(), low)
    enc_id : str = __newest_page_codec.encode(item_id)
    id : str = _create_objid_for(objid, ElementType.NEWEST_PAGED_PAGE, enc_id)
    #msgproc.log(f"_newest_page_to_entry for name [{name}] item_id [{item_id}] enc_id [{enc_id}]")
    entry = direntry(id, 
        objid, 
        name)
    art_uri = None
    art_id : str = _get_cached_element(ElementType.NEWEST_PAGED_PAGE, item_id)
    if art_id:
        #msgproc.log(f"_newest_page_to_entry cache entry hit for {item_id}")
        art_uri = connector.buildCoverArtUrl(art_id)
        _set_album_art_uri(art_uri, entry)
    #else:
    #    msgproc.log(f"_newest_page_to_entry cache entry miss for {item_id}")
    return entry

def _genre_page_to_entry(objid, genre : str, p_0_based : int, low : int) -> direntry:
    name : str = "Page {}".format(p_0_based + 1)
    # need a unique key
    key_str: str = "{}-{}-{}".format(ElementType.GENRE_PAGE.getName(), low, genre)
    item_id_dict : dict[str, str] = {}
    item_id_dict[ItemDictKey.GENRE.getName()] = genre
    item_id_dict[ItemDictKey.PAGE.getName()] = p_0_based
    item_id : str = __genre_page_codec.encode(key_str)
    __genre_page_map[item_id] = item_id_dict
    
    id : str = _create_objid_for(objid, ElementType.GENRE_PAGE, item_id)
    entry = direntry(id, 
        objid, 
        name)
    art_uri = None
    art_id : str = _get_cached_element(ElementType.GENRE_PAGE, item_id)
    if art_id:
        art_uri = connector.buildCoverArtUrl(art_id)
        _set_album_art_uri(art_uri, entry)
    #else:
    #    msgproc.log(f"_newest_page_to_entry cache entry miss for {item_id}")
    return entry

def _artist_to_entry(
        objid, 
        artist_id : str,
        artist_name : str) -> direntry:
    id : str = _create_objid_for(objid, ElementType.ARTIST, artist_id)
    name : str = artist_name
    msgproc.log(f"_artist_to_entry for {name}")
    artist_art_uri = None
    artist_art : str = _get_cached_element(ElementType.ARTIST, artist_id)
    if artist_art:
        #msgproc.log(f"_artist_to_entry cache entry hit for {artist_id}")
        artist_art_uri = connector.buildCoverArtUrl(artist_art)
    #else:
    #    msgproc.log(f"_artist_to_entry cache entry miss for {artist_id}")
    entry = direntry(id, 
        objid, 
        name,
        arturi = artist_art_uri)
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

def _is_thing(lastvalue : str, thing_name : str) -> bool:
    if "-" in lastvalue:
        lpath = lastvalue.split("-")
        if lpath and len(lpath) > 1:
            last = lpath[0]
            return last == thing_name
    return False

def _get_thing(lastvalue : str, thing_name : str) -> str:
    lpath = lastvalue.split("-")
    if lpath and len(lpath) > 1:
        last = lpath[0]
        if last == thing_name:
            return "-".join(lpath[1:])
    return None

def _get_newest_page_number(newest_page_id : str) -> int:
    splitted = newest_page_id.split("-")
    if splitted and len(splitted) == 2:
        first = splitted[0]
        if first == TagType.NEWEST_PAGED.getTagName():
            return int(splitted[1])
    raise Exception(f"Invalid newest page id [{newest_page_id}]")
   
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
        elif not (current_base_path == new_base_path):
            track_num = 1
        msgproc.log(f"_load_album_tracks current_base_path {current_base_path} new_base_path {new_base_path} track_num {track_num}")
        current_base_path = new_base_path
        entry = _song_to_entry(
            objid = objid, 
            song = current_song, 
            albumArtURI = albumArtURI, 
            multi_codec_album = multi_codec_album,
            track_num = str(track_num))
        entries.append(entry)

def _load_albums_by_type(
        objid, 
        entries : list, 
        tagType : TagType,
        offset : int = 0,
        size : int = __items_per_page):
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

def __load_albums_by_artist(objid, artist_id : str, entries : list) -> list:
    artist_tag_cached : bool = False
    artist_response : Response[Artist] = connector.getArtist(artist_id)
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
    if genres_response.isOk():
        genre_list = genres_response.getObj().getGenres()
        genre_list.sort(key = lambda x: x.getName())
        current_genre : Genre
        for current_genre in genre_list:
            #msgproc.log(f"genre {current_genre.getName()} albumCount {current_genre.getAlbumCount()}")
            if current_genre.getAlbumCount() > 0:
                entry : dict = _genre_to_entry(objid, current_genre)
                entries.append(entry)
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
            album_id : str = _get_thing(lastcrit, ElementType.ALBUM.getName())
            _load_album_tracks(objid, album_id, entries)
            return _returnentries(entries)

    if (TagType.NEWEST_PAGED.getTagName() == lastcrit 
        or TagType.NEWEST_SINGLE.getTagName() == lastcrit 
        or TagType.RANDOM.getTagName() == lastcrit):
        msgproc.log(f"match 1 with lastcrit: {lastcrit}")
        # reply with the list
        if lastvalue:
            #return selected album
            if _is_thing(lastvalue, ElementType.NEWEST_PAGED_PAGE.getName()):
                msgproc.log(f"match 1d (NEWEST_PAGED_PAGE) with lastvalue: {lastvalue}")
                newest_page_id : str = __newest_page_codec.decode(_get_thing(lastvalue, ElementType.NEWEST_PAGED_PAGE.getName()))
                newest_page_offset : int = _get_newest_page_number(newest_page_id) - 1
                msgproc.log(f"match 1d (NEWEST_PAGED_PAGE) selected id: {newest_page_id} offset {newest_page_offset}")
                _load_albums_by_type(
                    objid, 
                    entries, 
                    TagType.NEWEST_PAGED, 
                    offset = newest_page_offset)
                #cache
                if len(entries) > 0:
                    # grab first
                    first : dict = entries[0]
                    art_id = _get_album_id(first)
                    _cache_element_value(ElementType.NEWEST_PAGED_PAGE, newest_page_id, art_id)
                    if newest_page_offset == 0:
                        _cache_element_value(ElementType.TAG, TagType.NEWEST_PAGED.getTagName(), art_id)
                return _returnentries(entries)
        else:
            if TagType.NEWEST_PAGED.getTagName() == lastcrit:
                low : int = 1
                for p in range(0, __max_pages):
                    upper = low + __items_per_page
                    #msgproc.log(f"will add {low} to {upper - 1}")
                    entries.append(_newest_page_to_entry(objid, p, low))
                    low = upper
                return _returnentries(entries)
            else:
                _load_albums_by_type(objid, entries, _getTagTypeByName(lastcrit))
                return _returnentries(entries)
    
    if TagType.GENRES.getTagName() == lastcrit:
        msgproc.log(f"match 2 with lastcrit: {lastcrit}")
        # reply with the list
        if lastvalue:
            if _is_thing(lastvalue, ElementType.GENRE.getName()):
                genre : str = __genre_codec.decode(_get_thing(lastvalue, ElementType.GENRE.getName()))
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
            artists_response : Response[Artists] = connector.getArtists()
            if artists_response.isOk():
                artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
                current_artists_initial : ArtistsInitial
                for current_artists_initial in artists_initial:
                    msgproc.log(f"current artists initial = {current_artists_initial.getName()}")
                    current_artist : ArtistListItem
                    for current_artist in current_artists_initial.getArtistListItems():
                        msgproc.log(f"current artist name = {current_artist.getName()}")
                        entries.append(_artist_to_entry(
                            objid, 
                            current_artist.getId(), 
                            current_artist.getName()))
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
    
        if _is_thing(lastcrit, ElementType.ARTIST.getName()):
            msgproc.log(f"match 3a (artist) with lastcrit --{lastcrit}--")
            # load albums from the selected artist
            artist_id : str = _get_thing(lastcrit, ElementType.ARTIST.getName())
            entries = __load_albums_by_artist(objid, artist_id, entries)
            return _returnentries(entries)
        
        if _is_thing(lastcrit, ElementType.GENRE_PAGE.getName()):
            msgproc.log(f"match 3a (genre_page) with lastcrit --{lastcrit}--")
            #return genre list page by genre
            genre_page_id : str = _get_thing(lastcrit, ElementType.GENRE_PAGE.getName())
            msgproc.log(f"match 3a (genre_page) genre_page_id {genre_page_id}")
            item_dict : dict = __genre_page_map[genre_page_id]
            select_genre : str = item_dict[ItemDictKey.GENRE.getName()]
            page : int = item_dict[ItemDictKey.PAGE.getName()]
            msgproc.log(f"match 3a (genre_page) genre_page_id {genre_page_id} genre {select_genre} page {page}")
            offset : int = page * __items_per_page
            albumListResponse : Response[AlbumList] = connector.getAlbumList(
                ltype = ListType.BY_GENRE, 
                genre = select_genre,
                offset = offset,
                size = __items_per_page)
            once : bool = False
            if albumListResponse.isOk():
                albumList : list[Album] = albumListResponse.getObj().getAlbums()
                msgproc.log(f"got {len(albumList)} albums for genre {select_genre}")
                current_album : Album
                for current_album in albumList:
                    if not once:
                        _cache_element_value(ElementType.TAG, TagType.GENRES.getTagName(), current_album.getId())    
                        _cache_element_value(ElementType.GENRE_PAGE, genre_page_id, current_album.getId())
                        once = True
                    _cache_element_value(ElementType.GENRE, select_genre, current_album.getId())
                    _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
                    entries.append(_album_to_entry(objid, current_album))
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

