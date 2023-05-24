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

__subsonic_plugin_release : str = "0.1.12"

import cmdtalkplugin
import json
from html import escape as htmlescape, unescape as htmlunescape
from upmplgutils import *
from upmplgutils import setidprefix, direntry, getOptionValue

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
from subsonic_connector.playlists import Playlists
from subsonic_connector.playlist import Playlist
from subsonic_connector.playlist_entry import PlaylistEntry
from subsonic_connector.internet_radio_stations import InternetRadioStations
from subsonic_connector.internet_radio_station import InternetRadioStation
from subsonic_connector.random_songs import RandomSongs
from subsonic_connector.top_songs import TopSongs
from subsonic_connector.similar_artist import SimilarArtist
from subsonic_connector.artist_info import ArtistInfo

from config import UpmpdcliSubsonicConfig
from config import subsonic_max_return_size

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

from art_retriever import tag_art_retriever
from art_retriever import artist_art_retriever
from art_retriever import artist_initial_art_retriever
from art_retriever import get_artist_cover

from subsonic_util import get_random_art_by_genre

import secrets
import mimetypes
import time

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

__subsonic_max_return_size : int = subsonic_max_return_size

__items_per_page : int = min(__subsonic_max_return_size, int(getOptionValue("subsonicitemsperpage", "36")))
__append_year_to_album : int = int(getOptionValue("subsonicappendyeartoalbum", "1"))
__append_codecs_to_album : int = int(getOptionValue("subsonicappendcodecstoalbum", "1"))
__whitelist_codecs : list[str] = str(getOptionValue("subsonicwhitelistcodecs", "alac,wav,flac,dsf")).split(",")
__allow_blacklisted_codec_in_song : int = int(getOptionValue("subsonicallowblacklistedcodecinsong", "1"))

__disable_sparse_album : int = int(getOptionValue("subsonicdisablesparsealbumview", "0"))

__tag_enabled_prefix : str = "subsonictagenabled"
__autostart : int = int(getOptionValue("subsonicautostart", "0"))

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

def _get_cache_size(element_type : ElementType) -> int:
    cache : dict = _get_element_cache(element_type)
    return len(cache)

connector : Connector = Connector(UpmpdcliSubsonicConfig())

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
                _cache_element_value(ElementType.ARTIST, artist_id, album.getId(), force_update = False)
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

def __initial_caching_genre(genre : str):
    msgproc.log(f"Processing genre [{genre}]")
    if _is_element_cached(ElementType.GENRE, genre):
        #msgproc.log(f"Genre [{genre}] already has art, skipping")
        return
    msgproc.log(f"Genre {genre} has not art yet, looking for an album")
    # pick an album for the genre
    album_list_res : Response[AlbumList] = connector.getAlbumList(
        ltype = ListType.BY_GENRE, 
        size = __subsonic_max_return_size, 
        genre = genre)
    if album_list_res.isOk() and album_list_res.getObj() and len(album_list_res.getObj().getAlbums()) > 0:
        album_list : AlbumList = album_list_res.getObj()
        album : Album = secrets.choice(album_list.getAlbums())
        if album:
            msgproc.log(f"Caching genre [{genre}] with album_id [{album.getId()}]")
            _cache_element_value(ElementType.GENRE, genre, album.getId())

def __initial_caching_genres():
    genres_response : Response[Genres] = connector.getGenres()
    if not genres_response.isOk(): return
    genre_list = genres_response.getObj().getGenres()
    for current_genre in genre_list:
        genre : str = current_genre.getName()
        if genre: __initial_caching_genre(genre)

def __initial_caching():
    __initial_caching_by_newest()
    __initial_caching_by_artist_initials()
    __initial_caching_genres()

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
    init_success : bool = False
    try:
        __initial_caching()
        init_success = True
    except Exception as e:
        msgproc.log(f"Subsonic Initialization failed [{e}]")
    msgproc.log(f"Subsonic Initialization complete: {init_success}")
            
    _g_init = True
    return True

@dispatcher.record('trackuri')
def trackuri(a):
    # We generate URIs which directly point to the stream, so this method should never be called.
    raise Exception("trackuri: should not be called for subsonic!")

def _returnentries(entries):
    """Helper function: build plugin browse or search return value from items list"""
    return {"entries" : json.dumps(entries), "nocache" : "0"}

def __create_id_from_identifier(identifier : ItemIdentifier) -> str:
    return __thing_codec.encode(json.dumps(identifier.getDictionary()))

def _create_objid_simple(objid, id : str) -> str:
    return objid + "/" + _escape_objid(id)

def _escape_objid(value : str) -> str:
    return htmlescape(value, quote = True)

def _set_album_title(album_title : str, target : dict):
    target['tt'] = album_title

def _set_album_id(album_id : str, target : dict):
    target['album_id'] = album_id

