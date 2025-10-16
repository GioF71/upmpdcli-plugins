# Copyright (C) 2023,2024,2025 Giovanni Fulco
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

# this should contain all methods which interact directly with the subsonic server

from subsonic_connector.connector import Connector
from subsonic_connector.list_type import ListType
from subsonic_connector.response import Response
from subsonic_connector.album_list import AlbumList
from subsonic_connector.album import Album
from subsonic_connector.artist import Artist
from subsonic_connector.song import Song
from subsonic_connector.search_result import SearchResult

import cache_actions
from tag_type import TagType
from element_type import ElementType

import request_cache
import connector_provider
import cache_manager_provider

import album_util
import upnp_util
import config
from keyvaluecaching import KeyValueItem
import persistence
import persistence_constants
import cache_type

import cmdtalkplugin
import upmpdmeta

import secrets
import constants
import requests
import mimetypes
import glob

import copy
import os
import time
import musicbrainzutils

from functools import cmp_to_key
from typing import Callable
from enum import Enum
from track_info import TrackInfo

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

# additional lossy extensions listed here
additional_lossy_prefix_set: set[str] = {"m4a", "mp3"}


class DictKey(Enum):
    DICT_KEY_BITDEPTH = "BIT_DEPTH"
    DICT_KEY_SAMPLERATE = "SAMPLE_RATE"
    DICT_KEY_SUFFIX = "SUFFIX"
    DICT_KEY_BITRATE = "BITRATE"


def get_track_list_badge(track_list: list[Song], list_identifier: str = None) -> str:
    prop_dict: dict[str, list[int]] = _get_track_list_streaming_properties(track_list)
    track_info_list: list[TrackInfo] = get_track_info_list(track_list)
    if not track_info_list or len(track_info_list) == 0:
        msgproc.log(f"get_track_list_badge for [{list_identifier}] no tracks were processed")
        return None
    if (DictKey.DICT_KEY_BITDEPTH.value not in prop_dict or
            DictKey.DICT_KEY_SAMPLERATE.value not in prop_dict):
        msgproc.log(f"No streaming information available in [{list_identifier}]")
        return None
    # information are available, go on ...
    # are they all lossy?
    all_lossy: bool = __all_lossy(track_info_list)
    # do they all have the same bitrate?
    unique_bitrate: int = _get_unique_bitrate(prop_dict)
    # do they all have the same suffix?
    unique_suffix: str = _get_unique_suffix(prop_dict)
    # do they all have the same sampling rate?
    unique_sampling_rate: int = __get_unique_sampling_rate(prop_dict)
    readable_unique_sampling_rate: str = __get_readable_sampling_rate(unique_sampling_rate)
    if all_lossy:
        # we always return from this branch
        if unique_bitrate and unique_suffix and unique_sampling_rate:
            return f"{unique_suffix}@{unique_bitrate}/{readable_unique_sampling_rate}"
        else:
            avg_bitrate: int = _get_avg_bitrate_int(track_info_list)
            if (unique_suffix and unique_sampling_rate and
                    (avg_bitrate and avg_bitrate > 0)):
                # use avg bitrate rate
                return f"{unique_suffix}@{avg_bitrate}/{readable_unique_sampling_rate}"
            elif unique_suffix and unique_sampling_rate:
                # no avg bitrate
                return f"{unique_suffix}/{readable_unique_sampling_rate}"
            elif unique_suffix:
                return unique_suffix
            else:
                # fallback
                return "lossy"
    bit_depth_list: list[int] = prop_dict[DictKey.DICT_KEY_BITDEPTH.value]
    bit_depth_list.sort(reverse=True)
    sampling_rate_list: list[int] = prop_dict[DictKey.DICT_KEY_SAMPLERATE.value]
    sampling_rate_list.sort(reverse=True)
    if len(bit_depth_list) == 0 or len(sampling_rate_list) == 0:
        msgproc.log("Empty streaming info in [{list_identifier}]")
        return None
    best_bit_depth: int = bit_depth_list[0]
    best_sampling_rate: int = sampling_rate_list[0]
    if len(bit_depth_list) > 1 or len(sampling_rate_list) > 1:
        if best_bit_depth >= 24 and best_sampling_rate >= 44100:
            return "~HD"
        if best_bit_depth == 16 and best_sampling_rate == 44100:
            return "~CD"
        if best_bit_depth == 16 and best_sampling_rate >= 48000:
            return f"~16/{__get_readable_sampling_rate(best_sampling_rate)}"
        if best_bit_depth == 0:
            return f"~Lossy/{__get_readable_sampling_rate(best_sampling_rate)}"
        # other cases?
        return f"~{best_bit_depth}/{__get_readable_sampling_rate(best_sampling_rate)}"
    else:
        # list sizes or bit_depth and sampling rate are 1
        sr: str = __get_readable_sampling_rate(best_sampling_rate)
        if best_bit_depth == 0:
            # lossy
            suffix_list: list[str] = (prop_dict[DictKey.DICT_KEY_SUFFIX.value]
                                      if DictKey.DICT_KEY_SUFFIX.value in prop_dict
                                      else list())
            display_codec: str = (suffix_list[0]
                                  if len(suffix_list) == 1
                                  else "lossy")
            if unique_bitrate:
                display_codec = f"{display_codec}@{unique_bitrate}"
            return f"{display_codec}/{sr}"
        if unique_suffix and unique_suffix.lower() in config.whitelist_codecs:
            if best_bit_depth == 1:
                return f"DSD {sr}"
            else:
                return f"{best_bit_depth}/{sr}"
        elif unique_suffix:
            # mention suffix
            if best_bit_depth == 1:
                return f"{unique_suffix}@DSD/{sr}"
            else:
                return f"{unique_suffix}@{best_bit_depth}/{sr}"
        else:
            # use ~ as we don't have an unique suffix
            if best_bit_depth == 1:
                return f"~DSD {sr}"
            else:
                return f"~{best_bit_depth}/{sr}"


def _get_avg_bitrate(track_info_list: list[TrackInfo]) -> float:
    sum: float = 0.0
    current: TrackInfo
    for current in track_info_list:
        sum += float(current.bitrate) if current.bitrate else 0.0
    return sum / float(len(track_info_list))


def _get_avg_bitrate_int(track_info_list: list[TrackInfo]):
    return int(_get_avg_bitrate(track_info_list))


def get_track_info_list(track_list: list[Song]) -> list[TrackInfo]:
    result: list[TrackInfo] = list()
    song: Song
    for song in track_list:
        bit_depth: int = song.getItem().getByName(constants.ItemKey.BIT_DEPTH.value)
        sampling_rate: int = song.getItem().getByName(constants.ItemKey.SAMPLING_RATE.value)
        suffix: str = song.getSuffix()
        bitrate: int = song.getBitRate()
        current: TrackInfo = TrackInfo()
        current.bit_depth = bit_depth
        current.sampling_rate = sampling_rate
        current.suffix = suffix
        current.bitrate = bitrate
        result.append(current)
    return result


def __get_unique_sampling_rate(prop_dict: dict[str, list[int]]) -> int:
    sampling_rate_list: list[int] = (prop_dict[DictKey.DICT_KEY_SAMPLERATE.value]
                                     if DictKey.DICT_KEY_SAMPLERATE.value in prop_dict
                                     else list())
    if len(sampling_rate_list) == 1:
        return sampling_rate_list[0]
    return None


def _get_unique_bitrate(prop_dict: dict[str, list[int]]) -> int:
    bitrate_list: list[int] = (prop_dict[DictKey.DICT_KEY_BITRATE.value]
                               if DictKey.DICT_KEY_BITRATE.value in prop_dict
                               else list())
    if len(bitrate_list) == 1:
        return bitrate_list[0]
    return None


