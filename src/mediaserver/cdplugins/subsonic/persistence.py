# Copyright (C) 2023,2024,2025 Giovanni Fulco
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

from typing import Callable

# from common code
import upmplgutils
from keyvaluecaching import KeyValueItem
from keyvaluecaching import KeyValueTableName
from keyvaluecaching import build_create_v1_sql as build_create_cache_v1_sql
from keyvaluecaching import get_key_value_item
from keyvaluecaching import put_key_value_item
from keyvaluecaching import load_kv_item_v1
from keyvaluecaching import insert_kv_item_v1
from keyvaluecaching import update_kv_item_v1
from keyvaluecaching import delete_kv_item_v1
import sqlhelper

import constants
import config

from enum import Enum

from msgproc_provider import msgproc


class MaxLength(Enum):
    ALBUM_PATH = 65535


class TableName(Enum):
    ALBUM_METADATA = "album_metadata_v1"
    ARTIST_METADATA = "artist_metadata_v1"
    DB_VERSION = "db_version"


class ColumnName(Enum):
    CREATED_TIMESTAMP = "created_timestamp"
    UPDATED_TIMESTAMP = "updated_timestamp"
    ARTIST_ID = "artist_id"
    ARTIST_NAME = "artist_name"
    ARTIST_MB_ID = "artist_musicbrainz_id"
    ARTIST_ALBUM_COUNT = "artist_album_count"
    ARTIST_COVER_ART = "artist_cover_art"
    ALBUM_ID = "album_id"
    QUALITY_BADGE = "quality_badge"
    ALBUM_MB_ID = "album_musicbrainz_id"
    ARTIST_MEDIA_TYPE = "artist_media_type"
    ALBUM_ARTIST_ID = "album_artist_id"
    ALBUM_PATH = "album_path"


class AlbumMetadata:

    def __init__(
            self,
            album_id: str,
            quality_badge: str = None,
            album_musicbrainz_id: str = None,
            album_artist_id: str = None,
            album_path: str = None,
            created_timestamp: datetime.datetime = None,
            updated_timestamp: datetime.datetime = None):
        self.__album_id: str = album_id
        self.__quality_badge: str = quality_badge
        self.__album_musicbrainz_id: str = album_musicbrainz_id
        self.__album_artist_id: str = album_artist_id
        self.__album_path: str = album_path
        self.__created_timestamp: datetime.datetime = (created_timestamp
                                                       if created_timestamp
                                                       else datetime.datetime.now())
        self.__updated_timestamp: datetime.datetime = (updated_timestamp
                                                       if updated_timestamp
                                                       else self.created_timestamp)

    @property
    def album_id(self) -> str:
        return self.__album_id

    @property
    def quality_badge(self) -> str:
        return self.__quality_badge

    @property
    def album_musicbrainz_id(self) -> str:
        return self.__album_musicbrainz_id

    @property
    def album_artist_id(self) -> str:
        return self.__album_artist_id

    @property
    def album_path(self) -> str:
        return self.__album_path

    @property
    def created_timestamp(self) -> datetime.datetime:
        return self.__created_timestamp

    @property
    def updated_timestamp(self) -> datetime.datetime:
        return self.__updated_timestamp

    def update(
            self,
            quality_badge: str = None,
            album_musicbrainz_id: str = None,
            album_artist_id: str = None,
            album_path: str = None):
        any_update: bool = False
        if quality_badge and len(quality_badge) > 0:
            self.__quality_badge = quality_badge
            any_update = True
        if album_musicbrainz_id and len(album_musicbrainz_id) > 0:
            self.__album_musicbrainz_id = album_musicbrainz_id
            any_update = True
        if album_artist_id and len(album_artist_id) > 0:
            self.__album_artist_id = album_artist_id
            any_update = True
        if album_path and len(album_path) > 0:
            if len(album_path) > MaxLength.ALBUM_PATH.value:
                # protect from exceptions
                album_path = ""
            self.__album_path = album_path
            any_update = True
        if any_update:
            self.__updated_timestamp = datetime.datetime.now()

    def __repr__(self):
        return (f"Album Id [{self.album_id}] "
                f"QBadge [{self.quality_badge}] "
                f"Mb Id [{self.album_musicbrainz_id}] "
                f"Artist Id [{self.album_artist_id}] "
                f"Path [{self.album_path}]")


