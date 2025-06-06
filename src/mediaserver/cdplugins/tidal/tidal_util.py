# Copyright (C) 2023,2024,2025 Giovanni Fulco
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
import config
import requests
import os
import secrets
import mimetypes
import glob
import pathlib

import upmpdmeta
import upnp_util

from tidalapi import Quality as TidalQuality
from tidalapi.session import Session as TidalSession
from tidalapi.artist import Artist as TidalArtist
from tidalapi.album import Album as TidalAlbum
from tidalapi.playlist import Playlist as TidalPlaylist
from tidalapi.playlist import UserPlaylist as TidalUserPlaylist
from tidalapi.mix import Mix as TidalMix
from tidalapi.media import MediaMetadataTags as TidalMediaMetadataTags
from tidalapi.media import Track as TidalTrack
from tidalapi.media import Video as TidalVideo
from tidalapi.media import AudioMode as TidalAudioMode
from tidalapi.exceptions import ObjectNotFound

from typing import Callable
from typing import Union

from element_type import ElementType
from element_type import get_element_type_by_name

from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey

import identifier_util
import persistence
from played_track import PlayedTrack

from album_sort_criteria import AlbumSortCriteria
from album_adapter import AlbumAdapter
from datetime import datetime

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

log_unavailable_images_sizes: bool = (upmplgutils.getOptionValue(
    f"{constants.PluginConstant.PLUGIN_NAME.value}log_unavailable_images_sizes",
    "0") == "1")
log_unavailable_image: bool = (upmplgutils.getOptionValue(
                                f"{constants.PluginConstant.PLUGIN_NAME.value}log_unavailable_image",
                                "0") == "1")

default_image_sz_by_type: dict[str, int] = dict()
default_image_sz_by_type[TidalArtist.__name__] = [750, 480, 320, 160]
default_image_sz_by_type[TidalAlbum.__name__] = [1280, 640, 320, 160, 80]
default_image_sz_by_type[TidalPlaylist.__name__] = [1080, 750, 640, 480, 320, 160]
default_image_sz_by_type[TidalMix.__name__] = [1500, 640, 320]
default_image_sz_by_type[TidalUserPlaylist.__name__] = default_image_sz_by_type[TidalPlaylist.__name__]


class FavoriteAlbumsMode:

    __element_type: ElementType
    __display_name: str
    __sort_criteria_builder: Callable[[bool], list[AlbumSortCriteria]]
    __descending: bool

    @classmethod
    def create(
            cls,
            element_type: ElementType,
            display_name: str,
            sort_criteria_builder: Callable[[bool], list[AlbumSortCriteria]],
            descending: bool = False):
        obj: FavoriteAlbumsMode = FavoriteAlbumsMode()
        obj.__element_type = element_type
        obj.__display_name = display_name
        obj.__sort_criteria_builder = sort_criteria_builder
        obj.__descending = descending
        return obj

    @property
    def element_type(self) -> ElementType:
        return self.__element_type

    @property
    def display_name(self) -> str:
        return self.__display_name

    @property
    def sort_criteria_builder(self) -> Callable[[bool], list[AlbumSortCriteria]]:
        return self.__sort_criteria_builder

    @property
    def descending(self) -> bool:
        return self.__descending


def __get_image_dimension_list(obj: any) -> list[int]:
    key = type(obj).__name__
    return default_image_sz_by_type[key] if key in default_image_sz_by_type else list()


def get_name_or_title(obj: any) -> str:
    if hasattr(obj, "name"):
        return obj.name
    if hasattr(obj, "title"):
        return obj.title
    return None