def _get_unique_suffix(prop_dict: dict[str, list[int]]) -> str:
    suffix_list: list[str] = (prop_dict[DictKey.DICT_KEY_SUFFIX.value]
                              if DictKey.DICT_KEY_SUFFIX.value in prop_dict
                              else list())
    if len(suffix_list) == 1:
        return suffix_list[0]
    return None


def _get_track_list_streaming_properties(track_list: list[Song]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = dict()
    song: Song
    for song in track_list:
        # bit depth
        bit_depth: int = song.getItem().getByName(constants.ItemKey.BIT_DEPTH.value)
        __maybe_append_to_dict_list(result, DictKey.DICT_KEY_BITDEPTH.value, bit_depth)
        # sampling rate
        sampling_rate: int = song.getItem().getByName(constants.ItemKey.SAMPLING_RATE.value)
        __maybe_append_to_dict_list(result, DictKey.DICT_KEY_SAMPLERATE.value, sampling_rate)
        # suffix
        suffix: str = song.getSuffix().lower() if song.getSuffix() else None
        __maybe_append_to_dict_list(result, DictKey.DICT_KEY_SUFFIX.value, suffix)
        # bitrate
        bitrate: int = song.getBitRate()
        __maybe_append_to_dict_list(result, DictKey.DICT_KEY_BITRATE.value, bitrate)
    return result


def is_lossy(suffix: str, bit_depth: int) -> bool:
    if not bit_depth or bit_depth == 0:
        return True
    # also select suffix are lossy
    if suffix:
        return suffix in additional_lossy_prefix_set
    return False


def __all_lossy(track_info_list: list[TrackInfo]) -> bool:
    current: TrackInfo
    for current in track_info_list if track_info_list else list():
        if not current.is_lossy():
            return False
    return True


def __maybe_append_to_dict_list(
        prop_dict: dict[str, list[any]],
        dict_key: str,
        new_value: any):
    if new_value is None:
        return
    item_list: list[any] = None
    if dict_key not in prop_dict:
        item_list = list()
        # list was not there, safe to add
        item_list.append(new_value)
        prop_dict[dict_key] = item_list
    else:
        item_list = prop_dict[dict_key]
        if new_value not in item_list:
            item_list.append(new_value)


__readable_sr: dict[int, str] = {
    8000: "8k",
    11025: "11k",
    12000: "12k",
    22050: "22k",
    24000: "24k",
    32000: "32k",
    44100: "44k",
    48000: "48k",
    88200: "88k",
    96000: "96k",
    176400: "176k",
    192000: "192k",
    352800: "352k",
    384000: "384k",
    705600: "705k",
    768000: "768k",
    1411200: "1411k",
    1536000: "1536k",
    2822400: "2.8M",
    5644800: "5.6M",
    11289600: "11.2M",
    22579200: "22.4M"
}


def __get_readable_sampling_rate(sampling_rate: int) -> str:
    sr: str = (__readable_sr[sampling_rate]
               if sampling_rate in __readable_sr
               else str(sampling_rate))
    return sr


class ArtistIdAndName:

    def __init__(self, id: str, name: str, cover_art: str = None):
        self.__id: str = id
        self.__name: str = name
        self.__cover_art: str = cover_art

    @property
    def id(self) -> str:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name

    @property
    def cover_art(self) -> str:
        return self.__cover_art


class DiscTitle:

    def __init__(self, disc_num: int, title: str):
        self.__disc_num: str = disc_num
        self.__title: str = title

    @property
    def disc_num(self) -> str:
        return self.__disc_num

    @property
    def title(self) -> str:
        return self.__title


def get_random_art_by_genre(
        genre: str,
        max_items: int = 100) -> str:
    connector: Connector = connector_provider.get()
    response: Response[AlbumList] = connector.getAlbumList(
        ltype=ListType.BY_GENRE,
        genre=genre,
        size=max_items)
    if not response.isOk():
        return None
    album: Album = secrets.choice(response.getObj().getAlbums())
    if album:
        return album.getCoverArt()
    return None


def try_get_album(
        album_id: str,
        propagate_fail: bool = False,
        execute_cache_action: bool = False) -> Album:
    try:
        res: Response[Album] = connector_provider.get().getAlbum(album_id)
        if res and res.getObj() and res.isOk():
            album: Album = res.getObj()
            # execute on_album from cache_actions (stores metadata)
            if execute_cache_action:
                cache_actions.on_album(album)
            return album
    except Exception as e:
        msgproc.log(f"Cannot find Album by album_id [{album_id}] due to [{type(e)}] [{e}]")
        if propagate_fail:
            raise e


def try_get_artist(artist_id: str) -> Artist:
    start: float = time.time()
    try:
        res: Response[Artist] = connector_provider.get().getArtist(artist_id)
        artist: Artist = res.getObj() if res and res.isOk() else None
        if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
            msgproc.log(f"try_get_artist loaded artid_id [{artist_id}] "
                        f"success [{artist is not None}] in "
                        f"[{(time.time() - start):.3f}] sec")
        return artist
    except Exception as e:
        msgproc.log(f"Cannot find Artist by artist_id [{artist_id}] due to [{type(e)}] [{e}]")


def get_cover_art_by_song(song: Song) -> str:
    return song.getCoverArt() if song else None


def get_cover_art_by_album(album: Album) -> str:
    return album.getCoverArt() if album else None


def get_cover_art_by_album_id(album_id: str) -> str:
    album: Album = try_get_album(album_id)
    return get_cover_art_by_album(album)


def get_cover_art_url_by_album(album: Album) -> str:
    return build_cover_art_url(get_cover_art_by_album(album))


def get_cover_art_url_by_song(song: Song) -> str:
    return build_cover_art_url(get_cover_art_by_song(song))


def get_cover_art_url_by_album_id(album_id: str) -> str:
    return build_cover_art_url(get_cover_art_by_album_id(album_id))


def get_album_tracks(album_id: str) -> tuple[Album, album_util.AlbumTracks]:
    result: list[Song] = []
    album: Album = try_get_album(album_id)
    if album and album.getArtist():
        msgproc.log(f"get_album_tracks executing on_album on album_id [{album_id}] artist [{album.getArtist()}] ...")
        cache_actions.on_album(album)
    else:
        msgproc.log(f"get_album_tracks will not execute on_album on album_id [{album_id}] ...")
        return None, []
    albumArtURI: str = build_cover_art_url(album.getCoverArt())
    song_list: list[Song] = album.getSongs()
    sort_song_list_result: album_util.SortSongListResult = album_util.sort_song_list(song_list)
    current_song: Song
    for current_song in sort_song_list_result.getSongList():
        result.append(current_song)
    albumArtURI: str = build_cover_art_url(album.getCoverArt())
    return album, album_util.AlbumTracks(
        codec_set_by_path=sort_song_list_result.getCodecSetByPath(),
        album=album,
        song_list=result,
        art_uri=albumArtURI,
        multi_codec_album=sort_song_list_result.getMultiCodecAlbum())


def get_albums(
        query_type: str,
        size: int = config.get_items_per_page(),
        offset: int = 0,
        fromYear=None,
        toYear=None) -> list[Album]:
    connector: Connector = connector_provider.get()
    albumListResponse: Response[AlbumList]
    if TagType.RECENTLY_ADDED_ALBUMS.getQueryType() == query_type:
        albumListResponse = connector.getNewestAlbumList(
            size=size,
            offset=offset)
    elif TagType.NEWEST_ALBUMS.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(
            ltype=ListType.BY_YEAR,
            size=size,
            offset=offset,
            fromYear=fromYear,
            toYear=toYear)
    elif TagType.OLDEST_ALBUMS.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(
            ltype=ListType.BY_YEAR,
            size=size,
            offset=offset,
            fromYear=fromYear,
            toYear=toYear)
    elif TagType.RANDOM.getQueryType() == query_type:
        albumListResponse = request_cache.get_random_album_list(
            size=size,
            offset=offset)
    elif TagType.RECENTLY_PLAYED_ALBUMS.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(
            ltype=ListType.RECENT,
            size=size,
            offset=offset)
    elif TagType.MOST_PLAYED_ALBUMS.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(
            ltype=ListType.FREQUENT,
            size=size,
            offset=offset)
    elif TagType.HIGHEST_RATED_ALBUMS.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(
            ltype=ListType.HIGHEST,
            size=size,
            offset=offset)
    elif TagType.FAVOURITE_ALBUMS.getQueryType() == query_type:
        albumListResponse = connector.getAlbumList(
            ltype=ListType.STARRED,
            size=size,
            offset=offset)
    if not albumListResponse.isOk():
        raise Exception(f"Cannot execute query {query_type} "
                        f"for size {size} offset {offset}")
    return albumListResponse.getObj().getAlbums()


# this can be slow with large libraries
def load_artists_by_genre(genre: str, artist_offset: int, max_artists: int) -> list[ArtistIdAndName]:
    artist_set: set[ArtistIdAndName] = set()
    artist_id_set: set[str] = set()
    req_offset: int = 0
    loaded_album_count: int = 0
    while (len(artist_set) < (artist_offset + max_artists)):
        # we optimistically use max_artists as album size
        album_list_response: Response[AlbumList] = connector_provider.get().getAlbumList(
            ltype=ListType.BY_GENRE,
            genre=genre,
            offset=req_offset,
            size=100)
        if not album_list_response.isOk():
            return set()
        album_list: list[Album] = album_list_response.getObj().getAlbums()
        # exit when no data
        if (not album_list) or len(album_list) == 0:
            break
        # log how many albums have been retrieved
        loaded_album_count += len(album_list)
        msgproc.log(f"load_artists_by_genre for [{genre}] from offset [{artist_offset}] "
                    f"loaded [{loaded_album_count}] albums for [{len(artist_set)}] artists")
        cached: bool = False
        album: Album
        for album in album_list:
            artist_id: str = album.getArtistId()
            if not artist_id:
                msgproc.log(f"load_artists_by_genre skipping artist [{album.getArtist()}] (no artist_id)")
                continue
            if artist_id not in artist_id_set:
                artist_set.add(ArtistIdAndName(
                    id=artist_id,
                    name=album.getArtist(),
                    cover_art=album.getCoverArt()))
                artist_id_set.add(artist_id)
                if not cached:
                    cache_manager_provider.get().cache_element_value(
                        ElementType.GENRE_ARTIST_LIST,
                        genre,
                        album.getId())
                    cached = True
                if len(artist_set) >= (artist_offset + max_artists):
                    break
        req_offset += len(album_list)
    # publishing how many artists in the set
    msgproc.log(f"load_artists_by_genre for [{genre}] from artist_offset [{artist_offset}] "
                f"total artists found [{len(artist_set)}], providing offsetted list ...")
    artist_id_list: list[ArtistIdAndName] = list()
    # store set to a list
    for artist in artist_set:
        artist_id_list.append(artist)
    # slice the list
    artist_id_list = artist_id_list[artist_offset:] if len(artist_id_list) > artist_offset else list()
    return artist_id_list


def get_album_list_by_artist_genre(
        artist: Artist,
        genre_name: str) -> list[Album]:
    result: list[Album] = list()
    album_list: list[Album] = None
    offset: int = 0
    while not album_list or len(album_list) == constants.subsonic_max_return_size:
        album_list_response: Response[AlbumList] = connector_provider.get().getAlbumList(
            ltype=ListType.BY_GENRE,
            offset=offset,
            size=constants.subsonic_max_return_size,
            genre=genre_name)
        if not album_list_response.isOk():
            raise Exception(f"Failed to load albums for "
                            f"genre {genre_name} offset {offset}")
        album_list: list[Album] = album_list_response.getObj().getAlbums()
        current_album: Album
        for current_album in album_list if album_list and len(album_list) > 0 else []:
            if artist.getName() in current_album.getArtist():
                result.append(current_album)
        offset += len(album_list)
    return result


class ArtistsOccurrence:

    def __init__(self, id: str, name: str):
        self.__id = id
        self.__name = name

    @property
    def id(self) -> str:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name


class Contributor:

    def __init__(self, role: str, artist_reference: ArtistsOccurrence):
        self.__role: str = role
        self.__artist_reference: ArtistsOccurrence = artist_reference

    @property
    def role(self) -> str:
        return self.__role

    @property
    def artist_reference(self) -> ArtistsOccurrence:
        return self.__artist_reference


def get_album_artists_from_album(album: Album) -> list[dict[str, str]]:
    return album.getItem().getListByName(constants.ItemKey.ARTISTS.value)


def get_contributors_in_song_or_album(obj: Song | Album) -> list[ArtistsOccurrence]:
    contributor_list: list[dict[str, str]] = obj.getItem().getListByName(constants.ItemKey.CONTRIBUTORS.value)
    result: list[Contributor] = []
    current: dict[str, str]
    for current in contributor_list if contributor_list else []:
        if constants.DictKey.ROLE.value in current and constants.DictKey.ARTIST.value in current:
            role: str = current[constants.DictKey.ROLE.value]
            artist_dict: dict[str, str] = current[constants.DictKey.ARTIST.value]
            if not isinstance(artist_dict, dict):
                raise Exception(f"Item {constants.ItemKey.CONTRIBUTORS.value} does not contain the "
                                f"{constants.DictKey.ARTIST.value} dict")
            if constants.DictKey.ID.value not in artist_dict or constants.DictKey.NAME.value not in artist_dict:
                raise Exception(f"Item {constants.ItemKey.CONTRIBUTORS.value} does not contain the "
                                f"{constants.DictKey.ID.value} or {constants.DictKey.NAME.value} key")
            contributor: Contributor = Contributor(
                role=role,
                artist_reference=ArtistsOccurrence(
                    id=artist_dict[constants.DictKey.ID.value],
                    name=artist_dict[constants.DictKey.NAME.value]))
            result.append(contributor)
        else:
            raise Exception(f"Item {constants.ItemKey.CONTRIBUTORS.value} does not contain the expected keys")
    return result


def get_artists_in_song_or_album(obj: Song | Album, item_key: constants.ItemKey) -> list[ArtistsOccurrence]:
    artist_list: list[dict[str, str]] = obj.getItem().getListByName(item_key.value)
    result: list[ArtistsOccurrence] = []
    current: dict[str, str]
    for current in artist_list if artist_list else []:
        if constants.DictKey.NAME.value in current and constants.DictKey.ID.value in current:
            occ: ArtistsOccurrence = ArtistsOccurrence(current[constants.DictKey.ID.value], current[constants.DictKey.NAME.value])
            result.append(occ)
        else:
            raise Exception(f"Item {item_key.value} does not contain the expected keys")
    return result


def get_all_artists_in_album(album: Album, in_songs: bool = True) -> list[ArtistsOccurrence]:
    occ_list: list[ArtistsOccurrence] = list()
    artist_id_set: set[str] = set()
    # add id,name from album itself
    artist_id: str = album.getArtistId()
    artist_name: str = album.getArtist()
    if artist_id and artist_name:
        occ_list.append(ArtistsOccurrence(id=artist_id, name=artist_name))
        artist_id_set.add(artist_id)
    lst: list[dict[str, str]] = get_album_artists_from_album(album)
    if not lst:
        lst = list()
    current: dict[str, str]
    for current in lst:
        if ((constants.DictKey.NAME.value in current and constants.DictKey.ID.value in current)
                and not current[constants.DictKey.ID.value] in artist_id_set):
            occ_list.append(ArtistsOccurrence(id=current[constants.DictKey.ID.value], name=current[constants.DictKey.NAME.value]))
            artist_id_set.add(current[constants.DictKey.ID.value])
    song_list: list[Song] = album.getSongs() if in_songs else list()
    if song_list:
        song: Song
        for song in song_list:
            song_artist_list: list[ArtistsOccurrence] = []
            album_artist_list: list[ArtistsOccurrence] = get_artists_in_song_or_album(song, constants.ItemKey.ALBUM_ARTISTS)
            artist_list: list[ArtistsOccurrence] = get_artists_in_song_or_album(song, constants.ItemKey.ARTISTS)
            if album_artist_list:
                song_artist_list.extend(album_artist_list)
            if artist_list:
                song_artist_list.extend(artist_list)
            song_dict: ArtistsOccurrence
            for song_dict in song_artist_list:
                if song_dict.id not in artist_id_set:
                    occ_list.append(song_dict)
                    artist_id_set.add(song_dict.id)
    return occ_list


def is_artist_id_in_artist_occurrence_list(artist_id: str, lst: list[ArtistsOccurrence]) -> bool:
    curr: ArtistsOccurrence
    for curr in lst:
        if curr.id == artist_id:
            return True
    return False


def is_artist_id_in_contributor_list(artist_id: str, lst: list[Contributor], with_role: str = None) -> bool:
    curr: Contributor
    for curr in lst:
        if with_role and not curr.role == with_role:
            # does not match role
            continue
        if curr.artist_reference.id == artist_id:
            return True
    return False


def is_authored_or_contributed_by_artist_id(obj: Song | Album, artist_id: str, with_role: str = None) -> bool:
    album_artist_list: list[ArtistsOccurrence] = get_artists_in_song_or_album(obj, constants.ItemKey.ALBUM_ARTISTS)
    if is_artist_id_in_artist_occurrence_list(artist_id, album_artist_list):
        return True
    artist_list: list[ArtistsOccurrence] = get_artists_in_song_or_album(obj, constants.ItemKey.ARTISTS)
    if is_artist_id_in_artist_occurrence_list(artist_id, artist_list):
        return True
    # look in contributors
    contributor_list: list[Contributor] = get_contributors_in_song_or_album(obj)
    return is_artist_id_in_contributor_list(artist_id, contributor_list, with_role=with_role)


def filter_out_artist_id(artist_list: list[ArtistsOccurrence], artist_id: str) -> list[ArtistsOccurrence]:
    result: list[ArtistsOccurrence] = []
    occ: ArtistsOccurrence
    for occ in artist_list:
        if not occ.id == artist_id:
            result.append(occ)
    return result


def get_album_date_for_sorting(album: Album) -> str:
    result: str = album_util.get_album_original_release_date(album)
    if not result:
        # fallback to date.
        y: int = album.getYear()
        if y and isinstance(y, int):
            # assume january 1st
            result = f"{y:04}-01-01"
    return result if result else "0000-01-01"


def ensure_directory(base_dir: str, sub_dir_list: list[str]) -> str:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    curr_sub_dir: str
    curr_dir: str = base_dir
    for curr_sub_dir in sub_dir_list:
        new_dir: str = os.path.join(curr_dir, curr_sub_dir)
        if not os.path.exists(new_dir):
            if verbose:
                msgproc.log(f"creating dir [{new_dir}] ...")
            os.mkdir(new_dir)
        curr_dir = new_dir
    return curr_dir


def get_artist_albums_as_main_artist(artist_id: str, album_list: list[Album]) -> list[Album]:
    return get_artist_albums_as_appears_on(
        artist_id=artist_id,
        album_list=album_list,
        opposite=True)


def get_artist_albums_as_appears_on(artist_id: str, album_list: list[Album], opposite: bool = False) -> list[Album]:
    result: list[Album] = list()
    current: Album
    for current in album_list if album_list else list():
        # appears on is true if artist_id from current album is empty or
        # if artist id from current album is different from artist_id
        different: bool = not current.getArtistId() or (current.getArtistId() and artist_id != current.getArtistId())
        check: bool = not different if opposite else different
        if check:
            result.append(current)
    return result


class AlbumReleaseTypes:

    def __init__(self, types: list[str]):
        self.__types: list[str] = list()
        t: str
        for t in types:
            splitted: list[str] = t.split("/")
            s: str
            for s in splitted if splitted and len(splitted) > 0 else list():
                self.__types.append(s)

    @property
    def types(self) -> list[str]:
        return copy.deepcopy(self.__types)

    @property
    def num_items(self) -> int:
        return len(self.__types)

    @property
    def display_name(self) -> str:
        if (len(self.__types) == 0 or
           (len(self.__types) == 1 and len(self.__types[0]) == 0)):
            return "*EMPTY*"
        return " / ".join(musicbrainzutils.display_value(x) for x in self.__types)

    @property
    def key(self) -> str:
        return "/".join(self.__types)

    @property
    def empty(self) -> str:
        return len(self.__types) == 0


class ReleaseTypeAndCount:

    def __init__(self, rt: AlbumReleaseTypes, count: int):
        self.__rt: AlbumReleaseTypes = rt
        self.__count: int = count

    @property
    def album_release_type(self) -> AlbumReleaseTypes:
        return self.__rt

    @property
    def count(self) -> int:
        return self.__count


def compareAlbumReleaseTypes(left: AlbumReleaseTypes, right: AlbumReleaseTypes) -> int:
    left_str: str = left.key
    right_str: str = right.key
    return 0 if left_str == right_str else 1 if left_str > right_str else -1


def get_release_types(album_list: list[Album]) -> dict[str, int]:
    result: dict[str, int] = dict()
    current: Album
    for current in album_list if album_list else list():
        album_release_types: AlbumReleaseTypes = get_album_release_types(current)
        key: str = album_release_types.key.lower()
        if key not in result:
            result[key] = 1
        else:
            result[key] = result[key] + 1
    return result


def release_type_to_album_list_label(release_type: str, album_count: int = None) -> str:
    if album_count is not None:
        return f"Release Type: {release_type.title()} [{album_count}]"
    else:
        return f"Release Type: {release_type.title()}"


def get_artists_by_same_name(artist: Artist) -> list[Artist]:
    artist_list: list[Artist] = list()
    search_result: SearchResult = connector_provider.get().search(
        query=artist.getName(),
        artistCount=100,
        albumCount=0,
        songCount=0)
    matching_list: list[Artist] = search_result.getArtists()
    matching: Artist
    for matching in matching_list:
        if matching.getId() == artist.getId():
            # skip same artist of course
            continue
        if not (matching.getName().lower() == artist.getName().lower()):
            # skip artist which simply contain the artist name
            continue
        artist_list.append(matching)
    return artist_list


def album_has_release_types(album: Album) -> bool:
    return album.getItem().hasName(constants.ItemKey.RELEASE_TYPES.value)


def get_album_release_types(album: Album) -> AlbumReleaseTypes:
    has_release_types: bool = album_has_release_types(album)
    album_release_types: list[str] = (album.getItem().getByName(constants.ItemKey.RELEASE_TYPES.value)
                                      if has_release_types
                                      else list())
    return AlbumReleaseTypes(
        types=musicbrainzutils.sanitize_release_types(
            value_list=album_release_types,
            print_function=lambda x: msgproc.log(x)))


def uncategorized_releases_only(release_types: dict[str, int]) -> bool:
    rl: int = len(release_types)
    if rl > 1:
        return False
    if rl == 0:
        return True
    # rl is 1
    if "" in release_types:
        return True
    else:
        return False


def get_explicit_status(album: Album) -> str:
    return album.getItem().getByName(constants.ItemKey.EXPLICIT_STATUS.value)


def get_explicit_status_display_value(
        explicit_status: str,
        display_mode: constants.ExplicitDiplayMode = constants.ExplicitDiplayMode.SHORT) -> str:
    for _, v in constants.ExplicitStatus.__members__.items():
        explicit_info: constants._ExplicitStatusData = v.value
        if explicit_info.tag_value == explicit_status:
            return (explicit_info.display_value
                    if display_mode == constants.ExplicitDiplayMode.SHORT
                    else explicit_info.display_value_long)
    return None


def append_something_to_album_title(
        current_albumtitle: str,
        something: str,
        album_entry_type: constants.AlbumEntryType,
        is_search_result: bool,
        container_config: constants.ConfigParam,
        view_config: constants.ConfigParam,
        search_res_config: constants.ConfigParam) -> str:
    if not something:
        return current_albumtitle
    album_title: str = current_albumtitle
    do_append: bool = False
    if constants.AlbumEntryType.ALBUM_CONTAINER == album_entry_type:
        do_append = config.get_config_param_as_bool(container_config)
    elif constants.AlbumEntryType.ALBUM_VIEW == album_entry_type:
        # do we want the badge?
        if is_search_result:
            do_append = config.get_config_param_as_bool(search_res_config)
        else:
            do_append = config.get_config_param_as_bool(view_config)
    if do_append:
        album_title = f"{album_title} [{something}]"
    return album_title


def append_album_id_to_album_title(
        current_albumtitle: str,
        album_id: str,
        album_entry_type: constants.AlbumEntryType,
        is_search_result: bool) -> str:
    return append_something_to_album_title(
        current_albumtitle=current_albumtitle,
        something=album_id,
        album_entry_type=album_entry_type,
        is_search_result=is_search_result,
        container_config=constants.ConfigParam.APPEND_ALBUM_ID_IN_ALBUM_CONTAINER,
        view_config=constants.ConfigParam.APPEND_ALBUM_ID_IN_ALBUM_VIEW,
        search_res_config=constants.ConfigParam.APPEND_ALBUM_ID_IN_ALBUM_SEARCH_RES)


def append_album_badge_to_album_title(
        current_albumtitle: str,
        album_quality_badge: str,
        album_entry_type: constants.AlbumEntryType,
        is_search_result: bool) -> str:
    return append_something_to_album_title(
        current_albumtitle=current_albumtitle,
        something=album_quality_badge,
        album_entry_type=album_entry_type,
        is_search_result=is_search_result,
        container_config=constants.ConfigParam.ALLOW_QUALITY_BADGE_IN_ALBUM_CONTAINER,
        view_config=constants.ConfigParam.ALLOW_QUALITY_BADGE_IN_ALBUM_VIEW,
        search_res_config=constants.ConfigParam.ALLOW_QUALITY_BADGE_IN_ALBUM_SEARCH_RES)


def append_album_version_to_album_title(
        current_albumtitle: str,
        album_version: str,
        album_entry_type: constants.AlbumEntryType,
        is_search_result: bool) -> str:
    return append_something_to_album_title(
        current_albumtitle=current_albumtitle,
        something=album_version,
        album_entry_type=album_entry_type,
        is_search_result=is_search_result,
        container_config=constants.ConfigParam.ALLOW_ALBUM_VERSION_IN_ALBUM_CONTAINER,
        view_config=constants.ConfigParam.ALLOW_ALBUM_VERSION_IN_ALBUM_VIEW,
        search_res_config=constants.ConfigParam.ALLOW_ALBUM_VERSION_IN_ALBUM_SEARCH_RES)


def append_explicit_if_needed(current_albumtitle: str, album: Album) -> str:
    explicit_status: str = get_explicit_status(album)
    if (explicit_status is not None
            and len(explicit_status) > 0):
        if config.get_config_param_as_bool(constants.ConfigParam.DUMP_EXPLICIT_STATUS):
            msgproc.log(f"Explicit status is [{explicit_status}] for album [{album.getId()}] "
                        f"[{album.getTitle()}] by [{album.getArtist()}]")
        # find match ...
        display_value: str = get_explicit_status_display_value(explicit_status)
        explicit_expression = display_value if display_value else explicit_status
        return f"{current_albumtitle} [{explicit_expression}]"
    return current_albumtitle


def append_number_of_discs_to_album_title(
        current_albumtitle: str,
        album: Album,
        config_getter: Callable[[], bool]) -> str:
    result: str = current_albumtitle
    disc_titles: list[DiscTitle] = get_disc_titles_from_album(album)
    if config_getter() and len(disc_titles) > 1:
        result = f"{result} [{len(disc_titles)}]"
    return result


def append_number_of_tracks_to_album_title(
        current_albumtitle: str,
        album: Album,
        config_getter: Callable[[], bool]) -> str:
    result: str = current_albumtitle
    number_of_tracks: int = album.getSongCount()
    if config_getter() and number_of_tracks is not None:
        result = f"{result} [{number_of_tracks}]"
    return result


def get_disc_titles_from_album(album: Album) -> list[DiscTitle]:
    lst: list[DiscTitle] = []
    disc_title_list: list[dict[str, any]] = album.getItem().getByName(
        constants.ItemKey.DISC_TITLES.value,
        [])
    dt: dict[str, any]
    for dt in disc_title_list:
        disc_n: int = dt[constants.ItemKey.DISC_TITLES_DISC.value]
        disc_t: int = dt[constants.ItemKey.DISC_TITLES_TITLE.value]
        disc_title: DiscTitle = DiscTitle(disc_n, disc_t)
        lst.append(disc_title)
    return lst


def get_disc_titles_from_album_as_dict(album: Album) -> dict[int, str]:
    res: dict[int, str] = {}
    lst: list[DiscTitle] = get_disc_titles_from_album(album)
    dt: DiscTitle
    for dt in lst:
        if dt.disc_num not in res:
            res[dt.disc_num] = dt.title
    return res


def append_cached_mb_id_to_artist_entry_name_if_allowed(entry_name: str, artist_id: str) -> str:
    if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID):
        # see if we have it cached.
        artist_metadata: persistence.ArtistMetadata = persistence.get_artist_metadata(artist_id=artist_id)
        artist_mb_id: str = artist_metadata.artist_musicbrainz_id if artist_metadata else None
        if artist_mb_id:
            if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ACTION_ON_MB_ALBUM_CACHE):
                msgproc.log(f"Found mbid for artist_id [{artist_id}] -> [{artist_mb_id}]")
            as_ph: bool = config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID_AS_PLACEHOLDER)
            mb_val: str = ('mb' if as_ph else artist_mb_id)
            entry_name = f"{entry_name} [{mb_val}]"
        else:
            if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ACTION_ON_MB_ALBUM_CACHE):
                msgproc.log(f"Cannot find mbid for artist_id [{artist_id}]")
    return entry_name


