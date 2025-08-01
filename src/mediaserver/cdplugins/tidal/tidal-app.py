#!/usr/bin/env python3

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

import json
import os
import datetime
import time
import random
import secrets
import glob
import shutil

from typing import Callable
from typing import Union
from typing import Optional
from pathlib import Path

import cmdtalkplugin
import upmplgutils
import html
import pathlib
import re

import codec
import identifier_util
import upnp_util
import constants
import config
import persistence
import tidal_util

from tidal_util import FavoriteAlbumsMode

from tag_type import TagType
from tag_type import get_tidal_tag_type_by_name
from element_type import ElementType
from element_type import get_element_type_by_name
from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey
from option_key import OptionKey
from search_type import SearchType
from tile_type import TileType
from context import Context
from context_key import ContextKey

from tidalapi import Quality as TidalQuality
from tidalapi.session import Session as TidalSession
from tidalapi.album import Album as TidalAlbum
from tidalapi.artist import Artist as TidalArtist
from tidalapi.mix import Mix as TidalMix
from tidalapi.playlist import Playlist as TidalPlaylist
from tidalapi.playlist import UserPlaylist as TidalUserPlaylist
from tidalapi.media import Track as TidalTrack
from tidalapi.media import Video as TidalVideo
from tidalapi.media import AudioMode as TidalAudioMode
from tidalapi.page import Page as TidalPage
from tidalapi.page import PageItem as TidalPageItem
from tidalapi.page import ItemList as TidalItemList
from tidalapi.page import PageLink as TidalPageLink
from tidalapi.page import FeaturedItems as TidalFeaturedItems

from track_adapter import TrackAdapter
from tidal_track_adapter import TidalTrackAdapter
from played_track_adapter import PlayedTrackAdapter
from album_adapter import AlbumAdapter, tidal_album_to_adapter, album_adapter_by_album_id

from played_track import PlayedTrack
from played_album import PlayedAlbum
from played_track_request import PlayedTrackRequest
from tile_image import TileImage

from album_sort_criteria import AlbumSortCriteria
from artist_sort_criteria import ArtistSortCriteria

from functools import cmp_to_key

from streaming_info import StreamingInfo
from tidal_page_definition import TidalPageDefinition


static_images_dict: dict[str, list[str]] = {}


class SessionStatus:

    def __init__(self, tidal_session: TidalSession):
        self.update(tidal_session)

    @property
    def tidal_session(self) -> TidalSession:
        return self._tidal_session

    @property
    def update_time(self) -> datetime.datetime:
        return self._update_time

    def update(self, tidal_session: TidalSession):
        self._tidal_session: TidalSession = tidal_session
        self._update_time: datetime.datetime = datetime.datetime.now()


# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = f"0${constants.PluginConstant.PLUGIN_NAME.value}$"
upmplgutils.setidprefix(constants.PluginConstant.PLUGIN_NAME.value)

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


def album_retriever(tidal_session: TidalSession, album_id: str) -> TidalAlbum:
    return tidal_session.album(album_id)


def instance_tidal_track_adapter(
        tidal_session: TidalSession,
        track: TidalTrack) -> TidalTrackAdapter:
    return TidalTrackAdapter(
        tidal_session=tidal_session,
        track=track,
        album_retriever=album_retriever)


def has_type_attr(obj: any) -> str:
    if hasattr(obj, "type"):
        return True
    return False


def has_image_method(obj: any) -> str:
    if hasattr(obj, "image") and callable(obj.image):
        return True
    return False


def get_image_if_available(obj: any) -> str:
    if hasattr(obj, "image"):
        return obj.image
    return None


def safe_get_image_url(obj: any) -> str:
    return tidal_util.get_image_url(obj) if has_image_method(obj) else None


def guess_bit_depth(audio_quality: str = None, sample_rate: int = None) -> int:
    bit_depth: int = __guess_bit_depth(audio_quality=audio_quality, sample_rate=sample_rate)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"guess_bit_depth audio_quality=[{audio_quality}] sample_rate=[{sample_rate}] "
                    f"-> guessed bit_depth=[{bit_depth}]")
    return bit_depth


def __guess_bit_depth(audio_quality: str = None, sample_rate: int = None) -> int:
    # audio quality is the first choice
    if audio_quality:
        # use audio quality for guessing
        if audio_quality in [TidalQuality.hi_res_lossless]:
            return 24
    if sample_rate:
        # use sample rate for guessing hi-res content...
        if sample_rate >= 48000:
            return 24
    # fallback from config
    return 24 if config.get_config_param_as_str(constants.ConfigParam.AUDIO_QUALITY) in [TidalQuality.hi_res_lossless] else 16


def mp3_only() -> bool:
    q: TidalQuality = config.get_config_param_as_str(constants.ConfigParam.AUDIO_QUALITY)
    return tidal_util.is_mp3(q)


def build_session(audio_quality: str = config.get_config_param_as_str(constants.ConfigParam.AUDIO_QUALITY)) -> TidalSession:
    pkce_file_available: bool = tidal_util.pkce_credential_file_exists()
    oauth2_file_available: bool = tidal_util.oauth2_credential_file_exists()
    use_pkce: bool = pkce_file_available and not oauth2_file_available
    # msgproc.log(f"pkce_file_available [{pkce_file_available}] "
    #             f"oauth2_file_available [{oauth2_file_available}] "
    #             f"-> use_pkce [{use_pkce}]")
    session: TidalSession = TidalSession()
    if config.get_override_country_code():
        session.country_code = config.get_override_country_code()
        # msgproc.log(f"build_session creating a new session using country code [{session.country_code}] ...")
    if use_pkce:
        # msgproc.log(f"PKCE file [{tidal_util.get_pkce_credentials_file_name()}] available, building a new session ...")
        # return pkce session
        session_file = Path(tidal_util.get_pkce_credentials_file_name())
        # Load session from file; create a new session if necessary
        res: bool = session.login_session_file(session_file, do_pkce=True, fn_print=msgproc.log)
        if not res:
            msgproc.log("build pkce session failed")
            return None
        session.audio_quality = audio_quality
        # msgproc.log(f"Built a pkce session successfully, using audio_quality [{session.audio_quality}]")
        return session
    else:
        # msgproc.log(f"OAUTH2 file [{tidal_util.get_oauth2_credentials_file_name()}] "
        #             f"available [{oauth2_file_available}], building a new session ...")
        # return pkce session
        session_file = Path(tidal_util.get_oauth2_credentials_file_name())
        # Load session from file; create a new session if necessary
        res: bool = session.login_session_file(session_file, do_pkce=False, fn_print=msgproc.log)
        if not res:
            msgproc.log("build oauth2 session failed")
            return None
        session.audio_quality = audio_quality
        # msgproc.log(f"Built a oauth2 session successfully, using audio_quality [{session.audio_quality}]")
        return session


def get_session() -> TidalSession:
    return build_session()


def build_intermediate_url(track_id: str) -> str:
    http_host_port = os.environ["UPMPD_HTTPHOSTPORT"]
    url = f"http://{http_host_port}/{constants.PluginConstant.PLUGIN_NAME.value}/track/version/1/trackId/{track_id}"
    if config.log_intermediate_url:
        msgproc.log(f"intermediate_url for track_id {track_id} -> [{url}]")
    return url


def remove_older_files(files_path: str, delta_sec: int):
    now = time.time()
    for f in os.listdir(files_path):
        # msgproc.log(f"Found [{files_path}] [{f}]")
        if os.stat(os.path.join(files_path, f)).st_mtime < (now - delta_sec):
            # msgproc.log(f"Deleting file: [{os.path.join(files_path, f)}]")
            os.remove(os.path.join(files_path, f))


def try_get_stream(track: TidalTrack):
    try:
        return track.get_stream()
    except Exception as ex:
        msgproc.log(f"Cannot get stream for track [{track.id}] due to [{type(ex)}] [{ex}]")


def build_streaming_url(tidal_session: TidalSession, track: TidalTrack) -> StreamingInfo:
    track_id: str = track.id
    streaming_url: str = None
    document_root_dir: str = config.getWebServerDocumentRoot()
    stream = try_get_stream(track)
    if not stream:
        msgproc.log(f"build_streaming_url failed for track [{track.id}]")
        return None
    quality: TidalQuality = stream.audio_quality
    audio_mode: str = stream.audio_mode
    bit_depth = stream.bit_depth
    sample_rate = stream.sample_rate
    mimetype: str = stream.manifest_mime_type
    manifest = stream.get_stream_manifest()
    codecs: any = manifest.get_codecs()
    urls_available: bool = manifest.get_urls() is not None
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"build_streaming_url "
                    f"serve_mode [{config.serve_mode}] "
                    f"track_id [{track_id}] title:[{track.name}] "
                    f"from [{track.album.name}] [{track.album.id}] by [{track.album.name}] "
                    f"session_quality:[{tidal_session.audio_quality}] "
                    f"is_pkce [{tidal_session.is_pkce}] "
                    f"bit_depth [{bit_depth}] "
                    f"sample_rate [{sample_rate}] "
                    f"audio_mode [{audio_mode}] "
                    f"is_mpd [{stream.is_mpd}] "
                    f"is_bts [{stream.is_bts}] "
                    f"urls_available [{urls_available}]")
    if stream.is_mpd:
        data: any = None
        file_ext: str
        file_dir: str
        if "hls" == config.serve_mode:
            file_ext = "m3u8"
            file_dir = "m3u8-files"
            data = manifest.get_hls()
        elif "mpd" == config.serve_mode:
            file_ext = "mpd"
            file_dir = "mpd-files"
            data = stream.get_manifest_data()
        else:
            raise Exception(f"Invalid serve_mode: [{config.serve_mode}]")
        sub_dir_list: list[str] = [constants.PluginConstant.PLUGIN_NAME.value, file_dir]
        write_dir: str = tidal_util.ensure_directory(document_root_dir, sub_dir_list)
        file_name: str = "dash_{}.{}".format(track.id, file_ext)
        with open(os.path.join(write_dir, file_name), "w") as my_file:
            my_file.write(data)
            if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_DUMP_STREAM_DATA):
                msgproc.log(f"data=[{data}]")
        remove_older_files(files_path=write_dir, delta_sec=config.max_file_age_seconds)
        path: list[str] = list()
        path.extend([constants.PluginConstant.PLUGIN_NAME.value, file_dir])
        path.append(file_name)
        streaming_url = tidal_util.compose_docroot_url(os.path.join(*path))
    elif stream.is_bts:
        if not urls_available:
            raise Exception(f"Stream is BTS but urls are not available for track_id [{track_id}]")
        streaming_url = manifest.get_urls()
        if isinstance(streaming_url, list):
            if len(streaming_url) == 1:
                streaming_url = streaming_url[0]
            else:
                raise Exception(f"Invalid length from get_urls(), expected 1, got [{len(streaming_url)}]")
        else:
            raise Exception("Expecting a list from get_urls from mainfest of type bts, "
                            f"got a [{type(streaming_url) if streaming_url else 'None'}]")
    else:
        raise Exception(f"Unrecognized stream type for track_id [{track_id}]")
    result: StreamingInfo = StreamingInfo()
    result.url = streaming_url
    result.mimetype = mimetype
    result.codecs = codecs
    result.sample_rate = sample_rate
    result.audio_quality = quality
    result.audio_mode = audio_mode
    result.bit_depth = bit_depth
    msgproc.log(f"build_streaming_url for track_id: [{track_id}] [{track.name}] "
                f"from [{track.album.name if track.album else ''}] "
                f"[{track.album.id if track.album else ''}] by "
                f"[{track.artist.name if track.artist else ''}] -> "
                f"serve_mode [{config.serve_mode}] "
                f"session_quality [{tidal_session.audio_quality}] "
                f"is_pkce [{tidal_session.is_pkce}] "
                f"streamtype [{'mpd' if stream.is_mpd else 'bts'}] title [{track.name}] "
                f"[{streaming_url}] Q:[{quality}] M:[{audio_mode}] "
                f"MT:[{mimetype}] Codecs:[{codecs}] "
                f"SR:[{sample_rate}] BD:[{bit_depth}]")
    return result


def calc_bitrate(tidal_quality: TidalQuality, bit_depth: int, sample_rate: int) -> int:
    if tidal_util.is_mp3(tidal_quality):
        return 320 if TidalQuality.low_320k == tidal_quality else 96
    if bit_depth and sample_rate:
        return int((2 * bit_depth * sample_rate) / 1000)
    else:
        # fallback to redbook (might be wrong!)
        return 1411


class TrackUriEntry:

    def __init__(self, media_url: str):
        self.__media_url: str = media_url
        self.__creation_time: float = time.time()

    @property
    def media_url(self) -> str:
        return self.__media_url

    @property
    def creation_time(self) -> time:
        return self.__creation_time


track_uri_cache: dict[tuple[str, str], TrackUriEntry] = {}


def track_uri_entry_too_old(entry: TrackUriEntry, max_duration_sec: int) -> bool:
    now: float = time.time()
    diff: float = now - entry.creation_time
    if diff > max_duration_sec:
        return True
    return False


def track_uri_purge_old():
    max_duration_sec: int = config.get_config_param_as_int(constants.ConfigParam.TRACK_URI_ENTRY_EXPIRATION_SEC)
    to_purge_list: list[str] = list()
    k: str
    v: TrackUriEntry
    for k, v in track_uri_cache.items():
        # too old? add to purge list
        if track_uri_entry_too_old(v, max_duration_sec):
            to_purge_list.append(k)
    to_purge: any
    for to_purge in to_purge_list:
        del track_uri_cache[to_purge]


def get_cached_track_uri_entry(track_id: str, tidal_quality: str) -> TrackUriEntry:
    track_uri_purge_old()
    return track_uri_cache[(track_id, tidal_quality)] if (track_id, tidal_quality) in track_uri_cache else None


@dispatcher.record('trackuri')
def trackuri(a):
    upmpd_pathprefix = os.environ["UPMPD_PATHPREFIX"]
    track_id: str = upmplgutils.trackid_from_urlpath(upmpd_pathprefix, a)
    # trackuri validation
    if not track_id or not re.match(config.get_config_param_as_str(constants.ConfigParam.TRACK_ID_REGEX), track_id):
        msgproc.log(f"trackuri: invalid track_id [{track_id}]")
        return {}
    user_agent_whitelist_enabled: bool = config.get_config_param_as_bool(constants.ConfigParam.ENABLE_USER_AGENT_WHITELIST)
    msgproc.log(f"trackuri: path_prefix: [{upmpd_pathprefix}] a: [{a}] track_id: [{track_id}] "
                f"user_agent_whitelist_enabled: [{'yes' if user_agent_whitelist_enabled else 'no'}]")
    whitelisted: bool = True if not user_agent_whitelist_enabled else False
    max_audio_quality: str = config.get_config_param_as_str(constants.ConfigParam.AUDIO_QUALITY)
    select_audio_quality: str = max_audio_quality
    if (config.get_config_param_as_bool(constants.ConfigParam.ENABLE_USER_AGENT_WHITELIST) and
            max_audio_quality == TidalQuality.hi_res_lossless):
        # quality is dropped to TidalQuality.high_lossless if there is no match
        select_audio_quality = TidalQuality.high_lossless
        user_agent: str = a['user-agent'] if 'user-agent' in a else ""
        if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
            msgproc.log(f"Configured max quality is [{max_audio_quality}], "
                        f"applying whitelist on useragent [{user_agent}] ...")
        if user_agent is not None and len(user_agent) > 0:
            current: constants.UserAgentHiResWhitelist
            for current in constants.UserAgentHiResWhitelist:
                if user_agent and current.value.matcher(user_agent, current.user_agent_str):
                    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
                        msgproc.log(f"User Agent [{user_agent}] is in whitelist because of match with [{current.name}] "
                                    f"[{', '.join(current.device_list)}]")
                    whitelisted = True
                    # we can use max_audio_quality!
                    select_audio_quality = max_audio_quality
                    break
        else:
            if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
                msgproc.log("Empty user agent, no match.")
        msgproc.log(f"User Agent [{user_agent}] is whitelisted: [{whitelisted}] "
                    f"select_audio_quality: [{select_audio_quality}]")
    # we get a regular session if there is a match, otherwise we build a session with lower quality
    cached_entry: TrackUriEntry = get_cached_track_uri_entry(track_id, select_audio_quality)
    if cached_entry:
        msgproc.log(f"Returning cached media_url for track_id [{track_id}] "
                    f"quality [{select_audio_quality}]")
        return {"media_url": cached_entry.media_url}
    tidal_session: TidalSession = get_session() if whitelisted else build_session(audio_quality=select_audio_quality)
    tidal_track: TidalTrack
    ex: Exception
    tidal_track, ex = tidal_util.try_get_track(tidal_session=tidal_session, track_id=track_id)
    if not tidal_track:
        # cannot load track?
        msgproc.log(f"Cannot load track with id [{track_id}] due to [{type(ex)}] [{ex}]")
        # return empty dictionary
        return {}
    streaming_info: StreamingInfo = build_streaming_url(
        tidal_session=tidal_session,
        track=tidal_track)
    if not streaming_info:
        # nothing to do, report error and return nothing
        msgproc.log(f"Cannot execute trackuri for track_id [{track_id}]")
        return {}
    res: dict[str, any] = {}
    # we have the streaming info, we are good to go
    res['media_url'] = streaming_info.url
    best_streaming_info: StreamingInfo = streaming_info
    if not whitelisted:
        # get streaming info from a standard session
        best_streaming_info = build_streaming_url(
            tidal_session=get_session(),
            track=tidal_track)
    if best_streaming_info.url:
        track: TidalTrack = tidal_session.track(track_id)
        if track:
            played_track_request: PlayedTrackRequest = PlayedTrackRequest()
            played_track_request.track_id = track_id
            played_track_request.track_name = track.name
            played_track_request.track_duration = track.duration
            played_track_request.track_num = track.track_num
            played_track_request.volume_num = track.volume_num
            played_track_request.audio_quality = best_streaming_info.audio_quality
            played_track_request.explicit = track.explicit
            played_track_request.album_id = track.album.id
            played_track_request.artist_name = track.artist.name
            played_track_request.bit_depth = best_streaming_info.bit_depth
            played_track_request.sample_rate = best_streaming_info.sample_rate
            album: TidalAlbum = tidal_session.album(played_track_request.album_id)
            if album:
                played_track_request.album_track_count = album.num_tracks
                played_track_request.album_num_volumes = album.num_volumes
                played_track_request.album_duration = album.duration
                played_track_request.album_name = album.name
                played_track_request.album_artist_name = album.artist.name
                played_track_request.image_url = tidal_util.get_image_url(album)
                persistence.track_playback(played_track_request)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"trackuri is returning [{res}]")
    # update track uri cache
    track_uri_cache[(
        track_id,
        select_audio_quality)] = TrackUriEntry(media_url=streaming_info.url)
    return res


def tidal_track_to_played_track_request(
        track_adapter: TrackAdapter,
        tidal_session: TidalSession) -> PlayedTrackRequest:
    played_track_request: PlayedTrackRequest = PlayedTrackRequest()
    played_track_request.track_id = track_adapter.get_id()
    played_track_request.track_name = track_adapter.get_name()
    played_track_request.track_duration = track_adapter.get_duration()
    played_track_request.track_num = track_adapter.get_track_num()
    played_track_request.volume_num = track_adapter.get_volume_num()
    played_track_request.audio_quality = track_adapter.get_audio_quality()
    played_track_request.explicit = track_adapter.explicit()
    played_track_request.album_id = track_adapter.get_album_id()
    played_track_request.artist_name = track_adapter.get_artist_name()
    played_track_request.bit_depth = track_adapter.get_bit_depth()
    played_track_request.sample_rate = track_adapter.get_sample_rate()
    album: TidalAlbum = tidal_session.album(played_track_request.album_id)
    if album:
        played_track_request.album_track_count = album.num_tracks
        played_track_request.album_num_volumes = album.num_volumes
        played_track_request.album_duration = album.duration
        played_track_request.album_name = album.name
        played_track_request.album_artist_name = album.artist.name
        played_track_request.image_url = tidal_util.get_image_url(album)
    return played_track_request


def _returnentries(entries, no_cache: bool = False):
    """Helper function: build plugin browse or search return value from items list"""
    return {"entries": json.dumps(entries), "nocache": "1" if no_cache else "0"}


def _objidtopath(objid):
    if objid.find(_g_myprefix) != 0:
        raise Exception(f"tidal: bad objid {objid}: bad prefix")
    return objid[len(_g_myprefix):].lstrip("/")


def load_tile_image_unexpired(
        tile_type: TileType,
        tile_id: str,
        expiration_time_sec: int = config.get_tile_image_expiration_time_sec()) -> TileImage:
    tile_image: TileImage = persistence.load_tile_image(
        tile_type=tile_type,
        tile_id=tile_id)
    return (tile_image
            if tile_image and not is_tile_imaged_expired(
                tile_image=tile_image,
                expiration_time_sec=expiration_time_sec)
            else None)


def is_tile_imaged_expired(
        tile_image: TileImage,
        expiration_time_sec: int = config.get_tile_image_expiration_time_sec()) -> bool:
    update_time: datetime.datetime = tile_image.update_time
    if not update_time:
        return True
    if update_time < (datetime.datetime.now() - datetime.timedelta(seconds=expiration_time_sec)):
        return True
    return False


def get_category_image_url(
        tidal_session: TidalSession,
        category: TidalItemList) -> str:
    category_tile_image: TileImage = persistence.load_tile_image(TileType.CATEGORY, category.title)
    tile_image_valid: bool = category_tile_image and not is_tile_imaged_expired(category_tile_image)
    category_image_url: str = category_tile_image.tile_image if tile_image_valid else None
    msgproc.log(f"get_category_image_url category [{category.title}] "
                f"type [{type(category).__name__}] "
                f"cached [{'yes' if category_image_url else 'no'}]")
    if not category_image_url:
        # load category image
        image_url: str = None
        if isinstance(category, TidalFeaturedItems):
            featured: TidalFeaturedItems = category
            first_featured = featured.items[0] if featured.items and len(featured.items) > 0 else None
            if not first_featured:
                msgproc.log(f"get_category_image_url category "
                            f"[{category.title}] Featured: first_featured not found")
            has_type_attribute: bool = first_featured and has_type_attr(first_featured)
            if first_featured and not has_type_attribute:
                msgproc.log(f"get_category_image_url category "
                            f"[{category.title}] Featured: first_featured no type attribute, "
                            f"type [{type(first_featured).__name__}]")
            if first_featured and has_type_attribute:
                msgproc.log(f"get_category_image_url category [{category.title}] (TidalFeaturedItems) "
                            f"first item type [{first_featured.type if first_featured else None}]")
                if first_featured.type == constants.featured_type_name_playlist:
                    playlist: TidalPlaylist = tidal_session.playlist(first_featured.artifact_id)
                    image_url = safe_get_image_url(playlist) if playlist else None
                    if not image_url:
                        msgproc.log(f"get_category_image_url category [{category.title}]"
                                    f"(TidalFeaturedItems) cannot get image for playlist")
                else:
                    msgproc.log(f"get_category_image_url category [{category.title}] (TidalFeaturedItems): "
                                f"not processed item {first_featured.type}")
        else:  # other than FeaturedItems ...
            first_item = category.items[0] if category.items and len(category.items) > 0 else None
            first_item_type: type = type(first_item) if first_item else None
            msgproc.log(f"get_category_image_url starting load process for "
                        f"category [{category.title}] type of first_item "
                        f"[{first_item_type.__name__ if first_item_type else None}]")
            if first_item:
                if isinstance(first_item, TidalTrack):
                    # msgproc.log(f"  processing as Track ...")
                    track: TidalTrack = first_item
                    image_url = tidal_util.get_image_url(obj=track)
                elif isinstance(first_item, TidalMix):
                    # msgproc.log(f"  processing as Mix ...")
                    mix: TidalMix = first_item
                    image_url = tidal_util.get_image_url(mix) if mix else None
                elif isinstance(first_item, TidalPlaylist):
                    # msgproc.log(f"  processing as Playlist ...")
                    playlist: TidalPlaylist = first_item
                    image_url = tidal_util.get_image_url(playlist) if playlist else None
                elif isinstance(first_item, TidalAlbum):
                    # msgproc.log(f"  processing as Album ...")
                    album: TidalAlbum = first_item
                    image_url = tidal_util.get_image_url(album) if album else None
                elif isinstance(first_item, TidalArtist):
                    # msgproc.log(f"  processing as Artist ...")
                    artist: TidalAlbum = first_item
                    image_url = tidal_util.get_image_url(artist) if artist else None
                elif isinstance(first_item, TidalPageLink):
                    # msgproc.log(f"  processing as <PageLink> ...")
                    page_link: TidalPageLink = first_item
                    page_link_items: list[any] = get_items_in_page_link(
                        page_link=page_link,
                        limit=config.get_page_items_for_tile_image())
                    for current in page_link_items if page_link_items else list():
                        if (isinstance(current, TidalPlaylist) or
                                isinstance(current, TidalAlbum) or
                                isinstance(current, TidalArtist)):
                            # get an image from that
                            image_url = tidal_util.get_image_url(current)
                            # we only need the first
                            break
                        else:
                            msgproc.log(f"get_category_image_url got a [{type(current).__name__ if current else None}] "
                                        f"in a [{TidalPageLink.__name__}]")
                else:
                    msgproc.log(f"get_category_image_url category [{category.title}] "
                                f"type [{type(first_item).__name__}] has not been managed")
            else:
                image_url = safe_get_image_url(first_item) if first_item else None
        if image_url:
            persistence.save_tile_image(TileType.CATEGORY, category.title, image_url)
            category_image_url = image_url
        else:
            msgproc.log(f"get_category_image_url could not get an image for category [{category.title}]")
    return category_image_url


def category_to_entry(
        objid,
        tidal_session: TidalSession,
        category: TidalItemList) -> upmplgutils.direntry:
    if not category.title:
        msgproc.log("category_to_entry empty category, returning None")
        return None
    title: str = category.title if category.title else "Other"
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.CATEGORY.getName(),
        title)
    identifier.set(ItemIdentifierKey.CATEGORY_KEY, category.title)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, title)
    # category image
    category_image_url: str = get_category_image_url(
        tidal_session=tidal_session,
        category=category)
    if category_image_url:
        upnp_util.set_album_art_from_uri(category_image_url, entry)
    else:
        msgproc.log(f"category_to_entry *Warning* category [{category.title}] "
                    f"type [{type(category)}] tile image not set.")
    return entry


def get_option(options: dict[str, any], option_key: OptionKey) -> any:
    return options[option_key.get_name()] if option_key.get_name() in options else option_key.get_default_value()


def set_option(options: dict[str, any], option_key: OptionKey, option_value: any) -> None:
    options[option_key.get_name()] = option_value


def copy_option(
        in_options: dict[str, any],
        out_options: dict[str, any],
        option_key: OptionKey,
        allow_none: bool = False) -> None:
    option_value: any = get_option(options=in_options, option_key=option_key)
    if option_value or allow_none:
        set_option(
            options=out_options,
            option_key=option_key,
            option_value=option_value)


def get_album_track_num(track_adapter: TrackAdapter) -> str:
    if track_adapter.get_volume_num() and track_adapter.get_volume_num() > 1:
        return f"{track_adapter.get_volume_num()}.{track_adapter.get_track_num():02}"
    else:
        return track_adapter.get_track_num()


def track_apply_explicit(
        track_adapter: TrackAdapter,
        current_title: str = None,
        options: dict[str, any] = {}) -> str:
    title: str = current_title if current_title else track_adapter.get_name()
    if track_adapter.explicit():
        title: str = f"{title} [E]"
    return title


def get_track_name_for_track_container(
        track_adapter: TrackAdapter,
        options: dict[str, any] = {}) -> str:
    title: str = track_adapter.get_name()
    skip_track_artist: bool = get_option(
        options=options,
        option_key=OptionKey.SKIP_TRACK_ARTIST)
    if not skip_track_artist:
        track_omittable_artist_name: str = get_option(
            options=options,
            option_key=OptionKey.TRACK_OMITTABLE_ARTIST_NAME)
        if not track_omittable_artist_name or track_omittable_artist_name != track_adapter.get_artist_name():
            title = f"{track_adapter.get_artist_name()} - {title}"
    skip_track_number: bool = get_option(
        options=options,
        option_key=OptionKey.SKIP_TRACK_NUMBER)
    if not skip_track_number:
        forced_track_number: int = get_option(
            options=options,
            option_key=OptionKey.FORCED_TRACK_NUMBER)
        track_number: str = (f"{forced_track_number:02}"
                             if forced_track_number
                             else get_album_track_num(track_adapter))
        title = f"[{track_number:02}] {title}"
    title = track_apply_explicit(
        track_adapter=track_adapter,
        current_title=title,
        options=options)
    return title


