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
import persistence
import persistence_constants

import cmdtalkplugin

import secrets
import constants
import requests
import mimetypes
import glob

import copy
import os

from functools import cmp_to_key
from typing import Callable


# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


class ArtistIdAndName:

    def __init__(self, id: str, name: str):
        self.__id: str = id
        self.__name: str = name

    @property
    def id(self) -> str:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name


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


def try_get_album(album_id: str, propagate_fail: bool = False) -> Album:
    try:
        res: Response[Album] = connector_provider.get().getAlbum(album_id)
        return res.getObj() if res and res.isOk() else None
    except Exception as e:
        msgproc.log(f"Cannot find Album by album_id [{album_id}] due to [{type(e)}] [{e}]")
        if propagate_fail:
            raise e


def try_get_artist(artist_id: str) -> Artist:
    try:
        res: Response[Artist] = connector_provider.get().getArtist(artist_id)
        return res.getObj() if res and res.isOk() else None
    except Exception as e:
        msgproc.log(f"Cannot find Artist by artist_id [{artist_id}] due to [{type(e)}] [{e}]")


def get_album_cover_art_by_album(album: Album) -> str:
    return album.getCoverArt() if album else None


def get_album_cover_art_by_album_id(album_id: str) -> str:
    album: Album = try_get_album(album_id)
    return get_album_cover_art_by_album(album)


def get_album_cover_art_url_by_album(album: Album) -> str:
    return build_cover_art_url(get_album_cover_art_by_album(album))


def get_album_cover_art_url_by_album_id(album_id: str) -> str:
    return build_cover_art_url(get_album_cover_art_by_album_id(album_id))


def get_album_tracks(album_id: str) -> tuple[Album, album_util.AlbumTracks]:
    result: list[Song] = []
    album: Album = try_get_album(album_id)
    if album and album.getArtist():
        cache_actions.on_album(album)
    else:
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
            if artist_id not in artist_id_set:
                artist_set.add(ArtistIdAndName(id=artist_id, name=album.getArtist()))
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

    __id: str = None
    __name: str = None

    def __init__(self, id: str, name: str):
        self.__id = id
        self.__name = name

    @property
    def id(self) -> str:
        return self.__id

    @property
    def name(self) -> str:
        return self.__name


def get_album_artists_from_album(album: Album) -> list[dict[str, str]]:
    return album.getItem().getListByName(constants.ItemKey.ARTISTS.value)


def get_artists_in_album(album: Album, in_songs: bool = True) -> list[ArtistsOccurrence]:
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
        if "name" in current and "id" in current and not current["id"] in artist_id_set:
            occ_list.append(ArtistsOccurrence(id=current["id"], name=current["name"]))
            artist_id_set.add(current["id"])
    song_list: list[Song] = album.getSongs() if in_songs else list()
    if song_list:
        song: Song
        for song in song_list:
            song_artist_list: list[dict[str, str]] = list()
            album_artist_list: list[str, str] = song.getItem().getListByName(constants.ItemKey.ALBUM_ARTISTS.value)
            artist_list: list[dict[str, str]] = song.getItem().getListByName(constants.ItemKey.ARTISTS.value)
            if album_artist_list:
                song_artist_list.extend(album_artist_list)
            if artist_list:
                song_artist_list.extend(artist_list)
            song_dict: dict[str, str]
            for song_dict in song_artist_list:
                if "name" in song_dict and "id" in song_dict and not song_dict["id"] in artist_id_set:
                    occ_list.append(ArtistsOccurrence(id=song_dict["id"], name=song_dict["name"]))
                    artist_id_set.add(song_dict["id"])
    return occ_list


def filter_out_artist_id(artist_list: list[ArtistsOccurrence], artist_id: str) -> list[ArtistsOccurrence]:
    result: list[ArtistsOccurrence] = []
    occ: ArtistsOccurrence
    for occ in artist_list:
        if not occ.id == artist_id:
            result.append(occ)
    return result


def get_album_date_for_sorting(album: Album) -> str:
    result: str = album_util.getOriginalReleaseDate(album)
    if not result:
        # fallback to date.
        y: int = album.getYear()
        if y and isinstance(y, int):
            # assume january 1st
            result = f"{y:04}-01-01"
    return result if result else "0000-01-01"