def append_mb_id_to_artist_entry_name_if_allowed(entry_name: str, artist_mb_id: str) -> str:
    if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID):
        if artist_mb_id:
            as_ph: bool = config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID_AS_PLACEHOLDER)
            mb_val: str = ('mb' if as_ph else artist_mb_id)
            entry_name = f"{entry_name} [{mb_val}]"
    return entry_name


def append_genre_to_artist_entry_name_if_allowed(
        entry_name: str,
        album: Album,
        config_getter: Callable[[], bool]) -> str:
    result: str = entry_name
    if config_getter():
        genres: list[str] = album.getGenres()
        if genres and len(genres) > 0:
            result = f"{result} [{', '.join(genres)}]"
    return result


def __compare_album_by_date(left: Album, right: Album) -> int:
    cmp: int = 0
    left_v: str = get_album_date_for_sorting(left)
    right_v: str = get_album_date_for_sorting(right)
    cmp = -1 if left_v < right_v else 0 if left_v == right_v else 1
    return cmp


def sort_albums_by_date(album_list: list[Album]):
    reverse: bool = config.get_config_param_as_bool(constants.ConfigParam.ARTIST_ALBUM_NEWEST_FIRST)
    if album_list:
        album_list.sort(key=cmp_to_key(mycmp=__compare_album_by_date), reverse=reverse)


