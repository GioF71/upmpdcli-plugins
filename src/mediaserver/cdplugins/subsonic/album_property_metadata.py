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


from metadata_model import AlbumPropertyMetaModel
from typing import Any
import datetime


class AlbumPropertyMetadata:

    def __init__(
            self,
            album_id: str,
            key: str,
            value: str,
            created: datetime.datetime,
            updated: datetime.datetime):
        self.__album_id: str = album_id
        self.__key: str = key
        self.__value: str = value
        self.__created: datetime.datetime = created
        self.__updated: datetime.datetime = updated

    def set_value(self, album_metadata_model: AlbumPropertyMetaModel, value: Any):
        return self._set(album_metadata_model.column_name, value)

    @property
    def album_id(self) -> str:
        return self.__album_id

    @property
    def album_property_key(self) -> str:
        return self.__key

    @property
    def album_property_value(self) -> str:
        return self.__value

    @property
    def created_timestamp(self) -> datetime.datetime:
        return self.__created

    @property
    def updated_timestamp(self) -> datetime.datetime:
        return self.__updated
