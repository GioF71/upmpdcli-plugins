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


class AlbumMetadata:

    def __init__(self):
        self.created_timestamp = datetime.datetime.now()
        self.album_id: str = None
        self.album_name: str = None
        self.artist_id: str = None
        self.artist_name: str = None
        self.explicit: int = None
        self.release_date: datetime = None
        self.available_release_date: datetime = None
        self.image_url: str = None
        # comma separated values
        self.audio_modes: str = None
        self.audio_quality: str = None
        # comma separated values
        self.media_metadata_tags: str = None
        self.album_duration: int = None
        self.num_volumes: int = None
        self.num_tracks: int = None
        self.user_date_added: datetime = None
        self.created_timestamp: datetime = None
        self.artist_id_list: list[str] = []
        self.artist_name_list: list[str] = []
        self.artist_image_url_list: list[str] = []
