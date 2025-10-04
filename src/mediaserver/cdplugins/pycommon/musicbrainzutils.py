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

# source: https://musicbrainz.org/doc/Release_Group/Type

from enum import Enum
from typing import Callable


class _ReleaseTypeDefinition:

    def __init__(self, value_list: list[str], reference_value: str = None, display_value: str = None):
        self.__value_list: list[str] = value_list
        self.__reference_value: str = reference_value if reference_value else value_list[0]
        self.__display_value: str = display_value if display_value else self.__reference_value.title()

    @property
    def value_list(self) -> list[str]:
        return self.__value_list

    @property
    def reference_value(self) -> str:
        return self.__reference_value

    @property
    def display_value(self) -> str:
        return self.__display_value


def _words_to_array(word_list: list[str]) -> list[str]:
    lst: list[str] = []
    lst.append("/".join(word_list))
    lst.append("-".join(word_list))
    lst.append(" ".join(word_list))
    return lst


class PrimaryReleaseType(Enum):
    ALBUM = _ReleaseTypeDefinition(["album"])
    SINGLE = _ReleaseTypeDefinition(["single"])
    EP = _ReleaseTypeDefinition(["ep"])
    BROADCAST = _ReleaseTypeDefinition(["broadcast"])
    OTHER = _ReleaseTypeDefinition(["other"])

    @property
    def value_list(self) -> list[str]:
        return self.value.value_list

    @property
    def reference_value(self) -> str:
        return self.value.reference_value

    @property
    def display_value(self) -> str:
        return self.value.display_value


class SecondaryReleaseType(Enum):
    COMPILATION = _ReleaseTypeDefinition(["compilation"])
    SOUNDTRACK = _ReleaseTypeDefinition(["soundtrack"])
    SPOKEN_WORD = _ReleaseTypeDefinition(["spokenword"])
    INTERVIEW = _ReleaseTypeDefinition(["interview"])
    AUDIO_BOOK = _ReleaseTypeDefinition(["audiobook"], display_value="Audiobook")
    AUDIO_DRAMA = _ReleaseTypeDefinition(["audiodrama"], display_value="Audio drama")
    LIVE = _ReleaseTypeDefinition(["live"])
    REMIX = _ReleaseTypeDefinition(["remix"])
    DJ_MIX = _ReleaseTypeDefinition(_words_to_array(["dj", "mix"]), display_value="DJ-mix")
    MIXTAPE_STREET = _ReleaseTypeDefinition(_words_to_array(["mixtape", "street"]), display_value="Mixtape/Street")
    DEMO = _ReleaseTypeDefinition(["demo"])
    FIELD_RECORDING = _ReleaseTypeDefinition(_words_to_array(["field", "recording"]), display_value="Field recording")

    @property
    def value_list(self) -> list[str]:
        return self.value.value_list

    @property
    def reference_value(self) -> str:
        return self.value.reference_value

    @property
    def display_value(self) -> str:
        return self.value.display_value


def match_primary_release_type(t: str) -> PrimaryReleaseType:
    if not t:
        return False
    low_t: str = t.lower()
    prt: PrimaryReleaseType
    for prt in PrimaryReleaseType:
        if low_t in prt.value_list:
            return prt
    return None


def match_secondary_release_type(t: str) -> SecondaryReleaseType:
    if not t:
        return False
    low_t: str = t.lower()
    srt: SecondaryReleaseType
    for srt in SecondaryReleaseType:
        if low_t in srt.value_list:
            return srt
    return None


def is_primary_release_type(t: str) -> bool:
    return match_primary_release_type(t) is not None


def is_secondary_release_type(t: str) -> bool:
    return match_secondary_release_type(t) is not None


def any_primary_release_type(value_list: list[str]) -> bool:
    return len(extract_release_types(
        value_list=value_list,
        type_matcher=is_primary_release_type)) > 0