def ensure_directory(base_dir: str, sub_dir_list: list[str]) -> str:
    curr_sub_dir: str
    curr_dir: str = base_dir
    for curr_sub_dir in sub_dir_list:
        new_dir: str = os.path.join(curr_dir, curr_sub_dir)
        # msgproc.log(f"checking dir [{new_dir}] ...")
        if not os.path.exists(new_dir):
            msgproc.log(f"creating dir [{new_dir}] ...")
            os.mkdir(new_dir)
        # else:
        #     msgproc.log(f"dir [{new_dir}] already exists.")
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
        # artist is different from artist id
        different: bool = current.getArtistId() and artist_id != current.getArtistId()
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
        return "/".join(x.title() for x in self.__types)

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
    result: list[str] = list()
    has_release_types: bool = album_has_release_types(album)
    album_release_types: list[str] = (album.getItem().getByName(constants.ItemKey.RELEASE_TYPES.value)
                                      if has_release_types
                                      else list())
    if album_release_types and len(album_release_types) > 0:
        release_type: str
        for release_type in album_release_types:
            # split by "/"
            rt_splitted: list[str] = release_type.split("/")
            if rt_splitted and len(rt_splitted) > 1:
                msgproc.log(f"release type for album_id [{album.getId()}] "
                            f"is [{release_type}] -> [{rt_splitted}]")
            for rt in rt_splitted:
                if rt not in result:
                    result.append(rt)
    else:
        # if release_types is empty we default to album
        result = ["album"]
    return AlbumReleaseTypes(result)


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
    # msgproc.log(f"append_something_to_album_title EntryType [{album_entry_type}] "
    #             f"SearchResult [{is_search_result}] -> "
    #             f"do_append [{do_append}]")
    if do_append:
        # msgproc.log(f"append_something_to_album_title appending [{something}] to [{album_title}] ...")
        album_title = f"{album_title} [{something}]"
    # else:
        # msgproc.log(f"append_something_to_album_title NOT appending [{something}] to [{album_title}]!")
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
    return artist.getItem().getByName(constants.ItemKey.COVER_ART.value) if artist else None


def get_album_version(album: Album) -> str | None:
    return album.getItem().getByName(constants.ItemKey.VERSION.value) if album else None


def get_album_mediatype(album: Album) -> str | None:
    return album.getItem().getByName(constants.ItemKey.MEDIA_TYPE.value) if album else None


def get_artist_mediatype(artist: Artist) -> str | None:
    return artist.getItem().getByName(constants.ItemKey.MEDIA_TYPE.value) if artist else None


def get_album_record_label_names(album: Album) -> list[str]:
    result: list[str] = []
    rl: list[dict[str, str]] = album.getItem().getListByName(constants.ItemKey.ALBUM_RECORD_LABELS.value) if album else None
    current: dict[str, str]
    for current in rl:
        if "name" in current:
            result.append(current["name"])
    return result


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
    # msgproc.log(f"compose_docroot_url with doc_root_base_url: [{doc_root_base_url}] right: [{right}]")
    return f"{doc_root_base_url}/{right}" if doc_root_base_url else None


