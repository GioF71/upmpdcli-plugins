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
import constants
import config


base_chars: str = "abcdefghijklmnopqrtuvwxyz0123456789"
current_id: int = None


class _TagTypeData:

    def __init__(self, tag_title: str, query_type: str = None):
        global current_id
        if current_id is None:
            current_id = 0
        else:
            current_id += 1
        self.__tag_name: str = idgenerator.number_to_base_decoded(n=current_id, base_chars=base_chars)
        self.__tag_title: str = tag_title
        self.__query_type: str = query_type

    @property
    def tag_name(self) -> str:
        return self.__tag_name

    @property
    def tag_title(self) -> str:
        return self.__tag_title

    @property
    def query_type(self) -> str:
        return self.__query_type


class TagType(Enum):

    ALBUMS = _TagTypeData("Albums", None)
    RECENTLY_ADDED_ALBUMS = _TagTypeData("Recently Added Albums", query_type="newest")
    RECENTLY_PLAYED_ALBUMS = _TagTypeData("Recently Played Albums", query_type="recent")
    HIGHEST_RATED_ALBUMS = _TagTypeData("Highest Rated Albums", query_type="highest")
    FAVORITE_ALBUMS = _TagTypeData("Favorite Albums", query_type="starred")
    MOST_PLAYED_ALBUMS = _TagTypeData("Most Played Albums", query_type="frequent")
    NEWEST_ALBUMS = _TagTypeData("Newest Albums", query_type="byYear")
    OLDEST_ALBUMS = _TagTypeData("Oldest Albums", query_type="byYear")
    ALPHABETICAL_BY_NAME_ALBUMS = _TagTypeData("Alphabetical By Name", query_type="alphabeticalByName")
    ALPHABETICAL_BY_ARTIST_ALBUMS = _TagTypeData("Alphabetical By Artist", query_type="alphabeticalByArtist")
    RANDOM = _TagTypeData("Random Albums", query_type="random")
    ALBUMS_WITHOUT_MUSICBRAINZ = _TagTypeData("Albums without MusicBrainz")
    ALBUMS_WITHOUT_COVER = _TagTypeData("Albums without CoverArt")
    ALBUMS_WITHOUT_GENRE = _TagTypeData("Albums without Genre")
    ARTIST_ROLES = _TagTypeData("Artist Roles")
    ARTISTS = _TagTypeData("Artists")
    ALL_ARTISTS = _TagTypeData("All Artists (Sorted) (slow!)")
    ALL_ARTISTS_INDEXED = _TagTypeData("All Artists (By Initial) (slow!)")
    ALL_ARTISTS_UNSORTED = _TagTypeData("All Artists")
    ALL_ALBUM_ARTISTS_UNSORTED = _TagTypeData("Album Artists")
    ALL_COMPOSERS_UNSORTED = _TagTypeData("Composers")
    ALL_CONDUCTORS_UNSORTED = _TagTypeData("Conductors")
    FAVORITE_ARTISTS = _TagTypeData("Favorite Artists", "starred")
    SONGS = _TagTypeData("Songs")
    RANDOM_SONGS = _TagTypeData("Random Songs")
    RANDOM_SONGS_LIST = _TagTypeData("Random Songs (List)")
    FAVORITE_SONGS = _TagTypeData("Favorite Songs")
    FAVORITE_SONGS_LIST = _TagTypeData("Favorite Songs (List)")
    GENRES = _TagTypeData("Genres")
    PLAYLISTS = _TagTypeData("Playlists")
    INTERNET_RADIOS = _TagTypeData("Internet Radios")
    ALBUM_BROWSER = _TagTypeData("Album Browser")

    @property
    def tag_name(self) -> str:
        if config.get_config_param_as_bool(constants.ConfigParam.MINIMIZE_IDENTIFIER_LENGTH):
            return self.name
        else:
            return self.value.tag_name

    @property
    def tag_title(self) -> str:
        return self.value.tag_title

    @property
    def query_type(self) -> str:
        return self.value.query_type


def get_tag_type_by_name(tag_name: str) -> TagType:
    tag: TagType
    for tag in TagType:
        if tag_name == tag.tag_name:
            return tag
    raise Exception(f"get_tag_type_by_name with {tag_name} NOT found")
