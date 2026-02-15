# Copyright (C) 2023,2024,2025,2026 Giovanni Fulco
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

import os
import sqlite3
import sqlite3util
import datetime
import time
import secrets

from typing import Callable
from typing import Any

import upmplgutils

from persistence_tuple import CoverSource
from persistence_tuple import get_cover_source_by_name
from persistence_tuple import ArtistAlbumCoverArt
from persistence_tuple import AlbumPropertyValueSelection
from keyvaluecaching import KeyValueItem
from keyvaluecaching import KeyValueTableName
from keyvaluecaching import build_create_v1_sql as build_create_cache_v1_sql
from keyvaluecaching import get_key_value_item
from keyvaluecaching import put_key_value_item
from keyvaluecaching import load_kv_item_v1
from keyvaluecaching import insert_kv_item_v1
from keyvaluecaching import update_kv_item_v1
from keyvaluecaching import delete_kv_item_v1
from keyvaluecaching import KeyValueCacheColumnName
from cache_type import CacheType
import sqlhelper

import constants
import config
import metadata_converter

from column_name import ColumnName
from metadata_model import ArtistMetadataModel
from metadata_model import AlbumMetadataModel
from metadata_model import SongMetadataModel
from metadata_model import SongAlbumArtistMetaModel
from metadata_model import SongArtistMetaModel
from metadata_model import SongContributorMetaModel
from metadata_model import AlbumPropertyMetaModel
from artist_metadata import ArtistMetadata
from album_metadata import AlbumMetadata
from album_property_metadata import AlbumPropertyMetadata
from song_metadata import SongMetadata
from table_name import TableName
from table_name import DeletedTableName
from enum import Enum
from artist_from_album import ArtistFromAlbum
from disc_title import DiscTitle
from song_data_structures import SongArtist
from song_data_structures import SongContributor

from album_property_key import AlbumPropertyKeyValue

from msgproc_provider import msgproc


def __create_qmark_list(num_qmark: int) -> str:
    return ", ".join(["?"] * num_qmark)


def __adapt_flexible_timestamp(ts_bytes):
    """
    This function receives bytes from SQLite and converts them to a datetime object.
    """
    if not ts_bytes:
        return None
    # SQLite gives us bytes, so decode to string
    ts_str = ts_bytes.decode('utf-8')
    # Use the flexible logic we built earlier
    ts_str = ts_str.strip().replace('Z', '+00:00')
    try:
        # Standardize space to T for broader compatibility
        return datetime.datetime.fromisoformat(ts_str.replace(' ', 'T'))
    except ValueError:
        # Fallback for specific formats
        if '.' in ts_str:
            return datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f%z")
        return datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S%z")


class SaveMode(Enum):
    UPDATED = 1
    INSERTED = 0


__artist_metadata_model_list: list[ArtistMetadataModel] = list(ArtistMetadataModel)
__artist_metadata_model_pk_list: list[ArtistMetadataModel] = list(filter(
    lambda x: x.primary_key,
    __artist_metadata_model_list))
__artist_metadata_model_non_pk_list: list[ArtistMetadataModel] = list(filter(
    lambda x: not x.primary_key,
    __artist_metadata_model_list))

__artist_metadata_model_all_column_names: list[str] = list(map(
    lambda x: x.column_name.value,
    __artist_metadata_model_list))

__artist_metadata_model_pk_column_names: list[str] = list(map(
    lambda x: x.column_name.value,
    __artist_metadata_model_pk_list))
__artist_metadata_model_non_pk_column_names: list[str] = list(map(
    lambda x: x.column_name.value,
    __artist_metadata_model_non_pk_list))


__album_metadata_model_list: list[AlbumMetadataModel] = list(AlbumMetadataModel)
__album_metadata_model_pk_list: list[AlbumMetadataModel] = list(filter(
    lambda x: x.primary_key,
    __album_metadata_model_list))
__album_metadata_model_non_pk_list: list[AlbumMetadataModel] = list(filter(
    lambda x: not x.primary_key,
    __album_metadata_model_list))

__album_metadata_model_all_column_names: list[str] = list(map(lambda x: x.column_name.value, __album_metadata_model_list))

__album_metadata_model_pk_column_names: list[str] = list(map(lambda x: x.column_name.value, __album_metadata_model_pk_list))
__album_metadata_model_non_pk_column_names: list[str] = list(map(lambda x: x.column_name.value, __album_metadata_model_non_pk_list))


__song_metadata_model_list: list[SongMetadataModel] = list(SongMetadataModel)
__song_metadata_model_pk_list: list[SongMetadataModel] = list(filter(
    lambda x: x.primary_key,
    __song_metadata_model_list))
__song_metadata_model_non_pk_list: list[SongMetadataModel] = list(filter(
    lambda x: not x.primary_key,
    __song_metadata_model_list))

__song_metadata_model_all_column_names: list[str] = list(map(lambda x: x.column_name.value, __song_metadata_model_list))

__song_metadata_model_pk_column_names: list[str] = list(map(lambda x: x.column_name.value, __song_metadata_model_pk_list))
__song_metadata_model_non_pk_column_names: list[str] = list(map(lambda x: x.column_name.value, __song_metadata_model_non_pk_list))


def __song_metadata_by_row(row) -> AlbumMetadata:
    lst: list[SongMetadataModel] = __song_metadata_model_list
    song_metadata: SongMetadata = SongMetadata()
    meta: SongMetadataModel
    for meta in SongMetadataModel:
        song_metadata.set_value(song_metadata_model=meta, value=row[lst.index(meta)])
    return song_metadata


def __artist_metadata_by_row(row) -> ArtistMetadata:
    lst: list[ArtistMetadataModel] = __artist_metadata_model_list
    artist_metadata: ArtistMetadata = ArtistMetadata()
    meta: ArtistMetadataModel
    for meta in ArtistMetadataModel:
        artist_metadata.set_value(artist_metadata_model=meta, value=row[lst.index(meta)])
    return artist_metadata


def __album_metadata_by_row(row) -> AlbumMetadata:
    lst: list[AlbumMetadataModel] = __album_metadata_model_list
    album_metadata: AlbumMetadata = AlbumMetadata()
    meta: AlbumMetadataModel
    for meta in AlbumMetadataModel:
        album_metadata.set_value(album_metadata_model=meta, value=row[lst.index(meta)])
    return album_metadata


class ArtistRole:

    def __init__(
            self,
            artist_id: str,
            artist_role: str):
        self.__artist_id: str = artist_id
        self.__artist_role: str = artist_role

    @property
    def artist_id(self) -> str:
        return self.__artist_id

    @property
    def artist_role(self) -> str:
        return self.__artist_role


def __get_sql_create_table_album_art_by_artist_v1() -> str:
    return f"""
        CREATE TABLE {DeletedTableName.ALBUM_COVER_ART_BY_ARTIST_V1.value}(
        {ColumnName.ARTIST_ID.value} VARCHAR(255),
        {ColumnName.ALBUM_ID.value} VARCHAR(255),
        {ColumnName.ALBUM_COVER_ART.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (
            {ColumnName.ARTIST_ID.value},
            {ColumnName.ALBUM_ID.value}),
        FOREIGN KEY ({ColumnName.ARTIST_ID.value})
            REFERENCES {TableName.ARTIST_METADATA_V1.value}({ColumnName.ARTIST_ID.value})
            ON DELETE CASCADE
        FOREIGN KEY ({ColumnName.ALBUM_ID.value})
            REFERENCES {TableName.ALBUM_METADATA_V1.value}({ColumnName.ALBUM_ID.value})
            ON DELETE CASCADE);
    """


def __get_sql_create_table_song_metadata_v1() -> str:
    return f"""
        CREATE TABLE {TableName.SONG_METADATA_V1.value}(
        {ColumnName.SONG_ID.value} VARCHAR(255),
        {ColumnName.SONG_TITLE.value} TEXT,
        {ColumnName.SONG_ALBUM_ID.value} VARCHAR(255),
        {ColumnName.SONG_ARTIST_ID.value} VARCHAR(255),
        {ColumnName.SONG_ARTIST.value} TEXT,
        {ColumnName.SONG_COMMENT.value} TEXT,
        {ColumnName.SONG_BITDEPTH.value} INTEGER,
        {ColumnName.SONG_BITRATE.value} INTEGER,
        {ColumnName.SONG_CHANNEL_COUNT.value} INTEGER,
        {ColumnName.SONG_SAMPLING_RATE.value} INTEGER,
        {ColumnName.SONG_SIZE.value} INTEGER,
        {ColumnName.SONG_SUFFIX.value} VARCHAR(32),
        {ColumnName.SONG_DISC_NUMBER.value} INTEGER,
        {ColumnName.SONG_TRACK.value} INTEGER,
        {ColumnName.SONG_TYPE.value} VARCHAR(32),
        {ColumnName.SONG_DURATION.value} INTEGER,
        {ColumnName.SONG_CONTENT_TYPE.value} VARCHAR(32),
        {ColumnName.SONG_COVER_ART.value} TEXT,
        {ColumnName.SONG_CREATED.value} TIMESTAMP,
        {ColumnName.SONG_DISPLAY_ALBUM_ARTIST.value} TEXT,
        {ColumnName.SONG_DISPLAY_ARTIST.value} TEXT,
        {ColumnName.SONG_EXPLICIT_STATUS.value} VARCHAR(64),
        {ColumnName.SONG_GENRE.value} TEXT,
        {ColumnName.SONG_IS_DIR.value} INTEGER,
        {ColumnName.SONG_MEDIA_TYPE.value} VARCHAR(64),
        {ColumnName.SONG_MUSICBRAINZ_ID.value} VARCHAR(64),
        {ColumnName.SONG_PATH.value} TEXT,
        {ColumnName.SONG_PLAY_COUNT.value} INTEGER,
        {ColumnName.SONG_PLAYED.value} TIMESTAMP,
        {ColumnName.SONG_YEAR.value} INTEGER,
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        {ColumnName.UPDATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY ({ColumnName.SONG_ID.value}),
        FOREIGN KEY ({ColumnName.SONG_ALBUM_ID.value})
            REFERENCES {TableName.ALBUM_METADATA_V1.value}({ColumnName.ALBUM_ID.value})
        ON DELETE CASCADE);
"""


__sql_create_table_album_metadata_v1: str = f"""
        CREATE TABLE {TableName.ALBUM_METADATA_V1.value}(
        {ColumnName.ALBUM_ID.value} VARCHAR(255) PRIMARY KEY,
        {ColumnName.QUALITY_BADGE.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP,
        {ColumnName.UPDATED_TIMESTAMP.value} TIMESTAMP)
"""


__sql_create_table_artist_metadata_v1: str = f"""
        CREATE TABLE {TableName.ARTIST_METADATA_V1.value}(
        {ColumnName.ARTIST_ID.value} VARCHAR(255) PRIMARY KEY,
        {ColumnName.ARTIST_NAME.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP,
        {ColumnName.UPDATED_TIMESTAMP.value} TIMESTAMP)
"""


__sql_create_table_artist_role_v1: str = f"""
        CREATE TABLE {TableName.ARTIST_ROLE_V1.value}(
        {ColumnName.ARTIST_ID.value} VARCHAR(255),
        {ColumnName.ARTIST_ROLE.value} VARCHAR(255),
        PRIMARY KEY ({ColumnName.ARTIST_ID.value}, {ColumnName.ARTIST_ROLE.value}),
        FOREIGN KEY ({ColumnName.ARTIST_ID.value})
        REFERENCES {TableName.ARTIST_METADATA_V1.value}({ColumnName.ARTIST_ID.value})
        ON DELETE CASCADE);
"""


__sql_create_table_album_artist_v1: str = f"""
        CREATE TABLE {TableName.ALBUM_ARTIST_V1.value}(
        {ColumnName.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT,
        {ColumnName.ALBUM_ID.value} VARCHAR(255),
        {ColumnName.ARTIST_ID.value} VARCHAR(255),
        {ColumnName.ARTIST_NAME.value} VARCHAR(255),
        FOREIGN KEY ({ColumnName.ALBUM_ID.value})
        REFERENCES {TableName.ALBUM_METADATA_V1.value}({ColumnName.ALBUM_ID.value})
        ON DELETE CASCADE);
"""


__sql_create_table_album_disc_v1: str = f"""
        CREATE TABLE {TableName.ALBUM_DISC_V1.value}(
        {ColumnName.ALBUM_ID.value} VARCHAR(255),
        {ColumnName.DISC_NUM.value} INTEGER,
        {ColumnName.DISC_TITLE.value} VARCHAR(255),
        PRIMARY KEY ({ColumnName.ALBUM_ID.value}, {ColumnName.DISC_NUM.value})
        FOREIGN KEY ({ColumnName.ALBUM_ID.value})
        REFERENCES {TableName.ALBUM_METADATA_V1.value}({ColumnName.ALBUM_ID.value})
        ON DELETE CASCADE);
"""


def __get_sql_create_table_album_genre_v1() -> str:
    return f"""
        CREATE TABLE {TableName.ALBUM_GENRE_V1.value}(
        {ColumnName.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT,
        {ColumnName.ALBUM_ID.value} VARCHAR(255),
        {ColumnName.ALBUM_GENRE.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY ({ColumnName.ALBUM_ID.value})
        REFERENCES {TableName.ALBUM_METADATA_V1.value}({ColumnName.ALBUM_ID.value})
        ON DELETE CASCADE);
    """


def __get_sql_create_table_album_record_label_v1() -> str:
    return f"""
        CREATE TABLE {TableName.ALBUM_RECORD_LABEL_V1.value}(
        {ColumnName.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT,
        {ColumnName.ALBUM_ID.value} VARCHAR(255),
        {ColumnName.ALBUM_RECORD_LABEL.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY ({ColumnName.ALBUM_ID.value})
        REFERENCES {TableName.ALBUM_METADATA_V1.value}({ColumnName.ALBUM_ID.value})
        ON DELETE CASCADE);
    """


def __get_sql_create_table_album_mood_v1() -> str:
    return f"""
        CREATE TABLE {TableName.ALBUM_MOOD_V1.value}(
        {ColumnName.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT,
        {ColumnName.ALBUM_ID.value} VARCHAR(255),
        {ColumnName.ALBUM_MOOD.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY ({ColumnName.ALBUM_ID.value})
        REFERENCES {TableName.ALBUM_METADATA_V1.value}({ColumnName.ALBUM_ID.value})
        ON DELETE CASCADE);
    """


def __get_sql_create_table_song_album_artist_v1() -> str:
    return f"""
        CREATE TABLE {TableName.SONG_ALBUM_ARTIST_V1.value}(
        {ColumnName.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT,
        {SongAlbumArtistMetaModel.SONG_ID.column_name.value} VARCHAR(255),
        {SongAlbumArtistMetaModel.SONG_ALBUM_ARTIST_ID.column_name.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_song_album_artist UNIQUE(
            {SongAlbumArtistMetaModel.SONG_ID.column_name.value},
            {SongAlbumArtistMetaModel.SONG_ALBUM_ARTIST_ID.column_name.value}),
        FOREIGN KEY ({ColumnName.SONG_ID.value})
        REFERENCES {TableName.SONG_METADATA_V1.value}({SongMetadataModel.SONG_ID.column_name.value})
        ON DELETE CASCADE);
    """


def __get_sql_create_table_song_contributor_v1() -> str:
    return f"""
        CREATE TABLE {TableName.SONG_CONTRIBUTOR_V1.value}(
        {ColumnName.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT,
        {SongContributorMetaModel.SONG_ID.column_name.value} VARCHAR(255),
        {SongContributorMetaModel.SONG_ARTIST_ID.column_name.value} VARCHAR(255),
        {SongContributorMetaModel.SONG_CONTRIBUTOR_ROLE.column_name.value} VARCHAR(255),
        {SongContributorMetaModel.SONG_CONTRIBUTOR_SUB_ROLE.column_name.value} VARCHAR(255),
        {SongContributorMetaModel.SONG_ALBUM_ID.column_name.value} VARCHAR(255),
        {SongContributorMetaModel.CREATED_TIMESTAMP.column_name.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_song_artist UNIQUE(
            {SongContributorMetaModel.SONG_ID.column_name.value},
            {SongContributorMetaModel.SONG_ARTIST_ID.column_name.value}),
        FOREIGN KEY ({ColumnName.SONG_ID.value})
        REFERENCES {TableName.SONG_METADATA_V1.value}({SongMetadataModel.SONG_ID.column_name.value})
        ON DELETE CASCADE);
    """


