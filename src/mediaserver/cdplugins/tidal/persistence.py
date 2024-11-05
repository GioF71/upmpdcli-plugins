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

import os
import datetime
import sqlite3

from typing import Callable
from enum import Enum

import cmdtalkplugin
import upmplgutils
import constants

from played_track import PlayedTrack
from played_album import PlayedAlbum

from tile_type import TileType
from tile_image import TileImage

from played_track_request import PlayedTrackRequest

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

__table_name_played_track_v1 : str = "played_track_v1"

__table_name_listen_album_queue_v1 : str = "listen_album_queue_v1"
__table_name_listen_artist_queue_v1 : str = "listen_artist_queue_v1"
__table_name_listen_track_queue_v1 : str = "listen_track_queue_v1"

__table_name_album_metadata_cache_v1 : str = "album_metadata_cache_v1"

__field_name_album_id : str = "album_id"
__field_name_artist_id : str = "artist_id"
__field_name_artist_name : str = "artist_name"
__field_name_explicit : str = "explicit"
__field_name_release_date : str = "release_date"
__field_name_available_release_date : str = "available_release_date"
__field_name_image_url : str = "image_url"
__field_name_audio_modes : str = "audio_modes"
__field_name_audio_quality : str = "audio_quality"
__field_name_media_metadata_tags : str = "media_metadata_tags"
__field_name_track_id : str = "track_id"
__field_name_name : str = "name"

__field_name_created_timestamp : str = "created_timestamp"


__most_played_albums_query : str = """
    SELECT
        album_id,
        (SUM(CAST (play_count AS FLOAT) * (CAST (track_duration AS FLOAT) / CAST (album_duration AS FLOAT))))
            AS album_played_counter
    FROM
        played_track_v1
    WHERE
        album_duration IS NOT NULL AND
        track_duration IS NOT NULL AND
        play_count > 0 AND
        last_played IS NOT NULL
    GROUP BY
        album_id
    ORDER BY
        album_played_counter DESC, last_played DESC
    """


class AlbumMetadata:

    def __init__(self):
        self.created_timestamp = datetime.datetime.now()

    album_id: str = None
    album_name: str = None
    artist_id: str = None
    artist_name: str = None
    explicit: int = None
    release_date: datetime = None
    available_release_date: datetime = None
    image_url: str = None
    # comma separated values
    audio_modes: str = None
    audio_quality: str = None
    # comma separated values
    media_metadata_tags: str = None
    created_timestamp : datetime = None


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


def __get_db_filename() -> str:
    return f"{constants.plugin_name}.db"


def __get_db_full_path() -> str:
    return os.path.join(upmplgutils.getcachedir(constants.plugin_name), __get_db_filename())


