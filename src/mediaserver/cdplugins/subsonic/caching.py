# Copyright (C) 2023,2024 Giovanni Fulco
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

from subsonic_connector.album import Album

import secrets


class CacheManager:

    def __init__(self):
        self.__caches : dict[str, any] = {}

    def __get_element_cache(self, element_type : ElementType) -> dict:
        if element_type.getName() in self.__caches:
            return self.__caches[element_type.getName()]
        cache = {}
        self.__caches[element_type.getName()] = cache
        return cache

    def cache_element_value(self, element_type : ElementType, key : str, value : any):
        cache : dict = self.__get_element_cache(element_type)
        cache[key] = value

    def cache_element_multi_value(self, element_type : ElementType, key : str, value : any):
        cache : dict = self.__get_element_cache(element_type)
        existing : set[any] = cache[key] if key in cache else None
        if not existing:
            existing = set()
            cache[key] = existing
        if value not in existing:
            existing.add(value)

    def is_element_cached(self, element_type : ElementType, key : str) -> bool:
        cache : dict = self.__get_element_cache(element_type)
        return key in cache

    def get_cached_element(self, element_type : ElementType, key : str) -> any:
        cache : dict = self.__get_element_cache(element_type)
        return cache[key] if key in cache else None

    def get_cache_size(self, element_type : ElementType) -> int:
        return len(self.__get_element_cache(element_type))

    def on_album(self, album : Album):
        if album.getArtistId():
            self.cache_element_value(
                element_type = ElementType.ALBUM_ARTIST,
                key = album.getArtistId(),
                value = album.getArtistId())
            self.cache_element_multi_value(
                element_type = ElementType.ARTIST_ALBUMS,
                key = album.getArtistId(),
                value = album.getId())
        genre_list : list[str] = album.getGenres()
        self.on_album_for_genre_list(album, genre_list)

    def on_missing_artist_id(self, artist_id : str):
        # remove from ALBUM_ARTIST if there
        album_artist_cache : dict[str, any] = self.__get_element_cache(ElementType.ALBUM_ARTIST)
        if artist_id in album_artist_cache: del album_artist_cache[artist_id]
        # remove from ARTIST_ALBUMS if there
        artist_albums_cache : dict[str, any] = self.__get_element_cache(ElementType.ARTIST_ALBUMS)
        if artist_id in artist_albums_cache: del artist_albums_cache[artist_id]

    def is_album_artist(self, artist_id : str) -> bool:
        return self.is_element_cached(
            ElementType.ALBUM_ARTIST,
            artist_id)

    def get_random_album_id(self, artist_id : str) -> str:
        album_set : set[str] = self.get_cached_element(element_type = ElementType.ARTIST_ALBUMS, key = artist_id)
        if not album_set or len(album_set) == 0: return None
        album_id : str = secrets.choice(tuple(album_set))
        return album_id

    def on_album_for_genre_list(self, album : Album, genre_list : list[str]):
        for genre in genre_list if genre_list else list():
            self.on_album_for_genre(album, genre)

    def on_album_for_genre(self, album : Album, genre : str):
        self.cache_element_multi_value(
            ElementType.GENRE,
            genre,
            album.getId())