def __get_sql_create_table_album_property_v1() -> str:
    return f"""
        CREATE TABLE {TableName.ALBUM_PROPERTY_V1.value}(
        {AlbumPropertyMetaModel.ALBUM_ID.column_name.value} VARCHAR(255),
        {AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value} VARCHAR(255),
        {AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE.column_name.value} VARCHAR(255),
        {AlbumPropertyMetaModel.CREATED_TIMESTAMP.column_name.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        {AlbumPropertyMetaModel.UPDATED_TIMESTAMP.column_name.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (
            {AlbumPropertyMetaModel.ALBUM_ID.column_name.value},
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value},
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE.column_name.value})
        FOREIGN KEY ({AlbumPropertyMetaModel.ALBUM_ID.column_name.value})
        REFERENCES {TableName.ALBUM_METADATA_V1.value}({AlbumPropertyMetaModel.ALBUM_ID.column_name.value})
        ON DELETE CASCADE);
    """


def __get_sql_create_table_song_artist_v1() -> str:
    return f"""
        CREATE TABLE {TableName.SONG_ARTIST_V1.value}(
        {ColumnName.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT,
        {SongArtistMetaModel.SONG_ID.column_name.value} VARCHAR(255),
        {SongArtistMetaModel.SONG_ARTIST_ID.column_name.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_song_artist UNIQUE(
            {SongArtistMetaModel.SONG_ID.column_name.value},
            {SongArtistMetaModel.SONG_ARTIST_ID.column_name.value}),
        FOREIGN KEY ({ColumnName.SONG_ID.value})
        REFERENCES {TableName.SONG_METADATA_V1.value}({SongMetadataModel.SONG_ID.column_name.value})
        ON DELETE CASCADE);
    """


def __get_sql_create_table_album_release_type_v1() -> str:
    return f"""
        CREATE TABLE {TableName.ALBUM_RELEASE_TYPE_V1.value}(
        {ColumnName.ID.value} INTEGER PRIMARY KEY AUTOINCREMENT,
        {ColumnName.ALBUM_ID.value} VARCHAR(255),
        {ColumnName.ALBUM_RELEASE_TYPE.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY ({ColumnName.ALBUM_ID.value})
        REFERENCES {TableName.ALBUM_METADATA_V1.value}({ColumnName.ALBUM_ID.value})
        ON DELETE CASCADE);
    """


def __get_sql_alter_table_add_column(table_name: TableName, column_name: ColumnName, column_type: str) -> str:
    return f"""
        ALTER TABLE {table_name.value}
        ADD COLUMN {column_name.value} {column_type}
    """


def create_index_on_columns(table_name: str, index_name: str, column_name_list: list[ColumnName]) -> str:
    return (f"CREATE INDEX idx_{table_name}_{index_name} "
            f"ON {table_name}({", ".join(list(map(lambda x: x.value, column_name_list)))})")


def create_index_on_single_column(table_name: str, column_name: str) -> str:
    return f"CREATE INDEX idx_{table_name}_{column_name} ON {table_name}({column_name})"


def __get_sql_oldest_metadata(table_name: str) -> str:
    return f"""
        SELECT {ColumnName.UPDATED_TIMESTAMP.value}
        FROM {table_name}
        ORDER BY {ColumnName.UPDATED_TIMESTAMP.value} ASC
        LIMIT 1
    """


def __get_sqlite3_selector(connection: sqlite3.Connection = None) -> sqlhelper.SqlSelector:
    return sqlite3util.get_sqlite3_selector(connection if connection is not None else __get_connection())


def __get_sqlite3_executor(connection: sqlite3.Connection = None) -> sqlhelper.SqlExecutor:
    return sqlite3util.get_sqlite3_executor(connection if connection is not None else __get_connection())


def get_random_cover_art_by_artist_id(artist_id: str, connection: sqlite3.Connection = None) -> list[ArtistAlbumCoverArt]:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    art_list: list[ArtistAlbumCoverArt] = []
    sql: str = f"""
        SELECT
            {ColumnName.ALBUM_ID.value},
            {ColumnName.ALBUM_COVER_ART.value}
        FROM
            {TableName.ALBUM_METADATA_V1.value}
        WHERE
            {ColumnName.ALBUM_ID.value} IN (
                SELECT
                    DISTINCT {ColumnName.ALBUM_ID.value}
                FROM (
                    SELECT {ColumnName.ALBUM_ID.value}
                        FROM {TableName.ALBUM_ARTIST_V1.value}
                        WHERE {ColumnName.ARTIST_ID.value} = ?
                    UNION ALL
                    SELECT {ColumnName.ALBUM_ID.value}
                        FROM {TableName.ALBUM_METADATA_V1.value}
                        WHERE {ColumnName.ALBUM_ARTIST_ID.value} = ?))
    """
    # msgproc.log(sql)
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(sql=sql, parameters=(artist_id, artist_id))
    # any?
    for row in rows if rows else []:
        album_id: str = row[0]
        cover_art: str = row[1]
        msgproc.log(f"get_random_cover_art_by_artist_id -> adding artist_id [{artist_id}] "
                    f"album_id [{album_id}] "
                    f"cover_art [{cover_art}]")
        art_list.append(ArtistAlbumCoverArt(
            artist_id=artist_id,
            cover_source=CoverSource.ALBUM,
            object_id=album_id,
            cover_art=cover_art))
    if connection is None:
        the_connection.close()
    return art_list


class ArtistEntry:

    def __init__(
            self,
            artist_id: str,
            artist_name: str,
            artist_cover_art: str):
        self.__artist_id: str = artist_id
        self.__artist_name: str = artist_name
        self.__artist_cover_art: str = artist_cover_art

    @property
    def artist_id(self) -> str:
        return self.__artist_id

    @property
    def artist_name(self) -> str:
        return self.__artist_name

    @property
    def artist_cover_art(self) -> str:
        return self.__artist_cover_art


class ArtistRoleEntry:

    def __init__(
            self,
            artist_role: str,
            random_artist_id: str,
            random_artist_name: str,
            random_artist_cover_art: str):
        self.__artist_role: str = artist_role
        self.__random_artist_id: str = random_artist_id
        self.__random_artist_name: str = random_artist_name
        self.__random_artist_cover_art: str = random_artist_cover_art

    @property
    def artist_role(self) -> str:
        return self.__artist_role

    @property
    def random_artist_id(self) -> str:
        return self.__random_artist_id

    @property
    def random_artist_name(self) -> str:
        return self.__random_artist_name

    @property
    def random_artist_cover_art(self) -> str:
        return self.__random_artist_cover_art


class ArtistRoleInitialEntry:

    def __init__(
            self,
            artist_role: str,
            artist_initial: str,
            random_artist_id: str,
            random_artist_name: str,
            random_artist_cover_art: str):
        self.__artist_role: str = artist_role
        self.__artist_initial: str = artist_initial
        self.__random_artist_id: str = random_artist_id
        self.__random_artist_name: str = random_artist_name
        self.__random_artist_cover_art: str = random_artist_cover_art

    @property
    def artist_role(self) -> str:
        return self.__artist_role

    @property
    def artist_initial(self) -> str:
        return self.__artist_initial

    @property
    def random_artist_id(self) -> str:
        return self.__random_artist_id

    @property
    def random_artist_name(self) -> str:
        return self.__random_artist_name

    @property
    def random_artist_cover_art(self) -> str:
        return self.__random_artist_cover_art


def get_artist_roles(connection: sqlite3.Connection = None) -> list[ArtistRoleEntry]:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    sql: str = f"""
        SELECT
            {ColumnName.ARTIST_ROLE.value},
            {ColumnName.ARTIST_ID.value},
            {ColumnName.ARTIST_NAME.value},
            {ColumnName.ARTIST_COVER_ART.value}
        FROM (
            SELECT
                arv.{ColumnName.ARTIST_ROLE.value},
                amv.{ColumnName.ARTIST_ID.value},
                amv.{ColumnName.ARTIST_NAME.value},
                amv.{ColumnName.ARTIST_COVER_ART.value},
                ROW_NUMBER() OVER (
                    PARTITION BY arv.{ColumnName.ARTIST_ROLE.value}
                    ORDER BY
                        -- 1. Prioritize rows where art is NOT NULL and NOT empty
                        (amv.{ColumnName.ARTIST_COVER_ART.value} IS NULL OR amv.{ColumnName.ARTIST_COVER_ART.value} = '') ASC,
                        -- 2. Randomize within those two groups
                        RANDOM()
                    ) as rank
            FROM
                {TableName.ARTIST_ROLE_V1.value} arv
            JOIN
                {TableName.ARTIST_METADATA_V1.value} amv
                ON arv.{ColumnName.ARTIST_ID.value} = amv.{ColumnName.ARTIST_ID.value})
        WHERE rank = 1
        ORDER BY {ColumnName.ARTIST_ROLE.value};
    """
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(
        sql=sql,
        parameters=())
    # any?
    res: list[str] = []
    for row in rows if rows else []:
        role_name: str = row[0]
        artist_id: str = row[1]
        artist_name: str = row[2]
        artist_cover_art: str = row[3]
        entry: ArtistRoleEntry = ArtistRoleEntry(
            artist_role=role_name,
            random_artist_id=artist_id,
            random_artist_name=artist_name,
            random_artist_cover_art=artist_cover_art)
        res.append(entry)
    if connection is None:
        the_connection.close()
    return res


def get_artist_role_initials(artist_role: str, connection: sqlite3.Connection = None) -> list[ArtistRoleInitialEntry]:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    sql: str = f"""
        SELECT
            initial,
            {ArtistMetadataModel.ARTIST_ID.column_name.value},
            {ArtistMetadataModel.ARTIST_NAME.column_name.value},
            {ArtistMetadataModel.ARTIST_COVER_ART.column_name.value}
        FROM (
            SELECT
                UPPER(SUBSTR(amv.{ColumnName.ARTIST_NAME.value}, 1, 1)) AS initial,
                amv.{ArtistMetadataModel.ARTIST_NAME.column_name.value},
                amv.{ArtistMetadataModel.ARTIST_COVER_ART.column_name.value},
                amv.{ArtistMetadataModel.ARTIST_ID.column_name.value},
                ROW_NUMBER() OVER (
                    PARTITION BY UPPER(SUBSTR(amv.artist_name, 1, 1))
                    ORDER BY
                        -- 1. Prioritize rows with art
                        (amv.{ArtistMetadataModel.ARTIST_COVER_ART.column_name.value} IS NULL
                            OR amv.{ArtistMetadataModel.ARTIST_COVER_ART.column_name.value} = '') ASC,
                        -- 2. Randomize within the group
                        RANDOM()
                ) as rank
            FROM {TableName.ARTIST_METADATA_V1.value} amv
            JOIN {TableName.ARTIST_ROLE_V1.value} arv
                ON amv.{ArtistMetadataModel.ARTIST_ID.column_name.value} = arv.{ColumnName.ARTIST_ID.value}
            WHERE arv.{ColumnName.ARTIST_ROLE.value} = ?  -- Parameterized Role
        )
        WHERE rank = 1
        ORDER BY initial;
    """
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(
        sql=sql,
        parameters=(artist_role,))
    # any?
    res: list[str] = []
    for row in rows if rows else []:
        artist_initial: str = row[0]
        artist_id: str = row[1]
        artist_name: str = row[2]
        artist_cover_art: str = row[3]
        entry: ArtistRoleInitialEntry = ArtistRoleInitialEntry(
            artist_role=artist_role,
            artist_initial=artist_initial,
            random_artist_id=artist_id,
            random_artist_name=artist_name,
            random_artist_cover_art=artist_cover_art)
        res.append(entry)
    if connection is None:
        the_connection.close()
    return res


def get_artist_by_role_and_initial(
        artist_role: str,
        initial: str,
        offset: int,
        limit: int,
        connection: sqlite3.Connection = None) -> list[ArtistEntry]:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    sql: str = f"""
        SELECT
            amv.artist_id,
            amv.artist_name,
            amv.artist_cover_art
        FROM {TableName.ARTIST_METADATA_V1.value} amv
        JOIN artist_role_v1 arv ON amv.artist_id = arv.artist_id
        WHERE arv.artist_role = ?
        AND UPPER(amv.artist_name) LIKE ?
        ORDER BY UPPER(amv.artist_name)
        LIMIT ? OFFSET ?;
    """
    t = (artist_role, f"{initial}%", limit, offset)
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(
        sql=sql,
        parameters=t)
    # any?
    res: list[str] = []
    for row in rows if rows else []:
        artist_id: str = row[0]
        artist_name: str = row[1]
        artist_cover_art: str = row[2]
        entry: ArtistEntry = ArtistEntry(
            artist_id=artist_id,
            artist_name=artist_name,
            artist_cover_art=artist_cover_art)
        res.append(entry)
    if connection is None:
        the_connection.close()
    return res


def get_artist_id_list_by_display_name(artist_display_name: str, connection: sqlite3.Connection = None) -> list[str]:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    res: list[str] = []
    sql: str = f"""
        SELECT DISTINCT({ColumnName.ARTIST_ID.value})
        FROM (
            SELECT DISTINCT({ColumnName.ARTIST_ID.value}) AS {ColumnName.ARTIST_ID.value}
                FROM {TableName.ALBUM_ARTIST_V1.value}
                WHERE {ColumnName.ALBUM_ID.value} in (
                    SELECT {ColumnName.ALBUM_ID.value}
                        FROM {TableName.ALBUM_METADATA_V1.value}
                        WHERE {ColumnName.ALBUM_DISPLAY_ARTIST.value} = ?)
            UNION ALL
            SELECT DISTINCT({ColumnName.ARTIST_ID.value}) as {ColumnName.ARTIST_ID.value}
                FROM {TableName.ARTIST_METADATA_V1.value}
                WHERE
                    {ColumnName.ARTIST_SORT_NAME.value} = ?
                    or {ColumnName.ARTIST_NAME.value} = ?)
    """
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(
        sql=sql,
        parameters=(
            artist_display_name,
            artist_display_name,
            artist_display_name))
    # any?
    for row in rows if rows else []:
        artist_id: str = row[0]
        if artist_id is not None and len(artist_id) > 0 and artist_id not in res:
            res.append(artist_id)
    if connection is None:
        the_connection.close()
    return res


