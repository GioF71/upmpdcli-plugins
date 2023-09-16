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

import datetime

class PlayedTrack:

    def __init__(self):
        pass

    @property
    def track_id(self) -> str:
        return self._track_id

    @track_id.setter
    def track_id(self, value : str):
        self._track_id : str = value

    @property
    def album_id(self) -> str:
        return self._album_id

    @album_id.setter
    def album_id(self, value : str):
        self._album_id : str = value

    @property
    def album_track_count(self) -> int:
        return self._album_track_count

    @album_track_count.setter
    def album_track_count(self, value : str):
        self._album_track_count : int = value

    @property
    def play_count(self) -> int:
        return self._play_count

    @play_count.setter
    def play_count(self, value : int):
        self._play_count : int = value

    @property
    def last_played(self) -> datetime.datetime:
        return self._last_played

    @last_played.setter
    def last_played(self, value : datetime.datetime):
        self._last_played : datetime.datetime = value
