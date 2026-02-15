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
from column_name import ColumnName


class MetadataModelData:

    def __init__(
            self,
            column_name: ColumnName,
            primary_key: bool = False,
            calculated: bool = False,
            is_created_timestamp: bool = False,
            is_updated_timestamp: bool = False):
        self.__column_name: ColumnName = column_name
        self.__primary_key: bool = primary_key
        self.__calculated: bool = calculated
        self.__is_created_timestamp: bool = is_created_timestamp
        self.__is_updated_timestamp: bool = is_updated_timestamp

    @property
    def column_name(self) -> ColumnName:
        return self.__column_name

    @property
    def primary_key(self) -> bool:
        return self.__primary_key

    @property
    def calculated(self) -> bool:
        return self.__calculated

    @property
    def is_created_timestamp(self) -> bool:
        return self.__is_created_timestamp

    @property
    def is_updated_timestamp(self) -> bool:
        return self.__is_updated_timestamp


class ArtistMetadataModel(Enum):

    ARTIST_ID = MetadataModelData(
        column_name=ColumnName.ARTIST_ID,
        primary_key=True)
    ARTIST_NAME = MetadataModelData(column_name=ColumnName.ARTIST_NAME)
    ARTIST_MB_ID = MetadataModelData(column_name=ColumnName.ARTIST_MB_ID)
    ARTIST_ALBUM_COUNT = MetadataModelData(column_name=ColumnName.ARTIST_ALBUM_COUNT)
    ARTIST_COVER_ART = MetadataModelData(column_name=ColumnName.ARTIST_COVER_ART)
    ARTIST_MEDIA_TYPE = MetadataModelData(column_name=ColumnName.ARTIST_MEDIA_TYPE)
    ARTIST_SORT_NAME = MetadataModelData(column_name=ColumnName.ARTIST_SORT_NAME)
    CREATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.CREATED_TIMESTAMP,
        is_created_timestamp=True)
    UPDATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.UPDATED_TIMESTAMP,
        is_updated_timestamp=True)

    @property
    def column_name(self) -> ColumnName:
        return self.value.column_name

    @property
    def primary_key(self) -> bool:
        return self.value.primary_key

    @property
    def calculated(self) -> bool:
        return self.value.calculated

    @property
    def is_created_timestamp(self) -> bool:
        return self.value.is_created_timestamp

    @property
    def is_updated_timestamp(self) -> bool:
        return self.value.is_updated_timestamp


