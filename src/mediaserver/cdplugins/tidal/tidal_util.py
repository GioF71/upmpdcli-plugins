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
import config
import requests
import os
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
from typing import Callable

from element_type import ElementType
from element_type import get_element_type_by_name

from album_sort_criteria import AlbumSortCriteria

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

log_unavailable_images_sizes : bool = (upmplgutils.getOptionValue(
    f"{constants.plugin_name}log_unavailable_images_sizes",
    "0") == "1")
log_unavailable_image : bool = upmplgutils.getOptionValue(f"{constants.plugin_name}log_unavailable_image", "0") == "1"

default_image_sz_by_type : dict[str, int] = dict()
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
        obj : FavoriteAlbumsMode = FavoriteAlbumsMode()
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


def get_image_dimension_list(obj : any) -> list[int]:
    key = type(obj).__name__
    return default_image_sz_by_type[key] if key in default_image_sz_by_type else list()


def get_name_or_title(obj : any) -> str:
    if hasattr(obj, "name"):
        return obj.name
    if hasattr(obj, "title"):
        return obj.title
    return None


def set_album_art_from_album_id(album_id: str, tidal_session: TidalSession, entry: dict):
    album_art_url: str = get_album_url_by_id(album_id=album_id, tidal_session=tidal_session)
    upnp_util.set_album_art_from_uri(album_art_url, entry)


def get_album_url_by_id(album_id: str, tidal_session: TidalSession) -> str:
    if config.enable_image_caching:
        # try cached!
        document_root_dir : str = upmplgutils.getOptionValue("webserverdocumentroot")
        if document_root_dir:
            sub_dir_list: list[str] = [constants.plugin_name, "images", TidalAlbum.__name__]
            image_dir: str = ensure_directory(document_root_dir, sub_dir_list)
            cached_file_name: str = f"{str(album_id)}.jpg"
            cached_file: str = os.path.join(image_dir, cached_file_name)
            if os.path.exists(cached_file):
                # use cached file
                path: list[str] = list()
                path.extend(sub_dir_list)
                path.append(cached_file_name)
                cached_image_url: str = compose_docroot_url("/".join(path))
                # msgproc.log(f"get_album_url_by_id returning [{cached_image_url}] for [{album_id}]")
                return cached_image_url
    # if we are are, we fallback to normal
    # msgproc.log(f"get_album_url_by_id returning falling back for [{album_id}]")
    album: TidalAlbum = try_get_album(album_id=album_id, tidal_session=tidal_session)
    return get_image_url(obj=album)


def get_image_url(obj : any, refresh: bool = False) -> str:
    if not config.enable_image_caching: return __get_image_url(obj)
    document_root_dir : str = upmplgutils.getOptionValue("webserverdocumentroot")
    # webserverdocumentroot is required
    if not document_root_dir: return __get_image_url(obj)
    if type(obj) not in [TidalAlbum, TidalArtist]:
        return __get_image_url(obj)
    sub_dir_list : list[str] = [constants.plugin_name, "images", type(obj).__name__]
    image_dir : str = ensure_directory(document_root_dir, sub_dir_list)
    cached_file_name: str = f"{str(obj.id)}.jpg"
    cached_file: str = os.path.join(image_dir, cached_file_name)
    if refresh or not os.path.exists(cached_file):
        image_url : str = __get_image_url(obj=obj)
        # msgproc.log(f"get_image_url saving to [{image_dir}] [{dest_file}]")
        img_data : bytes = requests.get(image_url).content
        with open(cached_file, 'wb') as handler:
            handler.write(img_data)
    path : list[str] = list()
    path.extend(sub_dir_list)
    path.append(cached_file_name)
    cached_image_url: str = compose_docroot_url("/".join(path))
    return cached_image_url


def __get_image_url(obj : any) -> str:
    dimension_list : list[int] = get_image_dimension_list(obj)
    if not dimension_list or len(dimension_list) == 0:
        msgproc.log(f"Type [{type(obj).__name__}] does not have an image sizes list!")
        return None
    current : int
    for current in dimension_list if dimension_list else list():
        try:
            return obj.image(dimensions = current)
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


def is_mp3(q : TidalQuality) -> bool:
    return q == TidalQuality.low_320k or q == TidalQuality.low_96k


def get_mime_type(track_quality : TidalQuality) -> str:
    if is_mp3(track_quality):
        return "audio/mp3"
    else:
        return "audio/flac"


def is_multidisc_album(album : TidalAlbum) -> bool:
    return album.num_volumes and album.num_volumes > 1


