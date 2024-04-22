# Copyright (C) 2024 Giovanni Fulco
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

from enum import Enum


class ContextKey(Enum):
    CANNOT_GET_STREAM_INFO = 0, "cannot-get-stream-info", False
    SUCCESS_COUNT = 1, "success-count", 0
    PROCESS_COUNT = 2, "process-count", 0
    PLAYED_ALBUM_TRACKS_DICT = 3, "played-albums-tracks-dict", dict()
    KNOWN_TRACKS_COUNT = 4, "known-tracks-count", 0
    GUESSED_TRACKS_COUNT = 5, "guessed-tracks-count", 0
    IS_ALBUM = 6, "is-album", False
    ALBUM_FIRST_TRACK_BIT_DEPTH = 7, "album-first-track-bit-depth", None
    ALBUM_FIRST_TRACK_SAMPLE_RATE = 8, "album-first-track-sample-rate", None
    ALBUM_FIRST_TRACK_AUDIO_QUALITY = 9, "album-first-track-audio-quality", None
    ASSUMED_FROM_FIRST_ALBUM_TRACK_COUNT = 10, "assumed_from_first_album_track_count", 0
    GET_STREAM_COUNT = 11, "get-stream-count", 0
    IS_PLAYLIST = 12, "is-playlist", False
    IS_MIX = 13, "is-mix", False
    ASSUMED_BY_MAX_AUDIO_QUALITY_COUNT = 14, "assumed-by-max-audio-quality-count", 0
    KNOWN_TRACK_DICT = 15, "known-track-dict", None
    ASSUMED_FROM_FIRST_ALBUM_TRACK_DICT = 16, "assumed-from-first-album-track-dict", None
    GET_STREAM_DICT = 17, "get-stream-dict", None
    GUESSED_TRACK_DICT = 18, "guessed-track-dict", None

    def __init__(self,
            num : int,
            key_name : str,
            default_value : any):
        self.__num : int = num
        self.__key_name : str = key_name
        self.__default_value : any = default_value

    @property
    def name(self) -> str:
        return self.__key_name

    @property
    def default_value(self) -> any:
        return self.__default_value


# duplicate check
name_checker_set : set[str] = set()
id_checker_set : set[int] = set()
for v in ContextKey:
    if v.name in name_checker_set:
        raise Exception(f"Duplicated name [{v.name}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.name)
    id_checker_set.add(v.value[0])