class AlbumMetadataModel(Enum):

    ALBUM_ID = MetadataModelData(column_name=ColumnName.ALBUM_ID, primary_key=True)
    QUALITY_BADGE = MetadataModelData(
        column_name=ColumnName.QUALITY_BADGE,
        calculated=True)
    ALBUM_MB_ID = MetadataModelData(column_name=ColumnName.ALBUM_MB_ID)
    ALBUM_ARTIST_ID = MetadataModelData(column_name=ColumnName.ALBUM_ARTIST_ID)
    ALBUM_PATH = MetadataModelData(column_name=ColumnName.ALBUM_PATH, calculated=True)
    ALBUM_ARTIST = MetadataModelData(column_name=ColumnName.ALBUM_ARTIST)
    ALBUM_NAME = MetadataModelData(column_name=ColumnName.ALBUM_NAME)
    ALBUM_COVER_ART = MetadataModelData(column_name=ColumnName.ALBUM_COVER_ART)
    ALBUM_DISC_COUNT = MetadataModelData(column_name=ColumnName.ALBUM_DISC_COUNT)
    ALBUM_SONG_COUNT = MetadataModelData(column_name=ColumnName.ALBUM_SONG_COUNT)
    ALBUM_DURATION = MetadataModelData(column_name=ColumnName.ALBUM_DURATION)
    ALBUM_CREATED = MetadataModelData(column_name=ColumnName.ALBUM_CREATED)
    ALBUM_YEAR = MetadataModelData(column_name=ColumnName.ALBUM_YEAR)
    ALBUM_GENRE = MetadataModelData(column_name=ColumnName.ALBUM_GENRE)
    ALBUM_GENRE_LIST = MetadataModelData(column_name=ColumnName.ALBUM_GENRE_LIST)
    ALBUM_USER_RATING = MetadataModelData(column_name=ColumnName.ALBUM_USER_RATING)
    ALBUM_DISPLAY_ARTIST = MetadataModelData(column_name=ColumnName.ALBUM_DISPLAY_ARTIST)
    ALBUM_EXPLICIT_STATUS = MetadataModelData(column_name=ColumnName.EXPLICIT_STATUS)
    ALBUM_IS_COMPILATION = MetadataModelData(column_name=ColumnName.ALBUM_IS_COMPILATION)
    ALBUM_PLAY_COUNT = MetadataModelData(column_name=ColumnName.ALBUM_PLAY_COUNT)
    ALBUM_PLAYED = MetadataModelData(column_name=ColumnName.ALBUM_PLAYED)
    ALBUM_SORT_NAME = MetadataModelData(column_name=ColumnName.ALBUM_SORT_NAME)
    ALBUM_VERSION = MetadataModelData(column_name=ColumnName.ALBUM_VERSION)
    ALBUM_ORIGINAL_RELEASE_DATE_YEAR = MetadataModelData(column_name=ColumnName.ALBUM_ORIGINAL_RELEASE_DATE_YEAR)
    ALBUM_ORIGINAL_RELEASE_DATE_MONTH = MetadataModelData(column_name=ColumnName.ALBUM_ORIGINAL_RELEASE_DATE_MONTH)
    ALBUM_ORIGINAL_RELEASE_DATE_DAY = MetadataModelData(column_name=ColumnName.ALBUM_ORIGINAL_RELEASE_DATE_DAY)
    ALBUM_ORIGINAL_RELEASE_DATE_STR = MetadataModelData(column_name=ColumnName.ALBUM_ORIGINAL_RELEASE_DATE_STR, calculated=True)
    ALBUM_RELEASE_DATE_YEAR = MetadataModelData(column_name=ColumnName.ALBUM_RELEASE_DATE_YEAR)
    ALBUM_RELEASE_DATE_MONTH = MetadataModelData(column_name=ColumnName.ALBUM_RELEASE_DATE_MONTH)
    ALBUM_RELEASE_DATE_DAY = MetadataModelData(column_name=ColumnName.ALBUM_RELEASE_DATE_DAY)
    ALBUM_RELEASE_DATE_STR = MetadataModelData(column_name=ColumnName.ALBUM_RELEASE_DATE_STR, calculated=True)
    ALBUM_TRACK_QUALITY_SUMMARY = MetadataModelData(
        column_name=ColumnName.ALBUM_TRACK_QUALITY_SUMMARY,
        calculated=True)
    ALBUM_AVERAGE_BITRATE = MetadataModelData(
        column_name=ColumnName.ALBUM_AVERAGE_BITRATE,
        calculated=True)
    ALBUM_LOSSLESS_STATUS = MetadataModelData(
        column_name=ColumnName.ALBUM_LOSSLESS_STATUS,
        calculated=True)
    ALBUM_MOOD_LIST = MetadataModelData(column_name=ColumnName.ALBUM_MOOD_LIST)
    ALBUM_RECORD_LABEL_LIST = MetadataModelData(column_name=ColumnName.ALBUM_RECORD_LABEL_LIST)
    ALBUM_RELEASE_TYPE_LIST = MetadataModelData(column_name=ColumnName.ALBUM_RELEASE_TYPE_LIST)
    ALBUM_MEDIA_TYPE = MetadataModelData(column_name=ColumnName.ALBUM_MEDIA_TYPE)
    CREATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.CREATED_TIMESTAMP,
        is_created_timestamp=True)
    UPDATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.UPDATED_TIMESTAMP,
        is_updated_timestamp=True)

    @property
    def column_name(self) -> ColumnName:
        return self.value.column_name

    @property
    def primary_key(self) -> bool:
        return self.value.primary_key

    @property
    def calculated(self) -> bool:
        return self.value.calculated

    @property
    def is_created_timestamp(self) -> bool:
        return self.value.is_created_timestamp

    @property
    def is_updated_timestamp(self) -> bool:
        return self.value.is_updated_timestamp