def get_album_art_url_by_album_id(
        album_id: str,
        tidal_session: TidalSession,
        album: TidalAlbum = None) -> str:
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
    # if True:
        msgproc.log(f"get_album_art_url_by_album_id for album_id [{album_id}] album [{'set' if album else 'not set'}]")
    if config.get_enable_image_caching():
        # try cached!
        document_root_dir: str = config.getWebServerDocumentRoot()
        if document_root_dir:
            sub_dir_list: list[str] = [
                constants.PluginConstant.PLUGIN_NAME.value,
                constants.PluginConstant.CACHED_IMAGES_DIRECTORY.value,
                TidalAlbum.__name__]
            image_dir: str = ensure_directory(document_root_dir, sub_dir_list)
            cached_file_name_no_ext: str = f"{str(album_id)}"
            cached_files: list[str] = glob.glob(f"{os.path.join(image_dir, cached_file_name_no_ext)}.*")
            if config.get_dump_image_caching():
                msgproc.log(f"get_album_art_url_by_album_id [{album_id}] -> [{cached_files if cached_files else []}]")
            if cached_files and len(cached_files) > 0:
                # pick newest file
                cached_file: str = __select_newest_file(cached_files)
                cached_file_name_ext: str = os.path.splitext(cached_file)[1]
                # touch the file.
                # msgproc.log(f"About to touch file [{cached_file}] ...")
                pathlib.Path(cached_file).touch()
                # use cached file
                path: list[str] = list()
                path.extend(sub_dir_list)
                path.append(f"{str(album_id)}{cached_file_name_ext}")
                cached_image_url: str = compose_docroot_url(os.path.join(*path))
                if config.get_dump_image_caching():
                    msgproc.log(f"get_album_art_url_by_album_id [{album_id}] -> [{cached_image_url}]")
                return cached_image_url
            else:
                if config.get_dump_image_caching():
                    msgproc.log(f"get_album_art_url_by_album_id [{album_id}] -> cache miss")
    # if we are are, we fallback to normal
    if config.get_dump_image_caching():
        msgproc.log(f"get_album_art_url_by_album_id [{album_id}] -> loading from upstream service is required")
    # album: TidalAlbum = album if album else try_get_album(album_id=album_id, tidal_session=tidal_session)
    if not album:
        album = try_get_album(album_id=album_id, tidal_session=tidal_session)
    return get_image_url(obj=album, refresh=True) if album else None


def get_web_document_root_file_url(dir_list: list[str], file_name: str) -> str:
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"get_web_document_root_file_url for [{dir_list}] [{file_name}]")
    path: list[str] = list()
    path.extend(dir_list)
    path.append(file_name)
    file_url: str = compose_docroot_url(os.path.join(*path))
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"get_web_document_root_file_url for [{dir_list}] [{file_name}] "
                    f"-> [{file_url}]")
    return file_url


def get_image_url(obj: any, refresh: bool = False) -> str:
    if obj is None:
        return None
    if isinstance(obj, TidalTrack):
        # use album instead
        track: TidalTrack = obj
        obj = track.album
    if not config.get_enable_image_caching():
        return __get_image_url(obj)
    document_root_dir: str = config.getWebServerDocumentRoot()
    # webserverdocumentroot is required
    if not document_root_dir:
        return __get_image_url(obj)
    if type(obj) not in [TidalAlbum, TidalArtist, TidalPlaylist, TidalMix]:
        return __get_image_url(obj)
    sub_dir_list: list[str] = [
        constants.PluginConstant.PLUGIN_NAME.value,
        constants.PluginConstant.CACHED_IMAGES_DIRECTORY.value,
        type(obj).__name__]
    image_dir: str = ensure_directory(document_root_dir, sub_dir_list)
    cached_file_names: list[str] = __get_cached_file_names(image_dir, str(obj.id))
    # msgproc.log(f"get_image_url for [{str(obj.id)}] -> [{cached_file_names}]")
    # pick newest file
    cached_file_name: str = (__select_newest_file(cached_file_names)
                             if cached_file_names and len(cached_file_names) > 0
                             else None)
    # touch the file.
    if cached_file_name:
        # msgproc.log(f"About to touch file [{cached_file_name}] ...")
        pathlib.Path(cached_file_name).touch()
    # cached_file_name_ext will include the ".", so it will likely be ".jpg"
    cached_file_name_ext: str = os.path.splitext(cached_file_name)[1] if cached_file_name else None
    # msgproc.log(f"For itemid [{str(obj.id)}] found file [{cached_file_name}]")
    if refresh or not cached_file_name:
        image_url: str = __get_image_url(obj=obj)
        # msgproc.log(f"get_image_url saving to [{image_dir}] [{dest_file}]")
        response = requests.get(image_url)
        content_type = response.headers.get('content-type')
        file_types: list[str] = mimetypes.guess_all_extensions(content_type)
        if file_types and len(file_types) > 0:
            # file_types include the "."
            cached_file: str = os.path.join(image_dir, f"{str(obj.id)}{file_types[0].lower()}")
            if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
                msgproc.log(f"get_image_url got mimetype for [{image_url}] -> "
                            f"[{file_types}] -> "
                            f"saving to [{cached_file}]")
            img_data: bytes = requests.get(image_url).content
            with open(cached_file, 'wb') as handler:
                handler.write(img_data)
            cached_image_url: str = get_web_document_root_file_url(
                dir_list=sub_dir_list,
                file_name=f"{str(obj.id)}{file_types[0].lower()}")
            return cached_image_url
        else:
            msgproc.log(f"Cannot understand file type for item id [{str(obj.id)}], cannot cache.")
            return None
    elif cached_file_name:
        ## path: list[str] = list()
        ## path.extend(sub_dir_list)
        ## path.append(f"{str(obj.id)}{cached_file_name_ext}")
        # remember, cached_file_name_ext will include the ".", so it will likely be ".jpg"
        # cached_image_url: str = compose_docroot_url(os.path.join(*path))
        # msgproc.log(f"get_image_url returning cached [{cached_image_url}]")
        # return cached_image_url
        return get_web_document_root_file_url(
                dir_list=sub_dir_list,
                file_name=f"{str(obj.id)}{cached_file_name_ext}")