# Possibly the same #1 occ #1
def track_to_navigable_mix_item(
        objid,
        tidal_session: TidalSession,
        track: TidalTrack,
        options: dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid=objid,
        track_adapter=instance_tidal_track_adapter(
            tidal_session=tidal_session,
            track=track),
        element_type=ElementType.MIX_NAVIGABLE_ITEM,
        tidal_session=tidal_session,
        track=track,
        options=options)


def track_to_navigable_playlist_item(
        objid,
        tidal_session: TidalSession,
        track: TidalTrack,
        options: dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid=objid,
        track_adapter=instance_tidal_track_adapter(
            tidal_session=tidal_session,
            track=track),
        track=track,
        element_type=ElementType.PLAYLIST_NAVIGABLE_ITEM,
        tidal_session=tidal_session,
        options=options)


def track_to_navigable_track(
        objid,
        track_adapter: TrackAdapter,
        tidal_session: TidalSession,
        track: TidalTrack = None,
        options: dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid=objid,
        track_adapter=track_adapter,
        element_type=ElementType.NAVIGABLE_TRACK,
        tidal_session=tidal_session,
        track=track,
        options=options)


def track_to_navigable_track_by_element_type(
        objid,
        track_adapter: TrackAdapter,
        element_type: ElementType,
        tidal_session: TidalSession,
        track: TidalTrack = None,
        options: dict[str, any] = {}) -> dict:
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"track_to_navigable_track_by_element_type track [{track.id if track else 'None'}]")
    identifier: ItemIdentifier = ItemIdentifier(
        element_type.getName(),
        track_adapter.get_id())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    overridden_track_name: str = get_option(
        options=options,
        option_key=OptionKey.OVERRIDDEN_TRACK_NAME)
    if overridden_track_name:
        title = overridden_track_name
    else:
        title = get_track_name_for_track_container(
            track_adapter=track_adapter,
            options=options)
    track_entry = upmplgutils.direntry(id, objid, title)
    image_url: str = tidal_util.get_image_url(obj=track) if track else None
    if not image_url:
        from_adapter: str = track_adapter.get_image_url()
        image_url = from_adapter if from_adapter else None
    if not image_url:
        image_url = tidal_util.get_album_art_url_by_album_id(
                        album_id=track_adapter.get_album_id(),
                        tidal_session=tidal_session)
    upnp_util.set_album_art_from_uri(image_url, track_entry)
    return track_entry


def track_to_track_container(
        objid,
        tidal_session: TidalSession,
        track_adapter: TrackAdapter,
        options: dict[str, any] = {}) -> dict:
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.TRACK_CONTAINER.getName(),
        track_adapter.get_id())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    overridden_track_name: str = get_option(
        options=options,
        option_key=OptionKey.OVERRIDDEN_TRACK_NAME)
    if overridden_track_name:
        title = overridden_track_name
    else:
        title = get_track_name_for_track_container(
            track_adapter=track_adapter,
            options=options)
    track_entry = upmplgutils.direntry(id, objid, title)
    image_url: str = track_adapter.get_image_url()
    if not image_url:
        image_url = tidal_util.get_album_art_url_by_album_id(
                album_id=track_adapter.get_album_id(),
                tidal_session=tidal_session)
    upnp_util.set_album_art_from_uri(
        album_art_uri=image_url,
        target=track_entry)
    return track_entry


def track_to_entry(
        objid,
        track_adapter: TrackAdapter,
        tidal_session: TidalSession,
        options: dict[str, any] = {},
        context: Context = Context()) -> dict:
    entry = {}
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), track_adapter.get_id())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = track_adapter.get_id()
    upnp_util.set_object_type_item(entry)
    upnp_util.set_class_music_track(entry)
    # channels. I could use AudioMode but I can't exactly say how many channels are delivered
    # so I am assuming two, looks like a decent fallback for now
    upnp_util.set_channels(2, entry)
    song_uri: str = build_intermediate_url(track_adapter.get_id())
    upnp_util.set_uri(song_uri, entry)
    title: str = track_adapter.get_name()
    upnp_util.set_track_title(title, entry)
    upnp_util.set_album_title(track_adapter.get_album_name(), entry)
    upnp_util.set_artist(track_adapter.get_album_artist_name(), entry)
    skip_track_num: bool = get_option(
        options=options,
        option_key=OptionKey.SKIP_TRACK_NUMBER)
    if not skip_track_num:
        forced_track_number: int = get_option(
            options=options,
            option_key=OptionKey.FORCED_TRACK_NUMBER)
        track_num = (forced_track_number
                     if forced_track_number
                     else get_album_track_num(track_adapter))
        upnp_util.set_track_number(str(track_num), entry)
    skip_art: bool = get_option(
        options=options,
        option_key=OptionKey.SKIP_ART)
    if not skip_art:
        image_url: str = get_option(
            options=options,
            option_key=OptionKey.OVERRIDDEN_ART_URI)
        if not image_url:
            # use image url from track adapter first
            image_url = track_adapter.get_image_url()
            if not image_url:
                image_url = tidal_util.get_album_art_url_by_album_id(
                    album_id=track_adapter.get_album_id(),
                    tidal_session=tidal_session)
        if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
            msgproc.log(f"track_to_entry [{track_adapter.get_id()}] -> [{art_url}]")
        upnp_util.set_album_art_from_uri(
            album_art_uri=image_url,
            target=entry)
    else:
        msgproc.log(f"Skipping art for track_id [{track_adapter.get_id()}] "
                    f"title [{track_adapter.get_name()}] "
                    f"by [{track_adapter.get_artist_name()}] "
                    f"from [{track_adapter.get_album_name()}]")
    upnp_util.set_duration(track_adapter.get_duration(), entry)
    set_track_stream_information(
        entry=entry,
        tidal_session=tidal_session,
        track_adapter=track_adapter,
        context=context)
    get_stream_failed: bool = context.get(key=ContextKey.CANNOT_GET_STREAM_INFO)
    if not get_stream_failed:
        # update success count
        context.increment(key=ContextKey.SUCCESS_COUNT)
    context.increment(key=ContextKey.PROCESS_COUNT)
    if config.dump_track_to_entry_result:
        known: bool = context.dict_get(
            dict_key=ContextKey.KNOWN_TRACK_DICT,
            entry_key=track_adapter.get_id(),
            default_value=False)
        guessed: bool = context.dict_get(
            dict_key=ContextKey.GUESSED_TRACK_DICT,
            entry_key=track_adapter.get_id(),
            default_value=False)
        assumed_by_first: bool = context.dict_get(
            dict_key=ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_DICT,
            entry_key=track_adapter.get_id(),
            default_value=False)
        get_stream: bool = context.dict_get(
            dict_key=ContextKey.GET_STREAM_DICT,
            entry_key=track_adapter.get_id(),
            default_value=False)
        msgproc.log(f"Track [{track_adapter.get_id()}] Title [{track_adapter.get_name()}] "
                    f"from [{track_adapter.get_album_name()}] "
                    f"by [{track_adapter.get_artist_name()}] "
                    f"known: [{'yes' if known else 'no'}] "
                    f"guessed: [{'yes' if guessed else 'no'}] "
                    f"assumed from first: [{'yes' if assumed_by_first else 'no'}] "
                    f"get_stream: [{'yes' if get_stream else 'no'}]")
        # f"stream info obtained: [{stream_info_obtained}] "
        # f"bit_depth [{bit_depth if known else None}] "
        # f"sample_rate [{sample_rate if known else None}] "
        # f"assumed from first track: [{assumed_from_first}] "
        # f"assumed by config quality: [{assumed_by_config_quality}]")
    return entry


def report_get_stream_exception(
        ex: Exception,
        track_adapter: TrackAdapter,
        context: Context):
    success_count: int = context.get(key=ContextKey.SUCCESS_COUNT)
    msgproc.log(
        f"getting stream info failed for track_id [{track_adapter.get_id()}] "
        f"Title [{track_adapter.get_name()}] from [{track_adapter.get_album_name()}] "
        f"by [{track_adapter.get_artist_name()}], "
        f"setting CANNOT_GET_STREAM_INFO for context to True "
        f"after [{success_count}] successes "
        f"due to [{type(ex)}] [{ex}]")
    context.add(ContextKey.CANNOT_GET_STREAM_INFO, True)


def set_track_stream_information(
        entry: dict[str, any],
        tidal_session: TidalSession,
        track_adapter: TrackAdapter,
        context: Context):
    is_album: bool = context.get(key=ContextKey.IS_ALBUM)
    is_playlist: bool = context.get(key=ContextKey.IS_PLAYLIST)
    is_mix: bool = context.get(key=ContextKey.IS_MIX)
    is_track: bool = context.get(key=ContextKey.IS_TRACK)
    is_mix_or_playlist: bool = is_playlist or is_mix
    if config.dump_track_to_entry_result:
        msgproc.log(f"set_track_stream_information track_id [{track_adapter.get_id()}] "
                    f"is_album [{is_album}] is_playlist [{is_playlist}] "
                    f"is_mix [{is_mix}] is_track [{is_track}] "
                    f"is_mix_or_playlist [{is_mix_or_playlist}]")
    if is_album or is_track:
        set_stream_information_for_album_entry(
            entry=entry,
            tidal_session=tidal_session,
            track_adapter=track_adapter,
            context=context)
    elif is_mix_or_playlist:
        set_stream_information_for_mix_or_playlist_entry(
            entry=entry,
            tidal_session=tidal_session,
            track_adapter=track_adapter,
            context=context)
    # elif is_track:
    #     # nothing special to do
    #     pass
    else:
        # we do the same as fallback
        # TODO evaluate if we can so ignore is_mix, is_playlist
        set_stream_information_for_mix_or_playlist_entry(
            entry=entry,
            tidal_session=tidal_session,
            track_adapter=track_adapter,
            context=context)


def __played_track_has_stream_info(played_track: PlayedTrack) -> bool:
    return (played_track and
            played_track.bit_depth and
            played_track.sample_rate and
            played_track.audio_quality)


def __context_contains_first_track_data(context: Context) -> bool:
    return (
        context.contains(ContextKey.ALBUM_FIRST_TRACK_BIT_DEPTH) and
        context.contains(ContextKey.ALBUM_FIRST_TRACK_SAMPLE_RATE) and
        context.contains(ContextKey.ALBUM_FIRST_TRACK_AUDIO_QUALITY))


def context_increment_and_store_dict_of_bool(
        context: Context,
        counter_key: ContextKey,
        dict_key: ContextKey,
        track_id: str):
    context.increment(key=counter_key)
    context.dict_add(
        dict_key=dict_key,
        entry_key=track_id,
        entry_value=True)


def __select_played_track(played_tracks: list[PlayedTrack]) -> PlayedTrack:
    select: PlayedTrack
    for select in played_tracks if played_tracks else list():
        if (select.audio_quality and
                select.bit_depth and
                select.sample_rate):
            return select
    # none is good, so let's return first if available
    return played_tracks[0] if played_tracks and len(played_tracks) > 0 else None


def set_stream_information_for_mix_or_playlist_entry(
        entry: dict[str, any],
        tidal_session: TidalSession,
        track_adapter: TrackAdapter,
        context: Context):
    bit_depth: int = None
    sample_rate: int = None
    audio_quality: str = None
    # do we know the track from our played tracks?
    played_album_tracks: list[PlayedTrack] = get_or_load_played_album_tracks(
        context=context,
        album_id=track_adapter.get_album_id())
    played = get_played_track(
        played_album_tracks=played_album_tracks,
        track_id=track_adapter.get_id())
    got_from_played: bool = False
    if __played_track_has_stream_info(played):
        got_from_played = True
        context_increment_and_store_dict_of_bool(
            context=context,
            counter_key=ContextKey.KNOWN_TRACKS_COUNT,
            dict_key=ContextKey.KNOWN_TRACK_DICT,
            track_id=track_adapter.get_id())
    # ok, we don't have the current track, but do we have
    # a track from the same album?
    elif len(played_album_tracks) > 0 and config.allow_guess_stream_info_from_other_album_track:
        # take first know track, and assume that stream info is the same for all
        # of the tracks in the same albums, which most of the times is true
        got_from_played = True
        context_increment_and_store_dict_of_bool(
            context=context,
            counter_key=ContextKey.GUESSED_TRACKS_COUNT,
            dict_key=ContextKey.GUESSED_TRACK_DICT,
            track_id=track_adapter.get_id())
        played = __select_played_track(played_album_tracks)
    if not got_from_played:
        # get from first?
        if (__context_contains_first_track_data(context=context)):
            bit_depth = context.get(key=ContextKey.ALBUM_FIRST_TRACK_BIT_DEPTH, allow_empty=False)
            sample_rate = context.get(key=ContextKey.ALBUM_FIRST_TRACK_SAMPLE_RATE, allow_empty=False)
            audio_quality = context.get(key=ContextKey.ALBUM_FIRST_TRACK_AUDIO_QUALITY, allow_empty=False)
            #  assumed_from_first = True
            context_increment_and_store_dict_of_bool(
                context=context,
                counter_key=ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_COUNT,
                dict_key=ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_DICT,
                track_id=track_adapter.get_id())
    else:  # got from played
        bit_depth = played.bit_depth
        sample_rate = played.sample_rate
        audio_quality = correct_audio_quality(
            bit_depth=bit_depth,
            sample_rate=sample_rate,
            audio_quality=played.audio_quality)
    # still nothing? read stream info a max number of times
    if not bit_depth and not sample_rate and not audio_quality:
        get_stream_failed: bool = context.get(key=ContextKey.CANNOT_GET_STREAM_INFO)
        if not get_stream_failed:
            limit: int = config.max_get_stream_info_mix_or_playlist
            get_stream_count: int = context.get(key=ContextKey.GET_STREAM_COUNT)
            if get_stream_count < limit:
                try:
                    if config.dump_track_to_entry_result:
                        msgproc.log(f"Trying to get stream info for track_id [{track_adapter.get_id()}]")
                    bit_depth = track_adapter.get_bit_depth()
                    sample_rate = track_adapter.get_sample_rate()
                    audio_quality = track_adapter.get_audio_quality()
                    context_increment_and_store_dict_of_bool(
                        context=context,
                        counter_key=ContextKey.GET_STREAM_COUNT,
                        dict_key=ContextKey.GET_STREAM_DICT,
                        track_id=track_adapter.get_id())
                    # store ghost playback
                    persistence.track_ghost_playback(
                        played_track_request=tidal_track_to_played_track_request(
                            track_adapter=track_adapter,
                            tidal_session=tidal_session))
                except Exception as ex:
                    report_get_stream_exception(
                        ex=ex,
                        track_adapter=track_adapter,
                        context=context)
    if not bit_depth and config.enable_assume_bitdepth:
        #  last fallback for bit depth
        bit_depth = guess_bit_depth(audio_quality=audio_quality, sample_rate=sample_rate)
        # assume redbook
        if not audio_quality:
            audio_quality = TidalQuality.high_lossless
        if not bit_depth:
            bit_depth = 16
        if not sample_rate:
            sample_rate = 44100
        #  increment ASSUMED_BY_MAX_AUDIO_QUALITY_COUNT
        context.increment(key=ContextKey.ASSUMED_BY_MAX_AUDIO_QUALITY_COUNT)
    if not bit_depth or not sample_rate or not audio_quality:
        msgproc.log(f"No info for [{track_adapter.get_name()}] "
                    f"from [{track_adapter.get_album_name()}] "
                    f"by [{track_adapter.get_artist_name()}] "
                    f"bit_depth [{bit_depth}] "
                    f"sample_rate [{sample_rate}] "
                    f"audio_quality [{audio_quality}] "
                    f"using fallback values")
        # set fallback values where needed
        if not bit_depth:
            bit_depth = 16
        if not sample_rate:
            sample_rate = 44100
        if not audio_quality:
            audio_quality = config.get_fallback_quality_when_missing()
    if bit_depth:
        upnp_util.set_bit_depth(bit_depth, entry)
    if sample_rate:
        upnp_util.set_sample_rate(sample_rate, entry)
    if audio_quality:
        upnp_util.set_mime_type(tidal_util.get_mime_type(audio_quality), entry)


def set_stream_information_for_album_entry(
        entry: dict[str, any],
        tidal_session: TidalSession,
        track_adapter: TrackAdapter,
        context: Context):
    bit_depth: int = None
    sample_rate: int = None
    audio_quality: str = None
    # do we know the track from our played tracks?
    played_album_tracks: list[PlayedTrack] = get_or_load_played_album_tracks(
        context=context,
        album_id=track_adapter.get_album_id())
    played = get_played_track(
        played_album_tracks=played_album_tracks,
        track_id=track_adapter.get_id())
    got_from_played: bool = False
    if __played_track_has_stream_info(played):
        got_from_played = True
        context_increment_and_store_dict_of_bool(
            context=context,
            counter_key=ContextKey.KNOWN_TRACKS_COUNT,
            dict_key=ContextKey.KNOWN_TRACK_DICT,
            track_id=track_adapter.get_id())
    # ok, we don't have the current track, but do we have
    # a track from the same album?
    elif len(played_album_tracks) > 0 and config.allow_guess_stream_info_from_other_album_track:
        # take first know track, and assume that stream info is the same for all
        # of the tracks in the same albums, which most of the times is true
        got_from_played = True
        played = __select_played_track(played_album_tracks)
        context_increment_and_store_dict_of_bool(
            context=context,
            counter_key=ContextKey.GUESSED_TRACKS_COUNT,
            dict_key=ContextKey.GUESSED_TRACK_DICT,
            track_id=track_adapter.get_id())
    if not got_from_played:
        # get from first?
        if (__context_contains_first_track_data(context=context)):
            bit_depth = context.get(key=ContextKey.ALBUM_FIRST_TRACK_BIT_DEPTH, allow_empty=False)
            sample_rate = context.get(key=ContextKey.ALBUM_FIRST_TRACK_SAMPLE_RATE, allow_empty=False)
            audio_quality = context.get(key=ContextKey.ALBUM_FIRST_TRACK_AUDIO_QUALITY, allow_empty=False)
            #  assumed_from_first = True
            context_increment_and_store_dict_of_bool(
                context=context,
                counter_key=ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_COUNT,
                dict_key=ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_DICT,
                track_id=track_adapter.get_id())
    else:  # got from played
        bit_depth = played.bit_depth
        sample_rate = played.sample_rate
        audio_quality = correct_audio_quality(
            bit_depth=bit_depth,
            sample_rate=sample_rate,
            audio_quality=played.audio_quality)
    # still nothing? read from first track
    if not bit_depth and not sample_rate and not audio_quality:
        get_stream_failed: bool = context.get(key=ContextKey.CANNOT_GET_STREAM_INFO)
        if not get_stream_failed:
            try:
                if config.dump_track_to_entry_result:
                    msgproc.log(f"Trying to get stream info for track_id [{track_adapter.get_id()}]")
                bit_depth = track_adapter.get_bit_depth()
                sample_rate = track_adapter.get_sample_rate()
                audio_quality = track_adapter.get_audio_quality()
                context_increment_and_store_dict_of_bool(
                    context=context,
                    counter_key=ContextKey.GET_STREAM_COUNT,
                    dict_key=ContextKey.GET_STREAM_DICT,
                    track_id=track_adapter.get_id())
                # store in context
                context.add(key=ContextKey.ALBUM_FIRST_TRACK_BIT_DEPTH, value=bit_depth)
                context.add(key=ContextKey.ALBUM_FIRST_TRACK_SAMPLE_RATE, value=sample_rate)
                context.add(key=ContextKey.ALBUM_FIRST_TRACK_AUDIO_QUALITY, value=audio_quality)
                # store obtained information
                persistence.track_ghost_playback(
                    played_track_request=tidal_track_to_played_track_request(
                        track_adapter=track_adapter,
                        tidal_session=tidal_session))
            except Exception as ex:
                report_get_stream_exception(
                    ex=ex,
                    track_adapter=track_adapter,
                    context=context)
    if not bit_depth and config.enable_assume_bitdepth:
        #  last fallback for bit depth
        bit_depth = guess_bit_depth(audio_quality=audio_quality, sample_rate=sample_rate)
        # assume redbook
        if not audio_quality:
            audio_quality = TidalQuality.high_lossless
        if not bit_depth:
            bit_depth = 16
        if not sample_rate:
            sample_rate = 44100
        #  increment ASSUMED_BY_MAX_AUDIO_QUALITY_COUNT
        context.increment(key=ContextKey.ASSUMED_BY_MAX_AUDIO_QUALITY_COUNT)
    if not bit_depth or not sample_rate or not audio_quality:
        msgproc.log(f"No info for [{track_adapter.get_name()}] "
                    f"from [{track_adapter.get_album_name()}] "
                    f"by [{track_adapter.get_artist_name()}] "
                    f"bit_depth [{bit_depth}] "
                    f"sample_rate [{sample_rate}] "
                    f"audio_quality [{audio_quality}] "
                    f"using fallback values")
        # set fallback values where needed
        if not bit_depth:
            bit_depth = 16
        if not sample_rate:
            sample_rate = 44100
        if not audio_quality:
            audio_quality = config.get_fallback_quality_when_missing()
    if bit_depth:
        upnp_util.set_bit_depth(bit_depth, entry)
    if sample_rate:
        upnp_util.set_sample_rate(sample_rate, entry)
    if audio_quality:
        upnp_util.set_mime_type(tidal_util.get_mime_type(audio_quality), entry)


def correct_audio_quality(
        bit_depth: int,
        sample_rate: int,
        audio_quality: TidalQuality) -> TidalQuality:
    # can we evaluate bit available data?
    if bit_depth and sample_rate:
        if bit_depth > 16:
            return TidalQuality.hi_res_lossless
        if bit_depth == 16 and sample_rate in [44100, 48000]:
            if not audio_quality:
                return TidalQuality.high_lossless
            else:
                # can't be hires or hi_res_lossless
                if audio_quality not in [TidalQuality.hi_res_lossless]:
                    return audio_quality
                else:  # invalid!
                    return None
    else:
        # no bit_depth, no sample_rate
        # assume redbook if missing
        return audio_quality if audio_quality else TidalQuality.high_lossless


def get_or_load_played_album_tracks(context: Context, album_id: str) -> list[PlayedTrack]:
    played_album_tracks_dict: dict[str, list[PlayedTrack]] = context.get(ContextKey.PLAYED_ALBUM_TRACKS_DICT)
    played_tracks_list: list[PlayedTrack] = (
        played_album_tracks_dict[album_id]
        if album_id in played_album_tracks_dict
        else None)
    if not played_tracks_list:
        played_tracks_list = persistence.get_played_album_entries(album_id=str(album_id))
        played_album_tracks_dict[album_id] = played_tracks_list
        context.update(key=ContextKey.PLAYED_ALBUM_TRACKS_DICT, value=played_album_tracks_dict)
    return played_tracks_list


def get_played_track(played_album_tracks: list[PlayedTrack], track_id: str) -> PlayedTrack:
    played_track: PlayedTrack
    for played_track in played_album_tracks:
        if str(played_track.track_id) == str(track_id):
            return played_track
    return None


def artist_to_entry(
        objid,
        artist: TidalArtist) -> upmplgutils.direntry:
    art_uri: str = tidal_util.get_image_url(artist)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"artist_to_entry art_uri = [{art_uri}]")
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(),
        artist.id)
    identifier.set(ItemIdentifierKey.MISSING_ARTIST_ART, art_uri is None)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, title=artist.name)
    upnp_util.set_class_artist(entry)
    upnp_util.set_album_art_from_uri(art_uri, entry)
    return entry


def album_to_album_container(
        objid,
        tidal_session: TidalSession,
        album: TidalAlbum,
        options: dict[str, any] = dict()) -> upmplgutils.direntry:
    return album_adapter_to_album_container(
        objid=objid,
        tidal_session=tidal_session,
        album_adapter=tidal_album_to_adapter(album),
        album=album,
        options=options)


def album_adapter_to_album_container(
        objid,
        tidal_session: TidalSession,
        album_adapter: AlbumAdapter,
        album: TidalAlbum = None,
        options: dict[str, any] = dict()) -> upmplgutils.direntry:
    out_options: dict[str, any] = dict()
    copy_option(
        in_options=options,
        out_options=out_options,
        option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ENTRY_NAME)
    copy_option(
        in_options=options,
        out_options=out_options,
        option_key=OptionKey.OMIT_ARTIST_TO_ALBUM_ENTRY_UNLESS_DIFFERENT)
    copy_option(
        in_options=options,
        out_options=out_options,
        option_key=OptionKey.ALBUM_OMITTABLE_ARTIST_ID)
    set_option(
        options=out_options,
        option_key=OptionKey.ENTRY_AS_CONTAINER,
        option_value=True)
    set_option(
        options=out_options,
        option_key=OptionKey.ADD_ARTIST_TO_ALBUM_ENTRY,
        option_value=True)
    return album_adapter_to_entry(
        objid=objid,
        tidal_session=tidal_session,
        album_adapter=album_adapter,
        album=album,
        options=out_options)


# used in search, this needs to stay here
def album_to_entry(
        objid: any,
        tidal_session: TidalSession,
        album: TidalAlbum,
        options: dict[str, any] = {}) -> upmplgutils.direntry:
    # msgproc.log("album_to_entry -> album_adapter_to_entry ...")
    return album_adapter_to_entry(
        objid=objid,
        tidal_session=tidal_session,
        album_adapter=tidal_album_to_adapter(album),
        album=album,
        options=options)


def album_adapter_to_entry(
        objid: any,
        tidal_session: TidalSession,
        album_adapter: AlbumAdapter,
        album: TidalAlbum = None,
        options: dict[str, any] = {}) -> upmplgutils.direntry:
    as_container: bool = get_option(
        options=options,
        option_key=OptionKey.ENTRY_AS_CONTAINER)
    element_type: ElementType = (
        ElementType.ALBUM_CONTAINER if as_container
        else ElementType.ALBUM)
    identifier: ItemIdentifier = ItemIdentifier(
        element_type.getName(),
        album_adapter.id)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    album_title: str = album_adapter.name
    entry_number: int = get_option(
        options=options,
        option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ENTRY_NAME)
    if entry_number:
        album_title = f"[{entry_number:02}] {album_title}"
    add_explicit: bool = get_option(
        options=options,
        option_key=OptionKey.ADD_EXPLICIT)
    if add_explicit and album_adapter.explicit and "explicit" not in album_title.lower():
        album_title = f"{album_title} [E]"
    add_album_year: bool = get_option(
        options=options,
        option_key=OptionKey.ADD_ALBUM_YEAR)
    if add_album_year and album_adapter.year:
        album_title = f"{album_title} [{album_adapter.year}]"
    # add badge?
    cached_tidal_quality: tidal_util.CachedTidalQuality = tidal_util.get_cached_audio_quality(
        album_id=album_adapter.id)
    badge: str = tidal_util.get_quality_badge_raw(
        audio_modes=album_adapter.audio_modes,
        media_metadata_tags=album_adapter.media_metadata_tags,
        audio_quality=album_adapter.audio_quality,
        cached_tidal_quality=cached_tidal_quality)
    if badge:
        album_title = f"{album_title} [{badge}]"
    add_artist: bool = get_option(
        options=options,
        option_key=OptionKey.ADD_ARTIST_TO_ALBUM_ENTRY)
    allow_omittable: bool = get_option(
        options=options,
        option_key=OptionKey.OMIT_ARTIST_TO_ALBUM_ENTRY_UNLESS_DIFFERENT)
    if allow_omittable:
        omittable: str = get_option(
            options=options,
            option_key=OptionKey.ALBUM_OMITTABLE_ARTIST_ID)
        if omittable == album_adapter.artist_id:
            # avoid to prepend artist in this case
            add_artist = False
    if add_artist:
        album_title = f"{album_title} - {album_adapter.artist_name}"
    entry = upmplgutils.direntry(id, objid, title=album_title, artist=album_adapter.artist_name)
    upnp_util.set_date(datetime=album_adapter.release_date, target=entry)
    if not as_container:
        upnp_util.set_class_album(entry)
    image_url: str = album_adapter.image_url
    if not image_url:
        image_url = tidal_util.get_album_art_url_by_album_id(
            album_id=album_adapter.id,
            tidal_session=tidal_session,
            album=album)
    upnp_util.set_album_art_from_uri(
        album_art_uri=image_url,
        target=entry)
    tidal_util.add_album_adapter_metadata(album_adapter=album_adapter, target=entry)
    return entry


def pagelink_to_entry(
        objid,
        category: TidalItemList,
        page_link: TidalPageLink,
        page_list: list[str] = list()) -> upmplgutils.direntry:
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.PAGELINK.getName(),
        page_link.title)
    identifier.set(ItemIdentifierKey.PAGE_LINK_API_PATH, page_link.api_path)
    identifier.set(ItemIdentifierKey.CATEGORY_TITLE, category.title)
    identifier.set(ItemIdentifierKey.PAGE_LIST, page_list)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, title=page_link.title)
    return entry


def page_link_to_entry(
        objid,
        page_link: TidalPageLink) -> upmplgutils.direntry:
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.PAGE.getName(),
        page_link.api_path)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, title=page_link.title)
    return entry