def try_get_track(tidal_session : TidalSession, track_id : str) -> TidalTrack:
    track : TidalTrack = None
    try:
        track = tidal_session.track(track_id)
    except Exception as ex:
        msgproc.log(f"try_get_track failed for track_id [{track_id}] [{type(ex)}] [{ex}]")
    return track


def try_get_album(tidal_session : TidalSession, album_id : str) -> TidalAlbum:
    album : TidalAlbum = None
    try:
        album = tidal_session.album(album_id)
    except Exception as ex:
        msgproc.log(f"try_get_album failed for album_id [{album_id}] [{type(ex)}] [{ex}]")
    return album


def try_get_artist(tidal_session : TidalSession, artist_id : str) -> TidalArtist:
    artist : TidalArtist = None
    try:
        artist = tidal_session.artist(artist_id)
    except Exception as ex:
        msgproc.log(f"try_get_artist failed for artist_id [{artist_id}] [{type(ex)}] [{ex}]")
    return artist


class CachedTidalQuality:

    def __init__(
            self,
            bit_depth : int,
            sample_rate : int,
            audio_quality : TidalQuality,
            audio_mode : str = None):
        self._bit_depth : int = bit_depth
        self._sample_rate : int = sample_rate
        self._audio_quality : TidalQuality = audio_quality
        self._audio_mode : str = audio_mode

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


__readable_sr : dict[int, str] = {
    44100: "44.1",
    48000: "48",
    88200: "88.2",
    96000: "96",
    176400: "176.4",
    192000: "192"
}


def __readable_sample_rate(sample_rate : int) -> str:
    if sample_rate in __readable_sr:
        return __readable_sr[sample_rate]
    return None


def get_playlist_by_name(
        tidal_session : TidalSession,
        playlist_name : str,
        create_if_missing : bool = False) -> TidalUserPlaylist:
    tidal_session.user.playlists()
    user_playlists : list[TidalUserPlaylist] = tidal_session.user.playlists()
    # look for the first playlist with the configured name
    # if it does not exist, we create it, if we are allowed to
    listen_queue : TidalUserPlaylist = None
    current : TidalUserPlaylist
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
        tidal_session : TidalSession,
        album_id : str,
        playlist_name : str) -> bool:
    listen_queue : TidalUserPlaylist = get_playlist_by_name(
        tidal_session=tidal_session,
        playlist_name=playlist_name)
    if not listen_queue:
        msgproc.log(f"is_album_in_listen_queue for album_id [{album_id}] -> "
                    f"playlist [{config.listen_queue_playlist_name}] not found")
        return False
    # if we find a track from that album, we return True
    offset : int = 0
    limit : int = 100
    while True:
        item_list : list = listen_queue.items(offset = offset, limit = limit)
        msgproc.log(f"Getting [{len(item_list) if item_list else 0}] from playlist "
                    f"[{config.listen_queue_playlist_name}] from offset [{offset}]")
        if not item_list or len(item_list) == 0:
            # we are finished
            # msgproc.log(f"No more items from offset [{offset}], we are finished")
            break
        count : int = 0
        for current in item_list if item_list else list():
            count += 1
            # must be a track
            if not isinstance(current, TidalTrack): continue
            track : TidalTrack = current
            if track.album.id == album_id:
                # msgproc.log(f"Found track [{track.id}] from album [{album_id}], returning True")
                return True
        if count < limit:
            # msgproc.log(f"Found [{count}] instead of [{limit}] from offset [{offset}], we are finished")
            break
        offset += limit
    return False


def album_playlist_action(
        tidal_session : TidalSession,
        album_id : str,
        playlist_name : str,
        action : str) -> TidalAlbum:
    listen_queue : TidalUserPlaylist = get_playlist_by_name(
        tidal_session=tidal_session,
        playlist_name=playlist_name,
        create_if_missing=True)
    # remove anyway, add to the end if action is add
    remove_list : list[str] = list()
    offset : int = 0
    limit : int = 100
    while True:
        item_list : list = listen_queue.items(offset = offset, limit = limit)
        # msgproc.log(f"Getting [{len(item_list) if item_list else 0}] from playlist "
        #             f"[{config.listen_queue_playlist_name}] from offset [{offset}]")
        if not item_list or len(item_list) == 0:
            # we are finished
            msgproc.log(f"No more items from offset [{offset}], we are finished")
            break
        count : int = 0
        for current in item_list:
            count += 1
            # must be a track
            if not isinstance(current, TidalTrack): continue
            track : TidalTrack = current
            if track.album.id == album_id:
                # msgproc.log(f"Found track [{track.id}] from album [{album_id}], returning True")
                remove_list.append(track.id)
        if count < limit:
            # msgproc.log(f"Found [{count}] instead of [{limit}] from offset [{offset}], we are finished")
            break
        offset += limit
    for track_id in remove_list:
        listen_queue.remove_by_id(media_id=track_id)
    album : TidalAlbum = tidal_session.album(album_id = album_id)
    # add if needed
    if constants.listening_queue_action_add == action:
        # add the album tracks
        media_id_list : list[str] = list()
        t : TidalTrack
        for t in album.tracks():
            media_id_list.append(t.id)
        listen_queue.add(media_id_list)
    return album


