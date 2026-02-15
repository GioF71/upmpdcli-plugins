# Copyright (C) 2026 Giovanni Fulco
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

from artist_metadata import ArtistMetadata
from album_metadata import AlbumMetadata
from song_metadata import SongMetadata
from subsonic_connector.artist import Artist
from subsonic_connector.album import Album
from subsonic_connector.song import Song
from typing import Callable
from typing import Any
import subsonic_util
import album_util
import datetime
from metadata_model import ArtistMetadataModel
from metadata_model import AlbumMetadataModel
from metadata_model import SongMetadataModel
from release_date import ReleaseDate
from constants import ItemKey
from album_property_key import AlbumPropertyKey
from disc_title import DiscTitle
import audio_codec


def __prefer_data(
        extractor: Callable[[Any], Any],
        obj_list: list[Any],
        checker: Callable[[Any], bool]) -> str:
    for current in obj_list:
        v: Any = extractor(current)
        if checker(v):
            return v


def prefer_data_simple(extractor: Callable[[Any], Any], obj_list: list[Any]) -> str:
    return __prefer_data(
        extractor=extractor,
        obj_list=obj_list,
        checker=lambda s: __simplest_checker(s))


def __simplest_checker(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        if len(v) == 0:
            return False
    return True


def update_song_metadata(
        existing_metadata: SongMetadata,
        song_metadata: SongMetadata) -> SongMetadata:
    set_list: list[SongMetadataModel] = list(filter(
        lambda x: not (x.primary_key or x.is_created_timestamp or x.is_updated_timestamp),
        list(SongMetadataModel)))
    created_timestamp: datetime.datetime = (existing_metadata.created_timestamp
                                            if existing_metadata.created_timestamp
                                            else datetime.datetime.now())
    updated_timestamp: datetime.datetime = datetime.datetime.now()
    updated_metadata: SongMetadata = SongMetadata()
    updated_metadata.set_value(SongMetadataModel.SONG_ID, song_metadata.song_id)
    current: SongMetadataModel
    prefer_list: list[SongMetadata] = [song_metadata, existing_metadata]
    for current in set_list:
        if not current.calculated:
            # get most recent value, even if it is empty
            # for example, an ALBUM_VERSION can be changed and become empty
            updated_metadata.set_value(current, song_metadata.get_value(current))
        else:
            latest_value: any = prefer_data_simple(lambda x: x.get_value(current), prefer_list)
            updated_metadata.set_value(current, latest_value)
    updated_metadata.set_value(AlbumMetadataModel.CREATED_TIMESTAMP, created_timestamp)
    updated_metadata.set_value(AlbumMetadataModel.UPDATED_TIMESTAMP, updated_timestamp)
    return updated_metadata


def update_artist_metadata(
        existing_metadata: ArtistMetadata,
        artist_metadata: ArtistMetadata) -> ArtistMetadata:
    set_list: list[ArtistMetadataModel] = list(filter(
        lambda x: not (x.primary_key or x.is_created_timestamp or x.is_updated_timestamp),
        list(ArtistMetadataModel)))
    created_timestamp: datetime.datetime = (existing_metadata.created_timestamp
                                            if existing_metadata.created_timestamp
                                            else datetime.datetime.now())
    updated_timestamp: datetime.datetime = datetime.datetime.now()
    updated_metadata: ArtistMetadata = ArtistMetadata()
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_ID, artist_metadata.artist_id)
    current: ArtistMetadataModel
    prefer_list: list[ArtistMetadata] = [artist_metadata, existing_metadata]
    for current in set_list:
        if not current.calculated:
            # get most recent value, even if it is empty
            # for example, an ALBUM_VERSION can be changed and become empty
            updated_metadata.set_value(current, artist_metadata.get_value(current))
        else:
            latest_value: any = prefer_data_simple(lambda x: x.get_value(current), prefer_list)
            updated_metadata.set_value(current, latest_value)
    updated_metadata.set_value(ArtistMetadataModel.CREATED_TIMESTAMP, created_timestamp)
    updated_metadata.set_value(ArtistMetadataModel.UPDATED_TIMESTAMP, updated_timestamp)
    return updated_metadata


