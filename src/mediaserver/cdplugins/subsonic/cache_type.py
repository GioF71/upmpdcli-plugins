# Copyright (C) 2024 Giovanni Fulco
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


class CacheType(Enum):
    ALBUMS_BY_ARTIST = 1, "lbm4rtst"
    GENRE_ALBUM_ART = 2, "genre_album_art"
    ALBUM_TRACK_QUALITIES = 3, "album_track_qualities"

    def __init__(
            self,
            num: int,
            cache_name: str):
        self.num: int = num
        self.__cache_name: str = cache_name

    def getName(self) -> str:
        return self.__cache_name


def get_cache_type_by_name(cache_name: str) -> CacheType:
    for _, member in CacheType.__members__.items():
        if cache_name == member.getName():
            return member
    raise Exception(f"get_cache_type_by_name with {cache_name} NOT found")


# duplicate check
name_checker_set: set[str] = set()
id_checker_set: set[int] = set()
for v in CacheType:
    if v.getName() in name_checker_set:
        raise Exception(f"Duplicated name [{v.getName()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.getName())
    id_checker_set.add(v.value[0])