def is_stereo(album : TidalAlbum) -> bool:
    # missing -> assume STEREO
    media_metadata_tags : list[str] = album.media_metadata_tags
    if not media_metadata_tags or len(media_metadata_tags) == 0: return True
    return (TidalMediaMetadataTags.sony_360 not in media_metadata_tags and
            TidalMediaMetadataTags.dolby_atmos not in media_metadata_tags)


def not_stereo_skipmessage(album : TidalAlbum) -> str:
    return f"Skipping album with id [{album.id}] because [{album.media_metadata_tags}]"


def __is_mqa(media_metadata_tags : list[str]) -> bool:
    if not media_metadata_tags or len(media_metadata_tags) == 0: return False
    return TidalMediaMetadataTags.mqa in media_metadata_tags


def __get_best_quality(media_metadata_tags : list[str]) -> str:
    if not media_metadata_tags or len(media_metadata_tags) == 0: return None
    if TidalMediaMetadataTags.hires_lossless in media_metadata_tags: return TidalQuality.hi_res_lossless
    if TidalMediaMetadataTags.mqa in media_metadata_tags: return TidalQuality.hi_res
    if TidalMediaMetadataTags.lossless in media_metadata_tags: return TidalQuality.high_lossless
    if TidalMediaMetadataTags.sony_360 in media_metadata_tags: return TidalQuality.low_96k
    if TidalMediaMetadataTags.dolby_atmos in media_metadata_tags: return TidalQuality.low_96k
    return None


def try_get_all_favorites(tidal_session: TidalSession) -> list[TidalAlbum]:
    favorite_list: list[TidalAlbum] = list()
    offset : int = 0
    limit : int = 100
    while True:
        some : list[TidalAlbum] = None
        try:
            some : list[TidalAlbum] = tidal_session.user.favorites.albums(limit=limit, offset=offset)
        except Exception as ex:
            msg: str = f"Cannot get favorite albums from offset [{offset}] [{type(ex)}] [{ex}]"
            raise Exception(msg)
        some_len: int = len(some) if some else 0
        if some_len > 0: favorite_list.extend(some)
        if some_len < limit:
            break
        # another slice maybe
        offset += limit
    return favorite_list


def get_quality_badge(
        album : TidalAlbum,
        cached_tidal_quality : CachedTidalQuality) -> str:
    return get_quality_badge_raw(
        audio_modes=album.audio_modes,
        media_metadata_tags=album.media_metadata_tags,
        audio_quality=album.audio_quality,
        cached_tidal_quality=cached_tidal_quality)


def get_quality_badge_raw(
        audio_modes : list[str],
        media_metadata_tags: list[str],
        audio_quality : str,
        cached_tidal_quality : CachedTidalQuality) -> str:
    # msgproc.log(f"get_quality_badge type(audio_modes) -> {type(audio_modes) if audio_modes else 'none'}")
    # TODO maybe map DOLBY_ATMOS to say Atmos
    if audio_modes and audio_modes[0] != "STEREO": return audio_modes[0]
    tidal_quality : TidalQuality = __get_best_quality(media_metadata_tags)
    is_mqa : bool = __is_mqa(media_metadata_tags)
    if not tidal_quality: tidal_quality = audio_quality
    stream_info_available : bool = (cached_tidal_quality and
                cached_tidal_quality.bit_depth and
                cached_tidal_quality.sample_rate)
    bit_depth : int = cached_tidal_quality.bit_depth if cached_tidal_quality else None
    sample_rate : int = cached_tidal_quality.sample_rate if cached_tidal_quality else None
    ext_badge : str = (f"{bit_depth}/{__readable_sample_rate(sample_rate)}"
                       if stream_info_available else None)
    badge : str = None
    if is_mqa:
        if not stream_info_available:
            badge = "MQA"
        else:
            if bit_depth == 16 and sample_rate == 44100:
                badge = "MQA CD"
            elif bit_depth == 16 and sample_rate == 48000:
                badge = "MQA 16/48"
            else:
                badge = f"MQA {ext_badge}"
        return badge
    if TidalQuality.hi_res_lossless == tidal_quality:
        badge = f"HD {ext_badge}" if ext_badge else "MAX"
    elif TidalQuality.hi_res == tidal_quality:
        badge = f"HD {ext_badge}" if ext_badge else "HD"
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
                    f"s:[{sample_rate}] "
                    f"mqa:[{is_mqa}] -> [{badge}]")
    return badge