def get_album_musicbrainz_id(album: Album) -> str | None:
    return album.getItem().getByName(constants.ItemKey.MUSICBRAINZ_ID.value) if album else None


def get_artist_musicbrainz_id(artist: Artist) -> str | None:
    return artist.getItem().getByName(constants.ItemKey.MUSICBRAINZ_ID.value) if artist else None


def get_artist_cover_art(artist: Artist) -> str | None:
    if config.get_config_param_as_bool(constants.ConfigParam.ALLOW_ARTIST_COVER_ART):
        return artist.getItem().getByName(constants.ItemKey.COVER_ART.value) if artist else None
    else:
        None


def get_album_version(album: Album) -> str | None:
    return album.getItem().getByName(constants.ItemKey.VERSION.value) if album else None


def get_album_media_type(album: Album) -> str | None:
    return album.getItem().getByName(constants.ItemKey.MEDIA_TYPE.value) if album else None


def get_artist_media_type(artist: Artist) -> str | None:
    return artist.getItem().getByName(constants.ItemKey.MEDIA_TYPE.value) if artist else None


def get_album_record_label_names(album: Album) -> list[str]:
    result: list[str] = []
    rl: list[dict[str, str]] = album.getItem().getListByName(constants.ItemKey.ALBUM_RECORD_LABELS.value) if album else None
    current: dict[str, str]
    for current in rl:
        if constants.DictKey.NAME.value in current:
            result.append(current[constants.DictKey.NAME.value])
    return result