def playlist_to_playlist_container(
        objid,
        playlist: TidalPlaylist) -> upmplgutils.direntry:
    return raw_playlist_to_entry(
        objid=objid,
        playlist=playlist,
        element_type=ElementType.PLAYLIST_CONTAINER)


def playlist_to_entry(
        objid,
        playlist: TidalPlaylist) -> upmplgutils.direntry:
    return raw_playlist_to_entry(
        objid=objid,
        playlist=playlist,
        element_type=ElementType.PLAYLIST)


def raw_playlist_to_entry(
        objid,
        playlist: TidalPlaylist,
        element_type: ElementType = ElementType.PLAYLIST) -> upmplgutils.direntry:
    identifier: ItemIdentifier = ItemIdentifier(
        element_type.getName(),
        playlist.id)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, title=playlist.name)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(playlist), entry)
    return entry


def mix_to_entry(
        objid,
        mix: TidalMix) -> upmplgutils.direntry:
    options: dict[str, any] = dict()
    set_option(
        options=options,
        option_key=OptionKey.ENTRY_AS_CONTAINER,
        option_value=False)
    return raw_mix_to_entry(
        objid=objid,
        mix=mix,
        options=options)


def mix_to_mix_container(
        objid,
        mix: TidalMix) -> upmplgutils.direntry:
    options: dict[str, any] = dict()
    set_option(
        options=options,
        option_key=OptionKey.ENTRY_AS_CONTAINER,
        option_value=True)
    return raw_mix_to_entry(
        objid=objid,
        mix=mix,
        options=options)


def raw_mix_to_entry(
        objid,
        mix: TidalMix,
        options: dict[str, any] = {}) -> upmplgutils.direntry:
    as_container: bool = get_option(
        options=options,
        option_key=OptionKey.ENTRY_AS_CONTAINER)
    element_type: ElementType = ElementType.MIX_CONTAINER if as_container else ElementType.MIX
    identifier: ItemIdentifier = ItemIdentifier(
        element_type.getName(),
        mix.id)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, title=mix.title)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(mix), entry)
    return entry


def get_categories(tidal_session: TidalSession) -> list[TidalItemList]:
    home = tidal_session.home()
    home.categories.extend(tidal_session.explore().categories)
    # home.categories.extend(tidal_session.videos().categories)
    return home.categories


def get_category(
        tidal_session: TidalSession,
        category_name: str):
    categories: list[TidalItemList] = get_categories(tidal_session=tidal_session)
    match_list: list = list()
    first = None
    for current in categories:
        if current.title == category_name:
            if not first:
                first = current
            match_list.append(current)
    if len(match_list) > 1:
        msgproc.log(f"get_category: multiple matches for [{category_name}], returning first")
    return first


def compare_favorite_album_by_criteria_list(
        criteria_list: list[AlbumSortCriteria],
        left: TidalAlbum,
        right: TidalAlbum) -> int:
    cmp: int = 0
    current: AlbumSortCriteria
    for current in criteria_list:
        cmp = current.compare(left, right)
        if cmp != 0:
            break
    return cmp


def compare_favorite_artist_by_criteria_list(
        criteria_list: list[ArtistSortCriteria],
        left: TidalArtist,
        right: TidalArtist) -> int:
    cmp: int = 0
    current: ArtistSortCriteria
    for current in criteria_list:
        cmp = current.compare(left, right)
        if cmp != 0:
            break
    return cmp


def build_album_sort_criteria_by_artist(descending: bool = False) -> list[AlbumSortCriteria]:
    criteria_list: list[AlbumSortCriteria] = list()
    multiplier: int = -1 if descending else 1
    artist_extractor: Callable[[TidalAlbum], str] = (
        lambda a:
            a.artist.name.upper()
            if a.artist and a.artist.name
            else "")
    artist_comparator: Callable[[str, str], int] = (
        lambda left, right:
            multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(artist_extractor, artist_comparator))

    rd_extractor: Callable[[TidalAlbum], float] = (
        lambda a:
            a.available_release_date.timestamp()
            if a.available_release_date
            else 0.0)
    rd_comparator: Callable[[float, float], int] = (
        lambda left, right:
            multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(rd_extractor, rd_comparator))

    t_extractor: Callable[[TidalAlbum], str] = lambda a: a.name.upper() if a.name else ""
    t_comparator: Callable[[str, str], int] = (
        lambda left, right:
            multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(t_extractor, t_comparator))
    return criteria_list


def build_album_sort_criteria_by_release_date(descending: bool = False) -> list[AlbumSortCriteria]:
    criteria_list: list[AlbumSortCriteria] = list()
    multiplier: int = -1 if descending else 1
    extractor: Callable[[TidalAlbum], float] = (
        lambda a:
            a.available_release_date.timestamp() if a.available_release_date else 0.0)
    comparator: Callable[[float, float], int] = (
        lambda left, right:
            multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(extractor, comparator))
    return criteria_list


def build_album_sort_criteria_by_user_date_added(descending: bool = False) -> list[AlbumSortCriteria]:
    criteria_list: list[AlbumSortCriteria] = list()
    multiplier: int = -1 if descending else 1
    extractor: Callable[[TidalAlbum], float] = (
        lambda a:
            a.user_date_added.timestamp() if a.user_date_added else 0.0)
    comparator: Callable[[float, float], int] = (
        lambda left, right:
            multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(extractor, comparator))
    return criteria_list