class ArtistMetadata:

    def __init__(
            self,
            artist_id: str,
            artist_name: str = None,
            artist_musicbrainz_id: str = None,
            artist_album_count: int = None,
            artist_cover_art: str = None,
            artist_media_type: str = None,
            created_timestamp: datetime.datetime = None,
            updated_timestamp: datetime.datetime = None):
        self.__artist_id: str = artist_id
        self.__artist_name: str = artist_name
        self.__artist_musicbrainz_id: str = artist_musicbrainz_id
        self.__artist_album_count: int = artist_album_count
        self.__artist_cover_art: str = artist_cover_art
        self.__artist_media_type: str = artist_media_type
        self.__created_timestamp: datetime.datetime = (created_timestamp
                                                       if created_timestamp
                                                       else datetime.datetime.now())
        self.__updated_timestamp: datetime.datetime = (updated_timestamp
                                                       if updated_timestamp
                                                       else self.created_timestamp)

    @property
    def artist_id(self) -> str:
        return self.__artist_id

    @property
    def artist_name(self) -> str:
        return self.__artist_name

    @property
    def artist_musicbrainz_id(self) -> str:
        return self.__artist_musicbrainz_id

    @property
    def artist_album_count(self) -> int:
        return self.__artist_album_count

    @property
    def artist_cover_art(self) -> str:
        return self.__artist_cover_art

    @property
    def artist_media_type(self) -> str:
        return self.__artist_media_type

    @property
    def created_timestamp(self) -> datetime.datetime:
        return self.__created_timestamp

    @property
    def updated_timestamp(self) -> datetime.datetime:
        return self.__updated_timestamp

    def update(
            self,
            artist_name: str,
            artist_musicbrainz_id: str,
            artist_album_count: int = None,
            artist_cover_art: str = None,
            artist_media_type: str = None):
        any_update: bool = False
        if artist_name and len(artist_name) > 0:
            self.__artist_name = artist_name
            any_update = True
        if artist_musicbrainz_id and len(artist_musicbrainz_id) > 0:
            self.__artist_musicbrainz_id = artist_musicbrainz_id
            any_update = True
        if artist_album_count:
            self.__artist_album_count = artist_album_count
            any_update = True
        if artist_cover_art:
            self.__artist_cover_art = artist_cover_art
            any_update = True
        if artist_media_type:
            self.__artist_media_type = artist_media_type
            any_update = True
        if any_update:
            self.__updated_timestamp = datetime.datetime.now()


__album_metadata_cache: dict[str, AlbumMetadata] = {}
__artist_metadata_cache: dict[str, ArtistMetadata] = {}
__key_value_cache: dict[str, dict[str, KeyValueItem]] = {}


__sql_create_table_album_metadata_v1: str = f"""
        CREATE TABLE {TableName.ALBUM_METADATA.value}(
        {ColumnName.ALBUM_ID.value} VARCHAR(255) PRIMARY KEY,
        {ColumnName.QUALITY_BADGE.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP,
        {ColumnName.UPDATED_TIMESTAMP.value} TIMESTAMP)
"""


__sql_create_table_artist_metadata_v1: str = f"""
        CREATE TABLE {TableName.ARTIST_METADATA.value}(
        {ColumnName.ARTIST_ID.value} VARCHAR(255) PRIMARY KEY,
        {ColumnName.ARTIST_NAME.value} VARCHAR(255),
        {ColumnName.CREATED_TIMESTAMP.value} TIMESTAMP,
        {ColumnName.UPDATED_TIMESTAMP.value} TIMESTAMP)
"""


__sql_alter_table_artist_metadata_v1_add_artist_media_type: str = f"""
        ALTER TABLE {TableName.ARTIST_METADATA.value}
        ADD COLUMN {ColumnName.ARTIST_MEDIA_TYPE.value} VARCHAR(255)
"""