def __get_cached_file_names(cache_dir: str, item_id: str) -> list[str]:
    cached_file_path: str = os.path.join(cache_dir, item_id)
    item_id_ext: str = os.path.splitext(cached_file_path)[1]
    if item_id_ext:
        # cached_file_path has extension, we convert that to lower case
        item_id_ext = item_id_ext.lower()
        exists = os.path.exists(cached_file_path)
        if exists:
            return [cached_file_path]
    else:
        # no extension in item_id, look what's stored, if any
        matching_files: list[str] = glob.glob(f"{cached_file_path}.*")
        if matching_files and len(matching_files) > 0:
            return matching_files
    return []


def __select_newest_file(file_list: list[str]) -> str:
    if not file_list or len(file_list) == 0:
        return None
    if len(file_list) == 1:
        return file_list[0]
    by_modification_time: list[tuple[str, float]] = []
    curr_file: str
    for curr_file in file_list:
        curr_path = os.path.normcase(curr_file)
        mtime: float = os.path.getmtime(curr_path)
        by_modification_time.append((curr_file, mtime))
    # sort by mtime descending
    by_modification_time.sort(key=lambda x: x[1], reverse=True)
    # get first.
    return by_modification_time[0][0]


def __get_image_url(obj: any) -> str:
    if obj is None:
        return None
    dimension_list: list[int] = __get_image_dimension_list(obj)
    if not dimension_list or len(dimension_list) == 0:
        msgproc.log(f"Type [{type(obj).__name__}] does not have an image sizes list!")
        return None
    current: int
    for current in dimension_list if dimension_list else list():
        try:
            return obj.image(dimensions=current)
        except ValueError:
            if log_unavailable_images_sizes:
                msgproc.log(f"Cannot find image for type [{type(obj).__name__}] "
                            f"id [{obj.id}] Name [{get_name_or_title(obj)}] with size [{current}]")
        except AttributeError as ae_exc:
            msgproc.log(f"Cannot find image for type [{type(obj).__name__}] "
                        f"id [{obj.id}] Name [{get_name_or_title(obj)}] Exception [{ae_exc}]")
    if log_unavailable_image:
        msgproc.log(f"Cannot find image for type [{type(obj).__name__}] id [{obj.id}] "
                    f"Name [{get_name_or_title(obj)}] (any size)")
    return None


def is_mp3(q: TidalQuality) -> bool:
    return q == TidalQuality.low_320k or q == TidalQuality.low_96k


def get_mime_type(track_quality: TidalQuality) -> str:
    if is_mp3(track_quality):
        return "audio/mp3"
    else:
        return "audio/flac"


def is_multidisc_album(album: TidalAlbum) -> bool:
    return album.num_volumes and album.num_volumes > 1


def try_get_track(tidal_session: TidalSession, track_id: str) -> tuple[TidalTrack, Exception]:
    track: TidalTrack = None
    try:
        track = tidal_session.track(track_id)
    except Exception as ex:
        msgproc.log(f"try_get_track failed for track_id [{track_id}] [{type(ex)}] [{ex}]")
        return None, ex
    return track, None


def try_get_album(tidal_session: TidalSession, album_id: str) -> TidalAlbum:
    album: TidalAlbum = None
    try:
        album = tidal_session.album(album_id)
    except ObjectNotFound as onfEx:
        msgproc.log(f"try_get_album could not find album_id [{album_id}] [{type(onfEx)}] [{onfEx}]")
        # TODO more actions? like e.g. remove from favorites
    except Exception as ex:
        msgproc.log(f"try_get_album failed for album_id [{album_id}] [{type(ex)}] [{ex}]")
    return album


def try_get_artist(tidal_session: TidalSession, artist_id: str) -> TidalArtist:
    artist: TidalArtist = None
    try:
        artist = tidal_session.artist(artist_id)
    except Exception as ex:
        msgproc.log(f"try_get_artist failed for artist_id [{artist_id}] [{type(ex)}] [{ex}]")
    return artist


class CachedTidalQuality:

    def __init__(
            self,
            bit_depth: int,
            sample_rate: int,
            audio_quality: TidalQuality,
            audio_mode: str = None):
        self._bit_depth: int = bit_depth
        self._sample_rate: int = sample_rate
        self._audio_quality: TidalQuality = audio_quality
        self._audio_mode: str = audio_mode

    @property
    def bit_depth(self) -> int:
        return self._bit_depth

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def audio_quality(self) -> TidalQuality:
        return self._audio_quality

    @property
    def audio_mode(self) -> str:
        return self._audio_mode


