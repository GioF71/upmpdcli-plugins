# Copyright (C) 2023 Giovanni Fulco
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

import cmdtalkplugin
import upmplgutils
import constants
import os
import datetime
import sqlite3

from typing import Callable
from enum import Enum

from played_track import PlayedTrack
from tile_type import TileType
from tile_image import TileImage

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

class PlayedTracksSorting(Enum):

    LAST_PLAYED_FIRST = 0, "lp-first", "last_played", "DESC"
    MOST_PLAYED_FIRST = 1, "mp-first", "play_count", "DESC"

    def __init__(self, 
            num : int, 
            element_name : str,
            field_name : str,
            field_order : str):
        self.num : int = num
        self.element_name : str = element_name
        self.field_name : str = field_name
        self.field_order : str = field_order

    def get_name(self) -> str:
        return self.element_name
    
    def get_field_name(self) -> str:
        return self.field_name

    def get_field_order(self) -> str:
        return self.field_order

def __get_db_filename() -> str: return "tidal.db"

def __get_db_full_path() -> str:
    return os.path.join(upmplgutils.getcachedir(constants.plugin_name), __get_db_filename())

def __get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(
        __get_db_full_path(),
        detect_types = 
            sqlite3.PARSE_DECLTYPES |
            sqlite3.PARSE_COLNAMES)
    return connection

