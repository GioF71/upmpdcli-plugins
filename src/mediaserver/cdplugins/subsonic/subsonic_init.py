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

import config

from subsonic_connector.response import Response
from subsonic_connector.list_type import ListType
from subsonic_connector.album_list import AlbumList
from subsonic_connector.artist import Artist
from subsonic_connector.album import Album
from subsonic_connector.song import Song
from subsonic_connector.internet_radio_stations import InternetRadioStations
from subsonic_connector.search_result import SearchResult
import metadata_converter
import artist_from_album as artist_from_album
from song_data_structures import SongArtistType
from table_name import TableName
from album_metadata import AlbumMetadata
from metadata_model import AlbumMetadataModel
from typing import Callable
from typing import Any
import subsonic_util
import album_util
import connector_provider
from msgproc_provider import msgproc
import constants
import upmplgutils
import persistence
import sqlite3
import shutil
import time
import datetime
import os
import glob
import pathlib


def get_image_cache_path_for_pruning(www_image_path: list[str]) -> str:
    # check cache dir
    cache_dir: str = upmplgutils.getUpnpWebDocRoot(constants.PluginConstant.PLUGIN_NAME.value)
    if not cache_dir:
        msgproc.log("Cache directory is not set, cannot allow pruning.")
        return None
    candidate: pathlib.Path = pathlib.Path(cache_dir)
    # does the path actually exist?
    if not candidate.exists() or not candidate.is_dir():
        msgproc.log(f"Invalid cache path [{candidate}], cannot allow pruning.")
        return None
    # is the provided argument a valid non-empty list?
    if not www_image_path or not isinstance(www_image_path, list) or len(www_image_path) == 0:
        msgproc.log("www_image_path is not a valid list, cannot allow pruning.")
        return None
    return subsonic_util.ensure_directory(
        upmplgutils.getUpnpWebDocRoot(constants.PluginConstant.PLUGIN_NAME.value),
        www_image_path)


def prune_cache(images_static_dir: str):
    now: float = time.time()
    # list directories
    file_count: int = 0
    deleted_count: int = 0
    max_age_seconds: int = config.get_config_param_as_int(constants.ConfigParam.CACHED_IMAGE_MAX_AGE_DAYS) * (24 * 60 * 60)
    for filename in glob.glob(f"{images_static_dir}/**/*", recursive=True):
        filename_path = os.path.normpath(filename)
        file_count += 1
        time_diff_sec: float = now - os.path.getmtime(filename_path)
        if time_diff_sec >= float(max_age_seconds):
            os.remove(filename_path)
            deleted_count += 1
    msgproc.log(f"Deleted [{deleted_count}] cached images out of [{file_count}]")


def subsonic_init():
    msgproc.log(f"Subsonic [{constants.PluginConstant.PLUGIN_RELEASE.value}] Initializing ...")
    init_success: bool = False
    try:
        cache_dir: str = upmplgutils.getcachedir(constants.PluginConstant.PLUGIN_NAME.value)
        msgproc.log(f"Cache dir for [{constants.PluginConstant.PLUGIN_NAME.value}] is "
                    f"[{cache_dir}]")
        msgproc.log(f"DB version for [{constants.PluginConstant.PLUGIN_NAME.value}] is "
                    f"[{persistence.get_db_version()}]")
        persistence.purge_spurious_caches()
        purge_id_cache()
        initial_caching()
        check_supports()
        detect_anomalies()
        if config.get_config_param_as_bool(constants.ConfigParam.EXECUTE_VACUUM):
            persistence.do_vacuum()
        if config.getWebServerDocumentRoot():
            msgproc.log("WebServer is enabled ...")
            path_images_static: list[str] = config.get_webserver_path_images_static()
            images_static_dir: str = subsonic_util.ensure_directory(
                config.getWebServerDocumentRoot(),
                path_images_static)
            msgproc.log(f"Directory for static images [{images_static_dir}] created.")
            path_images_subsonic: list[str] = config.get_webserver_path_images_cache()
            images_cached_dir: str = subsonic_util.ensure_directory(
                config.getWebServerDocumentRoot(),
                path_images_subsonic)
            msgproc.log(f"Directory for cached images [{images_cached_dir}] created.")
            pkg_datadir: str = upmplgutils.getOptionValue('pkgdatadir')
            msgproc.log(f"pkg_datadir: [{pkg_datadir}]")
            src_path: str = (f"{pkg_datadir}/cdplugins/{constants.PluginConstant.PLUGIN_NAME.value}")
            src_static_images_path: str = f"{src_path}/images/static"
            for img in ["unknown-artist.svg", "unknown-cover.svg"]:
                shutil.copyfile(f"{src_static_images_path}/{img}",
                                f"{images_static_dir}/{img}")
        else:
            msgproc.log("WebServer not available")
        init_success = True
    except Exception as e:
        msgproc.log(f"Subsonic [{constants.PluginConstant.PLUGIN_RELEASE.value}] "
                    f"Initialization failed [{e}]")
    if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_CACHED_IMAGE_AGE_LIMIT):
        prune_path: str = get_image_cache_path_for_pruning(config.get_webserver_path_images_cache())
        if prune_path:
            msgproc.log(f"Pruning image cache at path [{prune_path}] ...")
            prune_cache(images_static_dir=prune_path)
            msgproc.log(f"Pruned image cache at path [{prune_path}].")
    else:
        msgproc.log("Image pruning disabled.")
    msgproc.log(f"Subsonic [{constants.PluginConstant.PLUGIN_RELEASE.value}] "
                f"Initialization success: [{init_success}]")


