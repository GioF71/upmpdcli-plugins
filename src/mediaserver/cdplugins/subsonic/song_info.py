# Copyright (C) 2025,2026 Giovanni Fulco
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


class SongInfo:

    def __init__(
            self,
            song_id: str,
            bitrate: int,
            bit_depth: int,
            sampling_rate: int,
            suffix: str,
            duration: int):
        self.__song_id: str = song_id
        self.__bit_depth: int = bit_depth
        self.__bitrate: int = bitrate
        self.__sampling_rate: int = sampling_rate
        self.__suffix: str = suffix
        self.__duration: int = duration

    @property
    def song_id(self) -> str:
        return self.__song_id

    @property
    def bitrate(self) -> int:
        return self.__bitrate

    @property
    def bit_depth(self) -> int:
        return self.__bit_depth

    @property
    def sampling_rate(self) -> int:
        return self.__sampling_rate

    @property
    def suffix(self) -> str:
        return self.__suffix

    @property
    def duration(self) -> int:
        return self.__duration