__sql_alter_table_artist_metadata_v1_add_artist_cover_art: str = f"""
        ALTER TABLE {TableName.ARTIST_METADATA.value}
        ADD COLUMN {ColumnName.ARTIST_COVER_ART.value} VARCHAR(255)
"""


__sql_alter_table_artist_metadata_v1_add_artist_album_count: str = f"""
        ALTER TABLE {TableName.ARTIST_METADATA.value}
        ADD COLUMN {ColumnName.ARTIST_ALBUM_COUNT.value} INTEGER
"""


__sql_alter_table_artist_metadata_v1_add_artist_musicbrainz_id: str = f"""
        ALTER TABLE {TableName.ARTIST_METADATA.value}
        ADD COLUMN {ColumnName.ARTIST_MB_ID.value} VARCHAR(255)
"""


__sql_alter_table_album_metadata_v1_add_album_musicbrainz_id: str = f"""
        ALTER TABLE {TableName.ALBUM_METADATA.value}
        ADD COLUMN {ColumnName.ALBUM_MB_ID.value} VARCHAR(255)
"""


__sql_alter_table_album_metadata_v1_add_album_artist_id: str = f"""
        ALTER TABLE {TableName.ALBUM_METADATA.value}
        ADD COLUMN {ColumnName.ALBUM_ARTIST_ID.value} VARCHAR(255)
"""


__sql_alter_table_album_metadata_v1_add_album_path: str = f"""
        ALTER TABLE {TableName.ALBUM_METADATA.value}
        ADD COLUMN {ColumnName.ALBUM_PATH.value} VARCHAR({MaxLength.ALBUM_PATH.value})
"""


def get_album_metadata(album_id: str) -> AlbumMetadata:
    start: float = time.time()
    result: AlbumMetadata = __get_album_metadata(album_id=album_id)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"get_album_metadata for album_id [{album_id}] executed in [{elapsed:.3f}]")
    return result


def __get_album_metadata(album_id: str) -> AlbumMetadata:
    # try in cache first, otherwise load.
    album_metadata: AlbumMetadata = (__album_metadata_cache[album_id]
                                     if album_id in __album_metadata_cache
                                     else None)
    if not album_metadata:
        album_metadata = _load_album_metadata(album_id=album_id)
        # add to cache if correctly loaded from db
        if album_metadata:
            __album_metadata_cache[album_id] = album_metadata
    return album_metadata


def get_artist_metadata(artist_id: str) -> ArtistMetadata:
    # try in cache first, otherwise load.
    artist_metadata: ArtistMetadata = (__artist_metadata_cache[artist_id]
                                       if artist_id in __artist_metadata_cache
                                       else None)
    if not artist_metadata:
        artist_metadata = _load_artist_metadata(artist_id=artist_id)
        # add to cache if correctly loaded from db
        if artist_metadata:
            __artist_metadata_cache[artist_id] = artist_metadata
    return artist_metadata


def get_kv_item(partition: str, key: str) -> KeyValueItem:
    return get_key_value_item(
        key_value_cache=__key_value_cache,
        partition=partition,
        key=key,
        kv_loader=_load_key_value_item)


def _load_album_metadata(album_id: str) -> AlbumMetadata:
    t = (album_id, )
    q: str = sqlhelper.create_simple_select_sql(
        table_name=TableName.ALBUM_METADATA.value,
        select_column_list=[
            ColumnName.CREATED_TIMESTAMP.value,
            ColumnName.UPDATED_TIMESTAMP.value,
            ColumnName.ALBUM_ID.value,
            ColumnName.QUALITY_BADGE.value,
            ColumnName.ALBUM_MB_ID.value,
            ColumnName.ALBUM_ARTIST_ID.value,
            ColumnName.ALBUM_PATH.value],
        where_colum_list=[
            ColumnName.ALBUM_ID.value])
    rows: list[any] = sqlite3util.get_sqlite3_selector(__connection)(
        sql=q,
        parameters=t)
    if not rows:
        return None
    if len(rows) > 1:
        raise Exception(f"Multiple {TableName.ALBUM_METADATA.value} records for [{album_id}]")
    row = rows[0]
    result: AlbumMetadata = AlbumMetadata(
        created_timestamp=row[0],
        updated_timestamp=row[1],
        album_id=row[2],
        quality_badge=row[3],
        album_musicbrainz_id=row[4],
        album_artist_id=row[5],
        album_path=row[6])
    return result


