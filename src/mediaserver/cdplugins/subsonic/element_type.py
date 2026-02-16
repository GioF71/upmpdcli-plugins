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


class _ElementTypeData:

    def __init__(self):
        global current_id
        if current_id is None:
            current_id = 0
        else:
            current_id += 1
        self.__element_name: str = idgenerator.number_to_base_decoded(n=current_id, base_chars=base_chars)

    @property
    def element_name(self) -> str:
        return self.__element_name


class ElementType(Enum):
    TAG = _ElementTypeData()
    ALBUM = _ElementTypeData()
    ALBUM_VERSION = _ElementTypeData()
    GENRE = _ElementTypeData()
    GENRE_ARTIST_LIST = _ElementTypeData()
    GENRE_ALBUM_LIST = _ElementTypeData()
    ARTIST = _ElementTypeData()
    GENRE_ARTIST = _ElementTypeData()
    ARTIST_BY_INITIAL = _ElementTypeData()
    SONG = _ElementTypeData()
    PLAYLIST = _ElementTypeData()
    INTERNET_RADIO = _ElementTypeData()
    SONG_ENTRY_NAVIGABLE = _ElementTypeData()
    SONG_ENTRY_THE_SONG = _ElementTypeData()
    NEXT_RANDOM_SONGS = _ElementTypeData()
    NAVIGABLE_ALBUM = _ElementTypeData()
    ARTIST_TOP_SONGS = _ElementTypeData()
    ARTIST_TOP_SONGS_LIST = _ElementTypeData()
    ARTIST_SIMILAR = _ElementTypeData()
    ARTIST_ALBUMS = _ElementTypeData()
    RADIO = _ElementTypeData()
    RADIO_SONG_LIST = _ElementTypeData()
    GENRE_ARTIST_ALBUMS = _ElementTypeData()
    # artist which appear as artistId for albums
    ALBUM_FOCUS = _ElementTypeData()
    ARTIST_FOCUS = _ElementTypeData()
    ADDITIONAL_ALBUM_ARTISTS = _ElementTypeData()
    ARTIST_APPEARANCES = _ElementTypeData()
    ALBUM_SONG_SELECTION_BY_ARTIST = _ElementTypeData()
    ALBUM_DISC = _ElementTypeData()
    ARTIST_ROLE = _ElementTypeData()
    ARTIST_ROLE_INITIAL = _ElementTypeData()
    ALBUM_BROWSE_FILTER_KEY = _ElementTypeData()
    ALBUM_BROWSE_FILTER_VALUE = _ElementTypeData()
    ALBUM_BROWSE_MATCHING_ALBUMS = _ElementTypeData()

    @property
    def element_name(self) -> str:
        if config.get_config_param_as_bool(constants.ConfigParam.MINIMIZE_IDENTIFIER_LENGTH):
            return self.name
        else:
            return self.value.element_name


def get_element_type_by_name(element_name: str) -> ElementType:
    element: ElementType
    for element in ElementType:
        if element.element_name == element_name:
            return element
    raise Exception(f"get_element_type_by_name with {element_name} NOT found")