def get_random_album_by_genre(genre_name: str, connection: sqlite3.Connection = None) -> AlbumMetadata:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    the_connection: sqlite3.Connection = get_working_connection(connection)
    album_metadata: AlbumMetadata = None
    column_list_names: list[str] = __album_metadata_model_all_column_names
    column_list_names_joined = ", ".join(column_list_names)
    sql_direct: str = f"""
        SELECT {column_list_names_joined}
            FROM {TableName.ALBUM_METADATA_V1.value}
            WHERE {ColumnName.ALBUM_GENRE.value} = ?
            ORDER BY RANDOM()
            LIMIT 1
    """
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(
        sql=sql_direct,
        parameters=(genre_name, ))
    if verbose:
        msgproc.log(f"get_random_album_by_genre query #1 for [{genre_name}] "
                    f"row_count [{len(rows) if rows else 0}]")
    if rows is not None and len(rows) > 0:
        if len(rows) > 1:
            raise Exception(f"get_random_album_by_genre query #1 for [{genre_name}] should select a single record")
        row: any = rows[0]
        album_metadata = __album_metadata_by_row(row=row)
    else:
        if verbose:
            msgproc.log(f"get_random_album_by_genre query #1 for [{genre_name}] "
                        f"row_count [{len(rows) if rows else 0}], no data available")
    # try using secondary table if needed
    if album_metadata is None:
        sql_sec: str = f"""
            SELECT {column_list_names_joined}
            FROM {TableName.ALBUM_METADATA_V1.value}
            WHERE {ColumnName.ALBUM_ID.value} = (
                SELECT {ColumnName.ALBUM_ID.value}
                FROM {TableName.ALBUM_GENRE_V1.value}
                WHERE {ColumnName.ALBUM_GENRE.value} = ?
                ORDER BY RANDOM()
                LIMIT 1)
        """
        rows = __get_sqlite3_selector(connection=the_connection)(
            sql=sql_sec,
            parameters=(genre_name, ))
        if verbose:
            msgproc.log(f"get_random_album_by_genre query #2 for [{genre_name}] "
                        f"row_count [{len(rows) if rows else 0}]")
        if rows is not None and len(rows) > 0:
            if len(rows) > 1:
                raise Exception(f"get_random_album_by_genre query #2 for [{genre_name}] should select a single record")
            row: any = rows[0]
            album_metadata = __album_metadata_by_row(row=row)
        else:
            if verbose:
                msgproc.log(f"get_random_album_by_genre query #2 for [{genre_name}] "
                            f"row_count [{len(rows) if rows else 0}], no data available")
    if connection is None:
        the_connection.close()
    if verbose:
        msgproc.log(f"get_random_album_by_genre for [{genre_name}] -> "
                    f"album_id [{album_metadata.album_id}] "
                    f"cover_art [{album_metadata.album_cover_art}]")
    return album_metadata


def choose_artist_album_cover_art(lst: list[ArtistAlbumCoverArt]) -> ArtistAlbumCoverArt:
    if not lst or len(lst) == 0:
        # safeguard
        return None
    # the ones that come from the artist metadata are preferable
    best_cover_art_list: list[ArtistAlbumCoverArt] = list(filter(lambda x: x.cover_source == CoverSource.ARTIST, lst))
    if len(best_cover_art_list) > 0:
        # best choice is presumably the first
        return best_cover_art_list[0]
    # as a second choice, we look for source to be an album
    best_cover_art_list = list(filter(lambda x: x.cover_source == CoverSource.ALBUM, lst))
    if len(best_cover_art_list) > 0:
        # best choice is presumably the first
        return best_cover_art_list[0]
    # otherwise, just choose randomly
    return secrets.choice(lst)


def get_cover_art_list_by_artist_id(artist_id: str, connection: sqlite3.Connection = None) -> list[ArtistAlbumCoverArt]:
    d: dict[str, list[ArtistAlbumCoverArt]] = get_cover_art_list_by_artist_id_list(
        artist_id_list=[artist_id],
        connection=connection)
    return d[artist_id] if artist_id in d else []


def get_cover_art_list_by_artist_id_list(
        artist_id_list: list[str],
        connection: sqlite3.Connection = None) -> dict[str, list[ArtistAlbumCoverArt]]:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    res: dict[str, list[ArtistAlbumCoverArt]] = {}
    qmark_list: str = __create_qmark_list(len(artist_id_list))
    sql: str = f"""
        SELECT
            {ArtistMetadataModel.ARTIST_ID.column_name.value} AS {ColumnName.ARTIST_ID.value},
            'artist' as object_type,
            {ArtistMetadataModel.ARTIST_ID.column_name.value} AS object_id,
            {ArtistMetadataModel.ARTIST_COVER_ART.column_name.value} AS {ColumnName.ALBUM_COVER_ART.value}
        FROM
            {TableName.ARTIST_METADATA_V1.value}
        WHERE
            {ColumnName.ARTIST_ID.value} IN ({qmark_list})
            AND {ArtistMetadataModel.ARTIST_COVER_ART.column_name.value} IS NOT NULL
        UNION ALL
        SELECT
            {AlbumMetadataModel.ALBUM_ARTIST_ID.column_name.value} AS {ColumnName.ARTIST_ID.value},
            'album' as object_type,
            {AlbumMetadataModel.ALBUM_ID.column_name.value} AS object_id,
            {AlbumMetadataModel.ALBUM_COVER_ART.column_name.value} AS {ColumnName.ALBUM_COVER_ART.value}
        FROM
            {TableName.ALBUM_METADATA_V1.value}
        WHERE
            {ColumnName.ARTIST_ID.value} IN ({qmark_list})
            AND {ColumnName.ALBUM_COVER_ART.value} IS NOT NULL
        UNION ALL
        SELECT
            {ColumnName.SONG_ARTIST_ID.value} AS {ColumnName.ARTIST_ID.value},
            'album' as object_type,
            {ColumnName.SONG_ALBUM_ID.value} AS object_id,
            {ColumnName.SONG_COVER_ART.value} AS {ColumnName.ALBUM_COVER_ART.value}
        FROM
            {TableName.SONG_METADATA_V1.value}
        WHERE
            {ColumnName.SONG_ARTIST_ID.value} IN ({qmark_list})
            AND {ColumnName.SONG_COVER_ART.value} IS NOT NULL
        UNION ALL
        SELECT
            aav.{ColumnName.ARTIST_ID.value} AS {ColumnName.ARTIST_ID.value},
            'album' as object_type,
            amv.{AlbumMetadataModel.ALBUM_ID.column_name.value} AS object_id,
            amv.{AlbumMetadataModel.ALBUM_COVER_ART.column_name.value} AS {ColumnName.ALBUM_COVER_ART.value}
        FROM
            {TableName.ALBUM_METADATA_V1.value} amv,
            {TableName.ALBUM_ARTIST_V1.value} aav
        WHERE
            amv.{AlbumMetadataModel.ALBUM_ID.column_name.value} = aav.{AlbumMetadataModel.ALBUM_ID.column_name.value}
            AND aav.{ColumnName.ARTIST_ID.value} IN ({qmark_list})
            AND amv.{AlbumMetadataModel.ALBUM_COVER_ART.column_name.value} IS NOT NULL
        UNION ALL
        SELECT
            sav2.{SongArtistMetaModel.SONG_ARTIST_ID.column_name.value},
            'song' as object_type,
            sav2.{SongArtistMetaModel.SONG_ALBUM_ID.column_name.value} as object_id,
            sm2.{SongMetadataModel.SONG_COVER_ART.column_name.value}
        FROM
            {TableName.SONG_ARTIST_V1.value} sav2
            JOIN {TableName.SONG_METADATA_V1.value} sm2
                on sav2.{SongArtistMetaModel.SONG_ID.column_name.value} = sm2.{SongMetadataModel.SONG_ID.column_name.value}
        WHERE
            sav2.{SongArtistMetaModel.SONG_ARTIST_ID.column_name.value} IN ({qmark_list})
            AND sm2.{SongMetadataModel.SONG_COVER_ART.column_name.value} IS NOT NULL
        UNION ALL
        SELECT
            sav1.{SongAlbumArtistMetaModel.SONG_ALBUM_ARTIST_ID.column_name.value},
            'song' as object_type,
            sav1.{SongAlbumArtistMetaModel.SONG_ALBUM_ID.column_name.value} as object_id,
            sm1.{SongMetadataModel.SONG_COVER_ART.column_name.value}
        FROM
            {TableName.SONG_ALBUM_ARTIST_V1.value} sav1
            JOIN {TableName.SONG_METADATA_V1.value} sm1
                on sav1.{SongAlbumArtistMetaModel.SONG_ID.column_name.value} = sm1.{SongMetadataModel.SONG_ID.column_name.value}
        WHERE
            sav1.{SongAlbumArtistMetaModel.SONG_ALBUM_ARTIST_ID.column_name.value} IN ({qmark_list})
            AND sm1.{SongMetadataModel.SONG_COVER_ART.column_name.value} IS NOT NULL
        UNION ALL
        SELECT
            sav3.{SongContributorMetaModel.SONG_ARTIST_ID.column_name.value},
            'song' as object_type,
            sav3.{SongContributorMetaModel.SONG_ALBUM_ID.column_name.value} as object_id,
            sm3.{SongMetadataModel.SONG_COVER_ART.column_name.value}
        FROM
            {TableName.SONG_CONTRIBUTOR_V1.value} sav3
            JOIN {TableName.SONG_METADATA_V1.value} sm3
                on sav3.{SongArtistMetaModel.SONG_ID.column_name.value} = sm3.{SongContributorMetaModel.SONG_ID.column_name.value}
        WHERE
            sav3.{SongContributorMetaModel.SONG_ARTIST_ID.column_name.value} IN ({qmark_list})
            AND sm3.{SongMetadataModel.SONG_COVER_ART.column_name.value} IS NOT NULL
    """
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(
        sql=sql,
        parameters=tuple(artist_id_list * 7))
    # any?
    occ_set: set[tuple[str, str]] = set()
    for row in rows if rows else []:
        artist_id: str = row[0]
        object_id: str = row[2]
        cover_art: str = row[3]
        # avoid duplicate tuple (artist_id, album_id)
        if (artist_id, object_id) in occ_set:
            continue
        occ_set.add((artist_id, object_id))
        entry: ArtistAlbumCoverArt = ArtistAlbumCoverArt(
            artist_id=artist_id,
            cover_source=get_cover_source_by_name(row[1]),
            object_id=object_id,
            cover_art=cover_art)
        entry_list: list[ArtistAlbumCoverArt] = res[entry.artist_id] if entry.artist_id in res else None
        if not entry_list:
            entry_list = []
            res[entry.artist_id] = entry_list
        entry_list.append(entry)
    if connection is None:
        the_connection.close()
    return res


def get_genre_list_by_artist_id(artist_id: str, connection: sqlite3.Connection = None) -> list[str]:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    genre_list: list[str] = []
    # use album metadata
    sql_meta: str = f"""
        SELECT DISTINCT({ColumnName.ALBUM_GENRE.value})
            FROM {TableName.ALBUM_METADATA_V1.value}
            WHERE {ColumnName.ALBUM_ID.value} IN (
                SELECT DISTINCT {ColumnName.ALBUM_ID.value} FROM (
                    SELECT {ColumnName.ALBUM_ID.value}
                        FROM {TableName.ALBUM_ARTIST_V1.value}
                        WHERE {ColumnName.ARTIST_ID.value} = ?
                    UNION ALL
                    SELECT {ColumnName.ALBUM_ID.value}
                        FROM {TableName.ALBUM_METADATA_V1.value}
                        WHERE {ColumnName.ALBUM_ARTIST_ID.value} = ?))
    """
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(sql=sql_meta, parameters=(artist_id, artist_id))
    # any?
    for row in rows if rows else []:
        genre: str = row[0]
        if genre is not None and len(genre) > 0 and genre not in genre_list:
            genre_list.append(genre)
    sql_genre: str = f"""
        SELECT DISTINCT(album_genre)
            FROM {TableName.ALBUM_GENRE_V1.value}
            WHERE {ColumnName.ALBUM_ID.value} in (
                SELECT DISTINCT {ColumnName.ALBUM_ID.value}
                    FROM (
                        SELECT {ColumnName.ALBUM_ID.value}
                            FROM {TableName.ALBUM_ARTIST_V1.value}
                            WHERE {ColumnName.ARTIST_ID.value} = ?
                        UNION ALL
                        SELECT {ColumnName.ALBUM_ID.value}
                        from {TableName.ALBUM_METADATA_V1.value}
                        WHERE {ColumnName.ALBUM_ARTIST_ID.value} = ?))
    """
    rows = __get_sqlite3_selector(connection=the_connection)(sql=sql_genre, parameters=(artist_id, artist_id))
    # any?
    for row in rows if rows else []:
        genre: str = row[0]
        if genre is not None and len(genre) > 0 and genre not in genre_list:
            genre_list.append(genre)
    if connection is None:
        the_connection.close()
    return genre_list


def get_oldest_metadata(table_name: TableName, connection: sqlite3.Connection = None) -> datetime.datetime | None:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    rows: list[Any] = __get_sqlite3_selector(the_connection)(
        sql=__get_sql_oldest_metadata(table_name=table_name.value),
        parameters=())
    if connection is None:
        the_connection.close()
    if not rows:
        return None
    if len(rows) > 1:
        raise Exception(f"get_oldest_metadata on {table_name.value} should retrieve only one record")
    # just return first column of first row
    return rows[0][0]


def get_song_metadata(song_id: str, connection: sqlite3.Connection = None) -> AlbumMetadata:
    start: float = time.time()
    result: SongMetadata = __load_song_metadata(song_id=song_id, connection=connection)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.TRACE_PERSISTENCE_OPERATIONS):
        msgproc.log(f"get_song_metadata for song_id [{song_id}] "
                    f"executed in [{elapsed:.3f}] "
                    f"found [{result is not None}]")
    return result


def get_album_metadata_dict(album_id_list: list[str], connection: sqlite3.Connection = None) -> dict[str, AlbumMetadata]:
    start: float = time.time()
    result: dict[str, AlbumMetadata] = __load_album_metadata_list(album_id_list=album_id_list, connection=connection)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.TRACE_PERSISTENCE_OPERATIONS):
        msgproc.log(f"get_album_metadata_dict for album_id list size [{len(album_id_list)}] "
                    f"executed in [{elapsed:.3f}] "
                    f"found [{result is not None}]")
    return result


def get_album_metadata(album_id: str, connection: sqlite3.Connection = None) -> AlbumMetadata:
    start: float = time.time()
    result: AlbumMetadata = __load_album_metadata(album_id=album_id, connection=connection)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.TRACE_PERSISTENCE_OPERATIONS):
        msgproc.log(f"get_album_metadata for album_id [{album_id}] "
                    f"executed in [{elapsed:.3f}] "
                    f"found [{result is not None}]")
    return result


def get_artist_metadata(artist_id: str, connection: sqlite3.Connection = None) -> ArtistMetadata:
    return __load_artist_metadata(artist_id=artist_id, connection=connection)


def get_kv_item(
        partition: str,
        key: str,
        connection: sqlite3.Connection = None) -> KeyValueItem:
    the_connection: sqlite3.Connection = get_working_connection(provided=connection)
    res: KeyValueItem = get_key_value_item(
        partition=partition,
        key=key,
        kv_loader=lambda partition, key: __load_key_value_item(
            partition=partition,
            key=key,
            connection=the_connection))
    if connection is None:
        the_connection.close()
    return res


def get_kv_items_by_value(
        partition: str,
        value: str,
        connection: sqlite3.Connection = None) -> list[KeyValueItem]:
    the_connection: sqlite3.Connection = get_working_connection(provided=connection)
    sql: str = f"""
        SELECT
            {KeyValueCacheColumnName.ITEM_KEY.value},
            {KeyValueCacheColumnName.CREATED_TIMESTAMP.value},
            {KeyValueCacheColumnName.UPDATED_TIMESTAMP.value}
        FROM
            {TableName.KV_CACHE_V1.value}
        WHERE
            {KeyValueCacheColumnName.ITEM_PARTITION.value} = ?
            AND {KeyValueCacheColumnName.ITEM_VALUE.value} = ?
    """
    t = (partition, value)
    rows: list[Any] = __get_sqlite3_selector(the_connection)(
        sql=sql,
        parameters=t)
    kv_list: list[KeyValueItem] = []
    for row in rows if rows else []:
        curr: KeyValueItem = KeyValueItem(
            partition=partition,
            key=row[0],
            value=value,
            created_timestamp=row[1],
            updated_timestamp=row[2])
        kv_list.append(curr)
    return kv_list


def get_kv_partition_count(
        partition: str,
        connection: sqlite3.Connection = None) -> int:
    the_connection: sqlite3.Connection = get_working_connection(provided=connection)
    sql: str = f"""
        SELECT COUNT(*)
        FROM {TableName.KV_CACHE_V1.value}
        WHERE {KeyValueCacheColumnName.ITEM_PARTITION.value} = ?
    """
    t = (partition,)
    rows: list[Any] = __get_sqlite3_selector(the_connection)(
        sql=sql,
        parameters=t)
    if not rows:
        raise Exception(f"get_kv_partition_count cannot get count for [{partition}]")
    if len(rows) == 0 or len(rows) > 1:
        raise Exception(f"get_kv_partition_count count should return 1 row for [{partition}] (we got [{len(rows)}])")
    cnt: int = rows[0][0]
    return cnt