def detect_anomalies():
    # detect_multiple_artists()
    pass


def check_supports():
    check_supports_highest()
    check_supports_internet_radios()


def check_supports_highest():
    # see if there is support for highest in getAlbumLists2
    supported: bool = False
    try:
        res: Response[AlbumList] = connector_provider.get().getAlbumList(ltype=ListType.HIGHEST, size=1)
        if res and res.isOk():
            # supported!
            supported = True
    except Exception as ex:
        msgproc.log(f"check_supports_highest highest not supported [{type(ex)}] [{ex}]")
    msgproc.log(f"highest type in getAlbumList supported: [{'yes' if supported else 'no'}]")
    if not supported:
        config.album_list_by_highest_supported = False


def check_supports_internet_radios():
    # see if there is support for highest in getAlbumLists2
    supported: bool = False
    try:
        res: Response[InternetRadioStations] = connector_provider.get().getInternetRadioStations()
        if res and res.isOk():
            # supported!
            supported = True
    except Exception as ex:
        msgproc.log(f"check_supports_highest highest not supported [{type(ex)}] [{ex}]")
    msgproc.log(f"Internet Radio stations supported: [{'yes' if supported else 'no'}]")
    if not supported:
        config.internet_radio_stations_supported = False


def wrap_action_with_connection(action: Callable[[sqlite3.Connection], Any], context: str):
    connection: sqlite3.Connection = persistence.get_working_connection(provided=None)
    res: Any = None
    try:
        res = action(connection)
    except Exception as ex:
        msgproc.log(f"{context} failed [{type(ex)}] [{ex}]")
        # don't commit
        connection.rollback()
        connection.close()
    persistence.commit(connection)
    connection.close()
    return res


class PreloadedAlbum:

    def __init__(
            self,
            album_id: str,
            song_count: int):
        self.__album_id: str = album_id
        self.__song_count: int = song_count

    @property
    def album_id(self) -> str:
        return self.__album_id

    @property
    def song_count(self) -> int:
        return self.__song_count


class PreloadAlbumsResult:

    def __init__(self):
        self.__albums: dict[str, PreloadedAlbum] = {}

    def add_album(self, album: PreloadedAlbum):
        self.__albums[album.album_id] = album

    def get_album(self, album_id: str) -> PreloadedAlbum | None:
        return self.__albums[album_id] if album_id in self.__albums else None

    @property
    def album_count(self) -> int:
        return len(self.__albums)


def get_loaded_song_list(loaded_by_album_id: dict[str, list[Song]], album_id: str) -> list[Song]:
    existing: list[Song] = loaded_by_album_id[album_id] if album_id in loaded_by_album_id else None
    if existing is None:
        existing = []
        loaded_by_album_id[album_id] = existing
    return existing


