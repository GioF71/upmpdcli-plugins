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


import copy
from collections.abc import Callable
from enum import Enum
from typing import Any, ClassVar

from audio_codec import LosslessStatus, ResolutionStatus


class KeySortType(Enum):
    KEY_SORT_TYPE_NONE = 0
    KEY_SORT_TYPE_STRING = 1
    KEY_SORT_TYPE_INTEGER = 2
    KEY_SORT_TYPE_OCCURRENCE = 3


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
    SORT_OCCURRENCE = _KeySortModeData(sort_type=KeySortType.KEY_SORT_TYPE_OCCURRENCE, reverse=False)
    SORT_OCCURRENCE_REVERSE = _KeySortModeData(sort_type=KeySortType.KEY_SORT_TYPE_OCCURRENCE, reverse=True)

    @property
    def data(self) -> _KeySortModeData:
        return self.value


class _AlbumPropertyKeyData:

    def __init__(
            self,
            property_key: str | None = None,
            display_value: str | None = None,
            max_items: int = 100,
            key_value_sort_mapper: Callable[[str], Any] | None = None,
            key_value_formatter: Callable[[str], str | None] | None = None,
            key_sort_mode: KeySortMode = KeySortMode.SORT_NONE):
        self.__property_key: str | None = property_key
        self.__display_value: str | None = display_value
        self.__max_items: int = max_items
        self.__key_value_sort_mapper: Callable[[str], Any] | None = key_value_sort_mapper
        self.__key_value_formatter: Callable[[str], str | None] | None = key_value_formatter
        self.__key_sort_mode: KeySortMode = key_sort_mode

    @property
    def property_key(self) -> str | None:
        return self.__property_key

    @property
    def display_value(self) -> str | None:
        return self.__display_value

    @property
    def max_items(self) -> int:
        return self.__max_items

    @property
    def key_value_sort_mapper(self) -> Callable[[str], str] | None:
        return self.__key_value_sort_mapper

    @property
    def key_value_formatter(self) -> Callable[[str], str] | None:
        return self.__key_value_formatter

    @property
    def key_sort_mode(self) -> KeySortMode:
        return self.__key_sort_mode


class _BitDepthPropertyKeyHelper:

    _d: ClassVar[dict[str, str]] = {
            "0": "Lossy",
            "1": "DSD",
            "4": "4 bit",
            "8": "8 bit",
            "16": "16 bit",
            "24": "24 bit",
            "32": "32 bit"}

    def format_value(v: str) -> str | None:
        if not v:
            return None
        return _BitDepthPropertyKeyHelper._d.get(v, "")


class _ChannelCountPropertyKeyHelper:

    _d: ClassVar[dict[str, str]] = {
            "1": "Mono",
            "2": "Stereo"}

    def format_value(v: str) -> str | None:
        if not v:
            return None
        return _ChannelCountPropertyKeyHelper._d.get(v, f"{v} channels")


def _bit_depth_formatter(v: str) -> str | None:
    return _BitDepthPropertyKeyHelper.format_value(v)


def _channel_count_formatter(v: str) -> str | None:
    return _ChannelCountPropertyKeyHelper.format_value(v)


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


class _ResolutionPropertyKeyHelper:

    _d: ClassVar[dict[str, tuple[int, str]]] = {
            ResolutionStatus.HIRES.value: (2, "HiRes"),
            ResolutionStatus.STD.value: (1, "Standard"),
            ResolutionStatus.LOW.value: (0, "Low")}

    _fallback: tuple[int, str] = _d.get(ResolutionStatus.LOW.value)

    def get_sort_value(v: str) -> int:
        return _ResolutionPropertyKeyHelper._d.get(
            v,
            _ResolutionPropertyKeyHelper._fallback)[0]

    def format_value(v: str) -> int:
        return _ResolutionPropertyKeyHelper._d.get(
            v,
            _ResolutionPropertyKeyHelper._fallback)[1]

# gives a value to the resolution status str
# so we can sort it more precisely
def _resolution_status_sort_mapper(v: str) -> int:
    return _ResolutionPropertyKeyHelper.get_sort_value(v)


def _resolution_status_formatter(v: str) -> str | None:
    return _ResolutionPropertyKeyHelper.format_value(v)