def _load_artist_metadata(artist_id: str) -> ArtistMetadata:
    t = (artist_id, )
    q: str = sqlhelper.create_simple_select_sql(
        table_name=TableName.ARTIST_METADATA.value,
        select_column_list=[
            ColumnName.CREATED_TIMESTAMP.value,
            ColumnName.UPDATED_TIMESTAMP.value,
            ColumnName.ARTIST_ID.value,
            ColumnName.ARTIST_NAME.value,
            ColumnName.ARTIST_MB_ID.value,
            ColumnName.ARTIST_ALBUM_COUNT.value,
            ColumnName.ARTIST_COVER_ART.value,
            ColumnName.ARTIST_MEDIA_TYPE.value
        ],
        where_colum_list=[
            ColumnName.ARTIST_ID.value
        ])
    rows: list[any] = sqlite3util.get_sqlite3_selector(__connection)(
        sql=q,
        parameters=t)
    if not rows:
        return None
    if len(rows) > 1:
        raise Exception(f"Multiple {TableName.ARTIST_METADATA.value} records for [{artist_id}]")
    row = rows[0]
    result: ArtistMetadata = ArtistMetadata(
        created_timestamp=row[0],
        updated_timestamp=row[1],
        album_id=row[2],
        artist_name=row[3],
        artist_musicbrainz_id=row[4],
        artist_album_count=row[5],
        artist_cover_art=row[6],
        artist_media_type=row[7])
    return result


def _update_kv_item(
        partition: str,
        key: str,
        value: str,
        update_timestamp: datetime.datetime) -> None:
    update_kv_item_v1(
        sql_executor=sqlite3util.get_sqlite3_executor(__connection),
        partition=partition,
        key=key,
        value=value,
        update_timestamp=update_timestamp)


def _load_key_value_item(partition: str, key: str) -> KeyValueItem:
    return load_kv_item_v1(
        sql_selector=sqlite3util.get_sqlite3_selector(__connection),
        partition=partition,
        key=key)


def delete_album_metadata(album_id: str):
    # remove from cache, then actually delete from db
    if album_id in __album_metadata_cache:
        del __album_metadata_cache[album_id]
    _delete_album_metadata_from_db(album_id=album_id)


def delete_artist_metadata(artist_id: str):
    # remove from cache, then actually delete from db
    if artist_id in __artist_metadata_cache:
        del __artist_metadata_cache[artist_id]
    _delete_artist_metadata_from_db(artist_id=artist_id)


def _delete_album_metadata_from_db(album_id: str):
    q: str = sqlhelper.create_simple_delete_sql(
        table_name=TableName.ALBUM_METADATA.value,
        where_colum_list=[ColumnName.ALBUM_ID.value])
    t = (album_id, )
    sqlite3util.get_sqlite3_executor(__connection)(
        sql=q,
        data=t,
        do_commit=True)


def _delete_artist_metadata_from_db(artist_id: str):
    q: str = sqlhelper.create_simple_delete_sql(
        table_name=TableName.ARTIST_METADATA.value,
        where_colum_list=[ColumnName.ARTIST_ID.value])
    t = (artist_id, )
    sqlite3util.get_sqlite3_executor(__connection)(
        sql=q,
        data=t,
        do_commit=True)


def _delete_kv_item_from_db(partition: str, key: str):
    delete_kv_item_v1(
        sql_executor=sqlite3util.get_sqlite3_executor(__connection),
        partition=partition,
        key=key)


def save_album_metadata(album_metadata: AlbumMetadata) -> AlbumMetadata:
    start: float = time.time()
    result: ArtistMetadata = __save_album_metadata(album_metadata=album_metadata)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"save_album_metadata for album_id [{album_metadata.album_id}] executed in [{elapsed:.3f}]")
    return result