__readable_sr: dict[int, str] = {
    44100: "44",
    48000: "48",
    88200: "88",
    96000: "96",
    176400: "176",
    192000: "192"
}


def __readable_sample_rate(sample_rate: int) -> str:
    if sample_rate in __readable_sr:
        return __readable_sr[sample_rate]
    return None


def get_playlist_by_name(
        tidal_session: TidalSession,
        playlist_name: str,
        create_if_missing: bool = False) -> TidalUserPlaylist:
    tidal_session.user.playlists()
    user_playlists: list[TidalUserPlaylist] = tidal_session.user.playlists()
    # look for the first playlist with the configured name
    # if it does not exist, we create it, if we are allowed to
    listen_queue: TidalUserPlaylist = None
    current: TidalUserPlaylist
    for current in user_playlists if user_playlists else list():
        # msgproc.log(f"get_playlist_by_name processing [{current.name}]")
        if current.name == config.listen_queue_playlist_name:
            listen_queue = current
            break
    if not listen_queue and create_if_missing:
        # we create the playlist
        listen_queue = tidal_session.user.create_playlist(playlist_name)
    return listen_queue


def is_album_in_playlist(
        tidal_session: TidalSession,
        album_id: str,
        playlist_name: str) -> bool:
    listen_queue: TidalUserPlaylist = get_playlist_by_name(
        tidal_session=tidal_session,
        playlist_name=playlist_name)
    if not listen_queue:
        msgproc.log(f"is_album_in_listen_queue for album_id [{album_id}] -> "
                    f"playlist [{config.listen_queue_playlist_name}] not found")
        return False
    # if we find a track from that album, we return True
    offset: int = 0
    limit: int = 100
    while True:
        item_list: list = listen_queue.items(offset=offset, limit=limit)
        msgproc.log(f"Getting [{len(item_list) if item_list else 0}] from playlist "
                    f"[{config.listen_queue_playlist_name}] from offset [{offset}]")
        if not item_list or len(item_list) == 0:
            # we are finished
            # msgproc.log(f"No more items from offset [{offset}], we are finished")
            break
        count: int = 0
        for current in item_list if item_list else list():
            count += 1
            # must be a track
            if not isinstance(current, TidalTrack):
                continue
            track: TidalTrack = current
            if track.album.id == album_id:
                # msgproc.log(f"Found track [{track.id}] from album [{album_id}], returning True")
                return True
        if count < limit:
            # msgproc.log(f"Found [{count}] instead of [{limit}] from offset [{offset}], we are finished")
            break
        offset += limit
    return False


def album_playlist_action(
        tidal_session: TidalSession,
        album_id: str,
        playlist_name: str,
        action: str) -> TidalAlbum:
    listen_queue: TidalUserPlaylist = get_playlist_by_name(
        tidal_session=tidal_session,
        playlist_name=playlist_name,
        create_if_missing=True)
    # remove anyway, add to the end if action is add
    remove_list: list[str] = list()
    offset: int = 0
    limit: int = 100
    while True:
        item_list: list = listen_queue.items(offset=offset, limit=limit)
        # msgproc.log(f"Getting [{len(item_list) if item_list else 0}] from playlist "
        #             f"[{config.listen_queue_playlist_name}] from offset [{offset}]")
        if not item_list or len(item_list) == 0:
            # we are finished
            msgproc.log(f"No more items from offset [{offset}], we are finished")
            break
        count: int = 0
        for current in item_list:
            count += 1
            # must be a track
            if not isinstance(current, TidalTrack):
                continue
            track: TidalTrack = current
            if track.album.id == album_id:
                # msgproc.log(f"Found track [{track.id}] from album [{album_id}], returning True")
                remove_list.append(track.id)
        if count < limit:
            # msgproc.log(f"Found [{count}] instead of [{limit}] from offset [{offset}], we are finished")
            break
        offset += limit
    for track_id in remove_list:
        listen_queue.remove_by_id(media_id=track_id)
    album: TidalAlbum = tidal_session.album(album_id=album_id)
    # add if needed
    if constants.ListeningQueueAction.ADD.value == action:
        # add the album tracks
        media_id_list: list[str] = list()
        t: TidalTrack
        for t in album.tracks():
            media_id_list.append(t.id)
        listen_queue.add(media_id_list)
    return album


def is_tidal_album_stereo(album: TidalAlbum) -> bool:
    # missing -> assume STEREO
    media_metadata_tags: list[str] = album.media_metadata_tags
    return is_stereo(media_metadata_tags)


def __audio_modes_has_stereo(audio_modes: list[str]) -> bool:
    if not audio_modes or len(audio_modes) == 0:
        return False
    current: str
    for current in audio_modes:
        if TidalAudioMode.stereo == current:
            return True
    return False


