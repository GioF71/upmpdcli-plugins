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
import datetime

from typing import Callable

import upmplgutils
import constants
import config

from enum import Enum


from msgproc_provider import msgproc


class MaxLength(Enum):
    ALBUM_PATH = 65535


class TableName(Enum):
    ALBUM_METADATA = "album_metadata_v1"
    ARTIST_METADATA = "artist_metadata_v1"
    KV_CACHE = "kv_cache_v1"


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
            created_timestamp: datetime.datetime = None,
            updated_timestamp: datetime.datetime = None):
        self.__artist_id: str = artist_id
        self.__artist_name: str = artist_name
        self.__artist_musicbrainz_id: str = artist_musicbrainz_id
        self.__artist_album_count: int = artist_album_count
        self.__artist_cover_art: str = artist_cover_art
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
            artist_cover_art: str = None):
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
        if any_update:
            self.__updated_timestamp = datetime.datetime.now()


class KeyValueItem:

    def __init__(
            self,
            partition: str,
            key: str,
            value: str,
            created_timestamp: datetime.datetime = None,
            updated_timestamp: datetime.datetime = None):
        self.__partition: str = partition
        self.__key: str = key
        self.__value: str = value
        self.__created_timestamp: datetime.datetime = (created_timestamp
                                                       if created_timestamp
                                                       else datetime.datetime.now())
        self.__updated_timestamp: datetime.datetime = (updated_timestamp
                                                       if updated_timestamp
                                                       else self.created_timestamp)

    @property
    def partition(self) -> str:
        return self.__partition

    @property
    def key(self) -> str:
        return self.__key

    @property
    def value(self) -> str:
        return self.__value

    @property
    def created_timestamp(self) -> datetime.datetime:
        return self.__created_timestamp

    @property
    def updated_timestamp(self) -> datetime.datetime:
        return self.__updated_timestamp

    def update(self, value: str):
        self.__value = value
        self.__updated_timestamp = datetime.datetime.now()


__album_metadata_cache: dict[str, AlbumMetadata] = {}
__artist_metadata_cache: dict[str, ArtistMetadata] = {}
__key_value_cache: dict[str, dict[str, KeyValueItem]] = {}

__field_name_created_timestamp: str = "created_timestamp"
__field_name_updated_timestamp: str = "updated_timestamp"

__field_name_artist_id: str = "artist_id"
__field_name_artist_name: str = "artist_name"
__field_name_artist_musicbrainz_id: str = "artist_musicbrainz_id"
__field_name_artist_album_count: str = "artist_album_count"
__field_name_artist_cover_art: str = "artist_cover_art"

__field_name_album_id: str = "album_id"
__field_name_album_quality_badge: str = "quality_badge"
__field_name_album_musicbrainz_id: str = "album_musicbrainz_id"
__field_name_album_artist_id: str = "album_artist_id"
__field_name_album_path: str = "album_path"


__field_name_kv_cache_partition: str = "partition"
__field_name_kv_cache_key: str = "key"
__field_name_kv_cache_value: str = "value"


__sql_create_table_album_metadata_v1: str = f"""
        CREATE TABLE {TableName.ALBUM_METADATA.value}(
        {__field_name_album_id} VARCHAR(255) PRIMARY KEY,
        {__field_name_album_quality_badge} VARCHAR(255),
        {__field_name_created_timestamp} TIMESTAMP,
        {__field_name_updated_timestamp} TIMESTAMP)
"""


__sql_create_table_kv_cache_v1: str = f"""
        CREATE TABLE {TableName.KV_CACHE.value}(
        {__field_name_kv_cache_partition} VARCHAR(255),
        {__field_name_kv_cache_key} VARCHAR(255),
        {__field_name_kv_cache_value}  VARCHAR(255),
        {__field_name_created_timestamp} TIMESTAMP,
        {__field_name_updated_timestamp} TIMESTAMP,
        PRIMARY KEY ({__field_name_kv_cache_partition}, {__field_name_kv_cache_key}))
"""


__sql_create_table_artist_metadata_v1: str = f"""
        CREATE TABLE {TableName.ARTIST_METADATA.value}(
        {__field_name_artist_id} VARCHAR(255) PRIMARY KEY,
        {__field_name_artist_name} VARCHAR(255),
        {__field_name_created_timestamp} TIMESTAMP,
        {__field_name_updated_timestamp} TIMESTAMP)
"""


__sql_alter_table_artist_metadata_v1_add_artist_cover_art: str = f"""
        ALTER TABLE {TableName.ARTIST_METADATA.value}
        ADD COLUMN {__field_name_artist_cover_art} VARCHAR(255)
"""


