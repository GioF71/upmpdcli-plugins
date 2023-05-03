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

# maybe remove this!
class GenreArtistCache:

    def __init__(self):
        self._cache : dict[str, set[str] ] = {}

    def __get_set(self, genre : str) -> set[str]:
        if genre in self._cache: return self._cache[genre]
        new_set : set[str] = set()
        self._cache[genre] = new_set
        return new_set

    def add(self, genre : str, artist_id : str) -> bool:
        genre_set : set[str] = self.__get_set(genre)
        if artist_id in genre_set: return False
        genre_set.add(artist_id)
        return True
