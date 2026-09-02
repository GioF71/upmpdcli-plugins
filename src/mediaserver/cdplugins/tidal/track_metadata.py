# Copyright (C) 2026 Giovanni Fulco
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


class TrackMetadata:

    def __init__(self):
        self.created_timestamp = datetime.datetime.now()
        self.track_id: str = None
        self.name: str = None
        self.duration: int = None
        self.explicit: bool = False
        self.user_date_added: datetime = None
        self.track_num: int = 1
        self.volume_num: int = 1
        self.artist_id: str = None
        self.artist_name: str = None
        self.album_id: str = None
        self.album_name: str = None
