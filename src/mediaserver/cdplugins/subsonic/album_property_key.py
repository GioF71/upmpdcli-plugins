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
    LABEL_INITIAL = _AlbumPropertyKeyData(display_value="Label (Initial)")
    LABEL = _AlbumPropertyKeyData(display_value="Label")
    DECADE = _AlbumPropertyKeyData(display_value="Decade", unique_value=True)
    YEAR = _AlbumPropertyKeyData(display_value="Year", unique_value=True)
    ARTIST = _AlbumPropertyKeyData(display_value="Artist")
    ARTIST_CONTRIBUTOR = _AlbumPropertyKeyData(display_value="Artist/Contributor")
    CONTRIBUTOR = _AlbumPropertyKeyData(display_value="Contributor")
    RELEASE_TYPE = _AlbumPropertyKeyData(display_value="Release Type")
    LOSSLESS_STATUS = _AlbumPropertyKeyData(display_value="Compression Type", unique_value=True)
    QUALITY_BADGE = _AlbumPropertyKeyData(display_value="Quality Badge", unique_value=True)
    BIT_DEPTH = _AlbumPropertyKeyData(display_value="Bit Depth")
    SAMPLING_RATE = _AlbumPropertyKeyData(display_value="Sampling Rate")
    CHANNEL_COUNT = _AlbumPropertyKeyData(display_value="Channel Count")
    HAS_MUSICBRAINZ = _AlbumPropertyKeyData(display_value="MusicBrainz Album Id")

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


class AlbumPropertyKeyOccurrence:

    def __init__(
            self,
            property_key: str,
            property_value_count: int,
            is_missing_for_some: bool,
            representative_album_id: str):
        self.__property_key: str = property_key
        self.__property_value_count: int = property_value_count
        self.__is_missing_for_some: bool = is_missing_for_some
        self.__representative_album_id: str = representative_album_id

    @property
    def property_key(self) -> str:
        return self.__property_key

    @property
    def property_value_count(self) -> int:
        return self.__property_value_count

    @property
    def is_missing_for_some(self) -> bool:
        return self.__is_missing_for_some

    @property
    def representative_album_id(self) -> str:
        return self.__representative_album_id


def condition_list_contains_negative(condition_list: list[AlbumPropertyKeyValue], album_property_key: str) -> bool:
    curr: AlbumPropertyKeyValue
    for curr in condition_list if condition_list else []:
        if curr.key == album_property_key and curr.value is None:
            return True
    return False


def condition_list_positive_count(condition_list: list[AlbumPropertyKeyValue], album_property_key: str) -> int:
    cnt: int = 0
    curr: AlbumPropertyKeyValue
    for curr in condition_list if condition_list else []:
        if curr.key == album_property_key and curr.value is not None:
            cnt += 1
    return cnt


def condition_list_contains_positive(
        condition_list: list[AlbumPropertyKeyValue],
        album_property_key: str,
        album_property_value: str) -> bool:
    curr: AlbumPropertyKeyValue
    for curr in condition_list if condition_list else []:
        if curr.key == album_property_key and curr.value == album_property_value:
            return True
    return False


class AlbumPropertyValueOccurrence:

    def __init__(
            self,
            property_value: str,
            album_count: int,
            is_missing_for_some: bool,
            representative_album_id: str):
        self.__property_value: str = property_value
        self.__album_count: int = album_count
        self.__is_missing_for_some: bool = is_missing_for_some
        self.__representative_album_id: str = representative_album_id

    @property
    def property_value(self) -> str:
        return self.__property_value

    @property
    def album_count(self) -> int:
        return self.__album_count

    @property
    def is_missing_for_some(self) -> bool:
        return self.__is_missing_for_some

    @property
    def representative_album_id(self) -> str:
        return self.__representative_album_id
