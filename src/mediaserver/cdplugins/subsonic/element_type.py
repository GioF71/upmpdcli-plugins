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


class ElementTypeException(Exception):
    """Raised when a ElementType error occurs."""

base_chars: str = "abcdefghijklmnopqrtuvwxyz0123456789"
current_id: int = None


class ElementType(Enum):
    TAG = auto()
    ALBUM = auto()
    ALBUM_VERSION = auto()
    GENRE = auto()
    GENRE_ARTIST_LIST = auto()
    GENRE_ALBUM_LIST = auto()
    ARTIST = auto()
    GENRE_ARTIST = auto()
    ARTIST_BY_INITIAL = auto()
    SONG = auto()
    PLAYLIST = auto()
    INTERNET_RADIO = auto()
    SONG_ENTRY_NAVIGABLE = auto()
    SONG_ENTRY_THE_SONG = auto()
    NEXT_RANDOM_SONGS = auto()
    NAVIGABLE_ALBUM = auto()
    ARTIST_TOP_SONGS = auto()
    ARTIST_TOP_SONGS_LIST = auto()
    ARTIST_SIMILAR = auto()
    ARTIST_ALBUMS = auto()
    RADIO = auto()
    RADIO_SONG_LIST = auto()
    GENRE_ARTIST_ALBUMS = auto()
    # artist which appear as artistId for albums
    ALBUM_FOCUS = auto()
    ARTIST_FOCUS = auto()
    ADDITIONAL_ALBUM_ARTISTS = auto()
    ARTIST_APPEARANCES = auto()
    ALBUM_SONG_SELECTION_BY_ARTIST = auto()
    ALBUM_DISC = auto()
    ARTIST_ROLE = auto()
    ARTIST_ROLE_INITIAL = auto()
    ALBUM_BROWSE_FILTER_KEY = auto()
    ALBUM_BROWSE_FILTER_VALUE = auto()
    ALBUM_BROWSE_MATCHING_ALBUMS = auto()
    FAVORITE_SONGS_AS_CONTAINERS = auto()
    FAVORITE_SONGS_CONTAINER = auto()
    ARTIST_ALBUMS_WITH_DUPLICATE_TITLES = auto()
    ARTIST_ALBUMS_WITH_DUPLICATE_TITLE_VERSION_PAIR = auto()
    ARTIST_ALBUMS_FILTERED_BY_TITLE = auto()
    ARTIST_ALBUMS_FILTERED_BY_TITLE_VERSION = auto()
    DUPLICATE_ALBUM = auto()
    INVALID_OBJECT_ID = auto()


    def __init__(self, val):
        self.__element_name: str = idgenerator.number_to_base_decoded(n=val, base_chars=base_chars)

    @property
    def element_name(self) -> str:
        # if MINIMIZE_IDENTIFIER_LENGTH is True
        # we return the name of the enum because it will be encoded anyway
        # otherwise return the short __element_name which is a
        # base encoded string of the auto() value
        if config.get_config_param_as_bool(constants.ConfigParam.MINIMIZE_IDENTIFIER_LENGTH):
            return self.name
        else:
            return self.__element_name


def get_element_type_by_name(element_name: str) -> ElementType:
    element: ElementType
    for element in ElementType:
        if element.element_name == element_name:
            return element
    raise ElementTypeException(f"get_element_type_by_name with {element_name} NOT found")