def is_stereo(media_metadata_tags: list[str]) -> bool:
    # nothing available -> assume STEREO
    if not media_metadata_tags or len(media_metadata_tags) == 0:
        return True
    return not __only_of(
        media_metadata_tags=media_metadata_tags,
        hit=[TidalMediaMetadataTags.dolby_atmos])


def __only_of(media_metadata_tags: list[str], hit: list[str]) -> bool:
    if not media_metadata_tags or len(media_metadata_tags) == 0:
        return False
    current: str
    for current in media_metadata_tags:
        if current not in hit:
            return False
    return True


def not_stereo_skipmessage(album: TidalAlbum) -> str:
    return (f"Skipping album with id [{album.id}] [{album.name}] by [{album.artist.name}] "
            f"because: [{album.media_metadata_tags}]")


def __get_best_quality(media_metadata_tags: list[str]) -> str:
    if not media_metadata_tags or len(media_metadata_tags) == 0:
        return None
    if TidalMediaMetadataTags.hi_res_lossless in media_metadata_tags:
        return TidalQuality.hi_res_lossless
    if TidalMediaMetadataTags.lossless in media_metadata_tags:
        return TidalQuality.high_lossless
    if TidalMediaMetadataTags.dolby_atmos in media_metadata_tags:
        return TidalQuality.low_96k
    return None


def try_get_all_favorites(tidal_session: TidalSession) -> list[TidalAlbum]:
    favorite_list: list[TidalAlbum] = list()
    offset: int = 0
    limit: int = 100
    while True:
        some: list[TidalAlbum] = None
        try:
            some: list[TidalAlbum] = tidal_session.user.favorites.albums(limit=limit, offset=offset)
        except Exception as ex:
            msg: str = f"Cannot get favorite albums from offset [{offset}] [{type(ex)}] [{ex}]"
            raise Exception(msg)
        some_len: int = len(some) if some else 0
        if some_len > 0:
            favorite_list.extend(some)
        if some_len < limit:
            break
        # another slice maybe
        offset += limit
    return favorite_list


def get_quality_badge(
        album: TidalAlbum,
        cached_tidal_quality: CachedTidalQuality) -> str:
    return get_quality_badge_raw(
        audio_modes=album.audio_modes,
        media_metadata_tags=album.media_metadata_tags,
        audio_quality=album.audio_quality,
        cached_tidal_quality=cached_tidal_quality)


def get_quality_badge_raw(
        audio_modes: list[str],
        media_metadata_tags: list[str],
        audio_quality: str,
        cached_tidal_quality: CachedTidalQuality) -> str:
    # msgproc.log(f"get_quality_badge type(audio_modes) -> {type(audio_modes) if audio_modes else 'none'}")
    # TODO maybe map DOLBY_ATMOS to say Atmos
    if audio_modes and not __audio_modes_has_stereo(audio_modes):
        return ",".join(audio_modes)
    tidal_quality: TidalQuality = __get_best_quality(media_metadata_tags)
    if not tidal_quality:
        tidal_quality = audio_quality
    stream_info_available: bool = (
        cached_tidal_quality and
        cached_tidal_quality.bit_depth and
        cached_tidal_quality.sample_rate)
    bit_depth: int = cached_tidal_quality.bit_depth if cached_tidal_quality else None
    sample_rate: int = cached_tidal_quality.sample_rate if cached_tidal_quality else None
    ext_badge: str = (f"{bit_depth}/{__readable_sample_rate(sample_rate)}"
                      if stream_info_available else None)
    badge: str = None
    if TidalQuality.hi_res_lossless == tidal_quality:
        if ext_badge:
            badge = ext_badge
        else:
            badge = f"HD {ext_badge}" if ext_badge else "MAX"
    elif TidalQuality.high_lossless == tidal_quality:
        if not stream_info_available:
            badge = "Lossless"
        else:
            if bit_depth == 16 and sample_rate == 44100:
                badge = "CD"
            elif bit_depth == 16 and sample_rate == 48000:
                badge = "16/48"
            else:
                badge = ext_badge
    elif TidalQuality.low_320k == tidal_quality:
        badge = "Low/320"
    elif TidalQuality.low_96k == tidal_quality:
        badge = "Low/96"
    if config.display_quality_badge:
        msgproc.log(f"get_quality_badge q:[{tidal_quality}] "
                    f"b:[{bit_depth}] "
                    f"s:[{sample_rate}] -> [{badge}]")
    return badge


def track_only(obj: any) -> any:
    if obj and isinstance(obj, TidalTrack):
        return obj