def __save_album_metadata(album_metadata: AlbumMetadata) -> AlbumMetadata:
    existing_metadata: AlbumMetadata = get_album_metadata(album_id=album_metadata.album_id)
    if existing_metadata:
        # update
        # might change if we add more fields to AlbumMetadata
        latest_quality_badge: str = (album_metadata.quality_badge
                                     if album_metadata.quality_badge
                                     else existing_metadata.quality_badge)
        latest_mb_id: str = (album_metadata.album_musicbrainz_id
                             if album_metadata.album_musicbrainz_id
                             else existing_metadata.album_musicbrainz_id)
        latest_artist_id: str = (album_metadata.album_artist_id
                                 if album_metadata.album_artist_id
                                 else existing_metadata.album_artist_id)
        latest_album_path: str = (album_metadata.album_path
                                  if (album_metadata.album_path and len(album_metadata.album_path) > 0)
                                  else existing_metadata.album_path)
        if latest_album_path and len(latest_album_path) > MaxLength.ALBUM_PATH.value:
            msgproc.log(f"save_album_metadata album_path too long for album [{album_metadata.album_id}], data removed")
            latest_album_path = ""
        now: datetime.datetime = datetime.datetime.now()
        update_values = (
            latest_quality_badge,
            latest_mb_id,
            latest_artist_id,
            latest_album_path,
            now,
            album_metadata.album_id)
        update_sql: str = sqlhelper.create_simple_update_sql(
                table_name=TableName.ALBUM_METADATA.value,
                set_column_list=[
                    ColumnName.QUALITY_BADGE.value,
                    ColumnName.ALBUM_MB_ID.value,
                    ColumnName.ALBUM_ARTIST_ID.value,
                    ColumnName.ALBUM_PATH.value,
                    ColumnName.UPDATED_TIMESTAMP.value],
                where_colum_list=[ColumnName.ALBUM_ID.value])
        __execute_update(update_sql, update_values)
        # update cache
        existing_metadata.update(
            quality_badge=latest_quality_badge,
            album_musicbrainz_id=latest_mb_id,
            album_artist_id=latest_artist_id,
            album_path=latest_album_path)
        return existing_metadata
    else:
        # insert
        __insert_album_metadata(album_metadata=album_metadata)
        __album_metadata_cache[album_metadata.album_id] = album_metadata
        return album_metadata


def save_artist_metadata(artist_metadata: ArtistMetadata) -> ArtistMetadata:
    start: float = time.time()
    result: ArtistMetadata = __save_artist_metadata(artist_metadata=artist_metadata)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"save_artist_metadata for artist_id [{artist_metadata.artist_id}] executed in [{elapsed:.3f}]")
    return result


def __save_artist_metadata(artist_metadata: ArtistMetadata) -> ArtistMetadata:
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"save_artist_metadata for artist_id: {artist_metadata.artist_id} "
                    f"name [{artist_metadata.artist_name}] "
                    f"musicbrainz_id [{artist_metadata.artist_musicbrainz_id}]")
    existing_metadata: ArtistMetadata = get_artist_metadata(artist_id=artist_metadata.artist_id)
    if existing_metadata:
        # update
        # might change if we add more fields to AlbumMetadata
        now: datetime.datetime = datetime.datetime.now()
        # use values from incoming data if valid
        update_values = (
            (artist_metadata.artist_name
                if artist_metadata.artist_name
                else existing_metadata.artist_name),
            (artist_metadata.artist_musicbrainz_id
                if artist_metadata.artist_musicbrainz_id
                else existing_metadata.artist_musicbrainz_id),
            (artist_metadata.artist_album_count
                if artist_metadata.artist_album_count
                else existing_metadata.artist_album_count),
            (artist_metadata.artist_cover_art
                if artist_metadata.artist_cover_art
                else existing_metadata.artist_cover_art),
            (artist_metadata.artist_media_type
                if artist_metadata.artist_media_type
                else existing_metadata.artist_media_type),
            now,
            artist_metadata.artist_id)
        update_sql: str = sqlhelper.create_simple_update_sql(
            table_name=TableName.ARTIST_METADATA.value,
            set_column_list=[
                ColumnName.ARTIST_NAME.value,
                ColumnName.ARTIST_MB_ID.value,
                ColumnName.ARTIST_ALBUM_COUNT.value,
                ColumnName.ARTIST_COVER_ART.value,
                ColumnName.ARTIST_MEDIA_TYPE.value,
                ColumnName.UPDATED_TIMESTAMP.value],
            where_colum_list=[
                ColumnName.ARTIST_ID.value])
        __execute_update(update_sql, update_values)
        # update cache
        existing_metadata.update(
            artist_name=artist_metadata.artist_name,
            artist_musicbrainz_id=artist_metadata.artist_musicbrainz_id,
            artist_album_count=artist_metadata.artist_album_count,
            artist_cover_art=artist_metadata.artist_cover_art,
            artist_media_type=artist_metadata.artist_media_type)
        return existing_metadata
    else:
        # insert
        __insert_artist_metadata(artist_metadata=artist_metadata)
        __artist_metadata_cache[artist_metadata.artist_id] = artist_metadata
        return artist_metadata