def build_artist_sort_criteria_by_user_date_added(descending: bool = False) -> list[ArtistSortCriteria]:
    criteria_list: list[ArtistSortCriteria] = list()
    multiplier: int = -1 if descending else 1
    extractor: Callable[[TidalArtist], float] = (
        lambda a:
            a.user_date_added.timestamp() if a.user_date_added else 0.0)
    comparator: Callable[[float, float], int] = (
        lambda left, right:
            multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(ArtistSortCriteria(extractor, comparator))
    return criteria_list


def build_album_sort_criteria_by_name(descending: bool = False) -> list[AlbumSortCriteria]:
    criteria_list: list[AlbumSortCriteria] = list()
    multiplier: int = -1 if descending else 1
    t_extractor: Callable[[TidalAlbum], str] = lambda a: a.name.upper() if a.name else ""
    t_comparator: Callable[[str, str], int] = (
        lambda left, right:
            multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(t_extractor, t_comparator))
    return criteria_list


def build_artist_sort_criteria_by_name(descending: bool = False) -> list[ArtistSortCriteria]:
    criteria_list: list[ArtistSortCriteria] = list()
    multiplier: int = -1 if descending else 1
    t_extractor: Callable[[TidalArtist], str] = lambda a: a.name.upper() if a.name else ""
    t_comparator: Callable[[str, str], int] = (
        lambda left, right:
            multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(ArtistSortCriteria(t_extractor, t_comparator))
    return criteria_list


def get_favorite_albums_by_artist(
        tidal_session: TidalSession,
        descending: bool,
        limit: int,
        offset: int = 0) -> list[TidalAlbum]:
    items: list[TidalAlbum] = tidal_util.try_get_all_favorites(tidal_session)
    sc_list: list[AlbumSortCriteria] = build_album_sort_criteria_by_artist(descending=descending)
    items.sort(key=cmp_to_key(lambda x, y: compare_favorite_album_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_albums_by_title(
        tidal_session: TidalSession,
        descending: bool,
        limit: int,
        offset: int = 0) -> list[TidalAlbum]:
    items: list[TidalAlbum] = tidal_util.try_get_all_favorites(tidal_session)
    sc_list: list[AlbumSortCriteria] = build_album_sort_criteria_by_name(descending=descending)
    items.sort(key=cmp_to_key(lambda x, y: compare_favorite_album_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_albums_by_release_date(
        tidal_session: TidalSession,
        descending: bool,
        limit: int,
        offset: int = 0) -> list[TidalAlbum]:
    items: list[TidalAlbum] = tidal_util.try_get_all_favorites(tidal_session)
    sc_list: list[AlbumSortCriteria] = build_album_sort_criteria_by_release_date(descending=descending)
    items.sort(key=cmp_to_key(lambda x, y: compare_favorite_album_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_albums_by_user_date_added(
        tidal_session: TidalSession,
        descending: bool,
        limit: int,
        offset: int = 0) -> list[TidalAlbum]:
    items: list[TidalAlbum] = tidal_util.try_get_all_favorites(tidal_session)
    sc_list: list[AlbumSortCriteria] = build_album_sort_criteria_by_user_date_added(descending=descending)
    items.sort(key=cmp_to_key(lambda x, y: compare_favorite_album_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_artists_by_name(
        tidal_session: TidalSession,
        descending: bool,
        limit: int,
        offset: int = 0) -> list[TidalArtist]:
    items: list[TidalArtist] = tidal_session.user.favorites.artists()
    sc_list: list[ArtistSortCriteria] = build_artist_sort_criteria_by_name(descending=descending)
    items.sort(key=cmp_to_key(lambda x, y: compare_favorite_artist_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_artists_by_user_date_added(
        tidal_session: TidalSession,
        descending: bool,
        limit: int,
        offset: int = 0) -> list[TidalArtist]:
    items: list[TidalArtist] = tidal_session.user.favorites.artists()
    sc_list: list[ArtistSortCriteria] = build_artist_sort_criteria_by_user_date_added(descending=descending)
    items.sort(key=cmp_to_key(lambda x, y: compare_favorite_artist_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def __handler_element_favorite_albums_common(
        descending: bool,
        element_type: ElementType,
        list_retriever: Callable[[TidalSession, bool, int, int], list[TidalAlbum]],
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    counter: int = offset
    max_items: int = config.albums_per_page
    # one over the max so I have the art for next
    items: list[TidalAlbum] = list_retriever(tidal_session, descending, max_items + 1, offset)
    # back to the target size
    next_album: TidalAlbum = items[max_items] if len(items) == max_items + 1 else None
    items = items[0:max_items] if len(items) == max_items + 1 else items
    current: TidalAlbum
    for current in items:
        counter += 1
        options: dict[str, any] = dict()
        if config.prepend_number_in_album_list:
            set_option(
                options=options,
                option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ENTRY_NAME,
                option_value=counter)
        if config.skip_non_stereo and not tidal_util.is_tidal_album_stereo(current):
            if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
                msgproc.log(tidal_util.not_stereo_skipmessage(current))
            continue
        entries.append(album_to_album_container(
            objid=objid,
            tidal_session=tidal_session,
            album=current,
            options=options))
    if len(items) >= max_items:
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=element_type,
            element_id=element_type.getName(),
            next_offset=offset + max_items)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_album.id,
                tidal_session=tidal_session),
            target=next_button)
        entries.append(next_button)
    return entries


def handler_element_favorite_albums_by_artist_asc(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_element_favorite_albums_common(
        descending=False,
        element_type=ElementType.FAVORITE_ALBUMS_BY_ARTIST_ASC,
        list_retriever=get_favorite_albums_by_artist,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_favorite_albums_by_artist_desc(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_element_favorite_albums_common(
        descending=True,
        element_type=ElementType.FAVORITE_ALBUMS_BY_ARTIST_DESC,
        list_retriever=get_favorite_albums_by_artist,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_favorite_albums_by_title_asc(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_element_favorite_albums_common(
        descending=False,
        element_type=ElementType.FAVORITE_ALBUMS_BY_TITLE_ASC,
        list_retriever=get_favorite_albums_by_title,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_favorite_albums_by_title_desc(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_element_favorite_albums_common(
        descending=True,
        element_type=ElementType.FAVORITE_ALBUMS_BY_TITLE_DESC,
        list_retriever=get_favorite_albums_by_title,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_favorite_albums_by_release_date_asc(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    return __handler_element_favorite_albums_common(
        descending=False,
        element_type=ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_ASC,
        list_retriever=get_favorite_albums_by_release_date,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_favorite_albums_by_release_date_desc(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    return __handler_element_favorite_albums_common(
        descending=True,
        element_type=ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_DESC,
        list_retriever=get_favorite_albums_by_release_date,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_favorite_albums_by_user_added_asc(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    return __handler_element_favorite_albums_common(
        descending=False,
        element_type=ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_ASC,
        list_retriever=get_favorite_albums_by_user_date_added,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_favorite_albums_by_user_added_desc(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    return __handler_element_favorite_albums_common(
        descending=True,
        element_type=ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_DESC,
        list_retriever=get_favorite_albums_by_user_date_added,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_tag_favorite_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tuple_array: list[FavoriteAlbumsMode] = [
        FavoriteAlbumsMode.create(
            element_type=ElementType.FAVORITE_ALBUMS_BY_ARTIST_ASC,
            display_name="By Artist (Asc)",
            sort_criteria_builder=build_album_sort_criteria_by_artist),
        FavoriteAlbumsMode.create(
            element_type=ElementType.FAVORITE_ALBUMS_BY_ARTIST_DESC,
            display_name="By Artist (Desc)",
            sort_criteria_builder=build_album_sort_criteria_by_artist,
            descending=True),
        FavoriteAlbumsMode.create(
            element_type=ElementType.FAVORITE_ALBUMS_BY_TITLE_ASC,
            display_name="By Title (Asc)",
            sort_criteria_builder=build_album_sort_criteria_by_name),
        FavoriteAlbumsMode.create(
            element_type=ElementType.FAVORITE_ALBUMS_BY_TITLE_DESC,
            display_name="By Title (Desc)",
            sort_criteria_builder=build_album_sort_criteria_by_name,
            descending=True),
        FavoriteAlbumsMode.create(
            element_type=ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_ASC,
            display_name="By Release Date (Asc)",
            sort_criteria_builder=build_album_sort_criteria_by_release_date),
        FavoriteAlbumsMode.create(
            element_type=ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_DESC,
            display_name="By Release Date (Desc)",
            sort_criteria_builder=build_album_sort_criteria_by_release_date,
            descending=True),
        FavoriteAlbumsMode.create(
            element_type=ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_ASC,
            display_name="By Date Added (Asc)",
            sort_criteria_builder=build_album_sort_criteria_by_user_date_added),
        FavoriteAlbumsMode.create(
            element_type=ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_DESC,
            display_name="By Date Added (Desc)",
            sort_criteria_builder=build_album_sort_criteria_by_user_date_added,
            descending=True)]
    tidal_session: TidalSession = get_session()
    tidal_favorite_list: list[TidalAlbum] = tidal_util.try_get_all_favorites(tidal_session)
    current_tuple: FavoriteAlbumsMode
    for current_tuple in tuple_array:
        identifier: ItemIdentifier = ItemIdentifier(
            current_tuple.element_type.getName(),
            current_tuple.element_type.getName())
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, objid, current_tuple.display_name)
        entries.append(entry)
        descending: bool = current_tuple.descending
        sc_list_builder: Callable[[bool], list[AlbumSortCriteria]] = current_tuple.sort_criteria_builder
        sc_list: list[AlbumSortCriteria] = sc_list_builder(descending)
        favorite_list: list[TidalAlbum] = tidal_favorite_list.copy()
        favorite_list.sort(key=cmp_to_key(lambda x, y: compare_favorite_album_by_criteria_list(sc_list, x, y)))
        first: TidalAlbum = favorite_list[0] if favorite_list and len(favorite_list) > 0 else None
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(first) if first else None, entry)
    return entries


def handler_favorite_artists_by_name_asc(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handler_favorite_artists_common(
        descending=False,
        element_type=ElementType.FAVORITE_ARTISTS_BY_NAME_ASC,
        list_retriever=get_favorite_artists_by_name,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_favorite_artists_by_name_desc(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handler_favorite_artists_common(
        descending=True,
        element_type=ElementType.FAVORITE_ARTISTS_BY_NAME_DESC,
        list_retriever=get_favorite_artists_by_name,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_favorite_artists_by_user_date_added_asc(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handler_favorite_artists_common(
        descending=False,
        element_type=ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_ASC,
        list_retriever=get_favorite_artists_by_user_date_added,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_favorite_artists_by_user_date_added_desc(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handler_favorite_artists_common(
        descending=True,
        element_type=ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_DESC,
        list_retriever=get_favorite_artists_by_user_date_added,
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_favorite_artists_common(
        descending: bool,
        element_type: ElementType,
        list_retriever: Callable[[TidalSession, bool, int, int], list[TidalArtist]],
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    max_items: int = config.artists_per_page
    items: list[TidalArtist] = list_retriever(tidal_session, descending, max_items + 1, offset)
    next_artist: TidalArtist = items[config.artists_per_page] if len(items) == config.artists_per_page + 1 else None
    # shrink
    items = items[0:min(len(items), config.artists_per_page)] if len(items) > 0 else list()
    current: TidalArtist
    for current in items:
        entries.append(artist_to_entry(objid=objid, artist=current))
    if next_artist:
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=element_type,
            element_id=element_type.getName(),
            next_offset=offset + max_items)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_image_url(obj=next_artist),
            target=next_button)
        entries.append(next_button)
    return entries


def handler_tag_favorite_artists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tuple_array = [
        (
            ElementType.FAVORITE_ARTISTS_BY_NAME_ASC,
            "By Name (Asc)",
            build_artist_sort_criteria_by_name, False),
        (
            ElementType.FAVORITE_ARTISTS_BY_NAME_DESC,
            "By Name (Desc)",
            build_artist_sort_criteria_by_name, True),
        (
            ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_ASC,
            "By Date Added (Asc)",
            build_artist_sort_criteria_by_user_date_added, False),
        (
            ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_DESC,
            "By Date Added (Desc)",
            build_artist_sort_criteria_by_user_date_added, True)]
    tidal_session: TidalSession = get_session()
    for current_tuple in tuple_array:
        identifier: ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(),
            current_tuple[0].getName())
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, objid, current_tuple[1])
        entries.append(entry)
        descending: bool = current_tuple[3]
        sc_list_builder: Callable[[bool], list[ArtistSortCriteria]] = current_tuple[2]
        sc_list: list[ArtistSortCriteria] = sc_list_builder(descending)
        favorite_list: list[TidalArtist] = tidal_session.user.favorites.artists()
        favorite_list.sort(key=cmp_to_key(lambda x, y: compare_favorite_artist_by_criteria_list(sc_list, x, y)))
        first: TidalArtist = favorite_list[0] if favorite_list and len(favorite_list) > 0 else None
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(first) if first else None, entry)
    return entries


def handler_tag_favorite_tracks(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tuple_array = [
        (ElementType.FAVORITE_TRACKS_NAVIGABLE, "My Tracks (Navigable)"),
        (ElementType.FAVORITE_TRACKS_LIST, "My Tracks (list)")]
    tidal_session: TidalSession = get_session()
    for current_tuple in tuple_array:
        identifier: ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(),
            current_tuple[0].getName())
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, objid, current_tuple[1])
        fav_tracks: list[TidalTrack] = tidal_session.user.favorites.tracks(limit=10)
        random_track: TidalTrack = secrets.choice(fav_tracks) if fav_tracks else None
        upnp_util.set_album_art_from_uri(
            tidal_util.get_album_art_url_by_album_id(
                album_id=random_track.album.id,
                tidal_session=tidal_session)
            if random_track and random_track.album else None,
            entry)
        entries.append(entry)
    return entries


def handler_tag_all_playlists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    max_items: int = config.playlist_items_per_page
    playlists: list[TidalPlaylist] = tidal_session.user.playlist_and_favorite_playlists(offset=offset)
    next_playlist: TidalPlaylist = (playlists[config.playlist_items_per_page]
                                    if len(playlists) > config.playlist_items_per_page
                                    else None)
    playlists = (playlists[0:min(len(playlists), config.playlist_items_per_page)]
                 if len(playlists) > 0 else list())
    current: TidalPlaylist
    for current in playlists:
        try:
            entries.append(playlist_to_playlist_container(
                objid=objid,
                playlist=current))
        except Exception as ex:
            msgproc.log(f"Cannot create playlist entry for playlist_id [{current.id}] Exception [{ex}]")
    if next_playlist:
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.TAG,
            element_id=TagType.ALL_PLAYLISTS.getTagName(),
            next_offset=offset + max_items)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_image_url(obj=next_playlist),
            target=next_button)
        entries.append(next_button)
    return entries


def handler_tag_my_playlists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tidal_session: TidalSession = get_session()
    playlists: list[TidalUserPlaylist] = tidal_session.user.playlists()
    current: TidalUserPlaylist
    for current in playlists:
        entries.append(playlist_to_playlist_container(
            objid=objid,
            playlist=current))
    return entries


def handler_tag_playback_statistics(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    tidal_session: TidalSession = get_session()
    last_played_tracks: list[PlayedTrack] = persistence.get_last_played_tracks(max_tracks=20)
    most_played_tracks: list[PlayedTrack] = persistence.get_most_played_tracks(max_tracks=20)
    most_played_albums: list[PlayedAlbum] = persistence.get_most_played_albums(max_albums=10)
    random_most_played_album: PlayedAlbum = (
        secrets.choice(most_played_albums)
        if most_played_albums and len(most_played_albums) > 0
        else None)
    most_played_album_url: str = (tidal_util.get_album_art_url_by_album_id(
        album_id=random_most_played_album.album_id,
        tidal_session=tidal_session)
        if random_most_played_album else None)
    last_played_albums: list[str] = get_last_played_album_id_list(max_tracks=10)
    random_last_played_album_id: str = (secrets.choice(last_played_albums)
                                        if last_played_albums and len(last_played_albums) > 0
                                        else None)
    random_last_played_album_url: str = (tidal_util.get_album_art_url_by_album_id(
        album_id=random_last_played_album_id,
        tidal_session=tidal_session)
        if random_last_played_album_id
        else None)
    get_url_of_random: Callable[[list[PlayedTrack]], str] = (
        lambda album_list:
            tidal_util.get_album_art_url_by_album_id(
                album_id=secrets.choice(album_list).album_id,
                tidal_session=tidal_session)
        if album_list and len(album_list) > 0 else None)
    tuple_array = [
        (
            ElementType.RECENTLY_PLAYED_ALBUMS,
            "Recently played albums",
            random_last_played_album_url),
        (
            ElementType.MOST_PLAYED_ALBUMS,
            "Most Played Albums",
            most_played_album_url),
        (
            ElementType.RECENTLY_PLAYED_TRACKS_NAVIGABLE,
            "Recently played tracks (Navigable)",
            get_url_of_random(last_played_tracks)),
        (
            ElementType.RECENTLY_PLAYED_TRACKS_LIST,
            "Recently played tracks (List)",
            get_url_of_random(last_played_tracks)),
        (
            ElementType.MOST_PLAYED_TRACKS_NAVIGABLE,
            "Most played tracks (Navigable)",
            get_url_of_random(most_played_tracks)),
        (
            ElementType.MOST_PLAYED_TRACKS_LIST,
            "Most played tracks (List)",
            get_url_of_random(most_played_tracks))]
    for current_tuple in tuple_array:
        identifier: ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(),
            current_tuple[1])
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, objid, current_tuple[1])
        art_url: str = current_tuple[2]
        if art_url:
            upnp_util.set_album_art_from_uri(art_url, entry)
        entries.append(entry)
    return entries


def song_listening_queue_art_retriever(tidal_session: TidalSession) -> str:
    select_track_id: str = __get_random_track_id_from_listen_queue()
    # msgproc.log(f"song_listening_queue_art_retriever random track_id is [{select_track_id}]")
    select_track: TidalTrack
    select_track, _ = (tidal_util.try_get_track(tidal_session, select_track_id)
                       if select_track_id else (None, None))
    # msgproc.log(f"song_listening_queue_art_retriever select_track is None: [{select_track is None}] "
    #             f"type [{type(select_track) if select_track else None}]")
    # msgproc.log("song_listening_queue_art_retriever select_track.album is None: "
    #             f"[{select_track is None or select_track.album is None}]")
    return tidal_util.get_image_url(select_track.album) if select_track and select_track.album else None


def album_listening_queue_art_retriever(tidal_session: TidalSession) -> str:
    select_album_id: str = __get_random_album_id_from_listen_queue()
    return (tidal_util.get_album_art_url_by_album_id(
            album_id=select_album_id,
            tidal_session=tidal_session)
            if select_album_id else None)


def artist_listening_queue_art_retriever(tidal_session: TidalSession) -> str:
    select_artist_id: str = __get_random_artist_id_from_listen_queue()
    select_artist: TidalArtist = (tidal_util.try_get_artist(tidal_session, select_artist_id)
                                  if select_artist_id else None)
    return tidal_util.get_image_url(select_artist) if select_artist else None


def handler_tag_bookmarks(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    tuple_array = [
        (ElementType.BOOKMARK_ARTISTS, "Artists", artist_listening_queue_art_retriever),
        (ElementType.BOOKMARK_ALBUMS, "Albums", album_listening_queue_art_retriever),
        (ElementType.BOOKMARK_TRACKS, "Songs", song_listening_queue_art_retriever)
    ]
    tidal_session: TidalSession = get_session()
    for current_tuple in tuple_array:
        identifier: ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(),
            current_tuple[1])
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        entry: dict[str, any] = upmplgutils.direntry(id, objid, current_tuple[1])
        image_url: str = current_tuple[2](tidal_session) if current_tuple[2] else (None)
        upnp_util.set_album_art_from_uri(image_url, entry)
        entries.append(entry)
    return entries


def handler_tag_page(
        objid,
        page_extractor: Callable[[TidalSession], TidalPage],
        entries: list,
        offset: int,
        next_button_element_id: str) -> list:
    tidal_session: TidalSession = get_session()
    return page_to_entries(
        objid=objid,
        tidal_session=tidal_session,
        page_extractor=page_extractor,
        entries=entries,
        offset=offset,
        limit=config.page_items_per_page,
        paginate=True,
        next_button_element_type=ElementType.TAG,
        next_button_element_id=next_button_element_id)


def handler_tag_page_selection(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    tidal_session: TidalSession = get_session()
    for tag in get_page_selection():
        show_single_tag(objid, tidal_session, tag, entries)
    return entries


def handler_tag_genres_page(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    return handler_tag_page(
        objid=objid,
        page_extractor=lambda x: get_tidal_page(x, TidalPageDefinition.GENRES),
        entries=entries,
        offset=offset,
        next_button_element_id=TagType.GENRES_PAGE.getTagName())


def handler_tag_local_genres_page(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    return handler_tag_page(
        objid=objid,
        page_extractor=lambda x: get_tidal_page(x, TidalPageDefinition.LOCAL_GENRES),
        entries=entries,
        offset=offset,
        next_button_element_id=TagType.LOCAL_GENRES_PAGE.getTagName())


def handler_tag_moods_page(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    return handler_tag_page(
        objid=objid,
        page_extractor=lambda x: get_tidal_page(x, TidalPageDefinition.MOODS),
        entries=entries,
        offset=offset,
        next_button_element_id=TagType.MOODS_PAGE.getTagName())


def handler_tag_explore_new_music(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    return handler_tag_page(
        objid=objid,
        page_extractor=lambda x: get_tidal_page(x, TidalPageDefinition.NEW_MUSIC),
        entries=entries,
        offset=offset,
        next_button_element_id=TagType.EXPLORE_NEW_MUSIC.getTagName())


def handler_tag_explore_tidal_rising(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    return handler_tag_page(
        objid=objid,
        page_extractor=lambda x: get_tidal_page(x, TidalPageDefinition.RISING),
        entries=entries,
        offset=offset,
        next_button_element_id=TagType.EXPLORE_TIDAL_RISING.getTagName())


def handler_tag_featured(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    return handler_tag_page(
        objid=objid,
        page_extractor=lambda x: get_tidal_page(x, TidalPageDefinition.HOME),
        entries=entries,
        offset=offset,
        next_button_element_id=TagType.HOME.getTagName())


def handler_tag_explore(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    return handler_tag_page(
        objid=objid,
        page_extractor=lambda x: get_tidal_page(x, TidalPageDefinition.EXPLORE),
        entries=entries,
        offset=offset,
        next_button_element_id=TagType.EXPLORE.getTagName())


def handler_tag_for_you(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    return handler_tag_page(
        objid=objid,
        page_extractor=lambda x: get_tidal_page(x, TidalPageDefinition.FOR_YOU),
        entries=entries,
        offset=offset,
        next_button_element_id=TagType.FOR_YOU.getTagName())


def handler_tag_hires_page(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    return handler_tag_page(
        objid=objid,
        page_extractor=lambda x: get_tidal_page(x, TidalPageDefinition.HI_RES),
        entries=entries,
        offset=offset,
        next_button_element_id=TagType.HIRES_PAGE.getTagName())


def handler_tag_categories(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    current: TidalItemList
    category_index: int = 0
    tidal_session: TidalSession = get_session()
    for current in get_categories(tidal_session=tidal_session):
        msgproc.log(f"handler_tag_categories processing category[{category_index}]: [{current.title}] "
                    f"type [{type(current).__name__ if current else None}]")
        entry = category_to_entry(
            objid=objid,
            tidal_session=tidal_session,
            category=current)
        if entry:
            entries.append(entry)
        category_index += 1
    return entries


def create_next_button(
        objid,
        element_type: ElementType,
        element_id: any,
        next_offset: int,
        other_keys: dict[ItemIdentifierKey, any] = {}) -> dict:
    next_identifier: ItemIdentifier = ItemIdentifier(element_type.getName(), element_id)
    next_identifier.set(ItemIdentifierKey.OFFSET, next_offset)
    k: ItemIdentifierKey
    for k, v in other_keys.items():
        next_identifier.set(k, v)
    next_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(next_identifier))
    next_entry: dict = upmplgutils.direntry(
        next_id,
        objid,
        title="Next")
    return next_entry


def handler_element_mix(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tidal_session: TidalSession = get_session()
    mix_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    mix: TidalMix = tidal_session.mix(mix_id)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items: int = item_identifier.get(
        ItemIdentifierKey.MAX_ITEMS,
        config.max_playlist_or_mix_items_per_page)
    tracks: list = mix.items()[offset:offset + max_items]
    track_number: int = offset + 1
    context: Context = Context()
    context.add(key=ContextKey.IS_MIX, value=True)
    for track in tracks:
        if not isinstance(track, TidalTrack):
            continue
        options: dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry = track_to_entry(
            objid,
            track_adapter=instance_tidal_track_adapter(
                tidal_session=tidal_session,
                track=track),
            options=options,
            tidal_session=tidal_session,
            context=context)
        track_number += 1
        entries.append(track_entry)
    success_count: int = context.get(ContextKey.SUCCESS_COUNT)
    known_tracks_count: int = context.get(ContextKey.KNOWN_TRACKS_COUNT)
    guessed_tracks_count: int = context.get(ContextKey.GUESSED_TRACKS_COUNT)
    get_stream_count: int = context.get(ContextKey.GET_STREAM_COUNT)
    msgproc.log(f"handler_element_mix finished with success_count [{success_count}] "
                f"Known [{known_tracks_count}] Guessed [{guessed_tracks_count}] "
                f"Get Stream Count [{get_stream_count}]")
    return entries


def follow_page_link(page_link: TidalPageLink) -> any:
    next = page_link
    while next:
        # msgproc.log(f"follow_page_link type of next is [{type(next).__name__}]")
        if isinstance(next, TidalPageLink):
            try:
                next = next.get()
            except Exception as next_exc:
                msgproc.log(f"Cannot execute next for [{page_link.title}] due to [{type(next_exc)}] [{next_exc}]")
                next = None
            # msgproc.log(f"  next found: [{'yes' if next else 'no'}] type: [{type(next).__name__ if next else None}]")
        else:
            break
    return next


def get_items_in_page_link(page_link: TidalPageLink, limit: int = None) -> list[any]:
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"get_items_in_page_link title [{page_link.title}] limit [{limit}] entering ...")
    items: list[any] = list()
    linked = follow_page_link(page_link)
    # msgproc.log(f"get_items_in_page_link linked_object is [{type(linked).__name__ if linked else None}]")
    if not linked:
        msgproc.log("get_items_in_page_link linked_object is empty, returning empty list")
        return items
    if isinstance(linked, TidalPage):
        # msgproc.log(f"get_items_in_page_link: found a Page")
        for current in linked:
            if limit and len(items) >= limit:
                break
            if isinstance(current, TidalPageLink):
                new_page_link: TidalPageLink = current
                items.extend(get_items_in_page_link(
                    page_link=new_page_link,
                    limit=limit))
            elif isinstance(current, str):
                # skipping strings
                # msgproc.log(f"get_items_in_page_link skipping type [{type(current)}] ...")
                continue
            else:
                if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
                    msgproc.log(f"get_items_in_page_link appending type [{type(current)}] ...")
                items.append(current)
    else:
        msgproc.log(f"get_items_in_page_link[{page_link.api_path}]: found a [{type(linked).__name__}], not handled")
    return items


def handler_element_pagelink(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    thing_name: str = item_identifier.get(ItemIdentifierKey.THING_NAME)
    thing_value: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    api_path: str = item_identifier.get(ItemIdentifierKey.PAGE_LINK_API_PATH)
    category_title: str = item_identifier.get(ItemIdentifierKey.CATEGORY_TITLE)
    msgproc.log(f"handler_element_pagelink name [{thing_name}] "
                f"value [{thing_value}] category_title [{category_title}] "
                f"api_path [{api_path}]")
    tidal_session: TidalSession = get_session()
    try:
        page: TidalPage = tidal_session.page.get(api_path)
        if not page:
            msgproc.log("handler_element_pagelink page not found")
            return entries
        pagelink_identifier: tidal_util.PageLinkIdentifier = tidal_util.PageLinkIdentifier(
            thing_value,
            api_path,
            category_title)
        if page:
            page_to_entries(
                objid=objid,
                tidal_session=tidal_session,
                page=page,
                offset=offset,
                limit=config.page_items_per_page,
                next_button_element_type=ElementType.PAGELINK,
                pagelink_identifier=pagelink_identifier,
                paginate=True,
                entries=entries)
    except Exception as ex:
        msgproc.log(f"handler_element_pagelink could not retrieve page at api_path [{api_path}] [{ex}]")
    return entries


def handler_element_page(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    thing_value: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    if verbose:
        msgproc.log(f"handler_element_page [{thing_value}] at offset [{offset}]")
    tidal_session: TidalSession = get_session()
    page: TidalPage = tidal_session.page.get(thing_value)
    if verbose:
        msgproc.log(f"handler_element_page [{thing_value}] at offset [{offset}] page [{thing_value}]")
    return page_to_entries(
        objid=objid,
        tidal_session=tidal_session,
        page=page,
        entries=entries,
        offset=offset,
        limit=config.page_items_per_page,
        paginate=True,
        next_button_element_type=ElementType.PAGE,
        next_button_element_id=thing_value,
        page_reference=thing_value)


def page_to_entries(
        objid,
        tidal_session: TidalSession,
        entries: list,
        page_extractor: Callable[[TidalSession], TidalPage] = None,
        page: TidalPage = None,
        paginate: bool = False,
        offset: int = 0,
        limit: int = 100,
        next_button_element_type: ElementType = None,
        next_button_element_id: str = None,
        pagelink_identifier: tidal_util.PageLinkIdentifier = None,
        page_reference: str = None) -> list:
    max_items: int = limit if limit else config.page_items_per_page
    if page_extractor:
        page_extraction_start: float = time.time()
        page = page_extractor(tidal_session)
        if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
            msgproc.log("page_to_entries extraction elapsed "
                        f"[{(time.time() - page_extraction_start):.3f}] sec")
    # extracting items from page
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"page_to_entries for [{page.title}] from offset [{offset}]")
    current_offset: int = 0
    sliced: list[any] = list()
    limit_size: int = max_items + 1 if paginate else max_items
    for current_page_item in page:
        current_offset += 1
        if (current_offset - 1) < offset:
            continue
        if (len(sliced) < limit_size):
            # add to sliced
            sliced.append(current_page_item)
        else:
            break
    next_needed: bool = paginate and (len(sliced) == max_items + 1)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"next_needed=[{next_needed}] len(sliced)={len(sliced)} "
                    f"max_items=[{max_items}] limit_size=[{limit_size}]")
    next_item: any = sliced[max_items] if next_needed else None
    msgproc.log(f"page_to_entries next_item [{next_item is not None}]")
    page_item_selection: list[any] = sliced[0:len(sliced) - 1] if next_needed else sliced
    for current_page_item in page_item_selection:
        try:
            # msgproc.log(f"page_to_entries processing [{type(current_page_item)}] [{current_page_item}] ...")
            new_entry: dict = convert_page_item_to_entry(
                objid=objid,
                tidal_session=tidal_session,
                page_item=current_page_item)
            if new_entry:
                entries.append(new_entry)
        except Exception as ex:
            msgproc.log(f"page_to_entries could not convert type "
                        f"[{type(current_page_item).__name__ if current_page_item else None}] "
                        f"due to [{type(ex)}] [{ex}]")
    if next_item:
        msgproc.log("page_to_entries adding next button")
        # use next_item for next button
        if next_button_element_type:
            next_entry: dict[str, any] = None
            if ElementType.TAG == next_button_element_type:
                if next_button_element_id:
                    next_entry = create_next_button(
                        objid=objid,
                        element_type=next_button_element_type,
                        element_id=next_button_element_id,
                        next_offset=offset + config.page_items_per_page)
                else:
                    msgproc.log(f"next_button_element_type is [{ElementType.TAG.name}] "
                                "but next_button_element_id was not specified")
            elif ElementType.PAGE == next_button_element_type:
                msgproc.log("TODO add link to next page items")
                next_entry = create_next_button(
                    objid=objid,
                    element_type=ElementType.PAGE,
                    element_id=page_reference,
                    next_offset=offset + config.page_items_per_page)
            elif ElementType.PAGELINK == next_button_element_type:
                if (pagelink_identifier and
                        pagelink_identifier.api_path and
                        pagelink_identifier.category_title):
                    next_entry = create_next_button(
                        objid=objid,
                        element_type=ElementType.PAGELINK,
                        element_id=pagelink_identifier.value,
                        other_keys={
                            ItemIdentifierKey.PAGE_LINK_API_PATH: pagelink_identifier.api_path,
                            ItemIdentifierKey.CATEGORY_TITLE: pagelink_identifier.category_title},
                        next_offset=offset + config.page_items_per_page)
                else:
                    msgproc.log(f"next_button_element_type is [{ElementType.PAGELINK.name}] "
                                "but pagelink_identifier was not specified correctly")
            # other cases?
            if next_entry:
                album_art_uri: str = None
                if isinstance(next_item, TidalPageLink):
                    album_art_uri = get_image_url_for_pagelink(page_link=next_item)
                else:
                    album_art_uri = tidal_util.get_image_url(obj=next_item)
                upnp_util.set_album_art_from_uri(
                    album_art_uri=album_art_uri,
                    target=next_entry)
                entries.append(next_entry)
        else:
            msgproc.log("Cannot add next button because next_button_element_type is not set")
    return entries


def get_image_url_for_pagelink(page_link: TidalPageLink) -> str:
    item_list: list[any] = get_items_in_page_link(
        page_link=page_link,
        limit=config.get_page_items_for_tile_image())
    if not item_list or len(item_list) == 0:
        return None
    for first_item in item_list:
        # playlists and mixes are good candidates for image url, other types?
        if tidal_util.is_instance_of_any(
                obj=first_item,
                type_list=[TidalPlaylist, TidalMix, TidalAlbum, TidalTrack]):
            return tidal_util.get_image_url(first_item)
        else:
            msgproc.log(f"get_image_url_for_pagelink [{page_link.title}] "
                        f"skipping type [{type(first_item).__name__}] "
                        f"first_item [{first_item}]")


def get_image_url_for_page_from_static_images(page_link: TidalPageLink) -> str:
    docroot_base_url: str = tidal_util.get_docroot_base_url()
    if not docroot_base_url:
        return None
    if not config.get_config_param_as_bool(constants.ConfigParam.ALLOW_STATIC_IMAGES_FOR_PAGES):
        return None
    page_title: str = page_link.title
    page_link_image_url: str = None
    title_splitted: list[str] = [page_title]
    by_slash: list[str] = page_title.split(" / ")
    by_conjunction: list[str] = page_title.split(" & ")
    by_space: list[str] = page_title.split(" ")
    by_dash: list[str] = page_title.split("-")
    title_splitted.extend(by_slash)
    title_splitted.extend(by_conjunction)
    title_splitted.extend(by_space)
    title_splitted.extend(by_dash)
    title_split_elem: str
    for title_split_elem in title_splitted:
        cached_image_file: str = get_static_image(
            image_type=constants.PluginImageDirectory.PAGES.value,
            image_name_no_ext=title_split_elem)
        msgproc.log(f"convert_page_item_to_entry name [{title_split_elem}] cached image [{cached_image_file}]")
        if cached_image_file:
            # get url.
            sub_dir_list: list[str] = [
                constants.PluginConstant.PLUGIN_NAME.value,
                constants.PluginConstant.STATIC_IMAGES_DIRECTORY.value,
                constants.PluginImageDirectory.PAGES.value]
            page_link_image_url = tidal_util.get_web_document_root_file_url(
                dir_list=sub_dir_list,
                file_name=cached_image_file)
            break
    return page_link_image_url


def convert_page_item_to_entry(
        objid,
        tidal_session: TidalSession,
        page_item: TidalPageItem) -> any:
    if isinstance(page_item, TidalPlaylist):
        return playlist_to_playlist_container(
            objid=objid,
            playlist=page_item)
    elif isinstance(page_item, TidalMix):
        return mix_to_mix_container(
            objid=objid,
            mix=page_item)
    elif isinstance(page_item, TidalAlbum):
        return album_to_album_container(
            objid=objid,
            tidal_session=tidal_session,
            album=page_item)
    elif isinstance(page_item, TidalArtist):
        return artist_to_entry(
            objid=objid,
            artist=page_item)
    elif isinstance(page_item, TidalTrack):
        track: TidalTrack = page_item
        options: dict[str, any] = dict()
        set_option(options=options, option_key=OptionKey.SKIP_TRACK_NUMBER, option_value=True)
        return track_to_navigable_track(
            objid=objid,
            tidal_session=tidal_session,
            track_adapter=instance_tidal_track_adapter(
                tidal_session=tidal_session,
                track=track),
            track=track,
            options=options)
    elif isinstance(page_item, TidalPageLink):
        # msgproc.log(f"convert_page_item_to_entry creating a [{TidalPageLink.__name__}] ...")
        page_link: TidalPageLink = page_item
        image_id: str = page_link.image_id
        icon: any = page_link.icon
        msgproc.log(f"convert_page_item_to_entry name [{page_link.title}] image_id [{image_id}] icon [{icon}]")
        # page_link_image_url: str = get_image_url_for_pagelink(page_link=page_link)
        page_link_image_url: str = get_image_url_for_page_from_static_images(page_link=page_link)
        get_image_start: float = time.time()
        if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
            msgproc.log("convert_page_item_to_entry get_image for pagelink "
                        f"[{(time.time() - get_image_start):.3f}] sec")
        if not page_link_image_url:
            tile_image: TileImage = persistence.load_tile_image(tile_type=TileType.PAGE_LINK, tile_id=page_link.title)
            if tile_image:
                page_link_image_url = tile_image.tile_image
            else:
                # loading a tile image the hard way
                msgproc.log(f"convert_page_item_to_entry name [{page_link.title}] using content for tile image ...")
                page_link_image_url = get_image_url_for_pagelink(page_link=page_link)
                persistence.save_tile_image(
                    tile_type=TileType.PAGE_LINK,
                    tile_id=page_link.title,
                    tile_image=page_link_image_url)
        page_link_entry = page_link_to_entry(
            objid=objid,
            page_link=page_link)
        upnp_util.set_album_art_from_uri(
            album_art_uri=page_link_image_url,
            target=page_link_entry)
        return page_link_entry
    else:
        msgproc.log(f"convert_page_item_to_entry item of type "
                    f"{type(page_item).__name__ if page_item else None} not handled")
    return None


def get_first_not_stereo(audio_modes) -> str:
    msgproc.log(f"get_first_not_stereo [{audio_modes}] is_list "
                f"[{'yes' if isinstance(audio_modes, list) else 'no'}]")
    if not audio_modes:
        msgproc.log("audio_modes is None")
        return None
    if isinstance(audio_modes, list):
        msgproc.log("audio_modes is list")
        ml: list[str] = audio_modes
        m: str
        for m in ml if len(ml) > 0 else []:
            msgproc.log(f"  array comparing with {m} ...")
            if m != TidalAudioMode.stereo:
                msgproc.log(f"  {m} different from '{TidalAudioMode.stereo}'")
                return m
        return None
    # else it's a string
    msgproc.log(f"audio_modes is string {audio_modes}")
    return audio_modes if TidalAudioMode.stereo != audio_modes else None


def create_missing_artist_entry(
        objid: any,
        tidal_session: TidalSession,
        artist_id: str,
        entries: list) -> list:
    identifier: ItemIdentifier = ItemIdentifier(
        name=ElementType.MISSING_ARTIST.getName(),
        value=artist_id)
    entry_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(entry_id, objid, f"Missing artist [{artist_id}]")
    # is the album in the favorites?
    in_favorites: bool = artist_id in get_favorite_artist_id_list(tidal_session=tidal_session)
    # is the album in the bookmarks?
    in_bookmarks: bool = persistence.is_in_artist_listen_queue(artist_id)
    # in statistics ?
    # in_played_tracks: bool = persistence.is_album_in_played_tracks(artist_id)
    # in_metadata_cache: bool = persistence.is_album_in_metadata_cache(artist_id)
    msgproc.log(f"Artist [{artist_id}]: Favorite [{in_favorites}] "
                f"Bookmarked [{in_bookmarks}]")
    # add favorite action if needed
    if config.get_allow_favorite_actions() and in_favorites:
        entries.append(__create_artist_fav_action_button(
            objid=objid,
            artist_id=artist_id,
            album=None,
            in_favorites=True))
    # button for bookmark action if needed
    if config.get_allow_bookmark_actions() and in_bookmarks:
        entries.append(__create_album_listen_queue_action_button(
            objid=objid,
            album_id=artist_id,
            album=None,
            in_listen_queue=True))
    return entry


def create_missing_album_entry(
        objid: any,
        tidal_session: TidalSession,
        album_id: str,
        entries: list) -> list:
    identifier: ItemIdentifier = ItemIdentifier(
        name=ElementType.MISSING_ALBUM.getName(),
        value=album_id)
    entry_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(entry_id, objid, f"Missing album [{album_id}]")
    # is the album in the favorites?
    in_favorites: bool = album_id in get_favorite_album_id_list(tidal_session=tidal_session)
    # is the album in the bookmarks?
    in_bookmarks: bool = persistence.is_in_album_listen_queue(album_id)
    # in statistics ?
    in_played_tracks: bool = persistence.is_album_in_played_tracks(album_id)
    in_metadata_cache: bool = persistence.is_album_in_metadata_cache(album_id)
    msgproc.log(f"Album [{album_id}]: Favorite [{in_favorites}] "
                f"Bookmarked [{in_bookmarks}] "
                f"In Played Tracks [{in_played_tracks}] "
                f"In Metadata Cache [{in_metadata_cache}]")
    # if in played tracks, we automatically remove those entries
    if in_played_tracks:
        persistence.purge_album_from_played_tracks(album_id)
    # if in metadata cache, we automatically remove those entries
    if in_metadata_cache:
        persistence.purge_album_from_metadata_cache(album_id)
    # add favorite action if needed
    if config.get_allow_favorite_actions() and in_favorites:
        entries.append(__create_album_fav_action_button(
            objid=objid,
            album_id=album_id,
            album=None,
            in_favorites=True))
    # button for bookmark action if needed
    if config.get_allow_bookmark_actions() and in_bookmarks:
        entries.append(__create_album_listen_queue_action_button(
            objid=objid,
            album_id=album_id,
            album=None,
            in_listen_queue=True))
    return entry


def create_missing_track_entry(
        objid: any,
        tidal_session: TidalSession,
        track_id: str) -> list:
    identifier: ItemIdentifier = ItemIdentifier(
        name=ElementType.MISSING_TRACK.getName(),
        value=track_id)
    entry_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(entry_id, objid, f"Missing track [{track_id}]")
    # is the album in the favorites?
    in_favorites: bool = track_id in get_favorite_track_id_list(tidal_session=tidal_session)
    # is the album in the bookmarks?
    in_bookmarks: bool = persistence.is_in_track_listen_queue(track_id)
    # in statistics ?
    msgproc.log(f"Missing track [{track_id}] Favorite [{in_favorites}] Bookmarked [{in_bookmarks}]")
    # TODO execute actions on statistics and bookmarks?
    return entry


def handler_element_album_container(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    album: TidalAlbum = tidal_util.try_get_album(tidal_session, album_id)
    if not album:
        # we could not get the album
        msgproc.log(f"Could not load album with id [{album_id}], "
                    f"returning a {ElementType.MISSING_ALBUM.name} entry")
        # return a MISSING_ALBUM entry
        entries.append(create_missing_album_entry(
            objid=objid,
            tidal_session=tidal_session,
            album_id=album_id,
            entries=entries))
        return entries
    # force refresh of album cover
    tidal_util.get_image_url(album, refresh=True)
    identifier: ItemIdentifier = ItemIdentifier(
        name=ElementType.ALBUM.getName(),
        value=album_id)
    entry_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    in_favorites: bool = album_id in get_favorite_album_id_list(tidal_session=tidal_session)
    in_listen_queue: bool = persistence.is_in_album_listen_queue(album_id)
    album_entry_title: str = "Album" if config.titleless_single_album_view else album.name
    cached_tidal_quality: tidal_util.CachedTidalQuality = tidal_util.get_cached_audio_quality(
        album_id=album.id)
    badge: str = tidal_util.get_quality_badge(album=album, cached_tidal_quality=cached_tidal_quality)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"handler_element_album_container album_id [{album_id}] "
                    f"badge [{badge}] in_favorites [{in_favorites}] "
                    f"in_listen_queue [{in_listen_queue}]")
    if badge:
        album_entry_title = f"{album_entry_title} [{badge}]"
    if in_favorites and config.badge_favorite_album:
        album_entry_title = f"{album_entry_title} [F]"
    if config.show_album_id:
        album_entry_title = f"{album_entry_title} [{album_id}]"
    entry = upmplgutils.direntry(entry_id, objid, album_entry_title)
    upnp_util.set_class_album(target=entry)
    upnp_util.set_artist(artist=album.artist.name if album.artist else None, target=entry)
    tidal_util.add_album_adapter_metadata(album_adapter=tidal_album_to_adapter(album), target=entry)
    # setting album title does not seem to be relevant for upplay
    # upnp_util.set_album_title(album_title=album.name, target=entry)
    # setting description does not seem to be relevant for upplay
    # upnp_util.set_description(description=album.name, target=entry)
    upnp_util.set_date(datetime=album.release_date, target=entry)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), entry)
    entries.append(entry)
    # add Album track entry
    __add_album_tracks_entry(
        objid=objid,
        album=album,
        entries=entries)
    # add Artists
    __add_album_artists_entries(
        objid=objid,
        tidal_session=tidal_session,
        album=album,
        entries=entries)
    # add favorite action
    if config.get_allow_favorite_actions():
        entries.append(__create_album_fav_action_button(
            objid=objid,
            album_id=album_id,
            album=album,
            in_favorites=in_favorites))
    # button for bookmark action
    if config.get_allow_bookmark_actions():
        entries.append(__create_album_listen_queue_action_button(
            objid=objid,
            album_id=album_id,
            album=album,
            in_listen_queue=in_listen_queue))
    # button for removing from statistics
    if config.get_allow_statistics_actions():
        _add_album_rmv_from_stats(
            objid=objid,
            album=album,
            entries=entries)
    return entries


def _add_album_rmv_from_stats(
        objid,
        album: TidalAlbum,
        entries: list):
    has_been_played: bool = persistence.album_has_been_played(album.id)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"Album with id [{album.id}] name [{album.name}] by [{album.artist.name}] "
                    f"has been played: "
                    f"[{'yes' if has_been_played else 'no'}]")
    if has_been_played:
        # add entry for removing from stats
        rm_stats: ItemIdentifier = ItemIdentifier(
            ElementType.REMOVE_ALBUM_FROM_STATS.getName(),
            album.id)
        rm_stats_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(rm_stats))
        rm_entry: dict[str, any] = upmplgutils.direntry(rm_stats_id, objid, "Remove from Statistics")
        # use same album image for this button
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), rm_entry)
        entries.append(rm_entry)


def __create_artist_fav_action_button(
        objid,
        artist_id: str,
        artist: TidalArtist,
        in_favorites: bool) -> dict[str, any]:
    fav_action_elem: ElementType
    fav_action_text: str
    fav_action_elem, fav_action_text = (
        (ElementType.FAV_ALBUM_DEL, constants.ActionButtonTitle.FAVORITE_RMV.value) if in_favorites else
        (ElementType.FAV_ALBUM_ADD, constants.ActionButtonTitle.FAVORITE_ADD.value))
    fav_action: ItemIdentifier = ItemIdentifier(
        fav_action_elem.getName(),
        artist_id)
    fav_action_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(fav_action))
    fav_entry: dict[str, any] = upmplgutils.direntry(fav_action_id, objid, fav_action_text)
    upnp_util.set_album_art_from_uri(
        album_art_uri=tidal_util.get_image_url(artist) if artist else None,
        target=fav_entry)
    return fav_entry


def __create_album_fav_action_button(
        objid,
        album_id: str,
        album: TidalAlbum,
        in_favorites: bool) -> dict[str, any]:
    fav_action_elem: ElementType
    fav_action_text: str
    fav_action_elem, fav_action_text = (
        (ElementType.FAV_ALBUM_DEL, constants.ActionButtonTitle.FAVORITE_RMV.value) if in_favorites else
        (ElementType.FAV_ALBUM_ADD, constants.ActionButtonTitle.FAVORITE_ADD.value))
    fav_action: ItemIdentifier = ItemIdentifier(
        fav_action_elem.getName(),
        album_id)
    fav_action_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(fav_action))
    fav_entry: dict[str, any] = upmplgutils.direntry(fav_action_id, objid, fav_action_text)
    upnp_util.set_album_art_from_uri(
        album_art_uri=tidal_util.get_image_url(album) if album else None,
        target=fav_entry)
    return fav_entry


def __add_album_artists_entries(
        objid,
        tidal_session: TidalSession,
        album: TidalAlbum,
        entries: list):
    artist_list: list[TidalArtist] = get_artist_list(
        artist=album.artist,
        artists=album.artists,
        tracks=album.tracks())
    for current in artist_list:
        entries.append(artist_to_entry(objid=objid, artist=current))


def __add_album_tracks_entry(
        objid,
        album: TidalAlbum,
        entries: list):
    album_tracks: ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_TRACKS.getName(),
        album.id)
    album_tracks_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(album_tracks))
    album_tracks_entry: dict[str, any] = upmplgutils.direntry(
        album_tracks_id,
        objid,
        "Tracks")
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), album_tracks_entry)
    entries.append(album_tracks_entry)


def __create_album_listen_queue_action_button(
        objid,
        album_id: str,
        album: TidalAlbum,
        in_listen_queue: bool) -> dict[str, any]:
    listen_queue_action_dict: dict[str, str] = (constants.listening_queue_action_del_dict
                                                if in_listen_queue
                                                else constants.listening_queue_action_add_dict)
    listen_queue_action: str = listen_queue_action_dict[constants.ListeningQueueKey.ACTION_KEY.value]
    listen_queue_button_name: str = listen_queue_action_dict[constants.ListeningQueueKey.BUTTON_TITLE_KEY.value]
    lqb_identifier: ItemIdentifier = ItemIdentifier(ElementType.BOOKMARK_ALBUM_ACTION.getName(), album_id)
    lqb_identifier.set(ItemIdentifierKey.LISTEN_QUEUE_ACTION, listen_queue_action)
    lqb_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(lqb_identifier))
    lqb_entry: dict[str, any] = upmplgutils.direntry(
        lqb_id,
        objid,
        title=listen_queue_button_name)
    # use same album image for this button
    upnp_util.set_album_art_from_uri(
        album_art_uri=tidal_util.get_image_url(album) if album else None,
        target=lqb_entry)
    return lqb_entry


def _add_track_listen_queue_action_button(
        objid,
        track: TidalTrack,
        entries: list):
    in_listen_queue: bool = persistence.is_in_track_listen_queue(track_id=track.id)
    listen_queue_action_dict: dict[str, str] = (constants.listening_queue_action_del_dict
                                                if in_listen_queue
                                                else constants.listening_queue_action_add_dict)
    listen_queue_action: str = listen_queue_action_dict[constants.ListeningQueueKey.ACTION_KEY.value]
    listen_queue_button_name: str = listen_queue_action_dict[constants.ListeningQueueKey.BUTTON_TITLE_KEY.value]
    lqb_identifier: ItemIdentifier = ItemIdentifier(ElementType.BOOKMARK_TRACK_ACTION.getName(), track.id)
    lqb_identifier.set(ItemIdentifierKey.LISTEN_QUEUE_ACTION, listen_queue_action)
    lqb_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(lqb_identifier))
    lqb_entry: dict = upmplgutils.direntry(
        lqb_id,
        objid,
        title=listen_queue_button_name)
    # use same album image for this button
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(track.album), lqb_entry)
    entries.append(lqb_entry)


def handler_element_mix_container(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    mix_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    mix: TidalMix = tidal_session.mix(mix_id)
    return handle_element_mix_or_playlist_container(
        objid=objid,
        mix_or_playlist=mix,
        mix_or_playlist_size=len(mix.items()),
        element_type=ElementType.MIX,
        navigable_element_type=ElementType.MIX_NAVIGABLE,
        entries=entries)


def handler_element_playlist_container(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    playlist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    playlist: TidalPlaylist = tidal_session.playlist(playlist_id)
    return handle_element_mix_or_playlist_container(
        objid=objid,
        mix_or_playlist=playlist,
        mix_or_playlist_size=playlist.num_tracks,
        element_type=ElementType.PLAYLIST,
        navigable_element_type=ElementType.PLAYLIST_NAVIGABLE,
        entries=entries)


def handle_element_mix_or_playlist_container(
        objid,
        mix_or_playlist: any,
        mix_or_playlist_size: int,
        navigable_element_type: ElementType,
        element_type: ElementType,
        entries: list) -> list:
    # add navigable version
    navigable_identifier: ItemIdentifier = ItemIdentifier(
        navigable_element_type.getName(),
        mix_or_playlist.id)
    navigable_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(navigable_identifier))
    # load all tracks.
    get_all_tracks_start: float = time.time()
    all_tracks: list[TidalTrack] = tidal_util.get_all_mix_or_playlist_tracks(mix_or_playlist=mix_or_playlist)
    msgproc.log(f"handle_element_mix_or_playlist_container get all tracks [{(time.time() - get_all_tracks_start):.3f}] sec")
    navigable_entry = upmplgutils.direntry(navigable_id, objid, "Navigable")
    navigable_start: float = time.time()
    mix_or_playlist_image_url: str = tidal_util.get_image_url(
        obj=mix_or_playlist,
        refresh=True)
    upnp_util.set_album_art_from_uri(
        album_art_uri=mix_or_playlist_image_url,
        target=navigable_entry)
    msgproc.log(f"handle_element_mix_or_playlist_container navigable [{(time.time() - navigable_start):.3f}] sec")
    entries.append(navigable_entry)
    # BEGIN add artists in mix or playlist
    artists_identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTISTS_IN_MIX_OR_PLAYLIST.getName(),
        mix_or_playlist.id)
    # store if it's a playlist or a mix
    artists_identifier.set(key=ItemIdentifierKey.UNDERLYING_TYPE, value=element_type.getName())
    artists_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(artists_identifier))
    artists_entry = upmplgutils.direntry(artists_id, objid, "Artists")
    # same art as the playlist/mix itself
    # we must try to avoid expensive calls here
    select_artist: TidalArtist = secrets.choice(tidal_util.get_artists_from_tracks(all_tracks))
    upnp_util.set_album_art_from_uri(
        album_art_uri=tidal_util.get_image_url(select_artist),
        target=artists_entry)
    entries.append(artists_entry)
    # BEGIN add albums in mix or playlist
    albums_identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ALBUMS_IN_MIX_OR_PLAYLIST.getName(),
        mix_or_playlist.id)
    # store if it's a playlist or a mix
    albums_identifier.set(key=ItemIdentifierKey.UNDERLYING_TYPE, value=element_type.getName())
    albums_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(albums_identifier))
    albums_entry = upmplgutils.direntry(albums_id, objid, "Albums")
    # same art as the playlist/mix itself
    # we must try to avoid expensive calls here
    select_album: TidalAlbum = secrets.choice(tidal_util.get_albums_from_tracks(all_tracks))
    upnp_util.set_album_art_from_uri(
        album_art_uri=tidal_util.get_image_url(select_album),
        target=albums_entry)
    entries.append(albums_entry)
    # END add albums in mix or playlist
    # Add "All tracks"
    all_t_start: float = time.time()
    all_tracks_entry: dict[str, any] = tidal_util.create_mix_or_playlist_all_tracks_entry(
                                        objid=objid,
                                        element_type=element_type,
                                        thing_id=mix_or_playlist.id,
                                        thing=mix_or_playlist,
                                        all_tracks=all_tracks)
    if all_tracks_entry:
        entries.append(all_tracks_entry)
    msgproc.log(f"handle_element_mix_or_playlist_container all_tracks [{(time.time() - all_t_start):.3f}] sec")
    # END "All tracks"
    # Add segmented entries
    segmented_start: float = time.time()
    playlist_size: int = mix_or_playlist_size
    modulo: int = playlist_size % config.max_playlist_or_mix_items_per_page
    tile_count = int(playlist_size / config.max_playlist_or_mix_items_per_page) + (1 if modulo > 0 else 0)
    tile_idx: int
    for tile_idx in range(0, tile_count):
        # msgproc.log(f"\ttile_idx=[{tile_idx}] tile_count=[{tile_count}]")
        segment_identifier: ItemIdentifier = ItemIdentifier(
            element_type.getName(),
            mix_or_playlist.id)
        offset: int = tile_idx * config.max_playlist_or_mix_items_per_page
        max_items: int = (config.max_playlist_or_mix_items_per_page
                          if modulo == 0 or tile_idx < (tile_count - 1)
                          else modulo)
        # msgproc.log(f"\ttile_idx=[{tile_idx}] tile_count=[{tile_count}] "
        #             f"offset=[{offset}] max_items=[{max_items}] total=[{playlist_size}] "
        #             f"all_tracks=[{len(all_tracks)}]")
        segment_identifier.set(ItemIdentifierKey.OFFSET, offset)
        segment_identifier.set(ItemIdentifierKey.MAX_ITEMS, max_items)
        segment_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(segment_identifier))
        entry = upmplgutils.direntry(
            segment_id,
            objid,
            f"Items [{offset + 1} to {offset + max_items}]")
        # select a random item
        # slice all_tracks to the area of interest
        tracks_slice: list[TidalTrack] = all_tracks[offset:offset + max_items]
        slice_track: TidalTrack = secrets.choice(tracks_slice) if tracks_slice else None
        upnp_util.set_album_art_from_uri(
                album_art_uri=tidal_util.get_image_url(slice_track),
                target=entry)
        entries.append(entry)
    msgproc.log(f"handle_element_mix_or_playlist_container segmented [{(time.time() - segmented_start):.3f}] sec")
    return entries


def handler_element_albums_in_mix_or_playlist(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    mix_or_playlist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    initial_offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    prev_page_last_found_id: int = item_identifier.get(ItemIdentifierKey.LAST_FOUND_ID, None)
    underlying_type_str: str = item_identifier.get(ItemIdentifierKey.UNDERLYING_TYPE)
    underlying_type: ElementType = get_element_type_by_name(element_name=underlying_type_str)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"handler_element_albums_in_mix_or_playlist for [{mix_or_playlist_id}] "
                    f"of type [{underlying_type}] from offset [{initial_offset}]")
    tidal_session: TidalSession = get_session()
    tidal_obj: any = (tidal_session.playlist(mix_or_playlist_id)
                      if ElementType.PLAYLIST == underlying_type
                      else tidal_session.mix(mix_or_playlist_id))
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"handler_element_albums_in_mix_or_playlist tidal_obj [{type(tidal_obj)}]")
    id_extractor: Callable[[any], str] = lambda x: x.album.id if x and x.album else None
    album_id_list: list[str]
    track_list: list[TidalTrack]
    last_offset: int
    album_id_list, track_list, last_offset, _, _ = tidal_util.load_unique_ids_from_mix_or_playlist(
        tidal_session=tidal_session,
        tidal_obj_id=mix_or_playlist_id,
        tidal_obj_type=underlying_type_str,
        id_extractor=id_extractor,
        max_id_list_length=config.albums_per_page + 1,
        previous_page_last_found_id=prev_page_last_found_id,
        initial_offset=initial_offset)
    needs_next: bool = len(track_list) == config.albums_per_page + 1
    next_track: TidalTrack = track_list[config.albums_per_page] if needs_next else None
    # shrink
    album_id_list = album_id_list[0:config.albums_per_page] if needs_next else album_id_list
    track_list = track_list[0:config.albums_per_page] if needs_next else track_list
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"handler_element_albums_in_mix_or_playlist for [{mix_or_playlist_id}] "
                    f"of type [{underlying_type}] from offset [{initial_offset}] "
                    f"got [{len(track_list)}] albums (needs_next [{needs_next}])")
    last_displayed_album_id: str = None
    # create entries for albums
    track: TidalTrack
    album_id: str
    for track in track_list:
        album_id = track.album.id
        last_displayed_album_id = album_id
        try:
            album_adapter: AlbumAdapter = tidal_album_to_adapter(tidal_album=track.album)
            if album_adapter:
                entries.append(album_adapter_to_album_container(
                    objid=objid,
                    tidal_session=tidal_session,
                    album_adapter=album_adapter,
                    album=track.album))
        except Exception as ex:
            msgproc.log(f"Cannot add album with id [{album_id}] [{type(ex)}] [{ex}]")
    if needs_next:
        # create next
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.ALBUMS_IN_MIX_OR_PLAYLIST,
            element_id=mix_or_playlist_id,
            next_offset=last_offset,
            other_keys={
                ItemIdentifierKey.UNDERLYING_TYPE: underlying_type_str,
                ItemIdentifierKey.LAST_FOUND_ID: last_displayed_album_id})
        next_image_url: str = tidal_util.get_image_url(obj=next_track.album)
        upnp_util.set_album_art_from_uri(
            album_art_uri=next_image_url,
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_artists_in_mix_or_playlist(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    mix_or_playlist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    initial_offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    prev_page_last_found_id: int = item_identifier.get(ItemIdentifierKey.LAST_FOUND_ID, None)
    underlying_type_str: str = item_identifier.get(ItemIdentifierKey.UNDERLYING_TYPE)
    underlying_type: ElementType = get_element_type_by_name(element_name=underlying_type_str)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"handler_element_artists_in_mix_or_playlist for [{mix_or_playlist_id}] "
                    f"of type [{underlying_type}] from offset [{initial_offset}]")
    tidal_session: TidalSession = get_session()
    id_extractor: Callable[[any], str] = lambda x: x.artist.id if x and x.artist else None
    track_list: list[TidalTrack]
    last_offset: int
    _, track_list, last_offset, _, _ = tidal_util.load_unique_ids_from_mix_or_playlist(
        tidal_session=tidal_session,
        tidal_obj_id=mix_or_playlist_id,
        tidal_obj_type=underlying_type_str,
        id_extractor=id_extractor,
        max_id_list_length=config.artists_per_page + 1,
        previous_page_last_found_id=prev_page_last_found_id,
        initial_offset=initial_offset)
    needs_next: bool = len(track_list) == config.artists_per_page + 1
    next_artist_track: TidalTrack = track_list[config.artists_per_page] if needs_next else None
    # shrink
    track_list = track_list[0:config.artists_per_page] if needs_next else track_list
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"handler_element_artists_in_mix_or_playlist for [{mix_or_playlist_id}] "
                    f"of type [{underlying_type}] from offset [{initial_offset}] "
                    f"got [{len(track_list)}] artists (needs_next [{needs_next}])")
    last_displayed_artist_id: str = None
    # create entries for artists
    track: TidalTrack
    for track in track_list:
        last_displayed_artist_id = track.artist.id
        entries.append(artist_to_entry(
            objid=objid,
            artist=track.artist))
    if needs_next:
        # create next button
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.ARTISTS_IN_MIX_OR_PLAYLIST,
            element_id=mix_or_playlist_id,
            next_offset=last_offset,
            other_keys={
                ItemIdentifierKey.UNDERLYING_TYPE: underlying_type_str,
                ItemIdentifierKey.LAST_FOUND_ID: last_displayed_artist_id})
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_image_url(obj=next_artist_track.artist),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_all_tracks_in_playlist_or_mix(
        objid: any,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    mix_or_playlist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    underlying_type_str: str = item_identifier.get(ItemIdentifierKey.UNDERLYING_TYPE)
    underlying_type: ElementType = get_element_type_by_name(element_name=underlying_type_str)
    msgproc.log(f"handler_all_tracks_in_playlist_or_mix id [{mix_or_playlist_id}] "
                f"Underlying type [{underlying_type_str}] -> [{underlying_type}]")
    if mix_or_playlist_id is None or underlying_type is None:
        return entries
    tidal_session: TidalSession = get_session()
    mix_or_playlist: Union[TidalPlaylist, TidalMix] = (tidal_session.playlist(mix_or_playlist_id)
                                                       if ElementType.PLAYLIST == underlying_type
                                                       else tidal_session.mix(mix_or_playlist_id))
    msgproc.log(f"handler_all_tracks_in_playlist_or_mix - {type(mix_or_playlist).__name__} loaded")
    tracks: list[TidalTrack] = tidal_util.get_all_mix_or_playlist_tracks(mix_or_playlist=mix_or_playlist)
    context: Context = Context()
    options: dict[str, any] = {}
    track: TidalTrack
    track_counter: int = 0
    for track in tracks if tracks else []:
        if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
            msgproc.log(f"handler_all_tracks_in_playlist_or_mix adding track [{track.id}] "
                        f"[{track.name}] from "
                        f"[{track.album.name if track.album else ''}] by "
                        f"[{track.artist.name if track.artist else ''}]")
        set_option(
            options=options,
            option_key=OptionKey.FORCED_TRACK_NUMBER,
            option_value=track_counter + 1)
        try:
            track_entry: dict[str, any] = track_to_entry(
                objid=objid,
                tidal_session=tidal_session,
                track_adapter=instance_tidal_track_adapter(
                    tidal_session=tidal_session,
                    track=track),
                options=options,
                context=context)
            if track_entry:
                entries.append(track_entry)
        except Exception as ex:
            msgproc.log(f"Cannot add track [{track.id}] [{track_counter}] due to [{type(ex)}] [{ex}]")
        track_counter += 1
    return entries


def get_artist_list(
        artist: TidalArtist,
        artists: list[TidalArtist],
        tracks: list[TidalTrack] = list()) -> list[TidalArtist]:
    result: list[TidalArtist] = list()
    artist_id_set: set[str] = set()
    result.append(artist)
    artist_id_set.add(artist.id)
    for other in artists if artists else list():
        if other.id in artist_id_set:
            continue
        result.append(other)
        artist_id_set.add(other.id)
    track: TidalTrack
    track_artist: TidalArtist
    for track in tracks if tracks else list():
        track_artist = track.artist
        if track_artist.id in artist_id_set:
            continue
        result.append(track_artist)
        artist_id_set.add(track_artist.id)
        track_artists: list[TidalArtist] = track.artists
        for track_artist in track_artists if track_artists else list():
            if track_artist.id in artist_id_set:
                continue
            result.append(track_artist)
            artist_id_set.add(track_artist.id)
    return result


def handler_element_mix_navigable_item(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    return handler_element_mix_playlist_toptrack_navigable_item(
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_navigable_track(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    return handler_element_mix_playlist_toptrack_navigable_item(
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_playlist_navigable_item(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    return handler_element_mix_playlist_toptrack_navigable_item(
        objid=objid,
        item_identifier=item_identifier,
        entries=entries)


def handler_element_mix_playlist_toptrack_navigable_item(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    track_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    track: TidalTrack = tidal_session.track(track_id)
    track_options: dict[str, any] = dict()
    set_option(
        options=track_options,
        option_key=OptionKey.OVERRIDDEN_TRACK_NAME,
        option_value="Track")
    entries.append(track_to_track_container(
        objid=objid,
        tidal_session=tidal_session,
        track_adapter=choose_track_adapter_by_tidal_track(tidal_session=tidal_session, track=track),
        options=track_options))
    # favorite?
    in_fav: bool = is_favorite_track_id(tidal_session=tidal_session, track_id=track_id)
    msgproc.log(f"handler_element_mix_playlist_toptrack_navigable_item track [{track_id}] "
                f"favorite: [{in_fav}]")
    album: TidalAlbum = tidal_util.try_get_album(tidal_session=tidal_session, album_id=track.album.id)
    # add button to add or remove from favorites, if allowed
    if config.get_allow_favorite_actions():
        fav_button_action: str = constants.fav_action_del if in_fav else constants.fav_action_add
        fav_button_text: str = constants.fav_action_dict[fav_button_action][constants.fav_button_title_key]
        fav_action_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.TRACK_FAVORITE_ACTION.getName(),
            track_id)
        fav_action_identifier.set(ItemIdentifierKey.FAVORITE_ACTION, fav_button_action)
        fav_action_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(fav_action_identifier))
        fav_entry: dict[str, any] = upmplgutils.direntry(fav_action_id, objid, fav_button_text)
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album) if album else None, fav_entry)
        entries.append(fav_entry)
    # add bookmark action
    if config.get_allow_bookmark_actions():
        _add_track_listen_queue_action_button(
            objid=objid,
            track=track,
            entries=entries)
    # add link to artists
    artist_list: list[TidalArtist] = get_artist_list(
        artist=track.artist,
        artists=track.artists)
    for current in artist_list:
        artist: TidalArtist = tidal_util.try_get_artist(tidal_session, current.id)
        if not artist:
            continue
        entries.append(artist_to_entry(
            objid=objid,
            artist=artist))
    # add link to album
    if album:
        entries.append(album_to_album_container(
            objid=objid,
            tidal_session=tidal_session,
            album=album))
    # add remove from stats if needed
    if config.get_allow_statistics_actions():
        entries = add_remove_track_from_stats_if_needed(
            objid=objid,
            track=track,
            album=album,
            entries=entries)
    return entries


def handler_element_mix_navigable(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    mix_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    mix: TidalMix = tidal_session.mix(mix_id)
    tracks: list[TidalTrack] = mix.items()
    # apply offset
    tracks = tracks[offset:] if len(tracks) > offset else list()
    next_track: TidalTrack = (tracks[config.mix_items_per_page]
                              if len(tracks) > config.mix_items_per_page else None)
    # display count
    display_count: int = min(len(tracks), config.mix_items_per_page)
    tracks = tracks[0:display_count] if len(tracks) >= display_count else list()
    track_number: int = offset + 1
    for track in tracks:
        options: dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry = track_to_navigable_mix_item(
            objid=objid,
            tidal_session=tidal_session,
            track=track,
            options=options)
        track_number += 1
        entries.append(track_entry)
    if next_track:
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.MIX_NAVIGABLE,
            element_id=mix_id,
            next_offset=offset + config.mix_items_per_page)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_track.album.id,
                tidal_session=tidal_session),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_playlist_navigable(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    tidal_session: TidalSession = get_session()
    playlist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    playlist: TidalPlaylist = tidal_session.playlist(playlist_id)
    tracks: list[TidalTrack] = playlist.tracks(
        limit=config.mix_items_per_page + 1,
        offset=offset)
    to_display: list[TidalTrack] = (tracks[0:config.mix_items_per_page]
                                    if len(tracks) == config.mix_items_per_page + 1
                                    else tracks)
    next_track: TidalTrack = tracks[config.mix_items_per_page] if len(tracks) == config.mix_items_per_page + 1 else None
    msgproc.log(f"handler_element_playlist_navigable available from offset [{offset}] "
                f"is [{len(to_display)}] "
                f"last [{'yes' if len(tracks) <= config.mix_items_per_page else 'no'}]")
    track_number: int = offset + 1
    for track in to_display:
        options: dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_id: str = track.id if track else None
        track, _ = tidal_util.try_get_track(tidal_session, track_id)
        if track:
            try:
                track_entry: dict = track_to_navigable_playlist_item(
                    objid=objid,
                    tidal_session=tidal_session,
                    track=track,
                    options=options)
                if track_entry:
                    entries.append(track_entry)
            except Exception as ex:
                msgproc.log(f"handler_element_playlist_navigable Cannot create track entry for track_id [{track.id}] "
                            f"num [{track_number}] [{track.name}] [{track.album.id}] "
                            f"[{track.album.name}] Exception [{type(ex)}] [{ex}]")
        else:
            msgproc.log(f"Track with id [{track_id}] for track number [{track_number}] could not be loaded")
        track_number += 1
    if next_track:
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.PLAYLIST_NAVIGABLE,
            element_id=playlist_id,
            next_offset=offset + config.mix_items_per_page)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_track.album.id,
                tidal_session=tidal_session),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_playlist(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    return playlist_to_entries(
        objid=objid,
        tidal_session=get_session(),
        item_identifier=item_identifier,
        entries=entries)


def playlist_to_entries(
        objid,
        tidal_session: TidalSession,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    playlist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items: int = item_identifier.get(
        ItemIdentifierKey.MAX_ITEMS,
        config.max_playlist_or_mix_items_per_page)
    playlist: TidalPlaylist = tidal_session.playlist(playlist_id)
    tracks: list[TidalTrack] = playlist.tracks(offset=offset, limit=max_items)
    track_number: int = offset + 1
    counter: int = 0
    context: Context = Context()
    context.add(key=ContextKey.IS_PLAYLIST, value=True)
    for track in tracks:
        track_entry: dict = None
        # reload track
        track_id: str = track.id if track else None
        track, _ = tidal_util.try_get_track(tidal_session, track_id) if track_id else None
        if track:
            options: dict[str, any] = dict()
            set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
            try:
                track_adapter: TrackAdapter = choose_track_adapter_by_tidal_track(
                    tidal_session=tidal_session,
                    track=track)
                track_entry = track_to_track_container(
                    objid=objid,
                    tidal_session=tidal_session,
                    track_adapter=track_adapter,
                    options=options)
                if track_entry:
                    entries.append(track_entry)
            except Exception as ex:
                msgproc.log(f"playlist_to_entries Cannot create track entry for track_id [{track.id}] "
                            f"num [{track_number}] [{track.name}] [{track.album.id}] "
                            f"[{track.album.name}] Exception [{type(ex)}] [{ex}]")
        else:
            msgproc.log(f"Cannot load track with id [{track_id}] for track_number [{track_number}]")
        # let user know some tracks are missing
        track_number += 1
        counter += 1
        if max_items and counter == max_items:
            break
    success_count: int = context.get(ContextKey.SUCCESS_COUNT)
    known_tracks_count: int = context.get(ContextKey.KNOWN_TRACKS_COUNT)
    guessed_tracks_count: int = context.get(ContextKey.GUESSED_TRACKS_COUNT)
    get_stream_count: int = context.get(ContextKey.GET_STREAM_COUNT)
    msgproc.log(f"playlist_to_entries finished with success_count [{success_count}] "
                f"Known [{known_tracks_count}] Guessed [{guessed_tracks_count}] "
                f"Get Stream Count [{get_stream_count}]")
    return entries


def handler_element_album(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    album_id: int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    page: int = item_identifier.get(ItemIdentifierKey.ALBUM_PAGE, None)
    offset: int = page * constants.default_max_album_tracks_per_page if page else 0
    tidal_session: TidalSession = get_session()
    album: TidalAlbum = tidal_session.album(album_id)
    is_multidisc_album: bool = tidal_util.is_multidisc_album(album)
    tracks: list[TidalTrack] = album.tracks()
    track_count: int = len(tracks)
    paged: bool = False
    if track_count > constants.default_max_album_tracks_per_page:
        paged = True
    msgproc.log(f"Album [{album_id}] Title [{album.name}] by [{album.artist.name}] "
                f"multidisc: [{is_multidisc_album}] "
                f"num_tracks: [{len(tracks)}] paged: [{paged}] "
                f"page: [{page if page else 'None'}] "
                f"offset: [{offset}]")
    # msgproc.log("handler_element_album creating Context ...")
    context: Context = Context()
    context.add(key=ContextKey.IS_ALBUM, value=True)
    options: dict[str, any] = {}
    set_option(options, OptionKey.SKIP_TRACK_ARTIST, True)
    track_num: int = offset + 1
    track: TidalTrack
    try:
        for track in tracks:
            # msgproc.log(f"handler_element_album track {track_num}")
            set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_num)
            tidal_track_adapter: TrackAdapter = choose_track_adapter_by_tidal_track(
                tidal_session=tidal_session,
                track=track)
            track_entry = track_to_entry(
                objid=objid,
                track_adapter=tidal_track_adapter,
                options=options,
                tidal_session=tidal_session,
                context=context)
            entries.append(track_entry)
            track_num += 1
    except Exception as ex:
        msgproc.log(f"handler_element_album add track failed due to [{type(ex)}] [{ex}]")
    success_count: int = context.get(ContextKey.SUCCESS_COUNT)
    known_tracks_count: int = context.get(ContextKey.KNOWN_TRACKS_COUNT)
    guessed_tracks_count: int = context.get(ContextKey.GUESSED_TRACKS_COUNT)
    assumed_from_first_count: int = context.get(ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_COUNT)
    get_stream_count: int = context.get(ContextKey.GET_STREAM_COUNT)
    msgproc.log(f"handler_element_album for id [{album_id}] finished with "
                f"success_count [{success_count}] out of [{track_count}] "
                f"Known [{known_tracks_count}] Guessed [{guessed_tracks_count}] "
                f"Assumed by first [{assumed_from_first_count}] Get Stream Count [{get_stream_count}]")
    return entries


def handler_element_artist_album_catch_all(
        objid,
        item_identifier: ItemIdentifier,
        album_extractor: Callable[[Optional[int], int], list[TidalAlbum]],
        entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items: int = config.albums_per_page
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
    if not artist:
        msgproc.log(f"Artist with id {artist_id} not found")
        # bail
        return entries
    current: TidalAlbum
    album_list: list[TidalAlbum] = album_extractor(artist, max_items + 1, offset)
    # is there a next album?
    next_album: TidalAlbum = album_list[max_items] if len(album_list) == max_items + 1 else None
    # shrink if needed
    album_list = album_list[0:max_items] if len(album_list) == max_items + 1 else album_list
    options: dict[str, any] = dict()
    set_option(
        options=options,
        option_key=OptionKey.OMIT_ARTIST_TO_ALBUM_ENTRY_UNLESS_DIFFERENT,
        option_value=True)
    set_option(
        options=options,
        option_key=OptionKey.ALBUM_OMITTABLE_ARTIST_ID,
        option_value=artist_id)
    for current in album_list:
        if config.skip_non_stereo and not tidal_util.is_tidal_album_stereo(current):
            if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
                msgproc.log(tidal_util.not_stereo_skipmessage(current))
            continue
        entries.append(album_to_album_container(
            objid=objid,
            tidal_session=tidal_session,
            album=current,
            options=options))
    if next_album:
        # add next button
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=get_element_type_by_name(item_identifier.get(ItemIdentifierKey.THING_NAME)),
            element_id=item_identifier.get(ItemIdentifierKey.THING_VALUE),
            next_offset=offset + max_items)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_album.id,
                tidal_session=tidal_session,
                album=next_album),
            target=next_button)
        entries.append(next_button)
        # set album art for next button
    return entries


def handler_element_artist_album_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handler_element_artist_album_catch_all(
        objid,
        item_identifier=item_identifier,
        album_extractor=lambda x, limit, offset: x.get_albums(limit, offset),
        entries=entries)


def handler_element_artist_album_ep_singles(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handler_element_artist_album_catch_all(
        objid,
        item_identifier=item_identifier,
        album_extractor=lambda x, limit, offset: x.get_ep_singles(limit, offset),
        entries=entries)


def handler_element_artist_album_others(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handler_element_artist_album_catch_all(
        objid,
        item_identifier=item_identifier,
        album_extractor=lambda x, limit, offset: x.get_other(limit, offset),
        entries=entries)


def get_similar_artists(artist: TidalArtist) -> list[TidalArtist]:
    try:
        return artist.get_similar()
    except Exception as ex:
        msgproc.log(f"Cannot get similar artists for artist id [{artist.id}] name [{artist.name}] Exception [{type(ex)}] [{ex}]")
    return list()


def get_top_tracks(
        artist: TidalArtist,
        limit: Optional[int] = None,
        offset: int = 0) -> list[TidalTrack]:
    try:
        return artist.get_top_tracks(
            limit=limit,
            offset=offset)
    except Exception as ex:
        msgproc.log(f"Cannot get top tracks for artist id [{artist.id}] name [{artist.name}] Exception [{type(ex)}] [{ex}]")
    return list()


def get_radio(artist: TidalArtist) -> list[TidalTrack]:
    try:
        return artist.get_radio()
    except Exception as ex:
        msgproc.log(f"Cannot get radio for artist id [{artist.id}] name [{artist.name}] Exception [{type(ex)}] [{ex}]")
    return list()


def handler_element_similar_artists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
    if not artist:
        return entries
    items: list[TidalArtist] = get_similar_artists(artist)
    # apply offset
    items = items[offset:] if len(items) > offset else ()
    # needs next?
    next_needed: bool = len(items) > config.artists_per_page
    next_artist: TidalArtist = items[config.artists_per_page] if next_needed else None
    items = items[0:config.artists_per_page] if len(items) > config.artists_per_page else items
    current: TidalArtist
    for current in items if items else list():
        entries.append(artist_to_entry(
            objid=objid,
            artist=current))
    if next_artist:
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.SIMILAR_ARTISTS,
            element_id=artist_id,
            next_offset=offset + config.artists_per_page)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_image_url(obj=next_artist),
            target=next_entry)
        entries.append(next_entry)
    return entries


def add_tracks_to_navigable_entries(
        objid,
        tidal_session: TidalSession,
        items: list[TidalTrack],
        entries: list) -> list:
    current: TidalTrack
    for current in items if items else list():
        options: dict[str, any] = dict()
        set_option(options=options, option_key=OptionKey.SKIP_TRACK_NUMBER, option_value=True)
        entries.append(track_to_navigable_track(
            objid=objid,
            tidal_session=tidal_session,
            track_adapter=choose_track_adapter_by_tidal_track(
                tidal_session=tidal_session,
                track=current),
            options=options))
    return entries


def add_track_as_list_to_entries(
        objid,
        tidal_session: TidalSession,
        items: list[TidalTrack],
        entries: list) -> list:
    context: Context = Context()
    context.add(key=ContextKey.IS_PLAYLIST, value=True)
    current: TidalTrack
    track_num: int = 1
    for current in items if items else list():
        options: dict[str, any] = dict()
        set_option(options=options, option_key=OptionKey.FORCED_TRACK_NUMBER, option_value=track_num)
        entries.append(track_to_entry(
            objid=objid,
            track_adapter=choose_track_adapter_by_tidal_track(
                tidal_session=tidal_session,
                track=current),
            options=options,
            tidal_session=tidal_session,
            context=context))
        track_num += 1
    return entries


def handler_element_favorite_tracks_navigable(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items: int = config.tracks_per_page
    tidal_session: TidalSession = get_session()
    items: list[TidalTrack] = tidal_session.user.favorites.tracks(
        limit=max_items + 1,
        offset=offset)
    next_track: TidalTrack = items[max_items] if len(items) == max_items + 1 else None
    # shrink
    items = items[0:max_items] if next_track else items
    entries = add_tracks_to_navigable_entries(
        objid=objid,
        tidal_session=tidal_session,
        items=items,
        entries=entries)
    if next_track:
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.FAVORITE_TRACKS_NAVIGABLE,
            element_id=ElementType.FAVORITE_TRACKS_NAVIGABLE.getName(),
            next_offset=offset + max_items)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_track.album.id,
                tidal_session=tidal_session),
            target=next_button)
        entries.append(next_button)
    return entries


def handler_element_favorite_tracks_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    limit: int = config.tracks_per_page
    # in order to understand if next is needed, we ask one more track
    tracks: list[TidalTrack] = tidal_session.user.favorites.tracks(offset=offset, limit=limit + 1)
    needs_next: bool = tracks and len(tracks) > limit
    next_track: TidalTrack = tracks[limit] if needs_next else None
    # shrink if needed
    tracks = tracks[0:limit] if needs_next else tracks
    options: dict[str, any] = dict()
    track_number: int = offset + 1
    current: TidalTrack
    for current in tracks:
        set_option(
            options=options,
            option_key=OptionKey.FORCED_TRACK_NUMBER,
            option_value=track_number)
        try:
            entries.append(track_to_track_container(
                objid=objid,
                tidal_session=tidal_session,
                track_adapter=choose_track_adapter_by_tidal_track(
                    tidal_session=tidal_session,
                    track=current),
                options=options))
        except Exception as ex:
            msgproc.log(f"handler_element_favorite_tracks_list cannot add track with id {current.id} "
                        f"due to [{type(ex)}] [{ex}]")
        track_number += 1
    if next_track:
        # create next
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.FAVORITE_TRACKS_LIST,
            element_id=ElementType.FAVORITE_TRACKS_LIST.getName(),
            next_offset=offset + config.tracks_per_page)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_track.album.id,
                tidal_session=tidal_session),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_artist_top_tracks_navigable(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items: int = config.artists_per_page
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
    if not artist:
        return entries
    items: list[TidalTrack] = get_top_tracks(
        artist=artist,
        limit=max_items + 1,
        offset=offset)
    next_track: TidalTrack = items[max_items] if len(items) == max_items + 1 else None
    # shrink
    items = items[0:max_items] if next_track else items
    entries = add_tracks_to_navigable_entries(
        objid=objid,
        tidal_session=tidal_session,
        items=items,
        entries=entries)
    if next_track:
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.ARTIST_TOP_TRACKS_NAVIGABLE,
            element_id=artist_id,
            next_offset=offset + max_items)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_track.album.id,
                tidal_session=tidal_session),
            target=next_button)
        entries.append(next_button)
    return entries


def handler_element_artist_top_tracks_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
    if not artist:
        return entries
    items: list[TidalTrack] = get_top_tracks(
        artist=artist,
        offset=offset,
        limit=config.tracks_per_page + 1)
    # needs next?
    next_track: TidalTrack = items[config.tracks_per_page] if len(items) == config.tracks_per_page + 1 else None
    items = items[0:config.tracks_per_page] if next_track else items
    options: dict[str, any] = dict()
    set_option(options=options, option_key=OptionKey.SKIP_TRACK_NUMBER, option_value=True)
    set_option(options=options, option_key=OptionKey.TRACK_OMITTABLE_ARTIST_NAME, option_value=artist.name)
    items = items[0:config.tracks_per_page] if len(items) > config.tracks_per_page else items
    current: TidalTrack
    for current in items:
        entries.append(track_to_track_container(
            objid=objid,
            tidal_session=tidal_session,
            track_adapter=choose_track_adapter_by_tidal_track(
                tidal_session=tidal_session,
                track=current),
            options=options))
    if next_track:
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.ARTIST_TOP_TRACKS_LIST,
            element_id=artist_id,
            next_offset=offset + config.tracks_per_page)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_track.album.id,
                tidal_session=tidal_session),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_artist_radio_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
    if not artist:
        return entries
    items: list[TidalTrack] = get_radio(artist)
    # apply offset
    items = items[offset:] if len(items) > offset else list()
    # needs next?
    next_track: TidalTrack = items[config.tracks_per_page] if len(items) > config.tracks_per_page else None
    options: dict[str, any] = dict()
    set_option(options=options, option_key=OptionKey.SKIP_TRACK_NUMBER, option_value=True)
    items = items[0:config.tracks_per_page] if len(items) > config.tracks_per_page else items
    current: TidalTrack
    for current in items:
        entries.append(track_to_track_container(
            objid=objid,
            tidal_session=tidal_session,
            track_adapter=choose_track_adapter_by_tidal_track(
                tidal_session=tidal_session,
                track=current),
            options=options))
    if next_track:
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.ARTIST_RADIO_LIST,
            element_id=artist_id,
            next_offset=offset + config.tracks_per_page)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_track.album.id,
                tidal_session=tidal_session),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_artist_radio_navigable(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
    if not artist:
        return entries
    items: list[TidalTrack] = get_radio(artist)
    # apply offset
    items = items[offset:] if len(items) > offset else ()
    # needs next?
    next_track: TidalTrack = items[config.tracks_per_page] if len(items) > config.tracks_per_page else None
    options: dict[str, any] = dict()
    set_option(options=options, option_key=OptionKey.SKIP_TRACK_NUMBER, option_value=True)
    items = items[0:config.tracks_per_page] if len(items) > config.tracks_per_page else items
    current: TidalTrack
    for current in items:
        entries.append(track_to_navigable_track(
            objid=objid,
            tidal_session=tidal_session,
            track_adapter=choose_track_adapter_by_tidal_track(
                tidal_session=tidal_session,
                track=current),
            track=current,
            options=options))
    if next_track:
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.ARTIST_RADIO_NAVIGABLE,
            element_id=artist_id,
            next_offset=offset + config.tracks_per_page)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_track.album.id,
                tidal_session=tidal_session),
            target=next_entry)
        entries.append(next_entry)
    return entries


def get_favorite_artist_id_list(tidal_session: TidalSession) -> list[str]:
    item_list: list[str] = list()
    offset: int = 0
    limit: int = 100
    while True:
        fav_list: list[TidalArtist] = tidal_session.user.favorites.artists(limit=limit, offset=offset)
        current: TidalArtist
        for current in fav_list:
            item_list.append(current.id)
        if not fav_list or len(fav_list) < limit:
            break
        offset += limit
    return item_list


def get_favorite_album_id_list(tidal_session: TidalSession) -> list[str]:
    item_list: list[str] = list()
    offset: int = 0
    limit: int = 100
    while True:
        fav_list: list[TidalAlbum] = tidal_session.user.favorites.albums(limit=limit, offset=offset)
        current: TidalAlbum
        for current in fav_list if fav_list else list():
            item_list.append(current.id)
        if not fav_list or len(fav_list) < limit:
            break
        offset += limit
    return item_list


def get_favorite_track_id_list(tidal_session: TidalSession) -> list[int]:
    item_list: list[str] = list()
    offset: int = 0
    limit: int = 100
    while True:
        fav_list: list[TidalTrack] = tidal_session.user.favorites.tracks(limit=limit, offset=offset)
        current: TidalTrack
        for current in fav_list if fav_list else list():
            item_list.append(current.id)
        if not fav_list or len(fav_list) < limit:
            break
        offset += limit
    return item_list


def is_favorite_track_id(tidal_session: TidalSession, track_id: any) -> bool:
    if not track_id:
        return False
    fav_list: list[int] = get_favorite_track_id_list(tidal_session)
    if isinstance(track_id, int):
        return track_id in fav_list
    if isinstance(track_id, str):
        current: int
        for current in fav_list:
            if str(current) == track_id:
                return True
    return False


def handler_element_artist_add_to_fav(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    if artist_id not in get_favorite_artist_id_list(tidal_session=tidal_session):
        tidal_session.user.favorites.add_artist(artist_id=artist_id)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(),
        artist_id)
    return handler_element_artist(objid, item_identifier=identifier, entries=entries)


def handler_element_album_add_to_fav(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    if album_id not in get_favorite_album_id_list(tidal_session=tidal_session):
        tidal_session.user.favorites.add_album(album_id=album_id)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_CONTAINER.getName(),
        album_id)
    return handler_element_album_container(objid, item_identifier=identifier, entries=entries)


def handler_element_artist_del_from_fav(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    if artist_id in get_favorite_artist_id_list(tidal_session=tidal_session):
        tidal_session.user.favorites.remove_artist(artist_id=artist_id)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(),
        artist_id)
    return handler_element_artist(objid, item_identifier=identifier, entries=entries)


def handler_element_album_del_from_fav(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    if album_id in get_favorite_album_id_list(tidal_session=tidal_session):
        tidal_session.user.favorites.remove_album(album_id=album_id)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_CONTAINER.getName(),
        album_id)
    return handler_element_album_container(objid, item_identifier=identifier, entries=entries)


def get_artist_albums_image_url(tidal_session: TidalSession, artist_id: str) -> str:
    return get_artist_albums_by_album_extractor_image_url(
        tidal_session=tidal_session,
        artist_id=artist_id,
        extractor=lambda artist: artist.get_albums())


def get_artist_albums_ep_singles_image_url(tidal_session: TidalSession, artist_id: str) -> str:
    return get_artist_albums_by_album_extractor_image_url(
        tidal_session=tidal_session,
        artist_id=artist_id,
        extractor=lambda artist: artist.get_ep_singles())


def get_artist_albums_others_image_url(tidal_session: TidalSession, artist_id: str) -> str:
    return get_artist_albums_by_album_extractor_image_url(
        tidal_session=tidal_session,
        artist_id=artist_id,
        extractor=lambda artist: artist.get_other())


def get_artist_albums_by_album_extractor_image_url(
        tidal_session: TidalSession,
        artist_id: str,
        extractor: Callable[[TidalArtist], list[TidalAlbum]]) -> str:
    try:
        artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
        if not artist:
            return None
        album_list: list[TidalAlbum] = extractor(artist)
        return choose_album_image_url(album_list)
    except Exception:
        msgproc.log(f"Cannot get albums for artist_id [{artist.id}]")


def get_artist_top_tracks_image_url(tidal_session: TidalSession, artist_id: str) -> str:
    try:
        artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
        if not artist:
            return None
        tracks: list[TidalTrack] = artist.get_top_tracks() if artist else None
        select: TidalTrack = secrets.choice(tracks) if tracks and len(tracks) > 0 else None
        return tidal_util.get_album_art_url_by_album_id(
            album_id=select.album.id,
            tidal_session=tidal_session)
    except Exception:
        msgproc.log(f"Cannot get top tracks image for artist_id [{artist.id}]")


def get_artist_radio_image_url(tidal_session: TidalSession, artist_id: str) -> str:
    try:
        artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
        if not artist:
            return None
        tracks: list[TidalTrack] = artist.get_radio() if artist else None
        select: TidalTrack = secrets.choice(tracks) if tracks and len(tracks) > 0 else None
        return (tidal_util.get_album_art_url_by_album_id(
                album_id=select.album.id,
                tidal_session=tidal_session)
                if select and select.album
                else None)
    except Exception:
        msgproc.log(f"Cannot get artist radio image for artist_id [{artist.id}]")


def choose_album_image_url(album_list: list[TidalAlbum]) -> str:
    select: TidalAlbum = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
    return tidal_util.get_image_url(select) if select else None


def get_similar_artists_image_url(tidal_session: TidalSession, artist_id: str) -> str:
    try:
        artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
        if not artist:
            return None
        similar_artist_list: list[TidalArtist] = artist.get_similar() if artist else None
        select: TidalArtist = (secrets.choice(similar_artist_list)
                               if similar_artist_list and len(similar_artist_list) > 0
                               else None)
        return tidal_util.get_image_url(select) if select else None
    except Exception:
        msgproc.log(f"Cannot get similar artists for artist_id [{artist.id}]")


def handler_element_artist_related(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    missing_artist_art: bool = item_identifier.get(ItemIdentifierKey.MISSING_ARTIST_ART)
    tidal_session: TidalSession = get_session()
    artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
    if not artist:
        return entries
    if not artist:
        msgproc.log(f"Artist with id {artist_id} not found")
        return entries
    album_tuple_array = [
        (ElementType.ARTIST_TOP_TRACKS_NAVIGABLE, "Top Tracks (Navigable)", get_artist_top_tracks_image_url),
        (ElementType.ARTIST_TOP_TRACKS_LIST, "Top Tracks (List)", get_artist_top_tracks_image_url),
        (ElementType.ARTIST_RADIO_NAVIGABLE, "Radio (Navigable)", get_artist_radio_image_url),
        (ElementType.ARTIST_RADIO_LIST, "Radio (List)", get_artist_radio_image_url),
        (ElementType.SIMILAR_ARTISTS, "Similar Artists", get_similar_artists_image_url),
    ]
    for album_tuple in album_tuple_array:
        # msgproc.log(f"handler_element_artist - artist_id {artist_id} current tuple [{album_tuple[0]}]")
        if missing_artist_art:
            continue
        try:
            album_art_uri: str = album_tuple[2](tidal_session, artist_id) if album_tuple[2] else None
            identifier: ItemIdentifier = ItemIdentifier(
                album_tuple[0].getName(),
                artist_id)
            id: str = identifier_util.create_objid(
                objid=objid,
                id=identifier_util.create_id_from_identifier(identifier))
            entry = upmplgutils.direntry(id, objid, album_tuple[1])
            upnp_util.set_album_art_from_uri(album_art_uri, entry)
            entries.append(entry)
        except Exception:
            msgproc.log(f"handler_element_artist_related - cannot create [{album_tuple[0]}]")
    return entries


def handler_element_artist(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    missing_artist_art: bool = item_identifier.get(ItemIdentifierKey.MISSING_ARTIST_ART)
    tidal_session: TidalSession = get_session()
    artist: TidalArtist = tidal_util.try_get_artist(tidal_session, artist_id)
    if not artist:
        return create_missing_artist_entry(
            objid=objid,
            tidal_session=tidal_session,
            artist_id=artist_id,
            artist=None,
            entries=entries)
    # force reload artist image
    tidal_util.get_image_url(artist, refresh=True)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"Loading page for artist_id: [{artist_id}] "
                    f"artist.id: [{artist.id}] "
                    f"artist.name: [{artist.name}]")
    album_tuple_array = [
        (ElementType.ARTIST_ALBUM_ALBUMS, "Albums", get_artist_albums_image_url),
        (ElementType.ARTIST_ALBUM_EP_SINGLES, "EP and Singles", get_artist_albums_ep_singles_image_url),
        (ElementType.ARTIST_ALBUM_OTHERS, "Other Albums", get_artist_albums_others_image_url)]
    for album_tuple in album_tuple_array:
        # msgproc.log(f"handler_element_artist - artist_id {artist_id} current tuple [{album_tuple[0]}]")
        try:
            album_art_uri: str = album_tuple[2](tidal_session, artist_id) if album_tuple[2] else None
            # if there is no album_art_uri, it means there are no albums in the category
            if not album_art_uri:
                continue
            identifier: ItemIdentifier = ItemIdentifier(
                album_tuple[0].getName(),
                artist_id)
            id: str = identifier_util.create_objid(
                objid=objid,
                id=identifier_util.create_id_from_identifier(identifier))
            entry = upmplgutils.direntry(id, objid, album_tuple[1])
            upnp_util.set_album_art_from_uri(album_art_uri, entry)
            entries.append(entry)
        except Exception:
            msgproc.log(f"handler_element_artist - cannot create [{album_tuple[0]}]")
    # add related node
    related_identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_FOCUS.getName(),
        artist_id)
    related_identifier.set(ItemIdentifierKey.MISSING_ARTIST_ART, missing_artist_art)
    related_identifier_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(related_identifier))
    entry = upmplgutils.direntry(
        related_identifier_id,
        objid,
        "Focus")
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(artist), entry)
    entries.append(entry)
    if config.get_allow_favorite_actions():
        in_favorites: bool = artist.id in get_favorite_artist_id_list(tidal_session=tidal_session)
        fav_action_elem: ElementType
        fav_action_text: str
        fav_action_elem, fav_action_text = (
            (ElementType.FAV_ARTIST_DEL, constants.ActionButtonTitle.FAVORITE_RMV.value) if in_favorites
            else (ElementType.FAV_ARTIST_ADD, constants.ActionButtonTitle.FAVORITE_ADD.value))
        # msgproc.log(f"Artist with id [{artist_id}] name [{artist_name}] is in favorites: "
        #             f"[{'yes' if in_favorites else 'no'}]")
        fav_action: ItemIdentifier = ItemIdentifier(
            fav_action_elem.getName(),
            artist_id)
        fav_action_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(fav_action))
        fav_entry: dict[str, any] = upmplgutils.direntry(fav_action_id, objid, fav_action_text)
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(artist), fav_entry)
        entries.append(fav_entry)
    if config.get_allow_bookmark_actions():
        lqb_entry: dict[str, any] = create_listen_queue_action_for_artist_view(objid, artist)
        entries.append(lqb_entry)
    return entries


