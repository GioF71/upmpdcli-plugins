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
from typing import Callable
import copy


class KeySortType(Enum):
    KEY_SORT_TYPE_NONE = 0
    KEY_SORT_TYPE_STRING = 1
    KEY_SORT_TYPE_INTEGER = 2


class _KeySortModeData:

    def __init__(self, sort_type: KeySortType, reverse: bool):
        self.__sort_type: KeySortType = sort_type
        self.__reverse: bool = reverse
    
    @property
    def sort_type(self) -> KeySortType:
        return self.__sort_type

    @property
    def reverse(self) -> bool:
        return self.__reverse


class KeySortMode(Enum):

    SORT_NONE = _KeySortModeData(sort_type=KeySortType.KEY_SORT_TYPE_NONE, reverse=False)
    SORT_DEFAULT = _KeySortModeData(sort_type=KeySortType.KEY_SORT_TYPE_STRING, reverse=False)
    SORT_REVERSE = _KeySortModeData(sort_type=KeySortType.KEY_SORT_TYPE_STRING, reverse=True)
    SORT_INTEGER = _KeySortModeData(sort_type=KeySortType.KEY_SORT_TYPE_INTEGER, reverse=False)
    SORT_INTEGER_REVERSE = _KeySortModeData(sort_type=KeySortType.KEY_SORT_TYPE_INTEGER, reverse=True)

    @property
    def data(self) -> _KeySortModeData:
        return self.value


class _AlbumPropertyKeyData:

    def __init__(
            self,
            property_key: str = None,
            display_value: str = None,
            unique_value: bool = False,
            max_items: int = 100,
            key_value_formatter: Callable[[str], str] = None,
            key_sort_mode: KeySortMode = KeySortMode.SORT_NONE):
        self.__property_key: str = property_key
        self.__display_value: str = display_value
        self.__unique_value: bool = unique_value
        self.__max_items: int = max_items
        self.__key_value_formatter: Callable[[str], str] = key_value_formatter
        self.__key_sort_mode: KeySortMode = key_sort_mode

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

    @property
    def key_value_formatter(self) -> Callable[[str], str]:
        return self.__key_value_formatter

    @property
    def key_sort_mode(self) -> KeySortMode:
        return self.__key_sort_mode


class _BitDepthPropertyKeyHelper:

    def __init__(self):
        self.__d: dict[str, str] = {
            "0": "Lossy",
            "1": "DSD",
            "16": "16 bit",
            "24": "24 bit",
            "32": "32 bit"
        }

    def format_value(self, v: str) -> str:
        if not v:
            return None
        return self.__d[v] if v in self.__d else ""


def _bit_depth_formatter(v: str) -> str:
    return _BitDepthPropertyKeyHelper().format_value(v)


def _sampling_rate_formatter(v: str) -> str:
    # Convert input to float (handles strings and numbers)
    try:
        hz = float(v)
    except (ValueError, TypeError):
        return "Invalid Input"

    if hz >= 1_000_000:
        # Convert to MHz
        return f"{hz / 1_000_000:g}MHz"
    elif hz >= 1_000:
        # Convert to kHz
        return f"{hz / 1_000:g}kHz"
    else:
        # Keep as Hz
        return f"{hz:g}Hz"


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


class AlbumPropertyKey(Enum):

    GENRE = _AlbumPropertyKeyData(display_value="Genre")
    MOOD = _AlbumPropertyKeyData(display_value="Mood")
    LABEL_INITIAL = _AlbumPropertyKeyData(display_value="Label (Initial)")
    LABEL = _AlbumPropertyKeyData(display_value="Label")
    DECADE = _AlbumPropertyKeyData(display_value="Decade", unique_value=True)
    YEAR = _AlbumPropertyKeyData(display_value="Year", unique_value=True)
    ALBUM_ARTIST = _AlbumPropertyKeyData(display_value="Album Artist")
    ARTIST = _AlbumPropertyKeyData(display_value="Artist")
    ARTIST_CONTRIBUTOR = _AlbumPropertyKeyData(display_value="Artist/Contributor")
    CONTRIBUTOR = _AlbumPropertyKeyData(display_value="Contributor")
    RELEASE_TYPE = _AlbumPropertyKeyData(display_value="Release Type")
    SUFFIX = _AlbumPropertyKeyData(display_value="Suffix")
    LOSSLESS_STATUS = _AlbumPropertyKeyData(display_value="Compression Type", unique_value=True)
    RESOLUTION_STATUS = _AlbumPropertyKeyData(display_value="Resolution")
    QUALITY_BADGE = _AlbumPropertyKeyData(display_value="Quality Badge", unique_value=True)
    BIT_DEPTH = _AlbumPropertyKeyData(
        display_value="Bit Depth",
        key_value_formatter=_bit_depth_formatter,
        key_sort_mode=KeySortMode.SORT_INTEGER_REVERSE)
    SAMPLING_RATE = _AlbumPropertyKeyData(
        display_value="Sampling Rate",
        key_value_formatter=_sampling_rate_formatter,
        key_sort_mode=KeySortMode.SORT_INTEGER_REVERSE)
    CHANNEL_COUNT = _AlbumPropertyKeyData(display_value="Channel Count")
    HAS_MUSICBRAINZ = _AlbumPropertyKeyData(display_value="MusicBrainz Album Id")
    HAS_COVER_ART = _AlbumPropertyKeyData(display_value="Cover Art")

    @property
    def property_key(self) -> str:
        return self.value.property_key if self.value.property_key else self.name.lower()

    @property
    def property_key_raw(self) -> str:
        v: str = self.value.property_key if self.value.property_key else self.name.lower()
        return v.lower().replace("_", "")

    @property
    def display_value(self) -> str:
        return self.value.display_value if self.value.display_value else self.name

    @property
    def unique_value(self) -> bool:
        return self.value.unique_value

    @property
    def max_items(self) -> int:
        return self.value.max_items
    
    @property
    def key_sort_mode(self) -> KeySortMode:
        return self.value.key_sort_mode

    def format_key_value(self, key_value: str) -> str:
        return key_value if self.value.key_value_formatter is None else self.value.key_value_formatter(key_value)

    def sort_key_values(self, value_occurrence_list: list[AlbumPropertyValueOccurrence]) -> list[AlbumPropertyValueOccurrence]:
        sort_mode: _KeySortModeData = self.key_sort_mode.data
        if KeySortType.KEY_SORT_TYPE_NONE == sort_mode.sort_type:
            # return as-is
            return value_occurrence_list
        v_occ_dict_by_value: dict[str, AlbumPropertyValueOccurrence] = {occ.property_value: occ for occ in value_occurrence_list}
        key_value_list: list[str] = [occ.property_value for occ in value_occurrence_list]
        # convert to list of int if needed
        values: list[any] = copy.deepcopy(
            key_value_list
            if sort_mode.sort_type == KeySortType.KEY_SORT_TYPE_STRING
            else [int(x) for x in key_value_list])
        # apply sorting
        values.sort(reverse=sort_mode.reverse)
        # return [str(x) for x in values]
        return [v_occ_dict_by_value[str(x)] for x in values]


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