def save_kv_item(key_value_item: KeyValueItem):
    put_key_value_item(
        key_value_cache=__key_value_cache,
        key_value_item=key_value_item,
        updater=_update_kv_item,
        creator=_insert_key_value_item,
        loader=_load_key_value_item)


def __insert_album_metadata(album_metadata: AlbumMetadata):
    now: datetime.datetime = datetime.datetime.now()
    insert_values = (
        album_metadata.album_id,
        album_metadata.quality_badge,
        album_metadata.album_artist_id,
        album_metadata.album_path,
        now,
        now)
    insert_sql: str = sqlhelper.create_simple_insert_sql(
        table_name=TableName.ALBUM_METADATA.value,
        column_list=[
            ColumnName.ALBUM_ID.value,
            ColumnName.QUALITY_BADGE.value,
            ColumnName.ALBUM_ARTIST_ID.value,
            ColumnName.ALBUM_PATH.value,
            ColumnName.CREATED_TIMESTAMP.value,
            ColumnName.UPDATED_TIMESTAMP.value])
    __execute_update(insert_sql, insert_values)


def __insert_artist_metadata(artist_metadata: ArtistMetadata):
    now: datetime.datetime = datetime.datetime.now()
    insert_values = (
        artist_metadata.artist_id,
        artist_metadata.artist_name,
        artist_metadata.artist_musicbrainz_id,
        artist_metadata.artist_album_count,
        artist_metadata.artist_cover_art,
        artist_metadata.artist_media_type,
        now,
        now)
    insert_sql: str = sqlhelper.create_simple_insert_sql(
        table_name=TableName.ARTIST_METADATA.value,
        column_list=[
            ColumnName.ARTIST_ID.value,
            ColumnName.ARTIST_NAME.value,
            ColumnName.ARTIST_MB_ID.value,
            ColumnName.ARTIST_ALBUM_COUNT.value,
            ColumnName.ARTIST_COVER_ART.value,
            ColumnName.ARTIST_MEDIA_TYPE.value,
            ColumnName.CREATED_TIMESTAMP.value,
            ColumnName.UPDATED_TIMESTAMP.value])
    __execute_update(insert_sql, insert_values)


def _insert_key_value_item(
        key_value: KeyValueItem,
        creation_timestamp: datetime.datetime) -> None:
    insert_kv_item_v1(
        sql_executor=sqlite3util.get_sqlite3_executor(__connection),
        key_value=key_value,
        creation_timestamp=creation_timestamp)


def preload_metadata(
        table_name: str,
        field_list: list[str],
        row_converter: Callable[[list[any]], any],
        cache_writer: Callable[[any, any], any]):
    sql: str = sqlhelper.create_simple_select_sql(
        table_name=table_name,
        select_column_list=field_list)
    rows: list[any] = sqlite3util.get_sqlite3_selector(__connection)(
        sql=sql,
        parameters=())
    for row in rows if rows else []:
        obj: any = row_converter(row)
        cache_writer(obj)
    msgproc.log(f"Loaded [{len(rows)}] records from [{table_name}].")


