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


def get_image_dimension_list(obj : any) -> list[int]:
    key = type(obj).__name__
    return default_image_sz_by_type[key] if key in default_image_sz_by_type else list()


def get_name_or_title(obj : any) -> str:
    if hasattr(obj, "name"):
        return obj.name
    if hasattr(obj, "title"):
        return obj.title
    return None


def get_image_url(obj : any) -> str:
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


def try_get_album(tidal_session : TidalSession, album_id : str) -> TidalAlbum:
    album : TidalAlbum = None
    try:
        album = tidal_session.album(album_id)
    except Exception as ex:
        msgproc.log(f"try_get_album failed for album_id [{album_id}] [{type(ex)}] [{ex}]")
    return album


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


def get_listen_queue_playlist(
        tidal_session : TidalSession,
        create_if_missing : bool = False) -> TidalUserPlaylist:
    tidal_session.user.playlists()
    user_playlists : list[TidalUserPlaylist] = tidal_session.user.playlists()
    # look for the first playlist with the configured name
    # if it does not exist, we create it, if we are allowed to
    listen_queue : TidalUserPlaylist = None
    current : TidalUserPlaylist
    for current in user_playlists if user_playlists else list():
        # msgproc.log(f"get_listen_queue_playlist processing [{current.name}]")
        if current.name == config.listen_queue_playlist_name:
            listen_queue = current
            break
    if not listen_queue and create_if_missing:
        # we create the playlist
        listen_queue = tidal_session.user.create_playlist(config.listen_queue_playlist_name)
    return listen_queue


def is_album_in_listen_queue(tidal_session : TidalSession, album_id : str) -> bool:
    listen_queue : TidalUserPlaylist = get_listen_queue_playlist(tidal_session=tidal_session)
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


def album_listen_queue_action(
        tidal_session : TidalSession,
        album_id : str,
        action : str) -> TidalAlbum:
    listen_queue : TidalUserPlaylist = get_listen_queue_playlist(
        tidal_session=tidal_session,
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
    if constants.listen_queue_action_add == action:
        # add the album tracks
        t : TidalTrack
        for t in album.tracks():
            listen_queue.add([t.id])
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


def get_quality_badge(
        album : TidalAlbum,
        cached_tidal_quality : CachedTidalQuality) -> str:
    audio_modes : list[str] = album.audio_modes
    # TODO maybe map DOLBY_ATMOS to say Atmos
    if audio_modes and audio_modes[0] != "STEREO": return audio_modes[0]
    media_metadata_tags : list[str] = album.media_metadata_tags
    tidal_quality : TidalQuality = __get_best_quality(media_metadata_tags)
    is_mqa : bool = __is_mqa(media_metadata_tags)
    if not tidal_quality: tidal_quality = album.audio_quality
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
    msgproc.log(f"get_quality_badge q:[{tidal_quality}] "
                f"b:[{bit_depth}] "
                f"s:[{sample_rate}] "
                f"mqa:[{is_mqa}] -> [{badge}]")
    return badge


def track_only(obj : any) -> any:
    if obj and isinstance(obj, TidalTrack): return obj


def load_unique_ids_from_mix_or_playlist(
        tidal_session : TidalSession,
        mix_or_playlist_id : str,
        tidal_obj_extractor : Callable[[TidalSession, str], TidalPlaylist | TidalMix],
        item_extractor : Callable[[any, int, int], list[any]],
        id_extractor : Callable[[any], str],
        max_id_list_length : int,
        previous_page_last_found_id : str = None,
        item_filter : Callable[[any], any] = lambda x : track_only(x),
        initial_offset : int = 0,
        max_slice_size : int = 100) -> tuple[list[str], int]:
    tidal_obj = tidal_obj_extractor(tidal_session, mix_or_playlist_id)
    last_offset : int = initial_offset
    id_list : list[str] = list()
    load_count : int = 0
    skip_count : int = 0
    finished : bool = False
    last_found : str = None
    while len(id_list) < max_id_list_length:
        max_loadable : int = max_slice_size
        msgproc.log(f"load_mix_or_playlist_tracks mix_or_pl [{mix_or_playlist_id}] "
                    f"loading [{max_loadable}] from offset [{last_offset}] "
                    f"load_count [{load_count}] skip_count [{skip_count}] ...")
        item_list : list[any] = item_extractor(tidal_obj, max_slice_size, last_offset)
        if not item_list or len(item_list) == 0:
            # no items, we are finished
            finished = True
            break
        slice_count : int = 0
        for i in item_list:
            slice_count += 1
            last_offset += 1
            item = item_filter(i) if item_filter else i
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
