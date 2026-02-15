# Copyright (C) 2024,2025,2026 Giovanni Fulco
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

import cache_type
import cache_manager_provider
import subsonic_util
import config
import constants
import persistence
import album_util
import time
import metadata_converter
from subsonic_connector.album import Album
from subsonic_connector.song import Song
from artist_from_album import ArtistFromAlbum
from song_data_structures import SongArtistType
from song_data_structures import SongArtist
from song_data_structures import SongContributor
from table_name import TableName
from metadata_model import SongMetadataModel
from msgproc_provider import msgproc
from typing import Any


def delete_key(cache_type: cache_type.CacheType, key: str) -> bool:
    return cache_manager_provider.get().delete_cached_element(cache_type.cache_name, key)


def on_album(album: Album):
    start: float = time.time()
    __on_album(album=album)
    elapsed: float = time.time() - start
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"on_album for album_id [{album.getId()}] executed in [{elapsed:.3f}]")


def __on_album(album: Album):
    if not album or not album.getId():
        # nothing to do
        return
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    album_quality_badge: str = None
    track_quality_summary: str = None
    album_path_joined: str = None
    song_list: list[Song] = album.getSongs()
    song_count: int = len(song_list) if song_list else 0
    if len(song_list) if song_list else 0:
        # we can calculate qualities and path
        album_quality_badge = subsonic_util.calc_song_list_quality_badge(song_list=song_list)
        track_quality_summary = subsonic_util.calc_song_quality_summary(song_list=song_list)
        album_path_joined = album_util.get_album_path_list_joined(song_list=song_list)
        if verbose:
            msgproc.log(f"__on_album [{album.getId()}] -> "
                        f"badge [{album_quality_badge}] "
                        f"summary [{track_quality_summary}] "
                        f"path [{album_path_joined}]")
    # delete orphaned tracks
    persistence.delete_song_list_not_in(
        album_id=album.getId(),
        song_list=list(map(lambda x: x.getId(), song_list)))
    # save metadata
    persistence.save_album_metadata(
        album_metadata=metadata_converter.build_album_metadata(
            album=album,
            quality_badge=album_quality_badge,
            song_quality_summary=track_quality_summary,
            album_path=album_path_joined),
        context="__on_album")
    # save properties
    album_properties: dict[str, list[Any]] = subsonic_util.build_album_properties(album=album)
    persistence.save_album_properties(
        album_id=album.getId(),
        properties=album_properties)
    # save other data
    album_artists: list[ArtistFromAlbum] = subsonic_util.get_artists_from_album(album=album)
    persistence.update_album_artists(
        album_id=album.getId(),
        album_artists=album_artists)
    persistence.update_album_discs(
        album_id=album.getId(),
        album_discs=subsonic_util.get_disc_titles_from_album(album=album))
    persistence.update_album_genres(
        album_id=album.getId(),
        album_genres=subsonic_util.get_genres_from_album(album=album))
    persistence.update_album_record_labels(
        album_id=album.getId(),
        album_record_labels=subsonic_util.get_album_record_label_names(album=album))
    persistence.update_album_moods(
        album_id=album.getId(),
        album_moods=subsonic_util.get_album_moods(album=album))
    persistence.update_album_release_types(
        album_id=album.getId(),
        album_release_types=subsonic_util.get_album_release_types(album=album).types)
    if verbose:
        msgproc.log("__on_album saving songs ...")
    song: Song
    for song in song_list if song_list else []:
        __on_album_song(album=album, song=song)
    # purge removed songs
    if song_count > 0:
        persistence.delete_by_parent_id_and_id_in_list(
            table_name=TableName.SONG_METADATA_V1,
            parent_id_column_name=SongMetadataModel.SONG_ALBUM_ID.column_name,
            parent_id=album.getId(),
            id_column_name=SongMetadataModel.SONG_ID.column_name,
            id_list=list(map(lambda x: x.getId(), song_list)),
            in_mode=persistence.InMode.NOT_IN)


def __on_album_song(
        album: Album,
        song: Song):
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    if verbose:
        msgproc.log(f"__on_album saving songs song [{song.getId()}] ...")
    persistence.save_song_metadata(
        song_metadata=metadata_converter.build_song_metadata(song=song),
        context="__on_album_song")
    # song album artists
    song_album_artist_list: list[SongArtist] = subsonic_util.get_song_artists_by_type(
        song=song,
        song_artist_type=SongArtistType.SONG_ALBUM_ARTIST)
    persistence.save_song_album_artist_list(
        song_id=song.getId(),
        album_id=album.getId(),
        song_album_artist_list=song_album_artist_list)
    if verbose:
        msgproc.log(f"__on_album [{album.getId()}] song [{song.getId()}] album_artists [{len(song_album_artist_list)}]")
    # song artists
    song_artist_list: list[SongArtist] = subsonic_util.get_song_artists_by_type(
        song=song,
        song_artist_type=SongArtistType.SONG_ARTIST)
    persistence.save_song_artist_list(
        song_id=song.getId(),
        album_id=album.getId(),
        song_artist_list=song_artist_list)
    if verbose:
        msgproc.log(f"__on_album [{album.getId()}] song [{song.getId()}] artists [{len(song_artist_list)}]")
    # contributors
    song_contributor_list: list[SongContributor] = subsonic_util.get_song_contributors(song=song)
    persistence.save_song_contributor_list(
        song_id=song.getId(),
        album_id=album.getId(),
        song_contributor_list=song_contributor_list)
    if verbose:
        msgproc.log(f"__on_album [{album.getId()}] song [{song.getId()}] contributors [{len(song_contributor_list)}]")