def _set_album_art_from_uri(album_art_uri : str, target : dict):
    target['upnp:albumArtURI'] = album_art_uri

def _set_album_art_from_album_id(album_id : str, target : dict):
    if album_id:
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
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    #msgproc.log(f"_album_version_to_entry caching artist_id {current_album.getArtistId()} to genre {current_album.getGenre()} [{cached}]")
    title : str = f"Version #{version_number}"
    if __append_year_to_album == 1 and current_album.getYear() is not None:
        title = "{} [{}]".format(title, current_album.getYear())
    codecs_str : str = ",".join(codec_set)
    title = "{} [{}]".format(title, codecs_str)
    last_path : str = get_last_path_element(album_version_path)
    title = "{} [{}]".format(title, last_path)
    artist = current_album.getArtist()
    _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId(), force_update = False)
    _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId(), force_update = False)
    msgproc.log(f"_album_version_to_entry searching initial for artist_id {current_album.getArtistId()}")
    artist_initial : str = (__artist_initial_by_id[current_album.getArtistId()] 
        if current_album.getArtistId() in __artist_initial_by_id 
        else None)
    if artist_initial:
        _cache_element_value(ElementType.ARTIST_INITIAL, artist_initial, current_album.getId())
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist)
    _set_album_art_from_album_id(current_album.getId(), entry)
    return entry

def _sparse_album_to_entry(objid, current_album : Album) -> direntry:
    title : str = current_album.getTitle()
    artist : str = current_album.getArtist()
    identifier : ItemIdentifier = ItemIdentifier(ElementType.SPARSE_ALBUM.getName(), current_album.getId())
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist)
    _set_album_art_from_album_id(current_album.getId(), entry)
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
    _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId(), force_update = False)
    _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId(), force_update = False)
    artist_initial : str = (__artist_initial_by_id[current_album.getArtistId()] 
        if current_album.getArtistId() in __artist_initial_by_id 
        else None)
    if artist_initial:
        _cache_element_value(ElementType.ARTIST_INITIAL, artist_initial, current_album.getId())
    #msgproc.log(f"_album_to_entry creating identifier for album_id {current_album.getId()}")
    identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), current_album.getId())
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist)
    _set_album_art_from_album_id(current_album.getId(), entry)
    _set_album_id(current_album.getId(), entry)
    return entry

def _genre_to_entry(objid, current_genre : Genre) -> direntry:
    name : str = current_genre.getName()
    #msgproc.log(f"_genre_to_entry for {name}")
    genre_art : str = _get_cached_element(ElementType.GENRE, current_genre.getName())
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE.getName(), 
        current_genre.getName())
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        name)
    _set_album_art_from_album_id(genre_art, entry)
    #msgproc.log(f"_genre_to_entry storing with thing_key {thing_key} id {id}")
    return entry

def _get_artist_art(artist_id : str) -> str:
    art_cache_size : int = _get_cache_size(ElementType.ARTIST)
    if art_cache_size == 0: __initial_caching()
    artist_art : str = _get_cached_element(ElementType.ARTIST, artist_id)
    if not artist_art:
        # can be new
        if art_cache_size == 0: __initial_caching()
        msgproc.log(f"_get_artist_art searching artist_art for artist_id {artist_id}")
        identifier : ItemIdentifier = ItemIdentifier(ElementType.ARTIST, artist_id)
        artist_art = artist_art_retriever(connector, identifier)
        # store if found
        if artist_art: _cache_element_value(ElementType.ARTIST, artist_id, artist_art, force_update = False)
    return artist_art

def _genre_artist_to_entry(
        objid, 
        artist_id : str,
        genre : str,
        artist_name : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ARTIST.getName(), 
        artist_id)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    #msgproc.log(f"_genre_artist_to_entry for {artist_name}")
    artist_art : str = _get_cached_element(ElementType.GENRE_ARTIST, artist_id)
    if not artist_art:
        # try art for artist in general
        artist_art : str = _get_artist_art(artist_id)
    entry = direntry(id, 
        objid, 
        artist_name)
    _set_album_art_from_album_id(artist_art, entry)
    return entry

def _artist_to_entry(
        objid, 
        artist_id : str,
        artist_name : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(), 
        artist_id)
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        artist_name)
    art_album_id : str = _get_artist_art(artist_id)
    _set_album_art_from_album_id(art_album_id, entry)
    return entry

def _artist_initial_to_entry(
        objid, 
        artist_initial : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_INITIAL.getName(), 
        artist_initial)
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    art_album_id : str = _get_cached_element(ElementType.ARTIST_INITIAL, artist_initial)
    if not art_album_id:
        # can be new
        identifier : ItemIdentifier = ItemIdentifier(ElementType.ARTIST_INITIAL, artist_initial)
        art_album_id = artist_initial_art_retriever(connector, identifier)
        # store if found
        if art_album_id: _cache_element_value(ElementType.ARTIST_INITIAL, artist_initial, artist_art)
    entry = direntry(id, 
        objid, 
        artist_initial)
    _set_album_art_from_album_id(art_album_id, entry)
    return entry