def get_artist_roles(artist: Artist) -> list[str]:
    return artist.getItem().getListByName(constants.ItemKey.ROLES.value) if artist else []


def get_album_moods(album: Album) -> list[str]:
    return album.getItem().getListByName(constants.ItemKey.MOODS.value) if album else []


def get_docroot_base_url() -> str:
    host_port: str = (os.environ["UPMPD_UPNPHOSTPORT"]
                      if "UPMPD_UPNPHOSTPORT" in os.environ
                      else None)
    doc_root: str = (os.environ["UPMPD_UPNPDOCROOT"]
                     if "UPMPD_UPNPDOCROOT" in os.environ
                     else None)
    if not host_port or not doc_root:
        return None
    return f"http://{host_port}"


def compose_docroot_url(right: str) -> str:
    doc_root_base_url: str = get_docroot_base_url()
    return f"{doc_root_base_url}/{right}" if doc_root_base_url else None


def match_supported_image_type_by_name(file_name: str) -> constants.SupportedImageType:
    if not file_name:
        return None
    file_name_lower: str = file_name.lower()
    s: constants.SupportedImageType
    for s in constants.SupportedImageType:
        ext: str
        for ext in s.extension_list:
            if (file_name_lower.endswith("." + ext)):
                return s
    return None


def match_supported_image_type_by_content_type(content_type: str) -> constants.SupportedImageType:
    s: constants.SupportedImageType
    for s in constants.SupportedImageType:
        ct: str
        for ct in s.content_type_list:
            if (content_type == ct):
                return s
    return None