def __prepare_table_db_version():
    cursor_obj = __connection.cursor()
    # Creating table
    create_table : str = """
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
    if rows: return rows[0][0]
    return None

def __store_db_version(version : str):
    current_db_version : str = get_db_version()
    if not current_db_version:
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

def __prepare_table_played_track_v1():
    msgproc.log(f"Preparing table played_track_v1 ...")
    cursor_obj = __connection.cursor()
    # Creating table
    create_table : str = """
        CREATE TABLE played_track_v1(
        track_id VARCHAR(255) PRIMARY KEY,
        play_count INTEGER,
        last_played TIMESTAMP)
    """
    cursor_obj.execute(create_table)
    # Creating index on last_played
    msgproc.log(f"Preparing index played_track_idx_last_played ...")
    create_index_last_played : str = """
        CREATE INDEX played_track_idx_last_played 
        ON played_track_v1(last_played)"""
    cursor_obj.execute(create_index_last_played)
    # Creating index on play_count
    msgproc.log(f"Preparing index played_track_idx_play_count ...")
    create_index_play_count : str = """
        CREATE INDEX played_track_idx_play_count 
        ON played_track_v1(play_count)"""
    cursor_obj.execute(create_index_play_count)
    cursor_obj.close()
    msgproc.log(f"Prepared table played_track_v1.")

def __prepare_table_tile_image_v1():
    msgproc.log(f"Preparing table tile_image_v1 ...")
    cursor_obj = __connection.cursor()
    # Creating table
    create_table : str = """
        CREATE TABLE tile_image_v1(
        tile_type VARCHAR(64) NOT NULL,
        tile_id VARCHAR(255) NOT NULL,
        tile_image VARCHAR(255),
        PRIMARY KEY(tile_type, tile_id)) 
    """
    cursor_obj.execute(create_table)
    cursor_obj.close()
    msgproc.log(f"Prepared table tile_image_v1.")

def load_tile_image(
        tile_type : TileType,
        tile_id : str) -> TileImage:
    tuple = (tile_type.tile_type_name, tile_id)
    cursor = __connection.cursor()
    cursor.execute(
        f"SELECT tile_image, update_time \
          FROM tile_image_v1 \
          WHERE tile_type = ? AND tile_id = ?", 
        tuple)
    rows = cursor.fetchall()
    cursor.close()
    if not rows: return None
    if len(rows) > 1:
        raise Exception(f"Multiple tile_image records for tile_type [{tile_type.tile_type_name}], tile_id [{tile_id}]")
    tile_image : TileImage = TileImage()
    tile_image.tile_image = rows[0][0]
    tile_image.update_time = rows[0][1]
    tile_image.tile_type = tile_type.tile_type_name
    tile_image.tile_id = tile_id
    return tile_image

def save_tile_image(
        tile_type : TileType,
        tile_id : str,
        tile_image : str):
    now : datetime.datetime = datetime.datetime.now()
    existing : TileImage = load_tile_image(tile_type = tile_type, tile_id = tile_id)
    if existing:
        tuple = (tile_image, now, tile_type.tile_type_name, tile_id)
        cursor = __connection.cursor()
        cursor.execute("UPDATE tile_image_v1 SET tile_image = ?, update_time = ? WHERE tile_type = ? AND tile_id = ?", tuple)
        cursor.close()
        __connection.commit()
    else: 
        tuple = (tile_type.tile_type_name, tile_id, tile_image, now)
        cursor = __connection.cursor()
        cursor.execute("INSERT INTO tile_image_v1(tile_type, tile_id, tile_image, update_time) VALUES(?, ?, ?, ?)", tuple)
        cursor.close()
        __connection.commit()

def __alter_played_track_v1_add_album_id():
    msgproc.log(f"Updating table played_track_v1 with new column album_id ...")
    cursor_obj = __connection.cursor()
    # Creating table
    alter : str = """
        ALTER TABLE played_track_v1
        ADD COLUMN album_id VARCHAR(255)
    """
    cursor_obj.execute(alter)
    cursor_obj.close()
    msgproc.log(f"Altered table played_track_v1 with new column album_id.")

def __alter_played_track_v1_add_album_track_count():
    msgproc.log(f"Updating table played_track_v1 with new column album_track_count ...")
    cursor_obj = __connection.cursor()
    # Creating table
    alter : str = """
        ALTER TABLE played_track_v1
        ADD COLUMN album_track_count INTEGER
    """
    cursor_obj.execute(alter)
    cursor_obj.close()
    msgproc.log(f"Altered table played_track_v1 with new column album_track_count.")

def __add_index_by_album_id_to_played_track_v1():
    msgproc.log(f"Adding index on album_id on table played_track_v1 ...")
    cursor_obj = __connection.cursor()
    create_index : str = """
        CREATE INDEX played_track_idx_album_id 
        ON played_track_v1(album_id)"""
    cursor_obj.execute(create_index)
    cursor_obj.close()
    msgproc.log(f"Added index on album_id to table played_track_v1")

def __alter_tile_image_v1_add_update_time():
    msgproc.log(f"Updating table tile_image_v1 with new column update_time ...")
    cursor_obj = __connection.cursor()
    # Creating table
    alter : str = """
        ALTER TABLE tile_image_v1
        ADD COLUMN update_time TIMESTAMP
    """
    cursor_obj.execute(alter)
    cursor_obj.close()
    msgproc.log(f"Altered table tile_image_v1 with new column update_time.")

def migration_0():
    msgproc.log(f"Creating db version 1 ...")
    __prepare_table_played_track_v1()
    __store_db_version("1")
    msgproc.log(f"Created db version 1.")

def migration_1():
    msgproc.log(f"Creating db version 2 ...")
    __prepare_table_tile_image_v1()
    __store_db_version("2")
    msgproc.log(f"Updated db to version 2.")

def migration_2():
    msgproc.log(f"Creating db version 3 ...")
    __alter_played_track_v1_add_album_id()
    __alter_played_track_v1_add_album_track_count()
    __store_db_version("3")
    msgproc.log(f"Updated db to version 3.")

def migration_3():
    msgproc.log(f"Creating db version 4 ...")
    __add_index_by_album_id_to_played_track_v1()
    __store_db_version("4")
    msgproc.log(f"Updated db to version 4.")

def migration_4():
    msgproc.log(f"Creating db version 4 ...")
    __alter_tile_image_v1_add_update_time()
    __store_db_version("5")
    msgproc.log(f"Updated db to version 5.")

def _insert_playback(
        track_id : str, 
        album_id : str,
        album_track_count : int, 
        play_count : str, 
        last_played : datetime.datetime):
    tuple = (track_id, album_id, album_track_count, play_count, last_played)
    cursor = __connection.cursor()
    cursor.execute("INSERT INTO played_track_v1(track_id, album_id, album_track_count, play_count, last_played) VALUES(?, ?, ?, ?, ?)", tuple)
    cursor.close()
    __connection.commit()

def _update_playback(
        track_id : str,
        album_id : str,
        album_track_count : int, 
        play_count : str, 
        last_played : datetime.datetime):
    tuple = (album_id, album_track_count, play_count, last_played, track_id)
    cursor = __connection.cursor()
    cursor.execute("UPDATE played_track_v1 set album_id = ?, album_track_count = ?, play_count = ?, last_played = ? WHERE track_id = ?", tuple)
    cursor.close()
    __connection.commit()

def get_played_tracks(sorting : PlayedTracksSorting, max_tracks : int = 50) -> list[PlayedTrack]:
    tuple = (max_tracks if max_tracks and max_tracks <= 100 else 50, )
    cursor = __connection.cursor()
    cursor.execute(
        f"SELECT track_id, play_count, last_played, album_id, album_track_count \
          FROM played_track_v1 \
          ORDER BY {sorting.get_field_name()} {sorting.get_field_order()} LIMIT ?", 
        tuple)
    rows = cursor.fetchall()
    cursor.close()
    if not rows: return list()
    played_list : list[PlayedTrack] = list()
    for row in rows:
        played : PlayedTrack = PlayedTrack()
        played.track_id = row[0]
        played.play_count = row[1]
        played.last_played = row[2]
        played.album_id = row[3]
        played.album_track_count = row[4]
        played_list.append(played)
    return played_list

def get_last_played_tracks(max_tracks : int = 50) -> list[PlayedTrack]:
    return get_played_tracks(sorting = PlayedTracksSorting.LAST_PLAYED_FIRST, max_tracks = max_tracks)
 
def get_most_played_tracks(max_tracks : int = 50) -> list[PlayedTrack]:
    return get_played_tracks(sorting = PlayedTracksSorting.MOST_PLAYED_FIRST, max_tracks = max_tracks)
 
def get_played_track_entry(track_id : str) -> PlayedTrack:
    tuple = (track_id,)
    cursor = __connection.cursor()
    cursor.execute("SELECT play_count, last_played FROM played_track_v1 WHERE track_id = ?", tuple)
    rows = cursor.fetchall()
    cursor.close()
    if not rows: return None
    result : PlayedTrack = PlayedTrack()
    result.track_id = track_id
    result.play_count = rows[0][0]
    result.last_played = rows[0][1]
    return result

def track_playback(track_id : str, album_id : str, album_track_count : int):
    now : datetime.datetime = datetime.datetime.now()
    existing_entry : PlayedTrack = get_played_track_entry(track_id)
    if existing_entry:
        # update!
        play_count : int = existing_entry.play_count
        msgproc.log(f"Updating playback entry for track_id {track_id} to play_count [{play_count + 1}] ...")
        _update_playback(
            track_id = track_id, 
            album_id = album_id,
            album_track_count = album_track_count,
            play_count = play_count + 1, 
            last_played = now)
    else:
        # insert
        msgproc.log(f"Inserting new playback entry for track_id {track_id} ...")
        _insert_playback(
            track_id = track_id, 
            album_id = album_id,
            album_track_count = album_track_count, 
            play_count = 1, 
            last_played = now)
    msgproc.log(f"Track playback for {track_id} completed.")

__connection : sqlite3.Connection = __get_connection()
__prepare_table_db_version()

current_db_version : str = get_db_version()

class Migration:

    def __init__(self, migration_name : str, apply_on : str,  migration_function : Callable[[], any]):
        self._migration_name : str = migration_name
        self._apply_on : str = apply_on
        self._migration_function : Callable[[], any] = migration_function
    
    @property
    def migration_name(self) -> str:
        """I'm the 'migration_name' property."""
        return self._migration_name

    @property
    def apply_on(self) -> int:
        """I'm the 'apply_on' property."""
        return self._apply_on

    @property
    def migration_function(self) -> Callable[[], any]:
        """I'm the 'migration_function' property."""
        return self._migration_function

migrations : list[Migration] = [
    Migration(migration_name = "initial_creation", apply_on = None, migration_function = migration_0),
    Migration(migration_name = "tile_image_v1", apply_on = "1", migration_function = migration_1),
    Migration(migration_name = "add_album_info_to_played_tracks_v1", apply_on = "2", migration_function = migration_2),
    Migration(migration_name = "add_album_id_index_to_played_tracks_v1", apply_on = "3", migration_function = migration_3),
    Migration(migration_name = "add_update_time_to_tile_image_v1", apply_on = "4", migration_function = migration_4)
]

current_migration : Migration
for current_migration in migrations:
    current_db_version : int = get_db_version()
    if not current_db_version or current_db_version == current_migration.apply_on:
        msgproc.log(f"Migration [{current_migration.migration_name}] is executing on current db version [{current_db_version}] ...")
        current_migration.migration_function()
        msgproc.log(f"Migration [{current_migration.migration_name}] executed.")
    else:
        msgproc.log(f"Migration [{current_migration.migration_name}] skipped.")

migrated_db_version : str = get_db_version()
msgproc.log(f"Current db version is [{migrated_db_version}]")