def _playlist_to_entry(
        objid, 
        playlist : Playlist) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.PLAYLIST.getName(), 
        playlist.getId())
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    art_uri = connector.buildCoverArtUrl(playlist.getCoverArt()) if playlist.getCoverArt() else None
    entry = direntry(id, 
        objid, 
        playlist.getName())
    if art_uri:
        _set_album_art_from_uri(art_uri, entry)
    return entry

def _station_to_entry(
        objid, 
        station : InternetRadioStation) -> direntry:
    stream_url : str = station.getStreamUrl()
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.INTERNET_RADIO.getName(), 
        station.getId())
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    entry : dict = {}
    entry['id'] = id
    entry['pid'] = station.getId()
    entry['upnp:class'] = 'object.item.audioItem.audioBroadcast'
    entry['uri'] = stream_url
    _set_album_title(station.getName(), entry)
    entry['tp']= 'it'
    entry['upnp:artist'] = "Internet Radio"
    mime_type : str = mimetypes.guess_type(stream_url)[0]
    msgproc.log(f"_station_to_entry guessed mimetype [{mime_type}] for stream_url [{stream_url}]")
    if not mime_type: mime_type = "audio/mpeg"
    entry['res:mime'] = mime_type
    return entry

def _song_data_to_entry(objid, entry_id : str, song : Song) -> dict:
    entry : dict = {}
    entry['id'] = entry_id
    entry['pid'] = song.getId()
    entry['upnp:class'] = 'object.item.audioItem.musicTrack'
    entry['uri'] = connector.buildSongUrlBySong(song)
    title : str = song.getTitle()
    _set_album_title(title, entry)
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
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = song.getId()
    entry['upnp:class'] = 'object.item.audioItem.musicTrack'
    song_uri : str = connector.buildSongUrlBySong(song)
    entry['uri'] = song_uri
    title : str = song.getTitle()
    if MultiCodecAlbum.YES == multi_codec_album and __allow_blacklisted_codec_in_song == 1 and (not song.getSuffix() in __whitelist_codecs):
        title = "{} [{}]".format(title, song.getSuffix())
    _set_album_title(title, entry)
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
    elif TagType.RECENTLY_PLAYED.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(ltype = ListType.RECENT, size = size, offset = offset)
    elif TagType.MOST_PLAYED.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(ltype = ListType.FREQUENT, size = size, offset = offset)
    elif TagType.HIGHEST_RATED.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(ltype = ListType.HIGHEST, size = size, offset = offset)
    elif TagType.FAVOURITES.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(ltype = ListType.STARRED, size = size, offset = offset)
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

def _load_albums_by_type(
        objid, 
        entries : list, 
        tagType : TagType,
        offset : int = 0,
        size : int = __items_per_page) -> list:
    albumList : list[Album] = _get_albums(tagType.getQueryType(), size = size, offset = str(offset))
    sz : int = len(albumList)
    current_album : Album
    tag_cached : bool = False
    for current_album in albumList:
        if tagType and (not tag_cached) and (offset == 0):
            _cache_element_value(ElementType.TAG, tagType.getTagName(), current_album.getId())
            tag_cached = True
        if __disable_sparse_album == 1:
            entries.append(_album_to_entry(objid, current_album))
        else:            
            entries.append(_sparse_album_to_entry(objid, current_album))
        # cache genre art
        current_genre : str = current_album.getGenre()
        _cache_element_value(ElementType.GENRE, current_genre, current_album.getId(), force_update = False)
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
        _cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId(), force_update = False)
        _cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId(), force_update = False)
        entries.append(_album_to_entry(objid, current_album))
    return entries

def __load_artists_by_initial(objid, artist_initial : str, entries : list) -> list:
    # caching disabled, too slow
    #art_by_artist_id : dict[str, str] = __create_art_by_artist_id_cache()
    art_cache_size : int = _get_cache_size(ElementType.ARTIST_INITIAL)
    msgproc.log(f"__load_artists_by_initial art_cache_size {art_cache_size}")
    if art_cache_size == 0: __initial_caching()
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
                msgproc.log(f"__load_artists_by_initial loading art for artist_id {current_artist.getId()} artist_name {current_artist.getName()}")
                entry : dict = _artist_to_entry(
                    objid, 
                    current_artist.getId(), 
                    current_artist.getName())
                # if artist has art, set that art for artists by initial tile
                artist_art : str = _get_artist_art(current_artist.getId())
                if artist_art:
                    _cache_element_value(ElementType.TAG, TagType.ARTISTS_INDEXED.getTagName(), artist_art)
                entries.append(entry)
    return entries