def get_table_count(
        table_name: TableName,
        connection: sqlite3.Connection = None) -> int:
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    q: str = sqlhelper.create_simple_count_sql(table_name=table_name.value)
    rows: list[Any] = sqlite3util.get_sqlite3_selector(the_connection)(sql=q, parameters=())
    if not rows:
        raise Exception(f"get_table_count for [{table_name.value}] did not return any result")
    if len(rows) > 1:
        raise Exception(f"get_table_count multiple results not allowed when requesting a count for [{table_name.value}]")
    res: int = rows[0][0]
    if connection is None:
        the_connection.close()
    return res


def get_working_connection(provided: sqlite3.Connection) -> sqlite3.Connection:
    return provided if provided is not None else __get_connection()


def __load_song_metadata(song_id: str, connection: sqlite3.Connection = None) -> AlbumMetadata:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    t = (song_id, )
    q: str = sqlhelper.create_simple_select_sql(
        table_name=TableName.SONG_METADATA_V1.value,
        select_column_list=[m.column_name.value for m in SongMetadataModel],
        where_column_list=[
            SongMetadataModel.SONG_ID.column_name.value])
    rows: list[Any] = __get_sqlite3_selector(the_connection)(
        sql=q,
        parameters=t)
    if connection is None:
        the_connection.close()
    if not rows:
        return None
    if len(rows) > 1:
        raise Exception(f"Multiple {TableName.SONG_METADATA_V1.value} records for [{song_id}]")
    row = rows[0]
    result: SongMetadata = __song_metadata_by_row(row=row)
    return result


def __load_album_metadata(album_id: str, connection: sqlite3.Connection = None) -> AlbumMetadata:
    res: dict[str, AlbumMetadata] = __load_album_metadata_list(album_id_list=[album_id], connection=connection)
    if res and len(res) > 1:
        raise Exception(f"__load_album_metadata only one record is expected for [{album_id}]")
    return res[album_id] if res and album_id in res else None


def __load_album_metadata_list(album_id_list: list[str], connection: sqlite3.Connection = None) -> dict[str, AlbumMetadata]:
    if len(album_id_list if album_id_list else []) == 0:
        raise Exception("__load_album_metadata_list requires a list of album ids")
    the_connection: sqlite3.Connection = get_working_connection(connection)
    t = tuple(album_id_list)
    qmarks: str = __create_qmark_list(len(album_id_list))
    q: str = f"""
    SELECT
        {", ".join([m.column_name.value for m in AlbumMetadataModel])}
    FROM
        {TableName.ALBUM_METADATA_V1.value}
    WHERE
        {AlbumMetadataModel.ALBUM_ID.column_name.value} IN ({qmarks})
    """
    rows: list[Any] = __get_sqlite3_selector(the_connection)(
        sql=q,
        parameters=t)
    if connection is None:
        the_connection.close()
    res: dict[str, AlbumMetadata] = {}
    for row in rows if rows else []:
        curr: AlbumMetadata = __album_metadata_by_row(row=row)
        res[curr.album_id] = curr
    return res


def __load_artist_metadata(artist_id: str, connection: sqlite3.Connection) -> ArtistMetadata:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    t = (artist_id, )
    q: str = sqlhelper.create_simple_select_sql(
        table_name=TableName.ARTIST_METADATA_V1.value,
        select_column_list=[m.column_name.value for m in ArtistMetadataModel],
        where_column_list=[ArtistMetadataModel.ARTIST_ID.column_name.value])
    rows: list[Any] = __get_sqlite3_selector(the_connection)(
        sql=q,
        parameters=t)
    if connection is None:
        the_connection.close()
    if not rows:
        return None
    if len(rows) > 1:
        raise Exception(f"Multiple {TableName.ARTIST_METADATA_V1.value} records for [{artist_id}]")
    row = rows[0]
    result: ArtistMetadata = __artist_metadata_by_row(row=row)
    return result


def __load_artist_roles(artist_id: str, connection: sqlite3.Connection = None) -> list[ArtistRole]:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    t = (artist_id, )
    q: str = sqlhelper.create_simple_select_sql(
        table_name=TableName.ARTIST_ROLE_V1.value,
        select_column_list=[
            ColumnName.ARTIST_ID.value,
            ColumnName.ARTIST_ROLE.value
        ],
        where_column_list=[
            ColumnName.ARTIST_ID.value
        ])
    rows: list[Any] = __get_sqlite3_selector(the_connection)(
        sql=q,
        parameters=t)
    if connection is None:
        the_connection.close()
    result: list[ArtistRole] = []
    for row in rows if rows else []:
        entry: ArtistRole = ArtistRole(
            artist_id=row[0],
            artist_role=row[1])
        result.append(entry)
    return result


def __load_album_artists(album_id: str, connection: sqlite3.Connection = None) -> list[ArtistFromAlbum]:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    t = (album_id, )
    q: str = sqlhelper.create_simple_select_sql(
        table_name=TableName.ALBUM_ARTIST_V1.value,
        select_column_list=[
            ColumnName.ARTIST_ID.value,
            ColumnName.ARTIST_NAME.value
        ],
        where_column_list=[
            ColumnName.ALBUM_ID.value
        ])
    rows: list[Any] = __get_sqlite3_selector(the_connection)(
        sql=q,
        parameters=t)
    if connection is None:
        the_connection.close()
    result: list[ArtistFromAlbum] = []
    for row in rows if rows else []:
        entry: ArtistFromAlbum = ArtistFromAlbum(
            album_id=album_id,
            artist_id=row[0],
            artist_name=row[1])
        result.append(entry)
    return result