def __update_album_cache(album_metadata: AlbumMetadata):
    __album_metadata_cache[album_metadata.album_id] = album_metadata


def __update_artist_cache(artist_metadata: ArtistMetadata):
    __artist_metadata_cache[artist_metadata.artist_id] = artist_metadata


def __preload_album_metadata():
    return preload_metadata(
        table_name=TableName.ALBUM_METADATA.value,
        field_list=[
            ColumnName.CREATED_TIMESTAMP.value,
            ColumnName.UPDATED_TIMESTAMP.value,
            ColumnName.ALBUM_ID.value,
            ColumnName.QUALITY_BADGE.value,
            ColumnName.ALBUM_MB_ID.value,
            ColumnName.ALBUM_ARTIST_ID.value,
            ColumnName.ALBUM_PATH.value],
        row_converter=lambda x: AlbumMetadata(
            created_timestamp=x[0],
            updated_timestamp=x[1],
            album_id=x[2],
            quality_badge=x[3],
            album_musicbrainz_id=x[4],
            album_artist_id=x[5],
            album_path=x[6]),
        cache_writer=lambda x: __update_album_cache(x))


def __preload_artist_metadata():
    return preload_metadata(
        table_name=TableName.ARTIST_METADATA.value,
        field_list=[
            ColumnName.CREATED_TIMESTAMP.value,
            ColumnName.UPDATED_TIMESTAMP.value,
            ColumnName.ARTIST_ID.value,
            ColumnName.ARTIST_NAME.value,
            ColumnName.ARTIST_MB_ID.value,
            ColumnName.ARTIST_ALBUM_COUNT.value,
            ColumnName.ARTIST_COVER_ART.value,
            ColumnName.ARTIST_MEDIA_TYPE.value
            ],
        row_converter=lambda x: ArtistMetadata(
            artist_id=x[2],
            artist_name=x[3],
            artist_musicbrainz_id=x[4],
            artist_album_count=x[5],
            artist_cover_art=x[6],
            artist_media_type=x[7],
            created_timestamp=x[0],
            updated_timestamp=x[1]),
        cache_writer=lambda x: __update_artist_cache(x))


def __preload():
    __preload_album_metadata()
    __preload_artist_metadata()


def __execute_update(
        sql: str,
        data: tuple,
        cursor=None,
        do_commit: bool = True):
    sqlhelper.neutral_execute_update(
        sql_executor=sqlite3util.get_sqlite3_executor(__connection),
        sql=sql,
        data=data,
        do_commit=do_commit)


def __do_create_table(table_name: str, sql: str):
    msgproc.log(f"Preparing table {table_name} ...")
    cursor_obj = __connection.cursor()
    cursor_obj.execute(sql)
    cursor_obj.close()
    msgproc.log(f"Prepared table {table_name}.")


def __get_db_filename() -> str:
    return f"{constants.PluginConstant.PLUGIN_NAME.value}.db"


def __get_db_full_path() -> str:
    return os.path.join(
        upmplgutils.getcachedir(constants.PluginConstant.PLUGIN_NAME.value),
        __get_db_filename())


def __get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(
        __get_db_full_path(),
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    return connection


def __prepare_table_db_version():
    # Creating table
    create_table: str = f"""
        CREATE TABLE IF NOT EXISTS {TableName.DB_VERSION.value}(
        version VARCHAR(32) PRIMARY KEY)
    """
    cursor_obj = __connection.cursor()
    cursor_obj.execute(create_table)
    cursor_obj.close()


def get_db_version() -> str:
    cursor = __connection.cursor()
    cursor.execute(sqlhelper.create_simple_select_sql(
        table_name=TableName.DB_VERSION.value,
        select_column_list=["version"]))
    rows = cursor.fetchall()
    cursor.close()
    if rows:
        return rows[0][0]
    return None


def __store_db_version(version: str):
    db_version: str = get_db_version()
    if not db_version:
        msgproc.log(f"Setting db version to [{version}] ...")
        insert_tuple = (version, )
        cursor = __connection.cursor()
        insert_sql: str = sqlhelper.create_simple_insert_sql(
            table_name=TableName.DB_VERSION.value,
            column_list=["version"])
        cursor.execute(insert_sql, insert_tuple)
        cursor.close()
    else:
        msgproc.log(f"Updating db version to [{version}] from [{db_version}] ...")
        update_tuple = (version, db_version)
        cursor = __connection.cursor()
        update_sql: str = sqlhelper.create_simple_update_sql(
            table_name=TableName.DB_VERSION.value,
            set_column_list=["version"],
            where_colum_list=["version"])
        cursor.execute(update_sql, update_tuple)
        cursor.close()
    __connection.commit()
    msgproc.log(f"Db version correctly set to [{version}]")


def do_migration_10():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA.value,
        sql=__sql_alter_table_artist_metadata_v1_add_artist_media_type)


