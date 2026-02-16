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
from metadata_model import AlbumMetadataModel
from typing import Optional
from typing import Any
import datetime


class AlbumMetadata(Metadata):

    def get_value(self, album_metadata_model: AlbumMetadataModel, dflt: Any = None) -> Optional[Any]:
        v: Any = self._get(album_metadata_model.column_name)
        if v is None and dflt is not None:
            v = dflt
        return v

    def set_value(self, album_metadata_model: AlbumMetadataModel, value: Any):
        return self._set(album_metadata_model.column_name, value)

    @property
    def album_id(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_ID)

    @property
    def quality_badge(self) -> str:
        return self.get_value(AlbumMetadataModel.QUALITY_BADGE)

    @property
    def album_media_type(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_MEDIA_TYPE)

    @property
    def album_lossless_status(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_LOSSLESS_STATUS)

    @property
    def album_average_bitrate(self) -> int:
        return self.get_value(AlbumMetadataModel.ALBUM_AVERAGE_BITRATE)

    @property
    def album_musicbrainz_id(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_MB_ID)

    @property
    def album_artist_id(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_ARTIST_ID)

    @property
    def album_path(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_PATH)

    @property
    def album_artist(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_ARTIST)

    @property
    def album_version(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_VERSION)

    @property
    def album_cover_art(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_COVER_ART)

    @property
    def album_name(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_NAME)

    @property
    def album_disc_count(self) -> int:
        return self.get_value(AlbumMetadataModel.ALBUM_DISC_COUNT)

    @property
    def album_song_count(self) -> int:
        return self.get_value(AlbumMetadataModel.ALBUM_SONG_COUNT)

    @property
    def album_duration(self) -> int:
        return self.get_value(AlbumMetadataModel.ALBUM_DURATION)

    @property
    def album_created(self) -> datetime.datetime:
        return self.get_value(AlbumMetadataModel.ALBUM_CREATED)

    @property
    def album_year(self) -> int:
        return self.get_value(AlbumMetadataModel.ALBUM_YEAR)

    @property
    def album_genre(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_GENRE)

    @property
    def album_genre_list(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_GENRE_LIST)

    @property
    def album_mood_list(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_MOOD_LIST)

    @property
    def album_record_label_list(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_RECORD_LABEL_LIST)

    @property
    def album_release_type_list(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_RELEASE_TYPE_LIST)

    @property
    def album_user_rating(self) -> int:
        return self.get_value(AlbumMetadataModel.ALBUM_USER_RATING)

    @property
    def album_display_artist(self) -> int:
        return self.get_value(AlbumMetadataModel.ALBUM_DISPLAY_ARTIST)

    @property
    def album_explicit_status(self) -> int:
        return self.get_value(AlbumMetadataModel.ALBUM_EXPLICIT_STATUS)

    @property
    def album_track_quality_summary(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_TRACK_QUALITY_SUMMARY)

    @property
    def album_release_date_str(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_RELEASE_DATE_STR, "")

    @property
    def album_original_release_date_str(self) -> str:
        return self.get_value(AlbumMetadataModel.ALBUM_ORIGINAL_RELEASE_DATE_STR, "")

    @property
    def created_timestamp(self) -> datetime.datetime:
        return self.get_value(AlbumMetadataModel.CREATED_TIMESTAMP)

    @property
    def updated_timestamp(self) -> datetime.datetime:
        return self.get_value(AlbumMetadataModel.UPDATED_TIMESTAMP)