def _create_list_of_genres(objid, entries : list) -> list:
    art_cache_size : int = _get_cache_size(ElementType.ARTIST_INITIAL)
    msgproc.log(f"_create_list_of_genres art_cache_size {art_cache_size}")
    if art_cache_size == 0: __initial_caching()
    genres_response : Response[Genres] = connector.getGenres()
    if not genres_response.isOk(): return entries
    genre_list = genres_response.getObj().getGenres()
    genre_list.sort(key = lambda x: x.getName())
    current_genre : Genre
    for current_genre in genre_list:
        if current_genre.getAlbumCount() > 0:
            entry : dict = _genre_to_entry(objid, current_genre)
            entries.append(entry)
    return entries

def _get_list_of_artists(objid, entries : list) -> list:
    art_cache_size : int = _get_cache_size(ElementType.ARTIST)
    if art_cache_size == 0: __initial_caching_by_artist_initials()
    artists_response : Response[Artists] = connector.getArtists()
    if not artists_response.isOk(): return entries
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
        current_artist : ArtistListItem
        for current_artist in current_artists_initial.getArtistListItems():
            entries.append(_artist_to_entry(
                objid = objid, 
                artist_id = current_artist.getId(), 
                artist_name = current_artist.getName()))
            __artist_initial_by_id[current_artist.getId()] = current_artists_initial.getName()
    return entries

def _create_list_of_playlist(objid, entries : list) -> list:
    response : Response[Playlists] = connector.getPlaylists()
    if not response.isOk(): return entries
    playlists : Playlists = response.getObj()
    playlist : Playlist
    for playlist in playlists.getPlaylists():
        entry : dict = _playlist_to_entry(
            objid, 
            playlist)
        entries.append(entry)
    return entries

def _create_list_of_internet_radio(objid, entries : list) -> list:
    response : Response[InternetRadioStations] = connector.getInternetRadioStations()
    if not response.isOk(): return entries
    stations : InternetRadioStations = response.getObj()
    station : InternetRadioStation
    for station in stations.getStations():
        entry : dict = _station_to_entry(
            objid, 
            station)
        entries.append(entry)
    return entries

def _playlist_entry_to_entry(
        objid, 
        playlist_entry : PlaylistEntry) -> dict:
    entry = {}
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), playlist_entry.getId())
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = playlist_entry.getId()
    entry['upnp:class'] = 'object.item.audioItem.musicTrack'
    song_uri : str = connector.buildSongUrl(playlist_entry.getId())
    entry['uri'] = song_uri
    title : str = playlist_entry.getTitle()
    entry['tt'] = title
    entry['tp']= 'it'
    _set_track_number(playlist_entry.getTrack(), entry)
    entry['upnp:artist'] = playlist_entry.getArtist()
    entry['upnp:album'] = playlist_entry.getAlbum()
    entry['res:mime'] = playlist_entry.getContentType()
    albumArtURI : str = connector.buildCoverArtUrl(playlist_entry.getId())
    if albumArtURI: _set_album_art_from_uri(albumArtURI, entry)
    entry['duration'] = str(playlist_entry.getDuration())
    return entry

def _create_list_of_playlist_entries(objid, playlist_id : str, entries : list) -> list:
    response : Response[Playlist] = connector.getPlaylist(playlist_id)
    if not response.isOk(): return entries
    entry_list : list[PlaylistEntry] = response.getObj().getEntries()
    playlist_entry : PlaylistEntry
    for playlist_entry in entry_list:
        entry : dict = _playlist_entry_to_entry(
            objid,
            playlist_entry)
        entries.append(entry)
    return entries

def _create_list_of_artist_initials(objid, entries : list) -> list:
    art_cache_size : int = _get_cache_size(ElementType.ARTIST_INITIAL)
    msgproc.log(f"_create_list_of_artist_initials art_cache_size {art_cache_size}")
    if art_cache_size == 0: __initial_caching()
    artists_response : Response[Artists] = connector.getArtists()
    if not artists_response.isOk(): return entries
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
        entry : dict = _artist_initial_to_entry(
            objid = objid, 
            artist_initial = current_artists_initial.getName())
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
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
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
            id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
            entry : dict = direntry(
                id = id, 
                pid = objid, 
                title = _getTagTypeByName(tag.getTagName()).getTagTitle())
            art_id : str = None
            if tagname in tag_art_retriever:
                art_id = tag_art_retriever[tagname](connector)
            if art_id:
                _set_album_art_from_album_id(art_id, entry)
            entries.append(entry)
    return entries

