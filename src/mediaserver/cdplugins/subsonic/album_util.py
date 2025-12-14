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

import os
import re
from enum import Enum
from functools import cmp_to_key
import copy
import time

from subsonic_connector.song import Song
from subsonic_connector.album import Album

from codec_delimiter_style import CodecDelimiterStyle
import constants
import config
import persistence_constants
from msgproc_provider import msgproc


__split_characters: list[str] = [' ', '-', '_']


def split_string(string, delimiters):
    pattern = r'|'.join(delimiters)
    return re.split(pattern, string)


class Starter(Enum):
    CD = 0
    DISC = 1
    DISCO = 2
    DISK = 3
    D = 4
    VOLUME = 5
    VOL = 6


def __is_int(value: str) -> bool:
    try:
        # converting to integer
        int(value)
        return True
    except ValueError:
        return False


def _ignorable(last_path: str) -> bool:
    # first case: start with a starter, then there is a number without a splitter
    for name, member in Starter.__members__.items():
        if last_path.upper().startswith(name):
            # is there a number after that?
            if len(last_path) > len(name):
                potential_discnumber: str = last_path[len(name)]
                if __is_int(potential_discnumber):
                    return True
    # second case: start with a starter, then there is a number after a splitter
    for name, member in Starter.__members__.items():
        if last_path.upper().startswith(name):
            splitted: list = split_string(last_path, __split_characters)
            if splitted is not None and len(splitted) >= 2:
                last: str = splitted[1]
                if __is_int(last):
                    return True
    return False


def get_last_path_element(path: str) -> str:
    return os.path.basename(os.path.normpath(path))


def get_dir_from_path(path: str) -> str:
    return os.path.dirname(path)


def get_album_base_path(path: str) -> str:
    last_path = os.path.basename(os.path.normpath(path))
    last_path_ignorable: bool = _ignorable(last_path)
    if last_path_ignorable:
        return os.path.split(path)[0]
    return path


class __Decorated_Song:

    def __init__(self, song: Song):
        self._song: Song = song
        self._disc: int = song.getDiscNumber() if song.getDiscNumber() else 0
        self._track: int = song.getTrack() if song.getTrack() else 0
        path: str = get_dir_from_path(song.getPath())
        last_path = os.path.basename(os.path.normpath(path))
        last_path_ignorable: bool = _ignorable(last_path)
        if last_path_ignorable:
            self._path: str = os.path.split(path)[0]
        else:
            self._path: str = path

    def getSong(self) -> Song: return self._song
    def getPath(self) -> str: return self._path
    def getDisc(self) -> int: return self._disc
    def getTrack(self) -> int: return self._track


def __compare_decorated_song(left: __Decorated_Song, right: __Decorated_Song) -> int:
    cmp: int
    left_album: str = left.getSong().getAlbum() if left.getSong().getAlbum() else ""
    right_album: str = right.getSong().getAlbum() if right.getSong().getAlbum() else ""
    cmp = -1 if left_album < right_album else 0 if left_album == right_album else 1
    if cmp == 0:
        cmp = -1 if left.getPath() < right.getPath() else 0 if left.getPath() == right.getPath() else 1
    if cmp == 0:
        cmp = -1 if left.getDisc() < right.getDisc() else 0 if left.getDisc() == right.getDisc() else 1
    if cmp == 0:
        cmp = -1 if left.getTrack() < right.getTrack() else 0 if left.getTrack() == right.getTrack() else 1
    return cmp


class MultiCodecAlbum(Enum):
    NO = 0
    YES = 1


class SortSongListResult:

    def __init__(
            self,
            codec_set_by_path: dict[str, set[str]],
            song_list: list[Song],
            multi_codec_album: MultiCodecAlbum):
        self._codec_set_by_path: dict[str, set[str]] = codec_set_by_path
        self._song_list: list[Song] = song_list
        self._multi_codec_album: MultiCodecAlbum = multi_codec_album

    def getCodecSetByPath(self) -> set[str]:
        return self._codec_set_by_path

    def getAlbumVersionCount(self) -> int:
        return len(self._codec_set_by_path.keys())

    def getSongList(self) -> list[Song]:
        return copy.deepcopy(self._song_list)

    def getMultiCodecAlbum(self) -> MultiCodecAlbum:
        return self._multi_codec_album


def get_album_release_date(album: Album) -> str:
    return _get_album_release_date(album=album, item_key=constants.ItemKey.RELEASE_DATE)


def get_album_original_release_date(album: Album) -> str:
    return _get_album_release_date(album=album, item_key=constants.ItemKey.ORIGINAL_RELEASE_DATE)


def _get_album_release_date(album: Album, item_key: constants.ItemKey) -> str:
    ord_dict: dict[str, any] = album.getItem().getByName(item_key.value)
    if ord_dict is None:
        return None
    # split and return
    y: int = ord_dict["year"] if "year" in ord_dict else None
    if y is None:
        return None
    m: int = ord_dict["month"] if "month" in ord_dict else None
    d: int = ord_dict["day"] if "day" in ord_dict else None
    if (m is None or d is None):
        return str(y)
    # ok to combine
    return f"{y:04}-{m:02}-{d:02}"


def _get_album_release_year(album: Album, item_key: constants.ItemKey) -> int:
    ord_dict: dict[str, any] = album.getItem().getByName(item_key.value)
    if ord_dict is None:
        return None
    # just return year.
    return ord_dict["year"] if "year" in ord_dict else None