def get_mix_or_playlist_items(
        tidal_session: TidalSession,
        tidal_obj_id: str,
        obj_type: str,
        limit: int,
        offset: int) -> list[any]:
    underlying_type: ElementType = get_element_type_by_name(element_name=obj_type)
    if underlying_type == ElementType.PLAYLIST:
        playlist: TidalPlaylist = tidal_session.playlist(tidal_obj_id)
        return playlist.tracks(limit=limit, offset=offset)
    elif underlying_type == ElementType.MIX:
        mix: TidalMix = tidal_session.mix(tidal_obj_id)
        items: list[any] = mix.items()
        items = items if items else list()
        sz: int = len(items)
        if offset >= sz:
            return list()
        if offset + limit > sz:
            # reduce limit
            limit = sz - offset
        return items[offset:offset + limit]
    else:
        raise Exception(f"Invalid type [{obj_type}]")


def load_unique_ids_from_mix_or_playlist(
        tidal_session: TidalSession,
        tidal_obj_id: str,
        tidal_obj_type: str,
        id_extractor: Callable[[any], str],
        max_id_list_length: int,
        previous_page_last_found_id: str = None,
        item_filter: Callable[[any], any] = lambda x: track_only(x),
        initial_offset: int = 0,
        max_slice_size: int = 100) -> tuple[list[str], list[any], int, bool, str]:
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"load_unique_ids_from_mix_or_playlist mix_or_playlist_id [{tidal_obj_id}] "
                    f"tidal_obj_type [{tidal_obj_type}] "
                    f"initial_offset [{initial_offset}] max_slice_size [{max_slice_size}]")
    last_offset: int = initial_offset
    id_list: list[str] = list()
    obj_list: list[any] = list()
    load_count: int = 0
    skip_count: int = 0
    finished: bool = False
    last_found: str = None
    while len(id_list) < max_id_list_length:
        max_loadable: int = max_slice_size
        if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
            msgproc.log(f"load_unique_ids_from_mix_or_playlist mix_or_pl [{tidal_obj_id}] "
                        f"tidal_obj_type [{tidal_obj_type}] "
                        f"loading [{max_loadable}] from offset [{last_offset}] "
                        f"load_count [{load_count}] skip_count [{skip_count}] ...")
        item_list: list[any] = get_mix_or_playlist_items(
            tidal_session=tidal_session,
            tidal_obj_id=tidal_obj_id,
            obj_type=tidal_obj_type,
            limit=max_slice_size,
            offset=last_offset)
        if not item_list or len(item_list) == 0:
            # no items, we are finished
            finished = True
            break
        slice_count: int = 0
        for i in item_list:
            slice_count += 1
            last_offset += 1
            item = item_filter(i) if item_filter is not None else i
            if item:
                id_value: str = id_extractor(item)
                # already collected?
                if (id_value and
                    (not previous_page_last_found_id or id_value != previous_page_last_found_id) and
                        (id_value not in id_list)):
                    id_list.append(id_value)
                    obj_list.append(item)
                    last_found = id_value
                if len(id_list) == max_id_list_length:
                    # we are finished
                    break
            else:
                skip_count += 1
        load_count += len(item_list)
        # did we extract less than requested?
        if len(item_list) < max_slice_size:
            # we are finished in this case
            finished = True
            break
    return id_list, obj_list, last_offset, finished, last_found


def get_webserver_cached_images_path() -> list[str]:
    return [
        constants.PluginConstant.PLUGIN_NAME.value,
        constants.PluginConstant.CACHED_IMAGES_DIRECTORY.value]


def get_webserver_static_images_path() -> list[str]:
    return [
        constants.PluginConstant.PLUGIN_NAME.value,
        constants.PluginConstant.STATIC_IMAGES_DIRECTORY.value]


def get_plugin_code_subpath() -> list[str]:
    return ["cdplugins", constants.PluginConstant.PLUGIN_NAME.value]


def get_plugin_code_static_images_subpath() -> list[str]:
    return get_plugin_code_subpath() + [constants.PluginConstant.PLUGIN_IMAGES_DIRECTORY.value]


def get_plugin_static_images_abs_path() -> str:
    plugin_data_dir: str = upmplgutils.getOptionValue("pkgdatadir")
    plugin_path: list[str] = get_plugin_code_static_images_subpath()
    p: str
    for p in plugin_path:
        plugin_data_dir = os.path.join(plugin_data_dir, p)
    return plugin_data_dir


def ensure_directory(base_dir: str, sub_dir_list: list[str]) -> str:
    curr_sub_dir: str
    curr_dir: str = base_dir
    for curr_sub_dir in sub_dir_list:
        new_dir: str = os.path.join(curr_dir, curr_sub_dir)
        # msgproc.log(f"checking dir [{new_dir}] ...")
        if not os.path.exists(new_dir):
            msgproc.log(f"creating dir [{new_dir}] ...")
            os.mkdir(new_dir)
        # else:
        #     msgproc.log(f"dir [{new_dir}] already exists.")
        curr_dir = new_dir
    return curr_dir


