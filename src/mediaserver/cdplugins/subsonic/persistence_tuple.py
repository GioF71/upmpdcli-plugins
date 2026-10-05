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
from typing import NamedTuple


class PersistenceTupleException(Exception):
    """Raised when a PersistenceTuple error occurs."""


class CoverSource(Enum):
    ARTIST = "artist"
    ALBUM = "album"
    SONG = "song"


def get_cover_source_by_name(name: str) -> CoverSource:
    curr: CoverSource
    for curr in CoverSource:
        if name == curr.value:
            return curr
    raise PersistenceTupleException(f"Name {name} could not be found")


class ArtistAlbumCoverArt:

    def __init__(
            self,
            artist_id: str,
            cover_source: CoverSource,
            object_id: str,
            cover_art: str):
        self.__artist_id: str = artist_id
        self.__cover_source: CoverSource = cover_source
        self.__object_id: str = object_id
        self.__cover_art: str = cover_art

    @property
    def artist_id(self) -> str:
        return self.__artist_id

    @property
    def cover_source(self) -> CoverSource:
        return self.__cover_source

    @property
    def object_id(self) -> str:
        return self.__object_id

    @property
    def cover_art(self) -> str:
        return self.__cover_art


class AlbumPropertyValueSelection:

    def __init__(
            self,
            album_property_key: str,
            album_property_value: str,
            album_count: int):
        self.__album_property_key: str = album_property_key
        self.__album_property_value: str = album_property_value
        self.__album_count: int = album_count

    @property
    def album_property_key(self) -> str:
        return self.__album_property_key

    @property
    def album_property_value(self) -> str:
        return self.__album_property_value

    @property
    def album_count(self) -> int:
        return self.__album_count


class DuplicateAlbumInfo(NamedTuple):
    occurrence_count: int
    album_cover_art: str
    album_artist: str
    album_title: str
    album_version: str | None = None


class DuplicateAlbumOccurrence(NamedTuple):
    album_id: str
    album_artist: str
    album_title: str
    album_version: str | None = None
    album_cover_art: str | None = None
    lossless_status: str | None = None
    quality_badge: str | None = None
    album_release_date_year: int | None = None
    album_release_date_month: int | None = None
    album_release_date_day: int | None = None
