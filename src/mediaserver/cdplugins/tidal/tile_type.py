# Copyright (C) 2023 Giovanni Fulco
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


class TileType(Enum):
    TAG = 1, "tag",
    CATEGORY = 2, "category"
    PAGE_LINK = 3, "pagelink"

    def __init__(self,
            type_type_num : int,
            tile_type_name : str):
        self._type_type_num : int = type_type_num
        self._tile_type_name : str = tile_type_name

    @property
    def tile_type_num(self) -> int:
        """I'm the 'tile_type_num' property."""
        return self._type_type_num

    @property
    def tile_type_name(self) -> str:
        """I'm the 'tile_type_name' property."""
        return self._tile_type_name


def get_tile_type_by_name(tile_type_name : str) -> TileType:
    # msgproc.log(f"get_tag_Type_by_name with {tag_name}")
    for _, member in TileType.__members__.items():
        if tile_type_name == member.tile_type_name:
            return member
    raise Exception(f"get_tile_type_by_name with {tile_type_name} NOT found")


# duplicate check
name_checker_set : set[str] = set()
id_checker_set : set[int] = set()
for v in TileType:
    if v.tile_type_name in name_checker_set:
        raise Exception(f"Duplicated name [{v.tile_type_name}]")
    if v.tile_type_num in id_checker_set:
        raise Exception(f"Duplicated id [{v.tile_type_num}]")
    name_checker_set.add(v.tile_type_name)
    id_checker_set.add(v.tile_type_num)
