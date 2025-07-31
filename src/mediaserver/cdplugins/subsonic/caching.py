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


class CacheManager:

    def __init__(self):
        self.__caches: dict[str, any] = {}

    def __get_element_cache(self, cache_name: str) -> dict[str, any]:
        if cache_name in self.__caches:
            return self.__caches[cache_name]
        cache: dict[str, any] = {}
        self.__caches[cache_name] = cache
        return cache

    def cache_element_value(self, cache_name: str, key: str, value: any):
        cache: dict[str, any] = self.__get_element_cache(cache_name)
        cache[key] = value

    def cache_element_multi_value(self, cache_name: str, key: str, value: any):
        cache: dict[str, any] = self.__get_element_cache(cache_name)
        existing: set[any] = cache[key] if key in cache else None
        if not existing:
            existing = set()
            cache[key] = existing
        if value not in existing:
            existing.add(value)

    def is_element_cached(self, cache_name: str, key: str) -> bool:
        cache: dict[str, any] = self.__get_element_cache(cache_name)
        return key in cache if cache else False

    def get_cached_element(self, cache_name: str, key: str) -> any:
        cache: dict[str, any] = self.__get_element_cache(cache_name)
        return cache[key] if key in cache else None

    def delete_cached_element(self, cache_name: str, key: str) -> bool:
        cache: dict[str, any] = self.__get_element_cache(cache_name)
        can_delete: bool = key in cache
        if can_delete:
            del cache[key]
        return can_delete

    def get_cache_size(self, cache_name: str) -> int:
        element_cache: dict[str, any] = self.__get_element_cache(cache_name)
        return len(element_cache) if element_cache else 0
