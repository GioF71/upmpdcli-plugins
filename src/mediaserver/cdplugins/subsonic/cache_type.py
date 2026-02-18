# Copyright (C) 2024,2025 Giovanni Fulco
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


class _CacheTypeData:

    def __init__(self, cache_name: str):
        self.__cache_name: str = cache_name

    @property
    def cache_name(self) -> str:
        return self.__cache_name


class CacheType(Enum):

    GENERIC_KEY_VALUE = _CacheTypeData("generic_kv")
    ITEM_IDENTIFIER_CODEC = _CacheTypeData("iid_codec")

    @property
    def cache_name(self) -> str:
        return self.value.cache_name


# duplicate check
name_checker_set: set[str] = set()
id_checker_set: set[int] = set()
for v in CacheType:
    if v.cache_name in name_checker_set:
        raise Exception(f"Duplicated name [{v.cache_name}]")
    name_checker_set.add(v.cache_name)
    id_checker_set.add(v.cache_name)
