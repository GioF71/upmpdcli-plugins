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
from metadata_model import SongMetadataModel
from typing import Optional
from typing import Any
import datetime


class SongMetadata(Metadata):

    def get_value(self, song_metadata_model: SongMetadataModel) -> Optional[Any]:
        return self._get(song_metadata_model.column_name)

    def set_value(self, song_metadata_model: SongMetadataModel, value: Any):
        return self._set(song_metadata_model.column_name, value)

    @property
    def song_id(self) -> str:
        return self.get_value(SongMetadataModel.SONG_ID)

    @property
    def album_id(self) -> str:
        return self.get_value(SongMetadataModel.SONG_ALBUM_ID)

    @property
    def created_timestamp(self) -> datetime.datetime:
        return self.get_value(SongMetadataModel.CREATED_TIMESTAMP)

    @property
    def updated_timestamp(self) -> datetime.datetime:
        return self.get_value(SongMetadataModel.UPDATED_TIMESTAMP)