class _LosslessPropertyKeyHelper:

    _d: ClassVar[dict[str, tuple[int, str]]] = {
            LosslessStatus.LOSSLESS.value: (2, "Lossless"),
            LosslessStatus.MIXED.value: (1, "Mixed"),
            LosslessStatus.LOSSY.value: (0, "Lossy")}

    _fallback: tuple[int, str] = _d.get(LosslessStatus.LOSSY.value)

    def get_sort_value(v: str) -> int:
        return _LosslessPropertyKeyHelper._d.get(
            v,
            _LosslessPropertyKeyHelper._fallback)[0]

    def format_value(v: str) -> int:
        return _LosslessPropertyKeyHelper._d.get(
            v,
            _LosslessPropertyKeyHelper._fallback)[1]

# gives a value to the resolution status str
# so we can sort it more precisely
def _lossless_status_sort_mapper(v: str) -> int:
    return _LosslessPropertyKeyHelper.get_sort_value(v)


def _lossless_status_formatter(v: str) -> str | None:
    return _LosslessPropertyKeyHelper.format_value(v)


class AlbumPropertyKey(Enum):

    GENRE = _AlbumPropertyKeyData(display_value="Genre")
    MOOD = _AlbumPropertyKeyData(display_value="Mood")
    LABEL_INITIAL = _AlbumPropertyKeyData(display_value="Label (Initial)")
    LABEL = _AlbumPropertyKeyData(display_value="Label")
    DECADE = _AlbumPropertyKeyData(display_value="Decade")
    YEAR = _AlbumPropertyKeyData(display_value="Year")
    ALBUM_ARTIST = _AlbumPropertyKeyData(display_value="Album Artist")
    ALBUM_TITLE = _AlbumPropertyKeyData(display_value="Album Title")
    ALBUM_VERSION = _AlbumPropertyKeyData(display_value="Album Version")
    ALBUM_MB_ID = _AlbumPropertyKeyData(display_value="MusicBrainz Id")
    ARTIST = _AlbumPropertyKeyData(display_value="Artist")
    ARTIST_CONTRIBUTOR = _AlbumPropertyKeyData(display_value="Artist/Contributor")
    CONTRIBUTOR = _AlbumPropertyKeyData(display_value="Contributor")
    RELEASE_TYPE = _AlbumPropertyKeyData(display_value="Release Type")
    QUALITY_BADGE = _AlbumPropertyKeyData(
        display_value="Quality Badge",
        key_sort_mode=KeySortMode.SORT_OCCURRENCE_REVERSE)
    SUFFIX = _AlbumPropertyKeyData(
        display_value="Suffix",
        key_sort_mode=KeySortMode.SORT_OCCURRENCE_REVERSE)
    LOSSLESS_STATUS = _AlbumPropertyKeyData(
        display_value="Compression Type",
        key_value_formatter=_lossless_status_formatter,
        key_sort_mode=KeySortMode.SORT_INTEGER_REVERSE,
        key_value_sort_mapper=_lossless_status_sort_mapper)
    RESOLUTION_STATUS = _AlbumPropertyKeyData(
        display_value="Resolution",
        key_value_formatter=_resolution_status_formatter,
        key_sort_mode=KeySortMode.SORT_INTEGER_REVERSE,
        key_value_sort_mapper=_resolution_status_sort_mapper)
    BIT_DEPTH = _AlbumPropertyKeyData(
        display_value="Bit Depth",
        key_value_formatter=_bit_depth_formatter,
        key_sort_mode=KeySortMode.SORT_INTEGER_REVERSE)
    SAMPLING_RATE = _AlbumPropertyKeyData(
        display_value="Sampling Rate",
        key_value_formatter=_sampling_rate_formatter,
        key_sort_mode=KeySortMode.SORT_INTEGER_REVERSE)
    CHANNEL_COUNT = _AlbumPropertyKeyData(
        display_value="Channel Count",
        key_sort_mode=KeySortMode.SORT_OCCURRENCE_REVERSE,
        key_value_formatter=_channel_count_formatter)
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
    def max_items(self) -> int:
        return self.value.max_items

    @property
    def key_sort_mode(self) -> KeySortMode:
        return self.value.key_sort_mode

    @property
    def key_value_formatter(self) -> Callable[[str], str] | None:
        return self.value.key_value_formatter

    @property
    def key_value_sort_mapper(self) -> Callable[[str], Any] | None:
        return self.value.key_value_sort_mapper

    def format_key_value(self, key_value: str) -> str:
        return key_value if self.value.key_value_formatter is None else self.value.key_value_formatter(key_value)

    def sort_key_values(self, value_occurrence_list: list[AlbumPropertyValueOccurrence]) -> list[AlbumPropertyValueOccurrence]:
        sort_mode: _KeySortModeData = self.key_sort_mode.data
        if KeySortType.KEY_SORT_TYPE_NONE == sort_mode.sort_type:
            # return as-is
            return value_occurrence_list
        v_occ_dict_by_value: dict[str, AlbumPropertyValueOccurrence] = {occ.property_value: occ for occ in value_occurrence_list}
        # key_value_list will be a list of tuples (two values)
        # first element of tuple is property_value itself
        # second element is the one that will be used by sorting anyway
        # second element is the album count if requested (KeySortType.KEY_SORT_TYPE_OCCURRENCE), or
        # second element is translated using key_value_sort_mapper if available
        # otherwise it's the same as the first element
        key_value_list: list[tuple[str, Any]] = [(
            occ.property_value,
            (occ.album_count if self.key_sort_mode.data.sort_type == KeySortType.KEY_SORT_TYPE_OCCURRENCE else
            (self.key_value_sort_mapper(occ.property_value) if self.key_value_sort_mapper else occ.property_value)))
            for occ in value_occurrence_list]
        # convert second element to int if requested, before sorting
        values: list[tuple[str, Any]] = copy.deepcopy(
            [(x[0], x[1]) for x in key_value_list]
            if sort_mode.sort_type == KeySortType.KEY_SORT_TYPE_STRING
            else [(x[0], int(x[1])) for x in key_value_list])
        # apply sorting
        values.sort(reverse=sort_mode.reverse, key=lambda x: x[1])
        return [v_occ_dict_by_value[str(x[0])] for x in values]