def get_docroot_base_url() -> str:
    host_port: str = (os.environ[constants.EnvironmentVariableName.UPMPD_UPNPHOSTPORT.value]
                      if constants.EnvironmentVariableName.UPMPD_UPNPHOSTPORT.value in os.environ
                      else None)
    doc_root: str = (os.environ["UPMPD_UPNPDOCROOT"]
                     if "UPMPD_UPNPDOCROOT" in os.environ
                     else None)
    if not host_port or not doc_root:
        return None
    return f"http://{host_port}"


def compose_docroot_url(right: str) -> str:
    doc_root_base_url: str = get_docroot_base_url()
    return f"{doc_root_base_url}/{right}" if doc_root_base_url else None


def get_oauth2_credentials_file_name() -> str:
    return os.path.join(upmplgutils.getcachedir(constants.PluginConstant.PLUGIN_NAME.value), constants.oauth2_credentials_file_name)


def oauth2_credential_file_exists() -> bool:
    return os.path.exists(get_oauth2_credentials_file_name())


def get_pkce_credentials_file_name() -> str:
    return os.path.join(upmplgutils.getcachedir(constants.PluginConstant.PLUGIN_NAME.value), constants.pkce_credentials_file_name)


def pkce_credential_file_exists() -> bool:
    return os.path.exists(get_pkce_credentials_file_name())


def is_instance_of_any(obj: any, type_list: list[type]) -> bool:
    t: type
    for t in type_list if type_list else list():
        if isinstance(obj, t):
            return True
    return False


def get_all_mix_or_playlist_tracks(mix_or_playlist: Union[TidalPlaylist, TidalMix]) -> list[TidalTrack]:
    return (get_all_playlist_tracks(playlist=mix_or_playlist)
            if isinstance(mix_or_playlist, TidalPlaylist)
            else get_all_mix_tracks(mix=mix_or_playlist))


def get_all_playlist_tracks(playlist: TidalPlaylist, max_tracks: int = None) -> list[TidalTrack]:
    result: list[TidalTrack] = []
    offset: int = 0
    default_limit: int = 100
    limit: int = min(default_limit, max_tracks) if max_tracks else default_limit
    finished: bool = False
    while not finished:
        slice: list[TidalTrack] = playlist.items(offset=offset, limit=limit)
        slice_len: int = len(slice) if slice else 0
        offset += slice_len
        finished = slice_len < limit
        item: Union[TidalTrack, TidalVideo]
        for item in slice if slice else []:
            if isinstance(item, TidalTrack):
                result.append(item)
                if max_tracks and len(result) >= max_tracks:
                    break
    return result


def get_albums_from_tracks(track_list: list[TidalTrack]) -> list[TidalAlbum]:
    return list(map(lambda t: t.album, track_list))


def get_artists_from_tracks(track_list: list[TidalTrack]) -> list[TidalArtist]:
    return list(map(lambda t: t.artist, track_list))


def get_all_mix_tracks(mix: TidalMix) -> list[TidalTrack]:
    result: list[TidalTrack] = []
    items: list[TidalTrack] = mix.items()
    item: Union[TidalTrack, TidalVideo]
    for item in items:
        if isinstance(item, TidalTrack):
            result.append(item)
    return result


def create_mix_or_playlist_all_tracks_entry(
        objid: any,
        element_type: ElementType,
        thing_id: str,
        thing: Union[TidalPlaylist, TidalMix],
        all_tracks: list[TidalTrack]) -> dict[str, any]:
    all_tracks_identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ALL_TRACKS_IN_PLAYLIST_OR_MIX.getName(),
        thing_id)
    all_tracks_identifier.set(key=ItemIdentifierKey.UNDERLYING_TYPE, value=element_type.getName())
    all_tracks_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(all_tracks_identifier))
    all_tracks_entry = upmplgutils.direntry(all_tracks_id, objid, "All Tracks")
    select_item: Union[TidalTrack | TidalVideo] = secrets.choice(all_tracks) if all_tracks else None
    msgproc.log(f"create_mix_or_playlist_all_tracks_entry select [{select_item is not None}] "
                f"type [{type(select_item) if select_item else None}]")
    upnp_util.set_album_art_from_uri(
        album_art_uri=get_image_url(select_item),
        target=all_tracks_entry)
    return all_tracks_entry


class PageLinkIdentifier:

    def __init__(self, value: str, api_path: str, category_title: str):
        self.__value: str = value
        self.__api_path: str = api_path
        self.__category_title: str = category_title

    @property
    def value(self) -> str:
        return self.__value

    @property
    def api_path(self) -> str:
        return self.__api_path

    @property
    def category_title(self) -> str:
        return self.__category_title


