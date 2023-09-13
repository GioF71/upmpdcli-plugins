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
        """I'm the 'track_id' property."""
        return self._track_id

    @track_id.setter
    def track_id(self, value : str):
        self._track_id : str = value

    @property
    def play_count(self) -> int:
        """I'm the 'play_count' property."""
        return self._play_count

    @play_count.setter
    def play_count(self, value : int):
        self._play_count : int = value

    @property
    def last_played(self) -> datetime.datetime:
        """I'm the 'last_played' property."""
        return self._last_played

    @last_played.setter
    def last_played(self, value : datetime.datetime):
        self._last_played : datetime.datetime = value
