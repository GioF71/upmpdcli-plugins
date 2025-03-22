# Copyright (C) 2023,2024 Giovanni Fulco
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
import cmdtalkplugin
import upmplgutils
import constants
import config

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


class AlbumMetadata:

    def __init__(self):
        self.created_timestamp: datetime.datetime = datetime.datetime.now()
        self.updated_timestamp = self.created_timestamp

    album_id: str = None
    quality_badge: str = None
    created_timestamp: datetime.datetime = None
    updated_timestamp: datetime.datetime = None


__table_name_album_metadata_v1: str = "album_metadata_v1"

__field_name_album_id: str = "album_id"
__field_name_album_quality_badge: str = "quality_badge"
__field_name_created_timestamp: str = "created_timestamp"
__field_name_updated_timestamp: str = "updated_timestamp"


__sql_create_table_album_metadata_v1: str = f"""
        CREATE TABLE {__table_name_album_metadata_v1}(
        {__field_name_album_id} VARCHAR(255) PRIMARY KEY,
        {__field_name_album_quality_badge} VARCHAR(255),
        {__field_name_created_timestamp} TIMESTAMP,
        {__field_name_updated_timestamp} TIMESTAMP)
"""


def get_album_metadata(album_id: str) -> AlbumMetadata:
    t = (album_id, )
    cursor = __connection.cursor()
    q: str = f"""
            SELECT
                {__field_name_album_id},
                {__field_name_album_quality_badge},
                {__field_name_created_timestamp},
                {__field_name_updated_timestamp}
            FROM
                {__table_name_album_metadata_v1}
            WHERE {__field_name_album_id} = ?"""
    cursor.execute(q, t)
    rows = cursor.fetchall()
    cursor.close()
    if not rows:
        return None
    if len(rows) > 1:
        raise Exception(f"Multiple {__table_name_album_metadata_v1} records for [{album_id}]")
    row = rows[0]
    result: AlbumMetadata = AlbumMetadata()
    result.album_id = row[0]
    result.quality_badge = row[1]
    result.created_timestamp = row[2]
    result.updated_timestamp = row[3]
    return result


def delete_album_metadata(album_id: str):
    t = (album_id, )
    cursor = __connection.cursor()
    q: str = f"""
            DELETE FROM {__table_name_album_metadata_v1}
            WHERE {__field_name_album_id} = ?"""
    cursor.execute(q, t)
    __connection.commit()


def save_quality_badge(album_id: str, quality_badge: str):
    # msgproc.log(f"save_quality_badge for album_id: {album_id} "
    #             f"quality_badge: {quality_badge}")
    album_metadata: AlbumMetadata = get_album_metadata(album_id=album_id)
    if album_metadata:
        to_update: bool = quality_badge != album_metadata.quality_badge
        # msgproc.log(f"{AlbumMetadata.__name__} exists for album_id {album_id}, updating: [{to_update}] ...")
        if to_update:
            if config.debug_badge_mngmt:
                msgproc.log(f"{AlbumMetadata.__name__} exists for album_id {album_id}, "
                            f"needs updating to [{quality_badge}]...")
            # this implementation does NOT change if we add more fields to AlbumMetadata
            now: datetime.datetime = datetime.datetime.now()
            update_values = (quality_badge, now, album_metadata.album_id)
            update_sql: str = f"""
                UPDATE
                    {__table_name_album_metadata_v1}
                SET
                    {__field_name_album_quality_badge} = ?,
                    {__field_name_updated_timestamp} = ?
                WHERE {__field_name_album_id} = ?
            """
            __execute_update(update_sql, update_values)
        else:
            if config.debug_badge_mngmt:
                msgproc.log(f"save_quality_badge not updating for album_id [{album_id}]")
    else:
        if config.debug_badge_mngmt:
            msgproc.log(f"{AlbumMetadata.__name__} not found for "
                        f"album_id {album_id}, inserting ...")
        # just create a new AlbumMetaData with just the quality badge and save it
        album_metadata = AlbumMetadata()
        album_metadata.album_id = album_id
        album_metadata.quality_badge = quality_badge
        insert_album_metadata(album_metadata=album_metadata)


def save_album_metadata(album_metadata: AlbumMetadata):
    msgproc.log(f"save_album_metadata for album_id: {album_metadata.album_id} "
                f"quality_badge: {album_metadata.quality_badge}")
    album_metadata: AlbumMetadata = get_album_metadata(album_id=album_metadata.album_id)
    now: datetime.datetime = datetime.datetime.now()
    if album_metadata:
        # update
        # might change if we add more fields to AlbumMetadata
        update_values = (album_metadata.quality_badge, now, album_metadata.album_id)
        update_sql: str = f"""
            UPDATE
                {__table_name_album_metadata_v1}
            SET
                {__field_name_album_quality_badge} = ?,
                {__field_name_updated_timestamp} = ?
            WHERE {__field_name_album_id} = ?
        """
        __execute_update(update_sql, update_values)
    else:
        # insert
        insert_album_metadata(album_metadata=album_metadata)


def insert_album_metadata(album_metadata: AlbumMetadata):
    if config.debug_badge_mngmt:
        msgproc.log(f"insert_album_metadata for album_id: {album_metadata.album_id} "
                    f"quality_badge: {album_metadata.quality_badge}")
    now: datetime.datetime = datetime.datetime.now()
    insert_values = (album_metadata.album_id, album_metadata.quality_badge, now, now)
    insert_sql: str = f"""
        INSERT INTO {__table_name_album_metadata_v1}(
            {__field_name_album_id},
            {__field_name_album_quality_badge},
            {__field_name_created_timestamp},
            {__field_name_updated_timestamp}
        ) VALUES (?, ?, ?, ?)
    """
    __execute_update(insert_sql, insert_values)


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
        msgproc.log(f"Updating db version to [{version}] from [{current_db_version}] ...")
        update_tuple = (version, current_db_version)
        cursor = __connection.cursor()
        cursor.execute("UPDATE db_version set version = ? WHERE version = ?", update_tuple)
        cursor.close()
    __connection.commit()
    msgproc.log(f"Db version correctly set to [{version}]")


def do_migration_1():
    __do_create_table(
        table_name=__table_name_album_metadata_v1,
        sql=__sql_create_table_album_metadata_v1)


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

current_db_version: str = get_db_version()


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


migrations: list[Migration] = [
    Migration(
        migration_name="Initial Creation",
        apply_on=None,
        migration_function=migration_0),
    Migration(
        migration_name=f"Create new table {__table_name_album_metadata_v1}",
        apply_on="1",
        migration_function=migration_1)]


current_migration: Migration
for current_migration in migrations:
    current_db_version: int = get_db_version()
    if not current_db_version or current_db_version == current_migration.apply_on:
        msgproc.log(f"Migration [{current_migration.migration_name}] "
                    f"is executing on current db version [{current_db_version}] ...")
        current_migration.migration_function()
        msgproc.log(f"Migration [{current_migration.migration_name}] executed.")
    else:
        msgproc.log(f"Migration [{current_migration.migration_name}] skipped.")

migrated_db_version: str = get_db_version()
msgproc.log(f"Current db version is [{migrated_db_version}]")