def __handler_tag_type(objid, item_identifier : ItemIdentifier, tag_type : TagType, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    entries = _load_albums_by_type(
        objid = objid, 
        entries = entries, 
        tagType = tag_type, 
        offset = offset)
    # offset is: current offset + the entries length
    if (len(entries) == __items_per_page):
        next_page : dict = _create_tag_next_entry(
            objid = objid, 
            tag = tag_type, 
            offset = offset + len(entries))
        entries.append(next_page)
    return entries

def _handler_tag_newest(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_tag_type(objid, item_identifier, TagType.NEWEST, entries)

def _handler_tag_most_played(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_tag_type(objid, item_identifier, TagType.MOST_PLAYED, entries)

def _handler_tag_favourites(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_tag_type(objid, item_identifier, TagType.FAVOURITES, entries)

def _handler_tag_highest_rated(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_tag_type(objid, item_identifier, TagType.HIGHEST_RATED, entries)

def _handler_tag_recently_played(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_tag_type(objid, item_identifier, TagType.RECENTLY_PLAYED, entries)

def _handler_tag_random(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_tag_type(objid, item_identifier, TagType.RANDOM, entries)

def _handler_tag_random_songs(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _get_random_songs(objid, item_identifier, entries)

def _handler_element_next_random_songs(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _get_random_songs(objid, item_identifier, entries)

def _handler_element_random_song_the_song(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_random_song start")
    song_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_random_song start song_id {song_id}")
    song : Song = connector.getSong(song_id).getObj()
    if song:
        entries.append(_song_to_entry(objid, song))
    return entries

def _handler_element_artist_top_songs(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_artist_top_songs start")
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_artist_top_songs artist_id {artist_id}")
    res : Response[Artist] = connector.getArtist(artist_id)
    if not res.isOk(): raise Exception(f"Cannot find artist by artist_id {artist_id}")
    artist : Artist = res.getObj()
    top_song_res : Response[TopSongs] = connector.getTopSongs(artist.getName())
    if not top_song_res.isOk(): raise Exception(f"Cannot get top songs for artist {artist.getName()}")
    song : Song
    for song in top_song_res.getObj().getSongs():
        song_entry : dict[str, any] = _song_to_entry(objid, song)
        entries.append(song_entry)
    return entries

def _random_song_to_entry(objid, song : Song) -> direntry:
    name : str = f"{song.getTitle()} - {song.getAlbum()}"
    art_id = song.getAlbumId()
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.RANDOM_SONG.getName(), 
        song.getId())
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        name)
    _set_album_art_from_album_id(art_id, entry)
    return entry

def _handler_element_random_song(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_random_song start")
    song_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_random_song start song_id {song_id}")
    song : Song = connector.getSong(song_id).getObj()
    song_identifier : ItemIdentifier = ItemIdentifier(ElementType.RANDOM_SONG_THE_SONG.getName(), song_id)
    song_entry_id : str = _create_objid_simple(objid, __create_id_from_identifier(song_identifier))
    song_entry = direntry(song_entry_id, 
        objid, 
        "Song")
    _set_album_art_from_album_id(song.getAlbumId(), song_entry)
    entries.append(song_entry)
    album : Album = connector.getAlbum(song.getAlbumId()).getObj()
    entries.append(_album_to_entry(objid, album))
    artist_id : str = song.getArtistId() if song.getArtistId() else album.getArtistId()
    if not artist_id: msgproc.log(f"_handler_element_random_song artist_id not found for song_id {song.getId()} album_id {song.getAlbumId()} artist {song.getArtist()}")
    if artist_id:
        msgproc.log(f"_handler_element_random_song searching artist for song_id {song.getId()} artist {song.getArtist()} artist_id {artist_id}")
        artist_response : Response[Artist] = connector.getArtist(artist_id)
        artist : Artist = artist_response.getObj() if artist_response.isOk() else None 
        if not artist: msgproc.log(f"_handler_element_random_song could not find artist for song_id {song.getId()} artist {song.getArtist()} artist_id {artist_id}")
        if artist: entries.append(_artist_to_entry(objid, artist.getId(), artist.getName()))
    return entries

def _get_random_songs(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    response : Response[RandomSongs] = connector.getRandomSongs(size = __items_per_page)
    if not response.isOk(): raise Exception(f"Cannot get random songs")
    song_list : list[Song] = response.getObj().getSongs()
    song : Song
    for song in song_list:
        entries.append(_random_song_to_entry(
            objid = objid, 
            song = song))
    # no offset, so we always add next
    next_identifier : ItemIdentifier = ItemIdentifier(ElementType.NEXT_RANDOM_SONGS.getName(), "some_random_song")
    next_id : str = _create_objid_simple(objid, __create_id_from_identifier(next_identifier))
    next_entry : dict = direntry(
        id = next_id, 
        pid = objid, 
        title = "Next")
    entries.append(next_entry)
    return entries

def _handler_tag_genres(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_genres(objid, entries)

def _genre_add_artists_node(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    genre : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_genre_add_artists_node genre {genre}")
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ARTIST_LIST.getName(), 
        genre)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    name : str = "Artists" # TODO parametrize maybe?
    artists_entry = direntry(id, 
        objid, 
        name)
    art_id : str = get_random_art_by_genre(connector, genre)
    if art_id:
        _set_album_art_from_album_id(art_id, artists_entry)
    #else:
    #    msgproc.log(f"_genre_add_artists_node art not found for {ElementType.GENRE_ARTIST_LIST.getName()} genre {genre}")
    entries.append(artists_entry)
    return entries

def _genre_add_albums_node(
        objid, 
        item_identifier : ItemIdentifier, 
        offset : int,
        entries : list) -> list:
    genre : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_genre_add_albums_node genre {genre}")
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ALBUM_LIST.getName(), 
        genre)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    identifier.set(ItemIdentifierKey.OFFSET, offset)
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    name : str = "Albums" if offset == 0 else "Next" # TODO parametrize maybe?
    artists_entry = direntry(id, 
        objid, 
        name)
    if offset == 0:
        art_id : str = get_random_art_by_genre(connector, genre)
        if art_id:
            _set_album_art_from_album_id(art_id, artists_entry)
        #else:
        #    msgproc.log(f"_genre_add_albums_node art not found for {ElementType.GENRE_ARTIST_LIST.getName()} genre {genre}")
    entries.append(artists_entry)
    return entries

def _handler_element_genre(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    # add nodes for albums by genre
    msgproc.log(f"_handler_element_genre")
    entries = _genre_add_artists_node(objid, item_identifier, entries)
    entries = _genre_add_albums_node(
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

def _handler_element_genre_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    genre : str = item_identifier.get(ItemIdentifierKey.GENRE_NAME)
    # get all albums by genre and collect a set of artists
    artist_id_set : set[str] = _load_all_artists_by_genre(genre)
    # present the list of artists
    artists_response : Response[Artists] = connector.getArtists()
    if not artists_response.isOk(): return entries
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
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
        entries = _genre_add_albums_node(
            objid = objid,
            item_identifier = item_identifier,
            offset = offset + __items_per_page,
            entries = entries)
    return entries

def _handler_tag_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _get_list_of_artists(objid, entries)

def _handler_tag_artists_indexed(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_artist_initials(objid, entries)

def _handler_tag_playlists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_playlist(objid, entries)

def _handler_tag_internet_radios(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return _create_list_of_internet_radio(objid, entries)

def _handler_element_playlist(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    playlist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    return _create_list_of_playlist_entries(objid, playlist_id, entries)

def _handler_element_artist_initial(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_initial : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    entries = __load_artists_by_initial(objid, artist_initial, entries)
    return entries

def _handler_element_artist_albums(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    entries = __load_albums_by_artist(objid, artist_id, entries)
    msgproc.log(f"Found {len(entries)} albums for artist_id {artist_id}")
    return entries

def _handler_element_artist(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist_response : Response[Artist] = connector.getArtist(artist_id)
    if not artist_response.isOk(): raise Exception(f"Cannot retrieve artist by id {artist_id}")
    artist : Artist = artist_response.getObj()
    #entries = __load_albums_by_artist(objid, artist_id, entries)
    #msgproc.log(f"Found {len(entries)} albums for artist_id {artist_id}")
    # TODO create "Albums entry"
    artist_album_identifier : ItemIdentifier = ItemIdentifier(ElementType.ARTIST_ALBUMS.getName(), artist_id)
    artist_album_id : str = _create_objid_simple(objid, __create_id_from_identifier(artist_album_identifier))
    albums_entry : dict = direntry(
        artist_album_id, 
        objid, 
        title = "Albums")
    album_art : str = get_artist_cover(connector, artist_id)
    if album_art: _set_album_art_from_album_id(album_art, albums_entry)
    entries.append(albums_entry)
    top_songs_entry : dict[str, any] = _artist_to_top_songs_entry(objid, artist_id, artist.getName())
    if top_songs_entry: entries.append(top_songs_entry)
    similar_artists_entry : dict[str, any] = _similar_artists_for_artist(objid, artist_id)
    if similar_artists_entry: entries.append(similar_artists_entry)
    return entries

def _handler_element_genre_artist(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist_response : Response[Artist] = connector.getArtist(artist_id)
    if not artist_response.isOk(): raise Exception(f"Cannot retrieve artist by id {artist_id}")
    artist : Artist = artist_response.getObj()
    genre : str = item_identifier.get(ItemIdentifierKey.GENRE_NAME)
    album_list : list[Album] = None
    offset : int = 0
    while not album_list or len(album_list) == __subsonic_max_return_size:
        album_list_response : Response[AlbumList] = connector.getAlbumList(
            ltype = ListType.BY_GENRE,
            size = __subsonic_max_return_size,
            genre = genre,
            offset = offset)
        if not album_list_response.isOk(): raise Exception(f"Failed to load albums for genre {genre} offset {offset}")
        album_list : list[Album] = album_list_response.getObj().getAlbums()
        album : Album
        for album in album_list:
            if artist.getName() in album.getArtist():
                # add the album
                album_entry : dict = _album_to_entry(objid, album)       
                entries.append(album_entry)
        offset += len(album_list)
    return entries

def _handler_element_sparse_album(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    response : Response[Album] = connector.getAlbum(album_id)
    if not response.isOk(): raise Exception(f"Cannot load album with album_id {album_id}")
    album : Album = response.getObj()
    album_entry : dict[str, any] = _album_to_entry(objid, album)
    # set title a little differently here ...
    title : str = f"Album: {album.getTitle()}"
    _set_album_title(title, album_entry)
    entries.append(album_entry)
    artist_entry : dict[str, any] = _artist_entry_for_album(objid, album)
    entries.append(artist_entry)
    top_songs_entry : dict[str, any] = _artist_to_top_songs_entry(objid, album.getArtistId(), album.getArtist())
    if top_songs_entry: entries.append(top_songs_entry)
    similar_artist_entry : dict[str, any] = _similar_artists_for_artist(objid, album.getArtistId())
    if similar_artist_entry: entries.append(similar_artist_entry)
    return entries

def _similar_artists_for_artist(objid, artist_id : str) -> dict[str, any]:
    res_artist_info : Response[ArtistInfo] = connector.getArtistInfo(artist_id)
    if not res_artist_info.isOk(): raise Exception(f"Cannot get artist info for artist_id {artist_id}")
    if len(res_artist_info.getObj().getSimilarArtists()) > 0:
        # ok to add similar artists entry
        similar_artist_identifier : ItemIdentifier = ItemIdentifier(ElementType.ARTIST_SIMILAR.getName(), artist_id)
        similar_artist_id : str = _create_objid_simple(objid, __create_id_from_identifier(similar_artist_identifier))
        similar_artists_entry : dict = direntry(
            similar_artist_id, 
            objid, 
            title = "Similar Artists")
        # artist_art
        sim_artist_art : str = _get_cached_element(ElementType.ARTIST, res_artist_info.getObj().getSimilarArtists()[0].getId())
        if sim_artist_art:
            _set_album_art_from_album_id(sim_artist_art, similar_artists_entry)
        return similar_artists_entry    

def _artist_entry_for_album(objid, album : Album) -> dict[str, any]:
    artist_identifier : ItemIdentifier = ItemIdentifier(ElementType.ARTIST.getName(), album.getArtistId())
    artist_id : str = _create_objid_simple(objid, __create_id_from_identifier(artist_identifier))
    artist_entry : dict = direntry(
        artist_id, 
        objid, 
        title = f"Artist: {album.getArtist()}")
    artist_art : str = _get_cached_element(ElementType.ARTIST, album.getArtistId())
    if not artist_art:
        artist_res : Response[Artist] = connector.getArtist(album.getArtistId())
        if not artist_res.isOk(): raise Exception(f"Cannot load artist with artist_id {album.getArtistId()}")
        artist_art = get_artist_cover(album.getArtistId())
    if artist_art:
        _set_album_art_from_album_id(artist_art, artist_entry)
        _cache_element_value(ElementType.ARTIST, album.getArtistId(), artist_art, force_update = False)
    return artist_entry

def _artist_to_top_songs_entry(objid, artist_id : str, artist : str) -> dict[str, any]:
    res_top_songs : Response[TopSongs] = connector.getTopSongs(artist)
    if not res_top_songs.isOk(): raise Exception(f"Cannot load top songs for artist {artist}")
    if len(res_top_songs.getObj().getSongs()) > 0:
        # ok to create top songs entry, else None
        top_songs_identifier : ItemIdentifier = ItemIdentifier(ElementType.ARTIST_TOP_SONGS.getName(), artist_id)
        top_songs_id : str = _create_objid_simple(objid, __create_id_from_identifier(top_songs_identifier))
        top_songs_entry : dict = direntry(
            top_songs_id, 
            objid, 
            title = f"Top Songs by {artist}")
        _set_album_art_from_album_id(res_top_songs.getObj().getSongs()[0].getAlbumId(), top_songs_entry)
        return top_songs_entry

def _handler_element_similar_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_similar_artists for artist_id {artist_id}")
    res : Response[ArtistInfo] = connector.getArtistInfo(artist_id)
    if not res.isOk(): raise Exception(f"Cannot get artist info for artist_id {artist_id}")
    sim_artist_list : list[SimilarArtist] = res.getObj().getSimilarArtists()
    sim_artist : SimilarArtist
    for sim_artist in sim_artist_list:
        entries.append(_artist_to_entry(objid, sim_artist.getId(), sim_artist.getName()))
    return entries

def _handler_element_album(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    avp_enc : str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, None)
    msgproc.log(f"_handler_element_album for album_id {album_id} avp_enc {avp_enc}")
    album_version_path : str = __thing_codec.decode(avp_enc) if avp_enc else None
    album_tracks : AlbumTracks = _get_album_tracks(album_id) if not album_version_path else None
    if album_tracks and album_tracks.getAlbumVersionCount() > 1:
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

def _handler_element_radio_station(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    msgproc.log(f"_handler_element_radio_station start")
    station_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_radio_station should serve station_id {station_id}")
    response : Response[InternetRadioStations] = connector.getInternetRadioStations()
    if not response.isOk(): raise Exception(f"Cannot get the internet radio stations")
    select_station : InternetRadioStation
    station : InternetRadioStation
    for station in response.getObj().getStations():
        if station.getId() == station_id:
            select_station = station
            break
    identifier : ItemIdentifier = ItemIdentifier(ElementType.INTERNET_RADIO.getName(), station_id)
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    station_entry : dict = _station_to_entry(objid, select_station)
    entries.append(station_entry)
    return entries

def _handler_element_track(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    #msgproc.log(f"_handler_element_track start")
    song_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_track should serve song_id {song_id}")
    song_response : Response[Song] = connector.getSong(song_id)
    if not song_response.isOk(): raise Exception(f"Cannot find song with id {song_id}")
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), song_id)
    id : str = _create_objid_simple(objid, __create_id_from_identifier(identifier))
    song_entry : dict = _song_data_to_entry(objid, id, song_response.getObj())
    entries.append(song_entry)
    return entries

__tag_action_dict : dict = {
    TagType.NEWEST.getTagName(): _handler_tag_newest,
    TagType.RECENTLY_PLAYED.getTagName(): _handler_tag_recently_played,
    TagType.HIGHEST_RATED.getTagName(): _handler_tag_highest_rated,
    TagType.MOST_PLAYED.getTagName(): _handler_tag_most_played,
    TagType.FAVOURITES.getTagName(): _handler_tag_favourites,
    TagType.RANDOM.getTagName(): _handler_tag_random,
    TagType.GENRES.getTagName(): _handler_tag_genres,
    TagType.ARTISTS_ALL.getTagName(): _handler_tag_artists,
    TagType.ARTISTS_INDEXED.getTagName(): _handler_tag_artists_indexed,
    TagType.PLAYLISTS.getTagName(): _handler_tag_playlists,
    TagType.INTERNET_RADIOS.getTagName(): _handler_tag_internet_radios,
    TagType.RANDOM_SONGS.getTagName(): _handler_tag_random_songs
}

__elem_action_dict : dict = {
    ElementType.GENRE.getName(): _handler_element_genre,
    ElementType.ARTIST_INITIAL.getName(): _handler_element_artist_initial,
    ElementType.ARTIST.getName(): _handler_element_artist,
    ElementType.GENRE_ARTIST.getName(): _handler_element_genre_artist,
    ElementType.ALBUM.getName(): _handler_element_album,
    ElementType.SPARSE_ALBUM.getName(): _handler_element_sparse_album,
    ElementType.GENRE_ARTIST_LIST.getName(): _handler_element_genre_artists,
    ElementType.GENRE_ALBUM_LIST.getName(): _handler_element_genre_album_list,
    ElementType.PLAYLIST.getName(): _handler_element_playlist,
    ElementType.TRACK.getName(): _handler_element_track,
    ElementType.RANDOM_SONG.getName(): _handler_element_random_song,
    ElementType.NEXT_RANDOM_SONGS.getName(): _handler_element_next_random_songs,
    ElementType.INTERNET_RADIO.getName(): _handler_element_radio_station,
    ElementType.RANDOM_SONG_THE_SONG.getName(): _handler_element_random_song_the_song,
    ElementType.ARTIST_TOP_SONGS.getName(): _handler_element_artist_top_songs,
    ElementType.ARTIST_SIMILAR.getName(): _handler_element_similar_artists,
    ElementType.ARTIST_ALBUMS.getName(): _handler_element_artist_albums
}

@dispatcher.record('browse')
def browse(a):
    msgproc.log(f"browse: args: --{a}--")
    _initsubsonic()
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    path = htmlunescape(_objidtopath(objid))
    msgproc.log(f"browse: path: --{path}--")
    path_list : list[str] = objid.split("/")
    curr_path : str
    for curr_path in path_list:
        if not _g_myprefix == curr_path:
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
                objid = objid, 
                artist_id = current_artist.getId(),
                artist_name = current_artist.getName()))
    #msgproc.log(f"browse: returning --{entries}--")
    return _returnentries(entries)

if __autostart == 1:
    _initsubsonic()
msgproc.log("Subsonic running")
msgproc.mainloop()