def __get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(
        __get_db_full_path(),
        detect_types = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
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
    if rows:
        return rows[0][0]
    return None


def __store_db_version(version : str):
    db_version : str = get_db_version()
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


def __prepare_table_played_track_v1():
    msgproc.log("Preparing table played_track_v1 ...")
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
    msgproc.log("Preparing index played_track_idx_last_played ...")
    create_index_last_played : str = """
        CREATE INDEX played_track_idx_last_played
        ON played_track_v1(last_played)"""
    cursor_obj.execute(create_index_last_played)
    # Creating index on play_count
    msgproc.log("Preparing index played_track_idx_play_count ...")
    create_index_play_count : str = """
        CREATE INDEX played_track_idx_play_count
        ON played_track_v1(play_count)"""
    cursor_obj.execute(create_index_play_count)
    cursor_obj.close()
    msgproc.log("Prepared table played_track_v1.")


def __prepare_table_tile_image_v1():
    msgproc.log("Preparing table tile_image_v1 ...")
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
    msgproc.log("Prepared table tile_image_v1.")


def load_tile_image(
        tile_type : TileType,
        tile_id : str) -> TileImage:
    t = (tile_type.tile_type_name, tile_id)
    cursor = __connection.cursor()
    cursor.execute(
        "SELECT tile_image, update_time \
          FROM tile_image_v1 \
          WHERE tile_type = ? AND tile_id = ?",
        t)
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
        t = (tile_image, now, tile_type.tile_type_name, tile_id)
        cursor = __connection.cursor()
        cursor.execute("""
            UPDATE
                tile_image_v1
            SET
                tile_image = ?,
                update_time = ?
            WHERE
                tile_type = ?
                AND tile_id = ?""",
            t)
        cursor.close()
        __connection.commit()
    else:
        t = (tile_type.tile_type_name, tile_id, tile_image, now)
        cursor = __connection.cursor()
        cursor.execute("INSERT INTO \
            tile_image_v1( \
                tile_type, \
                tile_id, \
                tile_image, \
                update_time \
            ) VALUES( \
                ?, ?, ?, ?)",
            t)
        cursor.close()
        __connection.commit()


def __alter_played_track_v1_add_album_id():
    msgproc.log("Updating table played_track_v1 with new column album_id ...")
    cursor_obj = __connection.cursor()
    # Creating table
    alter : str = """
        ALTER TABLE played_track_v1
        ADD COLUMN album_id VARCHAR(255)
    """
    cursor_obj.execute(alter)
    cursor_obj.close()
    msgproc.log("Altered table played_track_v1 with new column album_id.")


def __alter_played_track_v1_add_album_track_count():
    msgproc.log("Updating table played_track_v1 with new column album_track_count ...")
    cursor_obj = __connection.cursor()
    # Creating table
    alter : str = """
        ALTER TABLE played_track_v1
        ADD COLUMN album_track_count INTEGER
    """
    cursor_obj.execute(alter)
    cursor_obj.close()
    msgproc.log("Altered table played_track_v1 with new column album_track_count.")


def __add_index_by_album_id_to_played_track_v1():
    msgproc.log("Adding index on album_id on table played_track_v1 ...")
    cursor_obj = __connection.cursor()
    create_index : str = """
        CREATE INDEX played_track_idx_album_id
        ON played_track_v1(album_id)"""
    cursor_obj.execute(create_index)
    cursor_obj.close()
    msgproc.log("Added index on album_id to table played_track_v1")


def __alter_tile_image_v1_add_update_time():
    msgproc.log("Updating table tile_image_v1 with new column update_time ...")
    cursor_obj = __connection.cursor()
    # Creating table
    alter : str = """
        ALTER TABLE tile_image_v1
        ADD COLUMN update_time TIMESTAMP
    """
    cursor_obj.execute(alter)
    cursor_obj.close()
    msgproc.log("Altered table tile_image_v1 with new column update_time.")


def __alter_table_with_column(table_name : str, column_name : str, column_type : str):
    msgproc.log(f"Updating table {table_name} with new column {column_name} type {column_type} ...")
    cursor_obj = __connection.cursor()
    # Creating table
    alter : str = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
    cursor_obj.execute(alter)
    cursor_obj.close()
    msgproc.log(f"Altered table {table_name} with new column {column_name} type {column_type}.")


def __alter_table_drop_column(table_name : str, column_name : str):
    msgproc.log(f"Updating table {table_name} dropping column {column_name} ...")
    cursor_obj = __connection.cursor()
    # Creating table
    alter : str = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
    success : bool = False
    try:
        cursor_obj.execute(alter)
        success = True
    except Exception as ex:
        msgproc.log(f"WARN: Cannot alter table {table_name} and drop column {column_name} due to [{ex}]")
        msgproc.log("WARN: Check you sqlite3 version, it should be >= 3.35.0")
    cursor_obj.close()
    if success:
        msgproc.log(f"Altered table {table_name} dropping column {column_name}.")


def migration_0():
    msgproc.log("Creating db version 1 ...")
    __prepare_table_played_track_v1()
    __store_db_version("1")
    msgproc.log("Created db version 1.")


def migration_1():
    msgproc.log("Creating db version 2 ...")
    __prepare_table_tile_image_v1()
    __store_db_version("2")
    msgproc.log("Updated db to version 2.")


def migration_2():
    msgproc.log("Creating db version 3 ...")
    __alter_played_track_v1_add_album_id()
    __alter_played_track_v1_add_album_track_count()
    __store_db_version("3")
    msgproc.log("Updated db to version 3.")


def migration_3():
    msgproc.log("Creating db version 4 ...")
    __add_index_by_album_id_to_played_track_v1()
    __store_db_version("4")
    msgproc.log("Updated db to version 4.")


def migration_4():
    msgproc.log("Creating db version 4 ...")
    __alter_tile_image_v1_add_update_time()
    __store_db_version("5")
    msgproc.log("Updated db to version 5.")


def migration_5():
    msgproc.log("Creating db version 6 ...")
    table_name : str = __table_name_played_track_v1
    __alter_table_with_column(table_name, "track_name", "VARCHAR(4096)")
    __alter_table_with_column(table_name, "track_duration", "INTEGER")
    __alter_table_with_column(table_name, "track_num", "INTEGER")
    __alter_table_with_column(table_name, "volume_num", "INTEGER")
    __alter_table_with_column(table_name, "is_multidisc_album", "INTEGER")
    __alter_table_with_column(table_name, "album_num_volumes", "INTEGER")
    __alter_table_with_column(table_name, "album_name", "VARCHAR(4096)")
    __alter_table_with_column(table_name, "album_artist_name", "VARCHAR(4096)")
    __alter_table_with_column(table_name, "audio_quality", "VARCHAR(32)")
    __alter_table_with_column(table_name, "image_url", "VARCHAR(4096)")
    __store_db_version("6")
    msgproc.log("Updated db to version 6.")


def migration_template(new_version : str, migration_function : Callable):
    msgproc.log(f"Creating db version {new_version} ...")
    migration_function()
    __store_db_version(new_version)
    msgproc.log(f"Updated db to version {new_version}.")


def do_migration_6():
    table_name : str = __table_name_played_track_v1
    __alter_table_with_column(table_name, "explicit", "INTEGER")


def migration_6():
    migration_template("7", do_migration_6)


def do_migration_7():
    table_name : str = __table_name_played_track_v1
    __alter_table_with_column(table_name, "artist_name", "VARCHAR(4096)")


def migration_7():
    migration_template("8", do_migration_7)


def do_migration_8():
    table_name : str = __table_name_played_track_v1
    __alter_table_drop_column(table_name, "is_multidisc_album")


def migration_8():
    migration_template("9", do_migration_8)


def do_migration_9():
    table_name : str = __table_name_played_track_v1
    __alter_table_with_column(table_name, "album_duration", "INTEGER")


def migration_9():
    migration_template("10", do_migration_9)


def do_migration_10():
    msgproc.log("Adding index on tile_type, tile_id on table tile_image_v1 ...")
    cursor_obj = __connection.cursor()
    create_index : str = """
        CREATE INDEX tile_image_v1_idx_tile_type_and_id
        ON tile_image_v1(tile_type, tile_id)"""
    cursor_obj.execute(create_index)
    cursor_obj.close()
    msgproc.log("Added index on tile_type, tile_id on table tile_image_v1")


def migration_10():
    migration_template("11", do_migration_10)


def do_migration_11():
    table_name : str = __table_name_played_track_v1
    __alter_table_with_column(table_name, "bit_depth", "INTEGER")
    __alter_table_with_column(table_name, "sample_rate", "INTEGER")


def __do_migration_listen_queue(table_name : str, field_name : str):
    # Creating table
    create_table : str = f"""
        CREATE TABLE IF NOT EXISTS {table_name}(
        {field_name} VARCHAR(255) PRIMARY KEY,
        {__field_name_created_timestamp} TIMESTAMP)
    """
    cursor_obj = __connection.cursor()
    cursor_obj.execute(create_table)
    cursor_obj.close()


def do_migration_12():
    __do_migration_listen_queue(
        table_name=__table_name_listen_album_queue_v1,
        field_name=__field_name_album_id)


def do_migration_13():
    __do_migration_listen_queue(
        table_name=__table_name_listen_artist_queue_v1,
        field_name=__field_name_artist_id)


def do_migration_14():
    __do_migration_listen_queue(
        table_name=__table_name_listen_track_queue_v1,
        field_name=__field_name_track_id)


def do_migration_15():
    create_table : str = f"""
        CREATE TABLE IF NOT EXISTS {__table_name_album_metadata_cache_v1}(
        {__field_name_album_id} VARCHAR(255) PRIMARY KEY,
        {__field_name_name} VARCHAR(255),
        {__field_name_artist_id} VARCHAR(255),
        {__field_name_artist_name} VARCHAR(255),
        {__field_name_explicit} INTEGER,
        {__field_name_release_date} TIMESTAMP,
        {__field_name_available_release_date} TIMESTAMP,
        {__field_name_image_url} VARCHAR(255),
        {__field_name_audio_modes} VARCHAR(255),
        {__field_name_audio_quality} VARCHAR(255),
        {__field_name_media_metadata_tags} VARCHAR(255),
        {__field_name_created_timestamp} TIMESTAMP)
    """
    cursor_obj = __connection.cursor()
    cursor_obj.execute(create_table)
    cursor_obj.close()


def migration_11():
    migration_template("12", do_migration_11)


def migration_12():
    migration_template("13", do_migration_12)


def migration_13():
    migration_template("14", do_migration_13)


def migration_14():
    migration_template("15", do_migration_14)


def migration_15():
    migration_template("16", do_migration_15)


def insert_playback(
        played_track_request : PlayedTrackRequest,
        last_played : datetime.datetime):
    play_count : int = 1 if last_played else 0
    # msgproc.log(f"insert_playback [{played_track_request.track_id}] "
    #             f"with play_count [{play_count}] "
    #             f"last_played [{'NOT NULL' if last_played else 'NULL'}]")
    t = (
        played_track_request.track_id,
        played_track_request.album_id,
        played_track_request.album_track_count,
        played_track_request.track_name,
        played_track_request.track_duration,
        played_track_request.track_num,
        played_track_request.volume_num,
        played_track_request.album_num_volumes,
        played_track_request.album_name,
        played_track_request.audio_quality,
        played_track_request.album_artist_name,
        played_track_request.image_url,
        played_track_request.explicit,
        played_track_request.artist_name,
        played_track_request.album_duration,
        played_track_request.bit_depth,
        played_track_request.sample_rate,
        play_count,
        last_played)
    cursor = __connection.cursor()
    cursor.execute("INSERT INTO played_track_v1(track_id, \
                    album_id, \
                    album_track_count, \
                    track_name, \
                    track_duration, \
                    track_num, \
                    volume_num, \
                    album_num_volumes, \
                    album_name, \
                    audio_quality, \
                    album_artist_name, \
                    image_url, \
                    explicit, \
                    artist_name, \
                    album_duration, \
                    bit_depth, \
                    sample_rate, \
                    play_count, \
                    last_played) \
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                t)
    cursor.close()
    __connection.commit()


def update_playback(
        played_track_request : PlayedTrackRequest,
        last_played : datetime.datetime):
    msgproc.log(f"update_playback [{played_track_request.track_id}] "
                f"with last_played [{'NOT NULL' if last_played else 'NULL'}]")
    if last_played:
        t = (
            played_track_request.album_id,
            played_track_request.album_track_count,
            played_track_request.track_name,
            played_track_request.track_duration,
            played_track_request.track_num,
            played_track_request.volume_num,
            played_track_request.album_num_volumes,
            played_track_request.album_name,
            played_track_request.audio_quality,
            played_track_request.album_artist_name,
            played_track_request.image_url,
            played_track_request.explicit,
            played_track_request.artist_name,
            played_track_request.album_duration,
            played_track_request.bit_depth,
            played_track_request.sample_rate,
            played_track_request.track_id,
            last_played,
            played_track_request.track_id)
        cursor = __connection.cursor()
        cursor.execute("UPDATE played_track_v1 set album_id = ?, \
                    album_track_count = ?, \
                    track_name = ?, \
                    track_duration = ?, \
                    track_num = ?, \
                    volume_num = ?, \
                    album_num_volumes = ?, \
                    album_name = ?, \
                    audio_quality = ?, \
                    album_artist_name = ?, \
                    image_url = ?, \
                    explicit = ?, \
                    artist_name = ?, \
                    album_duration = ?, \
                    bit_depth = ?, \
                    sample_rate = ?, \
                    play_count = (SELECT play_count + 1 AS play_count FROM played_track_v1 WHERE track_id = ?), \
                    last_played = ? \
                    WHERE track_id = ?", t)
    else:
        # no playback -> we don't update play count and/or last_played
        t = (
            played_track_request.album_id,
            played_track_request.album_track_count,
            played_track_request.track_name,
            played_track_request.track_duration,
            played_track_request.track_num,
            played_track_request.volume_num,
            played_track_request.album_num_volumes,
            played_track_request.album_name,
            played_track_request.audio_quality,
            played_track_request.album_artist_name,
            played_track_request.image_url,
            played_track_request.explicit,
            played_track_request.artist_name,
            played_track_request.album_duration,
            played_track_request.bit_depth,
            played_track_request.sample_rate,
            played_track_request.track_id)
        cursor = __connection.cursor()
        cursor.execute("UPDATE played_track_v1 set album_id = ?, \
                    album_track_count = ?, \
                    track_name = ?, \
                    track_duration = ?, \
                    track_num = ?, \
                    volume_num = ?, \
                    album_num_volumes = ?, \
                    album_name = ?, \
                    audio_quality = ?, \
                    album_artist_name = ?, \
                    image_url = ?, \
                    explicit = ?, \
                    artist_name = ?, \
                    album_duration = ?, \
                    bit_depth = ?, \
                    sample_rate = ? \
                    WHERE track_id = ?", t)
    cursor.close()
    __connection.commit()


def _get_played_tracks(sorting : PlayedTracksSorting, max_tracks : int) -> list[PlayedTrack]:
    t = (max_tracks, )
    cursor = __connection.cursor()
    query : str = f"SELECT \
            track_id, \
            play_count, \
            last_played, \
            album_id, \
            album_track_count, \
            track_name, \
            track_duration, \
            track_num, \
            volume_num, \
            album_num_volumes, \
            album_name, \
            audio_quality, \
            album_artist_name, \
            image_url, \
            artist_name, \
            explicit, \
            album_duration, \
            bit_depth, \
            sample_rate \
          FROM \
              played_track_v1 \
          WHERE \
              play_count > 0 \
              AND last_played IS NOT null \
          ORDER BY \
              {sorting.get_field_name()} {sorting.get_field_order()} LIMIT ?"
    cursor.execute(
        query,
        t)
    rows = cursor.fetchall()
    cursor.close()
    if not rows: return list()
    played_list : list[PlayedTrack] = list()
    for row in rows:
        played : PlayedTrack = PlayedTrack()
        played.track_id = str(row[0])
        played.play_count = row[1]
        played.last_played = row[2]
        played.album_id = str(row[3])
        played.album_track_count = row[4]
        played.track_name = row[5]
        played.track_duration = row[6]
        played.track_num = row[7]
        played.volume_num = row[8]
        played.album_num_volumes = row[9]
        played.album_name = row[10]
        played.audio_quality = row[11]
        played.album_artist_name = row[12]
        played.image_url = row[13]
        played.artist_name = row[14]
        played.explicit = row[15]
        played.album_duration = row[16]
        played.bit_depth = row[17]
        played.sample_rate = row[18]
        played_list.append(played)
    return played_list


def get_last_played_tracks(max_tracks : int = 100) -> list[PlayedTrack]:
    return _get_played_tracks(
        sorting = PlayedTracksSorting.LAST_PLAYED_FIRST,
        max_tracks = max_tracks)


def get_most_played_tracks(max_tracks : int = 100) -> list[PlayedTrack]:
    return _get_played_tracks(
        sorting = PlayedTracksSorting.MOST_PLAYED_FIRST,
        max_tracks = max_tracks)


def get_played_track_entry(track_id : str) -> PlayedTrack:
    t = (track_id,)
    cursor = __connection.cursor()
    cursor.execute("SELECT \
                   play_count, \
                   last_played, \
                   album_id, \
                   album_track_count, \
                   track_name, \
                   track_duration, \
                   track_num, \
                   volume_num, \
                   album_num_volumes, \
                   album_name, \
                   audio_quality, \
                   album_artist_name, \
                   image_url, \
                   artist_name, \
                   explicit, \
                   album_duration, \
                   bit_depth, \
                   sample_rate \
                FROM played_track_v1 \
                WHERE track_id = ?", t)
    rows = cursor.fetchall()
    cursor.close()
    if not rows: return None
    result : PlayedTrack = PlayedTrack()
    result.track_id = track_id
    result.play_count = rows[0][0]
    result.last_played = rows[0][1]
    result.album_id = str(rows[0][2])
    result.album_track_count = rows[0][3]
    result.track_name = rows[0][4]
    result.track_duration = rows[0][5]
    result.track_num = rows[0][6]
    result.volume_num = rows[0][7]
    result.album_num_volumes = rows[0][8]
    result.album_name = rows[0][9]
    result.audio_quality = rows[0][10]
    result.album_artist_name = rows[0][11]
    result.image_url = rows[0][12]
    result.explicit = rows[0][13]
    result.artist_name = rows[0][14]
    result.album_duration = rows[0][15]
    result.bit_depth = rows[0][16]
    result.sample_rate = rows[0][17]
    return result


def get_played_album_entries(album_id : str) -> list[PlayedTrack]:
    t = (album_id,)
    cursor = __connection.cursor()
    cursor.execute("SELECT \
                   play_count, \
                   last_played, \
                   track_id, \
                   album_track_count, \
                   track_name, \
                   track_duration, \
                   track_num, \
                   volume_num, \
                   album_num_volumes, \
                   album_name, \
                   audio_quality, \
                   album_artist_name, \
                   image_url, \
                   artist_name, \
                   explicit, \
                   album_duration, \
                   bit_depth, \
                   sample_rate \
                FROM played_track_v1 \
                WHERE album_id = ? \
                ORDER BY volume_num, track_num", t)
    rows = cursor.fetchall()
    cursor.close()
    if not rows: return list()
    result : list[PlayedTrack] = list()
    for row in rows:
        played_track : PlayedTrack = PlayedTrack()
        played_track.album_id = album_id
        played_track.play_count = row[0]
        played_track.last_played = row[1]
        played_track.track_id = str(row[2])
        played_track.album_track_count = row[3]
        played_track.track_name = row[4]
        played_track.track_duration = row[5]
        played_track.track_num = row[6]
        played_track.volume_num = row[7]
        played_track.album_num_volumes = row[8]
        played_track.album_name = row[9]
        played_track.audio_quality = row[10]
        played_track.album_artist_name = row[11]
        played_track.image_url = row[12]
        played_track.explicit = row[13]
        played_track.artist_name = row[14]
        played_track.album_duration = row[15]
        played_track.bit_depth = row[16]
        played_track.sample_rate = row[17]
        result.append(played_track)
    return result


def track_has_been_played(track_id : str) -> bool:
    return get_played_track_entry(track_id) is not None


def album_has_been_played(album_id : str) -> bool:
    t = (album_id,)
    cursor = __connection.cursor()
    cursor.execute("SELECT album_id, COUNT(album_id) \
                FROM played_track_v1 \
                WHERE \
                    album_id = ? AND \
                    play_count > 0 \
                GROUP BY album_id", t)
    rows = cursor.fetchall()
    cursor.close()
    return rows and len(rows) == 1 and int(rows[0][1]) > 0


def remove_album_from_played_tracks(album_id : str):
    t = (album_id,)
    cursor = __connection.cursor()
    cursor.execute(
        "UPDATE played_track_v1 SET play_count = 0, last_played = NULL WHERE album_id = ?",
        t)
    cursor.close()
    __connection.commit()


def purge_album_from_played_tracks(album_id : str):
    return __purge_album_from_table(album_id, __table_name_played_track_v1)


def purge_album_from_metadata_cache(album_id : str):
    return __purge_album_from_table(album_id, __table_name_album_metadata_cache_v1)


def __purge_album_from_table(album_id : str, table_name):
    t = (album_id,)
    cursor = __connection.cursor()
    cursor.execute(f"DELETE FROM {table_name} "
                   f"WHERE {__field_name_album_id} = ?",
        t)
    cursor.close()
    __connection.commit()


def remove_track_from_played_tracks(track_id : str):
    t = (track_id,)
    cursor = __connection.cursor()
    cursor.execute(
        "UPDATE played_track_v1 SET play_count = 0, last_played = NULL WHERE track_id = ?",
        t)
    cursor.close()
    __connection.commit()


def is_album_in_played_tracks(
        album_id: str) -> bool:
    return __is_album_id_in_table(album_id, __table_name_played_track_v1)


def is_album_in_metadata_cache(
        album_id: str) -> bool:
    return __is_album_id_in_table(album_id, __table_name_album_metadata_cache_v1)


def __is_album_id_in_table(
        album_id: str,
        table_name: str) -> bool:
    t = (album_id, )
    cursor = __connection.cursor()
    cursor.execute(
        f"SELECT * \
          FROM {table_name} \
          WHERE {__field_name_album_id} = ?",
        t)
    rows = cursor.fetchall()
    cursor.close()
    if not rows: return False
    return True


def get_most_played_albums(max_albums : int = 100) -> list[PlayedAlbum]:
    cursor = __connection.cursor()
    cursor.execute(f"{__most_played_albums_query} LIMIT {max_albums}")
    rows = cursor.fetchall()
    cursor.close()
    result : list[PlayedAlbum] = list()
    if not rows: return result
    for row in rows:
        played : PlayedAlbum = PlayedAlbum()
        played.album_id = row[0]
        played.album_played_counter = row[1]
        result.append(played)
    return result


# this will track the collected required information to the
# played_tracks_v1 table but last_playback and play_count
# are left as they are
def track_ghost_playback(played_track_request : PlayedTrackRequest):
    if not track_has_been_played(track_id = played_track_request.track_id):
        insert_playback(
            played_track_request = played_track_request,
            last_played = None)


def track_playback(played_track_request : PlayedTrackRequest):
    now : datetime.datetime = datetime.datetime.now()
    # we try inserting first
    track_action : str = "insert"
    try:
        insert_playback(
            played_track_request = played_track_request,
            last_played = now)
    except sqlite3.IntegrityError:
        track_action : str = "update"
        update_playback(
            played_track_request = played_track_request,
            last_played = now)
    msgproc.log(f"Track playback for {played_track_request.track_id} completed [{track_action}].")


def __is_in_listen_queue(
        obj_id : str,
        key_field_name : str,
        table_name : str) -> bool:
    t = (obj_id, )
    cursor = __connection.cursor()
    cursor.execute(
        f"SELECT {key_field_name} \
          FROM {table_name} \
          WHERE {key_field_name} = ?",
        t)
    rows = cursor.fetchall()
    cursor.close()
    if not rows: return False
    if len(rows) > 1:
        raise Exception(f"Multiple {table_name} records for id [{obj_id}]")
    # only one record, yes, it's in listen queue
    return True


def is_in_track_listen_queue(track_id : str) -> bool:
    return __is_in_listen_queue(
        obj_id=track_id,
        key_field_name=__field_name_track_id,
        table_name=__table_name_listen_track_queue_v1)


def is_in_album_listen_queue(album_id : str) -> bool:
    return __is_in_listen_queue(
        obj_id=album_id,
        key_field_name=__field_name_album_id,
        table_name=__table_name_listen_album_queue_v1)


def is_in_artist_listen_queue(artist_id : str) -> bool:
    return __is_in_listen_queue(
        obj_id=artist_id,
        key_field_name=__field_name_artist_id,
        table_name=__table_name_listen_artist_queue_v1)


def __get_listen_queue(
        table_name : str,
        key_field_name : str) -> list[str]:
    cursor = __connection.cursor()
    cursor.execute(
        f"SELECT {key_field_name} \
          FROM {table_name} \
          ORDER BY {__field_name_created_timestamp}")
    rows = cursor.fetchall()
    cursor.close()
    result : list[str] = list()
    for row in rows if rows else list():
        id : str = row[0]
        result.append(id)
    return result


def get_album_listen_queue() -> list[str]:
    return __get_listen_queue(
        table_name=__table_name_listen_album_queue_v1,
        key_field_name=__field_name_album_id)


def get_artist_listen_queue() -> list[str]:
    return __get_listen_queue(
        table_name=__table_name_listen_artist_queue_v1,
        key_field_name=__field_name_artist_id)


def get_track_listen_queue() -> list[str]:
    return __get_listen_queue(
        table_name=__table_name_listen_track_queue_v1,
        key_field_name=__field_name_track_id)


def __add_to_listen_queue(
        obj_id : str,
        table_name : str,
        key_field_name : str) -> bool:
    if not __is_in_listen_queue(
            obj_id=obj_id,
            key_field_name=key_field_name,
            table_name=table_name):
        now : datetime.datetime = datetime.datetime.now()
        t = (obj_id, now)
        cursor = __connection.cursor()
        cursor.execute(
            f"""INSERT INTO {table_name}(
                {key_field_name},
                {__field_name_created_timestamp})
                VALUES(?, ?)""",
            t)
        cursor.close()
        __connection.commit()
        return True
    # already there
    msgproc.log(f"Object [{obj_id}] is already in {table_name}")
    return False


def add_to_album_listen_queue(album_id : str) -> bool:
    return __add_to_listen_queue(
        obj_id=album_id,
        table_name=__table_name_listen_album_queue_v1,
        key_field_name=__field_name_album_id)


def add_to_artist_listen_queue(artist_id : str) -> bool:
    return __add_to_listen_queue(
        obj_id=artist_id,
        table_name=__table_name_listen_artist_queue_v1,
        key_field_name=__field_name_artist_id)


def add_to_track_listen_queue(track_id : str) -> bool:
    return __add_to_listen_queue(
        obj_id=track_id,
        table_name=__table_name_listen_track_queue_v1,
        key_field_name=__field_name_track_id)


def __remove_from_listen_queue(
        obj_id : str,
        table_name : str,
        key_field_name : str) -> bool:
    if __is_in_listen_queue(
            obj_id=obj_id,
            table_name=table_name,
            key_field_name=key_field_name):
        t = (obj_id, )
        cursor = __connection.cursor()
        cursor.execute(
            f"""DELETE FROM {table_name}
                WHERE {key_field_name} = ?""",
            t)
        cursor.close()
        __connection.commit()
        return True
    # not there!
    msgproc.log(f"Object [{obj_id}] is not in {table_name}")
    return False


def remove_from_album_listen_queue(album_id : str) -> bool:
    return __remove_from_listen_queue(
        obj_id=album_id,
        table_name=__table_name_listen_album_queue_v1,
        key_field_name=__field_name_album_id)


def remove_from_artist_listen_queue(artist_id : str) -> bool:
    return __remove_from_listen_queue(
        obj_id=artist_id,
        table_name=__table_name_listen_artist_queue_v1,
        key_field_name=__field_name_artist_id)


def remove_from_track_listen_queue(track_id : str) -> bool:
    return __remove_from_listen_queue(
        obj_id=track_id,
        table_name=__table_name_listen_track_queue_v1,
        key_field_name=__field_name_track_id)


def get_album_metadata(album_id : str) -> AlbumMetadata:
    t = (album_id, )
    cursor = __connection.cursor()
    cursor.execute(f"""
            SELECT
                {__field_name_album_id},
                {__field_name_name},
                {__field_name_artist_id},
                {__field_name_artist_name},
                {__field_name_explicit},
                {__field_name_release_date},
                {__field_name_available_release_date},
                {__field_name_image_url},
                {__field_name_audio_modes},
                {__field_name_audio_quality},
                {__field_name_media_metadata_tags},
                {__field_name_created_timestamp}
            FROM
                {__table_name_album_metadata_cache_v1}
            WHERE {__field_name_album_id} = ?""",
        t)
    rows = cursor.fetchall()
    cursor.close()
    if not rows: return None
    if len(rows) > 1:
        raise Exception(f"Multiple {__table_name_album_metadata_cache_v1} records for [{album_id}]")
    row = rows[0]
    result : AlbumMetadata = AlbumMetadata()
    result.album_id = row[0]
    result.album_name = row[1]
    result.artist_id = row[2]
    result.artist_name = row[3]
    result.explicit = row[4]
    result.release_date = row[5]
    result.available_release_date = row[6]
    result.image_url = row[7]
    result.audio_modes = row[8]
    result.audio_quality = row[9]
    result.media_metadata_tags = row[10]
    result.created_timestamp = row[11]
    return result


def __insert_album_metadata(album : AlbumMetadata, commit : bool = False):
    t = (
        album.album_id,
        album.album_name,
        album.artist_id,
        album.artist_name,
        album.explicit,
        album.release_date,
        album.available_release_date,
        album.image_url,
        album.audio_modes,
        album.audio_quality,
        album.media_metadata_tags,
        album.created_timestamp)
    cursor = __connection.cursor()
    cursor.execute(f"""
            INSERT INTO {__table_name_album_metadata_cache_v1}(
                {__field_name_album_id},
                {__field_name_name},
                {__field_name_artist_id},
                {__field_name_artist_name},
                {__field_name_explicit},
                {__field_name_release_date},
                {__field_name_available_release_date},
                {__field_name_image_url},
                {__field_name_audio_modes},
                {__field_name_audio_quality},
                {__field_name_media_metadata_tags},
                {__field_name_created_timestamp}
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
        """,
        t)
    cursor.close()
    if commit: __connection.commit()


def __delete_album_metadata(album_id : str, commit : bool = False):
    t = (album_id, )
    cursor = __connection.cursor()
    cursor.execute(
        f"""DELETE FROM {__table_name_album_metadata_cache_v1}
            WHERE {__field_name_album_id} = ?""",
        t)
    cursor.close()
    if commit: __connection.commit()


def store_album_metadata(album_metadata : AlbumMetadata):
    if get_album_metadata(album_id = album_metadata.album_id):
        # we want to overwrite so we delete first
        __delete_album_metadata(
            album_id=album_metadata.album_id,
            commit=False)
    # now we can always insert
    __insert_album_metadata(
        album=album_metadata,
        commit=True)
    pass


__connection : sqlite3.Connection = __get_connection()
__prepare_table_db_version()

current_db_version : str = get_db_version()


class Migration:

    def __init__(self, migration_name : str, apply_on : str, migration_function : Callable[[], any]):
        self._migration_name : str = migration_name
        self._apply_on : str = apply_on
        self._migration_function : Callable[[], any] = migration_function

    @property
    def migration_name(self) -> str:
        return self._migration_name

    @property
    def apply_on(self) -> int:
        return self._apply_on

    @property
    def migration_function(self) -> Callable[[], any]:
        return self._migration_function


migrations : list[Migration] = [
    Migration(
        migration_name = "initial_creation",
        apply_on = None,
        migration_function = migration_0),
    Migration(
        migration_name = "tile_image_v1",
        apply_on = "1",
        migration_function = migration_1),
    Migration(
        migration_name = "add_album_info_to_played_tracks_v1",
        apply_on = "2",
        migration_function = migration_2),
    Migration(
        migration_name = "add_album_id_index_to_played_tracks_v1",
        apply_on = "3",
        migration_function = migration_3),
    Migration(
        migration_name = "add_update_time_to_tile_image_v1",
        apply_on = "4",
        migration_function = migration_4),
    Migration(
        migration_name = "add_columns_to_played_track_v1",
        apply_on = "5",
        migration_function = migration_5),
    Migration(
        migration_name = "add_explicit_to_played_track_v1",
        apply_on = "6",
        migration_function = migration_6),
    Migration(
        migration_name = "add_artist_name_to_played_track_v1",
        apply_on = "7",
        migration_function = migration_7),
    Migration(
        migration_name = "drop_is_multidisc_album_from_played_track_v1",
        apply_on = "8",
        migration_function = migration_8),
    Migration(
        migration_name = "add_album_duration_to_played_track_v1",
        apply_on = "9",
        migration_function = migration_9),
    Migration(
        migration_name = "add_indexes_to_tile_image_v1",
        apply_on = "10",
        migration_function = migration_10),
    Migration(
        migration_name = "add_bd_and_sr_to_played_track_v1",
        apply_on = "11",
        migration_function = migration_11),
    Migration(
        migration_name = "add_listen_album_queue_v1",
        apply_on = "12",
        migration_function = migration_12),
    Migration(
        migration_name = "add_listen_artist_queue_v1",
        apply_on = "13",
        migration_function = migration_13),
    Migration(
        migration_name = "add_listen_track_queue_v1",
        apply_on = "14",
        migration_function = migration_14),
    Migration(
        migration_name = "add_album_metadata_v1",
        apply_on = "15",
        migration_function = migration_15)]

current_migration : Migration
for current_migration in migrations:
    current_db_version : int = get_db_version()
    if not current_db_version or current_db_version == current_migration.apply_on:
        msgproc.log(f"Migration [{current_migration.migration_name}] "
                    f"is executing on current db version [{current_db_version}] ...")
        current_migration.migration_function()
        msgproc.log(f"Migration [{current_migration.migration_name}] executed.")
    else:
        msgproc.log(f"Migration [{current_migration.migration_name}] skipped.")

migrated_db_version : str = get_db_version()
msgproc.log(f"Current db version is [{migrated_db_version}]")