def __update_kv_item(
        partition: str,
        key: str,
        value: str,
        update_timestamp: datetime.datetime,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> None:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    update_kv_item_v1(
        sql_executor=__get_sqlite3_executor(the_connection),
        partition=partition,
        key=key,
        value=value,
        update_timestamp=update_timestamp)
    if do_commit or connection is None:
        commit(connection=the_connection)
    if connection is None:
        the_connection.close()


def __load_key_value_item(partition: str, key: str, connection: sqlite3.Connection = None) -> KeyValueItem:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    res: KeyValueItem = load_kv_item_v1(
        sql_selector=__get_sqlite3_selector(connection),
        partition=partition,
        key=key)
    if connection is None:
        the_connection.close()
    return res


def delete_album_metadata(
        album_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    __delete_album_metadata_from_db(
        album_id=album_id,
        connection=connection,
        do_commit=do_commit)


class InMode(Enum):

    IN = 1,
    NOT_IN = 2


def delete_song_list_not_in(
        album_id: str,
        song_list: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return delete_by_parent_id_and_id_in_list(
        table_name=TableName.SONG_METADATA_V1,
        parent_id_column_name=SongMetadataModel.SONG_ALBUM_ID.column_name,
        parent_id=album_id,
        id_column_name=SongMetadataModel.SONG_ID.column_name,
        id_list=song_list if song_list else [],
        in_mode=InMode.NOT_IN,
        connection=connection,
        do_commit=do_commit)


def delete_by_parent_id_and_id_in_list(
        table_name: TableName,
        parent_id_column_name: ColumnName,
        parent_id: str,
        id_column_name: ColumnName,
        id_list: list[str],
        in_mode: InMode,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    if not in_mode or in_mode not in [InMode.IN, InMode.NOT_IN]:
        raise Exception("delete_by_parent_id_and_id_in_list in_mode must be specified")
    the_connection: sqlite3.Connection = get_working_connection(connection)
    res: int = 0
    if len(id_list) > 0:
        qm: str = __create_qmark_list(num_qmark=len(id_list))
        q: str = f"""
        DELETE FROM {table_name.value}
        WHERE
            {parent_id_column_name.value} = ?
            AND {id_column_name.value} {'IN' if in_mode == InMode.IN else 'NOT IN'} ({qm})
        """
        t = tuple([parent_id] + id_list)
        res += __get_sqlite3_executor(the_connection)(
            sql=q,
            data=t,
            do_commit=False)
        if do_commit or connection is None:
            commit(connection=the_connection)
    if connection is None:
        the_connection.close()
    return res


def delete_artist_metadata(
        artist_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = False):
    __delete_artist_metadata_from_db(
        artist_id=artist_id,
        connection=connection,
        do_commit=do_commit)


def __delete_album_metadata_from_db(
        album_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    the_connection: sqlite3.Connection = get_working_connection(connection)
    q: str = sqlhelper.create_simple_delete_sql(
        table_name=TableName.ALBUM_METADATA_V1.value,
        where_column_list=[ColumnName.ALBUM_ID.value])
    t = (album_id, )
    __get_sqlite3_executor(the_connection)(
        sql=q,
        data=t,
        do_commit=False)
    if do_commit or connection is None:
        commit(connection=the_connection)
    if connection is None:
        the_connection.close()


def delete_by_key(
        table_name: TableName,
        column_list: list[ColumnName],
        values: list[Any],
        connection: sqlite3.Connection = None,
        do_commit: bool = False) -> int:
    if column_list is None or values is None:
        raise Exception("delete_by_key invalid arguments "
                        f"column_list empty [{column_list is None or len(column_list) == 0}] "
                        f"values empty [{values is None or len(values) == 0}]")
    if (len(column_list) if column_list else 0) != (len(values) if values else 0):
        raise Exception("delete_by_key invalid arguments "
                        f"len(column_list) [{len(column_list) if column_list else 0}] "
                        f"len(values) [{len(values) if values else 0}]")
    the_connection: sqlite3.Connection = get_working_connection(connection)
    q: str = sqlhelper.create_simple_delete_sql(
        table_name=table_name.value,
        where_column_list=list(map(lambda x: x.value, column_list)))
    t = tuple(values)
    res: int = __get_sqlite3_executor(the_connection)(
        sql=q,
        data=t,
        do_commit=False)
    if connection is None:
        # connection not provided, we commit
        commit(connection=the_connection)
        the_connection.close()
    else:
        if do_commit:
            commit(connection=connection)
    return res


def __delete_album_artists(
        album_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = False) -> int:
    return __delete_from_table(
        table_name=TableName.ALBUM_ARTIST_V1,
        column_list=[ColumnName.ALBUM_ID],
        data_list=[album_id],
        connection=connection,
        do_commit=do_commit)


def __delete_album_discs(
        album_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = False) -> int:
    return __delete_from_table(
        table_name=TableName.ALBUM_DISC_V1,
        column_list=[ColumnName.ALBUM_ID],
        data_list=[album_id],
        connection=connection,
        do_commit=do_commit)


def __delete_album_genres(
        album_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = False) -> int:
    return __delete_from_table(
        table_name=TableName.ALBUM_GENRE_V1,
        column_list=[ColumnName.ALBUM_ID],
        data_list=[album_id],
        connection=connection,
        do_commit=do_commit)


def __delete_album_record_labels(
        album_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = False) -> int:
    return __delete_from_table(
        table_name=TableName.ALBUM_RECORD_LABEL_V1,
        column_list=[ColumnName.ALBUM_ID],
        data_list=[album_id],
        connection=connection,
        do_commit=do_commit)


def __delete_album_moods(
        album_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = False) -> int:
    return __delete_from_table(
        table_name=TableName.ALBUM_MOOD_V1,
        column_list=[ColumnName.ALBUM_ID],
        data_list=[album_id],
        connection=connection,
        do_commit=do_commit)


def __delete_album_release_types(
        album_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = False) -> int:
    return __delete_from_table(
        table_name=TableName.ALBUM_RELEASE_TYPE_V1,
        column_list=[ColumnName.ALBUM_ID],
        data_list=[album_id],
        connection=connection,
        do_commit=do_commit)


def __delete_from_table(
        table_name: TableName,
        column_list: list[ColumnName],
        data_list: list[any],
        connection: sqlite3.Connection = None,
        do_commit: bool = False) -> int:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    q: str = sqlhelper.create_simple_delete_sql(
        table_name=table_name.value,
        where_column_list=list(map(lambda x: x.value, column_list)))
    t = tuple(data_list)
    delete_count: int = __get_sqlite3_executor(the_connection)(
        sql=q,
        data=t,
        do_commit=False)
    if connection is None:
        # connection not provided, commit enforced
        commit(connection=the_connection)
        the_connection.close()
    else:
        # commit if requested
        if do_commit:
            commit(connection=connection)
    return delete_count


def __delete_artist_metadata_from_db(
        artist_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = False):
    the_connection: sqlite3.Connection = get_working_connection(connection)
    q: str = sqlhelper.create_simple_delete_sql(
        table_name=TableName.ARTIST_METADATA_V1.value,
        where_column_list=[ColumnName.ARTIST_ID.value])
    t = (artist_id, )
    __get_sqlite3_executor(the_connection)(
        sql=q,
        data=t,
        do_commit=False)
    if connection is None:
        # connection not provided, we commit
        commit(connection=the_connection)
        the_connection.close()
    else:
        # commit if requested
        if do_commit:
            commit(connection=connection)


def _delete_kv_item_from_db(partition: str, key: str, connection: sqlite3.Connection = None):
    the_connection: sqlite3.Connection = get_working_connection(connection)
    delete_kv_item_v1(
        sql_executor=__get_sqlite3_executor(the_connection),
        partition=partition,
        key=key)
    if connection is None:
        the_connection.close()


def save_album_properties(
        album_id: str,
        properties: dict[str, list[Any]],
        delete_all: bool = False,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    res: int = 0
    # delete?
    if delete_all:
        res += delete_by_key(
            table_name=TableName.ALBUM_PROPERTY_V1,
            column_list=[AlbumPropertyMetaModel.ALBUM_ID.column_name],
            values=[album_id],
            connection=the_connection,
            do_commit=False)
    else:
        res += delete_by_parent_id_and_id_in_list(
            table_name=TableName.ALBUM_PROPERTY_V1,
            parent_id_column_name=AlbumPropertyMetaModel.ALBUM_ID.column_name,
            parent_id=album_id,
            id_column_name=AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name,
            id_list=list(properties.keys()),
            in_mode=InMode.IN,
            connection=the_connection,
            do_commit=False)
    # store new values
    ins_sql: str = sqlhelper.create_simple_insert_sql(
        table_name=TableName.ALBUM_PROPERTY_V1.value,
        column_list=[AlbumPropertyMetaModel.ALBUM_ID.column_name.value,
                     AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value,
                     AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE.column_name.value])
    k: str
    v: list[str]
    for k, v in properties.items():
        p: str
        # avoid duplications.
        for p in list(set(v)):
            res += __execute_update(
                sql=ins_sql,
                data=tuple([album_id, k, p]),
                connection=the_connection,
                do_commit=False)
    # final checks
    if connection is None or do_commit:
        commit(the_connection)
    if connection is None:
        the_connection.close()
    return res


def save_song_metadata(
        song_metadata: SongMetadata,
        context: str = None,
        force_insert: bool = False,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> tuple[SongMetadata, SaveMode]:
    start: float = time.time()
    result: SongMetadata
    saveMode: SaveMode
    result, saveMode = __save_song_metadata(
        song_metadata=song_metadata,
        force_insert=force_insert,
        connection=connection,
        do_commit=do_commit)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.TRACE_PERSISTENCE_OPERATIONS):
        msgproc.log(f"save_song_metadata for song_id [{song_metadata.song_id}] "
                    f"context [{context}] "
                    f"force_insert [{force_insert}] "
                    f"mode [{saveMode}] "
                    f"executed in [{elapsed:.3f}]")
    return (result, saveMode)


def __save_song_metadata(
        song_metadata: SongMetadata,
        force_insert: bool = False,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> tuple[SongMetadata, SaveMode]:
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    existing_metadata: SongMetadata = (get_song_metadata(song_id=song_metadata.song_id, connection=the_connection)
                                       if not force_insert
                                       else None)
    if existing_metadata:
        # update
        updated_metadata: SongMetadata = metadata_converter.update_song_metadata(
            existing_metadata=existing_metadata,
            song_metadata=song_metadata)
        set_values: list[Any] = list(map(lambda x: updated_metadata.get_value(x), __song_metadata_model_non_pk_list))
        where_values: list[Any] = list(map(lambda x: updated_metadata.get_value(x), __song_metadata_model_pk_list))
        update_sql: str = sqlhelper.create_simple_update_sql(
            table_name=TableName.SONG_METADATA_V1.value,
            set_column_list=__song_metadata_model_non_pk_column_names,
            where_column_list=__song_metadata_model_pk_column_names)
        update_values = tuple(set_values + where_values)
        upd_res: int = 0
        upd_res += __execute_update(
            sql=update_sql,
            data=update_values,
            connection=the_connection,
            do_commit=do_commit)
        if upd_res != 1:
            msgproc.log(f"__save_song_metadata could not update with song_id [{song_metadata.song_id}] "
                        f"upd_res [{upd_res}]")
        if connection is None:
            the_connection.close()
        return (updated_metadata, SaveMode.UPDATED)
    else:
        # set timestamps
        song_metadata.set_value(AlbumMetadataModel.CREATED_TIMESTAMP, datetime.datetime.now())
        song_metadata.set_value(AlbumMetadataModel.UPDATED_TIMESTAMP, datetime.datetime.now())
        # insert
        ins_res: int = __insert_song_metadata(
            song_metadata=song_metadata,
            connection=the_connection,
            do_commit=do_commit)
        if ins_res != 1:
            msgproc.log(f"__save_song_metadata could not insert with song_id [{song_metadata.song_id}] "
                        f"ins_res [{ins_res}]")
        if connection is None:
            the_connection.close()
        return (song_metadata, SaveMode.INSERTED)


def delete_song_contributors_not_in(
        song_id: str,
        song_contributor_list: list[SongContributor],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    id_list: list[str] = list(map(lambda x: x.artist_id, song_contributor_list))
    return delete_song_contributor_not_in(
        table_name=TableName.SONG_CONTRIBUTOR_V1,
        song_id=song_id,
        id_list=id_list,
        song_id_column_name=SongContributorMetaModel.SONG_ID.column_name,
        contributor_id_column_name=SongContributorMetaModel.SONG_ARTIST_ID.column_name,
        connection=connection,
        do_commit=do_commit)


def delete_song_artists_not_in(
        song_id: str,
        song_artist_list: list[SongArtist],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    id_list: list[str] = list(map(lambda x: x.artist_id, song_artist_list))
    return delete_song_contributor_not_in(
        table_name=TableName.SONG_ARTIST_V1,
        song_id=song_id,
        id_list=id_list,
        song_id_column_name=SongArtistMetaModel.SONG_ID.column_name,
        contributor_id_column_name=SongArtistMetaModel.SONG_ARTIST_ID.column_name,
        connection=connection,
        do_commit=do_commit)


def delete_song_album_artists_not_in(
        song_id: str,
        song_album_artist_list: list[SongArtist],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    id_list: list[str] = list(map(lambda x: x.artist_id, song_album_artist_list))
    return delete_song_contributor_not_in(
        table_name=TableName.SONG_ALBUM_ARTIST_V1,
        song_id=song_id,
        id_list=id_list,
        song_id_column_name=SongAlbumArtistMetaModel.SONG_ID.column_name,
        contributor_id_column_name=SongAlbumArtistMetaModel.SONG_ALBUM_ARTIST_ID.column_name,
        connection=connection,
        do_commit=do_commit)


def delete_song_contributor_not_in(
        table_name: TableName,
        song_id: str,
        id_list: list[str],
        song_id_column_name: ColumnName,
        contributor_id_column_name: ColumnName,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    the_connection: sqlite3.Connection = get_working_connection(provided=connection)
    qmark_list: str = __create_qmark_list(len(id_list))
    sql: str = f"""
        DELETE FROM
            {table_name.value}
        WHERE
            {song_id_column_name.value} = ?
            AND {contributor_id_column_name.value} NOT IN ({qmark_list})
    """
    values = tuple([song_id] + id_list)
    # delete
    res: int = __execute_update(sql=sql, data=values, connection=the_connection, do_commit=False)
    # commit if requested
    if do_commit or connection is None:
        commit(the_connection)
    if connection is None:
        the_connection.close()
    return res


def delete_song_artists(
        song_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return delete_by_key(
        table_name=TableName.SONG_ARTIST_V1,
        column_list=[SongArtistMetaModel.SONG_ID.column_name],
        values=[song_id],
        connection=connection,
        do_commit=do_commit)


def save_song_contributor_list(
        song_id,
        album_id: str,
        song_contributor_list: list[SongContributor],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    the_connection: sqlite3.Connection = get_working_connection(provided=connection)
    delete_song_contributors_not_in(
        song_id=song_id,
        song_contributor_list=song_contributor_list,
        connection=the_connection,
        do_commit=False)
    res: int = 0
    curr: SongContributor
    for curr in song_contributor_list if song_contributor_list else []:
        res += save_song_contributor(
            song_id=song_id,
            album_id=album_id,
            song_artist_id=curr.artist_id,
            artist_role=curr.role,
            artist_sub_role=curr.sub_role,
            connection=the_connection,
            do_commit=False)
    # commit if requested
    if do_commit or connection is None:
        commit(the_connection)
    if connection is None:
        the_connection.close()
    return res


def save_song_artist_list(
        song_id,
        album_id: str,
        song_artist_list: list[SongArtist],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    the_connection: sqlite3.Connection = get_working_connection(provided=connection)
    delete_song_artists_not_in(
        song_id=song_id,
        song_artist_list=song_artist_list,
        connection=the_connection,
        do_commit=False)
    res: int = 0
    curr: SongArtist
    for curr in song_artist_list if song_artist_list else []:
        res += save_song_artist(
            song_id=song_id,
            album_id=album_id,
            song_artist_id=curr.artist_id,
            connection=the_connection,
            do_commit=False)
    # commit if requested
    if do_commit or connection is None:
        commit(the_connection)
    if connection is None:
        the_connection.close()
    return res


def save_song_album_artist_list(
        song_id,
        album_id: str,
        song_album_artist_list: list[SongArtist],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    the_connection: sqlite3.Connection = get_working_connection(provided=connection)
    delete_song_album_artists_not_in(
        song_id=song_id,
        song_album_artist_list=song_album_artist_list,
        connection=the_connection,
        do_commit=False)
    res: int = 0
    curr: SongArtist
    for curr in song_album_artist_list if song_album_artist_list else []:
        res += save_song_album_artist(
            song_id=song_id,
            album_id=album_id,
            song_album_artist_id=curr.artist_id,
            connection=the_connection,
            do_commit=False)
    # commit if requested
    if do_commit or connection is None:
        commit(the_connection)
    if connection is None:
        the_connection.close()
    return res


def save_song_contributor(
        song_id: str,
        album_id: str,
        song_artist_id: str,
        artist_role: str,
        artist_sub_role: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    sql: str = f"""
        INSERT INTO {TableName.SONG_CONTRIBUTOR_V1.value}(
            {SongContributorMetaModel.SONG_ID.column_name.value},
            {SongContributorMetaModel.SONG_ARTIST_ID.column_name.value},
            {SongContributorMetaModel.SONG_ALBUM_ID.column_name.value},
            {SongContributorMetaModel.SONG_CONTRIBUTOR_ROLE.column_name.value},
            {SongContributorMetaModel.SONG_CONTRIBUTOR_SUB_ROLE.column_name.value})
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(
            {SongContributorMetaModel.SONG_ID.column_name.value},
            {SongContributorMetaModel.SONG_ARTIST_ID.column_name.value})
            DO UPDATE SET
                {SongContributorMetaModel.CREATED_TIMESTAMP.column_name.value} =
                    CURRENT_TIMESTAMP,
                {SongContributorMetaModel.SONG_ALBUM_ID.column_name.value} =
                    EXCLUDED.{SongArtistMetaModel.SONG_ALBUM_ID.column_name.value},
                {SongContributorMetaModel.SONG_CONTRIBUTOR_ROLE.column_name.value} =
                    EXCLUDED.{SongContributorMetaModel.SONG_CONTRIBUTOR_ROLE.column_name.value},
                {SongContributorMetaModel.SONG_CONTRIBUTOR_SUB_ROLE.column_name.value} =
                    EXCLUDED.{SongContributorMetaModel.SONG_CONTRIBUTOR_SUB_ROLE.column_name.value}
    """
    res: int = __execute_update(
        sql=sql,
        data=(song_id, song_artist_id, album_id, artist_role, artist_sub_role),
        connection=the_connection,
        do_commit=do_commit if connection else True)
    if connection is None:
        the_connection.close()
    return res


def save_song_artist(
        song_id: str,
        album_id: str,
        song_artist_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    sql: str = f"""
        INSERT INTO {TableName.SONG_ARTIST_V1.value}(
            {SongArtistMetaModel.SONG_ID.column_name.value},
            {SongArtistMetaModel.SONG_ARTIST_ID.column_name.value},
            {SongArtistMetaModel.SONG_ALBUM_ID.column_name.value})
        VALUES(?, ?, ?)
        ON CONFLICT(
            {SongArtistMetaModel.SONG_ID.column_name.value},
            {SongArtistMetaModel.SONG_ARTIST_ID.column_name.value})
            DO UPDATE SET
                {SongArtistMetaModel.CREATED_TIMESTAMP.column_name.value} =
                    CURRENT_TIMESTAMP,
                {SongArtistMetaModel.SONG_ALBUM_ID.column_name.value} =
                    EXCLUDED.{SongArtistMetaModel.SONG_ALBUM_ID.column_name.value}
    """
    res: int = __execute_update(
        sql=sql,
        data=(song_id, song_artist_id, album_id),
        connection=the_connection,
        do_commit=do_commit if connection else True)
    if connection is None:
        the_connection.close()
    return res


def save_song_album_artist(
        song_id: str,
        album_id: str,
        song_album_artist_id: str,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    sql: str = f"""
        INSERT INTO {TableName.SONG_ALBUM_ARTIST_V1.value}(
            {SongAlbumArtistMetaModel.SONG_ID.column_name.value},
            {SongAlbumArtistMetaModel.SONG_ALBUM_ARTIST_ID.column_name.value},
            {SongAlbumArtistMetaModel.SONG_ALBUM_ID.column_name.value})
        VALUES(?, ?, ?)
        ON CONFLICT(
            {SongAlbumArtistMetaModel.SONG_ID.column_name.value},
            {SongAlbumArtistMetaModel.SONG_ALBUM_ARTIST_ID.column_name.value})
            DO UPDATE SET
                {SongAlbumArtistMetaModel.CREATED_TIMESTAMP.column_name.value} =
                    CURRENT_TIMESTAMP,
                {SongAlbumArtistMetaModel.SONG_ALBUM_ID.column_name.value} =
                    EXCLUDED.{SongAlbumArtistMetaModel.SONG_ALBUM_ID.column_name.value}
    """
    res: int = __execute_update(
        sql=sql,
        data=(song_id, song_album_artist_id, album_id),
        connection=the_connection,
        do_commit=do_commit if connection else True)
    if connection is None:
        the_connection.close()
    return res


def save_album_metadata(
        album_metadata: AlbumMetadata,
        context: str = None,
        force_insert: bool = False,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> tuple[AlbumMetadata, SaveMode]:
    start: float = time.time()
    result: AlbumMetadata
    saveMode: SaveMode
    result, saveMode = __save_album_metadata(
        album_metadata=album_metadata,
        force_insert=force_insert,
        connection=connection,
        do_commit=do_commit)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.TRACE_PERSISTENCE_OPERATIONS):
        msgproc.log(f"save_album_metadata for album_id [{album_metadata.album_id}] "
                    f"context [{context}] "
                    f"force_insert [{force_insert}] "
                    f"mode [{saveMode}] "
                    f"executed in [{elapsed:.3f}]")
    return (result, saveMode)


def update_album_metadata_table(
        album_id: str,
        values: dict[AlbumMetadataModel, Any],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    sql: str = sqlhelper.create_simple_update_sql(
        table_name=TableName.ALBUM_METADATA_V1.value,
        set_column_list=[x.column_name.value for x in values.keys()],
        where_column_list=[AlbumMetadataModel.ALBUM_ID.column_name.value])
    data: tuple[Any] = tuple(list(values.values()) + [album_id])
    return __execute_update(
       sql=sql,
       data=data,
       connection=connection,
       do_commit=do_commit)


def __save_album_metadata(
        album_metadata: AlbumMetadata,
        force_insert: bool = False,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> tuple[AlbumMetadata, SaveMode]:
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    existing_metadata: AlbumMetadata = (get_album_metadata(album_id=album_metadata.album_id, connection=the_connection)
                                        if not force_insert
                                        else None)
    if existing_metadata:
        # update
        updated_metadata: AlbumMetadata = metadata_converter.update_album_metadata(
            existing_metadata=existing_metadata,
            album_metadata=album_metadata)
        set_values: list[Any] = list(map(lambda x: updated_metadata.get_value(x), __album_metadata_model_non_pk_list))
        where_values: list[Any] = list(map(lambda x: updated_metadata.get_value(x), __album_metadata_model_pk_list))
        update_sql: str = sqlhelper.create_simple_update_sql(
            table_name=TableName.ALBUM_METADATA_V1.value,
            set_column_list=__album_metadata_model_non_pk_column_names,
            where_column_list=__album_metadata_model_pk_column_names)
        update_values = tuple(set_values + where_values)
        upd_res: int = __execute_update(
            sql=update_sql,
            data=update_values,
            connection=the_connection,
            do_commit=do_commit)
        if upd_res != 1:
            msgproc.log(f"__save_album_metadata could not update with album_id [{album_metadata.album_id}] "
                        f"upd_res [{upd_res}]")
        if connection is None:
            the_connection.close()
        return (updated_metadata, SaveMode.UPDATED)
    else:
        # set timestamps
        album_metadata.set_value(AlbumMetadataModel.CREATED_TIMESTAMP, datetime.datetime.now())
        album_metadata.set_value(AlbumMetadataModel.UPDATED_TIMESTAMP, datetime.datetime.now())
        # insert
        ins_res: int = __insert_album_metadata(
            album_metadata=album_metadata,
            connection=the_connection,
            do_commit=do_commit)
        if ins_res != 1:
            msgproc.log(f"__save_album_metadata could not insert with album_id [{album_metadata.album_id}] "
                        f"ins_res [{ins_res}]")
        if connection is None:
            the_connection.close()
        return (album_metadata, SaveMode.INSERTED)


def save_artist_metadata(
        artist_metadata: ArtistMetadata,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> ArtistMetadata:
    start: float = time.time()
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    result: ArtistMetadata = __save_artist_metadata(
        artist_metadata=artist_metadata,
        connection=the_connection,
        do_commit=do_commit)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"save_artist_metadata for artist_id [{artist_metadata.artist_id}] executed in [{elapsed:.3f}]")
    if connection is None:
        the_connection.close()
    return result


def prune_metadata(
        table_name: TableName,
        update_timestamp: datetime.datetime,
        connection: sqlite3.Connection,
        do_commit: bool = True) -> int:
    sql: str = f"""
        DELETE FROM {table_name.value}
        WHERE {ColumnName.UPDATED_TIMESTAMP.value} < ?
    """
    return __execute_update(
        sql=sql,
        data=(update_timestamp,),
        connection=connection,
        do_commit=do_commit)


def prune_artist_metadata(
        update_timestamp: datetime.datetime,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return prune_metadata(
        table_name=TableName.ARTIST_METADATA_V1,
        update_timestamp=update_timestamp,
        connection=connection,
        do_commit=do_commit)


def prune_album_metadata(
        update_timestamp: datetime.datetime,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return prune_metadata(
        table_name=TableName.ALBUM_METADATA_V1,
        update_timestamp=update_timestamp,
        connection=connection,
        do_commit=do_commit)


def prune_song_metadata(
        update_timestamp: datetime.datetime,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return prune_metadata(
        table_name=TableName.SONG_METADATA_V1,
        update_timestamp=update_timestamp,
        connection=connection,
        do_commit=do_commit)


def __save_artist_metadata(
        artist_metadata: ArtistMetadata,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> ArtistMetadata:
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"save_artist_metadata for artist_id: {artist_metadata.artist_id} "
                    f"name [{artist_metadata.artist_name}] "
                    f"musicbrainz_id [{artist_metadata.artist_musicbrainz_id}]")
    existing_metadata: ArtistMetadata = get_artist_metadata(
        artist_id=artist_metadata.artist_id,
        connection=the_connection)
    if existing_metadata:
        # update
        updated_metadata: ArtistMetadata = metadata_converter.update_artist_metadata(
            existing_metadata=existing_metadata,
            artist_metadata=artist_metadata)
        set_values: list[Any] = list(map(lambda x: updated_metadata.get_value(x), __artist_metadata_model_non_pk_list))
        where_values: list[Any] = list(map(lambda x: updated_metadata.get_value(x), __artist_metadata_model_pk_list))
        update_sql: str = sqlhelper.create_simple_update_sql(
            table_name=TableName.ARTIST_METADATA_V1.value,
            set_column_list=__artist_metadata_model_non_pk_column_names,
            where_column_list=__artist_metadata_model_pk_column_names)
        update_values = tuple(set_values + where_values)
        __execute_update(
            sql=update_sql,
            data=update_values,
            connection=the_connection,
            do_commit=do_commit)
        if connection is None:
            the_connection.close()
        return updated_metadata
    else:
        # insert
        __insert_artist_metadata(
            artist_metadata=artist_metadata,
            connection=the_connection,
            do_commit=do_commit)
        if connection is None:
            the_connection.close()
        return artist_metadata


def save_kv_item(
        key_value_item: KeyValueItem,
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    the_connection: sqlite3.Connection = get_working_connection(provided=connection)
    put_key_value_item(
        key_value_item=key_value_item,
        updater=(lambda partition, key, value, update_timestamp, do_commit: __update_kv_item(
                    partition=partition,
                    key=key,
                    value=value,
                    update_timestamp=update_timestamp,
                    connection=the_connection,
                    do_commit=do_commit)),
        creator=(lambda key_value_item, creation_timestamp, do_commit: _insert_key_value_item(
                    key_value_item=key_value_item,
                    creation_timestamp=creation_timestamp,
                    connection=the_connection,
                    do_commit=do_commit)),
        loader=(lambda partition, key: __load_key_value_item(
                    partition=partition,
                    key=key,
                    connection=the_connection)),
        do_commit=do_commit)


def __insert_song_metadata(
        song_metadata: SongMetadata,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    insert_values = tuple(list(map(lambda x: song_metadata.get_value(x), __song_metadata_model_list)))
    insert_sql: str = sqlhelper.create_simple_insert_sql(
        table_name=TableName.SONG_METADATA_V1.value,
        column_list=__song_metadata_model_all_column_names)
    return __execute_update(
        sql=insert_sql,
        data=insert_values,
        connection=connection,
        do_commit=do_commit)


def __insert_album_metadata(
        album_metadata: AlbumMetadata,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    insert_values = tuple(list(map(lambda x: album_metadata.get_value(x), __album_metadata_model_list)))
    insert_sql: str = sqlhelper.create_simple_insert_sql(
        table_name=TableName.ALBUM_METADATA_V1.value,
        column_list=__album_metadata_model_all_column_names)
    return __execute_update(
        sql=insert_sql,
        data=insert_values,
        connection=connection,
        do_commit=do_commit)


def __insert_artist_metadata(
        artist_metadata: ArtistMetadata,
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    insert_values = tuple(list(map(lambda x: artist_metadata.get_value(x), __artist_metadata_model_list)))
    insert_sql: str = sqlhelper.create_simple_insert_sql(
        table_name=TableName.ARTIST_METADATA_V1.value,
        column_list=__artist_metadata_model_all_column_names)
    __execute_update(
        sql=insert_sql,
        data=insert_values,
        connection=connection,
        do_commit=do_commit)


def update_artist_roles(
        artist_id: str,
        artist_roles: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    # in the end, roles must match the provided roles
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    existing: list[ArtistRole] = __load_artist_roles(artist_id=artist_id, connection=the_connection)
    existing_roles: list[str] = list(map(lambda x: x.artist_role, existing))
    to_add: list[str] = list(filter(lambda r: r not in existing_roles, artist_roles))
    to_delete: list[str] = list(filter(lambda r: r not in artist_roles, existing_roles))
    total_op: int = len(to_add) + len(to_delete)
    op_counter: int = 0
    # insert missing
    if len(to_add) > 0:
        insert_sql: str = sqlhelper.create_simple_insert_sql(
            table_name=TableName.ARTIST_ROLE_V1.value,
            column_list=[ColumnName.ARTIST_ID.value, ColumnName.ARTIST_ROLE.value])
        i: str
        for i in to_add:
            op_counter += 1
            __execute_update(
                sql=insert_sql,
                data=(artist_id, i),
                connection=the_connection,
                do_commit=True if do_commit and op_counter == total_op else False)
    # delete removed
    if len(to_delete) > 0:
        delete_sql: str = sqlhelper.create_simple_delete_sql(
            table_name=TableName.ARTIST_ROLE_V1.value,
            where_column_list=[
                ColumnName.ARTIST_ID.value,
                ColumnName.ARTIST_ROLE.value])
        i: str
        for i in to_delete:
            # msgproc.log(f"update_artist_roles deleting [{artist_id}] [{i}]")
            op_counter += 1
            __execute_update(
                sql=delete_sql,
                data=(artist_id, i),
                connection=the_connection,
                do_commit=True if do_commit and op_counter == total_op else False)
    if connection is None:
        the_connection.close()


def __insert_album_discs(
        album_id: str,
        album_discs: list[DiscTitle],
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    return __insert_list(
        table_name=TableName.ALBUM_DISC_V1,
        column_list=[
            ColumnName.ALBUM_ID,
            ColumnName.DISC_NUM,
            ColumnName.DISC_TITLE,
            ColumnName.CREATED_TIMESTAMP],
        data_list=album_discs,
        column_extractor=lambda x: [
            album_id,
            x.disc_num,
            x.title,
            datetime.datetime.now()],
        connection=connection,
        do_commit=do_commit)


def __insert_album_genres(
        album_id: str,
        album_genres: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    return __insert_list(
        table_name=TableName.ALBUM_GENRE_V1,
        column_list=[
            ColumnName.ALBUM_ID,
            ColumnName.ALBUM_GENRE],
        data_list=album_genres,
        column_extractor=lambda x: [
            album_id,
            x],
        connection=connection,
        do_commit=do_commit)


def __insert_album_moods(
        album_id: str,
        album_moods: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    return __insert_list(
        table_name=TableName.ALBUM_MOOD_V1,
        column_list=[
            ColumnName.ALBUM_ID,
            ColumnName.ALBUM_MOOD],
        data_list=album_moods,
        column_extractor=lambda x: [
            album_id,
            x],
        connection=connection,
        do_commit=do_commit)


def __insert_album_release_types(
        album_id: str,
        album_release_types: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    return __insert_list(
        table_name=TableName.ALBUM_RELEASE_TYPE_V1,
        column_list=[
            ColumnName.ALBUM_ID,
            ColumnName.ALBUM_RELEASE_TYPE],
        data_list=album_release_types,
        column_extractor=lambda x: [
            album_id,
            x],
        connection=connection,
        do_commit=do_commit)


def __insert_album_record_labels(
        album_id: str,
        album_record_labels: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    return __insert_list(
        table_name=TableName.ALBUM_RECORD_LABEL_V1,
        column_list=[
            ColumnName.ALBUM_ID,
            ColumnName.ALBUM_RECORD_LABEL],
        data_list=album_record_labels,
        column_extractor=lambda x: [
            album_id,
            x],
        connection=connection,
        do_commit=do_commit)


def __insert_album_artists(
        album_id: str,
        album_artists: list[ArtistFromAlbum],
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    return __insert_list(
        table_name=TableName.ALBUM_ARTIST_V1,
        column_list=[
            ColumnName.ALBUM_ID,
            ColumnName.ARTIST_ID,
            ColumnName.ARTIST_NAME,
            ColumnName.CREATED_TIMESTAMP],
        data_list=album_artists,
        column_extractor=lambda x: [
            album_id,
            x.artist_id,
            x.artist_name,
            datetime.datetime.now()],
        connection=connection,
        do_commit=do_commit)


def __insert_list(
        table_name: TableName,
        column_list: list[ColumnName],
        data_list: list[Any],
        column_extractor: Callable[[Any], list[Any]],
        connection: sqlite3.Connection = None,
        do_commit: bool = True):
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    insert_sql: str = sqlhelper.create_simple_insert_sql(
        table_name=table_name.value,
        column_list=list(map(lambda x: x.value, column_list)))
    ins_count: int = 0
    op_counter: int = 0
    curr: ArtistFromAlbum
    for curr in data_list:
        # insert
        op_counter += 1
        data_list: list[Any] = column_extractor(curr)
        ins_count += __execute_update(
            sql=insert_sql,
            data=tuple(data_list),
            connection=the_connection,
            do_commit=False)
    if connection is None:
        # connection was not provided, we must commit
        commit(connection=the_connection)
        the_connection.close()
    else:
        # connection was provided, commit?
        if do_commit:
            commit(connection=the_connection)
    return ins_count


def update_album_discs(
        album_id: str,
        album_discs: list[DiscTitle],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return update_album_multivalue_table(
        album_id=album_id,
        values=album_discs,
        delete_f=__delete_album_discs,
        insert_f=__insert_album_discs,
        connection=connection,
        do_commit=do_commit,
        context="update_album_discs")


def update_album_artists(
        album_id: str,
        album_artists: list[ArtistFromAlbum],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return update_album_multivalue_table(
        album_id=album_id,
        values=album_artists,
        delete_f=__delete_album_artists,
        insert_f=__insert_album_artists,
        connection=connection,
        do_commit=do_commit,
        context="update_album_artists")


def update_album_genres(
        album_id: str,
        album_genres: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return update_album_multivalue_table(
        album_id=album_id,
        values=album_genres,
        delete_f=__delete_album_genres,
        insert_f=__insert_album_genres,
        connection=connection,
        do_commit=do_commit,
        context="update_album_genres")


def update_album_record_labels(
        album_id: str,
        album_record_labels: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return update_album_multivalue_table(
        album_id=album_id,
        values=album_record_labels,
        delete_f=__delete_album_record_labels,
        insert_f=__insert_album_record_labels,
        connection=connection,
        do_commit=do_commit,
        context="update_album_record_labels")


def update_album_moods(
        album_id: str,
        album_moods: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return update_album_multivalue_table(
        album_id=album_id,
        values=album_moods,
        delete_f=__delete_album_moods,
        insert_f=__insert_album_moods,
        connection=connection,
        do_commit=do_commit,
        context="update_album_moods")


def update_album_release_types(
        album_id: str,
        album_release_types: list[str],
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    return update_album_multivalue_table(
        album_id=album_id,
        values=album_release_types,
        delete_f=__delete_album_release_types,
        insert_f=__insert_album_release_types,
        connection=connection,
        do_commit=do_commit,
        context="update_album_release_types")


def update_album_multivalue_table(
        album_id: str,
        values: list[Any],
        delete_f: Callable[[str, sqlite3.Connection, bool], None],
        insert_f: Callable[[str, list[Any], sqlite3.Connection, bool], None],
        connection: sqlite3.Connection = None,
        do_commit: bool = True,
        context: str = None) -> int:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    try:
        delete_f(album_id, connection, False)
    except Exception as ex:
        msgproc.log(f"update_album_multivalue_table cannot delete album_id [{album_id}] "
                    f"context [{context}] "
                    f"for inserting values [{values}] "
                    f"due to [{type(ex)}] [{ex}]")
        raise ex
    ins_count: int = 0
    if values and len(values) > 0:
        try:
            ins_count += insert_f(album_id, values, connection, False)
        except Exception as ex:
            msgproc.log(f"update_album_multivalue_table cannot update album_id [{album_id}] "
                        f"context [{context}] "
                        f"with values [{values}] "
                        f"due to [{type(ex)}] [{ex}]")
            raise ex
    if connection is None:
        # we must commit and close
        commit(connection=the_connection)
        the_connection.close()
    else:
        # commit if requested
        if do_commit:
            commit(connection=connection)
    return ins_count


def get_album_property_dataset(
        property_key_list: list[str],
        connection: sqlite3.Connection = None) -> list[AlbumPropertyMetadata]:
    if len(property_key_list if property_key_list else []) == 0:
        raise Exception("get_album_property_dataset requires a list of property keys")
    qmarks: str = __create_qmark_list(len(property_key_list))
    sql: str = f"""
        SELECT
            {AlbumPropertyMetaModel.ALBUM_ID.column_name.value},
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value},
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE.column_name.value},
            {AlbumPropertyMetaModel.CREATED_TIMESTAMP.column_name.value},
            {AlbumPropertyMetaModel.UPDATED_TIMESTAMP.column_name.value}
        FROM
            {TableName.ALBUM_PROPERTY_V1.value}
        WHERE
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value} IN ({qmarks})
    """
    the_connection: sqlite3.Connection = get_working_connection(connection)
    result: list[AlbumPropertyMetadata] = []
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(sql=sql, parameters=tuple(property_key_list))
    for row in rows if rows else []:
        album_id: str = row[0]
        key: str = row[1]
        value: str = row[2]
        created: datetime.datetime = row[3]
        updated: datetime.datetime = row[4]
        curr: AlbumPropertyMetadata = AlbumPropertyMetadata()
        curr.set_value(AlbumPropertyMetaModel.ALBUM_ID, album_id)
        curr.set_value(AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY, key)
        curr.set_value(AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE, value)
        curr.set_value(AlbumPropertyMetaModel.CREATED_TIMESTAMP, created)
        curr.set_value(AlbumPropertyMetaModel.UPDATED_TIMESTAMP, updated)
        result.append(curr)
    if connection is None:
        the_connection.close()
    return result


def get_album_property_values(
        condition_list: list[AlbumPropertyKeyValue] = None,
        connection: sqlite3.Connection = None) -> list[AlbumPropertyValueSelection]:
    # msgproc.log(f"get_album_property_values condition count [{len(condition_list) if condition_list else 0}]")
    sql_initial: str = f"""
        SELECT
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value},
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE.column_name.value},
            count(*)
        FROM
            {TableName.ALBUM_PROPERTY_V1.value}
    """
    sql_intermediate: str = None
    if condition_list and len(condition_list) > 0:
        where_condition: str = (f"({AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value} = ? AND "
                                f"{AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE.column_name.value} = ?)")
        where: str = " OR ".join([where_condition] * len(condition_list))
        sql_intermediate = f"""
            WHERE {AlbumPropertyMetaModel.ALBUM_ID.column_name.value} in (
                SELECT
                    {AlbumPropertyMetaModel.ALBUM_ID.column_name.value}
                FROM
                    {TableName.ALBUM_PROPERTY_V1.value}
                WHERE
                    {where}
                GROUP BY
                    {AlbumPropertyMetaModel.ALBUM_ID.column_name.value}
                HAVING
                    COUNT(DISTINCT {AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE.column_name.value}) = {len(condition_list)})
        """
    else:
        sql_intermediate = ""
    sql_final: str = f"""
        GROUP BY
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value},
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE.column_name.value}
        ORDER BY
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value},
            {AlbumPropertyMetaModel.ALBUM_PROPERTY_VALUE.column_name.value}
    """
    sql: str = sql_initial + sql_intermediate + sql_final
    parameters: list[str] = []
    curr: AlbumPropertyKeyValue
    for curr in condition_list if condition_list else []:
        parameters.extend([curr.key, curr.value])
    # msgproc.log(f"sql [{sql}] parameters [{parameters}]")
    the_connection: sqlite3.Connection = get_working_connection(connection)
    result: list[AlbumPropertyValueSelection] = []
    rows: list[any] = __get_sqlite3_selector(connection=the_connection)(
        sql=sql,
        parameters=tuple(parameters))
    for row in rows if rows else []:
        key: str = row[0]
        value: str = row[1]
        album_count: int = row[2]
        result.append(AlbumPropertyValueSelection(
            album_property_key=key,
            album_property_value=value,
            album_count=album_count))
    if connection is None:
        the_connection.close()
    return result


def purge_spurious_caches():
    msgproc.log("purge_spurious_caches starting ...")
    cache_not_in: list[str] = [c.cache_name for c in CacheType]
    qmark_list: str = __create_qmark_list(len(cache_not_in))
    sql: str = f"""
        DELETE FROM {TableName.KV_CACHE_V1.name}
        WHERE {KeyValueCacheColumnName.ITEM_PARTITION.value} NOT IN ({qmark_list})
    """
    t = tuple(cache_not_in)
    upd_count: int = __execute_update(
        sql=sql,
        data=t)
    msgproc.log(f"purge_spurious_caches deleted [{upd_count}] entries")


def purge_id_cache():
    msgproc.log("purge_id_cache starting ...")
    sql: str = f"""
        DELETE FROM {TableName.KV_CACHE_V1.name}
        WHERE {KeyValueCacheColumnName.ITEM_PARTITION.value} = ?
    """
    t = (CacheType.ITEM_IDENTIFIER_CODEC.cache_name,)
    upd_count: int = __execute_update(
        sql=sql,
        data=t)
    msgproc.log(f"purge_id_cache deleted [{upd_count}] entries")


def _insert_key_value_item(
        key_value_item: KeyValueItem,
        creation_timestamp: datetime.datetime,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> None:
    the_connection: sqlite3.Connection = get_working_connection(connection)
    insert_kv_item_v1(
        sql_executor=__get_sqlite3_executor(the_connection),
        key_value_item=key_value_item,
        creation_timestamp=creation_timestamp,
        do_commit=do_commit if connection else True)
    if connection is None:
        the_connection.close()


def __execute_update(
        sql: str,
        data: tuple,
        connection: sqlite3.Connection = None,
        do_commit: bool = True) -> int:
    the_connection: sqlite3.Connection = connection if connection is not None else __get_connection()
    update_count: int = sqlhelper.neutral_execute_update(
        sql_executor=sqlite3util.get_sqlite3_executor(the_connection),
        sql=sql,
        data=data,
        do_commit=do_commit if connection is not None else True)
    if connection is None:
        the_connection.close()
    return update_count


def lock_immediate(connection: sqlite3.Connection):
    connection.execute("BEGIN IMMEDIATE")


def rollback(connection: sqlite3.Connection):
    connection.rollback()


def commit(connection: sqlite3.Connection):
    connection.commit()


def do_vacuum():
    msgproc.log("Executing VACUUM ...")
    connection: sqlite3.Connection = __get_connection()
    cursor_obj = connection.cursor()
    cursor_obj.execute("VACUUM")
    cursor_obj.close()
    connection.close()
    msgproc.log("VACCUM executed.")


def __do_delete_table(table_name: str):
    msgproc.log(f"Deleting table {table_name} ...")
    connection: sqlite3.Connection = __get_connection()
    cursor_obj = connection.cursor()
    cursor_obj.execute(f"DROP TABLE {table_name}")
    cursor_obj.close()
    connection.close()
    msgproc.log(f"Deleted table {table_name}.")


def __do_create_table(table_name: str, sql: str):
    msgproc.log(f"Preparing table {table_name} ...")
    connection: sqlite3.Connection = __get_connection()
    cursor_obj = connection.cursor()
    cursor_obj.execute(sql)
    cursor_obj.close()
    connection.close()
    msgproc.log(f"Prepared table {table_name}.")


def __get_db_filename() -> str:
    return f"{constants.PluginConstant.PLUGIN_NAME.value}.db"


def __get_db_full_path() -> str:
    return os.path.join(
        upmplgutils.getcachedir(constants.PluginConstant.PLUGIN_NAME.value),
        __get_db_filename())


def __get_connection() -> sqlite3.Connection:
    sqlite3.register_converter("TIMESTAMP", __adapt_flexible_timestamp)
    connection = sqlite3.connect(
        __get_db_full_path(),
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def __prepare_table_db_version():
    # Creating table
    create_table: str = f"""
        CREATE TABLE IF NOT EXISTS {TableName.DB_VERSION.value}(
        version VARCHAR(32) PRIMARY KEY)
    """
    connection: sqlite3.Connection = __get_connection()
    cursor_obj = connection.cursor()
    cursor_obj.execute(create_table)
    cursor_obj.close()
    connection.close()


def get_db_version() -> str:
    connection: sqlite3.Connection = __get_connection()
    cursor = connection.cursor()
    cursor.execute(sqlhelper.create_simple_select_sql(
        table_name=TableName.DB_VERSION.value,
        select_column_list=["version"]))
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    if rows:
        return rows[0][0]
    return None


def __store_db_version(version: str):
    db_version: str = get_db_version()
    if not db_version:
        msgproc.log(f"Setting db version to [{version}] ...")
        insert_tuple = (version, )
        connection: sqlite3.Connection = __get_connection()
        cursor = connection.cursor()
        insert_sql: str = sqlhelper.create_simple_insert_sql(
            table_name=TableName.DB_VERSION.value,
            column_list=["version"])
        cursor.execute(insert_sql, insert_tuple)
        cursor.close()
        connection.commit()
        connection.close()
    else:
        msgproc.log(f"Updating db version to [{version}] from [{db_version}] ...")
        update_tuple = (version, db_version)
        connection: sqlite3.Connection = __get_connection()
        cursor = connection.cursor()
        update_sql: str = sqlhelper.create_simple_update_sql(
            table_name=TableName.DB_VERSION.value,
            set_column_list=["version"],
            where_column_list=["version"])
        cursor.execute(update_sql, update_tuple)
        cursor.close()
        connection.commit()
        connection.close()
    msgproc.log(f"Db version correctly set to [{version}]")


def do_migration_66():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_MEDIA_TYPE.column_name,
            column_type="VARCHAR(255)"))


def do_migration_65():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_DISC_COUNT.column_name,
            column_type="INTEGER"))


def do_migration_64():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_RELEASE_TYPE_LIST.column_name,
            column_type="TEXT"))


def do_migration_63():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_RECORD_LABEL_LIST.column_name,
            column_type="TEXT"))


def do_migration_62():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_MOOD_LIST.column_name,
            column_type="TEXT"))


def do_migration_61():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_GENRE_LIST.column_name,
            column_type="TEXT"))


def do_migration_60():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_RELEASE_DATE_STR.column_name,
            column_type="VARCHAR(255)"))


def do_migration_59():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_ORIGINAL_RELEASE_DATE_STR.column_name,
            column_type="VARCHAR(255)"))


def do_migration_58():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_LOSSLESS_STATUS.column_name,
            column_type="VARCHAR(255)"))


def do_migration_57():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=AlbumMetadataModel.ALBUM_AVERAGE_BITRATE.column_name,
            column_type="INTEGER"))


def do_migration_56():
    __do_create_table(
        table_name=TableName.ALBUM_PROPERTY_V1.value,
        sql=create_index_on_columns(
            table_name=TableName.ALBUM_PROPERTY_V1.value,
            index_name=(f"{TableName.ALBUM_PROPERTY_V1.value}_"
                        f"{AlbumPropertyMetaModel.ALBUM_ID.column_name.value}_"
                        f"{AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value}"),
            column_name_list=[AlbumPropertyMetaModel.ALBUM_ID.column_name, AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name]))


def do_migration_55():
    __do_create_table(
        table_name=TableName.ALBUM_PROPERTY_V1.value,
        sql=__get_sql_create_table_album_property_v1())


def do_migration_54():
    __do_create_table(
        table_name=TableName.SONG_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.SONG_METADATA_V1,
            column_name=SongMetadataModel.SONG_LOSSLESS_STATUS.column_name,
            column_type="VARCHAR(255)"))


def do_migration_53():
    __do_delete_table(table_name=DeletedTableName.ALBUM_COVER_ART_BY_ARTIST_V1.value)


def do_migration_52():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=create_index_on_columns(
            table_name=TableName.ALBUM_METADATA_V1.value,
            index_name=f"{TableName.ALBUM_METADATA_V1.value}_{AlbumMetadataModel.ALBUM_ARTIST_ID.column_name.value}_index",
            column_name_list=[AlbumMetadataModel.ALBUM_ARTIST_ID.column_name]))


def do_migration_51():
    __do_create_table(
        table_name=TableName.SONG_CONTRIBUTOR_V1.value,
        sql=__get_sql_create_table_song_contributor_v1())


def do_migration_50():
    __do_create_table(
        table_name=TableName.SONG_METADATA_V1.value,
        sql=create_index_on_columns(
            table_name=TableName.SONG_METADATA_V1.value,
            index_name=f"{TableName.SONG_METADATA_V1.value}_{SongMetadataModel.SONG_COVER_ART.column_name.value}_index",
            column_name_list=[SongMetadataModel.SONG_COVER_ART.column_name]))


def do_migration_49():
    __do_create_table(
        table_name=TableName.SONG_ARTIST_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.SONG_ARTIST_V1,
            column_name=SongArtistMetaModel.SONG_ALBUM_ID.column_name,
            column_type="VARCHAR(255)"))


def do_migration_48():
    __do_create_table(
        table_name=TableName.SONG_ALBUM_ARTIST_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.SONG_ALBUM_ARTIST_V1,
            column_name=SongAlbumArtistMetaModel.SONG_ALBUM_ID.column_name,
            column_type="VARCHAR(255)"))


def do_migration_47():
    __do_create_table(
        table_name=TableName.SONG_ARTIST_V1.value,
        sql=__get_sql_create_table_song_artist_v1())


def do_migration_46():
    __do_create_table(
        table_name=TableName.SONG_ALBUM_ARTIST_V1.value,
        sql=__get_sql_create_table_song_album_artist_v1())


def do_migration_45():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA_V1.value,
        sql=create_index_on_columns(
            table_name=TableName.ARTIST_METADATA_V1.value,
            index_name=f"{TableName.ARTIST_METADATA_V1.value}_{ArtistMetadataModel.ARTIST_COVER_ART.column_name.value}_index",
            column_name_list=[ArtistMetadataModel.ARTIST_COVER_ART.column_name]))


def do_migration_44():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=create_index_on_columns(
            table_name=TableName.ALBUM_METADATA_V1.value,
            index_name=f"{TableName.ALBUM_METADATA_V1.value}_{ColumnName.ALBUM_COVER_ART.value}_index",
            column_name_list=[ColumnName.ALBUM_COVER_ART]))


def do_migration_43():
    __do_create_table(
        table_name=DeletedTableName.ALBUM_COVER_ART_BY_ARTIST_V1.value,
        sql=create_index_on_columns(
            table_name=DeletedTableName.ALBUM_COVER_ART_BY_ARTIST_V1.value,
            index_name="album_cover_art_by_artist_v1_album_cover_art_index",
            column_name_list=[ColumnName.ALBUM_COVER_ART]))


def do_migration_42():
    # msgproc.log(__get_sql_create_table_album_art_by_artist_v1())
    __do_create_table(
        table_name=DeletedTableName.ALBUM_COVER_ART_BY_ARTIST_V1.value,
        sql=__get_sql_create_table_album_art_by_artist_v1())


def do_migration_41():
    __do_create_table(
        table_name=TableName.SONG_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.SONG_METADATA_V1,
            column_name=ColumnName.SONG_DISPLAY_COMPOSER,
            column_type="TEXT"))
    __do_create_table(
        table_name=TableName.SONG_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.SONG_METADATA_V1,
            column_name=ColumnName.SONG_SORT_NAME,
            column_type="TEXT"))


def do_migration_40():
    __do_create_table(
        table_name=TableName.SONG_METADATA_V1.value,
        sql=__get_sql_create_table_song_metadata_v1())


def do_migration_39():
    __do_create_table(
        table_name=TableName.ALBUM_RELEASE_TYPE_V1.value,
        sql=__get_sql_create_table_album_release_type_v1())


def do_migration_38():
    __do_create_table(
        table_name=TableName.ALBUM_MOOD_V1.value,
        sql=__get_sql_create_table_album_mood_v1())


def do_migration_37():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_TRACK_QUALITY_SUMMARY,
            column_type="VARCHAR(255)"))


def do_migration_36():
    __do_create_table(
        table_name=TableName.ALBUM_RECORD_LABEL_V1.value,
        sql=__get_sql_create_table_album_record_label_v1())


def do_migration_35():
    __do_create_table(
        table_name=TableName.ALBUM_GENRE_V1.value,
        sql=__get_sql_create_table_album_genre_v1())


def do_migration_34():
    __do_create_table(
        table_name=TableName.ALBUM_ARTIST_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_ARTIST_V1,
            column_name=ColumnName.CREATED_TIMESTAMP,
            column_type="TIMESTAMP"))
    __do_create_table(
        table_name=TableName.ALBUM_DISC_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_DISC_V1,
            column_name=ColumnName.CREATED_TIMESTAMP,
            column_type="TIMESTAMP"))


def do_migration_33():
    __do_create_table(
        table_name=TableName.ALBUM_ARTIST_V1.value,
        sql=create_index_on_columns(
            table_name=TableName.ALBUM_ARTIST_V1.value,
            index_name="album_artist_artist_occurrence_index",
            column_name_list=[ColumnName.ALBUM_ID, ColumnName.ARTIST_ID]))
    __do_create_table(
        table_name=TableName.ALBUM_DISC_V1.value,
        sql=create_index_on_columns(
            table_name=TableName.ALBUM_DISC_V1.value,
            index_name="album_disc_index_index",
            column_name_list=[ColumnName.ALBUM_ID, ColumnName.DISC_NUM]))


def do_migration_32():
    __do_create_table(
        table_name=TableName.ALBUM_DISC_V1.value,
        sql=__sql_create_table_album_disc_v1)


def do_migration_31():
    __do_create_table(
        table_name=TableName.ALBUM_ARTIST_V1.value,
        sql=__sql_create_table_album_artist_v1)


def do_migration_30():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_ORIGINAL_RELEASE_DATE_YEAR,
            column_type="INTEGER"))
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_ORIGINAL_RELEASE_DATE_MONTH,
            column_type="INTEGER"))
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_ORIGINAL_RELEASE_DATE_DAY,
            column_type="INTEGER"))
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_RELEASE_DATE_YEAR,
            column_type="INTEGER"))
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_RELEASE_DATE_MONTH,
            column_type="INTEGER"))
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_RELEASE_DATE_DAY,
            column_type="INTEGER"))