__sql_alter_table_artist_metadata_v1_add_artist_album_count: str = f"""
        ALTER TABLE {TableName.ARTIST_METADATA.value}
        ADD COLUMN {__field_name_artist_album_count} INTEGER
"""


__sql_alter_table_artist_metadata_v1_add_artist_musicbrainz_id: str = f"""
        ALTER TABLE {TableName.ARTIST_METADATA.value}
        ADD COLUMN {__field_name_artist_musicbrainz_id} VARCHAR(255)
"""


__sql_alter_table_album_metadata_v1_add_album_musicbrainz_id: str = f"""
        ALTER TABLE {TableName.ALBUM_METADATA.value}
        ADD COLUMN {__field_name_album_musicbrainz_id} VARCHAR(255)
"""


__sql_alter_table_album_metadata_v1_add_album_artist_id: str = f"""
        ALTER TABLE {TableName.ALBUM_METADATA.value}
        ADD COLUMN {__field_name_album_artist_id} VARCHAR(255)
"""


__sql_alter_table_album_metadata_v1_add_album_path: str = f"""
        ALTER TABLE {TableName.ALBUM_METADATA.value}
        ADD COLUMN {__field_name_album_path} VARCHAR({MaxLength.ALBUM_PATH.value})
"""


def get_album_metadata(album_id: str) -> AlbumMetadata:
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
    # try in cache first, otherwise load.
    partition_dict: dict[str, KeyValueItem] = __key_value_cache[partition] if partition in __key_value_cache else None
    kv_item: KeyValueItem = partition_dict[key] if partition_dict and key in partition_dict else None
    # create partition if still not cached
    if not partition_dict:
        partition_dict = {}
        __key_value_cache[partition] = partition_dict
    if not kv_item:
        kv_item = _load_kv_item(partition=partition, key=key)
        # add to cache if correctly loaded from db
        if kv_item:
            partition_dict[key] = kv_item
    return kv_item


def _load_album_metadata(album_id: str) -> AlbumMetadata:
    t = (album_id, )
    cursor = __connection.cursor()
    q: str = f"""
            SELECT
                {__field_name_created_timestamp},
                {__field_name_updated_timestamp},
                {__field_name_album_id},
                {__field_name_album_quality_badge},
                {__field_name_album_musicbrainz_id},
                {__field_name_album_artist_id},
                {__field_name_album_path}
            FROM
                {TableName.ALBUM_METADATA.value}
            WHERE {__field_name_album_id} = ?"""
    cursor.execute(q, t)
    rows = cursor.fetchall()
    cursor.close()
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
    cursor = __connection.cursor()
    q: str = f"""
            SELECT
                {__field_name_created_timestamp},
                {__field_name_updated_timestamp},
                {__field_name_artist_id},
                {__field_name_artist_name},
                {__field_name_artist_musicbrainz_id},
                {__field_name_artist_album_count},
                {__field_name_artist_cover_art}
            FROM
                {TableName.ARTIST_METADATA.value}
            WHERE {__field_name_artist_id} = ?"""
    cursor.execute(q, t)
    rows = cursor.fetchall()
    cursor.close()
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
        artist_cover_art=row[6])
    return result


def _load_kv_item(partition: str, key: str) -> KeyValueItem:
    t = (partition, key)
    cursor = __connection.cursor()
    q: str = f"""
            SELECT
                {__field_name_created_timestamp},
                {__field_name_updated_timestamp},
                {__field_name_kv_cache_value}
            FROM
                {TableName.KV_CACHE.value}
            WHERE
                {__field_name_kv_cache_partition} = ? AND
                {__field_name_kv_cache_key} = ?
            """
    cursor.execute(q, t)
    rows = cursor.fetchall()
    cursor.close()
    if not rows:
        return None
    if len(rows) > 1:
        raise Exception(f"Multiple {TableName.KV_CACHE.value} records for [{partition}] [{key}]")
    row = rows[0]
    result: KeyValueItem = KeyValueItem(
        created_timestamp=row[0],
        updated_timestamp=row[1],
        partition=partition,
        key=key,
        value=row[2])
    return result


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
    t = (album_id, )
    cursor = __connection.cursor()
    q: str = f"""
            DELETE FROM {TableName.ALBUM_METADATA.value}
            WHERE {__field_name_album_id} = ?"""
    cursor.execute(q, t)
    __connection.commit()