def preload_songs(connection: sqlite3.Connection, preload_albums_result: PreloadAlbumsResult):
    msgproc.log("preload_songs starting ...")
    verbose_logging: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    preload_verbose_logging: bool = (verbose_logging and
                                     config.get_config_param_as_bool(constants.ConfigParam.PRELOAD_VERBOSE_LOGGING))
    start: float = time.time()
    preload_start: datetime.datetime = datetime.datetime.now()
    song_offset: int = 0
    total_stored: int = 0
    req_count: int = constants.Defaults.SUBSONIC_API_MAX_RETURN_SIZE.value
    insert_count: int = 0
    update_count: int = 0
    skip_count: int = 0
    album_id_set: set[str] = set()
    missing_album_id_set: set[str] = set()
    save_mode: persistence.SaveMode
    loaded_by_album_id: dict[str, list[Song]] = {}
    song_count_by_album_id: dict[str, int] = {}
    while True:
        res: SearchResult = connector_provider.get().search(
            query="",
            songCount=req_count,
            songOffset=song_offset,
            artistCount=0,
            albumCount=0)
        retrieved: int = len(res.getSongs())
        song: Song
        partial_insert_count: int = 0
        partial_update_count: int = 0
        partial_skip_count: int = 0
        cnt: int = 0
        for song in res.getSongs():
            album_exists: bool = song.getAlbumId() in album_id_set
            if not album_exists:
                if not song.getAlbumId() in missing_album_id_set:
                    # try loading.
                    album_md: AlbumMetadata = persistence.get_album_metadata(
                        album_id=song.getAlbumId(),
                        connection=connection)
                    if album_md:
                        album_id_set.add(song.getAlbumId())
                        album_exists = True
                    else:
                        missing_album_id_set.add(song.getAlbumId())
            cnt += 1
            if not album_exists:
                msgproc.log(f"Skipping song [{song.getId()}] (missing album [{song.getAlbumId()}])")
                partial_skip_count += 1
                continue
            if preload_verbose_logging:
                msgproc.log(f"preload_songs for [{song.getId()}] "
                            f"[{cnt}] of [{retrieved}] ([{cnt + song_offset}])...")
            try:
                _, save_mode = persistence.save_song_metadata(
                    song_metadata=metadata_converter.build_song_metadata(song=song),
                    context="preload",
                    connection=connection,
                    do_commit=False)
            except Exception as ex:
                msgproc.log(f"preload_songs error while saving song_id [{song.getId()}] [{type(ex)}] [{ex}]")
            if preload_verbose_logging:
                msgproc.log(f"preload_songs saved song_id [{song.getId()}] as [{save_mode}]")
            if save_mode == persistence.SaveMode.INSERTED:
                partial_insert_count += 1
            elif save_mode == persistence.SaveMode.UPDATED:
                partial_update_count += 1
            else:
                raise Exception(f"Invalid mode [{save_mode}]")
            persistence.save_song_album_artist_list(
                song_id=song.getId(),
                album_id=song.getAlbumId(),
                song_album_artist_list=subsonic_util.get_song_artists_by_type(
                    song=song,
                    song_artist_type=SongArtistType.SONG_ALBUM_ARTIST),
                connection=connection,
                do_commit=False)
            persistence.save_song_artist_list(
                song_id=song.getId(),
                album_id=song.getAlbumId(),
                song_artist_list=subsonic_util.get_song_artists_by_type(
                    song=song,
                    song_artist_type=SongArtistType.SONG_ARTIST),
                connection=connection,
                do_commit=False)
            persistence.save_song_contributor_list(
                song_id=song.getId(),
                album_id=song.getAlbumId(),
                song_contributor_list=subsonic_util.get_song_contributors(song=song),
                connection=connection,
                do_commit=False)
            loaded_list: list[Song] = get_loaded_song_list(loaded_by_album_id=loaded_by_album_id, album_id=song.getAlbumId())
            loaded_list.append(song)
            curr_album_song_count: int = (song_count_by_album_id[song.getAlbumId()] + 1
                                          if song.getAlbumId() in song_count_by_album_id else 1)
            song_count_by_album_id[song.getAlbumId()] = curr_album_song_count
            preloaded_album: PreloadedAlbum = (preload_albums_result.get_album(song.getAlbumId())
                                               if preload_albums_result else None)
            if preloaded_album and preloaded_album.song_count == curr_album_song_count:
                # song count for album complete, actions?
                album_properties: dict[str, list[Any]] = subsonic_util.build_album_properties_from_songs(song_list=loaded_list)
                persistence.save_album_properties(
                    album_id=song.getAlbumId(),
                    properties=album_properties,
                    connection=connection,
                    do_commit=False)
                # update album metadata?
                upd_dict: dict[AlbumMetadataModel, Any] = subsonic_util.convert_album_properties(album_properties=album_properties)
                album_path: str = album_util.get_album_path_list_joined(song_list=loaded_list)
                upd_dict[AlbumMetadataModel.ALBUM_PATH] = album_path
                if len(upd_dict) > 0:
                    persistence.update_album_metadata_table(
                        album_id=song.getAlbumId(),
                        values=upd_dict,
                        connection=connection,
                        do_commit=False)
                # purge from loaded_by_album_id
                del loaded_by_album_id[song.getAlbumId()]
        total_stored += retrieved
        insert_count += partial_insert_count
        update_count += partial_update_count
        skip_count += partial_skip_count
        msgproc.log(f"preload_songs stored [{retrieved}] "
                    f"i:[{partial_insert_count}] "
                    f"u:[{partial_update_count}] "
                    f"s:[{partial_skip_count}] "
                    f"(tot [{total_stored}] "
                    f"i:[{insert_count}] "
                    f"u:[{update_count}] "
                    f"s:[{skip_count}])")
        if (retrieved < req_count):
            # finished.
            break
        song_offset += retrieved
    # get count after loading entries
    count_before_prune: int = persistence.get_table_count(
        table_name=TableName.ALBUM_METADATA_V1,
        connection=connection)
    prune_count: int = persistence.prune_song_metadata(
        update_timestamp=preload_start,
        connection=connection,
        do_commit=False)
    elapsed: float = time.time() - start
    per_sec: float = float(total_stored) / elapsed
    msgproc.log(f"preload_songs loaded [{total_stored}] "
                f"count_before_prune [{count_before_prune}] "
                f"pruned [{prune_count}] "
                f"in [{elapsed:.3f}] "
                f"[{per_sec:.3f}] songs/sec")


