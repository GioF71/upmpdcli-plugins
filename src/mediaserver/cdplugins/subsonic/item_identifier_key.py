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

from enum import Enum, auto

import idgenerator

import config
import constants


class ItemIdentifierKeyException(Exception):
    """Raised when a ItemIdentifierKey error occurs."""

base_chars: str = "abcdefghijklmnopqrtuvwxyz0123456789"
current_id: int = None


class ItemIdentifierKey(Enum):
    THING_NAME = auto()
    THING_VALUE = auto()
    GENRE_NAME = auto()
    PAGE_NUMBER = auto()
    ALBUM_ID = auto()
    OFFSET = auto()
    TAG_TYPE = auto()
    ALBUM_VERSION_PATH_BASE64 = auto()
    RADIO_NAME = auto()
    SONG_AS_NAVIGABLE_ENTRY = auto()
    RANDOM_VALUE = auto()
    SKIP_ARTIST_ID = auto()
    ALBUM_RELEASE_TYPE = auto()
    ALBUM_ID_REF_FOR_ARTIST = auto()
    ALBUM_DISC_NUMBERS = auto()
    ALBUM_IGNORE_DISCNUMBERS = auto()
    ARTIST_ROLE = auto()
    ALBUM_BROWSE_SELECTION_LIST = auto()
    ALBUM_BROWSE_FILTER_KEY = auto()
    ALBUM_TITLE = auto()
    ALBUM_VERSION = auto()
    LIMIT = auto()
    ALBUM_ARTIST = auto()
    INCLUDE_ALBUM_VERSION = auto()

    def __init__(self, val):
        self.__identifier_name: str = idgenerator.number_to_base_decoded(n=val, base_chars=base_chars)

    @property
    def identifier_name(self) -> str:
        # if MINIMIZE_IDENTIFIER_LENGTH is True
        # we return the name of the enum because it will be encoded anyway
        # otherwise return the short __identifier_name which is a
        # base encoded string of the auto() value
        if config.get_config_param_as_bool(constants.ConfigParam.MINIMIZE_IDENTIFIER_LENGTH):
            return self.name
        else:
            return self.__identifier_name


# duplicate check
name_checker_set: set[str] = set()
for v in ItemIdentifierKey:
    if v.identifier_name in name_checker_set:
        raise ItemIdentifierKeyException(f"Duplicated name [{v.identifier_name}]")
    name_checker_set.add(v.identifier_name)