def sort_song_list(song_list: list[Song]) -> SortSongListResult:
    dec_list: list[__Decorated_Song] = []
    codec_dict: dict[str, int] = {}
    multi_codec: MultiCodecAlbum = MultiCodecAlbum.NO
    codec_set_by_path: dict[str, set[str]] = {}
    for song in song_list:
        dec: __Decorated_Song = __Decorated_Song(song)
        dec_list.append(dec)
        if not dec.getPath() in codec_set_by_path:
            codec_set_by_path[dec.getPath()] = set()
        codec_per_path_set: set[str] = codec_set_by_path[dec.getPath()]
        if not song.getSuffix().lower() in codec_per_path_set:
            codec_per_path_set.add(song.getSuffix().lower())
        if not song.getSuffix().lower() in codec_dict:
            codec_dict[song.getSuffix().lower()] = 1
        else:
            codec_dict[song.getSuffix().lower()] = codec_dict[song.getSuffix().lower()] + 1
    multi_codec = MultiCodecAlbum.YES if len(codec_dict) > 1 else MultiCodecAlbum.NO
    dec_list.sort(key=cmp_to_key(__compare_decorated_song))
    result: list[Song] = []
    current: __Decorated_Song
    for current in dec_list:
        result.append(current.getSong())
    return SortSongListResult(
        codec_set_by_path=codec_set_by_path,
        song_list=result,
        multi_codec_album=multi_codec)


def get_album_path_list(album: Album) -> list[str]:
    song: Song
    path_set: set[str] = set()
    for song in album.getSongs():
        curr_dir: str = get_dir_from_path(song.getPath())
        if curr_dir not in path_set:
            path_set.add(curr_dir)
    return list(path_set)


def get_album_path_list_joined(album: Album) -> list[str]:
    # this will return None if the album does not have songs
    # so if the album comes from a album list, the result will always be None
    start: float = time.time()
    result: str = persistence_constants.Separator.PATH.value.join(get_album_path_list(album=album))
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"get_album_path_list_joined for album [{album.getId()}] "
                    f"song_count [{album.getSongCount()}] "
                    f"available_song_count [{len(album.getSongs())}] -> "
                    f"[{result}] in [{elapsed:.3f}]")
    return result


class AlbumTracks:

    def __init__(
            self,
            codec_set_by_path: dict[str, set[str]],
            album: Album,
            song_list: list[Song],
            art_uri: str,
            multi_codec_album: MultiCodecAlbum):
        self._codec_set_by_path: dict[str, set[str]] = codec_set_by_path
        self._album: Album = album
        self._song_list: list[Song] = song_list
        self._art_uri: str = art_uri
        self._multi_codec_album: MultiCodecAlbum = multi_codec_album

    def getCodecSetByPath(self) -> dict[str, set[str]]:
        return copy.deepcopy(self._codec_set_by_path)

    def getAlbumVersionCount(self) -> int:
        return len(self._codec_set_by_path.keys())

    def getAlbum(self) -> Album:
        return self._album

    def getSongList(self) -> list[Song]:
        return copy.deepcopy(self._song_list)

    def getArtUri(self) -> str:
        return self._art_uri

    def getMultiCodecAlbum(self) -> MultiCodecAlbum:
        return self._multi_codec_album


# maybe delete this
# def get_playlist_display_artist(playlist_entry_artist: str) -> str:
#     if not playlist_entry_artist or len(playlist_entry_artist) == 0:
#         return ""
#     artist_list: list[str] = playlist_entry_artist.split(";")
#     return ", ".join(artist_list)


def strip_substring(initial_str, pattern):
    result_str = initial_str
    match = re.search(pattern, initial_str)
    if match:
        start = match.start()
        end = match.end()
        left = initial_str[0:start] if start > 0 else ""
        right = initial_str[match.end():] if end < (len(initial_str) - 1) else ""
        result_str = left + right
    return result_str


def to_codec_pattern(codec: str, style: CodecDelimiterStyle):
    return f" \\{style.get_left()}{codec}\\{style.get_right()}"


def strip_codec_from_album(album_title: str, codecs: set[str]) -> str:
    stripped_title: str = album_title
    if len(codecs) == 1:
        # get first and only codec
        codecs_str: str = list(codecs)[0]
        style: CodecDelimiterStyle
        for style in CodecDelimiterStyle:
            codec_pattern: str = to_codec_pattern(
                codecs_str,
                CodecDelimiterStyle.ROUND)
            if not album_title.startswith(codec_pattern):
                stripped_title = strip_substring(album_title, codec_pattern)
    return stripped_title


def has_year(album: Album) -> bool:
    album_year: str = get_album_year_str(album)
    return album_year is not None and len(album_year) > 0


def get_album_year_str(album: Album) -> str:
    year: int = album.getYear()
    rd_year: int = _get_album_release_year(album=album, item_key=constants.ItemKey.RELEASE_DATE)
    ord_year: int = _get_album_release_year(album=album, item_key=constants.ItemKey.ORIGINAL_RELEASE_DATE)
    y_list: list[int] = []
    if year:
        y_list.append(year)
    if rd_year and rd_year not in y_list:
        y_list.append(rd_year)
    if ord_year and ord_year not in y_list:
        y_list.append(ord_year)
    y_list.sort()
    return "/".join(str(x) for x in y_list)


# Tests
a1d1: str = "Disc 1 - Studio Album"
a1d2: str = "Disc 2 Live Album"

if not _ignorable(a1d1):
    raise Exception(f"Ignorable not working properly, [{a1d1}] should be ignorable")
if not _ignorable(a1d2):
    raise Exception(f"Ignorable not working properly, [{a1d2}] should be ignorable")
