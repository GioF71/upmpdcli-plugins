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

import os
from re import split
from enum import Enum
from functools import cmp_to_key
import copy

from subsonic_connector.song import Song
from subsonic_connector.album import Album

__split_characters : list[str] = [' ', '-', '_']

def split_string(string, delimiters):
  pattern = r'|'.join(delimiters)
  return split(pattern, string)

class Starter(Enum):
    
    CD = 0
    DISC = 1
    DISCO = 2

def __is_int(value : str) -> bool:
    try:
        # converting to integer
        int(value)
        return True
    except ValueError:
        return False


def _ignorable(last_path : str) -> bool:
    # first case: start with a starter, then there is a number without a splitter
    for name, member in Starter.__members__.items():
        if last_path.upper().startswith(name):
            # is there a number after that?
            if len(last_path) > len(name):
                potential_discnumber : str = last_path[len(name)]
                if __is_int(potential_discnumber): return True

    # second case: start with a starter, then there is a number after a splitter
    for name, member in Starter.__members__.items():
        if last_path.upper().startswith(name):
            splitted : list = split_string(last_path, __split_characters)
            if splitted is not None and len(splitted) == 2:
                last : str = splitted[1]
                if __is_int(last): return True

    return False

def get_last_path_element(path : str) -> str:
    return os.path.basename(os.path.normpath(path))
    
def get_dir_from_path(path : str ) -> str:
    return os.path.dirname(path)

def get_album_base_path(path : str) -> str:
    last_path = os.path.basename(os.path.normpath(path))
    last_path_ignorable : bool = _ignorable(last_path)
    if last_path_ignorable:
        return os.path.split(path)[0]
    return path

class __Decorated_Song:

    def __init__(self, song : Song):
        self._song = song
        self._disc : int = song.getDiscNumber() if song.getDiscNumber() else 0
        self._track : int = song.getTrack() if song.getTrack() else 0
        path : str = get_dir_from_path(song.getPath())
        last_path = os.path.basename(os.path.normpath(path))
        last_path_ignorable : bool = _ignorable(last_path)
        if last_path_ignorable:
            self._path = os.path.split(path)[0]
        else:
            self._path = path

    def getSong(self) -> Song: return self._song
    def getPath(self) -> str: return self._path
    def getDisc(self) -> int: return self._disc
    def getTrack(self) -> int: return self._track

def __compare_decorated_song(left : __Decorated_Song, right : __Decorated_Song) -> int:
    cmp : int
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
            codec_set_by_path : dict[str, set[str]],
            song_list : list[Song], 
            multi_codec_album : MultiCodecAlbum):
        self._codec_set_by_path : dict[str, set[str]] = codec_set_by_path
        self._song_list : list[Song] = song_list
        self._multi_codec_album : MultiCodecAlbum = multi_codec_album

    def getCodecSetByPath(self) -> set[str]:
        return self._codec_set_by_path

    def getAlbumVersionCount(self) -> int:
        return len(self._codec_set_by_path.keys())
    
    def getSongList(self) -> list[Song]:
        return copy.deepcopy(self._song_list)
    
    def getMultiCodecAlbum(self) -> MultiCodecAlbum:
        return self._multi_codec_album

def sort_song_list(song_list : list[Song]) -> SortSongListResult:
    dec_list : list[__Decorated_Song] = []
    codec_dict : dict[str, int] = {}
    multi_codec : MultiCodecAlbum = MultiCodecAlbum.NO
    codec_set_by_path : dict[str, set[str]] = {}
    for song in song_list:
        dec : __Decorated_Song = __Decorated_Song(song)
        dec_list.append(dec)
        if not dec.getPath() in codec_set_by_path:
            codec_set_by_path[dec.getPath()] = set()
        codec_per_path_set : set[str] = codec_set_by_path[dec.getPath()]
        if not song.getSuffix() in codec_per_path_set:
            codec_per_path_set.add(song.getSuffix())
        if not song.getSuffix() in codec_dict:
            codec_dict[song.getSuffix()] = 1
        else:
            codec_dict[song.getSuffix()] = codec_dict[song.getSuffix()] + 1
    multi_codec = MultiCodecAlbum.YES if len(codec_dict) > 1 else MultiCodecAlbum.NO
    dec_list.sort(key = cmp_to_key(__compare_decorated_song))
    result : list[song] = []
    current : __Decorated_Song
    for current in dec_list:
        result.append(current.getSong())
    return SortSongListResult(
        codec_set_by_path = codec_set_by_path,
        song_list = result, 
        multi_codec_album = multi_codec)
    
class AlbumTracks:

    def __init__(
            self, 
            codec_set_by_path : dict[str, set[str]],
            album : Album, 
            song_list : list[Song], 
            art_uri : str, 
            multi_codec_album : MultiCodecAlbum):
        self._codec_set_by_path : dict[str, set[str]] = codec_set_by_path
        self._album : Album = album
        self._song_list : list[Song] = song_list
        self._art_uri : str = art_uri
        self._multi_codec_album : MultiCodecAlbum = multi_codec_album

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