def build_cover_art_url(item_id: str, force_save: bool = False) -> str:
    if not item_id:
        # msgproc.log("build_cover_art_url got empty item_id")
        return None
    cover_art_url: str = connector_provider.get().buildCoverArtUrl(item_id=item_id)
    if not cover_art_url:
        # msgproc.log(f"build_cover_art_url cannot build coverArtUrl for item_id [{item_id}]")
        return None
    if (config.getWebServerDocumentRoot() and
            config.get_config_param_as_bool(constants.ConfigParam.ENABLE_IMAGE_CACHING)):
        images_cached_dir: str = ensure_directory(
            config.getWebServerDocumentRoot(),
            config.get_webserver_path_images_cache())
        # msgproc.log(f"images_cached_dir=[{images_cached_dir}] item_id=[{item_id}]")
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
            matching_files = glob.glob(f"{cached_file_path}.*")
            # msgproc.log(f"Files matching_files [{item_id}] -> [{matching_files if matching_files else None}]")
            if matching_files and len(matching_files) > 0:
                item_id_with_ext = os.path.basename(matching_files[0])
                # msgproc.log(f"item_id_with_ext = [{item_id_with_ext}]")
                # remove other matching_files files ...
                to_remove: str
                for to_remove in matching_files[1:]:
                    msgproc.log(f"build_cover_art_url Removing spurious file [{to_remove}] ...")
                    os.remove(to_remove)
                exists = True
        else:
            exists = os.path.exists(cached_file_path)
            if exists:
                matching_files = [cached_file_path]
        serve_local: bool = False
        if exists and not force_save:
            # file exists or force_save not set
            # msgproc.log(f"Cached file for [{item_id}] exists [{exists}] force_save [{force_save}]")
            serve_local = True
        else:
            # file does not exist or must be saved
            # msgproc.log(f"Saving file for [{item_id}] [{cached_file_path}] "
            #             f"exists [{exists}] force_save [{force_save}] ...")
            if exists and force_save:
                # msgproc.log(f"force_save [{force_save}] -> Removing [{len(matching_files)}] files ...")
                # remove matching_files
                to_remove: str
                for to_remove in matching_files:
                    # msgproc.log(f"force_save [{force_save}] -> Removing file [{to_remove}] ...")
                    try:
                        os.remove(to_remove)
                    except Exception as ex:
                        msgproc.log(f"Failed to remove [{to_remove}] due to [{type(ex)}] [{ex}]")
            try:
                response = requests.get(cover_art_url)
                content_type = response.headers.get('content-type')
                file_type: str = mimetypes.guess_all_extensions(content_type)
                item_id_ext: str = os.path.splitext(cached_file_path)[1]
                # msgproc.log(f"content_type [{content_type}] file_type [{file_type}] extension [{item_id_ext}]")
                # is cached_file_path without extension?
                if item_id_ext is None or len(item_id_ext) == 0:
                    if file_type and len(file_type) > 0:
                        cached_file_name = cached_file_name + file_type[0]
                        item_id_with_ext = cached_file_name
                        # msgproc.log(f"cached_file_name with extension added: [{cached_file_name}]")
                        cached_file_path: str = os.path.join(images_cached_dir, cached_file_name)
                        # msgproc.log(f"cached_file_path: [{cached_file_path}]")
                    else:
                        # we cannot save!
                        cached_file_path = None
                else:
                    cached_file_path: str = os.path.join(images_cached_dir, cached_file_name)
                    item_id_with_ext = item_id
                # msgproc.log(f"About to save file for [{item_id}] -> [{cached_file_path}] ...")
                if cached_file_path:
                    img_data: bytes = response.content
                    with open(cached_file_path, 'wb') as handler:
                        handler.write(img_data)
                    serve_local = True
            except Exception as ex:
                msgproc.log(f"Could not save file [{cached_file_path}] due to [{type(ex)}] [{ex}]")
        # can we serve the local file?
        if serve_local:
            path: list[str] = list()
            path.extend(config.get_webserver_path_images_cache())
            path.append(item_id_with_ext)
            cached_image_url: str = compose_docroot_url(os.path.join(*path))
            # msgproc.log(f"For item_id [{item_id}] cached -> [{cached_image_url}]")
            return cached_image_url
    else:
        return cover_art_url


def get_album_duration_display(album: Album) -> str:
    duration_sec: int = album.getDuration()
    # hours, minutes, seconds
    remaining_sec: int = duration_sec
    seconds: int = duration_sec % 60
    remaining_sec -= seconds
    minutes: int = int(int(remaining_sec / 60) % 60)
    remaining_sec -= (minutes * 60)
    hours: int = int(remaining_sec / 3600)
    result: str = ""
    # format it!
    if hours > 0:
        result += f"{hours}h"
    if minutes > 0:
        if len(result) > 0:
            result += " "
        result += f"{minutes:02d}m"
    # add seconds in any case
    if len(result) > 0:
        result += " "
    result += f"{seconds:02d}s"
    return result


def get_album_disc_and_track_counters(album: Album) -> str:
    disc_title_list: list[dict[str, any]] = album.getItem().getByName(
        constants.ItemKey.DISC_TITLES.value,
        [])
    disc_count: int = len(disc_title_list) if len(disc_title_list) > 1 else 1
    result: str = f"{disc_count} Disc{'s' if disc_count > 1 else ''}, "
    result += f"{album.getSongCount()} Track{'s' if album.getSongCount() > 1 else ''}"
    return result