def do_migration_9():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA.value,
        sql=__sql_alter_table_album_metadata_v1_add_album_path)


def do_migration_8():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA.value,
        sql=__sql_alter_table_artist_metadata_v1_add_artist_cover_art)


def do_migration_7():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA.value,
        sql=__sql_alter_table_artist_metadata_v1_add_artist_album_count)


def do_migration_6():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA.value,
        sql=__sql_alter_table_album_metadata_v1_add_album_artist_id)


def do_migration_5():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA.value,
        sql=__sql_alter_table_album_metadata_v1_add_album_musicbrainz_id)


def do_migration_4():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA.value,
        sql=__sql_alter_table_artist_metadata_v1_add_artist_musicbrainz_id)


def do_migration_3():
    __do_create_table(
        table_name=TableName.ARTIST_METADATA.value,
        sql=__sql_create_table_artist_metadata_v1)


def do_migration_2():
    __do_create_table(
        table_name=KeyValueTableName.TABLE_NAME_V1.table_name,
        sql=build_create_cache_v1_sql())


def do_migration_1():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA.value,
        sql=__sql_create_table_album_metadata_v1)


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


__connection: sqlite3.Connection = __get_connection()
__prepare_table_db_version()


class Migration:

    def __init__(self, migration_name: str, apply_on: str, migration_function: Callable[[], any]):
        self._migration_name: str = migration_name
        self._apply_on: str = apply_on
        self._migration_function: Callable[[], any] = migration_function

    @property
    def migration_name(self) -> str:
        return self._migration_name

    @property
    def apply_on(self) -> int:
        return self._apply_on

    @property
    def migration_function(self) -> Callable[[], any]:
        return self._migration_function


def __init():
    migrations: list[Migration] = [
        Migration(
            migration_name="Initial Creation",
            apply_on=None,
            migration_function=migration_0),
        Migration(
            migration_name=f"Create new table {TableName.ALBUM_METADATA.value}",
            apply_on="1",
            migration_function=migration_1),
        Migration(
            migration_name=f"Create new table {KeyValueTableName.TABLE_NAME_V1.table_name}",
            apply_on="2",
            migration_function=migration_2),
        Migration(
            migration_name=f"Create new table {TableName.ARTIST_METADATA.value}",
            apply_on="3",
            migration_function=migration_3),
        Migration(
            migration_name=f"Altering {TableName.ARTIST_METADATA.value}, adding artist musicbrainz id",
            apply_on="4",
            migration_function=migration_4),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA.value}, adding album musicbrainz id",
            apply_on="5",
            migration_function=migration_5),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA.value}, adding album artist id",
            apply_on="6",
            migration_function=migration_6),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA.value}, adding artist album count",
            apply_on="7",
            migration_function=migration_7),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA.value}, adding artist cover art",
            apply_on="8",
            migration_function=migration_8),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA.value}, adding album path",
            apply_on="9",
            migration_function=migration_9),
        Migration(
            migration_name=f"Altering {TableName.ALBUM_METADATA.value}, adding album media type",
            apply_on="10",
            migration_function=migration_10)]
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
    msgproc.log("Preloading ...")
    __preload()
    msgproc.log("Finished preloading.")


__init()
