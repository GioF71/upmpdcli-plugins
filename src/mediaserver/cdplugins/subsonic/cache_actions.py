# Copyright (C) 2024,2025 Giovanni Fulco
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

import subsonic_connector.album
import cache_type
import subsonic_connector
import cache_manager_provider
from caching import CacheManager
import subsonic_util
import cmdtalkplugin
import config
import constants

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


def get_album_id_by_artist_id(artist_id: str) -> str:
    return cache_manager_provider.get().get_cached_element(
        cache_name=cache_type.CacheType.ALBUMS_BY_ARTIST.getName(),
        key=artist_id)


def delete_album_by_artist_id(artist_id: str) -> bool:
    return delete_key(cache_type.CacheType.ALBUMS_BY_ARTIST, artist_id)


def delete_key(cache_type: cache_type.CacheType, key: str) -> bool:
    return cache_manager_provider.get().delete_cached_element(cache_type.getName(), key)


def get_album_mb_id(album_id: str) -> str | None:
    return cache_manager_provider.get().get_cached_element(
        cache_name=cache_type.CacheType.MB_ALBUM_ID_BY_ALBUM_ID.getName(),
        key=album_id)


def on_album_for_artist_id(artist_id: str, album: subsonic_connector.album.Album):
    cache_manager: CacheManager = cache_manager_provider.get()
    cache_manager.cache_element_value(
        cache_name=cache_type.CacheType.ALBUMS_BY_ARTIST.getName(),
        key=artist_id,
        value=album.getId())


def on_album(album: subsonic_connector.album.Album):
    if not album or not album.getId():
        return
    cache_manager: CacheManager = cache_manager_provider.get()
    if album.getArtistId():
        cache_manager.cache_element_value(
            cache_name=cache_type.CacheType.ALBUMS_BY_ARTIST.getName(),
            key=album.getArtistId(),
            value=album.getId())

    # musicbrainz album id
    mb_album_id: str = subsonic_util.get_album_musicbrainz_id(album)
    if mb_album_id:
        if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ACTION_ON_MB_ALBUM_CACHE):
            msgproc.log(f"Storing mb_id for [{album.getId()}] -> [{mb_album_id}]")
        cache_manager.cache_element_value(
            cache_name=cache_type.CacheType.MB_ALBUM_ID_BY_ALBUM_ID.getName(),
            key=album.getId(),
            value=mb_album_id)


def get_artist_mb_id(artist_id: str) -> str | None:
    return cache_manager_provider.get().get_cached_element(
        cache_name=cache_type.CacheType.MB_ARTIST_ID_BY_ARTIST_ID.getName(),
        key=artist_id)


def store_artist_mbid(artist_id: str, artist_mb_id: str):
    cache_manager: CacheManager = cache_manager_provider.get()
    cache_manager.cache_element_value(
        cache_name=cache_type.CacheType.MB_ARTIST_ID_BY_ARTIST_ID.getName(),
        key=artist_id,
        value=artist_mb_id)
