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

class PlayedAlbum:

    def __init__(self):
        self._album_id : str = None
        self._album_played_counter : float = None

    @property
    def album_id(self) -> str:
        return self._album_id

    @album_id.setter
    def album_id(self, value : str):
        self._album_id : str = value

    @property
    def album_played_counter(self) -> float:
        return self._album_played_counter

    @album_played_counter.setter
    def album_played_counter(self, value : float):
        self._album_played_counter : float = value