def create_listen_queue_action_for_artist_view(
        objid,
        artist: TidalArtist) -> dict[str, any]:
    artist_id: str = artist.id
    in_listen_queue: bool = persistence.is_in_artist_listen_queue(artist_id)
    listen_queue_action_dict: dict[str, str] = (constants.listening_queue_action_del_dict
                                                if in_listen_queue
                                                else constants.listening_queue_action_add_dict)
    listen_queue_action: str = listen_queue_action_dict[constants.ListeningQueueKey.ACTION_KEY.value]
    listen_queue_button_name: str = listen_queue_action_dict[constants.ListeningQueueKey.BUTTON_TITLE_KEY.value]
    lqb_identifier: ItemIdentifier = ItemIdentifier(ElementType.BOOKMARK_ARTIST_ACTION.getName(), artist_id)
    lqb_identifier.set(ItemIdentifierKey.LISTEN_QUEUE_ACTION, listen_queue_action)
    lqb_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(lqb_identifier))
    lqb_entry: dict = upmplgutils.direntry(
        lqb_id,
        objid,
        title=listen_queue_button_name)
    # use same album image for this button
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(artist), lqb_entry)
    return lqb_entry


def add_remove_track_from_stats_if_needed(
        objid,
        track: TidalTrack,
        album: TidalAlbum,
        entries: list) -> list:
    has_been_played: bool = persistence.track_has_been_played(track.id)
    msgproc.log(f"Track with id [{track.id}] name [{track.name}] has been tracked: "
                f"[{'yes' if has_been_played else 'no'}]")
    if has_been_played:
        # add entry for removing from stats
        rm_stats: ItemIdentifier = ItemIdentifier(
            ElementType.REMOVE_TRACK_FROM_STATS.getName(),
            track.id)
        rm_stats_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(rm_stats))
        rm_entry: dict[str, any] = upmplgutils.direntry(rm_stats_id, objid, "Remove from Statistics")
        entries.append(rm_entry)
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album) if album else None, rm_entry)
    return entries