def do_migration_29():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_VERSION,
            column_type="VARCHAR(255)"))


def do_migration_28():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_SORT_NAME,
            column_type="VARCHAR(255)"))


def do_migration_27():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_PLAYED,
            column_type="TIMESTAMP"))


def do_migration_26():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_PLAY_COUNT,
            column_type="INTEGER"))


def do_migration_25():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_IS_COMPILATION,
            column_type="INTEGER"))


def do_migration_24():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.EXPLICIT_STATUS,
            column_type="VARCHAR(64)"))


def do_migration_23():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_DISPLAY_ARTIST,
            column_type="VARCHAR(255)"))


def do_migration_22():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_USER_RATING,
            column_type="INTEGER"))


def do_migration_21():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_GENRE,
            column_type="VARCHAR(255)"))


def do_migration_20():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_YEAR,
            column_type="INTEGER"))


def do_migration_19():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_CREATED,
            column_type="TIMESTAMP"))


def do_migration_18():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_DURATION,
            column_type="INTEGER"))


def do_migration_17():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_SONG_COUNT,
            column_type="INTEGER"))


def do_migration_16():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_NAME,
            column_type="VARCHAR(255)"))


def do_migration_15():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_COVER_ART,
            column_type="VARCHAR(255)"))


def do_migration_14():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_ARTIST,
            column_type="VARCHAR(255)"))


