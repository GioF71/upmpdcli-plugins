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


from common_data_structures import ArtistIdName
from enum import Enum


class SongArtistType(Enum):
    SONG_ALBUM_ARTIST = 1
    SONG_ARTIST = 2


class SongArtist:

    def __init__(
            self,
            song_id: str,
            artist_id: str,
            artist_name: str):
        self.__song_id: str = song_id
        self.__artist: ArtistIdName = ArtistIdName(
            artist_id=artist_id,
            artist_name=artist_name)

    @property
    def song_id(self) -> str:
        return self.__song_id

    @property
    def artist_id(self) -> str:
        return self.__artist.artist_id

    @property
    def artist_name(self) -> str:
        return self.__artist.artist_name


class SongContributor:

    def __init__(
            self,
            song_id: str,
            role: str,
            sub_role: str,
            artist_id: str,
            artist_name: str):
        self.__song_id: str = song_id
        self.__role: str = role
        self.__sub_role: str = sub_role
        self.__artist: ArtistIdName = ArtistIdName(
            artist_id=artist_id,
            artist_name=artist_name)

    @property
    def song_id(self) -> str:
        return self.__song_id

    @property
    def role(self) -> str:
        return self.__role

    @property
    def sub_role(self) -> str:
        return self.__sub_role

    @property
    def artist_id(self) -> str:
        return self.__artist.artist_id

    @property
    def artist_name(self) -> str:
        return self.__artist.artist_name