def build_cover_art_url(item_id: str, force_save: bool = False) -> str:
    start: float = time.time()
    cover_art_url: str = __build_cover_art_url(item_id=item_id, force_save=force_save)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"build_cover_art_url for item_id [{item_id}] total elapsed [{elapsed:.3f}]")
    return cover_art_url


def __validate_image_caching_enabled() -> bool:
    return (config.getWebServerDocumentRoot() and
            config.get_config_param_as_bool(constants.ConfigParam.ENABLE_IMAGE_CACHING))


def __build_cover_art_url(item_id: str, force_save: bool = False) -> str:
    if not item_id:
        return None
    start: float = time.time()
    cover_art_url: str = connector_provider.get().buildCoverArtUrl(item_id=item_id)
    build_cover_art_url_elapsed: float = time.time() - start
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    if verbose:
        msgproc.log(f"__build_cover_art_url for [{item_id}] -> "
                    f"cover_art_url is [{cover_art_url}] "
                    f"created in [{build_cover_art_url_elapsed:.3f}]")
    if not cover_art_url:
        return None
    if (__validate_image_caching_enabled()):
        save_start: float = time.time()
        if verbose:
            msgproc.log(f"__build_cover_art_url saving image for item_id [{item_id}] ...")
        images_cached_dir: str = ensure_directory(
            config.getWebServerDocumentRoot(),
            config.get_webserver_path_images_cache())
        ensure_directory_elapsed: float = time.time() - save_start
        if verbose:
            msgproc.log(f"__build_cover_art_url ensured directory [{images_cached_dir}] "
                        f"exists in [{ensure_directory_elapsed:.3f}]")
        exists: str = False
        matching_files: list[str] = []
        cached_file_name: str = item_id
        cached_file_path: str = os.path.join(images_cached_dir, item_id)
        item_id_ext: str = os.path.splitext(cached_file_path)[1]
        if item_id_ext:
            # cached_file_path has extension, we convert that to lower case
            item_id_ext = item_id_ext.lower()
        item_id_with_ext: str = cached_file_path if item_id_ext else None
        if not item_id_with_ext:
            # item_id does not have an extension
            matching_files = __match_images_only(glob.glob(f"{cached_file_path}.*"))
            if matching_files and len(matching_files) > 0:
                item_id_with_ext = os.path.basename(matching_files[0])
                # remove other matching_files files ...
                to_remove: str
                for to_remove in matching_files[1:]:
                    msgproc.log(f"__build_cover_art_url removing spurious file [{to_remove}] ...")
                    os.remove(to_remove)
                exists = True
        else:
            exists = os.path.exists(cached_file_path)
            if exists:
                matching_files = [cached_file_path]
        serve_local: bool = False
        if exists and not force_save:
            # file exists or force_save not set
            serve_local = True
        else:
            # file does not exist or must be saved
            if exists and force_save:
                # remove matching_files
                to_remove: str
                for to_remove in matching_files:
                    try:
                        os.remove(to_remove)
                    except Exception as ex:
                        msgproc.log(f"Failed to remove [{to_remove}] due to [{type(ex)}] [{ex}]")
            try:
                read_start: float = time.time()
                response = requests.get(cover_art_url)
                content_type = response.headers.get('content-type')
                file_type: str = mimetypes.guess_all_extensions(content_type)
                # if file_type is "application/json", we probably have a failure
                ct_match: constants.SupportedImageType = match_supported_image_type_by_content_type(content_type)
                valid_file_type: bool = ct_match is not None
                read_elapsed: float = time.time() - read_start
                if verbose:
                    msgproc.log(f"reading [{item_id}] [{cover_art_url}] we got "
                                f"content_type [{content_type}] "
                                f"file_type [{file_type}] "
                                f"valid -> [{valid_file_type}] "
                                f"in [{read_elapsed:.3f}]")
                if valid_file_type:
                    item_id_ext: str = os.path.splitext(cached_file_path)[1]
                    # is cached_file_path without extension?
                    if item_id_ext is None or len(item_id_ext) == 0:
                        if file_type and len(file_type) > 0:
                            cached_file_name = cached_file_name + file_type[0]
                            item_id_with_ext = cached_file_name
                            cached_file_path: str = os.path.join(images_cached_dir, cached_file_name)
                        else:
                            # we cannot save!
                            cached_file_path = None
                    else:
                        cached_file_path: str = os.path.join(images_cached_dir, cached_file_name)
                        item_id_with_ext = item_id
                    if cached_file_path:
                        img_data: bytes = response.content
                        with open(cached_file_path, 'wb') as handler:
                            handler.write(img_data)
                        serve_local = True
            except Exception as ex:
                msgproc.log(f"Could not save file [{cached_file_path}] due to [{type(ex)}] [{ex}]")
        # can we serve the local file?
        if serve_local:
            cached_image_url: str = __build_image_path_as_list(item_id_with_ext=item_id_with_ext)
            save_elapsed: float = time.time() - save_start
            if verbose:
                msgproc.log(f"__build_cover_art_url serving cached [{cached_image_url}] instead of "
                            f"[{cover_art_url}] in [{save_elapsed:.3f}]")
            return cached_image_url
    else:
        return cover_art_url


