# Copyright (C) 2026 Giovanni Fulco
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


class _AlbumPropertyKeyData:

    def __init__(
            self,
            property_key: str = None,
            display_value: str = None,
            unique_value: bool = False,
            max_items: int = 100):
        self.__property_key: str = property_key
        self.__display_value: str = display_value
        self.__unique_value: bool = unique_value
        self.__max_items: int = max_items

    @property
    def property_key(self) -> str:
        return self.__property_key

    @property
    def display_value(self) -> str:
        return self.__display_value

    @property
    def unique_value(self) -> bool:
        return self.__unique_value

    @property
    def max_items(self) -> int:
        return self.__max_items


class AlbumPropertyKey(Enum):

    GENRE = _AlbumPropertyKeyData(display_value="Genre")
    MOOD = _AlbumPropertyKeyData(display_value="Mood")
    DECADE = _AlbumPropertyKeyData(display_value="Decade", unique_value=True)
    YEAR = _AlbumPropertyKeyData(display_value="Year", unique_value=True)
    ARTIST = _AlbumPropertyKeyData(display_value="Artist")
    CONTRIBUTOR = _AlbumPropertyKeyData(display_value="Contributor")
    ALL_ARTISTS = _AlbumPropertyKeyData(display_value="All Artists")
    RELEASE_TYPE = _AlbumPropertyKeyData(display_value="Release Type")
    LOSSLESS_STATUS = _AlbumPropertyKeyData(display_value="Compression Type", unique_value=True)
    QUALITY_BADGE = _AlbumPropertyKeyData(display_value="Quality Badge", unique_value=True)
    BIT_DEPTH = _AlbumPropertyKeyData(display_value="Bit Depth")
    SAMPLING_RATE = _AlbumPropertyKeyData(display_value="Sampling Rate")
    CHANNEL_COUNT = _AlbumPropertyKeyData(display_value="Channel Count")

    @property
    def property_key(self) -> str:
        return self.value.property_key if self.value.property_key else self.name.lower()

    @property
    def display_value(self) -> str:
        return self.value.display_value if self.value.display_value else self.name

    @property
    def unique_value(self) -> bool:
        return self.value.unique_value

    @property
    def max_items(self) -> int:
        return self.value.max_items


def get_album_property_key(property_key: str) -> AlbumPropertyKey:
    apk: AlbumPropertyKey
    for apk in AlbumPropertyKey:
        if property_key == apk.property_key:
            return apk
    # no match
    return None


class AlbumPropertyKeyValue:

    def __init__(
            self,
            key: str,
            value: str):
        self.__key: str = key
        self.__value: str = value

    @property
    def key(self) -> str:
        return self.__key

    @property
    def value(self) -> str:
        return self.__value