def do_migration_13():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA_V1.value,
        sql=create_index_on_single_column(
            table_name=TableName.ARTIST_METADATA_V1.value,
            column_name=ColumnName.UPDATED_TIMESTAMP.value))
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=create_index_on_single_column(
            table_name=TableName.ALBUM_METADATA_V1.value,
            column_name=ColumnName.UPDATED_TIMESTAMP.value))


def do_migration_12():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ARTIST_METADATA_V1,
            column_name=ColumnName.ARTIST_SORT_NAME,
            column_type="VARCHAR(255)"))


def do_migration_11():
    __do_create_table(
        table_name=TableName.ARTIST_ROLE_V1.value,
        sql=__sql_create_table_artist_role_v1)


def do_migration_10():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ARTIST_METADATA_V1,
            column_name=ColumnName.ARTIST_MEDIA_TYPE,
            column_type="VARCHAR(255)"))


def do_migration_9():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_PATH,
            column_type=f"VARCHAR({constants.MaxLength.ALBUM_PATH.value})"))


def do_migration_8():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ARTIST_METADATA_V1,
            column_name=ColumnName.ARTIST_COVER_ART,
            column_type="VARCHAR(255)"))


def do_migration_7():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ARTIST_METADATA_V1,
            column_name=ColumnName.ARTIST_ALBUM_COUNT,
            column_type="INTEGER"))