def handler_element_track_container(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    track_id: int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_element_track_container track_id [{track_id}]")
    tidal_session: TidalSession = get_session()
    track: TidalTrack
    track, _ = tidal_util.try_get_track(tidal_session, track_id)
    if track:
        context: Context = Context()
        context.add(key=ContextKey.IS_TRACK, value=True)
        tidal_track_adapter: TrackAdapter = choose_track_adapter_by_tidal_track(
            tidal_session=tidal_session,
            track=track)
        track_entry = track_to_entry(
            objid=objid,
            track_adapter=tidal_track_adapter,
            tidal_session=tidal_session,
            context=context)
        entries.append(track_entry)
    else:
        # track is most likely missing
        msgproc.log(f"Track [{track_id}] could not be found")
        # present MISSING_TRACK
        entries.append(create_missing_track_entry(
            objid=objid,
            tidal_session=tidal_session,
            track_id=track_id))
    return entries


def handler_element_category(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tidal_session: TidalSession = get_session()
    select_category: str = item_identifier.get(ItemIdentifierKey.CATEGORY_KEY)
    category: TidalItemList = get_category(
        tidal_session=tidal_session,
        category_name=select_category)
    if not category:
        msgproc.log("handler_element_category category not set")
        return entries
    obj = get_category(
        tidal_session=tidal_session,
        category_name=select_category)
    if not obj:
        msgproc.log(f"handler_element_category cannot load category [{select_category}]")
        return entries
    if isinstance(obj, TidalFeaturedItems):
        # msgproc.log(f"handler_element_category category [{select_category}] as TidalFeaturedItems")
        featured_items: TidalFeaturedItems = obj
        for fi_item in featured_items.items:
            if fi_item.type == constants.featured_type_name_playlist:
                playlist: TidalPlaylist = tidal_session.playlist(fi_item.artifact_id)
                entries.append(playlist_to_playlist_container(
                    objid=objid,
                    playlist=playlist))
            else:
                msgproc.log(f"handler_element_category not processed Item type {fi_item.type}")
    else:
        index: int = 0
        for item in category.items:
            item_type: str = type(item).__name__
            item_name: str = tidal_util.get_name_or_title(item)
            # msgproc.log(f"handler_element_category categories[{select_category}].item[{index}] type is [{item_type}]")
            if isinstance(item, TidalPageLink):
                page_link: TidalPageLink = item
                page_link_entry: dict = pagelink_to_entry(objid, category=category, page_link=item)
                entries.append(page_link_entry)
                # TODO maybe extract method for getting image for a PageLink
                tile_image: TileImage = load_tile_image_unexpired(TileType.PAGE_LINK, page_link.api_path)
                page_link_image_url: str = tile_image.tile_image if tile_image else None
                if not page_link_image_url:
                    items_in_page: list = get_items_in_page_link(
                        page_link=page_link,
                        limit=config.get_page_items_for_tile_image())
                    for current in items_in_page if items_in_page else list():
                        if (tidal_util.is_instance_of_any(
                            current,
                            [TidalPlaylist,
                                TidalMix,
                                TidalAlbum,
                                TidalArtist,
                                TidalTrack])):
                            # get an image from that
                            page_link_image_url = tidal_util.get_image_url(current)
                            persistence.save_tile_image(TileType.PAGE_LINK, page_link.api_path, page_link_image_url)
                            # we only need the first
                            break
                        else:
                            msgproc.log(f"handler_element_category [{category.title}] [{index}] "
                                        f"[{item_type}] [{item_name}] [{page_link.api_path}] "
                                        f"num_items [{len(items_in_page)}] "
                                        f"current [{type(current).__name__ if current else None}]")
                upnp_util.set_album_art_from_uri(page_link_image_url, page_link_entry)
            elif isinstance(item, TidalMix):
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                entries.append(mix_to_mix_container(objid, mix=item))
            elif isinstance(item, TidalTrack):
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                options: dict[str, any] = dict()
                set_option(options, OptionKey.SKIP_TRACK_NUMBER, True)
                entries.append(track_to_navigable_track(
                    objid=objid,
                    tidal_session=tidal_session,
                    track_adapter=instance_tidal_track_adapter(
                        tidal_session=tidal_session,
                        track=item),
                    track=item,
                    options=options))
            elif isinstance(item, TidalPlaylist):
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                entries.append(playlist_to_playlist_container(
                    objid=objid,
                    playlist=item))
            elif isinstance(item, TidalAlbum):
                album: TidalAlbum = item
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                options: dict[str, any] = dict()
                entries.append(album_to_album_container(
                    objid=objid,
                    tidal_session=tidal_session,
                    album=album))
            elif isinstance(item, TidalArtist):
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                entries.append(artist_to_entry(objid, artist=item))
            else:
                msgproc.log(f"handler_element_category [{category.title}] [{index}] [{item_type}] "
                            f"[{item_name}] was not handled!")
            index += 1
    return entries


# this allows kodi to work with the plugin
def track_data_to_entry(
        objid,
        tidal_session: TidalSession,
        entry_id: str,
        track: TidalTrack) -> dict:
    entry: dict = {}
    entry['id'] = entry_id
    entry['pid'] = track.id
    upnp_util.set_class_music_track(entry)
    upnp_util.set_uri(build_intermediate_url(track.id), entry)
    track_adapter: TrackAdapter = choose_track_adapter_by_tidal_track(
        tidal_session=tidal_session,
        track=track)
    if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_READ_STREAM_METADATA):
        bit_depth: int = track_adapter.get_bit_depth()
        sample_rate: int = track_adapter.get_sample_rate()
        upnp_util.set_bit_depth(bit_depth, entry)
        upnp_util.set_sample_rate(sample_rate, entry)
        upnp_util.set_bit_rate(
            bitrate=calc_bitrate(
                tidal_quality=track.audio_quality,
                bit_depth=bit_depth,
                sample_rate=sample_rate),
            target=entry)
    # channels. I could use AudioMode but I can't exactly say how many channels are delivered
    # so I am assuming two, looks like a decent fallback for now
    upnp_util.set_channels(2, entry)
    title: str = track.name
    upnp_util.set_track_title(title, entry)
    upnp_util.set_album_title(track.album.name, entry)
    upnp_util.set_object_type_item(entry)
    upnp_util.set_disc_number(track.volume_num, entry)
    upnp_util.set_track_number(track.track_num, entry)
    upnp_util.set_artist(track.artist.name, entry)
    upnp_util.set_mime_type(tidal_util.get_mime_type(track.audio_quality), entry)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(track.album), entry)
    upnp_util.set_duration(track.duration, entry)
    return entry


def handler_element_track_simple(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    track_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    track: TidalTrack = tidal_session.track(track_id)
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), track_id)
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    track_entry: dict = track_data_to_entry(
        objid=objid,
        tidal_session=tidal_session,
        entry_id=id,
        track=track)
    entries.append(track_entry)
    return entries