def update_album_metadata(
        existing_metadata: AlbumMetadata,
        album_metadata: AlbumMetadata) -> AlbumMetadata:
    set_list: list[AlbumMetadataModel] = list(filter(
        lambda x: not (x.primary_key or x.is_created_timestamp or x.is_updated_timestamp),
        list(AlbumMetadataModel)))
    created_timestamp: datetime.datetime = (existing_metadata.created_timestamp
                                            if existing_metadata.created_timestamp
                                            else datetime.datetime.now())
    updated_timestamp: datetime.datetime = datetime.datetime.now()
    updated_metadata: AlbumMetadata = AlbumMetadata()
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_ID, album_metadata.album_id)
    current: AlbumMetadataModel
    prefer_list: list[AlbumMetadata] = [album_metadata, existing_metadata]
    for current in set_list:
        if not current.calculated:
            # get most recent value, even if it is empty
            # for example, an ALBUM_VERSION can be changed and become empty
            updated_metadata.set_value(current, album_metadata.get_value(current))
        else:
            latest_value: any = prefer_data_simple(lambda x: x.get_value(current), prefer_list)
            updated_metadata.set_value(current, latest_value)
    updated_metadata.set_value(AlbumMetadataModel.CREATED_TIMESTAMP, created_timestamp)
    updated_metadata.set_value(AlbumMetadataModel.UPDATED_TIMESTAMP, updated_timestamp)
    return updated_metadata


def build_artist_metadata(
        artist: Artist,
        created_timestamp: datetime.datetime = None,
        updated_timestamp: datetime.datetime = None) -> ArtistMetadata:
    updated_metadata: ArtistMetadata = ArtistMetadata()
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_ID, artist.getId())
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_NAME, artist.getName())
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_MB_ID, subsonic_util.get_artist_musicbrainz_id(artist=artist))
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_ALBUM_COUNT, artist.getAlbumCount())
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_MEDIA_TYPE, subsonic_util.get_media_type(obj=artist))
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_COVER_ART, subsonic_util.get_artist_cover_art(artist=artist))
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_SORT_NAME, subsonic_util.get_artist_sort_name(artist=artist))
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_ID, artist.getId())
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_ID, artist.getId())
    updated_metadata.set_value(ArtistMetadataModel.ARTIST_ID, artist.getId())
    updated_metadata.set_value(
        ArtistMetadataModel.CREATED_TIMESTAMP,
        created_timestamp if created_timestamp else datetime.datetime.now())
    updated_metadata.set_value(
        ArtistMetadataModel.UPDATED_TIMESTAMP,
        updated_timestamp if updated_timestamp else datetime.datetime.now())
    return updated_metadata


