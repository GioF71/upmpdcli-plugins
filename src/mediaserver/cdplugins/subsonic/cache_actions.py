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

import sqlite3
import time
from typing import Any

from subsonic_connector.album import Album
from subsonic_connector.song import Song

import cache_manager_provider
import cache_type
import config
import metadata_converter
import persistence
import subsonic_util
from album_metadata import AlbumMetadata
from album_property_key import AlbumPropertyKey
from artist_from_album import ArtistFromAlbum
from metadata_model import AlbumMetadataModel, SongMetadataModel
from msgproc_provider import msgproc
from song_data_structures import SongArtist, SongArtistType, SongContributor
from table_name import TableName


class CacheActionException(Exception):
    """Raised when a Cache Action error occurs."""


def delete_key(cache_type: cache_type.CacheType, key: str) -> bool:
    return cache_manager_provider.get().delete_cached_element(cache_type.cache_name, key)


def on_album(
        album: Album,
        album_metadata: AlbumMetadata | None = None) -> AlbumMetadata | None:
    def msgproc_log(msg: str):
        msgproc.log(f"on_album {msg}")
    start: float = time.time()
    connection: sqlite3.Connection = persistence.get_working_connection()
    md: AlbumMetadata = None
    try:
        md = __on_album(album=album, album_metadata=album_metadata, connection=connection)
    except CacheActionException as ex:
        msgproc_log(f"failed due to [{type(ex)}] [{ex}]")
        connection.close()
    elapsed: float = time.time() - start
    if config.get_verbose_logging():
        msgproc_log(f"for album_id [{album.getId()}] executed in [{elapsed:.3f}]")
    return md


def __on_album(
        album: Album,
        album_metadata: AlbumMetadata | None = None,
        connection: sqlite3.Connection | None = None) -> AlbumMetadata | None:
    def msgproc_log(msg: str):
        msgproc.log(f"__on_album {msg}")
    if not album or not album.getId():
        # nothing to do
        return None
    verbose: bool = config.get_verbose_logging()
    the_connection: sqlite3.Connection = persistence.get_working_connection(connection)
    if not album_metadata:
        album_metadata = persistence.get_album_metadata(album_id=album.getId())
    # keep track of currently calculated values
    # so we don't lose them if the provided album does not have songs available
    # that happens when the album comes from a list of albums
    album_quality_badge: str = album_metadata.quality_badge if album_metadata else None
    track_quality_summary: str = album_metadata.get_value(AlbumMetadataModel.ALBUM_TRACK_QUALITY_SUMMARY) if album_metadata else None
    album_path_joined: str = album_metadata.get_value(AlbumMetadataModel.ALBUM_PATH) if album_metadata else None
    song_list: list[Song] = album.getSongs()
    song_count: int = len(song_list) if song_list else 0
    if verbose:
        msgproc_log(f"[{album.getId()}] -> len(song_list) [{len(song_list if song_list else [])}]")
    # delete orphaned tracks, if any
    # msgproc_log("delete_song_list_not_in")
    persistence.delete_song_list_not_in(
        album_id=album.getId(),
        song_list=[x.getId() for x in song_list],
        connection=the_connection,
        do_commit=False)
    # save metadata
    # msgproc_log("save_album_metadata")
    save_result: tuple[AlbumMetadata, persistence.SaveMode] = persistence.save_album_metadata(
        album_metadata=metadata_converter.build_album_metadata(
            album=album,
            current_metadata=album_metadata,
            quality_badge=album_quality_badge,
            track_quality_summary=track_quality_summary,
            album_path=album_path_joined),
        context="__on_album",
        connection=the_connection,
        do_commit=False)
    enabled_album_property_key_list: list[AlbumPropertyKey] = config.get_enabled_album_property_key_list()
    # save properties
    album_properties: dict[str, list[Any]] = subsonic_util.build_album_properties(album=album)
    # filter.
    album_properties = {k: v for k, v in album_properties.items() if k in [x.property_key for x in enabled_album_property_key_list]}
    # we delete all existing properties if we have an album with tracks (so not coming from album lists)
    delete_all: bool = song_count > 0
    persistence.save_album_properties(
        album_id=album.getId(),
        delete_all=delete_all,
        properties=album_properties,
        connection=the_connection,
        do_commit=False)
    # save other data
    album_artists: list[ArtistFromAlbum] = subsonic_util.get_artists_from_album(album=album)
    # msgproc_log("update_album_artists")
    persistence.update_album_artists(
        album_id=album.getId(),
        album_artists=album_artists,
        connection=the_connection,
        do_commit=False)
    # msgproc_log("update_album_discs")
    persistence.update_album_discs(
        album_id=album.getId(),
        album_discs=subsonic_util.get_disc_titles_from_album(album=album),
        connection=the_connection,
        do_commit=False)
    # msgproc_log("update_album_genres")
    persistence.update_album_genres(
        album_id=album.getId(),
        album_genres=subsonic_util.get_genres_from_album(album=album),
        connection=the_connection,
        do_commit=False)
    # msgproc_log("update_album_record_labels")
    persistence.update_album_record_labels(
        album_id=album.getId(),
        album_record_labels=subsonic_util.get_album_record_label_names(album=album),
        connection=the_connection,
        do_commit=False)
    # msgproc_log("update_album_moods")
    persistence.update_album_moods(
        album_id=album.getId(),
        album_moods=subsonic_util.get_album_moods(album=album),
        connection=the_connection,
        do_commit=False)
    # msgproc_log("update_album_release_types")
    persistence.update_album_release_types(
        album_id=album.getId(),
        album_release_types=subsonic_util.get_album_release_types(album=album).types,
        connection=the_connection,
        do_commit=False)
    if verbose:
        msgproc_log("saving songs ...")
    song: Song
    for song in song_list if song_list else []:
        # msgproc_log("__on_album_song")
        __on_album_song(
            album=album,
            song=song,
            connection=the_connection,
            do_commit=False)
    # purge songs that have vanished, if album has songs available
    if song_count > 0:
        persistence.delete_by_parent_id_and_id_in_list(
            table_name=TableName.SONG_METADATA_V1,
            parent_id_column_name=SongMetadataModel.SONG_ALBUM_ID.column_name,
            parent_id=album.getId(),
            id_column_name=SongMetadataModel.SONG_ID.column_name,
            id_list=[x.getId() for x in song_list],
            in_mode=persistence.InMode.NOT_IN,
            connection=the_connection,
            do_commit=False)
    persistence.commit(connection=the_connection)
    if connection is None:
        the_connection.close()
    return save_result[0] if save_result else None