def _delete_artist_metadata_from_db(artist_id: str):
    t = (artist_id, )
    cursor = __connection.cursor()
    q: str = f"""
            DELETE FROM {TableName.ARTIST_METADATA.value}
            WHERE {__field_name_artist_id} = ?"""
    cursor.execute(q, t)
    __connection.commit()


def _delete_kv_item_from_db(partition: str, key: str):
    t = (partition, key)
    cursor = __connection.cursor()
    q: str = f"""
            DELETE FROM {TableName.KV_CACHE.value}
            WHERE
                {__field_name_kv_cache_partition} = ? AND
                {__field_name_kv_cache_key} = ?
            """
    cursor.execute(q, t)
    __connection.commit()


def save_album_metadata(album_metadata: AlbumMetadata):
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
        update_sql: str = f"""
            UPDATE
                {TableName.ALBUM_METADATA.value}
            SET
                {__field_name_album_quality_badge} = ?,
                {__field_name_album_musicbrainz_id} = ?,
                {__field_name_album_artist_id} = ?,
                {__field_name_album_path} = ?,
                {__field_name_updated_timestamp} = ?
            WHERE {__field_name_album_id} = ?
        """
        __execute_update(update_sql, update_values)
        # update cache
        existing_metadata.update(
            quality_badge=latest_quality_badge,
            album_musicbrainz_id=latest_mb_id,
            album_artist_id=latest_artist_id,
            album_path=latest_album_path)
    else:
        # insert
        __insert_album_metadata(album_metadata=album_metadata)
        __album_metadata_cache[album_metadata.album_id] = album_metadata


def save_artist_metadata(artist_metadata: ArtistMetadata):
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"save_artist_metadata for artist_id: {artist_metadata.artist_id} "
                    f"name: {artist_metadata.artist_name} "
                    f"musicbrainz_id: {artist_metadata.artist_musicbrainz_id}")
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
            now,
            artist_metadata.artist_id)
        update_sql: str = f"""
            UPDATE
                {TableName.ARTIST_METADATA.value}
            SET
                {__field_name_artist_name} = ?,
                {__field_name_artist_musicbrainz_id} = ?,
                {__field_name_artist_album_count} = ?,
                {__field_name_artist_cover_art} = ?,
                {__field_name_updated_timestamp} = ?
            WHERE {__field_name_artist_id} = ?
        """
        __execute_update(update_sql, update_values)
        # update cache
        existing_metadata.update(
            artist_name=artist_metadata.artist_name,
            artist_musicbrainz_id=artist_metadata.artist_musicbrainz_id,
            artist_album_count=artist_metadata.artist_album_count,
            artist_cover_art=artist_metadata.artist_cover_art)
    else:
        # insert
        __insert_artist_metadata(artist_metadata=artist_metadata)
        __artist_metadata_cache[artist_metadata.artist_id] = artist_metadata


def save_key_value_item(key_value_item: KeyValueItem):
    existing: KeyValueItem = get_kv_item(partition=key_value_item.partition, key=key_value_item.key)
    if existing:
        # update
        now: datetime.datetime = datetime.datetime.now()
        update_values = (
            key_value_item.value,
            now,
            key_value_item.partition,
            key_value_item.key)
        update_sql: str = f"""
            UPDATE
                {TableName.KV_CACHE.value}
            SET
                {__field_name_kv_cache_value} = ?,
                {__field_name_updated_timestamp} = ?
            WHERE
                {__field_name_kv_cache_partition} = ? AND
                {__field_name_kv_cache_key} = ?
        """
        __execute_update(update_sql, update_values)
        # update cache
        existing.update(value=key_value_item.value)
    else:
        # insert
        __insert_key_value_item(key_value=key_value_item)
        # partition if empty
        partition_dict: dict[str, any] = (__key_value_cache[key_value_item.partition]
                                          if key_value_item.partition in __key_value_cache
                                          else None)
        if not partition_dict:
            partition_dict = {}
            __key_value_cache[key_value_item.partition] = partition_dict
        partition_dict[key_value_item.key] = key_value_item


def __insert_album_metadata(album_metadata: AlbumMetadata):
    now: datetime.datetime = datetime.datetime.now()
    insert_values = (
        album_metadata.album_id,
        album_metadata.quality_badge,
        album_metadata.album_artist_id,
        album_metadata.album_path,
        now,
        now)
    insert_sql: str = f"""
        INSERT INTO {TableName.ALBUM_METADATA.value}(
            {__field_name_album_id},
            {__field_name_album_quality_badge},
            {__field_name_album_artist_id},
            {__field_name_album_path},
            {__field_name_created_timestamp},
            {__field_name_updated_timestamp}
        ) VALUES (?, ?, ?, ?, ?, ?)
    """
    __execute_update(insert_sql, insert_values)