def __build_image_path_as_list(item_id_with_ext: str) -> list[str]:
    path: list[str] = list()
    path.extend(config.get_webserver_path_images_cache())
    path.append(item_id_with_ext)
    return compose_docroot_url(os.path.join(*path))


def __match_images_only(match_list: list[str]) -> list[str]:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    result: list[str] = []
    for m in match_list if match_list else []:
        if match_supported_image_type_by_name(m):
            if verbose:
                msgproc.log(f"__match_images_only matching image success for [{m}]")
            result.append(m)
        else:
            if verbose:
                msgproc.log(f"__match_images_only matching image failed for [{m}]")
    return result


def get_album_disc_numbers(album: Album) -> list[int]:
    disc_list: list[int] = []
    song: Song
    for song in album.getSongs():
        dn: int = song.getDiscNumber()
        if dn and dn not in disc_list:
            disc_list.append(dn)
    return disc_list


def get_song_duration_display(song: Song) -> str:
    return upmpdmeta.get_duration_display_from_sec(duration_sec=song.getDuration())


def get_album_duration_display(album: Album) -> str:
    return upmpdmeta.get_duration_display_from_sec(duration_sec=album.getDuration())


def get_album_disc_and_track_counters(album: Album) -> str:
    disc_title_list: list[dict[str, any]] = album.getItem().getByName(
        constants.ItemKey.DISC_TITLES.value,
        [])
    disc_count: int = len(disc_title_list) if len(disc_title_list) > 1 else 1
    result: str = f"{disc_count} Disc{'s' if disc_count > 1 else ''}, "
    result += f"{album.getSongCount()} Track{'s' if album.getSongCount() > 1 else ''}"
    return result


def get_songs_by_album_disc_numbers(album: Album) -> dict[int, list[Song]]:
    res: dict[int, list[Song]] = {}
    song: Song
    for song in album.getSongs():
        dn: int = song.getDiscNumber()
        lst: list[Song] = res[dn] if dn in res else None
        if not lst:
            # build and add to dict
            lst = []
            res[dn] = lst
        # append.
        lst.append(song)
    return res


def _get_name_list(song: Song, item_key: constants.ItemKey.SONG_ALBUM_ARTISTS) -> list[str]:
    result: list[str] = []
    rl: list[dict[str, str]] = song.getItem().getListByName(item_key.value) if song else None
    current: dict[str, str]
    for current in rl:
        if constants.DictKey.NAME.value in current:
            result.append(current[constants.DictKey.NAME.value])
    return result


def get_song_album_artists(song: Song) -> list[str]:
    return _get_name_list(song=song, item_key=constants.ItemKey.SONG_ALBUM_ARTISTS)


def get_song_artists(song: Song) -> list[str]:
    return _get_name_list(song=song, item_key=constants.ItemKey.SONG_ARTISTS)


def set_artist_metadata_by_artist_id(artist_id: str, target: dict):
    upnp_util.set_upmpd_meta(
        upmpdmeta.UpMpdMeta.ARTIST_ID,
        artist_id,
        target)
    artist_metadata: persistence.ArtistMetadata = persistence.get_artist_metadata(artist_id=artist_id)
    if artist_metadata:
        upnp_util.set_upnp_meta(
            constants.UpnpMeta.ARTIST,
            artist_metadata.artist_name,
            target)
        upnp_util.set_upmpd_meta(
            upmpdmeta.UpMpdMeta.ARTIST_MUSICBRAINZ_ID,
            artist_metadata.artist_musicbrainz_id,
            target)
        upnp_util.set_upmpd_meta(
            upmpdmeta.UpMpdMeta.ARTIST_ALBUM_COUNT,
            (str(artist_metadata.artist_album_count)
                if artist_metadata.artist_album_count
                else None),
            target)
        upnp_util.set_upmpd_meta(
            upmpdmeta.UpMpdMeta.ARTIST_MEDIA_TYPE,
            name_key_to_display(artist_metadata.artist_media_type),
            target)

    # genres?
    genres_kv: KeyValueItem = persistence.get_kv_item(
        partition=cache_type.CacheType.GENRES_FOR_ARTIST.value.cache_name,
        key=artist_id)
    if genres_kv and genres_kv.value:
        # prepare for display
        genre_list: list[str] = genres_kv.value.split(constants.Separator.GENRE_FOR_ARTIST_SEPARATOR.value)
        genre_list.sort()
        genres_display_value: str = join_with_comma(genre_list)
        upnp_util.set_upnp_meta(
            metadata_name=constants.UpnpMeta.GENRE,
            metadata_value=genres_display_value,
            target=target)


def name_key_to_display(name_key: str) -> str:
    if not name_key:
        return None
    name_translator: constants.NameTranslator
    for name_translator in constants.NameTranslator:
        if name_translator.name_key == name_key:
            return name_translator.display_name
    # no match.
    return name_key.capitalize()


def set_artist_metadata(artist: Artist, target: dict):
    upnp_util.set_upnp_meta(
        constants.UpnpMeta.ARTIST,
        artist.getName(),
        target)
    upnp_util.set_upmpd_meta(
        upmpdmeta.UpMpdMeta.ARTIST_ID,
        artist.getId(),
        target)
    upnp_util.set_upmpd_meta(
        upmpdmeta.UpMpdMeta.ARTIST_MUSICBRAINZ_ID,
        get_artist_musicbrainz_id(artist),
        target)
    upnp_util.set_upmpd_meta(
        upmpdmeta.UpMpdMeta.ARTIST_ALBUM_COUNT,
        str(artist.getAlbumCount()),
        target)
    upnp_util.set_upmpd_meta(
        upmpdmeta.UpMpdMeta.ARTIST_MEDIA_TYPE,
        name_key_to_display(get_artist_media_type(artist)),
        target)
    artist_roles: list[str] = get_artist_roles(artist=artist)
    artist_roles = list(map(name_key_to_display, artist_roles))
    upnp_util.set_upmpd_meta(
        upmpdmeta.UpMpdMeta.ARTIST_ROLE,
        join_with_comma(artist_roles),
        target)


def join_with_comma(str_list: list[str]) -> str:
    return ", ".join(str_list if str_list else [])