def build_album_metadata(
        album: Album,
        quality_badge: str = None,
        song_quality_summary: str = None,
        album_path: str = None,
        created_timestamp: datetime.datetime = datetime.datetime.now(),
        updated_timestamp: datetime.datetime = datetime.datetime.now()) -> AlbumMetadata:
    updated_metadata: AlbumMetadata = AlbumMetadata()
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_ID, album.getId())
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_MEDIA_TYPE, subsonic_util.get_media_type(album))
    updated_metadata.set_value(AlbumMetadataModel.QUALITY_BADGE, quality_badge)
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_TRACK_QUALITY_SUMMARY, song_quality_summary)
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_MB_ID, subsonic_util.get_album_musicbrainz_id(album))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_ARTIST_ID, album.getArtistId())
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_ARTIST, album.getArtist())
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_NAME, album.getTitle())
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_COVER_ART, album.getCoverArt())
    disc_title_list: list[DiscTitle] = subsonic_util.get_disc_titles_from_album(album=album)
    disc_count: int = len(disc_title_list) if disc_title_list and len(disc_title_list) > 1 else 1
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_DISC_COUNT, disc_count)
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_SONG_COUNT, subsonic_util.get_album_song_count(album))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_PATH, album_path)
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_DURATION, album.getDuration())
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_CREATED, subsonic_util.get_album_created(album))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_YEAR, album.getYear())
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_GENRE, album.getGenre())
    genre_list: list[str] = album.getGenres()
    if not genre_list and album.getGenre():
        genre_list = [album.getGenre()]
    genre_list_str: str = ", ".join(genre_list)
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_GENRE_LIST, genre_list_str)
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_MOOD_LIST, ", ".join(subsonic_util.get_album_moods(album)))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_RECORD_LABEL_LIST, ", ".join(subsonic_util.get_album_record_label_names(album)))
    album_release_types: subsonic_util.AlbumReleaseTypes = subsonic_util.get_album_release_types(album=album)
    if album_release_types:
        updated_metadata.set_value(
            AlbumMetadataModel.ALBUM_RELEASE_TYPE_LIST,
            ", ".join(album_release_types.types))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_USER_RATING, subsonic_util.get_album_user_rating(album))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_DISPLAY_ARTIST, subsonic_util.get_album_display_artist(album))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_EXPLICIT_STATUS, subsonic_util.get_explicit_status(album))
    is_compilation: bool | None = subsonic_util.get_album_is_compilation(album)
    v_is_compilation: int | None = None
    if is_compilation is not None:
        v_is_compilation = 1 if is_compilation else 0
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_IS_COMPILATION, v_is_compilation)
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_PLAY_COUNT, subsonic_util.get_album_play_count(album))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_PLAYED, subsonic_util.get_album_played(album))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_SORT_NAME, subsonic_util.get_album_sort_name(album))
    updated_metadata.set_value(AlbumMetadataModel.ALBUM_VERSION, subsonic_util.get_album_version(album))
    ord: ReleaseDate = album_util.get_album_release_date(album, ItemKey.ORIGINAL_RELEASE_DATE)
    if ord:
        updated_metadata.set_value(AlbumMetadataModel.ALBUM_ORIGINAL_RELEASE_DATE_YEAR, ord.year)
        updated_metadata.set_value(AlbumMetadataModel.ALBUM_ORIGINAL_RELEASE_DATE_MONTH, ord.month)
        updated_metadata.set_value(AlbumMetadataModel.ALBUM_ORIGINAL_RELEASE_DATE_DAY, ord.day)
        ord_int: int = (ord.year * 100 * 100) + ((ord.month if ord.month else 0) * 100) + (ord.day if ord.day else 0)
        # msgproc.log(f"ord_int [{ord_int}]")
        updated_metadata.set_value(AlbumMetadataModel.ALBUM_ORIGINAL_RELEASE_DATE_STR, str(ord_int))
    elif album.getYear():
        # msgproc.log(f"ord_int [{ord_int}] (using year only)")
        updated_metadata.set_value(AlbumMetadataModel.ALBUM_ORIGINAL_RELEASE_DATE_STR, str(album.getYear() * 100 * 100))
    rd: ReleaseDate = album_util.get_album_release_date(album, ItemKey.RELEASE_DATE)
    if rd:
        updated_metadata.set_value(AlbumMetadataModel.ALBUM_RELEASE_DATE_YEAR, rd.year)
        updated_metadata.set_value(AlbumMetadataModel.ALBUM_RELEASE_DATE_MONTH, rd.month)
        updated_metadata.set_value(AlbumMetadataModel.ALBUM_RELEASE_DATE_DAY, rd.day)
        rd_int: int = (rd.year * 100 * 100) + ((rd.month if rd.month else 0) * 100) + (rd.day if rd.day else 0)
        # msgproc.log(f"rd_int [{rd_int}]")
        updated_metadata.set_value(AlbumMetadataModel.ALBUM_RELEASE_DATE_STR, str(rd_int))
    # use songs if available
    song_list: list[Song] = album.getSongs()
    if len(song_list if song_list else []) > 0:
        prop_dict: dict[str, list[str]] = subsonic_util.build_album_properties_from_songs(song_list=song_list)
        # lossless status
        lossless_status: audio_codec.LosslessStatus = (
            audio_codec.get_lossless_status_by_value(v=prop_dict[AlbumPropertyKey.LOSSLESS_STATUS.property_key][0])
            if AlbumPropertyKey.LOSSLESS_STATUS.property_key in prop_dict
            else None)
        if lossless_status:
            updated_metadata.set_value(AlbumMetadataModel.ALBUM_LOSSLESS_STATUS, lossless_status.value)
        # quality badge
        quality_badge: str = (
            prop_dict[AlbumPropertyKey.QUALITY_BADGE.property_key][0]
            if AlbumPropertyKey.QUALITY_BADGE.property_key in prop_dict
            else None)
        if quality_badge:
            updated_metadata.set_value(AlbumMetadataModel.QUALITY_BADGE, quality_badge)
        album_path_joined: str = album_util.get_album_path_list_joined(song_list=song_list)
        if album_path_joined:
            updated_metadata.set_value(AlbumMetadataModel.ALBUM_PATH, album_path_joined)
        # song quality summary
        album_track_quality_summary: str = subsonic_util.calc_song_quality_summary(song_list=song_list)
        if album_track_quality_summary:
            updated_metadata.set_value(AlbumMetadataModel.ALBUM_TRACK_QUALITY_SUMMARY, album_track_quality_summary)
        # averate bitrate
        avg_bitrate: int = subsonic_util._get_avg_bitrate_int(subsonic_util.get_song_info_list(song_list=song_list))
        if avg_bitrate:
            updated_metadata.set_value(AlbumMetadataModel.ALBUM_AVERAGE_BITRATE, avg_bitrate)
        # album_path
        album_path: str = album_util.get_album_path_list_joined(song_list=song_list)
        if album_path and len(album_path) > 0:
            updated_metadata.set_value(AlbumMetadataModel.ALBUM_PATH, album_path)
    updated_metadata.set_value(AlbumMetadataModel.CREATED_TIMESTAMP, created_timestamp)
    updated_metadata.set_value(AlbumMetadataModel.UPDATED_TIMESTAMP, updated_timestamp)
    return updated_metadata