def get_album_property_key(property_key: str) -> AlbumPropertyKey | None:
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


class _AlbumPropertyKeySelectionRequirementData:

    def __init__(self, property_key: AlbumPropertyKey, req_value_on_keys: list[AlbumPropertyKey]):
        self._property_key: AlbumPropertyKey = property_key
        self._req_value_on_keys: list[AlbumPropertyKey] = req_value_on_keys

    @property
    def property_key(self) -> AlbumPropertyKey:
        return self._property_key

    @property
    def req_value_on_keys(self) -> list[AlbumPropertyKey]:
        return self._req_value_on_keys


class AlbumPropertyKeySelectionRequirement(Enum):

    ALBUM_TITLE_REQUIRES_ALBUM_ARTIST = _AlbumPropertyKeySelectionRequirementData(
        property_key=AlbumPropertyKey.ALBUM_TITLE,
        req_value_on_keys=[AlbumPropertyKey.ALBUM_ARTIST])

    ALBUM_VERSION_REQUIRES_ALBUM_ARTIST = _AlbumPropertyKeySelectionRequirementData(
        property_key=AlbumPropertyKey.ALBUM_VERSION,
        req_value_on_keys=[AlbumPropertyKey.ALBUM_ARTIST])

    ALBUM_MB_ID_REQUIRES_ALBUM_ARTIST_TITLE = _AlbumPropertyKeySelectionRequirementData(
        property_key=AlbumPropertyKey.ALBUM_MB_ID,
        req_value_on_keys=[
            AlbumPropertyKey.ALBUM_ARTIST,
            AlbumPropertyKey.ALBUM_TITLE])

    YEAR_REQUIRES_DECADE = _AlbumPropertyKeySelectionRequirementData(
        property_key=AlbumPropertyKey.YEAR,
        req_value_on_keys=[AlbumPropertyKey.DECADE])

    @property
    def property_key(self) -> AlbumPropertyKey:
        return self.value.property_key

    @property
    def req_value_on_keys(self) -> list[AlbumPropertyKey]:
        return self.value.req_value_on_keys


album_property_key_selection_req_dict: dict[AlbumPropertyKey, list[AlbumPropertyKey]] = {
    member.property_key: member.req_value_on_keys
    for member in AlbumPropertyKeySelectionRequirement
}