class SongMetadataModel(Enum):

    SONG_ID = MetadataModelData(column_name=ColumnName.SONG_ID, primary_key=True)
    SONG_TITLE = MetadataModelData(column_name=ColumnName.SONG_TITLE)
    SONG_ALBUM_ID = MetadataModelData(column_name=ColumnName.SONG_ALBUM_ID)
    SONG_ARTIST_ID = MetadataModelData(column_name=ColumnName.SONG_ARTIST_ID)
    SONG_ARTIST = MetadataModelData(column_name=ColumnName.SONG_ARTIST)
    SONG_COMMENT = MetadataModelData(column_name=ColumnName.SONG_COMMENT)
    SONG_BITDEPTH = MetadataModelData(column_name=ColumnName.SONG_BITDEPTH)
    SONG_BITRATE = MetadataModelData(column_name=ColumnName.SONG_BITRATE)
    SONG_CHANNEL_COUNT = MetadataModelData(column_name=ColumnName.SONG_CHANNEL_COUNT)
    SONG_SAMPLING_RATE = MetadataModelData(column_name=ColumnName.SONG_SAMPLING_RATE)
    SONG_SIZE = MetadataModelData(column_name=ColumnName.SONG_SIZE)
    SONG_SUFFIX = MetadataModelData(column_name=ColumnName.SONG_SUFFIX)
    SONG_DISC_NUMBER = MetadataModelData(column_name=ColumnName.SONG_DISC_NUMBER)
    SONG_TRACK = MetadataModelData(column_name=ColumnName.SONG_TRACK)
    SONG_TYPE = MetadataModelData(column_name=ColumnName.SONG_TYPE)
    SONG_DURATION = MetadataModelData(column_name=ColumnName.SONG_DURATION)
    SONG_CONTENT_TYPE = MetadataModelData(column_name=ColumnName.SONG_CONTENT_TYPE)
    SONG_COVER_ART = MetadataModelData(column_name=ColumnName.SONG_COVER_ART)
    SONG_CREATED = MetadataModelData(column_name=ColumnName.SONG_CREATED)
    SONG_DISPLAY_ALBUM_ARTIST = MetadataModelData(column_name=ColumnName.SONG_DISPLAY_ALBUM_ARTIST)
    SONG_DISPLAY_ARTIST = MetadataModelData(column_name=ColumnName.SONG_DISPLAY_ARTIST)
    SONG_EXPLICIT_STATUS = MetadataModelData(column_name=ColumnName.SONG_EXPLICIT_STATUS)
    SONG_GENRE = MetadataModelData(column_name=ColumnName.SONG_GENRE)
    SONG_IS_DIR = MetadataModelData(column_name=ColumnName.SONG_IS_DIR)
    SONG_MEDIA_TYPE = MetadataModelData(column_name=ColumnName.SONG_MEDIA_TYPE)
    SONG_MUSICBRAINZ_ID = MetadataModelData(column_name=ColumnName.SONG_MUSICBRAINZ_ID)
    SONG_PATH = MetadataModelData(column_name=ColumnName.SONG_PATH)
    SONG_PLAY_COUNT = MetadataModelData(column_name=ColumnName.SONG_PLAY_COUNT)
    SONG_PLAYED = MetadataModelData(column_name=ColumnName.SONG_PLAYED)
    SONG_YEAR = MetadataModelData(column_name=ColumnName.SONG_YEAR)
    SONG_DISPLAY_COMPOSER = MetadataModelData(column_name=ColumnName.SONG_DISPLAY_COMPOSER)
    SONG_SORT_NAME = MetadataModelData(column_name=ColumnName.SONG_SORT_NAME)
    SONG_LOSSLESS_STATUS = MetadataModelData(column_name=ColumnName.SONG_LOSSLESS_STATUS)
    CREATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.CREATED_TIMESTAMP,
        is_created_timestamp=True)
    UPDATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.UPDATED_TIMESTAMP,
        is_updated_timestamp=True)

    @property
    def column_name(self) -> ColumnName:
        return self.value.column_name

    @property
    def primary_key(self) -> bool:
        return self.value.primary_key

    @property
    def calculated(self) -> bool:
        return self.value.calculated

    @property
    def is_created_timestamp(self) -> bool:
        return self.value.is_created_timestamp

    @property
    def is_updated_timestamp(self) -> bool:
        return self.value.is_updated_timestamp