def __insert_artist_metadata(artist_metadata: ArtistMetadata):
    now: datetime.datetime = datetime.datetime.now()
    insert_values = (
        artist_metadata.artist_id,
        artist_metadata.artist_name,
        artist_metadata.artist_musicbrainz_id,
        artist_metadata.artist_album_count,
        artist_metadata.artist_cover_art,
        now,
        now)
    insert_sql: str = f"""
        INSERT INTO {TableName.ARTIST_METADATA.value}(
            {__field_name_artist_id},
            {__field_name_artist_name},
            {__field_name_artist_musicbrainz_id},
            {__field_name_artist_album_count},
            {__field_name_artist_cover_art},
            {__field_name_created_timestamp},
            {__field_name_updated_timestamp}
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    __execute_update(insert_sql, insert_values)


def __insert_key_value_item(key_value: KeyValueItem):
    now: datetime.datetime = datetime.datetime.now()
    insert_values = (key_value.partition, key_value.key, key_value.value, now, now)
    insert_sql: str = f"""
        INSERT INTO {TableName.KV_CACHE.value}(
            {__field_name_kv_cache_partition},
            {__field_name_kv_cache_key},
            {__field_name_kv_cache_value},
            {__field_name_created_timestamp},
            {__field_name_updated_timestamp}
        ) VALUES (?, ?, ?, ?, ?)
    """
    __execute_update(insert_sql, insert_values)


def preload_metadata(
        table_name: str,
        field_list: list[str],
        row_converter: Callable[[list[any]], any],
        cache_writer: Callable[[any, any], any]):
    cursor = __connection.cursor()
    q: str = f"""
        SELECT
            {", ".join(field_list)}
        FROM
            {table_name}
    """
    cursor.execute(q)
    rows = cursor.fetchall()
    cursor.close()
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
            __field_name_created_timestamp,
            __field_name_updated_timestamp,
            __field_name_album_id,
            __field_name_album_quality_badge,
            __field_name_album_musicbrainz_id,
            __field_name_album_artist_id,
            __field_name_album_path],
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
            __field_name_created_timestamp,
            __field_name_updated_timestamp,
            __field_name_artist_id,
            __field_name_artist_name,
            __field_name_artist_musicbrainz_id,
            __field_name_artist_album_count,
            __field_name_artist_cover_art
            ],
        row_converter=lambda x: ArtistMetadata(
            artist_id=x[2],
            artist_name=x[3],
            artist_musicbrainz_id=x[4],
            artist_album_count=x[5],
            artist_cover_art=x[6],
            created_timestamp=x[0],
            updated_timestamp=x[1]),
        cache_writer=lambda x: __update_artist_cache(x))


def __preload():
    __preload_album_metadata()
    __preload_artist_metadata()


def __execute_update(sql: str, data: tuple, cursor=None, do_commit: bool = True):
    the_cursor = cursor if cursor else __connection.cursor()
    the_cursor.execute(sql, data)
    if not cursor:
        the_cursor.close()
    if do_commit:
        __connection.commit()


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
    cursor_obj = __connection.cursor()
    # Creating table
    create_table: str = """
        CREATE TABLE IF NOT EXISTS db_version(
        version VARCHAR(32) PRIMARY KEY)
    """
    cursor_obj.execute(create_table)
    cursor_obj.close()


def get_db_version() -> str:
    cursor = __connection.cursor()
    cursor.execute("SELECT version FROM db_version")
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
        cursor.execute("INSERT INTO db_version(version) VALUES(?)", insert_tuple)
        cursor.close()
    else:
        msgproc.log(f"Updating db version to [{version}] from [{db_version}] ...")
        update_tuple = (version, db_version)
        cursor = __connection.cursor()
        cursor.execute("UPDATE db_version set version = ? WHERE version = ?", update_tuple)
        cursor.close()
    __connection.commit()
    msgproc.log(f"Db version correctly set to [{version}]")


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
        table_name=TableName.KV_CACHE.value,
        sql=__sql_create_table_kv_cache_v1)


def do_migration_1():
    __do_create_table(
        table_name=TableName.ALBUM_METADATA.value,
        sql=__sql_create_table_album_metadata_v1)


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
            migration_name=f"Create new table {TableName.KV_CACHE.value}",
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
            migration_function=migration_9)]
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
