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

import config
import request_cache

from subsonic_connector.response import Response
from subsonic_connector.list_type import ListType
from subsonic_connector.artist_list_item import ArtistListItem
from subsonic_connector.album_list import AlbumList
from subsonic_connector.artists_initial import ArtistsInitial
from subsonic_connector.artists import Artists
from subsonic_connector.internet_radio_stations import InternetRadioStations

import subsonic_util

import connector_provider
from msgproc_provider import msgproc

import constants
import upmplgutils
import persistence

import shutil
import time
import os
import glob


def get_webserver_path_cache_images() -> list[str]:
    return [
        constants.PluginConstant.PLUGIN_NAME.value,
        "images",
        "cache"]


def prune_cache():
    if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_CACHED_IMAGE_AGE_LIMIT):
        path_for_cache_images: list[str] = get_webserver_path_cache_images()
        images_static_dir: str = subsonic_util.ensure_directory(
            upmplgutils.getUpnpWebDocRoot(constants.PluginConstant.PLUGIN_NAME.value),
            path_for_cache_images)
        now: float = time.time()
        # list directories
        file_count: int = 0
        deleted_count: int = 0
        max_age_seconds: int = config.get_config_param_as_int(constants.ConfigParam.CACHED_IMAGES_MAX_AGE_DAYS) * (24 * 60 * 60)
        for filename in glob.glob(f"{images_static_dir}/**/*", recursive=True):
            filename_path = os.path.normpath(filename)
            file_count += 1
            time_diff_sec: float = now - os.path.getmtime(filename_path)
            # msgproc.log(f"Found file: timediff [{time_diff_sec:.2f}] [{filename}]")
            if time_diff_sec >= float(max_age_seconds):
                # msgproc.log(f"Deleting file [{filename}] which is older than "
                #             f"[{config.get_config_param_as_int(constants.ConfigParam.CACHED_IMAGES_MAX_AGE_DAYS)}] days")
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
        initial_caching()
        check_supports()
        detect_anomalies()
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
    msgproc.log("Pruning image cache ...")
    prune_cache()
    msgproc.log("Pruned image cache.")
    msgproc.log(f"Subsonic [{constants.PluginConstant.PLUGIN_RELEASE.value}] "
                f"Initialization success: [{init_success}]")


def detect_anomalies():
    # detect_multiple_artists()
    pass


class ArtistOccurrence:
    artist_id: str
    mb_id: str
    artist_name: str


def detect_multiple_artists():
    res: Response[Artists] = request_cache.get_artists()
    initial_list: list[ArtistsInitial] = res.getObj().getArtistListInitials() if res and res.isOk() else None
    if initial_list is None:
        msgproc.log(f"No [{ArtistsInitial.__name__}]")
        return
    artist_dict: dict[str, list[ArtistOccurrence]] = dict()
    curr_initial: ArtistsInitial
    for curr_initial in initial_list:
        msgproc.log(f"Processing [{ArtistsInitial.__name__}] [{curr_initial.getName()}]")
        ali_list: list[ArtistListItem] = curr_initial.getArtistListItems()
        curr_artist: ArtistListItem
        for curr_artist in ali_list:
            artist_id: str = curr_artist.getId()
            artist_name: str = curr_artist.getName().lower()
            artist_mb_id = subsonic_util.get_artist_musicbrainz_id(curr_artist)
            existing: list[ArtistOccurrence] = artist_dict[artist_name] if artist_name in artist_dict else list()
            # there must not be artist_id duplicates!
            if artist_id in existing:
                raise Exception(f"Multiple artist_id [{artist_id}]")
            occ: ArtistOccurrence = ArtistOccurrence()
            occ.artist_id = artist_id
            occ.artist_name = artist_name
            occ.mb_id = artist_mb_id
            existing.append(occ)
            artist_dict[artist_name] = existing
    # count by name
    k: str
    v_occ_list: list[ArtistOccurrence]
    for k, v_occ_list in artist_dict.items():
        if len(v_occ_list) > 1:
            msgproc.log(f"Duplicate artists for artist_name:[{k}]")
            occ: ArtistOccurrence
            for occ in v_occ_list:
                msgproc.log(f"\tartist_id:[{occ.artist_id}] mb_id:[{occ.mb_id}]")


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


def initial_caching():
    pass
