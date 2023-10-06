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

    def __init__(self, id : int, codec : str, url : str, title : str, mimetype : str):
        self._id : int = id
        self._title : str = title
        self._url : str = url
        self._codec : str = codec
        self._mimetype : str = mimetype

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
