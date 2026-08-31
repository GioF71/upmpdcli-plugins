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


from enum import Enum


class _ColumnData:

    def __init__(self, column_name: str, column_type: str):
        self.__column_name: str = column_name
        self.__column_type: str = column_type

    @property
    def column_name(self) -> str:
        return self.__column_name

    @property
    def column_type(self) -> str:
        return self.__column_type


class Column(Enum):

    CREATED_TIMESTAMP = _ColumnData(column_name="created_timestamp", column_type="TIMESTAMP")
    ALBUM_DURATION = _ColumnData(column_name="duration", column_type="INTEGER")
    NUM_VOLUMES = _ColumnData(column_name="num_volumes", column_type="INTEGER")
    NUM_TRACKS = _ColumnData(column_name="num_tracks", column_type="INTEGER")
    USER_DATE_ADDED = _ColumnData(column_name="user_date_added", column_type="TIMESTAMP")
    ARTIST_ID_LIST = _ColumnData(column_name="artist_id_list", column_type="TEXT")
    ARTIST_NAME_LIST = _ColumnData(column_name="artist_name_list", column_type="TEXT")
    ARTIST_IMAGE_URL_LIST = _ColumnData(column_name="artist_image_url_list", column_type="TEXT")
    ALBUM_ID = _ColumnData(column_name="album_id", column_type="TEXT")
    ALBUM_NAME = _ColumnData(column_name="album_name", column_type="TEXT")
    ARTIST_ID = _ColumnData(column_name="artist_id", column_type="TEXT")
    ARTIST_NAME = _ColumnData(column_name="artist_name", column_type="TEXT")
    TRACK_ID = _ColumnData(column_name="track_id", column_type="TEXT")
    TRACK_NAME = _ColumnData(column_name="track_name", column_type="TEXT")
    NAME = _ColumnData(column_name="name", column_type="TEXT")
    TRACK_DURATION = _ColumnData(column_name="track_duration", column_type="INTEGER")
    EXPLICIT = _ColumnData(column_name="explicit", column_type="INTEGER")
    TRACK_NUM = _ColumnData(column_name="track_num", column_type="INTEGER")
    VOLUME_NUM = _ColumnData(column_name="volume_num", column_type="INTEGER")

    @property
    def column_name(self) -> str:
        return self.value.column_name

    @property
    def column_type(self) -> str:
        return self.value.column_type