def build_song_metadata(
        song: Song,
        created_timestamp: datetime.datetime = None,
        updated_timestamp: datetime.datetime = None) -> SongMetadata:
    updated_metadata: SongMetadata = SongMetadata()
    updated_metadata.set_value(SongMetadataModel.SONG_ID, song.getId())
    updated_metadata.set_value(SongMetadataModel.SONG_TITLE, song.getTitle())
    updated_metadata.set_value(SongMetadataModel.SONG_ALBUM_ID, song.getAlbumId())
    updated_metadata.set_value(SongMetadataModel.SONG_ARTIST_ID, song.getArtistId())
    updated_metadata.set_value(SongMetadataModel.SONG_ARTIST, song.getArtist())
    updated_metadata.set_value(SongMetadataModel.SONG_COMMENT, subsonic_util.get_song_comment(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_BITDEPTH, subsonic_util.get_song_bit_depth(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_BITRATE, song.getBitRate())
    updated_metadata.set_value(SongMetadataModel.SONG_SAMPLING_RATE, subsonic_util.get_song_sampling_rate(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_CHANNEL_COUNT, subsonic_util.get_song_channel_count(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_SIZE, subsonic_util.get_song_size(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_SUFFIX, song.getSuffix())
    updated_metadata.set_value(SongMetadataModel.SONG_DISC_NUMBER, song.getDiscNumber())
    updated_metadata.set_value(SongMetadataModel.SONG_TRACK, song.getTrack())
    updated_metadata.set_value(SongMetadataModel.SONG_CONTENT_TYPE, song.getContentType())
    updated_metadata.set_value(SongMetadataModel.SONG_CREATED, subsonic_util.get_song_created(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_DISPLAY_ARTIST, subsonic_util.get_song_display_artist(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_DISPLAY_ALBUM_ARTIST, subsonic_util.get_song_display_album_artist(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_COVER_ART, song.getCoverArt())
    updated_metadata.set_value(SongMetadataModel.SONG_DURATION, song.getDuration())
    updated_metadata.set_value(SongMetadataModel.SONG_EXPLICIT_STATUS, subsonic_util.get_explicit_status(obj=song))
    updated_metadata.set_value(SongMetadataModel.SONG_GENRE, song.getGenre())
    updated_metadata.set_value(SongMetadataModel.SONG_IS_DIR, subsonic_util.get_song_is_dir(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_MEDIA_TYPE, subsonic_util.get_media_type(obj=song))
    updated_metadata.set_value(SongMetadataModel.SONG_MUSICBRAINZ_ID, subsonic_util.get_song_musicbrainz_id(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_PATH, song.getPath())
    updated_metadata.set_value(SongMetadataModel.SONG_PLAY_COUNT, subsonic_util.get_song_play_count(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_PLAYED, subsonic_util.get_song_played(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_YEAR, subsonic_util.get_song_year(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_DISPLAY_COMPOSER, subsonic_util.get_song_display_composer(song=song))
    updated_metadata.set_value(SongMetadataModel.SONG_SORT_NAME, subsonic_util.get_song_sort_name(song=song))
    updated_metadata.set_value(
        song_metadata_model=SongMetadataModel.SONG_LOSSLESS_STATUS,
        value=audio_codec.get_lossless_status(suffix=song.getSuffix()).value)
    updated_metadata.set_value(SongMetadataModel.SONG_TYPE, subsonic_util.get_song_type(song=song))
    updated_metadata.set_value(
        SongMetadataModel.CREATED_TIMESTAMP,
        created_timestamp if created_timestamp else datetime.datetime.now())
    updated_metadata.set_value(
        SongMetadataModel.UPDATED_TIMESTAMP,
        updated_timestamp if updated_metadata else datetime.datetime.now())
    return updated_metadata