def track_only(obj : any) -> any:
    if obj and isinstance(obj, TidalTrack): return obj


def get_mix_or_playlist_items(
        tidal_session : TidalSession,
        tidal_obj_id : str,
        obj_type : str,
        limit : int,
        offset : int) -> list[any]:
    underlying_type : ElementType = get_element_type_by_name(element_name = obj_type)
    if underlying_type == ElementType.PLAYLIST:
        playlist : TidalPlaylist = tidal_session.playlist(tidal_obj_id)
        return playlist.tracks(limit = limit, offset = offset)
    elif underlying_type == ElementType.MIX:
        mix : TidalMix = tidal_session.mix(tidal_obj_id)
        items : list[any] = mix.items()
        items = items if items else list()
        sz : int = len(items)
        if offset >= sz: return list()
        if offset + limit > sz:
            # reduce limit
            limit = sz - offset
        return items[offset:offset + limit]
    else: raise Exception(f"Invalid type [{obj_type}]")


def load_unique_ids_from_mix_or_playlist(
        tidal_session : TidalSession,
        tidal_obj_id : str,
        tidal_obj_type : str,
        id_extractor : Callable[[any], str],
        max_id_list_length : int,
        previous_page_last_found_id : str = None,
        item_filter : Callable[[any], any] = lambda x : track_only(x),
        initial_offset : int = 0,
        max_slice_size : int = 100) -> tuple[list[str], int]:
    # msgproc.log(f"load_unique_ids_from_mix_or_playlist mix_or_playlist_id [{tidal_obj_id}] "
    #             f"tidal_obj_type [{tidal_obj_type}] "
    #             f"initial_offset [{initial_offset}] max_slice_size [{max_slice_size}]")
    last_offset : int = initial_offset
    id_list : list[str] = list()
    load_count : int = 0
    skip_count : int = 0
    finished : bool = False
    last_found : str = None
    while len(id_list) < max_id_list_length:
        max_loadable : int = max_slice_size
        msgproc.log(f"load_unique_ids_from_mix_or_playlist mix_or_pl [{tidal_obj_id}] "
                    f"tidal_obj_type [{tidal_obj_type}] "
                    f"loading [{max_loadable}] from offset [{last_offset}] "
                    f"load_count [{load_count}] skip_count [{skip_count}] ...")
        item_list : list[any] = get_mix_or_playlist_items(
            tidal_session = tidal_session,
            tidal_obj_id = tidal_obj_id,
            obj_type = tidal_obj_type,
            limit = max_slice_size,
            offset = last_offset)
        if not item_list or len(item_list) == 0:
            # no items, we are finished
            finished = True
            break
        slice_count : int = 0
        for i in item_list:
            slice_count += 1
            last_offset += 1
            item = item_filter(i) if item_filter is not None else i
            if item:
                id_value : str = id_extractor(item)
                # already collected?
                if (id_value and
                    (not previous_page_last_found_id or id_value != previous_page_last_found_id) and
                        (id_value not in id_list)):
                    id_list.append(id_value)
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
    return id_list, last_offset, finished, last_found


def ensure_directory(base_dir : str, sub_dir_list : list[str]) -> str:
    curr_sub_dir : str
    curr_dir : str = base_dir
    for curr_sub_dir in sub_dir_list:
        new_dir : str = os.path.join(curr_dir, curr_sub_dir)
        # msgproc.log(f"checking dir [{new_dir}] ...")
        if not os.path.exists(new_dir):
            msgproc.log(f"creating dir [{new_dir}] ...")
            os.mkdir(new_dir)
        # else:
        #     msgproc.log(f"dir [{new_dir}] already exists.")
        curr_dir = new_dir
    return curr_dir


def compose_docroot_url(right : str) -> str:
    host_port : str = os.environ['UPMPD_UPNPHOSTPORT']
    doc_root : str = os.environ['UPMPD_UPNPDOCROOT']
    if not host_port and not doc_root: return None
    return f"http://{host_port}/{right}"


def get_oauth2_credentials_file_name() -> str:
    return os.path.join(upmplgutils.getcachedir(constants.plugin_name), constants.oauth2_credentials_file_name)


def oauth2_credential_file_exists() -> bool:
    return os.path.exists(get_oauth2_credentials_file_name())


def get_pkce_credentials_file_name() -> str:
    return os.path.join(upmplgutils.getcachedir(constants.plugin_name), constants.pkce_credentials_file_name)


def pkce_credential_file_exists() -> bool:
    return os.path.exists(get_pkce_credentials_file_name())