def handler_element_recently_played_tracks_navigable(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    options: dict[str, any] = dict()
    set_option(options=options, option_key=OptionKey.TRACK_AS_NAVIGABLE, option_value=True)
    return played_track_list_to_entries(
        objid=objid,
        tidal_session=get_session(),
        item_identifier=item_identifier,
        played_tracks=persistence.get_last_played_tracks(),
        entries=entries,
        options=options)


def handler_element_most_played_tracks_navigable(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    options: dict[str, any] = dict()
    set_option(options=options, option_key=OptionKey.TRACK_AS_NAVIGABLE, option_value=True)
    return played_track_list_to_entries(
        objid=objid,
        tidal_session=get_session(),
        item_identifier=item_identifier,
        played_tracks=persistence.get_most_played_tracks(),
        entries=entries,
        options=options)


def is_played_track_complete(played_track: PlayedTrack) -> bool:
    return (
        played_track.track_id is not None and
        played_track.album_id is not None and
        played_track.album_track_count is not None and
        played_track.track_name is not None and
        played_track.track_duration is not None and
        played_track.track_num is not None and
        played_track.volume_num is not None and
        played_track.album_num_volumes is not None and
        played_track.album_name is not None and
        played_track.audio_quality is not None and
        played_track.album_artist_name is not None and
        played_track.image_url is not None and
        played_track.explicit is not None and
        played_track.artist_name is not None and
        played_track.bit_depth is not None and
        played_track.sample_rate is not None)


def played_track_list_to_entries_raw(
        objid: any,
        tidal_session: TidalSession,
        played_tracks: list[PlayedTrack],
        options: dict[str, any],
        entries: list) -> list:
    initial_track_num: int = get_option(options=options, option_key=OptionKey.INITIAL_TRACK_NUMBER)
    current: PlayedTrack
    set_option(
        options=options,
        option_key=OptionKey.SKIP_TRACK_NUMBER,
        option_value=True)
    track_num: int = initial_track_num
    # limit maximum number of reload from tidal when some data is missing
    max_reload_count: int = 10
    reload_count: int = 0
    for current in played_tracks if played_tracks else list():
        track_adapter: TrackAdapter = (
            choose_track_adapter(
                tidal_session=tidal_session,
                played_track=current)
            if reload_count < max_reload_count
            else PlayedTrackAdapter(current))
        if isinstance(track_adapter, TidalTrackAdapter):
            # a reload has happened
            reload_count += 1
        out_options: dict[str, any] = dict()
        set_option(
            options=out_options,
            option_key=OptionKey.FORCED_TRACK_NUMBER,
            option_value=track_num)
        navigable: bool = get_option(
            options=options,
            option_key=OptionKey.TRACK_AS_NAVIGABLE)
        if navigable:
            track_entry: dict = track_to_navigable_track(
                objid=objid,
                track_adapter=track_adapter,
                tidal_session=tidal_session,
                options=out_options)
            entries.append(track_entry)
        else:
            track_entry: dict = track_to_track_container(
                objid=objid,
                tidal_session=tidal_session,
                track_adapter=track_adapter,
                options=out_options)
            entries.append(track_entry)
        track_num += 1
    return entries


def played_track_list_to_entries(
        objid,
        tidal_session: TidalSession,
        item_identifier: ItemIdentifier,
        played_tracks: list[PlayedTrack],
        entries: list,
        options: dict[str, any] = dict()) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    # apply offset
    played_tracks = played_tracks[offset:] if len(played_tracks) > offset else ()
    # needs next?
    next_needed: bool = len(played_tracks) > config.tracks_per_page
    next_track: PlayedTrack = played_tracks[config.tracks_per_page] if next_needed else None
    played_tracks = (played_tracks[0:config.tracks_per_page]
                     if len(played_tracks) > config.tracks_per_page
                     else played_tracks)
    out_options: dict[str, any] = dict()
    copy_option(in_options=options, out_options=out_options, option_key=OptionKey.TRACK_AS_NAVIGABLE)
    set_option(
        options=out_options,
        option_key=OptionKey.INITIAL_TRACK_NUMBER,
        option_value=offset + 1)
    entries = played_track_list_to_entries_raw(
        objid=objid,
        tidal_session=tidal_session,
        played_tracks=played_tracks,
        options=out_options,
        entries=entries)
    if next_needed:
        element_type: ElementType = get_element_type_by_name(item_identifier.get(ItemIdentifierKey.THING_NAME))
        next_entry: dict[str, any] = create_next_button(
            objid=objid,
            element_type=element_type,
            element_id=element_type.getName(),
            next_offset=offset + config.tracks_per_page)
        # cover art for next track button
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_track.album_id,
                tidal_session=tidal_session),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_recently_played_tracks_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return played_track_list_to_entries(
        objid=objid,
        tidal_session=get_session(),
        item_identifier=item_identifier,
        played_tracks=persistence.get_last_played_tracks(),
        entries=entries)


def handler_element_most_played_tracks_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return played_track_list_to_entries(
        objid=objid,
        tidal_session=get_session(),
        item_identifier=item_identifier,
        played_tracks=persistence.get_most_played_tracks(),
        entries=entries)


def get_unique_album_id_list(track_list: list[PlayedTrack]) -> list[str]:
    album_id_list: list[str] = list()
    album_id_set: set[str] = set()
    current: PlayedTrack
    for current in track_list if track_list else []:
        current_album_id: str = current.album_id
        if current_album_id not in album_id_set:
            album_id_list.append(current_album_id)
            album_id_set.add(current_album_id)
    return album_id_list


def get_last_played_album_id_list(max_tracks: int) -> list[str]:
    track_list: list[PlayedTrack] = persistence.get_last_played_tracks(max_tracks=max_tracks)
    return get_unique_album_id_list(track_list)


def handler_element_remove_track_from_stats(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    track_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    if not track_id:
        return entries
    msgproc.log(f"Removing {track_id} from playback statistics ...")
    persistence.remove_track_from_played_tracks(track_id)
    msgproc.log(f"Removed {track_id} from playback statistics.")
    tidal_session: TidalSession = get_session()
    track: TidalTrack = tidal_session.track(track_id)
    entries.append(track_to_navigable_track(
        objid=objid,
        tidal_session=tidal_session,
        track_adapter=instance_tidal_track_adapter(
            tidal_session=tidal_session,
            track=track),
        track=track))
    return entries


def handler_element_remove_album_from_stats(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    if not album_id:
        return entries
    msgproc.log(f"Removing {album_id} from playback statistics ...")
    persistence.remove_album_from_played_tracks(album_id)
    msgproc.log(f"Removed {album_id} from playback statistics.")
    album: TidalAlbum = tidal_session.album(album_id)
    entries.append(album_to_album_container(
        objid=objid,
        tidal_session=tidal_session,
        album=album))
    return entries


def handler_element_recently_played_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    # TODO remove hardcoded value
    max_tracks: int = 10000
    albums_per_page: int = config.albums_per_page
    next_needed: bool = False
    album_id_list: list[str] = get_last_played_album_id_list(max_tracks=max_tracks)
    from_offset_album_id_list: list[str] = album_id_list[offset:]
    if len(from_offset_album_id_list) >= albums_per_page:
        next_needed = True
    page_album_id_list: list[str] = from_offset_album_id_list[0:albums_per_page]
    current_album_id: str
    for current_album_id in page_album_id_list:
        try:
            album_adapter: AlbumAdapter = album_adapter_by_album_id(
                album_id=current_album_id,
                tidal_album_loader=get_tidal_album_loader(tidal_session))
            if album_adapter:
                entries.append(album_adapter_to_album_container(
                    objid=objid,
                    tidal_session=tidal_session,
                    album_adapter=album_adapter))
        except Exception as ex:
            msgproc.log(f"Cannot add album with id [{current_album_id}] due to [{type(ex)}] [{ex}]")
    if next_needed:
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.RECENTLY_PLAYED_ALBUMS,
            element_id=ElementType.RECENTLY_PLAYED_ALBUMS.getName(),
            next_offset=offset + albums_per_page)
        # get the cover for the Next button
        cover_album_id: str = from_offset_album_id_list[albums_per_page]
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=cover_album_id,
                tidal_session=tidal_session),
            target=next_button)
        entries.append(next_button)
    return entries


def handler_element_most_played_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session: TidalSession = get_session()
    albums_per_page: int = config.albums_per_page
    # TODO remove hardcoded value
    max_albums: int = 1000
    next_needed: bool = True
    items: list[PlayedAlbum] = persistence.get_most_played_albums(max_albums=max_albums)
    from_offset_album_list: list[PlayedAlbum] = items[offset:]
    if len(from_offset_album_list) < albums_per_page:
        next_needed = False
    page_played_album_list: list[PlayedAlbum] = from_offset_album_list[0:albums_per_page]
    current: PlayedAlbum
    for current in page_played_album_list:
        try:
            album_adapter: AlbumAdapter = album_adapter_by_album_id(
                album_id=current.album_id,
                tidal_album_loader=get_tidal_album_loader(tidal_session))
            if album_adapter:
                entries.append(album_adapter_to_album_container(
                    objid=objid,
                    tidal_session=tidal_session,
                    album_adapter=album_adapter))
        except Exception as ex:
            msgproc.log(f"Cannot add album with id [{current.album_id}] due to [{type(ex)}] [{ex}]")
    if next_needed:
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.MOST_PLAYED_ALBUMS,
            element_id=ElementType.MOST_PLAYED_ALBUMS.getName(),
            next_offset=offset + albums_per_page)
        # get the cover for the Next button
        next_album: PlayedAlbum = from_offset_album_list[albums_per_page]
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_album.album_id,
                tidal_session=tidal_session),
            target=next_button)
        entries.append(next_button)
    return entries


def handler_album_tracks_action(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session: TidalSession = get_session()
    album: TidalAlbum = tidal_util.try_get_album(tidal_session=tidal_session, album_id=album_id)
    if not album:
        return entries
    options: dict[str, any] = dict()
    set_option(
        options=options,
        option_key=OptionKey.TRACK_OMITTABLE_ARTIST_NAME,
        option_value=album.artist.name)
    track: TidalTrack
    for track in album.tracks():
        try:
            track_entry: dict[str, any] = track_to_navigable_track(
                objid=objid,
                tidal_session=tidal_session,
                track_adapter=instance_tidal_track_adapter(
                    tidal_session=tidal_session,
                    track=track),
                track=track,
                options=options)
            if track_entry:
                entries.append(track_entry)
        except Exception as ex:
            msgproc.log(f"handler_album_tracks_action cannot load "
                        f"track_id [{track.id}] from album_id [{album_id}] "
                        f"[{type(ex)}] [{ex}]")
    return entries


def handler_element_bookmark_artists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    obj_list: list[str] = persistence.get_artist_listen_queue()
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    counter: int = offset
    # start from the offset (slice obj_list)
    obj_list = obj_list[offset:] if len(obj_list) > offset else list()
    tidal_session: TidalSession = get_session()
    counter: int = 0
    success_count: int = 0
    obj_id: str
    for obj_id in obj_list:
        counter += 1
        try:
            tidal_obj: TidalArtist = tidal_util.try_get_artist(
                tidal_session=tidal_session,
                artist_id=obj_id)
            success_count += 1
            entries.append(artist_to_entry(objid, tidal_obj))
            if success_count == config.artists_per_page:
                break
        except Exception as ex:
            msgproc.log(f"handler_element_bookmark_artists cannot load [{type(tidal_obj)}] "
                        f"[{obj_id}] [{type(ex)}] [{ex}]")
    if len(obj_list) > counter:
        next_artist_id: str = obj_list[counter]
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.BOOKMARK_ARTISTS,
            element_id=ElementType.BOOKMARK_ARTISTS.getName(),
            next_offset=offset + counter)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_image_url(
                obj=tidal_util.try_get_artist(
                    tidal_session=tidal_session,
                    artist_id=next_artist_id)),
            target=next_button)
        entries.append(next_button)
    return entries


def handler_element_bookmark_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    obj_list: list[str] = persistence.get_album_listen_queue()
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    counter: int = offset
    # start from the offset (slice obj_list)
    obj_list = obj_list[offset:] if len(obj_list) > offset else list()
    tidal_session: TidalSession = get_session()
    counter: int = 0
    success_count: int = 0
    obj_id: str
    for obj_id in obj_list:
        counter += 1
        try:
            tidal_obj: TidalAlbum = tidal_util.try_get_album(
                tidal_session=tidal_session,
                album_id=obj_id)
            if tidal_obj:
                success_count += 1
                entries.append(album_to_album_container(
                    objid=objid,
                    tidal_session=tidal_session,
                    album=tidal_obj))
            if success_count == config.albums_per_page:
                break
        except Exception as ex:
            msgproc.log(f"handler_element_bookmark_albums cannot load [{type(tidal_obj)}] "
                        f"[{obj_id}] [{type(ex)}] [{ex}]")
    if len(obj_list) > counter:
        next_album_id: str = obj_list[counter]
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.BOOKMARK_ALBUMS,
            element_id=ElementType.BOOKMARK_ALBUMS.getName(),
            next_offset=offset + counter)
        upnp_util.set_album_art_from_uri(
            album_art_uri=tidal_util.get_album_art_url_by_album_id(
                album_id=next_album_id,
                tidal_session=tidal_session),
            target=next_button)
        entries.append(next_button)
    return entries


def handler_element_bookmark_tracks(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    obj_list: list[str] = persistence.get_track_listen_queue()
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    counter: int = offset
    # start from the offset (slice obj_list)
    obj_list = obj_list[offset:] if len(obj_list) > offset else list()
    # msgproc.log(f"handler_element_bookmark_tracks offset [{offset}] len [{len(obj_list)}]")
    tidal_session: TidalSession = get_session()
    counter: int = 0
    success_count: int = 0
    obj_id: str
    for obj_id in obj_list:
        counter += 1
        try:
            tidal_obj: TidalTrack
            tidal_obj, _ = tidal_util.try_get_track(
                tidal_session=tidal_session,
                track_id=obj_id)
            success_count += 1
            entries.append(track_to_navigable_track(
                objid=objid,
                tidal_session=tidal_session,
                track_adapter=instance_tidal_track_adapter(
                    tidal_session=tidal_session,
                    track=tidal_obj),
                track=tidal_obj))
            if success_count == config.tracks_per_page:
                break
        except Exception as ex:
            msgproc.log(f"handler_element_bookmark_tracks cannot load [{type(tidal_obj)}] "
                        f"[{obj_id}] [{type(ex)}] [{ex}]")
    if len(obj_list) > counter:
        next_track_id: str = obj_list[counter]
        next_button: dict[str, any] = create_next_button(
            objid=objid,
            element_type=ElementType.BOOKMARK_TRACKS,
            element_id=ElementType.BOOKMARK_TRACKS.getName(),
            next_offset=offset + counter)
        next_track: TidalTrack
        next_track, _ = tidal_util.try_get_track(
            tidal_session=tidal_session,
            track_id=next_track_id)
        if next_track:
            upnp_util.set_album_art_from_uri(
                album_art_uri=tidal_util.get_album_art_url_by_album_id(
                    album_id=next_track.album.id,
                    tidal_session=tidal_session),
                target=next_button)
        entries.append(next_button)
    return entries


def handler_element_track_bookmark_action(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    track_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    listen_queue_action: str = item_identifier.get(ItemIdentifierKey.LISTEN_QUEUE_ACTION)
    msgproc.log(f"handler_element_track_bookmark_action on [{track_id} -> [{listen_queue_action}]")
    # perform requested action
    if constants.ListeningQueueAction.ADD.value == listen_queue_action:
        persistence.add_to_track_listen_queue(track_id)
    if constants.ListeningQueueAction.DEL.value == listen_queue_action:
        persistence.remove_from_track_listen_queue(track_id)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.NAVIGABLE_TRACK.getName(),
        track_id)
    return handler_element_navigable_track(objid, item_identifier=identifier, entries=entries)


def handler_element_album_bookmark_action(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    listen_queue_action: str = item_identifier.get(ItemIdentifierKey.LISTEN_QUEUE_ACTION)
    msgproc.log(f"handler_element_album_bookmark_action on [{album_id} -> [{listen_queue_action}]")
    # perform requested action
    if constants.ListeningQueueAction.ADD.value == listen_queue_action:
        persistence.add_to_album_listen_queue(album_id)
    if constants.ListeningQueueAction.DEL.value == listen_queue_action:
        persistence.remove_from_album_listen_queue(album_id)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_CONTAINER.getName(),
        album_id)
    return handler_element_album_container(objid, item_identifier=identifier, entries=entries)


def handler_element_artist_bookmark_action(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    listen_queue_action: str = item_identifier.get(ItemIdentifierKey.LISTEN_QUEUE_ACTION)
    msgproc.log(f"handler_element_artist_bookmark_action on [{artist_id} -> [{listen_queue_action}]")
    # perform requested action
    if constants.ListeningQueueAction.ADD.value == listen_queue_action:
        persistence.add_to_artist_listen_queue(artist_id)
    if constants.ListeningQueueAction.DEL.value == listen_queue_action:
        persistence.remove_from_artist_listen_queue(artist_id)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(),
        artist_id)
    return handler_element_artist(objid, item_identifier=identifier, entries=entries)


def handler_track_favorite_action(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    track_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    action: str = item_identifier.get(ItemIdentifierKey.FAVORITE_ACTION)
    if constants.fav_action_add == action:
        msgproc.log(f"handler_track_favorite_action adding track [{track_id}] to favorites ...")
        get_session().user.favorites.add_track(track_id)
    elif constants.fav_action_del == action:
        msgproc.log(f"handler_track_favorite_action removing track [{track_id}] from favorites ...")
        get_session().user.favorites.remove_track(track_id)
    else:
        msgproc.log(f"handler_track_favorite_action invalid action [{action}]")
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.NAVIGABLE_TRACK.getName(),
        track_id)
    return handler_element_navigable_track(objid, item_identifier=identifier, entries=entries)


def choose_track_adapter(tidal_session: TidalSession, played_track: PlayedTrack) -> TrackAdapter:
    played_track_complete: bool = played_track and is_played_track_complete(played_track)
    return (PlayedTrackAdapter(played_track)
            if played_track_complete
            else __load_tidal_track_adapter_by_track_id(
                tidal_session=tidal_session,
                track_id=played_track.track_id))


def choose_track_adapter_by_tidal_track(
        tidal_session: TidalSession,
        track: TidalTrack) -> TrackAdapter:
    return (__choose_track_adapter_by_track_id(
        tidal_session=tidal_session,
        track_id=track.id) if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_READ_STREAM_METADATA)
        else __load_tidal_track_adapter_by_track(
            tidal_session=tidal_session,
            track=track))


def __load_tidal_track_adapter_by_track(
        tidal_session: TidalSession,
        track: TidalTrack) -> TidalTrackAdapter:
    # msgproc.log(f"Loading track details from Tidal for track_id: [{track_id}]")
    adapter: TidalTrackAdapter = TidalTrackAdapter(
        tidal_session=tidal_session,
        track=track,
        album_retriever=album_retriever)
    return adapter


def __load_tidal_track_adapter_by_track_id(
        tidal_session: TidalSession,
        track_id: str) -> TidalTrackAdapter:
    # msgproc.log(f"Loading track details from Tidal for track_id: [{track_id}]")
    adapter: TidalTrackAdapter = TidalTrackAdapter(
        tidal_session=tidal_session,
        track=tidal_session.track(track_id),
        album_retriever=album_retriever)
    # maybe update on db?
    if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_READ_STREAM_METADATA):
        current: PlayedTrack = persistence.get_played_track_entry(track_id=track_id)
        request: PlayedTrackRequest = PlayedTrackRequest()
        request.track_id = track_id
        request.album_track_count = adapter.get_album_track_count()
        request.album_num_volumes = adapter.get_album_num_volumes() if adapter.get_album_num_volumes() else 1
        request.album_id = adapter.get_album_id()
        request.album_artist_name = adapter.get_album_artist_name()
        request.album_name = adapter.get_album_name()
        request.artist_name = adapter.get_artist_name()
        try:
            request.audio_quality = adapter.get_audio_quality()
        except Exception as ex:
            msgproc.log(f"Cannot get audio_quality for track [{track_id}] due to [{type(ex)}] [{ex}]")
        request.explicit = adapter.explicit()
        request.track_duration = adapter.get_duration()
        request.track_name = adapter.get_name()
        request.track_num = adapter.get_track_num()
        request.volume_num = adapter.get_volume_num()
        request.image_url = adapter.get_image_url()
        request.explicit = 1 if adapter.explicit() else 0
        try:
            request.bit_depth = adapter.get_bit_depth()
        except Exception:
            msgproc.log(f"Cannot get bit_depth for track [{track_id}]")
        try:
            request.sample_rate = adapter.get_sample_rate()
        except Exception:
            msgproc.log(f"Cannot get sample_rate for track [{track_id}]")
        if current:
            # msgproc.log(f"Updating played_track for track_id [{track_id}] ...")
            # update using adapter
            persistence.update_playback(
                played_track_request=request,
                last_played=None)
        else:
            # msgproc.log(f"Inserting played_track for track_id [{track_id}] without a play_count ...")
            persistence.insert_playback(
                played_track_request=request,
                last_played=None)
    return adapter


def __choose_track_adapter_by_track_id(
        tidal_session: TidalSession,
        track_id: str) -> TrackAdapter:
    played_track: PlayedTrack = (persistence.get_played_track_entry(track_id=track_id)
                                 if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_READ_STREAM_METADATA)
                                 else None)
    return (choose_track_adapter(
            tidal_session=tidal_session,
            played_track=played_track)
            if played_track
            else __load_tidal_track_adapter_by_track_id(
                tidal_session=tidal_session,
                track_id=track_id))