def any_secondary_release_type(value_list: list[str]) -> bool:
    return len(extract_release_types(
        value_list=value_list,
        type_matcher=is_secondary_release_type)) > 0


def display_value(value: str) -> str:
    if not value:
        return None
    primary: PrimaryReleaseType = match_primary_release_type(value)
    if primary:
        return primary.display_value
    secondary: SecondaryReleaseType = match_secondary_release_type(value)
    if secondary:
        return secondary.display_value
    return value.title()


def extract_release_types(value_list: list[str], type_matcher: Callable[[str], bool]) -> list[str]:
    res: list[str] = []
    v: str
    for v in (value_list if value_list else []):
        if type_matcher(v):
            res.append(v)
    return res


def sanitize_release_types(
        value_list: list[str],
        fallback_primary: PrimaryReleaseType = PrimaryReleaseType.ALBUM,
        print_function: Callable[[str], None] = None) -> list[str]:
    # correct some common errors.
    primaries: list[PrimaryReleaseType] = []
    secondaries: list[SecondaryReleaseType] = []
    others: list[str] = []
    res: list[str] = []
    v: str
    for v in value_list if value_list else []:
        # skip empty values
        if not v:
            continue
        # primary?
        p: PrimaryReleaseType = match_primary_release_type(v)
        if p and p not in primaries:
            primaries.append(p)
        # secondary?
        s: SecondaryReleaseType = not p and match_secondary_release_type(v)
        if s and s not in secondaries:
            secondaries.append(s)
        if not (s or p):
            # other!
            if v not in others:
                others.append(v)
    # only a secondary value, and maybe others?
    if len(primaries) == 0 and len(secondaries) > 0:
        if fallback_primary:
            res.append(fallback_primary.reference_value)
        res.append(secondaries[0].reference_value)
        res.extend(others)
        if print_function:
            print_function(f"sanitize_release_types values [{value_list}] -> [{res}] (missing primary)")
    elif len(primaries) == 0 and len(secondaries) == 0 and len(others) == 0:
        if fallback_primary:
            res.append(fallback_primary.reference_value)
    else:
        # push everything.
        res.extend(map(lambda p: p.reference_value, primaries))
        res.extend(map(lambda p: p.reference_value, secondaries))
        res.extend(others)
    return res


# tests
album_is_primary: bool = any_primary_release_type(["Album", "ep"])
if not album_is_primary:
    raise Exception("Album should match as primary")
compilation_is_secondary: bool = any_secondary_release_type(["Album", "Compilation"])
if not compilation_is_secondary:
    raise Exception("Compilation should match as secondary")
# extract correctly
album_extract: list[str] = extract_release_types(
    value_list=["Demo", "Album"],
    type_matcher=is_primary_release_type)[0]
if not PrimaryReleaseType.ALBUM == match_primary_release_type(album_extract):
    raise Exception("Album should be extract as album regardless of the position")
# sanitize cases
sanitized_1: list[str] = sanitize_release_types(["compilation"])
if not ["album", "compilation"] == sanitized_1:
    raise Exception("Sanitization case #1 failed")
sanitized_2: list[str] = sanitize_release_types(["album", "live"])
if not ["album", "live"] == sanitized_2:
    raise Exception("Sanitization case #2 failed")
sanitized_3: list[str] = sanitize_release_types(["compilation", "some_other"])
if not ["album", "compilation", "some_other"] == sanitized_3:
    raise Exception("Sanitization case #3 failed")
wrong_4: list[str] = ["DeMo", "album"]
sanitized_4: list[str] = sanitize_release_types(wrong_4)
if not ["album", "demo"] == sanitized_4:
    raise Exception("Sanitization case #4 failed")
# secondary with separator
if not SecondaryReleaseType.MIXTAPE_STREET == match_secondary_release_type("mixtape-sTrEeT"):
    raise Exception(f"Match for {SecondaryReleaseType.MIXTAPE_STREET.reference_value} failed")