def __on_album_song(
        album: Album,
        song: Song,
        connection: sqlite3.Connection,
        do_commit: bool = True):
    def msgproc_log(msg: str):
        msgproc.log(f"__on_album_song {msg}")
    verbose: bool = config.get_verbose_logging()
    the_connection: sqlite3.Connection = persistence.get_working_connection(provided=connection)
    if verbose:
        msgproc_log(f"saving songs song [{song.getId()}] ...")
    # msgproc.log("__on_album_song save_song_metadata")
    persistence.save_song_metadata(
        song_metadata=metadata_converter.build_song_metadata(song=song),
        context="__on_album_song",
        connection=connection,
        do_commit=do_commit)
    # song album artists
    song_album_artist_list: list[SongArtist] = subsonic_util.get_song_artists_by_type(
        song=song,
        song_artist_type=SongArtistType.SONG_ALBUM_ARTIST)
    # msgproc.log("__on_album_song save_song_album_artist_list")
    persistence.save_song_album_artist_list(
        song_id=song.getId(),
        album_id=album.getId(),
        song_album_artist_list=song_album_artist_list,
        connection=the_connection,
        do_commit=do_commit)
    if verbose:
        msgproc_log(f"[{album.getId()}] song [{song.getId()}] album_artists [{len(song_album_artist_list)}]")
    # song artists
    song_artist_list: list[SongArtist] = subsonic_util.get_song_artists_by_type(
        song=song,
        song_artist_type=SongArtistType.SONG_ARTIST)
    # msgproc.log("__on_album_song save_song_artist_list")
    persistence.save_song_artist_list(
        song_id=song.getId(),
        album_id=album.getId(),
        song_artist_list=song_artist_list,
        connection=the_connection,
        do_commit=do_commit)
    if verbose:
        msgproc_log(f"[{album.getId()}] song [{song.getId()}] artists [{len(song_artist_list)}]")
    # contributors
    song_contributor_list: list[SongContributor] = subsonic_util.get_song_contributors(song=song)
    # msgproc.log("__on_album_song save_song_contributor_list")
    persistence.save_song_contributor_list(
        song_id=song.getId(),
        album_id=album.getId(),
        song_contributor_list=song_contributor_list,
        connection=the_connection,
        do_commit=do_commit)
    if verbose:
        msgproc_log(f"[{album.getId()}] song [{song.getId()}] contributors [{len(song_contributor_list)}]")