def get_cached_audio_quality(album_id: str) -> CachedTidalQuality:
    played_track_list: list[PlayedTrack] = persistence.get_played_album_entries(album_id)
    if not played_track_list or len(played_track_list) == 0:
        return None
    # get first
    played_track: PlayedTrack = played_track_list[0]
    # audio_mode: str = played_track.audio_mode
    audio_quality: TidalQuality = played_track.audio_quality
    # audio quality not available? fix when possible
    if not audio_quality:
        # identify hi_res_lossless
        if ((played_track.bit_depth and played_track.bit_depth > 16) and
           (played_track.sample_rate and played_track.sample_rate > 48000)):
            return CachedTidalQuality(
                bit_depth=played_track.bit_depth,
                sample_rate=played_track.sample_rate,
                audio_quality=TidalQuality.hi_res_lossless)
        # identify hi_res
        if played_track.bit_depth and played_track.bit_depth > 16:
            # just hires
            return CachedTidalQuality(
                bit_depth=played_track.bit_depth,
                sample_rate=played_track.sample_rate,
                audio_quality=TidalQuality.hi_res_lossless)
    # catch invalid combinations
    bit_depth: int = played_track.bit_depth
    sample_rate: int = played_track.sample_rate
    if bit_depth == 16 and sample_rate in [44100, 48000]:
        if audio_quality in [TidalQuality.hi_res_lossless]:
            # invalid!
            # reset audio_quality to None to avoid false hires identification
            audio_quality = None
    return CachedTidalQuality(
        bit_depth=bit_depth,
        sample_rate=sample_rate,
        audio_quality=audio_quality)


def get_album_disc_and_track_counters(album: AlbumAdapter) -> str:
    disc_count: int = album.num_volumes
    result: str = (f"{disc_count} Disc{'s' if disc_count > 1 else ''}, "
                   if disc_count and disc_count != -1 else "")
    result += (f"{album.num_tracks} Track{'s' if album.num_tracks > 1 else ''}"
               if album.num_tracks and album.num_tracks != -1 else "")
    return result


def date_to_display(dt: datetime) -> str:
    return f"{dt.year:04d}/{dt.month:02d}/{dt.day:02d}"


def add_album_adapter_metadata(album_adapter: AlbumAdapter, target: dict[str, any]):
    # upv
    universal_product_number: int = album_adapter.universal_product_number
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.UNIVERSAL_PRODUCT_NUMBER, str(universal_product_number), target)
    # artist id
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ARTIST_ID, album_adapter.artist_id, target)
    # album id
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_ID, album_adapter.id, target)
    # album title
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_TITLE, album_adapter.name, target)
    # version
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_VERSION, album_adapter.version, target)
    # explicit
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_EXPLICIT_STATUS, 'yes' if album_adapter.explicit else 'no', target)
    # copyright
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.COPYRIGHT, album_adapter.copyright, target)
    # audio quality
    cached_tidal_quality: CachedTidalQuality = get_cached_audio_quality(
        album_id=album_adapter.id)
    badge: str = get_quality_badge_raw(
        audio_modes=album_adapter.audio_modes,
        media_metadata_tags=album_adapter.media_metadata_tags,
        audio_quality=album_adapter.audio_quality,
        cached_tidal_quality=cached_tidal_quality)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_QUALITY, badge, target)
    # artist names
    artist_names: list[str] = []
    artist_list: list[TidalArtist] = album_adapter.artist_list if album_adapter.artist_list else []
    curr_artist: TidalArtist
    for curr_artist in artist_list:
        artist_names.append(curr_artist.name)
    # only show if this is meaningful
    if len(artist_list) > 1:
        artist_name_list: str = ", ".join(artist_names)
        upnp_util.set_upmpd_meta(
            upmpdmeta.UpMpdMeta.ALBUM_ARTIST,
            artist_name_list,
            target)
        if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
            msgproc.log(f"Artists for [{album_adapter.id}] set to [{artist_name_list}] ...")
    # duration
    duration_sec: int = album_adapter.duration
    if album_adapter.duration and album_adapter.duration != -1:
        upnp_util.set_upmpd_meta(
            upmpdmeta.UpMpdMeta.ALBUM_DURATION,
            upmpdmeta.get_duration_display_from_sec(duration_sec),
            target)
    # disc and tracks
    disc_track_counters: str = get_album_disc_and_track_counters(album_adapter)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_DISC_AND_TRACK_COUNTERS, disc_track_counters, target)
    # available release date
    available_release_date_str: str = date_to_display(album_adapter.available_release_date)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_AVAILABLE_RELEASE_DATE, available_release_date_str, target)
