# Copyright (C) 2025,2026 Giovanni Fulco
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

import datetime
from enum import Enum
from typing import Protocol
import sqlhelper


class KeyValueCachingException(Exception):
    pass


class Version(Enum):
    V1 = "v1"


class KeyValueTableName(Enum):
    TABLE_NAME_V1 = (Version.V1, "kv_cache_v1")

    @property
    def version(self) -> Version:
        return self.value[0]

    @property
    def table_name(self) -> str:
        return self.value[1]


class KeyValueCacheColumnName(Enum):
    CREATED_TIMESTAMP = "created_timestamp"
    UPDATED_TIMESTAMP = "updated_timestamp"
    ITEM_VALUE = "value"
    ITEM_KEY = "key"
    ITEM_PARTITION = "partition"


def _get_table_by_version(version: Version) -> KeyValueTableName:
    current: KeyValueTableName
    for current in KeyValueTableName:
        if current.version == version:
            return current
    return KeyValueCachingException(f"No result for version [{version}]")


def build_create_v1_sql() -> str:
    return f"""
        CREATE TABLE {KeyValueTableName.TABLE_NAME_V1.table_name}(
        {KeyValueCacheColumnName.ITEM_PARTITION.value} VARCHAR(255),
        {KeyValueCacheColumnName.ITEM_KEY.value} VARCHAR(255),
        {KeyValueCacheColumnName.ITEM_VALUE.value}  VARCHAR(255),
        {KeyValueCacheColumnName.CREATED_TIMESTAMP.value} TIMESTAMP,
        {KeyValueCacheColumnName.UPDATED_TIMESTAMP.value} TIMESTAMP,
        PRIMARY KEY (
        {KeyValueCacheColumnName.ITEM_PARTITION.value},
        {KeyValueCacheColumnName.ITEM_KEY.value}))
"""


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


def insert_kv_item_v1(
        sql_executor: sqlhelper.SqlExecutor,
        key_value_item: KeyValueItem,
        creation_timestamp: datetime.datetime,
        do_commit: bool = True) -> None:
    insert_values = (
        key_value_item.partition,
        key_value_item.key,
        key_value_item.value,
        creation_timestamp,
        creation_timestamp)
    insert_sql: str = sqlhelper.create_simple_insert_sql(
        table_name=KeyValueTableName.TABLE_NAME_V1.table_name,
        column_list=[
            KeyValueCacheColumnName.ITEM_PARTITION.value,
            KeyValueCacheColumnName.ITEM_KEY.value,
            KeyValueCacheColumnName.ITEM_VALUE.value,
            KeyValueCacheColumnName.CREATED_TIMESTAMP.value,
            KeyValueCacheColumnName.UPDATED_TIMESTAMP.value])
    sql_executor(
        sql=insert_sql,
        data=insert_values,
        do_commit=do_commit)


def update_kv_item_v1(
        sql_executor: sqlhelper.SqlExecutor,
        partition: str,
        key: str,
        value: str,
        update_timestamp: datetime.datetime) -> None:
    update_values = (
        value,
        update_timestamp,
        partition,
        key)
    update_sql: str = sqlhelper.create_simple_update_sql(
        table_name=KeyValueTableName.TABLE_NAME_V1.table_name,
        set_column_list=[
            KeyValueCacheColumnName.ITEM_VALUE.value,
            KeyValueCacheColumnName.UPDATED_TIMESTAMP.value],
        where_column_list=[
            KeyValueCacheColumnName.ITEM_PARTITION.value,
            KeyValueCacheColumnName.ITEM_KEY.value])
    sql_executor(
        sql=update_sql,
        data=update_values,
        do_commit=True)


def load_kv_item_v1(
        sql_selector: sqlhelper.SqlSelector,
        partition: str,
        key: str) -> KeyValueItem:
    t = (partition, key)
    q: str = sqlhelper.create_simple_select_sql(
        table_name=KeyValueTableName.TABLE_NAME_V1.table_name,
        select_column_list=[
            KeyValueCacheColumnName.CREATED_TIMESTAMP.value,
            KeyValueCacheColumnName.UPDATED_TIMESTAMP.value,
            KeyValueCacheColumnName.ITEM_VALUE.value],
        where_column_list=[
            KeyValueCacheColumnName.ITEM_PARTITION.value,
            KeyValueCacheColumnName.ITEM_KEY.value])
    rows = sql_selector(sql=q, parameters=t)
    if not rows:
        return None
    if len(rows) > 1:
        raise KeyValueCachingException(f"Multiple {KeyValueTableName.TABLE_NAME_V1.table_name} records for [{partition}] [{key}]")
    row = rows[0]
    result: KeyValueItem = KeyValueItem(
        created_timestamp=row[0],
        updated_timestamp=row[1],
        partition=partition,
        key=key,
        value=row[2])
    return result


def delete_kv_item_v1(
        sql_executor: sqlhelper.SqlExecutor,
        partition: str,
        key: str):
    t = (partition, key)
    q: str = f"""
            DELETE FROM
                {KeyValueTableName.TABLE_NAME_V1.table_name}
            WHERE
                {KeyValueCacheColumnName.ITEM_PARTITION.value} = ? AND
                {KeyValueCacheColumnName.ITEM_KEY.value} = ?
            """
    sql_executor(sql=q, data=t, do_commit=True)


class KvItemLoader(Protocol):
    def __call__(
            self,
            partition: str,
            key: str) -> KeyValueItem:
        ...


class KvItemUpdater(Protocol):
    def __call__(
            self,
            partition: str,
            key: str,
            value: str,
            update_timestamp: datetime.datetime,
            do_commit: bool) -> None:
        ...


class KvItemCreator(Protocol):
    def __call__(
            self,
            key_value_item: KeyValueItem,
            creation_timestamp: datetime.datetime,
            do_commit: bool) -> None:
        ...


def get_key_value_item(
        partition: str,
        key: str,
        kv_loader: KvItemLoader) -> KeyValueItem:
    kv_item: KeyValueItem = kv_loader(partition=partition, key=key)
    return kv_item


def put_key_value_item(
        key_value_item: KeyValueItem,
        creator: KvItemCreator,
        updater: KvItemUpdater,
        loader: KvItemLoader,
        do_commit: bool = True):
    existing: KeyValueItem = get_key_value_item(
        partition=key_value_item.partition,
        key=key_value_item.key,
        kv_loader=loader)
    if existing:
        # update persistent data
        now: datetime.datetime = datetime.datetime.now()
        updater(
            partition=key_value_item.partition,
            key=key_value_item.key,
            value=key_value_item.value,
            update_timestamp=now,
            do_commit=do_commit)
        # update cache
        existing.update(value=key_value_item.value)
    else:
        # insert
        creator(
            key_value_item=key_value_item,
            creation_timestamp=datetime.datetime.now(),
            do_commit=do_commit)