def set_song_metadata(song: Song, target: dict):
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_ARTIST, join_with_comma(get_song_album_artists(song)), target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_TITLE, song.getAlbum(), target)
    joined_genres: str = join_with_comma(song.getGenres())
    upnp_util.set_upnp_meta(constants.UpnpMeta.GENRE, joined_genres, target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.TRACK_DURATION, get_song_duration_display(song), target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.DISC_NUMBER, song.getDiscNumber(), target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.TRACK_NUMBER, song.getTrack(), target)
    # album quality if available
    album_id: str = song.getAlbumId()
    album_metadata: persistence.AlbumMetadata = persistence.get_album_metadata(album_id=album_id)
    if album_metadata:
        upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_QUALITY, album_metadata.quality_badge, target)
    # single track quality badge
    track_quality_bade: str = get_track_list_badge([song])
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.TRACK_QUALITY, track_quality_bade, target)


def set_album_metadata(album: Album, target: dict):
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_ARTIST, album.getArtist(), target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_TITLE, album.getTitle(), target)
    # year
    album_year: str = str(album.getYear()) if album.getYear() else None
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_YEAR, album_year, target)
    # release date
    upnp_util.set_upmpd_meta(
        metadata_name=upmpdmeta.UpMpdMeta.ALBUM_RELEASE_DATE,
        metadata_value=album_util.get_album_release_date(album=album),
        target=target)
    # original release date
    upnp_util.set_upmpd_meta(
        metadata_name=upmpdmeta.UpMpdMeta.ALBUM_ORIGINAL_RELEASE_DATE,
        metadata_value=album_util.get_album_original_release_date(album=album),
        target=target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_VERSION, get_album_version(album), target)
    joined_genres: str = join_with_comma(album.getGenres())
    upnp_util.set_upnp_meta(constants.UpnpMeta.GENRE, joined_genres, target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_ID, album.getId(), target)
    record_label_names: str = join_with_comma(get_album_record_label_names(album))
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_RECORD_LABELS, record_label_names, target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_MUSICBRAINZ_ID, get_album_musicbrainz_id(album), target)
    explicit_status: str = get_explicit_status_display_value(
        explicit_status=get_explicit_status(album),
        display_mode=constants.ExplicitDiplayMode.LONG)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_EXPLICIT_STATUS, explicit_status, target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_DURATION, get_album_duration_display(album), target)
    disc_track_counters: str = get_album_disc_and_track_counters(album)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_DISC_AND_TRACK_COUNTERS, disc_track_counters, target)
    is_compilation_bool: bool = album.getItem().getByName(constants.ItemKey.IS_COMPILATION.value, False)
    is_compilation: str = "yes" if is_compilation_bool else "no"
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.IS_COMPILATION, is_compilation, target)
    album_release_types: AlbumReleaseTypes = get_album_release_types(album)
    album_release_types_display: str = album_release_types.display_name if album_has_release_types else None
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.RELEASE_TYPES, album_release_types_display, target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_MEDIA_TYPE, name_key_to_display(get_album_media_type(album)), target)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.MOOD, join_with_comma(get_album_moods(album)), target)
    if config.get_config_param_as_bool(constants.ConfigParam.SHOW_META_ALBUM_PATH):
        # album path.
        path_list: str = album_util.get_album_path_list(album=album)
        if len(path_list) == 0:
            # album does not have the required information. Might be from an album list
            # we try and see if we have the cached information
            album_metadata: persistence.AlbumMetadata = persistence.get_album_metadata(album_id=album.getId())
            if album_metadata and album_metadata.album_path and len(album_metadata.album_path) > 0:
                path_list = album_metadata.album_path.split(persistence_constants.Separator.PATH.value)
        path_str: str = f"[{'], ['.join(path_list)}]" if len(path_list) > 0 else None
        # don't show more than ...
        if path_str and len(path_str) > constants.MetadataMaxLength.ALBUM_PATH.value:
            msgproc.log(f"set_album_metadata album_id: [{album.getId()}] Path: [{path_str}]")
            path_str = f"<Truncated path> [{path_str[0:constants.MetadataMaxLength.ALBUM_PATH.value]}"
        upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_PATH, path_str, target)
    track_detailed_qualities: str = get_tracks_detailed_quality(album)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_QUALITY_OF_TRACKS, track_detailed_qualities, target)


def get_tracks_detailed_quality(album: Album) -> str:
    song_list: list[Song] = album.getSongs()
    if not song_list or len(song_list) == 0:
        # is the value cached?
        kv_item: KeyValueItem = persistence.get_kv_item(
            partition=cache_type.CacheType.ALBUM_TRACK_QUALITIES.getName(),
            key=album.getId())
        return kv_item.value if kv_item else None
    # go on!
    q_dict: dict[str, int] = {}
    display_result: str = None
    lossy_count: int = 0
    lossless_count: int = 0
    lossy_key_count: int = 0
    lossless_key_count: int = 0
    song: Song
    for song in song_list:
        # get song quality badge
        song_is_lossy: bool = is_lossy(song.getSuffix(), song.getItem().getByName(constants.ItemKey.BIT_DEPTH.value))
        if song_is_lossy:
            lossy_count += 1
        else:
            lossless_count += 1
        song_quality_badge: str = get_track_list_badge([song])
        if song_quality_badge:
            # get current count, 0 if still not in dict
            count: int = q_dict[song_quality_badge] if song_quality_badge in q_dict else 0
            if count == 0:
                # keep track of new key for lossy or lossless
                if song_is_lossy:
                    lossy_key_count += 1
                else:
                    lossless_key_count += 1
            # store count
            q_dict[song_quality_badge] = count + 1
    if lossy_count > 0 and lossless_count > 0:
        # mixed, return a constant string
        display_result = mixed_lossless_lossy(
            lossless_count=lossless_count,
            lossy_count=lossy_count)
    # not too many lossy/lossless types allowed
    if lossy_key_count > 3 or lossless_key_count > 3:
        display_result = mixed_lossless_lossy(
            lossless_count=lossless_count,
            lossy_count=lossy_count)
    if not display_result:
        to_display: list[str] = []
        k: str
        v: int
        for k, v in q_dict.items():
            to_display.append(f"{k} ({v} {'songs' if v > 1 else 'song'})")
        display_result: str = join_with_comma(to_display)
    # cache the value
    persistence.save_kv_item(
        key_value_item=persistence.KeyValueItem(
            partition=cache_type.CacheType.ALBUM_TRACK_QUALITIES.getName(),
            key=album.getId(),
            value=display_result))
    return display_result


def mixed_lossless_lossy(lossless_count: int, lossy_count: int) -> str:
    if lossy_count == 0 and lossless_count == 0:
        return None
    if lossless_count == 0:
        return f"lossy ({lossy_count})"
    if lossy_count == 0:
        return f"lossless ({lossless_count})"
    return f"lossless ({lossless_count}), lossy ({lossy_count})"


def get_cached_image_subdir_list() -> list[str]:
    return [
        constants.PluginConstant.PLUGIN_NAME.value,
        constants.PluginConstant.CACHED_IMAGES_DIRECTORY.value]


def cached_images_exist(image_file_name: str) -> list[str]:
    document_root_dir: str = config.getWebServerDocumentRoot()
    if document_root_dir:
        sub_dir_list: list[str] = get_cached_image_subdir_list()
        image_dir: str = ensure_directory(base_dir=document_root_dir, sub_dir_list=sub_dir_list)
        cached_file_name_no_ext: str = f"{str(image_file_name)}"
        cached_files: list[str] = __match_images_only(glob.glob(f"{os.path.join(image_dir, cached_file_name_no_ext)}.*"))
        return cached_files if cached_files else []
    return []
