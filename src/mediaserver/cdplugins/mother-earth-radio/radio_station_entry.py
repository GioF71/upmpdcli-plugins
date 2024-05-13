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

class RadioStationEntry:

    def __init__(
            self,
            id : int,
            codec : str,
            url : str,
            title : str,
            mimetype : str,
            bit_depth : int,
            sampling_rate : int,
            channel_count : int):
        self._id : int = id
        self._title : str = title
        self._url : str = url
        self._codec : str = codec
        self._mimetype : str = mimetype
        self._bit_depth : int = bit_depth
        self._sampling_rate : int = sampling_rate
        self._channel_count : int = channel_count

    @property
    def id(self) -> int:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def url(self) -> str:
        return self._url
    
    @property
    def codec(self) -> str:
        return self._codec

    @property
    def mimetype(self) -> str:
        return self._mimetype

    @property
    def bit_depth(self) -> int:
        return self._bit_depth

    @property
    def sampling_rate(self) -> int:
        return self._sampling_rate

    @property
    def channel_count(self) -> int:
        return self._channel_count
