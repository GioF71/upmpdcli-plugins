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
from keyvaluecaching import KeyValueTableName


class DeletedTableName(Enum):

    ALBUM_COVER_ART_BY_ARTIST_V1 = "album_cover_art_by_artist_v1"


class TableName(Enum):
    ALBUM_METADATA_V1 = "album_metadata_v1"
    ARTIST_METADATA_V1 = "artist_metadata_v1"
    ARTIST_ROLE_V1 = "artist_role_v1"
    ALBUM_ARTIST_V1 = "album_artist_v1"
    ALBUM_DISC_V1 = "album_disc_v1"
    ALBUM_GENRE_V1 = "album_genre_v1"
    ALBUM_RECORD_LABEL_V1 = "album_record_label_v1"
    ALBUM_MOOD_V1 = "album_mood_v1"
    ALBUM_RELEASE_TYPE_V1 = "album_release_type_v1"
    SONG_METADATA_V1 = "song_metadata_v1"
    KV_CACHE_V1 = KeyValueTableName.TABLE_NAME_V1.table_name
    SONG_ALBUM_ARTIST_V1 = "song_album_artist_v1"
    SONG_ARTIST_V1 = "song_artist_v1"
    SONG_CONTRIBUTOR_V1 = "song_contributor_v1"
    ALBUM_PROPERTY_V1 = "album_property_v1"
    DB_VERSION = "db_version"
