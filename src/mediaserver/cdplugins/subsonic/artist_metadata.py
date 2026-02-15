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
from metadata_model import ArtistMetadataModel
from typing import Optional
from typing import Any
import datetime


class ArtistMetadata(Metadata):

    def get_value(self, artist_metadata_model: ArtistMetadataModel) -> Optional[Any]:
        return self._get(artist_metadata_model.column_name)

    def set_value(self, artist_metadata_model: ArtistMetadataModel, value: Any):
        return self._set(artist_metadata_model.column_name, value)

    @property
    def artist_id(self) -> str:
        return self.get_value(ArtistMetadataModel.ARTIST_ID)

    @property
    def artist_name(self) -> str:
        return self.get_value(ArtistMetadataModel.ARTIST_NAME)

    @property
    def artist_musicbrainz_id(self) -> str:
        return self.get_value(ArtistMetadataModel.ARTIST_MB_ID)

    @property
    def artist_album_count(self) -> int:
        return self.get_value(ArtistMetadataModel.ARTIST_ALBUM_COUNT)

    @property
    def artist_cover_art(self) -> str:
        return self.get_value(ArtistMetadataModel.ARTIST_COVER_ART)

    @property
    def artist_media_type(self) -> str:
        return self.get_value(ArtistMetadataModel.ARTIST_MEDIA_TYPE)

    @property
    def artist_sort_name(self) -> str:
        return self.get_value(ArtistMetadataModel.ARTIST_SORT_NAME)

    @property
    def created_timestamp(self) -> datetime.datetime:
        return self.get_value(ArtistMetadataModel.CREATED_TIMESTAMP)

    @property
    def updated_timestamp(self) -> datetime.datetime:
        return self.get_value(ArtistMetadataModel.UPDATED_TIMESTAMP)

    def update(
            self,
            artist_name: str,
            artist_musicbrainz_id: str,
            artist_album_count: int = None,
            artist_cover_art: str = None,
            artist_media_type: str = None,
            artist_sort_name: str = None):
        any_update: bool = False
        if artist_name and len(artist_name) > 0:
            self.set_value(ArtistMetadataModel.ARTIST_NAME, artist_name)
            any_update = True
        if artist_musicbrainz_id and len(artist_musicbrainz_id) > 0:
            self.set_value(ArtistMetadataModel.ARTIST_MB_ID, artist_musicbrainz_id)
            any_update = True
        if artist_album_count:
            self.set_value(ArtistMetadataModel.ARTIST_ALBUM_COUNT, artist_album_count)
            any_update = True
        if artist_cover_art:
            self.set_value(ArtistMetadataModel.ARTIST_COVER_ART, artist_cover_art)
            any_update = True
        if artist_media_type:
            self.set_value(ArtistMetadataModel.ARTIST_MEDIA_TYPE, artist_media_type)
            any_update = True
        if artist_sort_name:
            self.set_value(ArtistMetadataModel.ARTIST_SORT_NAME, artist_sort_name)
            any_update = True
        if any_update:
            self.set_value(ArtistMetadataModel.UPDATED_TIMESTAMP, datetime.datetime.now())