def preload_albums(connection: sqlite3.Connection) -> PreloadAlbumsResult:
    msgproc.log("preload_albums starting ...")
    result: PreloadAlbumsResult = PreloadAlbumsResult()
    verbose_logging: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    preload_verbose_logging: bool = (verbose_logging and
                                     config.get_config_param_as_bool(constants.ConfigParam.PRELOAD_VERBOSE_LOGGING))
    start: float = time.time()
    preload_start: datetime.datetime = datetime.datetime.now()
    album_offset: int = 0
    total_stored: int = 0
    req_count: int = constants.Defaults.SUBSONIC_API_MAX_RETURN_SIZE.value
    insert_count: int = 0
    update_count: int = 0
    save_mode: persistence.SaveMode
    while True:
        res: SearchResult = connector_provider.get().search(
            query="",
            albumCount=req_count,
            albumOffset=album_offset,
            artistCount=0,
            songCount=0)
        retrieved: int = len(res.getAlbums())
        album: Album
        partial_insert_count: int = 0
        partial_update_count: int = 0
        cnt: int = 0
        for album in res.getAlbums():
            cnt += 1
            if preload_verbose_logging:
                msgproc.log(f"preload_albums for [{album.getId()}] "
                            f"[{cnt}] of [{retrieved}] ([{cnt + album_offset}])...")
            has_album_artist: bool = album.getItem().getListByName(constants.ItemKey.ALBUM_ARTISTS.value)
            if has_album_artist:
                msgproc.log(f"preload_albums WARNING album [{album.getId()}] "
                            f"has [{constants.ItemKey.ALBUM_ARTISTS.value}] unexpectedly")
            try:
                _, save_mode = persistence.save_album_metadata(
                    album_metadata=metadata_converter.build_album_metadata(album=album),
                    context="preload",
                    connection=connection,
                    do_commit=False)
            except Exception as ex:
                msgproc.log(f"preload_albums error while saving album_id [{album.getId()}] [{type(ex)}] [{ex}]")
            if save_mode == persistence.SaveMode.INSERTED:
                partial_insert_count += 1
            elif save_mode == persistence.SaveMode.UPDATED:
                partial_update_count += 1
            else:
                raise Exception(f"Invalid mode [{save_mode}]")
            # save properties
            persistence.save_album_properties(
                album_id=album.getId(),
                properties=subsonic_util.build_album_properties(album=album),
                connection=connection,
                do_commit=False)
            # update album artists
            album_artist_list: list[artist_from_album.ArtistFromAlbum] = subsonic_util.get_artists_from_album(album=album)
            aar: int = persistence.update_album_artists(
                    album_id=album.getId(),
                    album_artists=album_artist_list,
                    connection=connection,
                    do_commit=False)
            # update album discs
            album_discs: list[subsonic_util.DiscTitle] = subsonic_util.get_disc_titles_from_album(album=album)
            ad: int = persistence.update_album_discs(
                album_id=album.getId(),
                album_discs=album_discs,
                connection=connection,
                do_commit=False)
            # genres
            album_genres: list[str] = subsonic_util.get_genres_from_album(album=album)
            ag: int = persistence.update_album_genres(
                    album_id=album.getId(),
                    album_genres=album_genres,
                    connection=connection,
                    do_commit=False)
            # record_labels
            album_record_labels: list[str] = subsonic_util.get_album_record_label_names(album=album)
            arl: int = persistence.update_album_record_labels(
                album_id=album.getId(),
                album_record_labels=album_record_labels,
                connection=connection,
                do_commit=False)
            # moods
            album_moods: list[str] = subsonic_util.get_album_moods(album=album)
            am: int = persistence.update_album_moods(
                album_id=album.getId(),
                album_moods=album_moods,
                connection=connection,
                do_commit=False)
            # release_types
            release_types: list[str] = subsonic_util.get_album_release_types(album=album).types
            art: int = persistence.update_album_release_types(
                album_id=album.getId(),
                album_release_types=release_types,
                connection=connection,
                do_commit=False)
            result.add_album(album=PreloadedAlbum(album_id=album.getId(), song_count=album.getSongCount()))
            if preload_verbose_logging:
                msgproc.log(f"preload_albums saved album_id [{album.getId()}] as [{save_mode}] "
                            f"artists [{aar}] "
                            f"discs [{ad}] "
                            f"genres [{ag}] "
                            f"record labels [{arl}] "
                            f"moods [{am}] "
                            f"release types [{art}]")
        total_stored += retrieved
        insert_count += partial_insert_count
        update_count += partial_update_count
        msgproc.log(f"preload_albums stored [{retrieved}] "
                    f"ins [{partial_insert_count}] "
                    f"upd [{partial_update_count}] "
                    f"(total [{total_stored}] "
                    f"ins [{insert_count}] "
                    f"upd [{update_count}])")
        if (retrieved < req_count):
            # finished.
            break
        album_offset += retrieved
    # get count after loading entries
    count_before_prune: int = persistence.get_table_count(
        table_name=TableName.ALBUM_METADATA_V1,
        connection=connection)
    # prune
    prune_count: int = persistence.prune_album_metadata(
        update_timestamp=preload_start,
        connection=connection,
        do_commit=False)
    elapsed: float = time.time() - start
    per_sec: float = float(total_stored) / elapsed
    msgproc.log(f"preload_albums loaded [{total_stored}] "
                f"count_before_prune [{count_before_prune}] "
                f"pruned [{prune_count}] "
                f"in [{elapsed:.3f}] "
                f"[{per_sec:.3f}] albums/sec")
    return result


