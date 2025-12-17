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


class KindType:

    ARTIST = "artist"
    ALBUM = "album"
    TRACK = "track"


class SearchType(Enum):
    ALBUM = 0, "album"
    ARTIST = 1, "artist"
    TRACK = 2, "track"

    def __init__(
            self,
            num: int,
            element_name: str):
        self.num: int = num
        self.element_name: str = element_name

    def getName(self):
        return self.element_name


# duplicate check
name_checker_set: set[str] = set()
id_checker_set: set[int] = set()
for v in SearchType:
    if v.getName() in name_checker_set:
        raise Exception(f"Duplicated name [{v.getName()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.getName())
    id_checker_set.add(v.value[0])