class SongAlbumArtistMetaModel(Enum):

    ID = MetadataModelData(column_name=ColumnName.ID, primary_key=True)
    SONG_ID = MetadataModelData(column_name=ColumnName.SONG_ID)
    SONG_ALBUM_ID = MetadataModelData(column_name=ColumnName.SONG_ALBUM_ID)
    SONG_ALBUM_ARTIST_ID = MetadataModelData(column_name=ColumnName.SONG_ALBUM_ARTIST_ID)
    CREATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.CREATED_TIMESTAMP,
        is_created_timestamp=True)

    @property
    def column_name(self) -> ColumnName:
        return self.value.column_name

    @property
    def calculated(self) -> bool:
        return self.value.calculated

    @property
    def is_created_timestamp(self) -> bool:
        return self.value.is_created_timestamp

    @property
    def is_updated_timestamp(self) -> bool:
        return self.value.is_updated_timestamp


class SongArtistMetaModel(Enum):

    ID = MetadataModelData(column_name=ColumnName.ID, primary_key=True)
    SONG_ID = MetadataModelData(column_name=ColumnName.SONG_ID)
    SONG_ALBUM_ID = MetadataModelData(column_name=ColumnName.SONG_ALBUM_ID)
    SONG_ARTIST_ID = MetadataModelData(column_name=ColumnName.SONG_ARTIST_ID)
    CREATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.CREATED_TIMESTAMP,
        is_created_timestamp=True)

    @property
    def column_name(self) -> ColumnName:
        return self.value.column_name

    @property
    def calculated(self) -> bool:
        return self.value.calculated

    @property
    def is_created_timestamp(self) -> bool:
        return self.value.is_created_timestamp

    @property
    def is_updated_timestamp(self) -> bool:
        return self.value.is_updated_timestamp


class SongContributorMetaModel(Enum):

    ID = MetadataModelData(column_name=ColumnName.ID)
    SONG_ID = MetadataModelData(column_name=ColumnName.SONG_ID)
    SONG_ALBUM_ID = MetadataModelData(column_name=ColumnName.SONG_ALBUM_ID)
    SONG_CONTRIBUTOR_ROLE = MetadataModelData(column_name=ColumnName.SONG_CONTRIBUTOR_ROLE)
    SONG_CONTRIBUTOR_SUB_ROLE = MetadataModelData(column_name=ColumnName.SONG_CONTRIBUTOR_SUB_ROLE)
    SONG_ARTIST_ID = MetadataModelData(column_name=ColumnName.SONG_ARTIST_ID)
    CREATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.CREATED_TIMESTAMP,
        is_created_timestamp=True)

    @property
    def column_name(self) -> ColumnName:
        return self.value.column_name

    @property
    def calculated(self) -> bool:
        return self.value.calculated

    @property
    def is_created_timestamp(self) -> bool:
        return self.value.is_created_timestamp

    @property
    def is_updated_timestamp(self) -> bool:
        return self.value.is_updated_timestamp


class AlbumPropertyMetaModel(Enum):

    ALBUM_ID = MetadataModelData(column_name=ColumnName.ALBUM_ID)
    ALBUM_PROPERTY_KEY = MetadataModelData(column_name=ColumnName.ALBUM_PROPERTY_KEY)
    ALBUM_PROPERTY_VALUE = MetadataModelData(column_name=ColumnName.ALBUM_PROPERTY_VALUE)
    CREATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.CREATED_TIMESTAMP,
        is_created_timestamp=True)
    UPDATED_TIMESTAMP = MetadataModelData(
        column_name=ColumnName.UPDATED_TIMESTAMP,
        is_updated_timestamp=True)

    @property
    def column_name(self) -> ColumnName:
        return self.value.column_name

    @property
    def calculated(self) -> bool:
        return self.value.calculated

    @property
    def is_created_timestamp(self) -> bool:
        return self.value.is_created_timestamp

    @property
    def is_updated_timestamp(self) -> bool:
        return self.value.is_updated_timestamp
