# Copyright (C) 2023,2024 Giovanni Fulco
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
import config

import cmdtalkplugin

import secrets
import constants

import copy
import os

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


def try_get_album(album_id: str) -> Album:
    try:
        album_res: Response[Album] = connector_provider.get().getAlbum(album_id)
        return album_res.getObj() if album_res and album_res.isOk() else None
    except Exception as e:
        msgproc.log(f"Cannot find Album by album_id [{album_id}] due to [{type(e)}] [{e}]")


def get_album_cover_art_by_album_id(album_id: str) -> str:
    album: Album = try_get_album(album_id)
    return album.getCoverArt() if album else None


def get_album_cover_art_url_by_album_id(album_id: str) -> str:
    return connector_provider.get().buildCoverArtUrl(get_album_cover_art_by_album_id(album_id))


def get_album_tracks(album_id: str) -> album_util.AlbumTracks:
    result: list[Song] = []
    connector: Connector = connector_provider.get()
    album: Album = try_get_album(album_id)
    if album and album.getArtist():
        cache_actions.on_album(album)
    albumArtURI: str = connector.buildCoverArtUrl(album.getCoverArt())
    song_list: list[Song] = album.getSongs()
    sort_song_list_result: album_util.SortSongListResult = album_util.sort_song_list(song_list)
    current_song: Song
    for current_song in sort_song_list_result.getSongList():
        result.append(current_song)
    albumArtURI: str = connector.buildCoverArtUrl(album.getCoverArt())
    return album_util.AlbumTracks(
        codec_set_by_path=sort_song_list_result.getCodecSetByPath(),
        album=album,
        song_list=result,
        art_uri=albumArtURI,
        multi_codec_album=sort_song_list_result.getMultiCodecAlbum())


def get_albums(
        query_type: str,
        size: int = config.items_per_page,
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
            artist_list: list[str, str] = song.getItem().getListByName(constants.ItemKey.ARTISTS.value)
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


def release_type_to_album_list_label(release_type: str) -> str:
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


def get_explicit_status_display_value(explicit_status: str) -> str:
    for _, v in constants.ExplicitStatus.__members__.items():
        explicit_info: constants.ExplicitInfo = v.value
        if explicit_info.tag_value == explicit_status:
            return explicit_info.display_value
    return None


def append_explicit_if_needed(current_albumtitle: str, album: Album) -> str:
    explicit_status: str = get_explicit_status(album)
    if explicit_status is not None and len(explicit_status) > 0:
        msgproc.log(f"Explicit status is [{explicit_status}]")
        # find match ...
        display_value: str = get_explicit_status_display_value(explicit_status)
        explicit_expression = display_value if display_value else explicit_status
        return f"{current_albumtitle} [{explicit_expression}]"
    return current_albumtitle
