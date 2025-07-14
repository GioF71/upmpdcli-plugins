# Copyright (C) 2025 Giovanni Fulco
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


import subsonic_util


class TrackInfo:

    def __init__(self):
        self.__trackId: str = None
        self.__bitrate: int = None
        self.__bit_depth: int = None
        self.__sampling_rate: int = None
        self.__suffix: str = None

    @property
    def trackId(self) -> str:
        return self.__trackId

    @trackId.setter
    def trackId(self, value: str):
        self.__trackId = value

    @property
    def bitrate(self) -> int:
        return self.__bitrate

    @bitrate.setter
    def bitrate(self, value: int):
        self.__bitrate = value

    @property
    def bit_depth(self) -> int:
        return self.__bit_depth

    @bit_depth.setter
    def bit_depth(self, value: int):
        self.__bit_depth = value

    @property
    def sampling_rate(self) -> int:
        return self.__sampling_rate

    @sampling_rate.setter
    def sampling_rate(self, value: int):
        self.__sampling_rate = value

    @property
    def suffix(self) -> str:
        return self.__suffix

    @suffix.setter
    def suffix(self, value: int):
        self.__suffix = value

    def is_lossy(self):
        return subsonic_util.is_lossy(
            suffix=self.__suffix,
            bit_depth=self.__bit_depth)
