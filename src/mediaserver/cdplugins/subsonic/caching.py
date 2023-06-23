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

from element_type import ElementType

class CacheManager:

    def __init__(self):
        self.__caches : dict[str, any] = {}
        
    def __get_element_cache(self, element_type : ElementType) -> dict:
        if element_type.getName() in self.__caches:
            return self.__caches[element_type.getName()]
        cache = {}
        self.__caches[element_type.getName()] = cache
        return cache

    def cache_element_value(self, element_type : ElementType, key : str, value : str):
        cache : dict = self.__get_element_cache(element_type)
        cache[key] = value

    def is_element_cached(self, element_type : ElementType, key : str) -> bool:
        cache : dict = self.__get_element_cache(element_type)
        return key in cache

    def get_cached_element(self, element_type : ElementType, key : str) -> str:
        cache : dict = self.__get_element_cache(element_type)
        if key in cache:
            return cache[key]
        return None

    def get_cache_size(self, element_type : ElementType) -> int:
        cache : dict = self.__get_element_cache(element_type)
        return len(cache)

