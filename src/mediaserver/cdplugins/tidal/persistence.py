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

from enum import Enum

from played_track import PlayedTrack

db_version : str = "1"

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

def get_db_version():
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
        cursor.execute("UPDATE db_version set(version = ?) WHERE version = ?", update_tuple)
        cursor.close()
    __connection.commit()
    msgproc.log(f"Db version correctly set to [{version}]")

def __prepare_table_played_track_v1():
    msgproc.log(f"Preparing table played_track_v1 ...")
    cursor_obj = __connection.cursor()
    # Creating table
    create_table : str = """
        CREATE TABLE IF NOT EXISTS played_track_v1 (
        track_id VARCHAR(255) PRIMARY KEY,
        play_count INTEGER,
        last_played TIMESTAMP)
    """
    cursor_obj.execute(create_table)
    # Creating index on last_player
    msgproc.log(f"Preparing index played_track_idx_last_played ...")
    create_index_last_played : str = """
        CREATE INDEX IF NOT EXISTS played_track_idx_last_played 
        ON played_track_v1(last_played)"""
    cursor_obj.execute(create_index_last_played)
    # Creating index on play_count
    msgproc.log(f"Preparing index played_track_idx_play_count ...")
    create_index_play_count : str = """
        CREATE INDEX IF NOT EXISTS played_track_idx_play_count 
        ON played_track_v1(play_count)"""
    cursor_obj.execute(create_index_play_count)
    cursor_obj.close()
    msgproc.log(f"Prepared table played_track_v1.")

def __create_db_version_1():
    msgproc.log(f"Creating db version 1 ...")
    __prepare_table_played_track_v1()
    __store_db_version("1")
    msgproc.log(f"Created db version 1.")

def _insert_playback(track_id : str, play_count : str, last_played : datetime.datetime):
    tuple = (track_id, play_count, last_played)
    cursor = __connection.cursor()
    cursor.execute("INSERT INTO played_track_v1(track_id, play_count, last_played) VALUES(?, ?, ?)", tuple)
    cursor.close()
    __connection.commit()

def _update_playback(track_id : str, play_count : str, last_played : datetime.datetime):
    tuple = (play_count, last_played, track_id)
    cursor = __connection.cursor()
    cursor.execute("UPDATE played_track_v1 set play_count = ?, last_played = ? WHERE track_id = ?", tuple)
    cursor.close()
    __connection.commit()

def get_played_tracks(sorting : PlayedTracksSorting, max_tracks : int = 50) -> list[PlayedTrack]:
    tuple = (max_tracks if max_tracks and max_tracks <= 100 else 50, )
    cursor = __connection.cursor()
    cursor.execute(
        f"SELECT track_id, play_count, last_played \
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

def track_playback(track_id : str):
    now : datetime.datetime = datetime.datetime.now()
    existing_entry : PlayedTrack = get_played_track_entry(track_id)
    if existing_entry:
        # update!
        play_count : int = existing_entry.play_count
        msgproc.log(f"Updating playback entry for track_id {track_id} to play_count [{play_count + 1}] ...")
        _update_playback(track_id, play_count + 1, now)
    else:
        # insert
        msgproc.log(f"Inserting new playback entry for track_id {track_id} ...")
        _insert_playback(track_id, 1, now)
    msgproc.log(f"Track playback for {track_id} completed.")

__connection : sqlite3.Connection = __get_connection()
__prepare_table_db_version()

current_db_version : str = get_db_version()

if current_db_version == None:
    __create_db_version_1()
elif current_db_version == db_version:
    msgproc.log(f"Current db version is [{current_db_version}], no migration is necessary.")
