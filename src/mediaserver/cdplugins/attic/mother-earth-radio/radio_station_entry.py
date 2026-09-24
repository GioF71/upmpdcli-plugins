# Copyright (C) 2023,2024,2025,2026 Giovanni Fulco
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


class RadioStationEntry:

    def __init__(
            self,
            codec: str,
            url: str,
            title: str,
            mimetype: str,
            bit_depth: int,
            sampling_rate: int,
            channel_count: int = 2):
        self.__title: str = title
        self.__url: str = url
        self.__codec: str = codec
        self.__mimetype: str = mimetype
        self.__bit_depth: int = bit_depth
        self.__sampling_rate: int = sampling_rate
        self.__channel_count: int = channel_count

    @property
    def title(self) -> str:
        return self.__title

    @property
    def url(self) -> str:
        return self.__url
    
    @property
    def codec(self) -> str:
        return self.__codec

    @property
    def mimetype(self) -> str:
        return self.__mimetype

    @property
    def bit_depth(self) -> int:
        return self.__bit_depth

    @property
    def sampling_rate(self) -> int:
        return self.__sampling_rate

    @property
    def channel_count(self) -> int:
        return self.__channel_count
