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
import config
import constants
import persistence
import album_util
from subsonic_connector.album import Album
from keyvaluecaching import KeyValueItem
from msgproc_provider import msgproc
import time


def get_album_track_qualities_by_album_id(album_id: str) -> str:
    return cache_manager_provider.get().get_cached_element(
        cache_name=cache_type.CacheType.ALBUM_TRACK_QUALITIES.getName(),
        key=album_id)


def save_album_track_qualities(album_id: str, qualities: str):
    cache_manager_provider.get().cache_element_value(
        cache_name=cache_type.CacheType.ALBUM_TRACK_QUALITIES.getName(),
        key=album_id,
        value=qualities)


def get_album_id_by_artist_id(artist_id: str) -> str:
    return cache_manager_provider.get().get_cached_element(
        cache_name=cache_type.CacheType.ALBUMS_BY_ARTIST.getName(),
        key=artist_id)


def delete_album_by_artist_id(artist_id: str) -> bool:
    return delete_key(cache_type.CacheType.ALBUMS_BY_ARTIST, artist_id)


def delete_key(cache_type: cache_type.CacheType, key: str) -> bool:
    return cache_manager_provider.get().delete_cached_element(cache_type.getName(), key)


def store_artist_genres(artist_id: str, album_list: list[Album]):
    if not album_list:
        return
    album: Album
    genre_list: list[str] = []
    for album in album_list if album_list else []:
        album_genres: list[str] = album.getGenres()
        curr_genre: str
        for curr_genre in album_genres if album_genres else []:
            if curr_genre not in genre_list:
                genre_list.append(curr_genre)
    # genre list now available
    genre_list_str: str = constants.Separator.GENRE_FOR_ARTIST_SEPARATOR.value.join(genre_list)
    key_value_item: KeyValueItem = KeyValueItem(
        partition=cache_type.CacheType.GENRES_FOR_ARTIST.cache_name,
        key=artist_id,
        value=genre_list_str)
    persistence.save_kv_item(key_value_item=key_value_item)


def on_album_for_artist_id(artist_id: str, album: subsonic_connector.album.Album):
    cache_manager: CacheManager = cache_manager_provider.get()
    cache_manager.cache_element_value(
        cache_name=cache_type.CacheType.ALBUMS_BY_ARTIST.getName(),
        key=artist_id,
        value=album.getId())


def on_album(album: subsonic_connector.album.Album):
    start: float = time.time()
    __on_album(album=album)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"on_album for album_id [{album.getId()}] executed in [{elapsed:.3f}]")


def __on_album(album: subsonic_connector.album.Album):
    if not album or not album.getId():
        return
    cache_manager: CacheManager = cache_manager_provider.get()
    if album.getArtistId():
        cache_manager.cache_element_value(
            cache_name=cache_type.CacheType.ALBUMS_BY_ARTIST.getName(),
            key=album.getArtistId(),
            value=album.getId())
    artist_id: str = album.getArtistId()
    # musicbrainz album id
    album_mbid: str = subsonic_util.get_album_musicbrainz_id(album)
    album_path_joined: str = album_util.get_album_path_list_joined(album=album)
    if album_mbid or album_path_joined:
        if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ACTION_ON_MB_ALBUM_CACHE):
            msgproc.log(f"Storing album_mbid for [{album.getId()}] -> [{album_mbid}]")
        persistence.save_album_metadata(album_metadata=persistence.AlbumMetadata(
            album_id=album.getId(),
            album_musicbrainz_id=album_mbid,
            album_artist_id=artist_id,
            album_path=album_path_joined))
    # update artist with cover art, if available
    if album.getArtistId() and album.getCoverArt():
        artist_metadata: persistence.ArtistMetadata = persistence.get_artist_metadata(artist_id=album.getArtistId())
        if (not artist_metadata or
            (not artist_metadata.artist_name or not artist_metadata.artist_name == album.getArtist()) or
                (not artist_metadata.artist_cover_art or not artist_metadata.artist_cover_art == album.getCoverArt())):
            # store this one as fallback
            persistence.save_artist_metadata(artist_metadata=persistence.ArtistMetadata(
                artist_id=album.getArtistId(),
                artist_name=album.getArtist(),
                artist_cover_art=album.getCoverArt()))
    album_genre_list = album.getGenres()
    # album per genre cache
    if album_genre_list:
        genre: str
        for genre in album_genre_list:
            persistence.save_kv_item(key_value_item=KeyValueItem(
                partition=cache_type.CacheType.GENRE_ALBUM_ART.getName(),
                key=genre,
                value=album.getCoverArt()))
    # genres for artist
    if album_genre_list and album.getArtistId():
        # load existing.
        kv_item: KeyValueItem = persistence.get_kv_item(
            partition=cache_type.CacheType.GENRES_FOR_ARTIST.cache_name,
            key=album.getArtistId())
        existing_genre_list_str: str = kv_item.value if kv_item else None
        # split by separator
        genre_list: list[str] = (existing_genre_list_str.split(constants.Separator.GENRE_FOR_ARTIST_SEPARATOR.value)
                                 if existing_genre_list_str
                                 else [])
        genre: str
        for genre in album_genre_list:
            if genre not in genre_list:
                genre_list.append(genre)
        # update cached value
        new_genre_list: str = constants.Separator.GENRE_FOR_ARTIST_SEPARATOR.value.join(genre_list)
        upd_kv_item: KeyValueItem = persistence.KeyValueItem(
            partition=cache_type.CacheType.GENRES_FOR_ARTIST.cache_name,
            key=album.getArtistId(),
            value=new_genre_list)
        persistence.save_kv_item(key_value_item=upd_kv_item)