def preload_artists(connection: sqlite3.Connection):
    msgproc.log("preload_artists starting ...")
    start: float = time.time()
    preload_start: datetime.datetime = datetime.datetime.now()
    msgproc.log("preload_artists connection created ...")
    artist_offset: int = 0
    total_stored: int = 0
    req_count: int = constants.Defaults.SUBSONIC_API_MAX_RETURN_SIZE.value
    while True:
        res: SearchResult = connector_provider.get().search(
            query="",
            artistCount=req_count,
            artistOffset=artist_offset,
            albumCount=0,
            songCount=0)
        retrieved: int = len(res.getArtists())
        artist: Artist
        for artist in res.getArtists():
            artist_roles: list[str] = subsonic_util.get_artist_roles(artist=artist)
            artist_metadata: persistence.ArtistMetadata = metadata_converter.build_artist_metadata(artist=artist)
            persistence.save_artist_metadata(
                artist_metadata=artist_metadata,
                connection=connection,
                do_commit=False)
            persistence.update_artist_roles(
                artist_id=artist.getId(),
                artist_roles=artist_roles,
                connection=connection,
                do_commit=False)
        total_stored += retrieved
        msgproc.log(f"preload_artists stored [{retrieved}] (total [{total_stored}])")
        if (retrieved < req_count):
            # finished.
            break
        artist_offset += retrieved
    # prune
    prune_count: int = persistence.prune_artist_metadata(
        update_timestamp=preload_start,
        connection=connection,
        do_commit=False)
    elapsed: float = time.time() - start
    per_sec: float = float(total_stored) / elapsed
    msgproc.log(f"preload_artists loaded [{total_stored}] "
                f"pruned [{prune_count}] "
                f"in [{elapsed:.3f}] "
                f"[{per_sec:.3f}] artists/sec")