def set_artist_metadata_by_artist_id(artist_id: str, target: dict):
    upnp_util.set_upmpd_meta(
        constants.UpMpdMeta.ARTIST_ID,
        artist_id,
        target)
    artist_metadata: persistence.ArtistMetadata = persistence.get_artist_metadata(artist_id=artist_id)
    # msgproc.log(f"Executing set_artist_metadata_by_artist_id for artist_id [{artist_id}] "
    #             f"Metadata available [{'yes' if artist_metadata else 'no'}]")
    if not artist_metadata:
        # nothing to do here
        return
    upnp_util.set_upnp_meta(
        constants.UpnpMeta.ARTIST,
        artist_metadata.artist_name,
        target)
    upnp_util.set_upmpd_meta(
        constants.UpMpdMeta.ARTIST_MUSICBRAINZ_ID,
        artist_metadata.artist_musicbrainz_id,
        target)
    upnp_util.set_upmpd_meta(
        constants.UpMpdMeta.ARTIST_ALBUM_COUNT,
        (str(artist_metadata.artist_album_count)
            if artist_metadata.artist_album_count
            else None),
        target)


def set_artist_metadata(artist: Artist, target: dict):
    upnp_util.set_upnp_meta(
        constants.UpnpMeta.ARTIST,
        artist.getName(),
        target)
    upnp_util.set_upmpd_meta(
        constants.UpMpdMeta.ARTIST_ID,
        artist.getId(),
        target)
    upnp_util.set_upmpd_meta(
        constants.UpMpdMeta.ARTIST_MUSICBRAINZ_ID,
        get_artist_musicbrainz_id(artist),
        target)
    upnp_util.set_upmpd_meta(
        constants.UpMpdMeta.ARTIST_ALBUM_COUNT,
        str(artist.getAlbumCount()),
        target)
    upnp_util.set_upmpd_meta(
        constants.UpMpdMeta.ARTIST_MEDIA_TYPE,
        get_artist_mediatype(artist),
        target)


def set_album_metadata(album: Album, target: dict):
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_ARTIST, album.getArtist(), target)
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_TITLE, album.getTitle(), target)
    album_year: str = str(album.getYear()) if album.getYear() else None
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_YEAR, album_year, target)
    original_release_date_int: int = album.getOriginalReleaseDate()
    original_reldate: str = str(original_release_date_int) if original_release_date_int else None
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_ORIGINAL_RELEASE_DATE, original_reldate, target)
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_VERSION, get_album_version(album), target)
    joined_genres: str = ", ".join(album.getGenres())
    upnp_util.set_upnp_meta(constants.UpnpMeta.GENRE, joined_genres, target)
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_ID, album.getId(), target)
    record_label_names: str = ", ".join(get_album_record_label_names(album))
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_RECORD_LABELS, record_label_names, target)
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_MUSICBRAINZ_ID, get_album_musicbrainz_id(album), target)
    explicit_status: str = get_explicit_status_display_value(
        explicit_status=get_explicit_status(album),
        display_mode=constants.ExplicitDiplayMode.LONG)
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_EXPLICIT_STATUS, explicit_status, target)
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_DURATION, get_album_duration_display(album), target)
    disc_track_counters: str = get_album_disc_and_track_counters(album)
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_DISC_AND_TRACK_COUNTERS, disc_track_counters, target)
    is_compilation_bool: bool = album.getItem().getByName(constants.ItemKey.IS_COMPILATION.value, False)
    is_compilation: str = "yes" if is_compilation_bool else "no"
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.IS_COMPILATION, is_compilation, target)
    album_release_types: AlbumReleaseTypes = get_album_release_types(album)
    album_release_types_display: str = album_release_types.display_name if album_has_release_types else None
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.RELEASE_TYPES, album_release_types_display, target)
    upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_MEDIA_TYPE, get_album_mediatype(album), target)
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
            path_str = f"<Truncated path> [{path_str[0:constants.MetadataMaxLength.ALBUM_PATH.value]}"
        upnp_util.set_upmpd_meta(constants.UpMpdMeta.ALBUM_PATH, path_str, target)
