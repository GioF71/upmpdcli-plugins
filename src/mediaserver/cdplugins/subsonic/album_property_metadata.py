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


from metadata import Metadata
from metadata_model import AlbumPropertyMetaModel
from typing import Optional
from typing import Any
import datetime


class AlbumPropertyMetadata(Metadata):

    def get_value(self, album_metadata_model: AlbumPropertyMetaModel) -> Optional[Any]:
        return self._get(album_metadata_model.column_name)

    def set_value(self, album_metadata_model: AlbumPropertyMetaModel, value: Any):
        return self._set(album_metadata_model.column_name, value)

    @property
    def id(self) -> str:
        return self.get_value(AlbumPropertyMetaModel.ALBUM_ID)

    @property
    def album_id(self) -> str:
        return self.get_value(AlbumPropertyMetaModel.ALBUM_ID)

    @property
    def album_property_key(self) -> str:
        return self.get_value(AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY)

    @property
    def album_property_value(self) -> str:
        return self.get_value(AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE)

    @property
    def created_timestamp(self) -> datetime.datetime:
        return self.get_value(AlbumPropertyMetaModel.CREATED_TIMESTAMP)

    @property
    def updated_timestamp(self) -> datetime.datetime:
        return self.get_value(AlbumPropertyMetaModel.UPDATED_TIMESTAMP)