def initial_caching():
    preload_success: bool = True
    preload_start: float = time.time()
    initial_caching_start: datetime.datetime = datetime.datetime.fromtimestamp(preload_start)
    preload_max_delta_sec: int = config.get_config_param_as_int(constants.ConfigParam.PRELOAD_MAX_DELTA_SEC)
    preload_artists_enabled: bool = config.get_config_param_as_bool(constants.ConfigParam.PRELOAD_ARTISTS)
    preload_albums_enabled: bool = preload_artists_enabled and config.get_config_param_as_bool(constants.ConfigParam.PRELOAD_ALBUMS)
    preload_songs_enabled: bool = preload_albums_enabled and config.get_config_param_as_bool(constants.ConfigParam.PRELOAD_SONGS)
    msgproc.log(f"initial_caching preload artists [{preload_artists_enabled}] "
                f"preload albums [{preload_albums_enabled}] "
                f"preload songs [{preload_songs_enabled}]")
    if preload_artists_enabled:
        oldest: float | None = persistence.get_oldest_metadata(table_name=TableName.ARTIST_METADATA_V1)
        artist_initial_count: int = persistence.get_table_count(
            table_name=TableName.ARTIST_METADATA_V1)
        msgproc.log(f"initial_caching {TableName.ARTIST_METADATA_V1.value} "
                    f"current count [{artist_initial_count}] "
                    f"oldest [{oldest}]")
        if oldest is None or (initial_caching_start - oldest).total_seconds() > preload_max_delta_sec:
            try:
                wrap_action_with_connection(
                    action=preload_artists,
                    context="preload_artists")
            except Exception as ex:
                msgproc.log(f"preload_artists failed [{type(ex)}] [{ex}]")
        else:
            msgproc.log("initial_caching skipping preload_artists because "
                        f"start - oldest [{(initial_caching_start - oldest).total_seconds()}] <= "
                        f"max_delta [{preload_max_delta_sec}]")
    preload_albums_result: PreloadAlbumsResult = None
    if preload_albums_enabled:
        oldest = persistence.get_oldest_metadata(table_name=TableName.ALBUM_METADATA_V1)
        album_initial_count: int = persistence.get_table_count(table_name=TableName.ALBUM_METADATA_V1)
        msgproc.log(f"initial_caching {TableName.ALBUM_METADATA_V1.value} "
                    f"current count [{album_initial_count}] "
                    f"oldest [{oldest}]")
        if oldest is None or (initial_caching_start - oldest).total_seconds() > preload_max_delta_sec:
            try:
                preload_albums_result = wrap_action_with_connection(
                    action=preload_albums,
                    context="preload_albums")
                preload_success = True
            except Exception as ex:
                msgproc.log(f"preload_albums failed [{type(ex)}] [{ex}]")
        else:
            msgproc.log("initial_caching skipping preload_albums because "
                        f"start - oldest [{(initial_caching_start - oldest).total_seconds()}] <= "
                        f"max_delta [{preload_max_delta_sec}]")
    if preload_songs_enabled:
        msgproc.log(f"Preloaded [{preload_albums_result.album_count if preload_albums_result else 0}] albums, "
                    "starting song preload")
        oldest = persistence.get_oldest_metadata(table_name=TableName.SONG_METADATA_V1)
        song_initial_count: int = persistence.get_table_count(table_name=TableName.SONG_METADATA_V1)
        msgproc.log(f"initial_caching {TableName.SONG_METADATA_V1.value} "
                    f"current count [{song_initial_count}] "
                    f"oldest [{oldest}]")
        if oldest is None or (initial_caching_start - oldest).total_seconds() > preload_max_delta_sec:
            try:
                wrap_action_with_connection(
                    action=lambda x: preload_songs(x, preload_albums_result),
                    context="preload_songs")
            except Exception as ex:
                msgproc.log(f"preload_songs failed [{type(ex)}] [{ex}]")
        else:
            msgproc.log("initial_caching skipping preload_songs because "
                        f"start - oldest [{(initial_caching_start - oldest).total_seconds()}] <= "
                        f"max_delta [{preload_max_delta_sec}]")
    preload_elapsed: float = time.time() - preload_start
    if preload_artists_enabled or preload_albums_enabled or preload_songs_enabled:
        msgproc.log(f"initial_caching completed with success [{preload_success}] "
                    f"in [{preload_elapsed:.3f}]")


def purge_id_cache():
    if config.get_config_param_as_bool(constants.ConfigParam.PURGE_IDENTIFIER_CACHE):
        persistence.purge_id_cache()