def do_migration_6():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_ARTIST_ID,
            column_type="VARCHAR(255)"))


def do_migration_5():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ALBUM_METADATA_V1,
            column_name=ColumnName.ALBUM_MB_ID,
            column_type="VARCHAR(255)"))


def do_migration_4():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA_V1.value,
        sql=__get_sql_alter_table_add_column(
            table_name=TableName.ARTIST_METADATA_V1,
            column_name=ColumnName.ARTIST_MB_ID,
            column_type="VARCHAR(255)"))


def do_migration_3():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA_V1.value,
        sql=__sql_create_table_artist_metadata_v1)


def do_migration_2():
    __do_create_table(
        table_name=KeyValueTableName.TABLE_NAME_V1.table_name,
        sql=build_create_cache_v1_sql())


def do_migration_1():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA_V1.value,
        sql=__sql_create_table_album_metadata_v1)


def migration_24():
    migration_template("25", do_migration_24)


def migration_23():
    migration_template("24", do_migration_23)


def migration_22():
    migration_template("23", do_migration_22)


def migration_21():
    migration_template("22", do_migration_21)


def migration_20():
    migration_template("21", do_migration_20)


def migration_19():
    migration_template("20", do_migration_19)


def migration_18():
    migration_template("19", do_migration_18)


def migration_17():
    migration_template("18", do_migration_17)


def migration_16():
    migration_template("17", do_migration_16)


def migration_15():
    migration_template("16", do_migration_15)


def migration_14():
    migration_template("15", do_migration_14)


def migration_13():
    migration_template("14", do_migration_13)


def migration_12():
    migration_template("13", do_migration_12)


def migration_11():
    migration_template("12", do_migration_11)


def migration_10():
    migration_template("11", do_migration_10)


def migration_9():
    migration_template("10", do_migration_9)


def migration_8():
    migration_template("9", do_migration_8)


def migration_7():
    migration_template("8", do_migration_7)


def migration_6():
    migration_template("7", do_migration_6)


def migration_5():
    migration_template("6", do_migration_5)


def migration_4():
    migration_template("5", do_migration_4)


def migration_3():
    migration_template("4", do_migration_3)


def migration_2():
    migration_template("3", do_migration_2)


def migration_1():
    migration_template("2", do_migration_1)


def migration_0():
    msgproc.log("Creating db version 1 ...")
    __store_db_version("1")
    msgproc.log("Created db version 1.")


def migration_template(new_version: str, migration_function: Callable):
    msgproc.log(f"Creating db version {new_version} ...")
    migration_function()
    __store_db_version(new_version)
    msgproc.log(f"Updated db to version {new_version}.")


class Migration:

    def __init__(self, migration_name: str, apply_on: str, migration_function: Callable[[], Any]):
        self._migration_name: str = migration_name
        self._apply_on: str = apply_on
        self._migration_function: Callable[[], Any] = migration_function

    @property
    def migration_name(self) -> str:
        return self._migration_name

    @property
    def apply_on(self) -> int:
        return self._apply_on

    @property
    def migration_function(self) -> Callable[[], Any]:
        return self._migration_function


def __create_migration(applies_on: int, migration_name: str, migration_function: Callable[[], None]):
    return Migration(
            migration_name=migration_name,
            apply_on=str(applies_on),
            migration_function=lambda: migration_template(str(applies_on + 1), migration_function))


def __init():
    __prepare_table_db_version()
    migrations: list[Migration] = [
        Migration(
            migration_name="Initial Creation",
            apply_on=None,
            migration_function=migration_0),
        Migration(
            migration_name=f"Create new table {TableName.ALBUM_METADATA_V1.value}",
            apply_on="1",
            migration_function=migration_1),
        Migration(
            migration_name=f"Create new table {KeyValueTableName.TABLE_NAME_V1.table_name}",
            apply_on="2",
            migration_function=migration_2),
        Migration(
            migration_name=f"Create new table {TableName.ARTIST_METADATA_V1.value}",
            apply_on="3",
            migration_function=migration_3),
        Migration(
            migration_name=f"Altering {TableName.ARTIST_METADATA_V1.value}, adding artist musicbrainz id",
            apply_on="4",
            migration_function=migration_4),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding album musicbrainz id",
            apply_on="5",
            migration_function=migration_5),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding album artist id",
            apply_on="6",
            migration_function=migration_6),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding artist album count",
            apply_on="7",
            migration_function=migration_7),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding artist cover art",
            apply_on="8",
            migration_function=migration_8),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding album path",
            apply_on="9",
            migration_function=migration_9),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding album media type",
            apply_on="10",
            migration_function=migration_10),
        Migration(
            migration_name=f"Creating new table {TableName.ARTIST_ROLE_V1.value}",
            apply_on="11",
            migration_function=migration_11),
        Migration(
            migration_name=f"Altering {TableName.ARTIST_METADATA_V1.value}, adding {ColumnName.ARTIST_SORT_NAME.value}",
            apply_on="12",
            migration_function=migration_12),
        Migration(
            migration_name=f"Altering {TableName.ARTIST_METADATA_V1.value} and {TableName.ALBUM_METADATA_V1.value}, "
                           f"adding indexes on {ColumnName.UPDATED_TIMESTAMP.value}",
            apply_on="13",
            migration_function=migration_13),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_ARTIST.value}",
            apply_on="14",
            migration_function=migration_14),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_COVER_ART.value}",
            apply_on="15",
            migration_function=migration_15),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_NAME.value}",
            apply_on="16",
            migration_function=migration_16),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_SONG_COUNT.value}",
            apply_on="17",
            migration_function=migration_17),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_DURATION.value}",
            apply_on="18",
            migration_function=migration_18),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_CREATED.value}",
            apply_on="19",
            migration_function=migration_19),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_YEAR.value}",
            apply_on="20",
            migration_function=migration_20),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_GENRE.value}",
            apply_on="21",
            migration_function=migration_21),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_USER_RATING.value}",
            apply_on="22",
            migration_function=migration_22),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_DISPLAY_ARTIST.value}",
            apply_on="23",
            migration_function=migration_23),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.EXPLICIT_STATUS.value}",
            apply_on="24",
            migration_function=migration_24),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_IS_COMPILATION.value}",
            apply_on="25",
            migration_function=lambda: migration_template("26", do_migration_25)),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_PLAY_COUNT.value}",
            apply_on="26",
            migration_function=lambda: migration_template("27", do_migration_26)),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_PLAYED.value}",
            apply_on="27",
            migration_function=lambda: migration_template("28", do_migration_27)),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_SORT_NAME.value}",
            apply_on="28",
            migration_function=lambda: migration_template("29", do_migration_28)),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_VERSION.value}",
            apply_on="29",
            migration_function=lambda: migration_template("30", do_migration_29)),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding Original Release Date and Release date columns",
            apply_on="30",
            migration_function=lambda: migration_template("31", do_migration_30)),
        __create_migration(
            applies_on=31,
            migration_name=f"Creating new table {TableName.ALBUM_ARTIST_V1.value}",
            migration_function=do_migration_31),
        __create_migration(
            applies_on=32,
            migration_name=f"Creating new table {TableName.ALBUM_DISC_V1.value}",
            migration_function=do_migration_32),
        __create_migration(
            applies_on=33,
            migration_name=f"Creating indexes on {TableName.ALBUM_ARTIST_V1.value} and {TableName.ALBUM_DISC_V1.value}",
            migration_function=do_migration_33),
        __create_migration(
            applies_on=34,
            migration_name=(f"Adding {ColumnName.CREATED_TIMESTAMP.value} on "
                            f"{TableName.ALBUM_ARTIST_V1.value} and {TableName.ALBUM_DISC_V1.value}"),
            migration_function=do_migration_34),
        __create_migration(
            applies_on=35,
            migration_name=f"Creating new table {TableName.ALBUM_GENRE_V1.value}",
            migration_function=do_migration_35),
        __create_migration(
            applies_on=36,
            migration_name=f"Creating new table {TableName.ALBUM_RECORD_LABEL_V1.value}",
            migration_function=do_migration_36),
        __create_migration(
            applies_on=37,
            migration_name=f"Altering {TableName.ALBUM_METADATA_V1.value}, adding {ColumnName.ALBUM_TRACK_QUALITY_SUMMARY.value}",
            migration_function=do_migration_37),
        __create_migration(
            applies_on=38,
            migration_name=f"Creating new table {TableName.ALBUM_MOOD_V1.value}",
            migration_function=do_migration_38),
        __create_migration(
            applies_on=39,
            migration_name=f"Creating new table {TableName.ALBUM_RELEASE_TYPE_V1.value}",
            migration_function=do_migration_39),
        __create_migration(
            applies_on=40,
            migration_name=f"Creating new table {TableName.SONG_METADATA_V1.value}",
            migration_function=do_migration_40),
        __create_migration(
            applies_on=41,
            migration_name=(f"Altering {TableName.SONG_METADATA_V1.value}, "
                            f"adding {ColumnName.SONG_DISPLAY_COMPOSER.value} and "
                            f"{ColumnName.SONG_SORT_NAME.value}"),
            migration_function=do_migration_41),
        __create_migration(
            applies_on=42,
            migration_name=f"Creating new table {DeletedTableName.ALBUM_COVER_ART_BY_ARTIST_V1.value}",
            migration_function=do_migration_42),
        __create_migration(
            applies_on=43,
            migration_name=(f"Creating index for {ColumnName.ALBUM_COVER_ART.value} on "
                            f"{DeletedTableName.ALBUM_COVER_ART_BY_ARTIST_V1.value}"),
            migration_function=do_migration_43),
        __create_migration(
            applies_on=44,
            migration_name=f"Creating index for {ColumnName.ALBUM_COVER_ART.value} on {TableName.ALBUM_METADATA_V1.value}",
            migration_function=do_migration_44),
        __create_migration(
            applies_on=45,
            migration_name=(f"Creating index for {ArtistMetadataModel.ARTIST_COVER_ART.column_name.value} "
                            f"on {TableName.ARTIST_METADATA_V1.value}"),
            migration_function=do_migration_45),
        __create_migration(
            applies_on=46,
            migration_name=f"Creating new table {TableName.SONG_ALBUM_ARTIST_V1.value}",
            migration_function=do_migration_46),
        __create_migration(
            applies_on=47,
            migration_name=f"Creating new table {TableName.SONG_ARTIST_V1.value}",
            migration_function=do_migration_47),
        __create_migration(
            applies_on=48,
            migration_name=(f"Altering table {TableName.SONG_ALBUM_ARTIST_V1.value} "
                            f"adding {SongAlbumArtistMetaModel.SONG_ALBUM_ID.column_name.value}"),
            migration_function=do_migration_48),
        __create_migration(
            applies_on=49,
            migration_name=(f"Altering table {TableName.SONG_ARTIST_V1.value} "
                            f"adding {SongArtistMetaModel.SONG_ALBUM_ID.column_name.value}"),
            migration_function=do_migration_49),
        __create_migration(
            applies_on=50,
            migration_name=(f"Altering table {TableName.SONG_METADATA_V1.value} "
                            f"adding index for {SongMetadataModel.SONG_COVER_ART.column_name.value}"),
            migration_function=do_migration_50),
        __create_migration(
            applies_on=51,
            migration_name=f"Creating new table {TableName.SONG_CONTRIBUTOR_V1.value}",
            migration_function=do_migration_51),
        __create_migration(
            applies_on=52,
            migration_name=(f"Creating index for {AlbumMetadataModel.ALBUM_ARTIST_ID.column_name.value} "
                            f"on {TableName.ALBUM_METADATA_V1.value}"),
            migration_function=do_migration_52),
        __create_migration(
            applies_on=53,
            migration_name=f"Deleting table [{DeletedTableName.ALBUM_COVER_ART_BY_ARTIST_V1.value}]",
            migration_function=do_migration_53),
        __create_migration(
            applies_on=54,
            migration_name=(f"Altering table {TableName.SONG_METADATA_V1.value} "
                            f"adding {SongMetadataModel.SONG_LOSSLESS_STATUS.column_name.value}"),
            migration_function=do_migration_54),
        __create_migration(
            applies_on=55,
            migration_name=f"Creating new table {TableName.ALBUM_PROPERTY_V1.value}",
            migration_function=do_migration_55),
        __create_migration(
            applies_on=56,
            migration_name=(f"Creating index for {AlbumPropertyMetaModel.ALBUM_ID.column_name.value} and "
                            f"{AlbumPropertyMetaModel.ALBUM_PROPERTY_KEY.column_name.value} "
                            f"on {TableName.ALBUM_PROPERTY_V1.value}"),
            migration_function=do_migration_56),
        __create_migration(
            applies_on=57,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_AVERAGE_BITRATE.column_name.value}"),
            migration_function=do_migration_57),
        __create_migration(
            applies_on=58,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_LOSSLESS_STATUS.column_name.value}"),
            migration_function=do_migration_58),
        __create_migration(
            applies_on=59,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_ORIGINAL_RELEASE_DATE_STR.column_name.value}"),
            migration_function=do_migration_59),
        __create_migration(
            applies_on=60,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_RELEASE_DATE_STR.column_name.value}"),
            migration_function=do_migration_60),
        __create_migration(
            applies_on=61,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_GENRE_LIST.column_name.value}"),
            migration_function=do_migration_61),
        __create_migration(
            applies_on=62,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_MOOD_LIST.column_name.value}"),
            migration_function=do_migration_62),
        __create_migration(
            applies_on=63,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_RECORD_LABEL_LIST.column_name.value}"),
            migration_function=do_migration_63),
        __create_migration(
            applies_on=64,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_RELEASE_TYPE_LIST.column_name.value}"),
            migration_function=do_migration_64),
        __create_migration(
            applies_on=65,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_DISC_COUNT.column_name.value}"),
            migration_function=do_migration_65),
        __create_migration(
            applies_on=66,
            migration_name=(f"Altering table {TableName.ALBUM_METADATA_V1.value} "
                            f"adding {AlbumMetadataModel.ALBUM_MEDIA_TYPE.column_name.value}"),
            migration_function=do_migration_66)]
    current_migration: Migration
    migration_counter: int = 0
    for current_migration in migrations:
        db_version: str = get_db_version()
        msgproc.log(f"Current db version is [{db_version}] -> "
                    f"Examining migration [{current_migration.migration_name}] "
                    f"index [{migration_counter}] ...")
        if not db_version or db_version == current_migration.apply_on:
            msgproc.log(f"Migration [{current_migration.migration_name}] "
                        f"is executing on current db version [{db_version}] ...")
            current_migration.migration_function()
            msgproc.log(f"Migration [{current_migration.migration_name}] executed.")
        else:
            msgproc.log(f"Migration [{current_migration.migration_name}] skipped.")
        migration_counter += 1
    migrated_db_version: str = get_db_version()
    msgproc.log(f"Current db version is [{migrated_db_version}]")


__init()
