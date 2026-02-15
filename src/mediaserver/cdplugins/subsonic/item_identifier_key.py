# Copyright (C) 2023,2024,2025 Giovanni Fulco
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
import idgenerator
import config
import constants

base_chars: str = "abcdefghijklmnopqrtuvwxyz0123456789"
current_id: int = None


class _ItemIdentifierKey:

    def __init__(self):
        global current_id
        if current_id is None:
            current_id = 0
        else:
            current_id += 1
        self.__element_name: str = idgenerator.number_to_base_decoded(n=current_id, base_chars=base_chars)

    @property
    def identifier_name(self) -> str:
        return self.__identifier_name


class ItemIdentifierKey(Enum):
    THING_NAME = _ItemIdentifierKey()
    THING_VALUE = _ItemIdentifierKey()
    GENRE_NAME = _ItemIdentifierKey()
    PAGE_NUMBER = _ItemIdentifierKey()
    ALBUM_ID = _ItemIdentifierKey()
    OFFSET = _ItemIdentifierKey()
    TAG_TYPE = _ItemIdentifierKey()
    ALBUM_VERSION_PATH_BASE64 = _ItemIdentifierKey()
    RADIO_NAME = _ItemIdentifierKey()
    SONG_AS_ENTRY = _ItemIdentifierKey()
    RANDOM_VALUE = _ItemIdentifierKey()
    SKIP_ARTIST_ID = _ItemIdentifierKey()
    ALBUM_RELEASE_TYPE = _ItemIdentifierKey()
    ALBUM_ID_REF_FOR_ARTIST = _ItemIdentifierKey()
    ALBUM_DISC_NUMBERS = _ItemIdentifierKey()
    ALBUM_IGNORE_DISCNUMBERS = _ItemIdentifierKey()
    ARTIST_ROLE = _ItemIdentifierKey()
    ALBUM_BROWSE_SELECTION_LIST = _ItemIdentifierKey()
    ALBUM_BROWSE_FILTER_KEY = _ItemIdentifierKey()

    @property
    def identifier_name(self) -> str:
        if config.get_config_param_as_bool(constants.ConfigParam.MINIMIZE_IDENTIFIER_LENGTH):
            return self.name
        else:
            return self.value.element_name


# duplicate check
name_checker_set: set[str] = set()
for v in ItemIdentifierKey:
    if v.identifier_name in name_checker_set:
        raise Exception(f"Duplicated name [{v.identifier_name}]")
    name_checker_set.add(v.identifier_name)