def image_retriever_categories(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    categories = get_categories(tidal_session=tidal_session)
    first = categories[0] if categories and len(categories) > 0 else None
    return get_category_image_url(
        tidal_session=tidal_session,
        category=first) if first else None


def image_retriever_home_page(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    return __image_retriever_by_page_definition(tidal_session, TidalPageDefinition.HOME)


def image_retriever_explore_new_music(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    return __image_retriever_by_page_definition(tidal_session, TidalPageDefinition.NEW_MUSIC)


def image_retriever_rising(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    return __image_retriever_by_page_definition(tidal_session, TidalPageDefinition.RISING)


def image_retriever_featured(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    return __image_retriever_by_page_definition(tidal_session, TidalPageDefinition.HOME)


def image_retriever_for_you(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    return __image_retriever_by_page_definition(tidal_session, TidalPageDefinition.FOR_YOU)


def image_retriever_explore(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    return __image_retriever_by_page_definition(tidal_session, TidalPageDefinition.EXPLORE)


def __image_retriever_by_page_definition(
        tidal_session: TidalSession,
        tidal_page_definition: TidalPageDefinition) -> str:
    page: TidalPage = get_tidal_page(tidal_session, tidal_page_definition)
    return image_retriever_page(page=page)


def image_retriever_hires_page(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    page: TidalPage = get_tidal_page(tidal_session, TidalPageDefinition.HI_RES)
    return image_retriever_page(page=page)


def image_retriever_genres_page(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    page: TidalPage = get_tidal_page(tidal_session, TidalPageDefinition.GENRES)
    return image_retriever_page(page=page)


def image_retriever_local_genres_page(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    page: TidalPage = get_tidal_page(tidal_session, TidalPageDefinition.LOCAL_GENRES)
    return image_retriever_page(page=page)


def image_retriever_moods_page(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    page: TidalPage = get_tidal_page(tidal_session, TidalPageDefinition.MOODS)
    return image_retriever_page(page=page)


def image_retriever_page(
        page: TidalPage,
        limit: int = config.get_page_items_for_tile_image()) -> str:
    item_list: list = list()
    for current_page_item in page:
        if len(item_list) >= limit:
            break
        if isinstance(current_page_item, TidalPageLink):
            page_link_items: list[any] = get_items_in_page_link(
                page_link=current_page_item,
                limit=config.get_page_items_for_tile_image())
            first_item: any = page_link_items[0] if page_link_items and len(page_link_items) > 0 else None
            if first_item:
                item_list.append(first_item)
        elif isinstance(current_page_item, str):
            if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
                msgproc.log(f"image_retriever_page item of type [{type(current_page_item)}]")
        else:
            item_list.append(current_page_item)
    if len(item_list) == 0:
        msgproc.log(f"image_retriever_page no item for page [{page.title}]")
        return None
    # get random item
    random_item = secrets.choice(item_list)
    # random_item = item_list[0]
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"image_retriever_page selected type is [{type(random_item).__name__}]")
    image_url: str = tidal_util.get_image_url(random_item)
    if not image_url:
        msgproc.log(f"image_retriever_page no image for [{page.title}] "
                    f"from [{type(random_item).__name__}]")
    return image_url


def image_retriever_cached(tidal_session: TidalSession, tag_type: TagType, loader) -> str:
    tile_image: TileImage = load_tile_image_unexpired(
        tile_type=TileType.TAG,
        tile_id=tag_type.getTagName())
    image_url: str = tile_image.tile_image if tile_image else None
    # ignore cached images if caching is disabled
    if image_url:
        base_url: str = tidal_util.get_docroot_base_url()
        if base_url and not config.get_enable_image_caching() and image_url.startswith(base_url):
            msgproc.log(f"Ignoring cached url [{image_url}]")
            image_url = None
    # msgproc.log(f"Image for tag [{tag_type.getTagName()}] "
    #             f"cached [{'yes' if image_url else 'no'}] "
    #             f"url [{image_url}]")
    if not image_url:
        image_url = loader(tidal_session, tag_type)
        if image_url:
            persistence.save_tile_image(TileType.TAG, tag_type.getTagName(), image_url)
    return image_url


def image_retriever_my_playlists(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    playlists: list[TidalUserPlaylist] = tidal_session.user.playlists()
    first: TidalUserPlaylist = playlists[0] if playlists and len(playlists) > 0 else None
    return tidal_util.get_image_url(first) if first else None


def image_retriever_all_playlists(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    playlists: list[TidalPlaylist] = tidal_session.user.playlist_and_favorite_playlists()
    first: TidalPlaylist = playlists[0] if playlists and len(playlists) > 0 else None
    return tidal_util.get_image_url(first) if first else None


def image_retriever_favorite_albums(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    items: list[TidalAlbum] = tidal_session.user.favorites.albums(limit=1, offset=0)
    first: TidalAlbum = items[0] if items and len(items) > 0 else None
    return tidal_util.get_image_url(first) if first else None


def image_retriever_favorite_artists(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    items: list[TidalArtist] = tidal_session.user.favorites.artists(limit=1, offset=0)
    first: TidalArtist = items[0] if items and len(items) > 0 else None
    return tidal_util.get_image_url(first) if first else None


def image_retriever_favorite_tracks(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    items: list[TidalTrack] = tidal_session.user.favorites.tracks(limit=1, offset=0)
    first: TidalTrack = items[0] if items and len(items) > 0 else None
    return (tidal_util.get_album_art_url_by_album_id(
            album_id=first.album.id,
            tidal_session=tidal_session)
            if first and first.album else None)


def image_retriever_playback_statistics(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    items: list[PlayedTrack] = persistence.get_last_played_tracks(max_tracks=10)
    first: PlayedTrack = secrets.choice(items) if items and len(items) > 0 else None
    return (tidal_util.get_album_art_url_by_album_id(
            album_id=first.album_id,
            tidal_session=tidal_session)
            if first else None)


def __get_random_track_id_from_listen_queue() -> str:
    track_id_list: list[str] = persistence.get_track_listen_queue()
    return secrets.choice(track_id_list) if track_id_list and len(track_id_list) > 0 else None


def __get_random_album_id_from_listen_queue() -> str:
    album_id_list: list[str] = persistence.get_album_listen_queue()
    return secrets.choice(album_id_list) if album_id_list and len(album_id_list) > 0 else None


def __get_random_artist_id_from_listen_queue() -> str:
    artist_id_list: list[str] = persistence.get_artist_listen_queue()
    return secrets.choice(artist_id_list) if artist_id_list and len(artist_id_list) > 0 else None


def image_retriever_listen_queue(
        tidal_session: TidalSession,
        tag_type: TagType) -> str:
    select_album_id: str = __get_random_album_id_from_listen_queue()
    return (tidal_util.get_album_art_url_by_album_id(
        album_id=select_album_id,
        tidal_session=tidal_session)
        if select_album_id else None)


def get_tidal_page(tidal_session: TidalSession, tidal_page_def: TidalPageDefinition) -> TidalPage:
    return __get_page(tidal_session, tidal_page_def.page_path)


def __get_page(tidal_session: TidalSession, page_path: str) -> TidalPage:
    return tidal_session.page.get(page_path)


__tag_image_retriever: dict = {
    # image for PAGE_SELECTION is same as featured
    TagType.PAGE_SELECTION.getTagName(): image_retriever_featured,
    TagType.CATEGORIES.getTagName(): image_retriever_categories,
    TagType.EXPLORE_NEW_MUSIC.getTagName(): image_retriever_explore_new_music,
    TagType.EXPLORE_TIDAL_RISING.getTagName(): image_retriever_rising,
    TagType.HOME.getTagName(): image_retriever_featured,
    TagType.EXPLORE.getTagName(): image_retriever_explore,
    TagType.FOR_YOU.getTagName(): image_retriever_for_you,
    TagType.HIRES_PAGE.getTagName(): image_retriever_hires_page,
    TagType.GENRES_PAGE.getTagName(): image_retriever_genres_page,
    TagType.LOCAL_GENRES_PAGE.getTagName(): image_retriever_local_genres_page,
    TagType.MOODS_PAGE.getTagName(): image_retriever_moods_page,
    TagType.MY_PLAYLISTS.getTagName(): image_retriever_my_playlists,
    TagType.ALL_PLAYLISTS.getTagName(): image_retriever_all_playlists,
    TagType.FAVORITE_ALBUMS.getTagName(): image_retriever_favorite_albums,
    TagType.FAVORITE_ARTISTS.getTagName(): image_retriever_favorite_artists,
    TagType.FAVORITE_TRACKS.getTagName(): image_retriever_favorite_tracks,
    TagType.PLAYBACK_STATISTICS.getTagName(): image_retriever_playback_statistics,
    TagType.BOOKMARKS.getTagName(): image_retriever_listen_queue
}


def get_tidal_album_loader(tidal_session: TidalSession) -> Callable[[str], TidalAlbum]:
    return lambda x: tidal_util.try_get_album(
        tidal_session=tidal_session,
        album_id=x)


__tag_action_dict: dict = {
    TagType.PAGE_SELECTION.getTagName(): handler_tag_page_selection,
    TagType.CATEGORIES.getTagName(): handler_tag_categories,
    TagType.EXPLORE_NEW_MUSIC.getTagName(): handler_tag_explore_new_music,
    TagType.EXPLORE_TIDAL_RISING.getTagName(): handler_tag_explore_tidal_rising,
    TagType.HOME.getTagName(): handler_tag_featured,
    TagType.EXPLORE.getTagName(): handler_tag_explore,
    TagType.FOR_YOU.getTagName(): handler_tag_for_you,
    TagType.HIRES_PAGE.getTagName(): handler_tag_hires_page,
    TagType.GENRES_PAGE.getTagName(): handler_tag_genres_page,
    TagType.LOCAL_GENRES_PAGE.getTagName(): handler_tag_local_genres_page,
    TagType.MOODS_PAGE.getTagName(): handler_tag_moods_page,
    TagType.MY_PLAYLISTS.getTagName(): handler_tag_my_playlists,
    TagType.ALL_PLAYLISTS.getTagName(): handler_tag_all_playlists,
    TagType.FAVORITE_ALBUMS.getTagName(): handler_tag_favorite_albums,
    TagType.FAVORITE_ARTISTS.getTagName(): handler_tag_favorite_artists,
    TagType.FAVORITE_TRACKS.getTagName(): handler_tag_favorite_tracks,
    TagType.PLAYBACK_STATISTICS.getTagName(): handler_tag_playback_statistics,
    TagType.BOOKMARKS.getTagName(): handler_tag_bookmarks
}

__elem_action_dict: dict = {
    ElementType.CATEGORY.getName(): handler_element_category,
    ElementType.ALBUM.getName(): handler_element_album,
    ElementType.ALBUM_CONTAINER.getName(): handler_element_album_container,
    ElementType.PLAYLIST.getName(): handler_element_playlist,
    ElementType.PLAYLIST_CONTAINER.getName(): handler_element_playlist_container,
    ElementType.PLAYLIST_NAVIGABLE.getName(): handler_element_playlist_navigable,
    ElementType.PLAYLIST_NAVIGABLE_ITEM.getName(): handler_element_playlist_navigable_item,
    ElementType.MIX.getName(): handler_element_mix,
    ElementType.MIX_CONTAINER.getName(): handler_element_mix_container,
    ElementType.MIX_NAVIGABLE.getName(): handler_element_mix_navigable,
    ElementType.MIX_NAVIGABLE_ITEM.getName(): handler_element_mix_navigable_item,
    ElementType.ALBUMS_IN_MIX_OR_PLAYLIST.getName(): handler_element_albums_in_mix_or_playlist,
    ElementType.ARTISTS_IN_MIX_OR_PLAYLIST.getName(): handler_element_artists_in_mix_or_playlist,
    ElementType.ALL_TRACKS_IN_PLAYLIST_OR_MIX.getName(): handler_all_tracks_in_playlist_or_mix,
    ElementType.PAGELINK.getName(): handler_element_pagelink,
    ElementType.PAGE.getName(): handler_element_page,
    ElementType.ARTIST.getName(): handler_element_artist,
    ElementType.ARTIST_FOCUS.getName(): handler_element_artist_related,
    ElementType.FAV_ARTIST_ADD.getName(): handler_element_artist_add_to_fav,
    ElementType.FAV_ARTIST_DEL.getName(): handler_element_artist_del_from_fav,
    ElementType.FAV_ALBUM_ADD.getName(): handler_element_album_add_to_fav,
    ElementType.FAV_ALBUM_DEL.getName(): handler_element_album_del_from_fav,
    ElementType.ARTIST_ALBUM_ALBUMS.getName(): handler_element_artist_album_albums,
    ElementType.ARTIST_ALBUM_EP_SINGLES.getName(): handler_element_artist_album_ep_singles,
    ElementType.ARTIST_ALBUM_OTHERS.getName(): handler_element_artist_album_others,
    ElementType.ARTIST_TOP_TRACKS_NAVIGABLE.getName(): handler_element_artist_top_tracks_navigable,
    ElementType.ARTIST_TOP_TRACKS_LIST.getName(): handler_element_artist_top_tracks_list,
    ElementType.ARTIST_RADIO_NAVIGABLE.getName(): handler_element_artist_radio_navigable,
    ElementType.ARTIST_RADIO_LIST.getName(): handler_element_artist_radio_list,
    ElementType.NAVIGABLE_TRACK.getName(): handler_element_navigable_track,
    ElementType.TRACK_CONTAINER.getName(): handler_element_track_container,
    ElementType.TRACK.getName(): handler_element_track_simple,
    ElementType.SIMILAR_ARTISTS.getName(): handler_element_similar_artists,
    ElementType.FAVORITE_TRACKS_NAVIGABLE.getName(): handler_element_favorite_tracks_navigable,
    ElementType.FAVORITE_TRACKS_LIST.getName(): handler_element_favorite_tracks_list,
    ElementType.RECENTLY_PLAYED_TRACKS_NAVIGABLE.getName(): handler_element_recently_played_tracks_navigable,
    ElementType.RECENTLY_PLAYED_TRACKS_LIST.getName(): handler_element_recently_played_tracks_list,
    ElementType.MOST_PLAYED_TRACKS_NAVIGABLE.getName(): handler_element_most_played_tracks_navigable,
    ElementType.MOST_PLAYED_TRACKS_LIST.getName(): handler_element_most_played_tracks_list,
    ElementType.RECENTLY_PLAYED_ALBUMS.getName(): handler_element_recently_played_albums,
    ElementType.MOST_PLAYED_ALBUMS.getName(): handler_element_most_played_albums,
    ElementType.REMOVE_ALBUM_FROM_STATS.getName(): handler_element_remove_album_from_stats,
    ElementType.REMOVE_TRACK_FROM_STATS.getName(): handler_element_remove_track_from_stats,
    ElementType.FAVORITE_ALBUMS_BY_ARTIST_ASC.getName(): handler_element_favorite_albums_by_artist_asc,
    ElementType.FAVORITE_ALBUMS_BY_ARTIST_DESC.getName(): handler_element_favorite_albums_by_artist_desc,
    ElementType.FAVORITE_ALBUMS_BY_TITLE_ASC.getName(): handler_element_favorite_albums_by_title_asc,
    ElementType.FAVORITE_ALBUMS_BY_TITLE_DESC.getName(): handler_element_favorite_albums_by_title_desc,
    ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_ASC.getName(): handler_element_favorite_albums_by_release_date_asc,
    ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_DESC.getName(): handler_element_favorite_albums_by_release_date_desc,
    ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_ASC.getName(): handler_element_favorite_albums_by_user_added_asc,
    ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_DESC.getName(): handler_element_favorite_albums_by_user_added_desc,
    ElementType.FAVORITE_ARTISTS_BY_NAME_ASC.getName(): handler_favorite_artists_by_name_asc,
    ElementType.FAVORITE_ARTISTS_BY_NAME_DESC.getName(): handler_favorite_artists_by_name_desc,
    ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_ASC.getName(): handler_favorite_artists_by_user_date_added_asc,
    ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_DESC.getName(): handler_favorite_artists_by_user_date_added_desc,
    ElementType.BOOKMARK_ALBUMS.getName(): handler_element_bookmark_albums,
    ElementType.BOOKMARK_ARTISTS.getName(): handler_element_bookmark_artists,
    ElementType.BOOKMARK_TRACKS.getName(): handler_element_bookmark_tracks,
    ElementType.BOOKMARK_ALBUM_ACTION.getName(): handler_element_album_bookmark_action,
    ElementType.BOOKMARK_ARTIST_ACTION.getName(): handler_element_artist_bookmark_action,
    ElementType.BOOKMARK_TRACK_ACTION.getName(): handler_element_track_bookmark_action,
    ElementType.ALBUM_TRACKS.getName(): handler_album_tracks_action,
    ElementType.TRACK_FAVORITE_ACTION.getName(): handler_track_favorite_action
}


def tag_list_to_entries(objid, tag_list: list[TagType]) -> list[dict[str, any]]:
    entry_list: list[dict[str, any]] = list()
    tag: TagType
    for tag in tag_list:
        entry: dict[str, any] = tag_to_entry(objid, tag)
        entry_list.append(entry)
    return entry_list


def tag_to_entry(objid, tag: TagType) -> dict[str, any]:
    tagname: str = tag.getTagName()
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TAG.getName(), tagname)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry: dict = upmplgutils.direntry(
        id=id,
        pid=objid,
        title=get_tidal_tag_type_by_name(tag.getTagName()).getTagTitle())
    return entry


def get_page_selection() -> list[TagType]:
    return [
        TagType.CATEGORIES,
        TagType.FOR_YOU,
        TagType.EXPLORE_NEW_MUSIC,
        TagType.EXPLORE_TIDAL_RISING,
        TagType.GENRES_PAGE,
        TagType.LOCAL_GENRES_PAGE,
        TagType.MOODS_PAGE,
        TagType.HOME,
        TagType.HIRES_PAGE,
        TagType.EXPLORE]


def get_tag_hidden_from_front_page() -> list[TagType]:
    return get_page_selection()


def show_tags(objid, entries: list, tidal_session: TidalSession) -> list:
    for tag in TagType:
        if tag not in get_tag_hidden_from_front_page():
            show_single_tag(objid, tidal_session, tag, entries)
        else:
            msgproc.log(f"{TagType.__name__} [{tag.getTagName()}] is hidden from the front page")
    return entries


def is_tag_enabled(tag: TagType) -> bool:
    if TagType.BOOKMARKS == tag:
        return config.get_allow_bookmark_actions()
    else:
        return True


def show_single_tag(objid, tidal_session: TidalSession, tag: TagType, entries: list) -> list:
    if not is_tag_enabled(tag):
        # tag is disabled, we do nothing
        return entries
    tag_display_name: str = get_tidal_tag_type_by_name(tag.getTagName())
    get_image_start: float = time.time()
    curr_tag_img_retriever = (__tag_image_retriever[tag.getTagName()]
                              if tag.getTagName() in __tag_image_retriever
                              else None)
    get_image_elapsed: float = time.time() - get_image_start
    msgproc.log(f"show_single_tag [{tag.getTagName()}] get_image elapsed [{get_image_elapsed:.3f}] sec")
    if not curr_tag_img_retriever:
        msgproc.log(f"show_single_tag cannot find handler for tag [{tag_display_name}]")
    curr_tag_img: str = (image_retriever_cached(
        tidal_session=tidal_session,
        tag_type=tag,
        loader=curr_tag_img_retriever) if curr_tag_img_retriever else None)
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"show_single_tag image for [{tag_display_name}] is [{curr_tag_img}]")
    tag_entry: dict[str, any] = tag_to_entry(objid, tag)
    if curr_tag_img and len(curr_tag_img) > 0:
        upnp_util.set_album_art_from_uri(curr_tag_img, tag_entry)
    entries.append(tag_entry)


cachable_tag_list: list[TagType] = [
]

non_cachable_element_type_list: list[ElementType] = [
]


def skip_cache(item_identifier: ItemIdentifier) -> bool:
    element_name: str = item_identifier.get(ItemIdentifierKey.THING_NAME)
    element_type: ElementType = get_element_type_by_name(element_name)
    if not element_type:
        raise Exception(f"Invalid [{element_name}]")
    return element_type in non_cachable_element_type_list


@dispatcher.record('browse')
def browse(a):
    start: float = time.time()
    msgproc.log(f"browse: args: --{a}--")
    _inittidal()
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    path = html.unescape(_objidtopath(objid))
    msgproc.log(f"browse: path: --{path}--")
    path_list: list[str] = objid.split("/")
    curr_path: str
    for curr_path in path_list:
        if not _g_myprefix == curr_path:
            msgproc.log(f"browse: current_path [{curr_path}] decodes to [{codec.decode(curr_path)}]")
    last_path_item: str = path_list[len(path_list) - 1] if path_list and len(path_list) > 0 else None
    msgproc.log(f"browse: path_list: --{path_list}-- last: --{last_path_item}--")
    entries = []
    if len(path_list) == 1 and _g_myprefix == last_path_item:
        # show tags
        entries = show_tags(objid=objid, entries=entries, tidal_session=get_session())
        msgproc.log(f"browse executed (show_tags) in [{(time.time() - start):.3f}]")
        return _returnentries(entries, no_cache=True)
    else:
        # decode
        decoded_path: str = codec.decode(last_path_item)
        item_dict: dict[str, any] = json.loads(decoded_path)
        item_identifier: ItemIdentifier = ItemIdentifier.from_dict(item_dict)
        thing_name: str = item_identifier.get(ItemIdentifierKey.THING_NAME)
        thing_value: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
        rnd_value: str = item_identifier.get(ItemIdentifierKey.RANDOM_VALUE)
        msgproc.log(f"browse: item_identifier "
                    f"name: --{thing_name}-- "
                    f"value: --{thing_value}-- "
                    f"rnd_value: --{rnd_value}--")
        if ElementType.TAG.getName() == thing_name:
            tag_handler = __tag_action_dict[thing_value] if thing_value in __tag_action_dict else None
            msgproc.log(f"browse: should serve tag [{thing_value}], handler found: [{'yes' if tag_handler else 'no'}]")
            if tag_handler:
                entries = tag_handler(objid, item_identifier, entries)
                # no_cache?
                tag_no_cache: bool = True
                tag: TagType = get_tidal_tag_type_by_name(thing_value)
                if tag and tag in cachable_tag_list:
                    tag_no_cache = False
                # msgproc.log(f"Tag [{thing_value}] no_cache: [{tag_no_cache}]")
                msgproc.log(f"browse executed for [{thing_name}] in [{(time.time() - start):.3f}]")
                return _returnentries(entries, no_cache=tag_no_cache)
            else:
                msgproc.log(f"no tag handler for [{thing_value}], elapsed [{(time.time() - start):.3f}]")
                return _returnentries(entries)
        else:  # it's an element
            elem_handler = __elem_action_dict[thing_name] if thing_name in __elem_action_dict else None
            display_thing_name: str = get_element_type_by_name(thing_name) if elem_handler else thing_name
            msgproc.log(f"browse: should serve element [{display_thing_name}], handler found: "
                        f"[{'yes' if elem_handler else 'no'}]")
            if elem_handler:
                entries = elem_handler(objid, item_identifier, entries)
                no_elem_cache: bool = skip_cache(item_identifier)
                msgproc.log(f"browse executed for [{thing_name}] in [{(time.time() - start):.3f}]")
                return _returnentries(entries, no_cache=no_elem_cache)
            else:
                msgproc.log(f"no element handler for [{thing_name}], elapsed [{(time.time() - start):.3f}]")
                return _returnentries(entries)


def tidal_search(
        tidal_session: TidalSession,
        search_type: SearchType,
        value: str,
        limit: int = config.get_search_limit(),
        offset: int = 0) -> list:
    search_result: dict = tidal_session.search(
        query=value,
        limit=limit,
        offset=offset,
        models=[search_type.get_model()])
    item_list: list = search_result[search_type.get_dict_entry()]
    return item_list


@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    _inittidal()
    objid = a["objid"]
    entries = []

    # Run the search and build a list of entries in the expected format. See for example
    # ../radio-browser/radiotoentry for an example
    value: str = a["value"]
    field: str = a["field"]
    objkind: str = a["objkind"] if "objkind" in a else None
    origsearch: str = a["origsearch"] if "origsearch" in a else None
    # if not objkind or len(objkind) == 0: objkind = field

    msgproc.log(f"Searching for [{value}] as [{field}] objkind [{objkind}] origsearch [{origsearch}] ...")
    resultset_length: int = 0

    tidal_session: TidalSession = get_session()

    if not objkind or len(objkind) == 0:
        if SearchType.ARTIST.get_name() == field:
            # search artists by specified value
            item_list: list[TidalArtist] = tidal_search(
                tidal_session=tidal_session,
                search_type=SearchType.ARTIST,
                value=value)
            resultset_length = len(item_list) if item_list else 0
            for item in item_list:
                entries.append(artist_to_entry(
                    objid=objid,
                    artist=item))
        elif SearchType.ALBUM.get_name() == field:
            # search albums by specified value
            item_list: list[TidalAlbum] = tidal_search(
                tidal_session=tidal_session,
                search_type=SearchType.ALBUM,
                value=value)
            resultset_length = len(item_list) if item_list else 0
            for item in item_list:
                entries.append(album_to_entry(
                    objid=objid,
                    tidal_session=tidal_session,
                    album=item))
        elif SearchType.TRACK.get_name() == field:
            # search tracks by specified value
            item_list: list[TidalTrack] = tidal_search(
                tidal_session=tidal_session,
                search_type=SearchType.TRACK,
                value=value)
            resultset_length = len(item_list) if item_list else 0
            options: dict[str, any] = dict()
            context: Context = Context()
            set_option(options=options, option_key=OptionKey.SKIP_TRACK_NUMBER, option_value=True)
            for item in item_list:
                entries.append(track_to_entry(
                    objid=objid,
                    track_adapter=instance_tidal_track_adapter(
                        tidal_session=tidal_session,
                        track=item),
                    options=options,
                    tidal_session=tidal_session,
                    context=context))
    else:
        # objkind is set
        model_map: dict[str, SearchType] = dict()
        model_map["track"] = SearchType.TRACK
        model_map["album"] = SearchType.ALBUM
        model_map["artist"] = SearchType.ARTIST
        search_type_list: list[SearchType] = list()
        if objkind in model_map.keys():
            search_type_list.append(model_map[objkind])
        track_options: dict[str, any] = dict()
        set_option(options=track_options, option_key=OptionKey.SKIP_TRACK_NUMBER, option_value=True)
        st: SearchType
        for st in search_type_list:
            # perform search
            item_list = tidal_search(
                tidal_session=tidal_session,
                search_type=st,
                value=value)
            resultset_length += len(item_list) if item_list else 0
            context: Context = Context()
            for item in item_list:
                if st.get_model() == TidalArtist:
                    entries.append(artist_to_entry(
                        objid=objid,
                        artist=item))
                elif st.get_model() == TidalAlbum:
                    entries.append(album_to_entry(
                        objid=objid,
                        tidal_session=tidal_session,
                        album=item))
                elif st.get_model() == TidalTrack:
                    entries.append(track_to_entry(
                        objid=objid,
                        track_adapter=instance_tidal_track_adapter(
                            tidal_session=tidal_session,
                            track=item),
                        options=track_options,
                        tidal_session=tidal_session,
                        context=context))
    msgproc.log(f"Search for [{value}] as [{field}] with objkind [{objkind}] returned [{resultset_length}] entries")
    return _returnentries(entries)


# Possible once initialisation. Always called by browse() or search(), should remember if it has
# something to do (e.g. the _g_init thing, but this could be something else).
_g_init = False


def get_image_cache_path_for_pruning(www_image_path: list[str]) -> bool:
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
    return tidal_util.ensure_directory(
        upmplgutils.getUpnpWebDocRoot(constants.PluginConstant.PLUGIN_NAME.value),
        www_image_path)


def prune_cache(cached_images_dir: str):
    now: float = time.time()
    # list directories
    file_count: int = 0
    deleted_count: int = 0
    max_age_seconds: int = config.get_config_param_as_int(constants.ConfigParam.CACHED_IMAGE_MAX_AGE_DAYS) * (24 * 60 * 60)
    for filename in glob.glob(f"{cached_images_dir}/**/*", recursive=True):
        filename_path = os.path.normpath(filename)
        file_count += 1
        time_diff_sec: float = now - os.path.getmtime(filename_path)
        # msgproc.log(f"Found file: timediff [{time_diff_sec:.2f}] [{filename}]")
        if time_diff_sec >= float(max_age_seconds):
            # msgproc.log(f"Deleting file [{filename}] which is older than "
            #             f"[{config.get_config_param_as_int(constants.ConfigParam.CACHED_IMAGE_MAX_AGE_DAYS)}] days")
            os.remove(filename_path)
            deleted_count += 1
    msgproc.log(f"Deleted [{deleted_count}] cached images out of [{file_count}]")


def get_static_image(image_type: str, image_name_no_ext: str) -> str:
    # msgproc.log(f"get_static_image for [{len(static_images_dict)}] keys.")
    img_list: list[str] = static_images_dict[image_type] if image_type in static_images_dict else []
    img: str
    for img in img_list:
        # msgproc.log(f"get_static_image examining [{image_type}] [{img}] ...")
        no_ext_img: str = os.path.splitext(img)[0]
        if no_ext_img.lower() == image_name_no_ext.lower():
            return img
    return None


def load_static_images(path_static_images: list[str], static_images_dir: str):
    msgproc.log(f"copy_static_images to [{path_static_images}]")
    # plugin_static_images_dir: str = tidal_util.get_plugin_static_images_abs_path()
    plugin_image_dir: constants.PluginImageDirectory
    for plugin_image_dir in constants.PluginImageDirectory:
        dict_image_list: list[str] = static_images_dict[plugin_image_dir.value] if plugin_image_dir.value in static_images_dict else None
        if not dict_image_list:
            # we create a list and add it to the dict
            dict_image_list = []
            static_images_dict[plugin_image_dir.value] = dict_image_list
        # image_name_list: list[str] = []
        # curr_dir: str = os.path.join(tidal_util.get_webserver_static_images_path(), plugin_image_dir.value)
        ensure_path_list: list[str] = [
            constants.PluginConstant.PLUGIN_NAME.value,
            constants.PluginConstant.PLUGIN_IMAGES_DIRECTORY.value,
            plugin_image_dir.value]
        msgproc.log(f"load_static_images [{plugin_image_dir.value}] -> [{ensure_path_list}]")
        webserver_path: str = tidal_util.ensure_directory(
            upmplgutils.getUpnpWebDocRoot(constants.PluginConstant.PLUGIN_NAME.value),
            ensure_path_list)
        msgproc.log(f"load_static_images webserver_path [{webserver_path}]")
        dir_content: list[str] = os.listdir(webserver_path)
        static_file: str
        for static_file in dir_content:
            if static_file == ".placeholder":
                # ignore this one
                continue
            msgproc.log(f"Found [{static_file}] in [{webserver_path}], adding to static_images_dict ...")
            if static_file not in dict_image_list:
                msgproc.log(f"Tracking file [{static_file}] ...")
                dict_image_list.append(static_file)
            else:
                msgproc.log(f"File [{static_file}] already tracked.")
            # shutil.copy(os.path.join(curr_dir, static_file), target_path)
            # msgproc.log(f"File [{static_file}] in [{'/'.join(ensure_path_list)}] has been copied to [{target_path}].")
            # image_name_list.append(static_file)
        # static_images_dict[plugin_image_dir.value] = image_name_list
        msgproc.log(f"load_static_images for [{plugin_image_dir.value}] -> [{len(dict_image_list)}] files tracked.")
    msgproc.log(f"load_static_images completed, [{len(static_images_dict)}] keys.")


def copy_static_images(path_static_images: list[str], static_images_dir: str):
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    msgproc.log(f"copy_static_images to [{path_static_images}]")
    plugin_static_images_dir: str = tidal_util.get_plugin_static_images_abs_path()
    msgproc.log(f"copy_static_images from [{plugin_static_images_dir}]")
    if not os.path.exists(plugin_static_images_dir) or not os.path.isdir(plugin_static_images_dir):
        msgproc.log(f"copy_static_images path [{plugin_static_images_dir}] does not exist or is not a directory.")
        return

    plugin_image_dir: constants.PluginImageDirectory
    for plugin_image_dir in constants.PluginImageDirectory:
        # image_name_list: list[str] = []
        curr_dir: str = os.path.join(plugin_static_images_dir, plugin_image_dir.value)
        if not os.path.exists(curr_dir) or not os.path.isdir(curr_dir):
            msgproc.log(f"copy_static_images path [{curr_dir}] does not exist or is not a directory.")
            return
        ensure_path_list: list[str] = path_static_images + [plugin_image_dir.value]
        msgproc.log(f"copy_static_images [{plugin_image_dir.value}] -> [{ensure_path_list}]")
        target_path: str = tidal_util.ensure_directory(
            upmplgutils.getUpnpWebDocRoot(constants.PluginConstant.PLUGIN_NAME.value),
            ensure_path_list)
        msgproc.log(f"copy_static_images plugin dir [{curr_dir}]")
        dir_content: list[str] = os.listdir(curr_dir)
        static_file: str
        skip_count: int = 0
        file_count: int = 0
        for static_file in dir_content:
            if static_file == ".placeholder":
                # ignore this one, don't event count as skipped
                continue
            file_count += 1
            target_file_name: str = os.path.join(target_path, static_file)
            source_file_name: str = os.path.join(curr_dir, static_file)
            exists: bool = os.path.exists(target_file_name)
            is_file: bool = os.path.isfile(target_file_name)
            if exists and not is_file:
                # it exists but it is a directory, we need to skip the file.
                msgproc.log(f"copy_static_images [{target_file_name}] exists but is not a file.")
                continue
            if exists:
                if verbose:
                    msgproc.log(f"copy_static_images [{target_file_name}] exists and is a file.")
                # load source and file, then compare
                source_modified: float = os.path.getmtime(source_file_name)
                target_modified: float = os.path.getmtime(target_file_name)
                # skip if target is newer
                if target_modified >= source_modified:
                    if verbose:
                        msgproc.log(f"copy_static_images [{target_file_name}] same or newer, skipping.")
                    skip_count += 1
                    continue
                else:
                    if verbose:
                        msgproc.log(f"copy_static_images [{target_file_name}] is older, copying ...")
            else:
                if verbose:
                    msgproc.log(f"copy_static_images [{target_file_name}] does not exist, copying ...")
            action: tuple[str, str] = ("copying", "copied") if not exists else ("updating", "updated")
            msgproc.log(f"Found [{static_file}] in [{'/'.join(ensure_path_list)}], {action[0]} to [{target_file_name}]...")
            shutil.copy(source_file_name, target_file_name)
            msgproc.log(f"File [{static_file}] in [{'/'.join(ensure_path_list)}] has been {action[1]} to [{target_path}].")
        msgproc.log(f"copy_static_images loaded completed for [{plugin_image_dir.value}] "
                    f"count [{file_count}] "
                    f"skipped [{skip_count}]")
    msgproc.log(f"copy_static_images loaded [{len(static_images_dict)}] keys.")


def _inittidal():
    global _g_init
    if _g_init:
        return True
    # Do whatever is needed here
    msgproc.log(f"Tidal Plugin Release {constants.PluginConstant.PLUGIN_RELEASE.value}")
    msgproc.log(f"enable_read_stream_metadata=["
                f"{config.get_config_param_as_bool(constants.ConfigParam.ENABLE_READ_STREAM_METADATA)}]")
    msgproc.log(f"enable_assume_bitdepth=[{config.enable_assume_bitdepth}]")
    msgproc.log(f"enable_image_caching=[{config.get_enable_image_caching()}]")
    msgproc.log(f"Image caching enabled [{config.get_enable_image_caching()}], cleaning metadata cache ...")
    docroot_base_url: str = tidal_util.get_docroot_base_url()
    if docroot_base_url:
        persistence.clean_image_url_starting_with(
            base_root=docroot_base_url,
            opposite=(True if config.get_enable_image_caching() else False))
    msgproc.log(f"Image caching enabled [{config.get_enable_image_caching()}], cleaning complete")
    cache_dir: str = upmplgutils.getcachedir(constants.PluginConstant.PLUGIN_NAME.value)
    msgproc.log(f"Cache dir for [{constants.PluginConstant.PLUGIN_NAME.value}] is [{cache_dir}]")
    msgproc.log(f"DB version for [{constants.PluginConstant.PLUGIN_NAME.value}] is [{persistence.get_db_version()}]")
    # prepare path for static images
    path_static_images: list[str] = tidal_util.get_webserver_static_images_path()
    static_images_dir: str = tidal_util.ensure_directory(
        base_dir=upmplgutils.getUpnpWebDocRoot(constants.PluginConstant.PLUGIN_NAME.value),
        sub_dir_list=path_static_images)
    msgproc.log(f"Static images dir is [{static_images_dir}]")
    # copy static images from plugin code to static images path
    copy_static_images(path_static_images, static_images_dir)
    # load static images
    load_static_images(path_static_images, static_images_dir)
    # prepare path for cached images
    path_cached_images: list[str] = tidal_util.get_webserver_cached_images_path()
    cached_images_dir: str = tidal_util.ensure_directory(
        upmplgutils.getUpnpWebDocRoot(constants.PluginConstant.PLUGIN_NAME.value),
        path_cached_images)
    msgproc.log(f"Cached images dir is [{cached_images_dir}]")
    # pruning of cached images
    if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_CACHED_IMAGE_AGE_LIMIT):
        prune_path: str = get_image_cache_path_for_pruning(tidal_util.get_webserver_cached_images_path())
        if prune_path:
            msgproc.log(f"Pruning image cache at path [{prune_path}] ...")
            prune_cache(cached_images_dir=prune_path)
            msgproc.log(f"Pruned image cache at path [{prune_path}].")
    else:
        msgproc.log("Image pruning disabled.")
    _g_init = True
    return True


msgproc.mainloop()
