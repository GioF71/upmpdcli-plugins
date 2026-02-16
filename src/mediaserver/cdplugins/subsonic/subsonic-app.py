#!/usr/bin/env python3
# Copyright (C) 2023,2024,2025,2026 Giovanni Fulco
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

import subsonic_init
import subsonic_util
import request_cache

import json
import posixpath
import re
import upmplgutils
import upmpdmeta
import os
import statistics
import random

from subsonic_connector.response import Response
from subsonic_connector.album_list import AlbumList
from subsonic_connector.album import Album
from subsonic_connector.song import Song
from subsonic_connector.genres import Genres
from subsonic_connector.genre import Genre
from subsonic_connector.list_type import ListType
from subsonic_connector.search_result import SearchResult
from subsonic_connector.artists import Artists
from subsonic_connector.artists_initial import ArtistsInitial
from subsonic_connector.artist import Artist
from subsonic_connector.artist_list_item import ArtistListItem
from subsonic_connector.playlists import Playlists
from subsonic_connector.playlist import Playlist
from subsonic_connector.playlist_entry import PlaylistEntry
from subsonic_connector.internet_radio_stations import InternetRadioStations
from subsonic_connector.internet_radio_station import InternetRadioStation
from subsonic_connector.random_songs import RandomSongs
from subsonic_connector.top_songs import TopSongs
from subsonic_connector.similar_artist import SimilarArtist
from subsonic_connector.artist_info import ArtistInfo
from subsonic_connector.similar_songs import SimilarSongs
from subsonic_connector.starred import Starred
from persistence_tuple import ArtistAlbumCoverArt

import config

from tag_type import TagType, get_tag_type_by_name
from element_type import ElementType, get_element_type_by_name
from search_type import SearchType
from search_type import KindType

from item_identifier_key import ItemIdentifierKey
from item_identifier import ItemIdentifier

import codec
import cache_actions
import cache_manager_provider
import identifier_util
import upnp_util
import entry_creator
import constants
import persistence
import metadata_converter
from album_metadata import AlbumMetadata
from album_property_metadata import AlbumPropertyMetadata
from album_property_key import AlbumPropertyKey
from album_property_key import get_album_property_key
from album_property_key import AlbumPropertyKeyValue
from album_property_dataset import AlbumPropertyDataset
from album_property_dataset import AlbumPropertyDatasetProcessor
from common_data_structures import ArtistIdNameCoverArt

from album_util import sort_song_list
from album_util import get_album_base_path
from album_util import get_dir_from_path
from album_util import MultiCodecAlbum
from album_util import AlbumTracks
from album_util import get_album_year_str
from album_util import has_year

from value_holder import encode_value_holder
from value_holder import decode_value_holder

from tag_to_entry_context import TagToEntryContext

import art_retriever
from retrieved_art import RetrievedArt

from subsonic_util import get_random_art_by_genre
from subsonic_util import get_album_tracks

from option_key import OptionKey
import option_util

import connector_provider

from radio_entry_type import RadioEntryType

import secrets
import mimetypes
import time
import datetime
from typing import Callable
from typing import Any

from msgproc_provider import msgproc
from msgproc_provider import dispatcher

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = f"0${constants.PluginConstant.PLUGIN_NAME.value}$"
upmplgutils.setidprefix(constants.PluginConstant.PLUGIN_NAME.value)

__tag_initial_page_enabled_default: dict[str, bool] = {
    TagType.RECENTLY_ADDED_ALBUMS.tag_name: False,
    TagType.NEWEST_ALBUMS.tag_name: False,
    TagType.OLDEST_ALBUMS.tag_name: False,
    TagType.RECENTLY_PLAYED_ALBUMS.tag_name: False,
    TagType.HIGHEST_RATED_ALBUMS.tag_name: False,
    TagType.MOST_PLAYED_ALBUMS.tag_name: False,
    TagType.ALPHABETICAL_BY_NAME_ALBUMS.tag_name: False,
    TagType.ALPHABETICAL_BY_ARTIST_ALBUMS.tag_name: False,
    TagType.RANDOM.tag_name: False,
    TagType.ALBUMS_WITHOUT_MUSICBRAINZ.tag_name: False,
    TagType.ALBUMS_WITHOUT_COVER.tag_name: False,
    TagType.ALBUMS_WITHOUT_GENRE.tag_name: False,
    TagType.FAVORITE_ALBUMS.tag_name: False,
    TagType.ALL_ARTISTS.tag_name: False,
    TagType.ARTIST_ROLES.tag_name: False,
    TagType.ALL_ARTISTS_INDEXED.tag_name: False,
    TagType.ALL_ARTISTS_UNSORTED.tag_name: False,
    TagType.ALL_ALBUM_ARTISTS_UNSORTED.tag_name: False,
    TagType.ALL_COMPOSERS_UNSORTED.tag_name: False,
    TagType.ALL_CONDUCTORS_UNSORTED.tag_name: False,
    TagType.FAVORITE_ARTISTS.tag_name: False,
    TagType.RANDOM_SONGS.tag_name: False,
    TagType.RANDOM_SONGS_LIST.tag_name: False,
    TagType.FAVORITE_SONGS.tag_name: False,
    TagType.FAVORITE_SONGS_LIST.tag_name: False,
    TagType.INTERNET_RADIOS.tag_name: False,
    TagType.ALBUM_BROWSER.tag_name: False
}


def __tag_playlists_precondition() -> bool:
    if config.get_config_param_as_bool(constants.ConfigParam.SHOW_EMPTY_PLAYLISTS):
        return True
    response: Response[Playlists] = connector_provider.get().getPlaylists()
    if not response or not response.isOk():
        return False
    return len(response.getObj().getPlaylists()) > 0


__tag_show_precondition: dict[str, Callable[[], bool]] = {
    TagType.PLAYLISTS.tag_name: __tag_playlists_precondition
}


def tag_enabled_in_initial_page(tag_type: TagType) -> bool:
    enabled_default: bool = (__tag_initial_page_enabled_default[tag_type.tag_name]
                             if tag_type.tag_name in __tag_initial_page_enabled_default
                             else True)
    enabled_int: int = (int(upmplgutils.getOptionValue(
        f"{config.get_plugin_config_variable_name('taginitialpageenabled')}{tag_type.tag_name}",
        "1" if enabled_default else "0")))
    return enabled_int == 1


# Possible once initialisation. Always called by browse() or search(), should remember if it has
# something to do (e.g. the _g_init thing, but this could be something else).
_g_init = False


def _initsubsonic():
    global _g_init
    if _g_init:
        return True
    # Do whatever is needed here
    msgproc.log(f"Subsonic Plugin Release {constants.PluginConstant.PLUGIN_RELEASE.value}")
    _g_init = True
    return True


def build_streaming_url(track_id: str) -> str:
    streaming_url: str = connector_provider.get().buildSongUrl(
        song_id=track_id,
        format=config.get_transcode_codec(),
        max_bitrate=config.get_transcode_max_bitrate())
    msgproc.log(f"build_streaming_url for track_id: [{track_id}] -> [{streaming_url}]")
    return streaming_url


def __resource_id_from_urlpath(pathprefix, a, resource_name, id_name):
    if "path" not in a:
        raise Exception("coverartid_from_urlpath: no 'path' in args")
    path = a["path"]
    # Updated to use dynamic resource_name and id_name
    # Pattern 1: pathprefix/resource_name/version/1/id_name/value
    exp = posixpath.join(pathprefix, rf"{resource_name}/version/1/{id_name}/(.+)$")
    m = re.match(exp, path)
    if m is None:
        # Pattern 2: pathprefix/resource_name?version=1&id_name=value
        exp_old = posixpath.join(pathprefix, rf"{resource_name}\?version=1&{id_name}=(.+)$")
        m = re.match(exp_old, path)
    if m is None:
        raise Exception(f"coverartid_from_urlpath: path [{path}] does not match expected patterns")
    return m.group(1)


def __trackid_from_urlpath(pathprefix, a):
    return __resource_id_from_urlpath(pathprefix=pathprefix, a=a, resource_name="track", id_name="trackId")


def __coverartid_from_urlpath(pathprefix, a):
    return __resource_id_from_urlpath(pathprefix=pathprefix, a=a, resource_name="coverart", id_name="coverartId")


@dispatcher.record('trackuri')
def trackuri(a):
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    if verbose:
        msgproc.log(f"trackuri --- {a} ---")
    upmpd_pathprefix = os.environ["UPMPD_PATHPREFIX"]
    path: str = a["path"] if "path" in a else None
    if not path:
        msgproc.log("trackuri: path is missing!")
        return {}
    # must start with /subsonic
    starts_with_subsonic: str = "/subsonic"
    if not path.startswith(starts_with_subsonic):
        msgproc.log(f"trackuri: {path} is expected to start with [{starts_with_subsonic}]")
        return {}
    after_subsonic: str = path[len(starts_with_subsonic) + 1:]
    if verbose:
        msgproc.log(f"path after [{starts_with_subsonic}]: [{after_subsonic}]")
    track_id_path_prefix: str = "track/version/1/trackId"
    cover_art_path_prefix: str = "coverart/version/1/coverartId"
    result: dict[str, Any] = {}
    if after_subsonic.startswith(track_id_path_prefix):
        track_id: str = __trackid_from_urlpath(upmpd_pathprefix, a)
        result = song_trackuri(track_id)
    elif after_subsonic.startswith(cover_art_path_prefix):
        cover_art_id: str = __coverartid_from_urlpath(upmpd_pathprefix, a)
        result = cover_art_trackuri(cover_art_id)
    else:
        msgproc.log(f"Invalid path [{path}]")
    return result


def cover_art_trackuri(item_id: str):
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    if verbose:
        msgproc.log(f"cover_art_trackuri for item_id [{item_id}]")
    cover_art_url: str = subsonic_util.build_cover_art_url(item_id=item_id, force_final_url=True)
    result: dict[str, Any] = {}
    if cover_art_url:
        if verbose:
            msgproc.log(f"cover_art_trackuri for item_id [{item_id}] -> [{cover_art_url}]")
        result["media_url"] = cover_art_url
    return result


def song_trackuri(track_id: str):
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    song: Song = None
    try:
        res: Response[Song] = connector_provider.get().getSong(song_id=track_id)
        song = res.getObj() if res and res.isOk() else None
    except Exception as ex:
        msgproc.log(f"Cannot get a song from id [{track_id}] [{type(ex)}] [{ex}]")
    if not song:
        return {'media_url': ""}
    song_suffix: str = song.getSuffix()
    # scrobble if allowed
    scrobble_msg: str = "no"
    if config.get_config_param_as_bool(constants.ConfigParam.SERVER_SIDE_SCROBBLING):
        scrobble_time: float = 0.0
        scrobble_start: float = time.time()
        scrobble_success: bool = False
        try:
            connector_provider.get().scrobble(song_id=song.getId())
            scrobble_success = True
        except Exception as ex:
            msgproc.log(f"trackuri scrobble failed [{type(ex)}] [{ex}]")
        scrobble_time = time.time() - scrobble_start
        scrobble_msg = f"Success: ({'yes' if scrobble_success else 'no'}) Elapsed ({scrobble_time:.3f})]"
    tr_format: str = config.get_transcode_codec()
    tr_bitrate: int = config.get_transcode_max_bitrate()
    if tr_format and song.getSuffix() and tr_format.lower() == song.getSuffix().lower():
        # skip transcoding when not needed
        if verbose:
            msgproc.log(f"trackuri transcoding skipped because suffix is [{song.getSuffix()}] "
                        f"and transcoding format is [{tr_format}]")
        tr_format = None
        tr_bitrate = None
    media_url: str = connector_provider.get().buildSongUrlBySong(
        song=song,
        format=tr_format,
        max_bitrate=tr_bitrate)
    # media_url is now set, we can now start collecting information
    # just to show metadata from the subsonic server
    mimetype: str = song.getContentType()
    bitrate: str = str(song.getBitRate()) if song.getBitRate() else None
    duration: str = str(song.getDuration()) if song.getDuration() else None
    msgproc.log(f"trackuri for track_id [{track_id}] "
                f"tr_format [{tr_format}] "
                f"tr_bitrate [{tr_bitrate}] "
                f"media_url [{media_url}] "
                f"source mimetype [{mimetype}] "
                f"source suffix [{song_suffix}] "
                f"source bitRate [{bitrate}] "
                f"source bitDepth [{subsonic_util.get_song_bit_depth(song=song)}] "
                f"source samplingRate [{subsonic_util.get_song_sampling_rate(song=song)}] "
                f"duration [{duration}] "
                f"scrobble [{scrobble_msg}]")
    result: dict[str, str] = dict()
    # only media_url is necessary
    # anything else would be ignored
    result["media_url"] = media_url
    return result


def _returnentries(entries, no_cache: bool = False):
    """Helper function: build plugin browse or search return value from items list"""
    return {"entries": json.dumps(entries), "nocache": "1" if no_cache else "0"}


def _station_to_entry(
        objid,
        station: InternetRadioStation) -> upmplgutils.direntry:
    stream_url: str = station.getStreamUrl()
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.INTERNET_RADIO.element_name,
        station.getId())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry: dict[str, any] = {}
    entry['id'] = id
    entry['pid'] = station.getId()
    upnp_util.set_class('object.item.audioItem.audioBroadcast', entry)
    entry['uri'] = stream_url
    upnp_util.set_track_title(station.getName(), entry)
    entry['tp'] = 'it'
    upnp_util.set_artist("Internet Radio", entry)
    guess_mimetype_tuple = mimetypes.guess_type(stream_url)
    mimetype: str = guess_mimetype_tuple[0] if guess_mimetype_tuple else None
    msgproc.log(f"_station_to_entry guessed mimetype [{mimetype}] for stream_url [{stream_url}]")
    if not mimetype:
        mimetype = "audio/mpeg"
    upnp_util.set_mimetype(mimetype, entry)
    return entry


def _song_data_to_entry(objid, entry_id: str, song: Song) -> dict:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    if verbose:
        msgproc.log(f"entering _song_data_to_entry for song id [{song.getId()}] ...")
    entry: dict[str, any] = {}
    entry['id'] = entry_id
    entry['pid'] = song.getId()
    upnp_util.set_class_music_track(entry)
    entry['uri'] = entry_creator.build_intermediate_url(track_id=song.getId(), suffix=song.getSuffix())
    title: str = song.getTitle()
    upnp_util.set_track_title(title, entry)
    entry['tp'] = 'it'
    entry['discnumber'] = song.getDiscNumber()
    upnp_util.set_track_number(song.getTrack(), entry)
    upnp_util.set_artist(
        artist=subsonic_util.get_song_display_artist(song=song),
        target=entry)
    entry['upnp:album'] = song.getAlbum()
    upnp_util.set_mimetype(song.getContentType(), entry)
    entry['upnp:genre'] = song.getGenre()
    upnp_util.set_album_art_from_uri(
        album_art_uri=subsonic_util.build_cover_art_url(item_id=song.getCoverArt()),
        target=entry)
    entry['duration'] = str(song.getDuration())
    entry_creator.set_song_quality_flags(song=song, entry=entry)
    if verbose:
        msgproc.log(f"_song_data_to_entry song id [{song.getId()}] -> [{entry}]")
    return entry


def present_album_version(
        objid,
        item_identifier: ItemIdentifier,
        album_id: str,
        album_version_path: str,
        entries: list,
        album_and_tracks: tuple[Album, AlbumTracks] = None) -> list:
    album: Album
    album_tracks: AlbumTracks
    album, album_tracks = album_and_tracks if album_and_tracks else get_album_tracks(album_id)
    if album is None or album_tracks is None:
        return None
    discnumber_list: list[int] = subsonic_util.get_album_disc_numbers(album)
    disc_count: int = len(discnumber_list) if discnumber_list else 1
    is_multi_disc: bool = disc_count > 1
    disc_title_dict: dict[int, str] = subsonic_util.get_disc_titles_from_album_as_dict(album)
    has_disc_titles: bool = is_multi_disc and len(disc_title_dict) > 0
    max_tracks: int = config.get_config_param_as_int(constants.ConfigParam.MAX_TRACKS_FOR_NO_DISC_SPLIT)
    too_many_songs: bool = album.getSongCount() > max_tracks
    show_as_multidisc = (is_multi_disc) and (has_disc_titles or too_many_songs)
    ignore_multidisc: bool = item_identifier.get(ItemIdentifierKey.ALBUM_IGNORE_DISCNUMBERS, "0") == "1"
    if show_as_multidisc and not ignore_multidisc:
        # we should present discs here, passing for now.
        # we will need avp_enc possibly
        avp_enc: str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, None)
        songs_by_disc_number: dict[int, list[Song]] = subsonic_util.get_songs_by_album_disc_numbers(album)
        dn: int
        for dn in discnumber_list:
            disc_title: str = disc_title_dict[dn] if dn in disc_title_dict else ""
            entry_name: str = f"Disc {dn}/{len(discnumber_list)}{': ' + disc_title if disc_title else ''}"
            # create disc entry.
            disc_identifier: ItemIdentifier = ItemIdentifier(ElementType.ALBUM_DISC.element_name, album_id)
            if avp_enc:
                disc_identifier.set(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, avp_enc)
            disc_identifier.set(ItemIdentifierKey.ALBUM_DISC_NUMBERS, str(dn))
            disc_id: str = identifier_util.create_objid(
                objid=objid,
                id=identifier_util.create_id_from_identifier(disc_identifier))
            entry: dict[str, any] = upmplgutils.direntry(
                disc_id,
                objid,
                title=entry_name)
            cover_art_songs: list[Song] = songs_by_disc_number[dn] if dn in songs_by_disc_number else []
            cover_art_song: Song = cover_art_songs[0] if len(cover_art_songs) > 0 else None
            upnp_util.set_album_art_from_uri(
                album_art_uri=subsonic_util.get_cover_art_url_by_song(cover_art_song),
                target=entry)
            entries.append(entry)
        return entries
    album_mbid: str = subsonic_util.get_album_musicbrainz_id(album)
    song_list: list[Song] = album_tracks.getSongList()
    multi_codec_album: MultiCodecAlbum = album_tracks.getMultiCodecAlbum()
    current_base_path: str = None
    track_num: int = 0
    album_path_set: set[str] = set()
    force_cover_art_save_trackid_set: set[str] = set()
    for current_song in song_list:
        song_path: str = get_dir_from_path(current_song.getPath())
        song_path = get_album_base_path(song_path)
        # keep track of album path(s)
        if song_path not in album_path_set:
            album_path_set.add(song_path)
        if album_version_path is None or album_version_path == song_path:
            new_base_path: str = get_album_base_path(get_dir_from_path(current_song.getPath()))
            if not current_base_path:
                track_num = 1
            elif current_base_path == new_base_path:
                track_num += 1
            # maybe incorporate this in first condition in or
            # Wait for a test case to make sure it still works...
            elif not (current_base_path == new_base_path):
                track_num = 1
            current_base_path = new_base_path
            options: dict[str, any] = {}
            option_util.set_option(
                options=options,
                option_key=OptionKey.FORCE_TRACK_NUMBER,
                option_value=track_num)
            option_util.set_option(
                options=options,
                option_key=OptionKey.MULTI_CODEC_ALBUM,
                option_value=multi_codec_album)
            # try to force-save each track cover art once
            force_cover_art_save: bool = False
            song_cover_art: str = current_song.getCoverArt()
            if song_cover_art and song_cover_art not in force_cover_art_save_trackid_set:
                force_cover_art_save = True
            entry = entry_creator.song_to_entry(
                objid=objid,
                song=current_song,
                force_cover_art_save=force_cover_art_save,
                options=options)
            if force_cover_art_save:
                force_cover_art_save_trackid_set.add(song_cover_art)
            entries.append(entry)
    # show paths if requested
    if config.get_config_param_as_bool(constants.ConfigParam.SHOW_PATHS_IN_ALBUM):
        curr_album_path: str
        cnt: int = 1
        for curr_album_path in album_path_set:
            msgproc.log(f"present_album_version album_paths for [{album_id}] album_mbid [{album_mbid}]"
                        f"-> [{curr_album_path}] [{cnt}/{len(album_path_set)}]")
            cnt += 1
    return entries


def _load_albums_by_type(
        objid: any,
        entries: list,
        tag_type: TagType,
        offset: int = 0,
        size: int = config.get_items_per_page(),
        fromYear: any = None,
        toYear: any = None,
        options: dict[str, any] = dict()) -> list:
    roundtrip_start: float = time.time()
    use_last_for_next: bool = option_util.get_option(options=options, option_key=OptionKey.USE_LAST_FOR_NEXT)
    request_size: int = size + 1 if use_last_for_next else size
    req_start: float = time.time()
    albumList: list[Album] = subsonic_util.get_albums(
        tag_type.query_type,
        size=request_size,
        offset=str(offset),
        fromYear=fromYear if not tag_type == TagType.OLDEST_ALBUMS else toYear,
        toYear=toYear if not tag_type == TagType.OLDEST_ALBUMS else fromYear)
    req_elapsed: float = time.time() - req_start
    msgproc.log(f"Requested [{request_size}] albums from offset [{offset}] -> received [{len(albumList)}] in [{req_elapsed:.3f}]")
    current_album: Album
    tag_cached: bool = False
    counter: int = offset
    to_show: list[Album] = albumList[0:min(len(albumList), size)]
    add_next: bool = len(albumList) == request_size
    total_elapsed_list: list[float] = []
    caching_elapsed_list: list[float] = []
    for current_album in to_show:
        try:
            current_total_start: float = time.time()
            counter += 1
            if config.get_config_param_as_bool(constants.ConfigParam.PREPEND_NUMBER_IN_ALBUM_LIST):
                option_util.set_option(
                    options=options,
                    option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE,
                    option_value=counter)
            current_caching_start: float = time.time()
            # cache_actions.on_album(album=current_album)
            if tag_type and (not tag_cached) and (offset == 0):
                cache_manager_provider.get().cache_element_value(
                    ElementType.TAG,
                    tag_type.tag_name,
                    current_album.getId())
                tag_cached = True
            current_caching_elapsed: float = time.time() - current_caching_start
            caching_elapsed_list.append(current_caching_elapsed)
            if config.get_config_param_as_bool(constants.ConfigParam.DISABLE_NAVIGABLE_ALBUM):
                entries.append(entry_creator.album_to_entry(
                    objid=objid,
                    album=current_album,
                    options=options))
            else:
                entries.append(entry_creator.album_to_navigable_entry(
                    objid=objid,
                    album=current_album,
                    options=options))
        except Exception as add_entry_ex:
            msgproc.log(f"_load_albums_by_type [{tag_type.query_type}] "
                        f"cannot add album with album_id [{current_album.getId()}] "
                        f"counter [{counter}] "
                        f"due to [{type(add_entry_ex)}] [{add_entry_ex}]")
        current_total_elapsed: float = time.time() - current_total_start
        total_elapsed_list.append(current_total_elapsed)
    if add_next:
        next_start: float = time.time()
        for_next: Album = albumList[len(albumList) - 1]
        try:
            next_page: dict[str, any] = _create_tag_next_entry(
                objid=objid,
                tag=tag_type,
                offset=offset + len(entries))
        except Exception as add_next:
            msgproc.log(f"_load_albums_by_type [{tag_type.query_type}] "
                        f"cannot add album_id [{current_album.getId()}] "
                        f"as next entry due to [{type(add_next)}] [{add_next}]")
        next_cover_art: str = subsonic_util.build_cover_art_url(item_id=for_next.getCoverArt())
        upnp_util.set_album_art_from_uri(next_cover_art, next_page)
        entries.append(next_page)
        next_total_elapsed: float = time.time() - next_start
        total_elapsed_list.append(next_total_elapsed)
    roundtrip_elapsed: float = time.time() - roundtrip_start
    msgproc.log(f"_load_albums_by_type roundtrip [{roundtrip_elapsed:.3f}] "
                f"api [{req_elapsed:.3f}] "
                f"proc total [{sum(total_elapsed_list):.3f}] (cnt [{len(total_elapsed_list)}] "
                f"avg [{statistics.fmean(total_elapsed_list):.3f}] "
                f"min [{min(total_elapsed_list):.3f}] "
                f"max [{max(total_elapsed_list):.3f}]) "
                f"proc caching (portion of proc) [{sum(caching_elapsed_list):.3f}] (cnt [{len(caching_elapsed_list)}] "
                f"avg [{statistics.fmean(caching_elapsed_list):.3f}] "
                f"min [{min(caching_elapsed_list):.3f}] "
                f"max [{max(caching_elapsed_list):.3f}])")
    return entries


def _load_albums_by_artist(artist_id: str, release_types: subsonic_util.AlbumReleaseTypes) -> list[Album]:
    artist_response: Response[Artist] = connector_provider.get().getArtist(artist_id)
    if not artist_response.isOk():
        raise Exception(f"Cannot get albums for artist_id {artist_id}")
    album_list: list[Album] = artist_response.getObj().getAlbumList()
    msgproc.log(f"_load_albums_by_artist [{artist_id}] -> [{len(album_list)}] albums")
    if release_types:
        album_list = albums_by_release_type(artist_id, album_list, release_types)
    return album_list


def _albums_by_artist_to_entries(
        objid: any,
        artist_id: str,
        album_list: list[Album],
        offset: int,
        entries: list) -> list:
    current_album: Album
    counter: int = offset
    for current_album in album_list if album_list else []:
        counter += 1
        if current_album.getArtistId():
            cache_actions.on_album(album=current_album)
        genre_list: list[str] = current_album.getGenres()
        for curr in genre_list:
            # TODO what do I do with these genres?
            pass
        options: dict[str, any] = {}
        option_util.set_option(
            options=options,
            option_key=OptionKey.APPEND_ARTIST_IN_ALBUM_TITLE,
            option_value=False)
        option_util.set_option(
            options=options,
            option_key=OptionKey.SKIP_ARTIST_ID,
            option_value=artist_id)
        if config.get_config_param_as_bool(constants.ConfigParam.PREPEND_NUMBER_IN_ALBUM_LIST):
            option_util.set_option(
                options=options,
                option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE,
                option_value=counter)
        if config.get_config_param_as_bool(constants.ConfigParam.DISABLE_NAVIGABLE_ALBUM):
            entries.append(entry_creator.album_to_entry(
                objid=objid,
                album=current_album,
                options=options))
        else:
            entries.append(entry_creator.album_to_navigable_entry(
                objid=objid,
                album=current_album,
                options=options))
    return entries


def __load_artists_by_initial(
        objid,
        artist_initial: str,
        entries: list,
        element_type: ElementType,
        options: dict[str, any] = {}) -> list:
    offset: int = option_util.get_option(options=options, option_key=OptionKey.OFFSET)
    counter: int = 0
    artists_response: Response[Artists] = request_cache.get_artists()
    if not artists_response.isOk():
        return entries
    artists_initial: list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial: ArtistsInitial
    broke_out: bool = False
    found_initial: bool = False
    for current_artists_initial in artists_initial:
        # more permissive: provided initial can be in the actual initial
        if current_artists_initial.getName() == artist_initial:
            if not found_initial:
                found_initial = True
            current_artist: ArtistListItem
            for current_artist in current_artists_initial.getArtistListItems():
                entry: dict[str, any] = entry_creator.artist_to_entry(
                    objid=objid,
                    artist=current_artist)
                # if artist has art, set that art for artists by initial tile
                if counter < offset:
                    counter += 1
                    continue
                if counter >= offset + config.get_items_per_page():
                    broke_out = True
                    break
                counter += 1
                entries.append(entry)
        else:
            if found_initial:
                # we are at the next initial
                break
    if broke_out:
        next_identifier: ItemIdentifier = ItemIdentifier(
            element_type.element_name,
            codec.base64_encode(artist_initial))
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.get_items_per_page())
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        entries.append(next_entry)
    return entries


def create_entries_for_genres(objid, entries: list) -> list:
    genres_response: Response[Genres] = request_cache.get_genres()
    if not genres_response.isOk():
        msgproc.log("create_entries_for_genres invalid response, exiting ...")
        return entries
    genre_list = genres_response.getObj().getGenres()
    msgproc.log(f"create_entries_for_genres got [{len(genre_list)}] genres ...")
    genre_list.sort(key=lambda x: x.getName())
    current_genre: Genre
    for current_genre in genre_list:
        msgproc.log(f"create_entries_for_genres creating entry for [{current_genre.getName()}] ...")
        entry: dict[str, any] = entry_creator.genre_to_entry(
            objid,
            current_genre)
        entries.append(entry)
    return entries


def __load_artists(
        objid,
        entries: list,
        tag: TagType,
        options: dict[str, any] = {}) -> list:
    offset: int = option_util.get_option(options=options, option_key=OptionKey.OFFSET)
    all_artist: list[Artist] = request_cache.get_all_artists()
    msgproc.log(f"Sorting [{len(all_artist)}] artists ...")
    all_artist.sort(key=lambda a: a.getName())
    msgproc.log(f"Slicing at offset [{offset}] ...")
    all_artist = all_artist[offset:]
    last_artist: Artist = (all_artist[config.get_items_per_page()]
                           if len(all_artist) > config.get_items_per_page()
                           else None)
    to_display: list[Artist] = all_artist[0:min(len(all_artist), config.get_items_per_page())]
    msgproc.log(f"Displaying [{config.get_items_per_page()}] artists, "
                f"next available [{last_artist is not None}]...")
    current_artist: ArtistListItem
    for current_artist in to_display:
        entries.append(entry_creator.artist_to_entry(
            objid=objid,
            artist=current_artist,
            options=options))
    # show next?
    if last_artist:
        next_entry: dict[str, any] = _create_tag_next_entry(
            objid=objid,
            tag=tag,
            offset=offset + config.get_items_per_page())
        last_artist_album_art_uri: str = art_retriever.get_album_cover_art_url_by_artist_id(last_artist.getId())
        upnp_util.set_album_art_from_uri(
            album_art_uri=last_artist_album_art_uri,
            target=next_entry)
        entries.append(next_entry)
    return entries


def _create_list_of_playlist(objid, entries: list) -> list:
    response: Response[Playlists] = connector_provider.get().getPlaylists()
    if not response.isOk():
        return entries
    playlists: Playlists = response.getObj()
    playlist: Playlist
    for playlist in playlists.getPlaylists():
        entry: dict[str, any] = entry_creator.playlist_to_entry(
            objid,
            playlist)
        entries.append(entry)
    return entries


def _create_list_of_internet_radio(objid, entries: list) -> list:
    response: Response[InternetRadioStations] = connector_provider.get().getInternetRadioStations()
    if not response.isOk():
        return entries
    stations: InternetRadioStations = response.getObj()
    station: InternetRadioStation
    for station in stations.getStations():
        entry: dict[str, any] = _station_to_entry(
            objid,
            station)
        entries.append(entry)
    return entries


def _playlist_entry_to_entry(
        objid,
        playlist_entry: PlaylistEntry) -> dict:
    entry = {}
    identifier: ItemIdentifier = ItemIdentifier(ElementType.SONG.element_name, playlist_entry.getId())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = playlist_entry.getId()
    upnp_util.set_class_music_track(entry)
    song_uri: str = entry_creator.build_intermediate_url(track_id=playlist_entry.getId(), suffix=playlist_entry.getSuffix())
    entry['uri'] = song_uri
    title: str = playlist_entry.getTitle()
    entry['tt'] = title
    entry['tp'] = 'it'
    upnp_util.set_track_number(playlist_entry.getTrack(), entry)
    upnp_util.set_artist(
        artist=subsonic_util.get_playlist_entry_display_artist(playlist_entry=playlist_entry),
        target=entry)
    entry['upnp:album'] = playlist_entry.getAlbum()
    entry['upnp:artist'] = playlist_entry.getArtist()
    upnp_util.set_mimetype(playlist_entry.getContentType(), entry)
    upnp_util.set_album_art_from_uri(
        album_art_uri=subsonic_util.build_cover_art_url(item_id=playlist_entry.getCoverArt()),
        target=entry)
    entry['duration'] = str(playlist_entry.getDuration())
    # add track quality information
    entry_creator.set_song_quality_flags(song=playlist_entry, entry=entry)
    return entry


def _create_list_of_playlist_entries(objid, playlist_id: str, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    start_time: float = time.time()
    response: Response[Playlist] = connector_provider.get().getPlaylist(playlist_id)
    get_playlist_elapsed: float = time.time() - start_time
    if not response.isOk():
        msgproc.log(f"_create_list_of_playlist_entries for playlist_id [{playlist_id}] api call failed.")
        return entries
    entry_list: list[PlaylistEntry] = response.getObj().getEntries()
    song_count: int = len(entry_list)
    msgproc.log(f"_create_list_of_playlist_entries for playlist_id [{playlist_id}] count [{song_count}] "
                f"api call took [{get_playlist_elapsed:.3f}]")
    start_time = time.time()
    playlist_entry: PlaylistEntry
    counter: int = 0
    for playlist_entry in entry_list:
        counter += 1
        entry_start_time: float = time.time()
        entry: dict[str, any] = _playlist_entry_to_entry(
            objid,
            playlist_entry)
        entries.append(entry)
        entry_elapsed_time: float = time.time() - entry_start_time
        if verbose:
            msgproc.log(f"_create_list_of_playlist_entries adding song [{counter}/{song_count}] "
                        f"took [{entry_elapsed_time:.3f}]")
    create_entries_elapsed: float = time.time() - start_time
    msgproc.log(f"_create_list_of_playlist_entries add [{song_count}] entries took [{create_entries_elapsed:.3f}]")
    return entries


def _create_list_of_artist_initials(
        objid,
        entries: list,
        options: dict[str, any] = dict()) -> list:
    artists_response: Response[Artists] = request_cache.get_artists()
    if not artists_response.isOk():
        return entries
    artists_initial: list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial: ArtistsInitial
    for current_artists_initial in artists_initial:
        entry: dict[str, any] = entry_creator.artist_initial_to_entry(
            objid=objid,
            artist_initial=current_artists_initial.getName(),
            options=options)
        entries.append(entry)
        # populate cache of artist by initial
    return entries


def _create_tag_next_entry(
        objid,
        tag: TagType,
        offset: int) -> dict:
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TAG.element_name, tag.tag_name)
    identifier.set(ItemIdentifierKey.OFFSET, offset)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    tag_entry: dict[str, any] = upmplgutils.direntry(
        id=id,
        pid=objid,
        title="Next")
    return tag_entry


def __handler_tag_album_listype(objid, item_identifier: ItemIdentifier, tag_type: TagType, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    counter: int = offset
    try:
        counter += 1
        options: dict[str, any] = dict()
        if config.get_config_param_as_bool(constants.ConfigParam.PREPEND_NUMBER_IN_ALBUM_LIST):
            option_util.set_option(
                options=options,
                option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE,
                option_value=counter)
        option_util.set_option(
            options=options,
            option_key=OptionKey.USE_LAST_FOR_NEXT,
            option_value=True)
        entries = _load_albums_by_type(
            objid=objid,
            entries=entries,
            tag_type=tag_type,
            offset=offset,
            fromYear=datetime.datetime.now().year,
            toYear=0,
            options=options)
        return entries
    except Exception as ex:
        msgproc.log(f"Cannot handle tag [{tag_type.tag_name}] [{type(ex)}] [{ex}]")
        return list()


def handler_tag_albums_without_musicbrainz(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handle_tag_albums_with_anomaly(
        objid=objid,
        item_identifier=item_identifier,
        entries=entries,
        anomaly_detector=lambda lbm: not subsonic_util.get_album_musicbrainz_id(lbm))


def handler_tag_albums_without_cover(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handle_tag_albums_with_anomaly(
        objid=objid,
        item_identifier=item_identifier,
        entries=entries,
        anomaly_detector=lambda lbm: not lbm.getCoverArt())


def handler_tag_albums_without_genre(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handle_tag_albums_with_anomaly(
        objid=objid,
        item_identifier=item_identifier,
        entries=entries,
        anomaly_detector=lambda lbm: len(lbm.getGenres()) == 0)


def handle_tag_albums_with_anomaly(
        objid,
        item_identifier: ItemIdentifier,
        entries: list,
        anomaly_detector: Callable[[Album], bool]) -> list:
    initial_offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    offset: int = initial_offset
    finished: bool = False
    album_selection: list[Album] = []
    finished: bool = False
    max_load_size: int = config.get_config_param_as_int(constants.ConfigParam.MAINTENANCE_MAX_ALBUM_LOAD_SIZE)
    load_count: int = 0
    search_size: int = config.get_config_param_as_int(constants.ConfigParam.SEARCH_SIZE_ALBUM_LIBRARY_MAINTENANCE)
    show_next: bool = False
    while not finished:
        msgproc.log(f"Executing search with offset [{offset}] selection size [{len(album_selection)}]")
        search_result: SearchResult = connector_provider.get().search(
            "",
            artistCount=0,
            songCount=0,
            albumCount=search_size,
            albumOffset=offset)
        album_list: list[Album] = search_result.getAlbums()
        load_count += len(album_list) if album_list else 0
        curr: Album
        for curr in album_list:
            # if not subsonic_util.get_album_musicbrainz_id(curr):
            if anomaly_detector(curr):
                album_selection.append(curr)
                msgproc.log(f"Using offset [{offset}] selection size [{len(album_selection)}]")
                if len(album_selection) == (config.get_items_per_page() + 1):
                    # enough albums
                    finished = True
                    break
                else:
                    offset += 1
            else:
                offset += 1
        if len(album_list) < search_size:
            # finished
            finished = True
        # are we hitting the max load?
        if not finished and load_count >= max_load_size:
            # force show next button, however there won't be an image
            show_next = True
            finished = True
    to_display: list[Album] = album_selection[0:min(len(album_selection), config.get_items_per_page())]
    next_album: Album = (album_selection[config.get_items_per_page()]
                         if len(album_selection) == (config.get_items_per_page() + 1)
                         else None)
    curr_to_display: Album
    for curr_to_display in to_display:
        entries.append(entry_creator.album_to_navigable_entry(
            objid=objid,
            album=curr_to_display))
    if show_next or next_album:
        # add next album entry
        next_entry: dict[str, any] = _create_tag_next_entry(
            objid=objid,
            tag=get_tag_type_by_name(item_identifier.get(ItemIdentifierKey.THING_VALUE)),
            offset=offset)
        if next_album:
            # set album art
            next_cover_art: str = subsonic_util.build_cover_art_url(item_id=next_album.getCoverArt())
            upnp_util.set_album_art_from_uri(next_cover_art, next_entry)
        entries.append(next_entry)
    return entries


def handler_tag_recently_added_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.RECENTLY_ADDED_ALBUMS, entries)


def handler_tag_newest_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.NEWEST_ALBUMS, entries)


def handler_tag_alphabetical_by_name_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.ALPHABETICAL_BY_NAME_ALBUMS, entries)


def handler_tag_alphabetical_by_artist_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.ALPHABETICAL_BY_ARTIST_ALBUMS, entries)


def handler_tag_oldest_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.OLDEST_ALBUMS, entries)


def handler_tag_most_played(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.MOST_PLAYED_ALBUMS, entries)


def handler_tag_favourite_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.FAVORITE_ALBUMS, entries)


def handler_tag_highest_rated(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.HIGHEST_RATED_ALBUMS, entries)


def handler_tag_recently_played(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.RECENTLY_PLAYED_ALBUMS, entries)


def handler_tag_random(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.RANDOM, entries)


def handler_tag_random_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    item_identifier.set(ItemIdentifierKey.SONG_AS_ENTRY, True)
    return _get_random_songs(objid, item_identifier, entries)


def handler_tag_random_songs_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    # just show plain songs here
    max_songs: int = min(
        config.get_config_param_as_int(constants.ConfigParam.MAX_RANDOM_SONG_LIST_SIZE),
        constants.Defaults.SUBSONIC_API_MAX_RETURN_SIZE.value)
    res: Response[RandomSongs]
    try:
        res = connector_provider.get().getRandomSongs(size=max_songs)
        if not res or not res.isOk():
            msgproc.log("Cannot load random songs")
            return entries
    except Exception as ex:
        msgproc.log(f"Cannot load random songs [{type(ex)}] [{ex}]")
        return entries
    # good to go
    song_options: dict[str, any] = dict()
    song: Song
    for song in res.getObj().getSongs():
        option_util.set_option(
            options=song_options,
            option_key=OptionKey.FORCE_TRACK_NUMBER,
            option_value=len(entries) + 1)
        song_entry: dict[str, any] = entry_creator.song_to_entry(
            objid=objid,
            song=song,
            options=song_options)
        if song_entry:
            entries.append(song_entry)
    return entries


def handler_tag_favourite_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    item_identifier.set(ItemIdentifierKey.SONG_AS_ENTRY, True)
    return _get_favourite_songs(objid, item_identifier, entries)


def handler_tag_favourite_songs_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    # just show plain songs here
    res: Response[Starred]
    try:
        res = request_cache.get_starred()
        if not res or not res.isOk():
            msgproc.log("Cannot load starred")
            return entries
    except Exception as ex:
        msgproc.log(f"Cannot load starred songs [{type(ex)}] [{ex}]")
        return entries
    # good to go
    song_options: dict[str, any] = dict()
    song: Song
    for song in res.getObj().getSongs():
        option_util.set_option(
            options=song_options,
            option_key=OptionKey.FORCE_TRACK_NUMBER,
            option_value=len(entries) + 1)
        song_entry: dict[str, any] = entry_creator.song_to_entry(
            objid=objid,
            song=song,
            options=song_options)
        if song_entry:
            entries.append(song_entry)
    return entries


def __get_album_property_dataset() -> AlbumPropertyDataset:
    dataset_load_start: float = time.time()
    key_list: list[str] = [x.property_key for x in AlbumPropertyKey]
    dataset: list[AlbumPropertyMetadata] = persistence.get_album_property_dataset(property_key_list=key_list)
    dataset_load_elapsed: float = time.time() - dataset_load_start
    msgproc.log(f"__get_album_property_dataset dataset ({len(dataset)} items) loaded in [{dataset_load_elapsed:.3f}]")
    return AlbumPropertyDataset(dataset)


def handler_tag_album_browser(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    # get the dataset
    dataset: AlbumPropertyDataset = __get_album_property_dataset()
    # extract keys, no need to sort them
    property_keys: list[str] = dataset.keys
    # matching albums
    album_id_list: list[str] = dataset.album_id_list
    random_album_id_list: list[str] = random.choices(album_id_list, k=len(property_keys))
    random_album_metadata_dict: dict[str, AlbumMetadata] = persistence.get_album_metadata_dict(album_id_list=random_album_id_list)
    # just get the albums
    random_album_metadata_list: list[AlbumMetadata] = list(random_album_metadata_dict.values())
    if verbose:
        msgproc.log(f"handler_tag_album_browser property keys [{property_keys}]")
    curr: AlbumPropertyKey
    for curr in AlbumPropertyKey:
        if curr.property_key not in property_keys:
            msgproc.log(f"handler_tag_album_browser property [{curr.display_value}] [{curr.property_key}] skipped")
            continue
        value_count: int = len(dataset.get_values(key=curr.property_key))
        if value_count > curr.max_items:
            msgproc.log(f"handler_tag_album_browser property [{curr.display_value}] [{curr.property_key}] "
                        f"skipped (too many values [{value_count}], max is [{curr.max_items}])")
            continue
        # none will show up?
        none_needed: bool = dataset.get_album_id_count_for_key(key=curr.property_key) < dataset.album_id_count
        if none_needed > 0:
            #  [None] will be displayed, so we increment counter
            value_count += 1
        key: str = curr.property_key
        identifier: ItemIdentifier = ItemIdentifier(
            ElementType.ALBUM_BROWSE_FILTER_KEY.element_name,
            key)
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        # values for the specified key?
        entry: dict[str, any] = upmplgutils.direntry(
            id=id,
            pid=objid,
            title=f"{curr.display_value} [{value_count}]")
        # set cover art if one is available
        if len(random_album_metadata_list) > 0:
            random_album: AlbumMetadata = random_album_metadata_list.pop(0)
            upnp_util.set_album_art_from_uri(
                album_art_uri=subsonic_util.build_cover_art_url(item_id=random_album.album_cover_art),
                target=entry)
        entries.append(entry)
    return entries


def condition_list_to_dict(condition_list: list[AlbumPropertyKeyValue]) -> dict[str, list[str]]:
    res: dict[str, list[str]] = {}
    curr: AlbumPropertyKeyValue
    for curr in condition_list if condition_list else []:
        list_by_key: list[str] = res[curr.key] if curr.key in res else None
        if list_by_key is None:
            list_by_key = [curr.value]
            res[curr.key] = list_by_key
        else:
            # add if it does not already exists
            if curr.value not in list_by_key:
                list_by_key.append(curr.value)
    return res


def __condition_exists(condition_list: list[AlbumPropertyKeyValue], key: str, value: str) -> bool:
    curr: AlbumPropertyKeyValue
    for curr in condition_list if condition_list else []:
        if curr.key == key and curr.value == value:
            return True
    return False


def handler_album_browse_filter_key(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    album_property_key: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    current_selection_list: list[list[str]] = []
    current_selection_list_str: str = item_identifier.get(ItemIdentifierKey.ALBUM_BROWSE_SELECTION_LIST)
    if current_selection_list_str:
        # decode it
        lst: list[tuple[str, str]] = json.loads(codec.base64_decode(current_selection_list_str))
        # add to main list
        current_selection_list.extend(lst)
    # list_to_encode
    encoded_list: str = codec.base64_encode(json.dumps(current_selection_list))
    msgproc.log(f"handler_album_browse_filter_key for [{album_property_key}] selection list [{current_selection_list}]")
    condition_list: list[AlbumPropertyKeyValue] = []
    curr_selection: list[str]
    for curr_selection in current_selection_list if current_selection_list else []:
        condition: AlbumPropertyKeyValue = AlbumPropertyKeyValue(
            key=curr_selection[0],
            value=curr_selection[1])
        if verbose:
            msgproc.log(f"handler_album_browse_filter_key appending condition [{curr_selection[0]}]:[{curr_selection[1]}]")
        condition_list.append(condition)
    full_dataset: AlbumPropertyDataset = __get_album_property_dataset()
    # shrink dataset (if needed)
    dataset: AlbumPropertyDataset = None
    if len(condition_list) > 0:
        # actually shrink the dataset applying the conditions
        dataset_processor: AlbumPropertyDatasetProcessor = AlbumPropertyDatasetProcessor(dataset=full_dataset)
        dataset = dataset_processor.apply_filters(filter_list=condition_list)
    else:
        # empty conditions dataset is same as the full dataset
        dataset = full_dataset
    matching_album_count: int = dataset.album_id_count
    if verbose:
        msgproc.log(f"dataset with size [{full_dataset.size}] -> "
                    f"filtered to [{dataset.size}] "
                    f"albums [{matching_album_count}]")
    values: list[str] = sorted(dataset.get_values(key=album_property_key))
    curr_value: str
    random_matching_album_id_by_value: dict[str, str] = {}
    match_count_by_value: dict[str, int] = {}
    album_id_list_to_load: list[str] = []
    for curr_value in values:
        value_matching_album_list: list[str] = dataset.get_album_id_list_by_key_value(key=album_property_key, value=curr_value)
        match_count_by_value[curr_value] = len(value_matching_album_list)
        random_album_id: str = secrets.choice(value_matching_album_list)
        random_matching_album_id_by_value[curr_value] = random_album_id
        if verbose:
            msgproc.log(f"random_matching_album_id_by_value for [{curr_value}] -> {random_album_id}")
        album_id_list_to_load.append(random_album_id)
        if verbose:
            msgproc.log(f"album_id_list_to_load appending [{random_album_id}] for [{curr_value}]")
            msgproc.log(f"handler_album_browse_filter_key pair [{album_property_key}]:[{curr_value}] "
                        f"matches [{len(value_matching_album_list)}] albums out of [{matching_album_count}]")
    none_album_id_list: list[str] = list(dataset.album_id_set - dataset.get_album_id_set_for_key(key=album_property_key))
    none_random_album_id: str = secrets.choice(none_album_id_list) if len(none_album_id_list) > 0 else None
    if none_random_album_id:
        if verbose:
            msgproc.log(f"random_matching_album_id_by_value appending [{none_random_album_id}] for None")
        album_id_list_to_load.append(none_random_album_id)
    none_entry_size: int = len(none_album_id_list)
    none_entry_needed: bool = none_entry_size > 0
    # find album matching None
    if verbose:
        msgproc.log(f"handler_album_browse_filter_key for [{album_property_key}] [none] "
                    f"matches [{len(none_album_id_list)}] albums")
    if verbose:
        msgproc.log(f"loading album with id list: [{album_id_list_to_load}]")
    random_album_metadata_dict: dict[str, AlbumMetadata] = persistence.get_album_metadata_dict(album_id_list=album_id_list_to_load)
    if verbose:
        msgproc.log(f"loaded album_id: [{list(random_album_metadata_dict.keys())}]")
    values_to_show: list[str] = [None] + values if none_entry_needed else values
    for curr_value in values_to_show:
        if verbose:
            msgproc.log(f"handler_album_browse_filter_key for [{album_property_key}] appending value [{curr_value}]")
        # avoid to re-add the same conditions
        if __condition_exists(condition_list=condition_list, key=album_property_key, value=curr_value):
            msgproc.log(f"handler_album_browse_filter_key skipping [{album_property_key}]:[{curr_value}], would be repeated")
            continue
        identifier: ItemIdentifier = ItemIdentifier(
            ElementType.ALBUM_BROWSE_FILTER_VALUE.element_name,
            encode_value_holder(value=curr_value))
        identifier.set(ItemIdentifierKey.ALBUM_BROWSE_FILTER_KEY, album_property_key)
        identifier.set(ItemIdentifierKey.ALBUM_BROWSE_SELECTION_LIST, encoded_list)
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        entry: dict[str, any] = upmplgutils.direntry(
            id=id,
            pid=objid,
            title=f"{curr_value} [{match_count_by_value[curr_value]}]" if curr_value else f"[None] [{none_entry_size}]")
        # get cover art, special case for None
        curr_album_id: str = (none_random_album_id if curr_value is None
                              else (random_matching_album_id_by_value[curr_value]
                                    if curr_value in random_matching_album_id_by_value
                                    else None))
        # do we have it loaded?
        random_album_metadata: AlbumMetadata = (random_album_metadata_dict[curr_album_id]
                                                if curr_album_id in random_album_metadata_dict
                                                else None)
        # set cover art
        if random_album_metadata:
            upnp_util.set_album_art_from_uri(
                album_art_uri=subsonic_util.build_cover_art_url(item_id=random_album_metadata.album_cover_art),
                target=entry)
        entries.append(entry)
    return entries


def property_key_in_filter_list(property_key: str, filter_list: list[list[str]]) -> bool:
    curr: list[str]
    for curr in filter_list if filter_list else []:
        # first in list is the key
        msgproc.log(f"property_key_in_filter_list key [{curr[0]}]")
        if curr[0] == property_key:
            return True
    return False


def __any_none_condition_for_key(condition_list: list[AlbumPropertyKeyValue], property_key: str) -> bool:
    curr: AlbumPropertyKeyValue
    conditions_by_key: list[AlbumPropertyKeyValue] = list(filter(
        lambda x: x.key == property_key,
        condition_list if condition_list else []))
    for curr in conditions_by_key:
        if curr.value is None:
            return True
    return False


def handler_album_browse_filter_value(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    encoded_filter_value: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    filter_value: str = decode_value_holder(encoded_filter_value)
    filter_key: str = item_identifier.get(ItemIdentifierKey.ALBUM_BROWSE_FILTER_KEY)
    if True:
        msgproc.log(f"handler_album_browse_filter_value filter_key [{filter_key}] "
                    f"filter_value [{encoded_filter_value}] -> [{filter_value}]")
    msgproc.log(f"handler_album_browse_filter_value [{filter_key}] [{filter_value}]")
    current_selection_list_str: str = item_identifier.get(ItemIdentifierKey.ALBUM_BROWSE_SELECTION_LIST)
    current_selection_list: list[list[str]] = []
    if current_selection_list_str:
        # decode
        lst: list[tuple[str, str]] = json.loads(codec.base64_decode(current_selection_list_str))
        current_selection_list.extend(lst)
    # add current selection
    current_selection_list.append([filter_key, filter_value])
    # rebuild filters
    encoded_list: str = codec.base64_encode(json.dumps(current_selection_list))
    msgproc.log(f"filter list [{current_selection_list}] encodes to [{encoded_list}]")
    condition_list: list[AlbumPropertyKeyValue] = []
    curr_selection: list[str]
    for curr_selection in current_selection_list if current_selection_list else []:
        condition: AlbumPropertyKeyValue = AlbumPropertyKeyValue(
            key=curr_selection[0],
            value=curr_selection[1])
        condition_list.append(condition)
    full_dataset: AlbumPropertyDataset = __get_album_property_dataset()
    # shrink dataset.
    dataset_processor: AlbumPropertyDatasetProcessor = AlbumPropertyDatasetProcessor(dataset=full_dataset)
    dataset: AlbumPropertyDataset = dataset_processor.apply_filters(filter_list=condition_list)
    matching_albums: list[str] = dataset.album_id_list
    msgproc.log(f"dataset with size [{full_dataset.size}] -> "
                f"filtered to [{dataset.size}] "
                f"albums [{len(matching_albums)}]")
    dataset_keys: list[str] = dataset.keys
    msgproc.log(f"dataset keys [{dataset_keys}]")
    key_list: list[str] = []
    curr: AlbumPropertyKey
    for curr in AlbumPropertyKey:
        curr_key: str = curr.property_key
        if curr_key not in dataset_keys:
            msgproc.log(f"handler_album_browse_filter_value property [{curr.display_value}] [{curr.property_key}] skipped")
            continue
        # values for key?
        if __any_none_condition_for_key(condition_list=condition_list, property_key=curr_key):
            msgproc.log(f"handler_album_browse_filter_value key [{curr_key}] already has a filter for None, skipping")
            continue
        # get values for key
        values: list[str] = dataset.get_values(key=curr_key)
        if len(values) > curr.max_items:
            msgproc.log(f"handler_album_browse_filter_value property [{curr.display_value}] [{curr.property_key}] "
                        f"skipped (too many values [{len(values)}], max is [{curr.max_items}])")
            continue
        if verbose:
            msgproc.log(f"handler_album_browse_filter_value values for [{curr_key}] -> [{values}]")
        # is there only one value, and this matches all items?
        valid_value_count: int = 0
        curr_value: str
        for curr_value in values if values else []:
            val_match_count: int = len(dataset.get_album_id_list_by_key_value(key=curr_key, value=curr_value))
            if val_match_count == len(matching_albums):
                if verbose:
                    msgproc.log(f"handler_album_browse_filter_value pair [{curr_key}]: [{curr_value}] "
                                "matches the entire dataset, skipping")
                continue
            if val_match_count > 0:
                if verbose:
                    msgproc.log(f"handler_album_browse_filter_value pair [{curr_key}]: [{curr_value}] "
                                f"matches [{val_match_count}] out of [{len(matching_albums)}]")
                valid_value_count += 1
            else:
                if verbose:
                    msgproc.log(f"handler_album_browse_filter_value pair [{curr_key}]: [{curr_value}] "
                                "does not match anything, skipping")
        if valid_value_count == 0:
            continue
        key_list.append(curr_key)
    msgproc.log(f"handler_album_browse_filter_value we should present [{key_list}]")
    property_key_list: list[AlbumPropertyKey] = list(map(lambda x: get_album_property_key(x), key_list))
    curr_album_property_key: AlbumPropertyKey
    # load some albums just to get cover arts, also considering one for "matching albums"
    random_album_id_list: list[str] = (random.choices(matching_albums, k=len(property_key_list) + 1)
                                       if len(matching_albums) > 0
                                       else [])
    random_album_metadata_dict: dict[str, AlbumMetadata] = (persistence.get_album_metadata_dict(album_id_list=random_album_id_list)
                                                            if len(random_album_id_list) > 0
                                                            else {})
    for curr_album_property_key in AlbumPropertyKey:
        if curr_album_property_key not in property_key_list:
            continue
        values_by_key: list[str] = dataset.get_values(key=curr_album_property_key.property_key)
        msgproc.log(f"handler_album_browse_filter_value presenting [{curr_album_property_key.display_value}] "
                    f"([{curr_album_property_key.property_key}]) for [{len(values_by_key)}] values")
        identifier: ItemIdentifier = ItemIdentifier(
            ElementType.ALBUM_BROWSE_FILTER_KEY.element_name,
            curr_album_property_key.property_key)
        identifier.set(ItemIdentifierKey.ALBUM_BROWSE_SELECTION_LIST, encoded_list)
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        # size by key?
        property_size_to_display: int = len(values_by_key)
        # none will show up?
        none_needed: bool = dataset.get_album_id_count_for_key(key=curr_album_property_key.property_key) < dataset.album_id_count
        if none_needed:
            #  [None] will be displayed, so we increment counter
            property_size_to_display += 1
        # strip already set
        curr_condition: AlbumPropertyKeyValue
        for curr_condition in condition_list:
            if not curr_condition.key == curr_album_property_key.property_key:
                continue
            if curr_condition.value and curr_condition.value in values_by_key:
                property_size_to_display -= 1
        entry: dict[str, any] = upmplgutils.direntry(
            id=id,
            pid=objid,
            title=f"{curr_album_property_key.display_value} [{property_size_to_display}]")
        # set cover art if one is available
        random_album_id: str = random_album_id_list.pop(0) if len(random_album_id_list) > 0 else None
        random_album: AlbumMetadata = (random_album_metadata_dict[random_album_id]
                                       if random_album_id and random_album_id in random_album_metadata_dict
                                       else None)
        if random_album:
            upnp_util.set_album_art_from_uri(
                album_art_uri=subsonic_util.build_cover_art_url(item_id=random_album.album_cover_art),
                target=entry)
        entries.append(entry)
    # Add matching albums entry
    msgproc.log(f"Creating matching albums entry with value [{current_selection_list_str}]")
    matching_identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_BROWSE_MATCHING_ALBUMS.element_name,
        encoded_list)
    matching_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(matching_identifier))
    matching_entry: dict[str, any] = upmplgutils.direntry(
        id=matching_id,
        pid=objid,
        title=f"Matching albums [{len(matching_albums)}]")
    entries.append(matching_entry)
    random_album_id: str = random_album_id_list.pop(0) if len(random_album_id_list) > 0 else None
    random_album: AlbumMetadata = (random_album_metadata_dict[random_album_id]
                                   if random_album_id and random_album_id in random_album_metadata_dict
                                   else None)
    if random_album:
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=random_album.album_cover_art),
            target=matching_entry)
    return entries


def __sort_matching_album_list(album_metadata_list: list[AlbumMetadata]):
    # 1. Sort by the least important (DESC)
    album_metadata_list.sort(key=lambda x: x.album_release_date_str, reverse=True)
    # 2. Sort by the second priority (DESC)
    album_metadata_list.sort(key=lambda x: x.album_original_release_date_str, reverse=True)
    # 3. Sort by the highest priority (ASC)
    album_metadata_list.sort(key=lambda x: x.album_display_artist)


def handler_element_matching_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    # filter_value_encoded: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    current_selection_list_str: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    if verbose:
        msgproc.log(f"handler_element_matching_albums current_selection_list_str [{current_selection_list_str}]")
    current_selection_list: list[list[str]] = []
    if current_selection_list_str:
        # decode
        lst: list[tuple[str, str]] = json.loads(codec.base64_decode(current_selection_list_str))
        current_selection_list.extend(lst)
    if verbose:
        msgproc.log(f"handler_element_matching_albums current_selection_list [{current_selection_list}] "
                    f"offset [{offset}]")
    condition_list: list[AlbumPropertyKeyValue] = []
    curr_selection: list[str]
    for curr_selection in current_selection_list if current_selection_list else []:
        condition: AlbumPropertyKeyValue = AlbumPropertyKeyValue(
            key=curr_selection[0],
            value=curr_selection[1])
        condition_list.append(condition)
    full_dataset: AlbumPropertyDataset = __get_album_property_dataset()
    # shrink dataset.
    dataset_processor: AlbumPropertyDatasetProcessor = AlbumPropertyDatasetProcessor(dataset=full_dataset)
    dataset: AlbumPropertyDataset = dataset_processor.apply_filters(filter_list=condition_list)
    matching_albums: list[str] = dataset.album_id_list
    matching_album_count: int = len(matching_albums)
    msgproc.log(f"handler_element_matching_albums matching_album_count [{matching_album_count}]")
    # load albums
    album_metadata_dict: dict[str, AlbumMetadata] = (persistence.get_album_metadata_dict(album_id_list=matching_albums)
                                                     if matching_album_count > 0
                                                     else {})
    msgproc.log(f"handler_element_matching_albums loaded {len(album_metadata_dict)} albums")
    # create a list from dict
    loaded_albums: list[AlbumMetadata] = list(album_metadata_dict.values())
    msgproc.log(f"handler_element_matching_albums created list of [{len(loaded_albums)}] albums")
    # apply sorting.
    # sorted_albums: list[AlbumMetadata] = loaded_albums
    __sort_matching_album_list(loaded_albums)
    num_albums_to_display: int = config.get_config_param_as_int(constants.ConfigParam.ITEMS_PER_PAGE)
    # get slice?
    to_show: list[Album] = None
    if len(loaded_albums) > offset:
        end_offset: int = min(len(loaded_albums), offset + num_albums_to_display + 1)
        to_show: list[AlbumMetadata] = loaded_albums[offset:end_offset]
        msgproc.log(f"handler_element_matching_albums to_show [{len(to_show)}] albums")
    else:
        msgproc.log("handler_element_matching_albums nothing to show")
        to_show = []
    to_display: list[AlbumMetadata] = (to_show if len(to_show) <= num_albums_to_display
                                       else to_show[0:config.get_config_param_as_int(constants.ConfigParam.ITEMS_PER_PAGE)])
    navigable: bool = not config.get_config_param_as_bool(constants.ConfigParam.DISABLE_NAVIGABLE_ALBUM)
    curr: AlbumMetadata
    for curr in to_display:
        album_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.NAVIGABLE_ALBUM.element_name if navigable else ElementType.ALBUM.element_name,
            curr.album_id)
        album_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(album_identifier))
        album_entry: dict[str, any] = upmplgutils.direntry(
            id=album_id,
            pid=objid,
            title=curr.album_name)
        upnp_util.set_artist(artist=curr.album_display_artist, target=album_entry)
        if not navigable:
            upnp_util.set_class_album(target=album_entry)
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=curr.album_cover_art),
            target=album_entry)
        subsonic_util.set_album_metadata_by_metadata_only(
            album_metadata=curr,
            target=album_entry)
        entries.append(album_entry)
    # next if needed?
    if len(to_show) == num_albums_to_display + 1:
        next_album: AlbumMetadata = to_show[len(to_show) - 1]
        next_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.ALBUM_BROWSE_MATCHING_ALBUMS.element_name,
            current_selection_list_str)
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + num_albums_to_display)
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            id=next_id,
            pid=objid,
            title="Next")
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=next_album.album_cover_art),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_next_random_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return _get_random_songs(objid, item_identifier, entries)


def handler_element_song_entry_song(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    msgproc.log("handler_element_song_entry_song start")
    song_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_element_song_entry_song start song_id {song_id}")
    song: Song = connector_provider.get().getSong(song_id).getObj()
    if song:
        entries.append(entry_creator.song_to_entry(
            objid=objid,
            song=song))
    return entries


def handler_radio(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    msgproc.log("handler_radio start")
    iid: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_radio iid {iid}")
    res: Response[SimilarSongs] = connector_provider.get().getSimilarSongs(iid)
    if not res.isOk():
        raise Exception(f"Cannot get similar songs for iid {iid}")
    song: Song
    for song in res.getObj().getSongs():
        entries.append(_song_to_song_entry(
            objid=objid,
            song=song,
            song_as_entry=True))
    return entries


def handler_radio_song_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    msgproc.log("handler_radio_song_list start")
    iid: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_radio_song_list iid {iid}")
    res: Response[SimilarSongs] = connector_provider.get().getSimilarSongs(iid)
    if not res.isOk():
        raise Exception(f"Cannot get similar songs for iid {iid}")
    song: Song
    cnt: int = 0
    options: dict[str, any] = {}
    for song in res.getObj().getSongs():
        cnt += 1
        option_util.set_option(
            options=options,
            option_key=OptionKey.FORCE_TRACK_NUMBER,
            option_value=cnt)
        song_entry: dict[str, any] = entry_creator.song_to_entry(
            objid=objid,
            song=song,
            options=options)
        entries.append(song_entry)
    return entries


def handler_element_artist_top_songs_navigable(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return _handler_element_artist_top_songs_common(
        objid=objid,
        item_identifier=item_identifier,
        list_mode=False,
        entries=entries)


def handler_element_artist_top_songs_song_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return _handler_element_artist_top_songs_common(
        objid=objid,
        item_identifier=item_identifier,
        list_mode=True,
        entries=entries)


def _handler_element_artist_top_songs_common(
        objid,
        item_identifier: ItemIdentifier,
        list_mode: bool,
        entries: list) -> list:
    msgproc.log("_handler_element_artist_top_songs_common start")
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_artist_top_songs_common artist_id {artist_id}")
    res: Response[Artist] = connector_provider.get().getArtist(artist_id)
    if not res.isOk():
        raise Exception(f"Cannot find artist by artist_id {artist_id}")
    artist: Artist = res.getObj()
    top_song_res: Response[TopSongs] = connector_provider.get().getTopSongs(artist.getName())
    if not top_song_res.isOk():
        raise Exception(f"Cannot get top songs for artist {artist.getName()}")
    song: Song
    cnt: int = 0
    options: dict[str, any] = {}
    for song in top_song_res.getObj().getSongs():
        cnt += 1
        if list_mode:
            option_util.set_option(
                options=options,
                option_key=OptionKey.FORCE_TRACK_NUMBER,
                option_value=cnt)
            song_entry: dict[str, any] = entry_creator.song_to_entry(
                objid=objid,
                song=song,
                options=options)
            entries.append(song_entry)
        else:
            entries.append(_song_to_song_entry(
                objid=objid,
                song=song,
                song_as_entry=True))
    return entries


def _song_to_song_entry(objid, song: Song, song_as_entry: bool) -> upmplgutils.direntry:
    name: str = song.getTitle()
    song_artist: str = song.getArtist()
    if song_artist:
        name = f"{name} [{song_artist}]"
    song_year: str = song.getYear()
    if song_year:
        name = f"{name} [{song_year}]"
    song_album: str = song.getAlbum()
    if song_album:
        name = f"{name} [{song_album}]"
    song_cover_art: str = song.getCoverArt()
    select_element: ElementType = (
        ElementType.SONG_ENTRY_NAVIGABLE if song_as_entry else
        ElementType.SONG_ENTRY_THE_SONG)
    identifier: ItemIdentifier = ItemIdentifier(
        select_element.element_name,
        song.getId())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, name)
    upnp_util.set_album_art_from_uri(
        album_art_uri=subsonic_util.build_cover_art_url(item_id=song_cover_art),
        target=entry)
    entry['upnp:album'] = song.getAlbum()
    upnp_util.set_artist(
        artist=subsonic_util.get_song_display_artist(song=song),
        target=entry)
    upnp_util.set_track_number(track_number=song.getTrack(), target=entry)
    subsonic_util.set_song_metadata(
        song=song,
        target=entry)
    return entry


def handler_element_song_entry(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    msgproc.log("handler_element_song_entry start")
    song_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_element_song_entry start song_id {song_id}")
    song: Song = connector_provider.get().getSong(song_id).getObj()
    song_identifier: ItemIdentifier = ItemIdentifier(ElementType.SONG_ENTRY_THE_SONG.element_name, song_id)
    song_entry_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(song_identifier))
    song_entry = upmplgutils.direntry(song_entry_id, objid, "Song")
    upnp_util.set_album_art_from_uri(
        album_art_uri=subsonic_util.build_cover_art_url(item_id=song.getCoverArt()),
        target=song_entry)
    entries.append(song_entry)
    msgproc.log(f"handler_element_song_entry start song_id {song_id} go on with album")
    album: Album = subsonic_util.try_get_album(album_id=song.getAlbumId(), propagate_fail=True)
    options: dict[str, any] = dict()
    option_util.set_option(
        options=options,
        option_key=OptionKey.FORCE_RELOAD_ALBUM_QUALITY_INFO,
        option_value=True)
    entries.append(entry_creator.album_to_entry(
        objid=objid,
        album=album,
        options=options))
    artist_id: str = song.getArtistId() if song.getArtistId() else album.getArtistId()
    if not artist_id:
        msgproc.log(f"handler_element_song_entry artist_id not found for "
                    f"song_id {song.getId()} album_id {song.getAlbumId()} "
                    f"artist {song.getArtist()}")
    if artist_id:
        msgproc.log(f"handler_element_song_entry searching artist for song_id {song.getId()} "
                    f"artist {song.getArtist()} artist_id {artist_id}")
        artist_response: Response[Artist] = connector_provider.get().getArtist(artist_id)
        artist: Artist = artist_response.getObj() if artist_response.isOk() else None
        if not artist:
            msgproc.log(f"handler_element_song_entry could not find artist for "
                        f"song_id {song.getId()} artist {song.getArtist()} "
                        f"artist_id {artist_id}")
        if artist:
            entries.append(entry_creator.artist_to_entry(
                objid=objid,
                artist=artist))
    return entries


def _get_favourite_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    song_as_entry: bool = item_identifier.get(ItemIdentifierKey.SONG_AS_ENTRY, True)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    response: Response[Starred] = request_cache.get_starred()
    if not response.isOk():
        raise Exception("Cannot retrieve starred items")
    song_list: list[Song] = response.getObj().getSongs()
    need_next: bool = song_list and len(song_list) > (offset + config.get_items_per_page())
    song_slice: list[Song] = song_list[offset:min(len(song_list), offset + config.get_items_per_page())]
    next_song: Song = song_list[offset + config.get_items_per_page()] if need_next else None
    current_song: Song
    for current_song in song_slice if song_slice and len(song_slice) > 0 else []:
        entry: dict[str, any] = _song_to_song_entry(
            objid=objid,
            song=current_song,
            song_as_entry=song_as_entry)
        entries.append(entry)
    if need_next:
        next_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.TAG.element_name,
            TagType.FAVORITE_SONGS_LIST.tag_name)
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.get_items_per_page())
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(next_song.getCoverArt()),
            target=next_entry)
        entries.append(next_entry)
    return entries


def _get_random_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    song_as_entry: bool = item_identifier.get(ItemIdentifierKey.SONG_AS_ENTRY, True)
    req_song_count: int = config.get_items_per_page() + 1
    response: Response[RandomSongs] = connector_provider.get().getRandomSongs(size=req_song_count)
    if not response.isOk():
        raise Exception("Cannot get random songs")
    song_list: list[Song] = response.getObj().getSongs()
    next_song: Song = song_list[len(song_list) - 1] if len(song_list) == req_song_count else None
    to_display: list[Song] = song_list[0:config.get_items_per_page()] if next_song else song_list
    song: Song
    for song in to_display:
        song_entry = _song_to_song_entry(
            objid=objid,
            song=song,
            song_as_entry=song_as_entry)
        entries.append(song_entry)
    if next_song:
        # no offset, so we always add next
        next_identifier: ItemIdentifier = ItemIdentifier(ElementType.NEXT_RANDOM_SONGS.element_name, "some_random_song")
        next_identifier.set(ItemIdentifierKey.SONG_AS_ENTRY, song_as_entry)
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            id=next_id,
            pid=objid,
            title="Next")
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=next_song.getCoverArt()),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_tag_genres(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return create_entries_for_genres(objid, entries)


def _genre_add_artists_node(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    genre: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_genre_add_artists_node genre {genre}")
    identifier: ItemIdentifier = ItemIdentifier(ElementType.GENRE_ARTIST_LIST.element_name, genre)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    name: str = "Artists"  # TODO parametrize maybe?
    artists_entry = upmplgutils.direntry(id, objid, name)
    cover_art: str = get_random_art_by_genre(genre)
    if cover_art:
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=cover_art),
            target=artists_entry)
    entries.append(artists_entry)
    return entries


def _genre_add_albums_node(
        objid,
        item_identifier: ItemIdentifier,
        offset: int,
        entries: list) -> list:
    genre: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_genre_add_albums_node genre {genre}")
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ALBUM_LIST.element_name,
        genre)
    # identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    identifier.set(ItemIdentifierKey.OFFSET, offset)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    name: str = "Albums" if offset == 0 else "Next"  # TODO parametrize maybe?
    albums_entry = upmplgutils.direntry(id, objid, name)
    if offset == 0:
        art_id: str = get_random_art_by_genre(genre)
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=art_id),
            target=albums_entry)
    entries.append(albums_entry)
    return entries


def handler_element_genre(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    # add nodes for albums by genre
    msgproc.log("handler_element_genre")
    entries = _genre_add_artists_node(objid, item_identifier, entries)
    entries = _genre_add_albums_node(
        objid=objid,
        item_identifier=item_identifier,
        offset=0,
        entries=entries)
    return entries


def handler_element_genre_artists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    genre: str = item_identifier.get(ItemIdentifierKey.GENRE_NAME)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    msgproc.log(f"handler_element_genre_artists for [{genre}] offset [{offset}] ...")
    # get all albums by genre and collect a set of artists
    display_size: int = config.get_config_param_as_int(constants.ConfigParam.MAX_ARTISTS_PER_PAGE)
    artist_id_list: list[ArtistIdNameCoverArt] = subsonic_util.load_artists_by_genre(
        genre=genre,
        artist_offset=offset,
        max_artists=display_size + 1)
    msgproc.log(f"handler_element_genre_artists got {len(artist_id_list)} from offset [{offset}] "
                f"display_size [{display_size}] ...")
    list_len: int = len(artist_id_list) if artist_id_list else 0
    to_display: list[ArtistIdNameCoverArt] = artist_id_list[0:min(list_len, display_size)] if list_len > 0 else []
    next_artist: ArtistIdNameCoverArt = artist_id_list[display_size] if list_len == display_size + 1 else None
    msgproc.log(f"handler_element_genre_artists for [{genre}] initial offset [{offset}] "
                f"to_display [{len(to_display)}] "
                f"next [{'yes' if next_artist is not None else 'no'}] ...")
    # present the list of artists
    item_count: int = 0
    needs_next: bool = False
    current: ArtistIdNameCoverArt
    for current in to_display:
        # load artist if it has an id
        if current.artist_id:
            artist_entry: dict[str, any] = entry_creator.genre_artist_to_entry(
                objid=objid,
                genre=genre,
                artist_id=current.artist_id,
                artist_name=current.artist_name,
                album_cover_art=current.cover_art)
            entries.append(artist_entry)
            # was cover art set?
            entry_art_uri: str = upnp_util.get_album_art_uri(entry=artist_entry)
            if not entry_art_uri:
                # fallback to album art
                msgproc.log(f"handler_element_genre_artists cover for [{current.artist_name}] was not set, "
                            f"falling back to album cover art [{current.cover_art}]")
                upnp_util.set_album_art_from_uri(
                    album_art_uri=subsonic_util.build_cover_art_url(item_id=current.cover_art),
                    target=artist_entry)
            item_count += 1
        else:
            msgproc.log(f"Skipping [{current.artist_name}] as there is no id")
    if len(artist_id_list) == config.get_config_param_as_int(constants.ConfigParam.MAX_ARTISTS_PER_PAGE) + 1:
        # we need the next button
        msgproc.log(f"handler_element_genre_artists genre [{genre}] initial offset [{offset}]: next is needed")
        needs_next = True
    if needs_next:
        next_offset: int = offset + config.get_config_param_as_int(constants.ConfigParam.MAX_ARTISTS_PER_PAGE)
        msgproc.log(f"handler_element_genre_artists for [{genre}] next offset is [{next_offset}] ...")
        # add the next button
        next_identifier: ItemIdentifier = ItemIdentifier(ElementType.GENRE_ARTIST_LIST.element_name, genre)
        next_identifier.set(ItemIdentifierKey.OFFSET, next_offset)
        next_identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        # use next_artist for cover art
        next_cover_art_uri: str = art_retriever.get_album_cover_art_url_by_artist_id(artist_id=next_artist.artist_id)
        upnp_util.set_album_art_from_uri(album_art_uri=next_cover_art_uri, target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_genre_artist_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    genre_name: str = item_identifier.get(ItemIdentifierKey.GENRE_NAME)
    artist_res: Response[Artist] = connector_provider.get().getArtist(artist_id)
    if not artist_res.isOk():
        raise Exception(f"Cannot get artist for id {artist_id}")
    artist: Artist = artist_res.getObj()
    album_list: list[Album] = subsonic_util.get_album_list_by_artist_genre(artist, genre_name)
    need_next: bool = album_list and len(album_list) > (offset + config.get_items_per_page())
    album_slice: list[Album] = album_list[offset:min(len(album_list), offset + config.get_items_per_page())]
    current_album: Album
    counter: int = offset
    for current_album in album_slice if album_slice and len(album_slice) > 0 else []:
        counter += 1
        options: dict[str, any] = {}
        if config.get_config_param_as_bool(constants.ConfigParam.PREPEND_NUMBER_IN_ALBUM_LIST):
            option_util.set_option(
                options=options,
                option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE,
                option_value=counter)
        option_util.set_option(
            options=options,
            option_key=OptionKey.APPEND_ARTIST_IN_ALBUM_TITLE,
            option_value=False)
        entry: dict[str, any] = entry_creator.album_to_entry(
            objid=objid,
            album=current_album,
            options=options)
        entries.append(entry)
    if need_next:
        next_identifier: ItemIdentifier = ItemIdentifier(ElementType.GENRE_ARTIST_ALBUMS.element_name, artist_id)
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.get_items_per_page())
        next_identifier.set(ItemIdentifierKey.GENRE_NAME, genre_name)
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        entries.append(next_entry)
    return entries


def handler_element_genre_album_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    msgproc.log("handler_element_genre_album_list")
    genre: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET)
    msgproc.log(f"handler_element_genre_album_list genre {genre} offset {offset}")
    album_list_response: Response[AlbumList] = connector_provider.get().getAlbumList(
        ltype=ListType.BY_GENRE,
        genre=genre,
        offset=offset,
        size=config.get_items_per_page() + 1)
    if not album_list_response.isOk():
        return entries
    album_list: list[Album] = album_list_response.getObj().getAlbums()
    msgproc.log(f"got {len(album_list)} albums for genre {genre} from offset {offset}")
    counter: int = offset
    current_album: Album
    to_show: list[Album] = (album_list[0:min(len(album_list), config.get_items_per_page())]
                            if len(album_list) > 0 else [])
    for current_album in to_show:
        counter += 1
        options: dict[str, any] = dict()
        if config.get_config_param_as_bool(constants.ConfigParam.PREPEND_NUMBER_IN_ALBUM_LIST):
            option_util.set_option(
                options=options,
                option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE,
                option_value=counter)
        if config.get_config_param_as_bool(constants.ConfigParam.DISABLE_NAVIGABLE_ALBUM):
            entries.append(entry_creator.album_to_entry(
                objid=objid,
                album=current_album,
                options=options))
        else:
            entries.append(entry_creator.album_to_navigable_entry(
                objid=objid,
                album=current_album,
                options=options))
    if len(album_list) == (config.get_items_per_page() + 1):
        # create next button
        next_album: Album = album_list[config.get_items_per_page()]
        next_identifier: ItemIdentifier = ItemIdentifier(ElementType.GENRE_ALBUM_LIST.element_name, genre)
        # next_identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.get_items_per_page())
        next_id: str = identifier_util.create_objid(
            objid,
            identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        cover_art: str = next_album.getCoverArt()
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=cover_art),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handle_tag_all_artists_unsorted_by_role(
        objid,
        item_identifier: ItemIdentifier,
        tag_type: TagType,
        entries: list,
        role_filter: Callable[[Artist], True] = None) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    initial_offset: int = offset
    req_count: int = config.get_config_param_as_int(constants.ConfigParam.ITEMS_PER_PAGE)
    selection: list[Artist] = []
    exit_loop: bool = False
    # search_size: int = (req_count + 1) * 2
    search_size: int = 100
    while not exit_loop:
        msgproc.log(f"Searching [{search_size}] artists from offset [{offset}] ...")
        search_result: SearchResult = connector_provider.get().search(
            query="",
            artistCount=search_size,
            artistOffset=offset)
        artist_list: list[Artists] = search_result.getArtists()
        msgproc.log(f"Search for [{search_size}] artists returned [{len(artist_list)}] artists.")
        current_artist: Artist
        for current_artist in artist_list:
            increment_offset: bool = True
            if not role_filter or role_filter(current_artist):
                selection.append(current_artist)
                if len(selection) == (req_count + 1):
                    # enough filtered artists have been collected collected
                    exit_loop = True
                    # this artist is for the "next" entry, so we don't increment the offset
                    # because next page must start from this artist
                    increment_offset = False
                    break
            if increment_offset:
                offset += 1
        if not exit_loop and (len(artist_list) < (search_size)):
            # no data
            msgproc.log(f"Retrieved less than [{search_size}] artists, finished.")
            exit_loop = True
    next_artist: Artist = selection[len(selection) - 1] if (len(selection) == (req_count + 1)) else None
    to_display: list[Artist] = selection if not next_artist else selection[0:len(selection) - 1]
    msgproc.log(f"Showing [{len(to_display)}] "
                f"artists from initial offset [{initial_offset}] "
                f"to offset [{offset}] "
                f"next available [{next_artist is not None}]")
    current: Artist
    for current in to_display:
        if verbose:
            msgproc.log(f"handle_tag_all_artists_unsorted_by_role showing [{current.getName()}] ...")
        entries.append(entry_creator.artist_to_entry(
            objid=objid,
            artist=current))
    if next_artist:
        if verbose:
            msgproc.log("handle_tag_all_artists_unsorted_by_role creating entry for "
                        f"next page using artist_id [{next_artist.getId()}] ...")
        next_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.TAG.element_name,
            tag_type.tag_name)
        next_identifier.set(ItemIdentifierKey.OFFSET, offset)
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        # image
        next_album_art_uri: str = art_retriever.get_album_cover_art_uri_by_artist(artist=next_artist)
        upnp_util.set_album_art_from_uri(
            album_art_uri=next_album_art_uri,
            target=next_entry)
        entries.append(next_entry)
        if verbose:
            msgproc.log("handle_tag_all_artists_unsorted_by_role added entry for next page"
                        f" using artist_id [{next_artist.getId()}]")
    if verbose:
        msgproc.log("handle_tag_all_artists_unsorted_by_role finished creating entries.")
    return entries


def handler_tag_all_album_artists_unsorted(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handle_tag_all_artists_unsorted_by_role(
        objid=objid,
        item_identifier=item_identifier,
        tag_type=TagType.ALL_ALBUM_ARTISTS_UNSORTED,
        role_filter=lambda a: constants.RoleName.ALBUM_ARTIST.value in subsonic_util.get_artist_roles(a),
        entries=entries)


def handler_tag_all_composers_unsorted(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handle_tag_all_artists_unsorted_by_role(
        objid=objid,
        item_identifier=item_identifier,
        tag_type=TagType.ALL_COMPOSERS_UNSORTED,
        role_filter=lambda a: constants.RoleName.COMPOSER.value in subsonic_util.get_artist_roles(a),
        entries=entries)


def handler_tag_all_conductors_unsorted(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handle_tag_all_artists_unsorted_by_role(
        objid=objid,
        item_identifier=item_identifier,
        tag_type=TagType.ALL_CONDUCTORS_UNSORTED,
        role_filter=lambda a: constants.RoleName.CONDUCTOR.value in subsonic_util.get_artist_roles(a),
        entries=entries)


def handler_tag_all_artists_unsorted(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return handle_tag_all_artists_unsorted_by_role(
        objid=objid,
        item_identifier=item_identifier,
        tag_type=TagType.ALL_ARTISTS_UNSORTED,
        entries=entries)


def handler_tag_artist_roles(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    roles: list[persistence.ArtistRoleEntry] = persistence.get_artist_roles()
    role_entry: persistence.ArtistRoleEntry
    for role_entry in roles if roles else []:
        if verbose:
            msgproc.log(f"handler_tag_artist_roles should add [{role_entry.artist_role}] "
                        f"artist [{role_entry.random_artist_id}] [{role_entry.random_artist_name}] "
                        f"cover_art [{role_entry.random_artist_cover_art}]")
        identifier: ItemIdentifier = ItemIdentifier(
            ElementType.ARTIST_ROLE.element_name,
            role_entry.artist_role)
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        entry: dict[str, any] = upmplgutils.direntry(id=id, pid=objid, title=role_entry.artist_role.capitalize())
        artist_cover_art: str = role_entry.random_artist_cover_art
        if not artist_cover_art:
            if verbose:
                msgproc.log(f"handler_tag_artist_roles querying db for a cover art "
                            f"for role [{role_entry.artist_role}] using random "
                            f"artist [{role_entry.random_artist_id}] [{role_entry.random_artist_name}]")
            artist_cover_art = art_retriever.get_album_cover_art_by_artist_id(
                artist_id=role_entry.random_artist_id,
                skip_artist_metadata_cache=True)
        if artist_cover_art:
            upnp_util.set_album_art_from_uri(
                album_art_uri=subsonic_util.build_cover_art_url(item_id=artist_cover_art),
                target=entry)
        entries.append(entry)
    return entries


def handler_tag_all_artists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    # all album artists, paginated -> no skip art
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    options: dict[str, any] = dict()
    option_util.set_option(
        options=options,
        option_key=OptionKey.SKIP_ART,
        option_value=False)
    option_util.set_option(
        options=options,
        option_key=OptionKey.OFFSET,
        option_value=offset)
    return __load_artists(
        objid=objid,
        tag=TagType.ALL_ARTISTS,
        entries=entries,
        options=options)


def handler_tag_favourite_artists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    response: Response[Starred] = connector_provider.get().getStarred()
    artist_list: list[Artist] = response.getObj().getArtists()
    need_next: bool = artist_list and len(artist_list) > (offset + config.get_items_per_page())
    artist_slice: list[Artist] = artist_list[offset:min(len(artist_list), offset + config.get_items_per_page())]
    current_artist: Artist
    for current_artist in artist_slice if artist_slice and len(artist_slice) > 0 else []:
        entry: dict[str, any] = entry_creator.artist_to_entry(
            objid=objid,
            artist=current_artist)
        entries.append(entry)
    if need_next:
        next_artist: Artist = artist_list[offset + config.get_items_per_page()]
        next_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.TAG.element_name,
            TagType.FAVORITE_ARTISTS.tag_name)
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.get_items_per_page())
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        # image
        next_album_art_uri: str = art_retriever.get_album_cover_art_uri_by_artist(artist=next_artist)
        upnp_util.set_album_art_from_uri(
            album_art_uri=next_album_art_uri,
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_tag_all_artists_indexed(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    options: dict[str, any] = dict()
    return _create_list_of_artist_initials(objid, entries, options=options)


def handler_tag_playlists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return _create_list_of_playlist(objid, entries)


def handler_tag_internet_radios(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return _create_list_of_internet_radio(objid, entries)


def handler_element_playlist(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    playlist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    return _create_list_of_playlist_entries(objid, playlist_id, entries)


def handler_element_artists_by_initial(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    encoded_artist_initial: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist_initial: str = codec.base64_decode(encoded_artist_initial)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    # load album artists only flag from identifier and put in options
    options: dict[str, any] = dict()
    option_util.set_option(
        options=options,
        option_key=OptionKey.OFFSET,
        option_value=offset)
    entries = __load_artists_by_initial(
        objid=objid,
        artist_initial=artist_initial,
        element_type=ElementType.ARTIST_BY_INITIAL,
        entries=entries,
        options=options)
    return entries


def handler_element_artist_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    release_types: str = item_identifier.get(ItemIdentifierKey.ALBUM_RELEASE_TYPE, "")
    msgproc.log(f"handler_element_artist_albums artist_id {artist_id} "
                f"release_types [{release_types}] "
                f"items per page [{config.get_items_per_page()}] "
                f"offset [{offset}]")
    album_list: list[Album]
    try:
        album_list = _load_albums_by_artist(
            artist_id,
            subsonic_util.AlbumReleaseTypes([release_types]) if release_types else None)
    except Exception as ex:
        msgproc.log(f"Cannot get albums for artistId {artist_id} [{type(ex)}] [{ex}]")
        album_list = []
    if verbose:
        msgproc.log(f"handler_element_artist_albums artist_id {artist_id} found {len(album_list)} albums")
    # sort albums by date ...
    subsonic_util.sort_albums_by_date(album_list)
    # next_needed: bool = len(album_list) > (config.get_items_per_page() + offset)
    # slice at offset
    at_offset: list[Album] = (album_list[offset:min(len(album_list), offset + config.get_items_per_page() + 1)]
                              if len(album_list) > offset else [])
    msgproc.log(f"handler_element_artist_albums at_offset length [{len(at_offset)}]")
    # to show?
    to_show: list[Album] = at_offset[0:min(config.get_items_per_page(), len(at_offset))]
    next_album: Album = at_offset[config.get_items_per_page()] if len(at_offset) > config.get_items_per_page() else None
    msgproc.log(f"handler_element_artist_albums artist_id {artist_id} "
                f"next_needed {next_album is not None} num_albums_to_show {len(to_show)}")
    # if len(to_show) == 0:
    #     # nothing to show
    #     return []
    entries = _albums_by_artist_to_entries(
        objid=objid,
        artist_id=artist_id,
        album_list=to_show,
        offset=offset,
        entries=entries)
    if verbose:
        msgproc.log(f"Found {len(entries)} albums for artist_id {artist_id}")
    if next_album is not None:
        next_identifier: ItemIdentifier = ItemIdentifier(ElementType.ARTIST_ALBUMS.element_name, artist_id)
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.get_items_per_page())
        next_id: str = identifier_util.create_objid(
            objid,
            identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        # next_album: Album = album_list[offset + num_albums_to_show]
        cover_art: str = next_album.getCoverArt()
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=cover_art),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_artist_appearances(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    # show artist appearances
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    if verbose:
        msgproc.log(f"handler_artist_appearances artist_id {artist_id} "
                    f"offset {offset}")
    # load artist
    artist: Artist = subsonic_util.try_get_artist(artist_id=artist_id)
    album_list: list[Album] = subsonic_util.get_artist_albums_as_appears_on(
        artist_id=artist_id,
        album_list=artist.getAlbumList(),
        opposite=False) if artist else []
    # sort albums by date ...
    subsonic_util.sort_albums_by_date(album_list)
    # slice at offset
    album_list = album_list[offset:min(offset + config.get_items_per_page() + 1, len(album_list))]
    next_album: Album = album_list[config.get_items_per_page()] if len(album_list) > config.get_items_per_page() else None
    to_show: list[Album] = album_list[0: min(config.get_items_per_page(), len(album_list))]
    if verbose:
        msgproc.log(f"handler_artist_appearances artist_id {artist_id} "
                    f"next_needed {next_album is not None} "
                    f"num_albums_to_show {len(to_show)}")
    entries = _albums_by_artist_to_entries(
        objid=objid,
        artist_id=artist_id,
        album_list=to_show,
        offset=offset,
        entries=entries)
    if verbose:
        msgproc.log(f"Found {len(entries)} albums for artist_id {artist_id}")
    if next_album:
        next_identifier: ItemIdentifier = ItemIdentifier(ElementType.ARTIST_APPEARANCES.element_name, artist_id)
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.get_items_per_page())
        next_id: str = identifier_util.create_objid(
            objid,
            identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        cover_art: str = next_album.getCoverArt()
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=cover_art),
            target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_artist_role(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    artist_role: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    roles_initials: list[persistence.ArtistRoleInitialEntry] = persistence.get_artist_role_initials(artist_role=artist_role)
    role_initial_entry: persistence.ArtistRoleInitialEntry
    for role_initial_entry in roles_initials if roles_initials else []:
        if verbose:
            msgproc.log(f"handler_element_artist_role for [{artist_role}] "
                        f"should add [{role_initial_entry.artist_initial}] "
                        f"artist [{role_initial_entry.random_artist_id}] [{role_initial_entry.random_artist_name}] "
                        f"cover_art [{role_initial_entry.random_artist_cover_art}]")
        identifier: ItemIdentifier = ItemIdentifier(
            ElementType.ARTIST_ROLE_INITIAL.element_name,
            role_initial_entry.artist_initial)
        identifier.set(key=ItemIdentifierKey.ARTIST_ROLE, value=artist_role)
        id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(identifier))
        entry: dict[str, any] = upmplgutils.direntry(id=id, pid=objid, title=role_initial_entry.artist_initial)
        artist_cover_art: str = role_initial_entry.random_artist_cover_art
        if not artist_cover_art:
            if verbose:
                msgproc.log(f"handler_element_artist_role querying db for a cover art "
                            f"for role [{artist_role}] using random "
                            f"artist [{role_initial_entry.random_artist_id}] [{role_initial_entry.random_artist_name}]")
            artist_cover_art = art_retriever.get_album_cover_art_by_artist_id(
                artist_id=role_initial_entry.random_artist_id,
                skip_artist_metadata_cache=True)
        if artist_cover_art:
            upnp_util.set_album_art_from_uri(
                album_art_uri=subsonic_util.build_cover_art_url(item_id=artist_cover_art),
                target=entry)
        entries.append(entry)
    return entries


def handler_element_artist_role_initial(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    artist_initial: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist_role: str = item_identifier.get(ItemIdentifierKey.ARTIST_ROLE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    if verbose:
        msgproc.log(f"handler_element_artist_role_initial role [{artist_role}] "
                    f"initial [{artist_initial}] "
                    f"offset [{offset}]")
    page_size: int = config.get_config_param_as_int(constants.ConfigParam.MAX_ARTISTS_PER_PAGE)
    artists: list[persistence.ArtistEntry] = persistence.get_artist_by_role_and_initial(
        artist_role=artist_role,
        initial=artist_initial,
        offset=offset,
        limit=page_size + 1)
    if verbose:
        msgproc.log(f"handler_element_artist_role_initial role [{artist_role}] "
                    f"initial [{artist_initial}] "
                    f"offset [{offset}] "
                    f"got [{len(artists)}] artists")
    cover_arts_by_artist_id: dict[str, str] = {}
    artist_id_list_missing_cover: list[str] = []
    # iterate all extracted artists
    curr_artist: persistence.ArtistEntry
    for curr_artist in artists:
        if curr_artist.artist_cover_art:
            # ok, store.
            cover_arts_by_artist_id[curr_artist.artist_id] = curr_artist.artist_cover_art
        else:
            # keep track of artist id with missing cover art
            artist_id_list_missing_cover.append(curr_artist.artist_id)
    if verbose:
        msgproc.log(f"handler_element_artist_role_initial missing [{len(artist_id_list_missing_cover)}] "
                    f"cover arts out of [{len(artists)}] "
                    f"missing [{artist_id_list_missing_cover}]")
    # see if we can get cover arts where missing
    cover_list_dict: dict[str, list[ArtistAlbumCoverArt]] = persistence.get_cover_art_list_by_artist_id_list(
        artist_id_list=artist_id_list_missing_cover)
    curr_artist_id_missing_cover: str
    for curr_artist_id_missing_cover in artist_id_list_missing_cover:
        # cover art list if available
        lst: list[ArtistAlbumCoverArt] = (cover_list_dict[curr_artist_id_missing_cover]
                                          if curr_artist_id_missing_cover in cover_list_dict
                                          else None)
        if lst is None or len(lst) == 0:
            if verbose:
                msgproc.log(f"handler_element_artist_role_initial still no cover art for [{curr_artist_id_missing_cover}]")
            continue
        # just select one and store it
        selected: ArtistAlbumCoverArt = persistence.choose_artist_album_cover_art(lst=lst)
        select_cover_art: str = selected.cover_art if selected else None
        if verbose:
            msgproc.log(f"handler_element_artist_role_initial artist_id [{curr_artist_id_missing_cover}] -> [{select_cover_art}]")
        cover_arts_by_artist_id[curr_artist_id_missing_cover] = select_cover_art
    initially_missing_cnt: int = len(artist_id_list_missing_cover)
    artist_id_list_missing_cover: list[str] = list(filter(lambda x: x not in cover_arts_by_artist_id, artist_id_list_missing_cover))
    if verbose and len(artist_id_list_missing_cover) > 0:
        msgproc.log(f"handler_element_artist_role_initial still missing [{len(artist_id_list_missing_cover)}] "
                    f"cover arts out of [{len(artists)}] "
                    f"initially [{initially_missing_cnt}] "
                    "after get_cover_art_list_by_artist_id_list "
                    f"[{artist_id_list_missing_cover}]")
    display_size: int = min(len(artists), page_size)
    has_next: bool = len(artists) == (page_size + 1)
    if verbose:
        msgproc.log(f"handler_element_artist_role_initial role [{artist_role}] "
                    f"initial [{artist_initial}] "
                    f"offset [{offset}] "
                    f"got [{len(artists)}] artists "
                    f"display_size [{display_size}] "
                    f"has_next [{has_next}]")
    curr_artist: persistence.ArtistEntry
    for curr_artist in artists[0:display_size]:
        cover_art: str = (cover_arts_by_artist_id[curr_artist.artist_id]
                          if curr_artist.artist_id in cover_arts_by_artist_id
                          else None)
        if verbose:
            msgproc.log(f"handler_element_artist_role_initial for [{artist_role}] "
                        f"should add [{curr_artist.artist_id}] [{curr_artist.artist_name}] "
                        f"cover_art [{cover_art}]")
        # add entry
        entries.append(entry_creator.artist_to_entry_raw(
            objid=objid,
            artist_id=curr_artist.artist_id,
            artist_entry_name=curr_artist.artist_name,
            artist_cover_art=cover_art))
    if has_next:
        # get last.
        next_identifier: ItemIdentifier = ItemIdentifier(
            name=ElementType.ARTIST_ROLE_INITIAL.element_name,
            value=artist_initial)
        next_identifier.set(
            key=ItemIdentifierKey.OFFSET,
            value=offset + page_size)
        next_identifier.set(
            key=ItemIdentifierKey.ARTIST_ROLE,
            value=artist_role)
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        next_artist: persistence.ArtistEntry = artists[len(artists) - 1]
        if next_artist.artist_cover_art:
            upnp_util.set_album_art_from_uri(
                album_art_uri=subsonic_util.build_cover_art_url(item_id=next_artist.artist_cover_art),
                target=next_entry)
        elif next_artist.artist_id in cover_arts_by_artist_id:
            next_album_art_uri: str = subsonic_util.build_cover_art_url(item_id=cover_arts_by_artist_id[next_artist.artist_id])
            upnp_util.set_album_art_from_uri(album_art_uri=next_album_art_uri, target=next_entry)
        entries.append(next_entry)
    return entries


def handler_element_artist(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    ref_album_id: str = item_identifier.get(ItemIdentifierKey.ALBUM_ID_REF_FOR_ARTIST, None)
    if ref_album_id:
        msgproc.log(f"Artist entry for artist_id [{artist_id}] created with reference to album_id [{ref_album_id}]")
        # create entry for album song selection
        songsel_identifier: ItemIdentifier = ItemIdentifier(
            name=ElementType.ALBUM_SONG_SELECTION_BY_ARTIST.element_name,
            value=artist_id)
        songsel_identifier.set(ItemIdentifierKey.ALBUM_ID_REF_FOR_ARTIST, ref_album_id)
        songsel_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(songsel_identifier))
        ref_album: Album = subsonic_util.try_get_album(album_id=ref_album_id)
        contributed_songs: list[Song] = (subsonic_util.get_authored_or_contributed_songs(album=ref_album, artist_id=artist_id)
                                         if ref_album
                                         else [])
        partial: bool = ((len(contributed_songs) > 0 and len(contributed_songs) < ref_album.getSongCount())
                         if ref_album else False)
        msgproc.log(f"Show song selection if partial: [{partial}]")
        if ref_album and partial:
            songsel_entry: dict[str, any] = upmplgutils.direntry(
                songsel_id,
                objid,
                f"Song selection in [{ref_album.getTitle()}]")
            upnp_util.set_album_art_from_uri(
                album_art_uri=subsonic_util.get_cover_art_url_by_album(album=ref_album),
                target=songsel_entry)
            entries.append(songsel_entry)
    artist: Artist = subsonic_util.try_get_artist(artist_id=artist_id)
    if not artist:
        msgproc.log(f"Cannot retrieve artist by id {artist_id}")
        persistence.delete_artist_metadata(artist_id=artist_id)
        return entries
    album_list: list[Album] = artist.getAlbumList()
    artist_mb_id: str = subsonic_util.get_artist_musicbrainz_id(artist)
    artist_cover_art_from_artist_api: bool = True
    # split album list in albums_as_main_artist and albums_as_appears_on
    albums_as_main_artist: list[Album] = subsonic_util.get_artist_albums_as_main_artist(
        artist_id=artist.getId(),
        album_list=album_list)
    subsonic_util.sort_albums_by_date(albums_as_main_artist)
    albums_as_appears_on: list[Album] = subsonic_util.get_artist_albums_as_appears_on(
        artist_id=artist.getId(),
        album_list=album_list)
    subsonic_util.sort_albums_by_date(albums_as_appears_on)
    artist_cover_art: str = subsonic_util.get_artist_cover_art(artist)
    if not artist_cover_art:
        artist_cover_art_from_artist_api = False
        # try from albums, as main artist first
        artist_cover_art = get_valid_cover_art_from_album_list(albums_as_main_artist)
    if not artist_cover_art:
        # try again from albums, as but also appearances
        artist_cover_art = get_valid_cover_art_from_album_list(albums_as_appears_on)
    msgproc.log(f"handler_element_artist artist_cover_art [{artist_cover_art}] "
                f"from api [{'yes' if artist_cover_art_from_artist_api else 'no'}]")
    # store artist metadata
    artist_metadata: persistence.ArtistMetadata = metadata_converter.build_artist_metadata(artist=artist)
    persistence.save_artist_metadata(artist_metadata)
    artist_roles: list[str] = subsonic_util.get_artist_roles(artist=artist)
    persistence.update_artist_roles(artist_id=artist_id, artist_roles=artist_roles, do_commit=True)
    if artist_mb_id:
        # at least the musicbrainz artist id is logged
        msgproc.log(f"Artist [{artist_id}] -> [{artist.getName()}] [{artist_mb_id}]")
    # do other artist by the same name exist?
    by_same_name_list: list[Artist] = (subsonic_util.get_artists_by_same_name(artist)
                                       if artist_mb_id
                                       else list())
    msgproc.log(f"Count of artists by same name: [{len(by_same_name_list)}]")
    if len(by_same_name_list) > 0:
        by_same_name: Artist
        cnt: int = 0
        for by_same_name in by_same_name_list:
            cnt += 1
            msgproc.log(f"Found artist #{cnt} by same name: [{by_same_name.getId()}]")
            bsn_entry_name: str = f"{by_same_name.getName()} [{by_same_name.getId()}] [{by_same_name.getAlbumCount()}]"
            bsn_entry: dict[str, any] = entry_creator.artist_to_entry(
                objid=objid,
                artist=by_same_name,
                entry_name=bsn_entry_name)
            if bsn_entry:
                entries.append(bsn_entry)
    # use one album for this entry image
    # understand release types.
    has_appearances: bool = len(albums_as_appears_on) > 0
    msgproc.log(f"Artist [{artist_id}] [{artist.getName()}] has \"Appears on\" albums: [{len(albums_as_appears_on)}]")
    artist_release_types: dict[str, int] = subsonic_util.get_release_types(album_list)
    msgproc.log(f"Artist [{artist_id}] [{artist.getName()}] release types counters are: [{artist_release_types}]")
    one_release_type: bool = len(artist_release_types.keys()) == 1
    single_release_type: str = next(iter(artist_release_types)) if one_release_type else None
    if one_release_type:
        msgproc.log(f"Artist [{artist_id}] [{artist.getName()}] one release type only: [{single_release_type}]")
    if not one_release_type:
        msgproc.log(f"Artist [{artist_id}] [{artist.getName()}] has [({len(artist_release_types.keys())})] "
                    f"release types: [{single_release_type}] "
                    "so we can add by-releasetype album entries!")
    else:
        msgproc.log(f"Artist [{artist_id}] [{artist.getName()}] has one release type only: [{single_release_type}] "
                    "so there is no need for by-releasetype album entries.")
    cover_art_album: Album
    if len(albums_as_main_artist) > 0:
        # to rule out album where artist just appears on
        cover_art_album = secrets.choice(albums_as_main_artist)
    else:
        # choose randomly in all albums
        cover_art_album = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
    albums_entry: dict[str, any] = create_artist_albums_entry(
        objid=objid,
        artist_id=artist_id,
        cover_art_album=cover_art_album,
        album_entry_name=(subsonic_util.release_type_to_album_list_label(single_release_type, len(album_list))
                          if one_release_type
                          else f"All Releases [{len(album_list)}]"))
    msgproc.log(f"handler_element_artist for [{artist_id}] [{artist.getName()}] -> "
                f"selected album_id: {cover_art_album.getId() if cover_art_album else None}")
    if not one_release_type:
        # add by release type.
        current_rt_str: str
        for current_rt_str in artist_release_types.keys():
            release_types: subsonic_util.AlbumReleaseTypes = subsonic_util.AlbumReleaseTypes(current_rt_str.split("/"))
            msgproc.log(f"Processing release type [{release_types.key}] [{release_types.display_name}] ...")
            by_rt_list: list[Album] = albums_by_release_type(artist_id, album_list, release_types)
            by_type_album: Album = secrets.choice(by_rt_list) if len(by_rt_list) > 0 else None
            by_type_album_count: int = len(by_rt_list)
            if by_type_album_count == 0:
                # skip release type, no albums (should appear among "Appearances")
                msgproc.log(f"Skipping release type [{release_types.key}] [{release_types.display_name}] "
                            f"because there are no albums for artist_id [{artist_id}], look in the Appearances")
                continue
            by_type_entry_name: str = subsonic_util.release_type_to_album_list_label(
                release_type=release_types.display_name,
                album_count=by_type_album_count)
            rt_entry: dict[str, any] = create_artist_albums_entry(
                objid=objid,
                artist_id=artist_id,
                cover_art_album=by_type_album,
                album_entry_name=by_type_entry_name,
                release_types=release_types)
            entries.append(rt_entry)
    # do we have appearances?
    if has_appearances:
        # we have appearances
        msgproc.log(f"We add the \"Appears on\" entry as we have [{len(albums_as_appears_on)}] appearances")
        appearances_entry: dict[str, any] = create_artist_albums_entry_for_appearances(
            objid=objid,
            artist_id=artist_id,
            album_entry_name=f"Appearances [{len(albums_as_appears_on)}]",
            cover_art_album=secrets.choice(albums_as_appears_on))
        entries.append(appearances_entry)
    # add fallback albums entry, can be "all releases" or just one entry because there are no release types
    entries.append(albums_entry)
    # add artist focus entry ...
    artist_focus_entry = entry_creator.artist_id_to_artist_focus(objid, artist_id)
    # possibly select another album for artist focus, preferring albums as main artist
    focus_select_album = (secrets.choice(albums_as_main_artist)
                          if len(albums_as_main_artist) > 0
                          else secrets.choice(album_list)
                          if album_list and len(album_list) > 0
                          else None)
    focus_select_album_cover_art: str = focus_select_album.getCoverArt() if focus_select_album else None
    upnp_util.set_album_art_from_uri(
        album_art_uri=subsonic_util.build_cover_art_url(item_id=focus_select_album_cover_art),
        target=artist_focus_entry)
    entries.append(artist_focus_entry)
    return entries


def get_valid_cover_art_from_album_list(album_list: list[Album]) -> str:
    curr_album: Album
    for curr_album in album_list:
        curr_album_art: str = curr_album.getCoverArt()
        if curr_album_art and len(curr_album_art) > 0:
            # found.
            artist_cover_art = curr_album_art
            return artist_cover_art


def albums_by_release_type(
        artist_id: str,
        album_list: list[Album],
        release_types: subsonic_util.AlbumReleaseTypes) -> list[Album]:
    msgproc.log(f"albums_by_release_type with release_types=[{release_types.key}]")
    result: list[Album] = list()
    rt_key: str = release_types.key
    current: Album
    for current in album_list if album_list else list():
        # artist id must be among the album main artists, otherwise it's a contributor (shown separately)
        if not subsonic_util.artist_id_among_main_artists(artist_id=artist_id, album=current):
            continue
        # check release type
        if subsonic_util.album_has_release_types(current):
            current_rt: subsonic_util.AlbumReleaseTypes = subsonic_util.get_album_release_types(current)
            if current_rt.key.lower() == rt_key.lower():
                result.append(current)
    return result


def create_artist_albums_entry(
        objid: any,
        artist_id: str,
        cover_art_album: Album,
        album_entry_name: str,
        release_types: subsonic_util.AlbumReleaseTypes = None) -> dict[str, any]:
    msgproc.log(f"create_artist_albums_entry for [{artist_id}] "
                f"release_types [{release_types.key if release_types else None}] "
                f"album_entry_name [{album_entry_name}]")
    item_identifier: ItemIdentifier = ItemIdentifier(
        name=ElementType.ARTIST_ALBUMS.element_name,
        value=artist_id)
    if release_types:
        item_identifier.set(ItemIdentifierKey.ALBUM_RELEASE_TYPE, release_types.key)
    artist_album_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(item_identifier))
    albums_entry: dict[str, any] = upmplgutils.direntry(
        id=artist_album_id,
        pid=objid,
        title=album_entry_name)
    upnp_util.set_album_art_from_uri(
        album_art_uri=subsonic_util.build_cover_art_url(item_id=cover_art_album.getCoverArt()) if cover_art_album else None,
        target=albums_entry)
    return albums_entry


def create_artist_albums_entry_for_appearances(
        objid: any,
        artist_id: str,
        cover_art_album: Album,
        album_entry_name: str) -> dict[str, any]:
    msgproc.log(f"create_artist_albums_entry_for_appearances for [{artist_id}]")
    item_identifier: ItemIdentifier = ItemIdentifier(
        name=ElementType.ARTIST_APPEARANCES.element_name,
        value=artist_id)
    artist_album_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(item_identifier))
    albums_entry: dict[str, any] = upmplgutils.direntry(
        id=artist_album_id,
        pid=objid,
        title=album_entry_name)
    upnp_util.set_album_art_from_uri(
        album_art_uri=subsonic_util.build_cover_art_url(item_id=cover_art_album.getCoverArt()) if cover_art_album else None,
        target=albums_entry)
    return albums_entry


def handler_element_artist_focus(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist: Artist = subsonic_util.try_get_artist(artist_id)
    if artist is None:
        return entries
    try:
        top_songs_entry_list: list[dict[str, any]] = create_artist_top_songs_entry(
            objid=objid,
            artist_id=artist_id,
            artist_name=artist.getName())
        top_songs_entry: dict[str, any]
        for top_songs_entry in top_songs_entry_list:
            entries.append(top_songs_entry)
    except Exception as ex:
        msgproc.log(f"Cannot get top songs for artist_id [{artist_id}] [{type(ex)}] [{ex}]")
    similar_artists_entry: dict[str, any] = create_similar_artists_entry(objid, artist_id)
    if similar_artists_entry:
        entries.append(similar_artists_entry)
    radio_entry_list: list[dict[str, any]] = create_artist_radio_entry(
        objid=objid,
        iid=artist.getId(),
        radio_entry_type=RadioEntryType.ARTIST_RADIO)
    radio_entry: dict[str, any]
    for radio_entry in radio_entry_list if radio_entry_list else []:
        entries.append(radio_entry)
    return entries


def handler_element_genre_artist(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    genre: str = item_identifier.get(ItemIdentifierKey.GENRE_NAME)
    artist_response: Response[Artist] = connector_provider.get().getArtist(artist_id)
    if not artist_response.isOk():
        raise Exception(f"Cannot retrieve artist by id {artist_id}")
    artist: Artist = artist_response.getObj()
    album_list: list[Album] = subsonic_util.get_album_list_by_artist_genre(artist, genre)
    artist_entry: dict[str, any] = entry_creator.artist_to_entry(
        objid=objid,
        artist=artist)
    # select first cover from album selection for artist within genre
    artist_entry_album_id: str = album_list[0].getId() if album_list and len(album_list) > 0 else None
    # load the album
    album: Album = subsonic_util.try_get_album(artist_entry_album_id)
    album_cover_art: str = album.getCoverArt() if album else None
    upnp_util.set_album_art_from_uri(
        album_art_uri=subsonic_util.build_cover_art_url(item_id=album_cover_art),
        target=artist_entry)
    entries.append(artist_entry)
    # entry for albums from artist within genre
    album_list_identifier: ItemIdentifier = ItemIdentifier(ElementType.GENRE_ARTIST_ALBUMS.element_name, artist_id)
    album_list_identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    album_list_id: str = identifier_util.create_objid(
        objid,
        identifier_util.create_id_from_identifier(album_list_identifier))
    album_list_entry: dict[str, any] = upmplgutils.direntry(
        album_list_id,
        objid,
        title=f"Albums for genre: [{genre}]")
    album_list_entry_album_id: str = artist_entry_album_id  # fallback to first
    if len(album_list) > 1:
        album_list_entry_album_id = album_list[1].getId()
    upnp_util.set_album_art_from_uri(
        album_art_uri=subsonic_util.get_cover_art_url_by_album_id(album_list_entry_album_id),
        target=album_list_entry)
    entries.append(album_list_entry)
    return entries


def handler_element_album_focus(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album: Album = subsonic_util.try_get_album(album_id=album_id)
    if not album:
        return entries
    start_time: float = time.time()
    get_top_songs_elapsed_time: float = 0
    get_top_songs_start_time: float = time.time()
    get_top_songs_elapsed_time: float = None
    if album.getArtistId():
        try:
            top_songs_entry_list: list[dict[str, any]] = create_artist_top_songs_entry(
                objid=objid,
                artist_id=album.getArtistId(),
                artist_name=subsonic_util.get_album_display_artist(album=album))
            top_songs_entry: dict[str, any]
            get_top_songs_elapsed_time = time.time() - get_top_songs_start_time
            for top_songs_entry in top_songs_entry_list:
                entries.append(top_songs_entry)
        except Exception as ex:
            msgproc.log(f"handler_element_album_focus cannot add top songs entry [{type(ex)}] [{ex}]")
    else:
        msgproc.log("handler_element_album_focus no artistId for "
                    f"album [{album.getId()}] [{album.getTitle()}], "
                    "not creating top songs entry")
    get_similar_artists_start_time: float = time.time()
    get_similar_artists_elapsed_time: float = None
    if album.getArtistId():
        similar_artist_entry: dict[str, any] = create_similar_artists_entry(objid, album.getArtistId())
        get_similar_artists_elapsed_time = time.time() - get_similar_artists_start_time
        if similar_artist_entry:
            entries.append(similar_artist_entry)
    else:
        msgproc.log(f"handler_element_album_focus no artistId for "
                    f"album [{album.getId()}] [{album.getTitle()}], "
                    "not creating similar artists entry")
    get_radio_entry_list_start_time: float = time.time()
    get_radio_entry_list_elapsed_time: float = None
    _radio_entry_list: list[dict[str, any]] = create_artist_radio_entry(
        objid=objid,
        iid=album.getId(),
        radio_entry_type=RadioEntryType.ALBUM_RADIO)
    get_radio_entry_list_elapsed_time = time.time() - get_radio_entry_list_start_time
    radio_entry: dict[str, any]
    for radio_entry in _radio_entry_list if _radio_entry_list else []:
        entries.append(radio_entry)
    elapsed_time: float = time.time() - start_time
    msgproc.log(f"handler_element_album_focus for album_id {album_id} took [{elapsed_time:.3f}] seconds")
    if get_top_songs_elapsed_time:
        msgproc.log(f"  top songs:       [{get_top_songs_elapsed_time:.3f}])")
    if get_similar_artists_elapsed_time:
        msgproc.log(f"  similar artists: [{get_similar_artists_elapsed_time:.3f}])")
    if get_radio_entry_list_elapsed_time:
        msgproc.log(f"  radio:           [{get_radio_entry_list_elapsed_time:.3f}])")
    return entries


def handler_element_navigable_album(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album: Album = subsonic_util.try_get_album(album_id=album_id)
    if not album:
        msgproc.log(f"Album [{album_id}] not found")
        persistence.delete_album_metadata(album_id=album_id)
        return entries
    album_metadata: AlbumMetadata = persistence.get_album_metadata(album_id=album.getId())
    # reload quality badges. We are displaying one album, so we can do this
    quality_badge: str = subsonic_util.calc_song_list_quality_badge(
        song_list=album.getSongs(),
        list_identifier=album.getId())
    song_quality_summary: str = subsonic_util.calc_song_quality_summary(song_list=album.getSongs())
    # Save it
    # if album_metadata is None:
    album_metadata, _ = persistence.save_album_metadata(
        album_metadata=metadata_converter.build_album_metadata(
            album=album,
            quality_badge=quality_badge,
            song_quality_summary=song_quality_summary),
        context="handler_element_navigable_album",
        force_insert=True if album_metadata is None else False)
    clean_title: str = album.getTitle()
    album_mb_id: str = subsonic_util.get_album_musicbrainz_id(album)
    media_type: str = subsonic_util.get_media_type(album)
    release_types: str = album.getItem().getByName(constants.ItemKey.RELEASE_TYPES.value, [])
    genres: list[str] = album.getGenres()
    album_version: str = subsonic_util.get_album_version(album)
    album_last_played: str = subsonic_util.get_album_played(album)
    record_label_names: list[str] = subsonic_util.get_album_record_label_names(album)
    if verbose:
        msgproc.log(f"handler_element_navigable_album album [{album_id}] -> artist_id: [{album.getArtistId()}]")
        msgproc.log(f"handler_element_navigable_album album [{album_id}] -> album_mbid: [{album_mb_id}]")
        msgproc.log(f"handler_element_navigable_album album [{album_id}] -> media type [{media_type}]")
        msgproc.log(f"handler_element_navigable_album album [{album_id}] -> release types [{release_types}]")
        msgproc.log(f"handler_element_navigable_album album [{album_id}] -> genres [{genres}]")
        msgproc.log(f"handler_element_navigable_album album [{album_id}] -> version [{album_version}]")
        msgproc.log(f"handler_element_navigable_album album [{album_id}] -> last played [{album_last_played}]")
        msgproc.log(f"handler_element_navigable_album album [{album_id}] -> record label names [{record_label_names}]")
    album_entry: dict[str, any] = entry_creator.album_to_entry(
        objid=objid,
        album=album)
    # set title a little differently here ...
    title: str = clean_title
    # album year if available
    if config.get_config_param_as_bool(constants.ConfigParam.APPEND_YEAR_TO_ALBUM_VIEW) and has_year(album):
        title = f"{title} [{get_album_year_str(album)}]"
    # add genre if allowed
    title = subsonic_util.append_genre_to_artist_entry_name_if_allowed(
        entry_name=title,
        album=album,
        config_getter=(lambda: config.get_config_param_as_bool(constants.ConfigParam.ALLOW_GENRE_IN_ALBUM_VIEW)))
    # badge if available
    album_quality_badge: str = (album_metadata.quality_badge
                                if album_metadata
                                else subsonic_util.calc_song_list_quality_badge(
                                    song_list=album.getSongs(),
                                    list_identifier=album.getId()))
    title = subsonic_util.append_album_badge_to_album_title(
        current_albumtitle=title,
        album_quality_badge=album_quality_badge,
        album_entry_type=constants.AlbumEntryType.ALBUM_VIEW,
        is_search_result=False)
    title = subsonic_util.append_album_version_to_album_title(
        current_albumtitle=title,
        album_version=album_version,
        album_entry_type=constants.AlbumEntryType.ALBUM_VIEW,
        is_search_result=False)
    title = subsonic_util.append_album_id_to_album_title(
        current_albumtitle=title,
        album_id=album_id,
        album_entry_type=constants.AlbumEntryType.ALBUM_VIEW,
        is_search_result=False)
    if album_mb_id and config.get_config_param_as_bool(constants.ConfigParam.SHOW_ALBUM_MBID_IN_ALBUM_VIEW):
        if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ALBUM_MB_ID_AS_PLACEHOLDER):
            title = f"{title} [mb]"
        else:
            title = f"{title} [mb:{album_mb_id}]"
    upnp_util.set_track_title(title, album_entry)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_QUALITY, album_quality_badge, album_entry)
    subsonic_util.set_album_metadata(
        album=album,
        target=album_entry,
        album_metadata=album_metadata)
    entries.append(album_entry)
    # add artist if needed
    skip_artist_id: str = item_identifier.get(ItemIdentifierKey.SKIP_ARTIST_ID)
    if skip_artist_id:
        msgproc.log(f"handler_element_navigable_album skip_artist_id: [{skip_artist_id}]")
    skip_artist_id_set: set[str] = set()
    if skip_artist_id:
        skip_artist_id_set.add(skip_artist_id)
    # additional...
    inline_additional_artists_for_album: bool = True
    additional: list[subsonic_util.ArtistsOccurrence] = subsonic_util.get_all_artists_in_album(album=album)
    additional_artist_len: int = len(additional)
    additional_artists_max: int = config.get_config_param_as_int(constants.ConfigParam.MAX_ADDITIONAL_ARTISTS)
    if additional_artist_len > additional_artists_max:
        msgproc.log("handler_element_navigable_album Suppressing additional artists because there are too many "
                    f"for album [{album.getId()}], "
                    f"limit is [{additional_artists_max}], "
                    f"but we have [{additional_artist_len}]")
        # reset additional so they are not presented
        inline_additional_artists_for_album = False
    curr_additional: subsonic_util.ArtistsOccurrence
    for curr_additional in additional:
        msgproc.log(f"handler_element_navigable_album for album_id [{album.getId()}] "
                    f"found artist_id:[{curr_additional.artist_id}] "
                    f"name:[{curr_additional.artist_name}]")
    if inline_additional_artists_for_album and len(additional) > 0:
        msgproc.log(f"handler_element_navigable_album adding {len(additional)} additional artists "
                    f"[{list(map(lambda c: c.artist_id, additional))}] "
                    f"skip_artist_id_set [{skip_artist_id_set}] ...")
        additional_artist_entries: list[dict, str] = create_entries_for_album_additional_artists(
            objid=objid,
            album_id=album_id,
            additional=additional,
            skip_artist_id_set=skip_artist_id_set)
        entries.extend(additional_artist_entries)
    elif len(additional) > 0:
        # create main artist entry if album has artist id
        if album.getArtistId():
            main_artist: Artist = subsonic_util.try_get_artist(artist_id=album.getArtistId())
            if main_artist:
                entries.append(
                    entry_creator.artist_to_entry(
                        objid=objid,
                        artist=main_artist))
            else:
                msgproc.log(f"handler_element_navigable_album cannot load main artist [{album.getArtistId()}] "
                            f"for album_id [{album.getId()}]")
        # create dedicated entry for additional album artists
        msgproc.log(f"handler_element_navigable_album creating entry for {len(additional)} additional artists ...")
        additional_album_artists_identifier: ItemIdentifier = ItemIdentifier(
            name=ElementType.ADDITIONAL_ALBUM_ARTISTS.element_name,
            value=album_id)
        additional_album_artists_identifier_id: str = identifier_util.create_objid(
                objid=objid,
                id=identifier_util.create_id_from_identifier(additional_album_artists_identifier))
        additional_album_artists_entry: dict[str, any] = upmplgutils.direntry(
            id=additional_album_artists_identifier_id,
            pid=objid,
            title="Additional Artists")
        # select random artist
        select_random_artist: subsonic_util.ArtistsOccurrence = secrets.choice(additional)
        msgproc.log("handler_element_navigable_album selected for additional artist entry "
                    f"[{select_random_artist.artist_name}] "
                    f"[{select_random_artist.artist_id}]")
        random_artist_cover_art_uri: str = art_retriever.get_album_cover_art_url_by_artist_id(select_random_artist.artist_id)
        upnp_util.set_album_art_from_uri(
            album_art_uri=random_artist_cover_art_uri,
            target=additional_album_artists_entry)
        entries.append(additional_album_artists_entry)
        pass
    entry: dict[str, any] = entry_creator.album_id_to_album_focus(objid=objid, album=album)
    entries.append(entry)
    cache_actions.on_album(album=album)
    return entries


def handler_additional_album_artists(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    page_size: int = config.get_config_param_as_int(constants.ConfigParam.MAX_ADDITIONAL_ALBUM_ARTISTS_PER_PAGE)
    msgproc.log(f"handler_additional_album_artists for album_id [{album_id}] offset [{offset}]")
    album: Album = subsonic_util.try_get_album(album_id=album_id)
    if not album:
        return entries
    skip_artist_id_set: set[str] = set()
    if album.getArtistId():
        skip_artist_id_set.add(album.getArtistId())
    additional: list[subsonic_util.ArtistsOccurrence] = subsonic_util.filter_out_artist_id(
        artist_list=subsonic_util.get_all_artists_in_album(album=album),
        artist_id=album.getArtistId())
    current: subsonic_util.ArtistsOccurrence
    # apply offset
    additional = additional[offset:] if len(additional) > offset else []
    next_artist: subsonic_util.ArtistsOccurrence = (additional[page_size]
                                                    if len(additional) > page_size
                                                    else None)
    sliced: list[subsonic_util.ArtistsOccurrence] = additional[0:min(len(additional), page_size)]
    for current in sliced:
        entry_name: str = current.artist_name
        if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_ID):
            entry_name = f"{entry_name} [{current.artist_id}]"
        entry_name = subsonic_util.append_cached_mb_id_to_artist_entry_name_if_allowed(
            entry_name=entry_name,
            artist_id=current.artist_id)
        curr_entry: dict[str, any] = entry_creator.artist_to_entry_raw(
            objid=objid,
            artist_id=current.artist_id,
            artist_entry_name=current.artist_name,
            additional_identifier_properties={
                ItemIdentifierKey.ALBUM_ID_REF_FOR_ARTIST: album_id})
        if curr_entry:
            entries.append(curr_entry)
    if next_artist:
        next_offset: int = (offset +
                            config.get_config_param_as_int(constants.ConfigParam.MAX_ADDITIONAL_ALBUM_ARTISTS_PER_PAGE))
        msgproc.log("handler_additional_album_artists "
                    f"Adding next button for album [{album_id}] "
                    "for offset "
                    f"[{next_offset}] ...")
        next_identifier: ItemIdentifier = ItemIdentifier(
            name=ElementType.ADDITIONAL_ALBUM_ARTISTS.element_name,
            value=album_id)
        next_identifier.set(
            key=ItemIdentifierKey.OFFSET,
            value=next_offset)
        next_id: str = identifier_util.create_objid(
            objid=objid,
            id=identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        next_album_art_uri: str = art_retriever.get_album_cover_art_url_by_artist_id(next_artist.artist_id)
        upnp_util.set_album_art_from_uri(album_art_uri=next_album_art_uri, target=next_entry)
        entries.append(next_entry)
    return entries


def create_entries_for_album_additional_artists(
        objid: any,
        album_id: str,
        additional: list[subsonic_util.ArtistsOccurrence],
        skip_artist_id_set: set[str]) -> list[dict[str, any]]:
    artist_entries: list[dict[str, any]] = []
    artist_id_list: list[str] = [x.artist_id for x in additional]
    cover_dict: dict[str, list[ArtistAlbumCoverArt]] = persistence.get_cover_art_list_by_artist_id_list(
        artist_id_list=artist_id_list)
    curr_artist: subsonic_util.ArtistsOccurrence
    for curr_artist in additional:
        add_current: bool = curr_artist.artist_id not in skip_artist_id_set
        msgproc.log(f"create_entries_for_album_additional_artists handling [{curr_artist.artist_id}] [{curr_artist.artist_name}] "
                    f"adding [{'yes' if add_current else 'no'}]")
        if add_current:
            entry_name: str = curr_artist.artist_name
            if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_ID):
                entry_name = f"{entry_name} [{curr_artist.artist_id}]"
            # do we know the artist mb id?
            if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID):
                # see if we have it cached.
                artist_metadata: persistence.ArtistMetadata = persistence.get_artist_metadata(artist_id=curr_artist.artist_id)
                # artist_mb_id: str = cache_actions.get_artist_mb_id(curr_artist.id)
                artist_mb_id: str = artist_metadata.artist_musicbrainz_id if artist_metadata else None
                if artist_mb_id:
                    if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ACTION_ON_MB_ALBUM_CACHE):
                        msgproc.log(f"Found mbid for artist_id [{curr_artist.artist_id}] -> [{artist_mb_id}]")
                    if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID_AS_PLACEHOLDER):
                        entry_name = f"{entry_name} [mb]"
                    else:
                        entry_name = f"{entry_name} [{artist_mb_id}]"
                else:
                    if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ACTION_ON_MB_ALBUM_CACHE):
                        msgproc.log(f"Cannot find mbid for artist_id [{curr_artist.artist_id}]")
            msgproc.log(f"Adding artist entry: [{entry_name}] for artist_id: [{curr_artist.artist_id}] ...")
            additional_identifier_properties: dict[ItemIdentifierKey, any] = {}
            if curr_artist.artist_id not in skip_artist_id_set:
                additional_identifier_properties[ItemIdentifierKey.ALBUM_ID_REF_FOR_ARTIST] = album_id
            # load the artist
            cover_lst: list[ArtistAlbumCoverArt] = (cover_dict[curr_artist.artist_id]
                                                    if curr_artist.artist_id in cover_dict else [])
            artist_cover_art: ArtistAlbumCoverArt = persistence.choose_artist_album_cover_art(cover_lst)
            cover_art: str = artist_cover_art.cover_art if artist_cover_art else None
            artist_entries.append(entry_creator.artist_to_entry_raw(
                objid=objid,
                artist_id=curr_artist.artist_id,
                artist_entry_name=curr_artist.artist_name,
                artist_cover_art=cover_art,
                additional_identifier_properties=additional_identifier_properties))
            msgproc.log(f"Adding artist_id: [{curr_artist.artist_id}] to skip set ...")
            skip_artist_id_set.add(curr_artist.artist_id)
        else:
            msgproc.log(f"create_entries_for_album_additional_artists handling [{curr_artist.artist_id}] "
                        f"[{curr_artist.artist_name}] -> not adding!")
    return artist_entries


def create_artist_radio_entry(objid, iid: str, radio_entry_type: RadioEntryType) -> list[dict[str, any]]:
    msgproc.log(f"create_artist_radio_entry for {iid} [{radio_entry_type}]")
    radio_identifier: ItemIdentifier = ItemIdentifier(ElementType.RADIO.element_name, iid)
    radio_id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(radio_identifier))
    radio_entry: dict[str, any] = upmplgutils.direntry(
        radio_id,
        objid,
        title="Radio")
    radio_song_list_identifier: ItemIdentifier = ItemIdentifier(ElementType.RADIO_SONG_LIST.element_name, iid)
    radio_song_list_id: str = identifier_util.create_objid(
        objid,
        identifier_util.create_id_from_identifier(radio_song_list_identifier))
    radio_song_list_entry: dict[str, any] = upmplgutils.direntry(
        radio_song_list_id,
        objid,
        title="Radio (List)")
    if RadioEntryType.ARTIST_RADIO == radio_entry_type:
        # pick two random albums
        res: Response[Artist] = connector_provider.get().getArtist(artist_id=iid)
        artist: Artist = res.getObj() if res and res.isOk() else None
        album_list: list[Album] = artist.getAlbumList() if artist else None
        first_art_album: Album = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
        second_art_album: Album = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=first_art_album.getCoverArt()) if first_art_album else None,
            target=radio_entry)
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=second_art_album.getCoverArt() if second_art_album else None),
            target=radio_song_list_entry)
    else:
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.get_cover_art_url_by_album_id(album_id=iid),
            target=radio_entry)
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.get_cover_art_url_by_album_id(album_id=iid),
            target=radio_song_list_entry)
    return [radio_entry, radio_song_list_entry]


def create_similar_artists_entry(objid, artist_id: str) -> dict[str, any]:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    res_artist_info: Response[ArtistInfo] = connector_provider.get().getArtistInfo(artist_id)
    if not res_artist_info.isOk():
        raise Exception(f"Cannot get artist info for artist_id {artist_id}")
    similar_artists: list[SimilarArtist] = res_artist_info.getObj().getSimilarArtists()
    if len(similar_artists if similar_artists else []) > 0:
        # ok to add similar artists entry
        similar_artist_identifier: ItemIdentifier = ItemIdentifier(ElementType.ARTIST_SIMILAR.element_name, artist_id)
        similar_artist_id: str = identifier_util.create_objid(
            objid,
            identifier_util.create_id_from_identifier(similar_artist_identifier))
        similar_artists_entry: dict[str, any] = upmplgutils.direntry(
            similar_artist_id,
            objid,
            title="Similar Artists")
        # artist_art
        select_similar_artist: SimilarArtist = res_artist_info.getObj().getSimilarArtists()[0]
        similar_artist_id: str = select_similar_artist.getId()
        if verbose:
            msgproc.log(f"create_similar_artists_entry for artist [{artist_id}] "
                        f"selected similar artist [{similar_artist_id}] "
                        f"[{select_similar_artist.getName()}]")
        # show art for similar_artist_id if available
        if similar_artist_id:
            upnp_util.set_album_art_from_uri(
                album_art_uri=art_retriever.get_album_cover_art_url_by_artist_id(artist_id=similar_artist_id),
                target=similar_artists_entry)
        return similar_artists_entry
    else:
        # no similar artists.
        msgproc.log(f"Similar artists not available for [{artist_id}]")


def create_artist_top_songs_entry(objid, artist_id: str, artist_name: str) -> list[dict[str, any]]:
    result: list[dict[str, any]] = list()
    res_top_songs: Response[TopSongs] = connector_provider.get().getTopSongs(artist_name)
    if not res_top_songs.isOk():
        raise Exception(f"Cannot load top songs for artist {artist_name}")
    if len(res_top_songs.getObj().getSongs()) > 0:
        # ok to create top songs entry, else None
        top_songs_identifier: ItemIdentifier = ItemIdentifier(ElementType.ARTIST_TOP_SONGS.element_name, artist_id)
        top_songs_id: str = identifier_util.create_objid(
            objid,
            identifier_util.create_id_from_identifier(top_songs_identifier))
        top_songs_entry: dict[str, any] = upmplgutils.direntry(
            top_songs_id,
            objid,
            title=f"Top Songs by {artist_name}")
        top_songs: list[Song] = res_top_songs.getObj().getSongs()
        art_select_song: Song = secrets.choice(top_songs) if top_songs and len(top_songs) > 0 else None
        art_select_song_art: str = art_select_song.getCoverArt() if art_select_song else None
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=art_select_song_art),
            target=top_songs_entry)
        result.append(top_songs_entry)
        top_songs_list_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.ARTIST_TOP_SONGS_LIST.element_name,
            artist_id)
        top_songs_list_id: str = identifier_util.create_objid(
            objid,
            identifier_util.create_id_from_identifier(top_songs_list_identifier))
        top_songs_list_entry: dict[str, any] = upmplgutils.direntry(
            top_songs_list_id,
            objid,
            title=f"Top Songs (List) by {artist_name}")
        art_select_song = secrets.choice(res_top_songs.getObj().getSongs())
        upnp_util.set_album_art_from_uri(
            album_art_uri=subsonic_util.build_cover_art_url(item_id=art_select_song.getCoverArt()),
            target=top_songs_list_entry)
        result.append(top_songs_list_entry)
    return result


def handler_element_similar_artists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_element_similar_artists for artist_id {artist_id}")
    res: Response[ArtistInfo] = connector_provider.get().getArtistInfo(artist_id)
    if not res.isOk():
        raise Exception(f"Cannot get artist info for artist_id {artist_id}")
    sim_artist_list: list[SimilarArtist] = res.getObj().getSimilarArtists()
    sim_artist: SimilarArtist
    for sim_artist in sim_artist_list:
        entries.append(entry_creator.artist_to_entry_raw(
            objid=objid,
            artist_id=sim_artist.getId(),
            artist_cover_art=subsonic_util.get_artist_cover_art(artist=sim_artist),
            artist_entry_name=sim_artist.getName()))
    return entries


def handler_album_song_selection_by_artist(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    ref_album_id: str = item_identifier.get(ItemIdentifierKey.ALBUM_ID_REF_FOR_ARTIST)
    msgproc.log(f"handler_album_song_selection_by_artist for artist_id [{artist_id}] "
                f"ref_album_id [{ref_album_id}]")
    # load album.
    album: Album = subsonic_util.try_get_album(album_id=ref_album_id)
    if not album:
        return entries
    song_selection: list[Song] = subsonic_util.get_authored_or_contributed_songs(
        album=album,
        artist_id=artist_id)
    curr: Song
    # display the song selection
    for curr in song_selection:
        song_entry: dict[str, any] = entry_creator.song_to_entry(
            objid=objid,
            song=curr)
        if song_entry:
            entries.append(song_entry)
    return entries


def handler_element_album_disc(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    avp_enc: str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, None)
    disc_num_str: str = item_identifier.get(ItemIdentifierKey.ALBUM_DISC_NUMBERS, None)
    msgproc.log(f"handler_element_album_disc for album_id [{album_id}] "
                f"avp_enc [{avp_enc}] disc_num [{disc_num_str}]")
    if not disc_num_str:
        msgproc.log(f"handler_element_album_disc for album_id [{album_id}] missing disc number")
        return entries
    # split disc numbers
    disc_number_str_list: list[str] = disc_num_str.split(constants.Separator.DISC_NUMBER_SEPARATOR.value)
    disc_number_list: list[int] = list(map(int, disc_number_str_list))
    # get the album tracks
    album_version_path: str = codec.base64_decode(avp_enc) if avp_enc else None
    album: Album = subsonic_util.try_get_album(album_id=album_id)
    if not album:
        msgproc.log(f"handler_element_album_disc cannot get album by album_id [{album_id}]")
        return entries
    song_list: list[Song] = album.getSongs()
    to_display: list[Song] = song_list if not album_version_path else []
    if album_version_path:
        # filter
        current: Song
        for current in song_list:
            if current.getPath().startswith(album_version_path):
                to_display.append(current)
    song: Song
    for song in to_display:
        if song.getDiscNumber() in disc_number_list:
            # add to entries ...
            song_entry: dict[str, any] = entry_creator.song_to_entry(
                objid=objid,
                song=song)
            if song_entry:
                entries.append(song_entry)
    return entries


def handler_element_album(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    avp_enc: str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, None)
    msgproc.log(f"handler_element_album for album_id [{album_id}] avp_enc [{avp_enc}]")
    album_version_path: str = codec.base64_decode(avp_enc) if avp_enc else None
    msgproc.log(f"handler_element_album for album_id [{album_id}] "
                f"album_version_path [{album_version_path}]")
    album: Album
    album_tracks: AlbumTracks
    album, album_tracks = get_album_tracks(album_id) if not album_version_path else (None, None)
    if not album:
        msgproc.log(f"Album [{album_id}] not found")
        persistence.delete_album_metadata(album_id=album_id)
        return entries
    if album_tracks and album_tracks.getAlbumVersionCount() > 1:
        msgproc.log(f"handler_element_album for album_id [{album_id}] -> [{album_tracks.getAlbumVersionCount()}] versions")
        version_counter: int = 0
        album_version_path: str
        codec_set: set[str]
        for album_version_path in album_tracks.getCodecSetByPath().keys():
            msgproc.log(f"Presenting version [{version_counter + 1}/{album_tracks.getAlbumVersionCount()}] "
                        f"album_version_path [{album_version_path}]...")
            codec_set: set[str] = album_tracks.getCodecSetByPath()[album_version_path]
            album_version_entry: dict[str, any] = entry_creator.album_version_to_entry(
                objid=objid,
                current_album=album_tracks.getAlbum(),
                version_number=version_counter + 1,
                album_version_path=album_version_path,
                codec_set=codec_set)
            entries.append(album_version_entry)
            version_counter += 1
        return entries
    # one version only
    if album:
        msgproc.log(f"One version only for album [{album.getId()}] "
                    f"mb [{subsonic_util.get_album_musicbrainz_id(album)}], presenting ...")
    return present_album_version(
        objid=objid,
        item_identifier=item_identifier,
        album_id=album_id,
        album_version_path=album_version_path,
        entries=entries)


def handler_element_album_version(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album_version_path: str = None
    if item_identifier.has(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64):
        avp_encoded: str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64)
        album_version_path = codec.base64_decode(avp_encoded)
    msgproc.log(f"handler_element_album_version for album_id [{album_id}] "
                f"avp_enc [{avp_encoded}] "
                f"album_version_path [{album_version_path}]")
    return present_album_version(
        objid=objid,
        item_identifier=item_identifier,
        album_id=album_id,
        album_version_path=album_version_path,
        entries=entries)


def handler_element_radio_station(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    station_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    response: Response[InternetRadioStations] = connector_provider.get().getInternetRadioStations()
    if not response.isOk():
        raise Exception("Cannot get the internet radio stations")
    select_station: InternetRadioStation
    station: InternetRadioStation
    for station in response.getObj().getStations():
        if station.getId() == station_id:
            select_station = station
            break
    station_entry: dict[str, any] = _station_to_entry(objid, select_station)
    entries.append(station_entry)
    return entries


def handler_element_song(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    song_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_element_song should serve song_id {song_id}")
    song_response: Response[Song] = connector_provider.get().getSong(song_id)
    if not song_response.isOk():
        raise Exception(f"Cannot find song with id {song_id}")
    identifier: ItemIdentifier = ItemIdentifier(ElementType.SONG.element_name, song_id)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    song_entry: dict[str, any] = _song_data_to_entry(objid, id, song_response.getObj())
    entries.append(song_entry)
    return entries


def handler_tag_group_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tag_list: list[TagType] = [
        TagType.NEWEST_ALBUMS,
        TagType.OLDEST_ALBUMS,
        TagType.RECENTLY_ADDED_ALBUMS,
        TagType.RECENTLY_PLAYED_ALBUMS,
        TagType.HIGHEST_RATED_ALBUMS,
        TagType.MOST_PLAYED_ALBUMS,
        TagType.ALPHABETICAL_BY_NAME_ALBUMS,
        TagType.ALPHABETICAL_BY_ARTIST_ALBUMS,
        TagType.RANDOM]
    if config.get_config_param_as_bool(constants.ConfigParam.PRELOAD_ALBUMS):
        tag_list.append(TagType.ALBUM_BROWSER)
    add_fav: bool = config.get_config_param_as_bool(constants.ConfigParam.SHOW_EMPTY_FAVORITES)
    if not add_fav:
        msgproc.log("handler_tag_group_albums loading favorites ...")
        res: Response[Starred] = request_cache.get_starred()
        if res.isOk:
            fav_albums: list[Album] = res.getObj().getAlbums()
            msgproc.log(f"handler_tag_group_albums favorite albums [{len(fav_albums) if fav_albums else 0}] ...")
            if fav_albums and len(fav_albums) > 0:
                # add fav tags
                add_fav = True
    if add_fav:
        tag_list.append(TagType.FAVORITE_ALBUMS)
    # add maintenance features
    if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_MAINTENANCE_FEATURES):
        tag_list.extend([
            TagType.ALBUMS_WITHOUT_MUSICBRAINZ,
            TagType.ALBUMS_WITHOUT_COVER,
            TagType.ALBUMS_WITHOUT_GENRE])
    context: TagToEntryContext = TagToEntryContext()
    current: TagType
    for current in tag_list:
        if config.is_tag_supported(current):
            try:
                entry: dict[str, any] = tag_to_entry(
                    objid=objid,
                    tag=current,
                    context=context)
                entries.append(entry)
            except Exception as ex:
                msgproc.log(f"Cannot create entry for tag [{current.tag_name}] "
                            f"[{type(ex)}] [{ex}]")
        else:
            msgproc.log(f"handler_tag_group_albums skipping unsupported [{current}]")
    return entries


def get_first_cover_art_from_song_list(song_list: list[Song]) -> str:
    song: Song
    for song in song_list if song_list else []:
        if song.getCoverArt():
            return song.getCoverArt()
    return None


def get_group_artists_item_list() -> list[Any]:
    if config.get_config_param_as_bool(constants.ConfigParam.PRELOAD_ARTISTS):
        return [
            TagType.ARTIST_ROLES]
    else:
        return [
            TagType.ALL_ARTISTS,
            TagType.ALL_ARTISTS_INDEXED,
            TagType.ALL_ARTISTS_UNSORTED,
            TagType.ALL_ALBUM_ARTISTS_UNSORTED,
            TagType.ALL_COMPOSERS_UNSORTED,
            TagType.ALL_CONDUCTORS_UNSORTED]


def handler_tag_group_artists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tag_list: list[Any] = get_group_artists_item_list()
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    random_size: int = 100
    msgproc.log(f"handler_tag_group_artists getting [{random_size}] random songs ...")
    res: Response[AlbumList] = connector_provider.get().getRandomAlbumList(size=random_size)
    album_list: list[Album] = res.getObj().getAlbums() if res and res.isOk() else []
    msgproc.log(f"handler_tag_group_artists got [{len(album_list)}] random songs")
    # filter out songs without cover art
    album_list = list(filter(lambda x: x.getCoverArt() is not None, album_list))
    # unique cover arts
    unique_cover_art_set: set[Song] = set()
    album: Album
    for album in album_list if album_list else None:
        if album.getCoverArt() not in unique_cover_art_set:
            unique_cover_art_set.add(album.getCoverArt())
    current_tag: TagType
    for current_tag in tag_list:
        if isinstance(current_tag, TagType):
            msgproc.log(f"handler_tag_group_artists current_tag [{current_tag.tag_name}] ...")
            entry: dict[str, any] = create_entry_for_tag(objid, current_tag)
            in_set: bool = len(unique_cover_art_set) > 0
            select_cover_art: str = unique_cover_art_set.pop() if in_set else None
            if not select_cover_art:
                select_album: Album = secrets.choice(album_list)
                select_cover_art = select_album.getCoverArt() if select_album else None
            upnp_util.set_album_art_from_uri(
                album_art_uri=subsonic_util.build_cover_art_url(item_id=select_cover_art),
                target=entry)
            entries.append(entry)
    # more entries ...
    fav_artists: list[Artist] = list()
    fav_res: Response[Starred] = request_cache.get_starred()
    fav_artists = fav_res.getObj().getArtists() if fav_res and fav_res.isOk() else None
    msgproc.log(f"handler_tag_group_artists favorite artists count: [{len(fav_artists)}]")
    select_fav: Artist = secrets.choice(fav_artists) if fav_artists and len(fav_artists) > 0 else None
    add_fav: bool = (config.get_config_param_as_bool(constants.ConfigParam.SHOW_EMPTY_FAVORITES)
                     or select_fav is not None)
    if add_fav:
        fav_artist_entry: dict[str, any] = create_entry_for_tag(objid, TagType.FAVORITE_ARTISTS)
        if select_fav:
            msgproc.log(f"handler_tag_group_artists fav_artist [{select_fav.getId()}] "
                        f"[{select_fav.getName() if select_fav else None}]")
            fav_art_uri: str = None
            artist_cover_art: str = subsonic_util.get_artist_cover_art(artist=select_fav)
            if verbose:
                msgproc.log(f"handler_tag_group_artists got cover art from artist: [{'yes' if artist_cover_art else 'no'}] "
                            f"CoverArt: [{artist_cover_art}]")
            if not artist_cover_art:
                if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
                    msgproc.log(f"handler_tag_group_artists artist [{select_fav.getId()}] [{select_fav.getName()}] "
                                "has no cover art, using albums (slower) ...")
                fav_art_uri = art_retriever.get_album_cover_art_url_by_artist_id(artist_id=select_fav.getId())
            else:
                fav_art_uri = subsonic_util.build_cover_art_url(item_id=artist_cover_art)
            upnp_util.set_album_art_from_uri(
                album_art_uri=fav_art_uri,
                target=fav_artist_entry)
        entries.append(fav_artist_entry)
    return entries


def handler_tag_group_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tag_list: list[TagType] = [
        TagType.RANDOM_SONGS,
        TagType.RANDOM_SONGS_LIST]
    add_fav: bool = config.get_config_param_as_bool(constants.ConfigParam.SHOW_EMPTY_FAVORITES)
    if not add_fav:
        res: Response[Starred] = request_cache.get_starred()
        if res.isOk:
            fav_songs: list[Album] = res.getObj().getSongs()
            if fav_songs and len(fav_songs) > 0:
                # add fav tags
                add_fav = True
    if add_fav:
        tag_list.extend([
            TagType.FAVORITE_SONGS,
            TagType.FAVORITE_SONGS_LIST])
    entry_list: list[dict[str, any]] = tag_list_to_entries(
        objid,
        tag_list)
    entries.extend(entry_list)
    return entries


__tag_action_dict: dict = {
    TagType.ALBUMS.tag_name: handler_tag_group_albums,
    TagType.ARTISTS.tag_name: handler_tag_group_artists,
    TagType.SONGS.tag_name: handler_tag_group_songs,
    TagType.RECENTLY_ADDED_ALBUMS.tag_name: handler_tag_recently_added_albums,
    TagType.NEWEST_ALBUMS.tag_name: handler_tag_newest_albums,
    TagType.ALPHABETICAL_BY_NAME_ALBUMS.tag_name: handler_tag_alphabetical_by_name_albums,
    TagType.ALPHABETICAL_BY_ARTIST_ALBUMS.tag_name: handler_tag_alphabetical_by_artist_albums,
    TagType.OLDEST_ALBUMS.tag_name: handler_tag_oldest_albums,
    TagType.RECENTLY_PLAYED_ALBUMS.tag_name: handler_tag_recently_played,
    TagType.HIGHEST_RATED_ALBUMS.tag_name: handler_tag_highest_rated,
    TagType.MOST_PLAYED_ALBUMS.tag_name: handler_tag_most_played,
    TagType.FAVORITE_ALBUMS.tag_name: handler_tag_favourite_albums,
    TagType.ALBUMS_WITHOUT_MUSICBRAINZ.tag_name: handler_tag_albums_without_musicbrainz,
    TagType.ALBUMS_WITHOUT_COVER.tag_name: handler_tag_albums_without_cover,
    TagType.ALBUMS_WITHOUT_GENRE.tag_name: handler_tag_albums_without_genre,
    TagType.RANDOM.tag_name: handler_tag_random,
    TagType.GENRES.tag_name: handler_tag_genres,
    TagType.ARTIST_ROLES.tag_name: handler_tag_artist_roles,
    TagType.ALL_ARTISTS.tag_name: handler_tag_all_artists,
    TagType.ALL_ARTISTS_INDEXED.tag_name: handler_tag_all_artists_indexed,
    TagType.ALL_ARTISTS_UNSORTED.tag_name: handler_tag_all_artists_unsorted,
    TagType.ALL_ALBUM_ARTISTS_UNSORTED.tag_name: handler_tag_all_album_artists_unsorted,
    TagType.ALL_COMPOSERS_UNSORTED.tag_name: handler_tag_all_composers_unsorted,
    TagType.ALL_CONDUCTORS_UNSORTED.tag_name: handler_tag_all_conductors_unsorted,
    TagType.FAVORITE_ARTISTS.tag_name: handler_tag_favourite_artists,
    TagType.PLAYLISTS.tag_name: handler_tag_playlists,
    TagType.INTERNET_RADIOS.tag_name: handler_tag_internet_radios,
    TagType.RANDOM_SONGS.tag_name: handler_tag_random_songs,
    TagType.RANDOM_SONGS_LIST.tag_name: handler_tag_random_songs_list,
    TagType.FAVORITE_SONGS.tag_name: handler_tag_favourite_songs,
    TagType.FAVORITE_SONGS_LIST.tag_name: handler_tag_favourite_songs_list,
    TagType.ALBUM_BROWSER.tag_name: handler_tag_album_browser
}

__elem_action_dict: dict = {
    ElementType.GENRE.element_name: handler_element_genre,
    ElementType.ARTIST_BY_INITIAL.element_name: handler_element_artists_by_initial,
    ElementType.ARTIST.element_name: handler_element_artist,
    ElementType.ARTIST_ROLE.element_name: handler_element_artist_role,
    ElementType.ARTIST_ROLE_INITIAL.element_name: handler_element_artist_role_initial,
    ElementType.ARTIST_FOCUS.element_name: handler_element_artist_focus,
    ElementType.GENRE_ARTIST.element_name: handler_element_genre_artist,
    ElementType.ALBUM.element_name: handler_element_album,
    ElementType.ALBUM_VERSION.element_name: handler_element_album_version,
    ElementType.ALBUM_DISC.element_name: handler_element_album_disc,
    ElementType.ALBUM_SONG_SELECTION_BY_ARTIST.element_name: handler_album_song_selection_by_artist,
    ElementType.NAVIGABLE_ALBUM.element_name: handler_element_navigable_album,
    ElementType.ADDITIONAL_ALBUM_ARTISTS.element_name: handler_additional_album_artists,
    ElementType.ALBUM_FOCUS.element_name: handler_element_album_focus,
    ElementType.GENRE_ARTIST_LIST.element_name: handler_element_genre_artists,
    ElementType.GENRE_ALBUM_LIST.element_name: handler_element_genre_album_list,
    ElementType.GENRE_ARTIST_ALBUMS.element_name: handler_element_genre_artist_albums,
    ElementType.PLAYLIST.element_name: handler_element_playlist,
    ElementType.SONG.element_name: handler_element_song,
    ElementType.SONG_ENTRY_NAVIGABLE.element_name: handler_element_song_entry,
    ElementType.SONG_ENTRY_THE_SONG.element_name: handler_element_song_entry_song,
    ElementType.NEXT_RANDOM_SONGS.element_name: handler_element_next_random_songs,
    ElementType.INTERNET_RADIO.element_name: handler_element_radio_station,
    ElementType.ARTIST_TOP_SONGS.element_name: handler_element_artist_top_songs_navigable,
    ElementType.ARTIST_TOP_SONGS_LIST.element_name: handler_element_artist_top_songs_song_list,
    ElementType.ARTIST_SIMILAR.element_name: handler_element_similar_artists,
    ElementType.ARTIST_ALBUMS.element_name: handler_element_artist_albums,
    ElementType.ARTIST_APPEARANCES.element_name: handler_artist_appearances,
    ElementType.RADIO.element_name: handler_radio,
    ElementType.RADIO_SONG_LIST.element_name: handler_radio_song_list,
    ElementType.ALBUM_BROWSE_FILTER_KEY.element_name: handler_album_browse_filter_key,
    ElementType.ALBUM_BROWSE_FILTER_VALUE.element_name: handler_album_browse_filter_value,
    ElementType.ALBUM_BROWSE_MATCHING_ALBUMS.element_name: handler_element_matching_albums
}


def tag_list_to_entries(
        objid,
        tag_list: list[TagType],
        context: TagToEntryContext = None) -> list[dict[str, any]]:
    entry_list: list[dict[str, any]] = list()
    tag: TagType
    for tag in tag_list:
        entry: dict[str, any] = tag_to_entry(
            objid=objid,
            tag=tag,
            context=context)
        entry_list.append(entry)
    return entry_list


def create_entry_for_tag(objid, tag: TagType) -> dict[str, any]:
    tagname: str = tag.tag_name
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TAG.element_name, tagname)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry: dict[str, any] = upmplgutils.direntry(
        id=id,
        pid=objid,
        title=get_tag_type_by_name(tag.tag_name).tag_title)
    return entry


def tag_to_entry(
        objid,
        tag: TagType,
        context: TagToEntryContext = None) -> dict[str, any]:
    entry: dict[str, any] = create_entry_for_tag(objid, tag)
    retrieved_art: RetrievedArt = art_retriever.execute_art_retriever(
        tag=tag,
        context=context)
    upnp_util.set_album_art_from_uri(
        album_art_uri=retrieved_art.art_url if retrieved_art and retrieved_art.art_url else None,
        target=entry)
    return entry


def show_tag_entries(objid, entries: list) -> list:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    if verbose:
        msgproc.log("show_tag_entries starting ...")
    context: TagToEntryContext = TagToEntryContext()
    for tag in TagType:
        if config.is_tag_supported(tag):
            if tag_enabled_in_initial_page(tag):
                if verbose:
                    msgproc.log(f"show_tag_entries adding tag [{tag}] ...")
                start_time: float = time.time()
                # is there a precondition?
                precondition: Callable[[], bool] = (
                    __tag_show_precondition[tag.tag_name]
                    if tag.tag_name in __tag_show_precondition
                    else None)
                do_show: bool = not precondition or precondition()
                if do_show:
                    if verbose:
                        msgproc.log(f"show_tag_entries actually showing tag [{tag}] ...")
                    entries.append(tag_to_entry(
                        objid=objid,
                        tag=tag,
                        context=context))
                    if verbose:
                        msgproc.log(f"show_tag_entries finished showing tag [{tag}]")
                elapsed: float = time.time() - start_time
                msgproc.log(f"show_tag_entries adding tag [{tag}] "
                            f"shown [{'yes' if do_show else 'no'}] "
                            f"took [{elapsed:.3f}].")
        else:
            if verbose:
                msgproc.log(f"show_tag_entries skipping unsupported [{tag}]")
    if verbose:
        msgproc.log("show_tag_entries finished.")
    return entries


@dispatcher.record('browse')
def browse(a):
    start: float = time.time()
    without_cache: bool = config.get_config_param_as_bool(constants.ConfigParam.BROWSE_WITHOUT_CACHE)
    msgproc.log(f"browse: args: --{a}--")
    _initsubsonic()
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    path_list: list[str] = objid.split("/")
    entries = []
    curr_path: str
    last_decoded_path: str = None
    for curr_path in path_list:
        if not _g_myprefix == curr_path:
            try:
                last_decoded_path = codec.decode(curr_path)
            except Exception as ex:
                msgproc.log(f"Could not decode [{curr_path}] [{type(ex)}] [{ex}]")
                return _returnentries(entries, no_cache=without_cache)
    last_path_item: str = path_list[len(path_list) - 1] if path_list and len(path_list) > 0 else None
    if len(path_list) == 1 and _g_myprefix == last_path_item:
        # show tags
        entries = show_tag_entries(objid, entries)
        msgproc.log(f"browse executed (show_tag_entries) collecting [{len(entries if entries else 0)}] entries "
                    f"in [{(time.time() - start):.3f}]")
        return _returnentries(entries, no_cache=without_cache)
    else:
        # decode
        decoded_path: str = last_decoded_path
        item_dict: dict[str, any] = json.loads(decoded_path)
        item_identifier: ItemIdentifier = ItemIdentifier.from_dict(item_dict)
        thing_name: str = item_identifier.get(ItemIdentifierKey.THING_NAME)
        thing_value: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
        msgproc.log(f"browse: item_identifier name: [{thing_name}] value: [{thing_value}]")
        if ElementType.TAG.element_name == thing_name:
            msgproc.log(f"browse: should serve tag: [{thing_value}]")
            tag_handler = __tag_action_dict[thing_value] if thing_value in __tag_action_dict else None
            if tag_handler:
                current_tag: TagType = get_tag_type_by_name(thing_value)
                msgproc.log(f"browse: found tag handler for [{thing_value}]: [{current_tag}]")
                entries = tag_handler(objid, item_identifier, entries)
                msgproc.log(f"browse executed (tag [{current_tag}]) "
                            f"collecting [{len(entries) if entries else 0}] entries "
                            f"in [{(time.time() - start):.3f}]")
                return _returnentries(entries, no_cache=without_cache)
            else:
                msgproc.log(f"browse: tag handler for [{thing_value}] not found")
                return _returnentries(entries, no_cache=without_cache)
        else:  # it's an element
            msgproc.log(f"browse: should serve element: [{thing_name}] [{thing_value}]")
            elem_handler = __elem_action_dict[thing_name] if thing_name in __elem_action_dict else None
            if elem_handler:
                curr_element: ElementType = get_element_type_by_name(thing_name)
                msgproc.log(f"browse: found elem handler for [{thing_name}]: [{curr_element}]")
                entries = elem_handler(objid, item_identifier, entries)
                msgproc.log(f"browse executed (element [{curr_element}]) "
                            f"collecting [{len(entries) if entries else 0}] entries "
                            f"in [{(time.time() - start):.3f}]")
                return _returnentries(entries, no_cache=without_cache)
            else:
                msgproc.log(f"browse: element handler for [{thing_name}] not found")
                return _returnentries(entries, no_cache=without_cache)


def _objidtopath(objid):
    if objid.find(_g_myprefix) != 0:
        raise Exception(f"subsonic: bad objid {objid}: bad prefix")
    return objid[len(_g_myprefix):].lstrip("/")


def log_search_duration(
        search_type: str,
        what: str,
        how_many: int,
        start: float):
    duration: float = time.time() - start
    msgproc.log(f"Search (api) t:[{search_type}] q:[{what}] "
                f"returned [{how_many}] entries in [{duration:.3f}]")


def search_artist_by_artist_name(artist_name: str) -> list[Artist]:
    artist_list: list[Artist] = []
    artist_id_set: set[str] = set()
    # try to search artists by the provided artist_name
    res: SearchResult = connector_provider.get().search(
        query=artist_name,
        artistCount=20,
        albumCount=0,
        songCount=0)
    msgproc.log(f"search_artist_by_artist_name for [{artist_name}] -> [{len(res.getArtists()) if res else 0}] artists")
    current: Artist
    for current in res.getArtists():
        if not current.getId() in artist_id_set:
            # keep track and store in list
            artist_id_set.add(current.getId())
            msgproc.log(f"search_artist_by_artist_name for [{artist_name}] adding [{current.getId()}] [{current.getName()}]")
            artist_list.append(current)
    # we also want to see if we have matching artist id by the provided artist_name
    artist_id_list: list[str] = persistence.get_artist_id_list_by_display_name(artist_display_name=artist_name)
    msgproc.log(f"search_artist_by_artist_name [{artist_name}] -> [{artist_id_list}]")
    artist_id: str
    # split it!
    for artist_id in artist_id_list:
        # avoid duplicates
        if artist_id in artist_id_set:
            continue
        artist_id_set.add(artist_id)
        # load the artist and add to artist_list
        artist_res: Response[Artist] = connector_provider.get().getArtist(artist_id=artist_id)
        if not artist_res or not artist_res.isOk():
            msgproc.log(f"search_artist_by_artist_name could not retrieve artist by id [{artist_id}]")
            continue
        found: Artist = artist_res.getObj()
        msgproc.log(f"search_artist_by_artist_name for [{artist_name}] adding [{found.getId()}] [{found.getName()}]")
        artist_list.append(found)
    return artist_list


def search_songs_by_song_title(song_title: str) -> list[Song]:
    song_list: list[Song] = []
    res: SearchResult = connector_provider.get().search(
        query=song_title,
        artistCount=0,
        albumCount=0,
        songCount=20)
    msgproc.log(f"search_songs_by_song_title for [{song_title}] -> [{len(res.getSongs()) if res else 0}] songs")
    song: Song
    for song in res.getSongs():
        msgproc.log(f"search_songs_by_song_title for song_title [{song_title}] "
                    f"found song_id [{song.getId()}] "
                    f"title [{song.getTitle()}] "
                    f"album_id [{song.getAlbumId()}]")
        # we must load the album
        song_list.append(song)
    return song_list


def search_songs_by_artist(artist_name: str) -> list[Song]:
    song_list: list[Song] = []
    album_id_set: set[str] = set()
    song_id_set: set[str] = set()
    # get the artists by the provided name
    artist_list: list[Artist] = search_artist_by_artist_name(artist_name=artist_name)
    current_artist: Artist
    for current_artist in artist_list:
        msgproc.log(f"search_songs_by_artist for artist_name [{artist_name}] "
                    f"found artist_id [{current_artist.getId()}] [{current_artist.getName()}]")
        # we must load the artist
        artist_res: Response[Artist] = connector_provider.get().getArtist(artist_id=current_artist.getId())
        if not artist_res or not artist_res.isOk():
            msgproc.log(f"search_songs_by_artist could not retrieve artist by id [{current_artist.getId()}]")
            continue
        artist: Artist = artist_res.getObj()
        # get albums by that artist and append to result list
        artist_album_list: list[Album] = artist.getAlbumList()
        album: Album
        for album in artist_album_list:
            if album.getId() in album_id_set:
                continue
            album_id_set.add(album.getId())
            msgproc.log(f"search_songs_by_artist for artist_name [{artist_name}] "
                        f"artist_id [{artist.getId()}] [{artist.getName()}] "
                        f"found album_id [{album.getId()}] "
                        f"title [{album.getTitle()}]")
            # we must load the album
            album_res: Response[Album] = connector_provider.get().getAlbum(albumId=album.getId())
            if not album_res or not album_res.isOk():
                msgproc.log(f"search_songs_by_artist could not retrieve album by id [{album.getId()}]")
                continue
            # add the songs to the list
            song: Song
            for song in album_res.getObj().getSongs():
                if song.getId() in song_id_set:
                    continue
                song_id_set.add(song.getId())
                msgproc.log(f"search_songs_by_artist for artist_name [{artist_name}] "
                            f"artist_id [{artist.getId()}] [{artist.getName()}] "
                            f"album_id [{album.getId()}] "
                            f"title [{album.getTitle()}] "
                            f"adding song: [{song.getTitle()}]")
                song_list.append(song)
    return song_list


def search_albums_by_album_title(album_title: str, found_album_id_set: set[str]) -> list[Album]:
    album_list: list[Album] = []
    res: SearchResult = connector_provider.get().search(
        query=album_title,
        artistCount=0,
        albumCount=20,
        songCount=0)
    msgproc.log(f"search_albums_by_album_title for [{album_title}] -> [{len(res.getAlbums()) if res else 0}] albums")
    album: Album
    for album in res.getAlbums():
        if album.getId() in found_album_id_set:
            continue
        found_album_id_set.add(album.getId())
        msgproc.log(f"search_albums_by_album_title for album_title [{album_title}] "
                    f"found album_id [{album.getId()}] "
                    f"title [{album.getTitle()}]")
        # we must load the album
        loaded: Album = subsonic_util.try_get_album(album_id=album.getId())
        if loaded:
            album_list.append(loaded)
    return album_list


def search_albums_by_song_title(song_title: str, found_album_id_set: set[str]) -> list[Album]:
    album_list: list[Album] = []
    res: SearchResult = connector_provider.get().search(
        query=song_title,
        artistCount=0,
        albumCount=0,
        songCount=20)
    msgproc.log(f"search_albums_by_song_title for [{song_title}] -> [{len(res.getArtists()) if res else 0}] songs")
    song: Song
    for song in res.getSongs():
        if song.getAlbumId() in found_album_id_set:
            continue
        found_album_id_set.add(song.getAlbumId())
        msgproc.log(f"search_albums_by_song_title for song_title [{song_title}] "
                    f"found song_id [{song.getId()}] "
                    f"title [{song.getTitle()}] "
                    f"album_id [{song.getAlbumId()}]")
        # we must load the album
        album: Album = subsonic_util.try_get_album(album_id=song.getAlbumId())
        if album:
            album_list.append(album)
    return album_list


def search_artist_by_title(title: str) -> list[Artist]:
    artist_list: list[Artist] = []
    artist_id_set: set[str] = set()
    res: SearchResult = connector_provider.get().search(
        query=title,
        artistCount=20,
        albumCount=20,
        songCount=20)
    if not res:
        # it's already over
        return artist_list
    msgproc.log(f"search_artist_by_title for [{title}] -> "
                f"[{len(res.getArtists())}] artists "
                f"[{len(res.getAlbums())}] albums "
                f"[{len(res.getSongs())}] songs")
    # process artists
    loaded: Artist
    artist: Artist
    for artist in res.getArtists():
        if artist.getId() in artist_id_set:
            continue
        artist_id_set.add(artist.getId())
        loaded = subsonic_util.try_get_artist(artist_id=artist.getId())
        if loaded:
            artist_list.append(loaded)
    # process albums
    album: Album
    for album in res.getAlbums():
        artist_id_list: list[str] = subsonic_util.get_album_artist_id_list_from_album(album=album)
        curr_artist_id: str
        for curr_artist_id in artist_id_list:
            if curr_artist_id in artist_id_set:
                continue
            artist_id_set.add(curr_artist_id)
            loaded = subsonic_util.try_get_artist(artist_id=curr_artist_id)
            if loaded:
                artist_list.append(loaded)
    # process songs
    song: Song
    for song in res.getSongs():
        artist_occ: list[subsonic_util.ArtistsOccurrence] = subsonic_util.get_artists_in_song_or_album_by_artist_type(
            obj=song,
            item_key=constants.ItemKey.ALBUM_ARTISTS)
        artist_occ.extend(subsonic_util.get_artists_in_song_or_album_by_artist_type(
            obj=song,
            item_key=constants.ItemKey.ARTISTS))
        curr_occ: subsonic_util.ArtistsOccurrence
        for curr_occ in artist_occ:
            if curr_occ.artist_id in artist_id_set:
                continue
            artist_id_set.add(curr_occ.artist_id)
            loaded = subsonic_util.try_get_artist(artist_id=curr_occ.artist_id)
            if loaded:
                artist_list.append(loaded)
    return artist_list


def search_albums_by_artist(artist_name: str) -> list[Album]:
    album_list: list[Album] = []
    album_id_set: set[str] = set()
    # get the artists.
    artist_list: list[Artist] = search_artist_by_artist_name(artist_name=artist_name)
    current_artist: Artist
    for current_artist in artist_list:
        msgproc.log(f"search_albums_by_artist for artist_name [{artist_name}] "
                    f"found artist_id [{current_artist.getId()}] [{current_artist.getName()}]")
        # we must load the artist
        artist_res: Response[Artist] = connector_provider.get().getArtist(artist_id=current_artist.getId())
        if not artist_res or not artist_res.isOk():
            msgproc.log(f"search_albums_by_artist could not retrieve artist by id [{current_artist.getId()}]")
            continue
        artist: Artist = artist_res.getObj()
        # get albums by that artist and append to result list
        artist_album_list: list[Album] = artist.getAlbumList()
        album: Album
        for album in artist_album_list:
            if album.getId() in album_id_set:
                continue
            album_id_set.add(album.getId())
            msgproc.log(f"search_albums_by_artist for artist_name [{artist_name}] "
                        f"artist_id [{artist.getId()}] [{artist.getName()}] "
                        f"found album_id [{album.getId()}] "
                        f"title [{album.getTitle()}]")
            album_list.append(album)
    return album_list


@dispatcher.record('search')
def search(a):
    without_cache: bool = config.get_config_param_as_bool(constants.ConfigParam.SEARCH_WITHOUT_CACHE)
    msgproc.log("search: [%s]" % a)
    _initsubsonic()
    objid = a["objid"]
    entries = []
    # Run the search and build a list of entries in the expected format. See for example
    # ../radio-browser/radiotoentry for an example
    value: str = a["value"]
    field: str = a["field"]
    objkind: str = a["objkind"] if "objkind" in a else None
    origsearch: str = a["origsearch"] if "origsearch" in a else None
    msgproc.log(f"Searching for [{value}] as [{field}] objkind [{objkind}] origsearch [{origsearch}] ...")
    if not value:
        # required, we return nothing if not set
        return _returnentries(entries, no_cache=without_cache)
    kind_specified: bool = objkind and len(objkind) > 0
    field_specified: bool = field and len(field) > 0
    album_as_container: bool = (config.get_config_param_as_bool(constants.ConfigParam.SEARCH_RESULT_ALBUM_AS_CONTAINER)
                                and not config.get_config_param_as_bool(constants.ConfigParam.DISABLE_NAVIGABLE_ALBUM))
    album_entry_options: dict[str, any] = {}
    option_util.set_option(
        options=album_entry_options,
        option_key=OptionKey.APPEND_ARTIST_IN_ALBUM_TITLE,
        option_value=False)
    option_util.set_option(
        options=album_entry_options,
        option_key=OptionKey.SEARCH_RESULT,
        option_value=True)
    resultset_length: int = 0
    search_start: float = time.time()
    if kind_specified and field_specified:
        msgproc.log(f"Both specified: kind [{objkind}] field [{field}]")
        if objkind == KindType.ALBUM:
            # looking for albums.
            if SearchType.ARTIST.getName() == field:
                # looking for albums by artist
                album_list: list[Album] = search_albums_by_artist(artist_name=value)
                for current_album in album_list:
                    # cache_actions.on_album(album=current_album)
                    if album_as_container:
                        entries.append(entry_creator.album_to_navigable_entry(
                            objid=objid,
                            album=current_album))
                    else:
                        entries.append(entry_creator.album_to_entry(
                            objid=objid,
                            album=current_album,
                            options=album_entry_options))
                    resultset_length += 1
            elif SearchType.TRACK.getName() == field:
                found_album_id_set: set[str] = set()
                # we need to find albums by tracks
                album_list: list[Album] = search_albums_by_song_title(song_title=value, found_album_id_set=found_album_id_set)
                # actually the searcher might also want to search album by the album title
                # we will use value as the album title
                album_list.extend(search_albums_by_album_title(album_title=value, found_album_id_set=found_album_id_set))
                for current_album in album_list:
                    # cache_actions.on_album(album=current_album)
                    if album_as_container:
                        entries.append(entry_creator.album_to_navigable_entry(
                            objid=objid,
                            album=current_album))
                    else:
                        entries.append(entry_creator.album_to_entry(
                            objid=objid,
                            album=current_album,
                            options=album_entry_options))
                    resultset_length += 1
                # actually the searcher might also want to search album by the album title
                # we will use value as the album title
            else:
                msgproc.log(f"unimplemented search schema objkind [{objkind}] field [{field}]")
        elif objkind == KindType.TRACK:
            # looking for tracks
            if SearchType.ARTIST.getName() == field:
                # looking for tracks by artist
                song_list: list[Song] = search_songs_by_artist(artist_name=value)
                for current_song in song_list:
                    entries.append(entry_creator.song_to_entry(
                        objid=objid,
                        song=current_song))
                    resultset_length += 1
            elif SearchType.TRACK.getName() == field:
                # looking for track by tracks
                song_list: list[Song] = search_songs_by_song_title(song_title=value)
                for current_song in song_list:
                    entries.append(entry_creator.song_to_entry(
                        objid=objid,
                        song=current_song))
                    resultset_length += 1
            else:
                msgproc.log(f"unimplemented search schema objkind [{objkind}] field [{field}]")
        elif objkind == KindType.ARTIST:
            if SearchType.TRACK.getName() == field:
                # we search artists by any title
                artist_list: list[Artist] = search_artist_by_title(title=value)
                artist: Artist
                for artist in artist_list:
                    entries.append(entry_creator.artist_to_entry(
                        objid=objid,
                        artist=artist))
                    resultset_length += 1
            else:
                msgproc.log(f"unimplemented search schema objkind [{objkind}] field [{field}]")
        else:
            msgproc.log(f"unimplemented search schema objkind [{objkind}] field [{field}]")
    # if not kind_specified:
    elif field_specified:
        if SearchType.ALBUM.getName() == field:
            # search albums by specified value
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=0,
                songCount=0,
                albumCount=config.get_config_param_as_int(constants.ConfigParam.ALBUM_SEARCH_LIMIT))
            album_list: list[Album] = search_result.getAlbums()
            log_search_duration(search_type="album", what=value, how_many=len(album_list), start=search_start)
            current_album: Album
            filters: dict[str, str] = {}
            msgproc.log(f"search: filters = {filters}")
            for current_album in album_list:
                # cache_actions.on_album(album=current_album)
                if album_as_container:
                    entries.append(entry_creator.album_to_navigable_entry(
                        objid=objid,
                        album=current_album))
                else:
                    entries.append(entry_creator.album_to_entry(
                        objid=objid,
                        album=current_album,
                        options=album_entry_options))
                resultset_length += 1
        elif SearchType.TRACK.getName() == field:
            # search tracks by specified value
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=0,
                songCount=config.get_config_param_as_int(constants.ConfigParam.SONG_SEARCH_LIMIT),
                albumCount=0)
            song_list: list[Song] = search_result.getSongs()
            log_search_duration(search_type="track", what=value, how_many=len(song_list), start=search_start)
            sorted_song_list: list[Song] = sort_song_list(song_list).getSongList()
            current_song: Song
            for current_song in sorted_song_list:
                entries.append(entry_creator.song_to_entry(
                    objid=objid,
                    song=current_song))
                resultset_length += 1
        elif SearchType.ARTIST.getName() == field:
            # search artists
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=config.get_config_param_as_int(constants.ConfigParam.ARTIST_SEARCH_LIMIT),
                songCount=0,
                albumCount=0)
            artist_list: list[Artist] = search_result.getArtists()
            log_search_duration(search_type="artist", what=value, how_many=len(artist_list), start=search_start)
            current_artist: Artist
            for current_artist in artist_list:
                roles: list[str] = current_artist.getItem().getByName("roles", [])
                msgproc.log(f"found artist [{current_artist.getName()}] "
                            f"with roles [{roles}] "
                            f"artist art [{subsonic_util.get_artist_cover_art(current_artist)}]")
                entry_title: str = current_artist.getName()
                if roles and len(roles) > 0:
                    entry_title = f"{entry_title} [{', '.join(roles)}]"
                if current_artist.getId() and config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_ID):
                    msgproc.log(f"Adding [{current_artist.getId()}] to [{entry_title}]")
                    entry_title = f"{entry_title} [{current_artist.getId()}]"
                artist_mb_id: str = subsonic_util.get_artist_musicbrainz_id(current_artist)
                if artist_mb_id and config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID):
                    msgproc.log(f"Adding [{artist_mb_id}] to [{entry_title}]")
                    if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID_AS_PLACEHOLDER):
                        entry_title = f"{entry_title} [mb]"
                    else:
                        entry_title = f"{entry_title} [mb:{artist_mb_id}]"
                entries.append(entry_creator.artist_to_entry(
                    objid=objid,
                    artist=current_artist))
                resultset_length += 1
    else:
        # objkind is set
        if SearchType.ALBUM.getName() == objkind:
            # search albums by specified value
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=0,
                songCount=0,
                albumCount=config.get_config_param_as_int(constants.ConfigParam.ALBUM_SEARCH_LIMIT))
            album_list: list[Album] = search_result.getAlbums()
            log_search_duration(search_type="album", what=value, how_many=len(album_list), start=search_start)
            current_album: Album
            filters: dict[str, str] = {}
            msgproc.log(f"search: filters = {filters}")
            for current_album in album_list:
                genre_list: list[str] = current_album.getGenres()
                for curr in genre_list:
                    cache_manager_provider.get().cache_element_multi_value(
                        ElementType.GENRE,
                        curr,
                        current_album.getId())
                if album_as_container:
                    entries.append(entry_creator.album_to_navigable_entry(
                        objid=objid,
                        album=current_album))
                else:
                    entries.append(entry_creator.album_to_entry(
                        objid=objid,
                        album=current_album,
                        options=album_entry_options))
                resultset_length += 1
        elif SearchType.TRACK.getName() == objkind:
            # search tracks by specified value
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=0,
                songCount=config.get_config_param_as_int(constants.ConfigParam.SONG_SEARCH_LIMIT),
                albumCount=0)
            song_list: list[Song] = search_result.getSongs()
            log_search_duration(search_type="song", what=value, how_many=len(song_list), start=search_start)
            sorted_song_list: list[Song] = sort_song_list(song_list).getSongList()
            current_song: Song
            for current_song in sorted_song_list:
                entries.append(entry_creator.song_to_entry(
                    objid=objid,
                    song=current_song))
                resultset_length += 1
        elif SearchType.ARTIST.getName() == objkind:
            # search artists
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=config.get_config_param_as_int(constants.ConfigParam.ARTIST_SEARCH_LIMIT),
                songCount=0,
                albumCount=0)
            artist_list: list[Artist] = search_result.getArtists()
            log_search_duration(search_type="artist", what=value, how_many=len(artist_list), start=search_start)
            current_artist: Artist
            for current_artist in artist_list:
                roles: list[str] = current_artist.getItem().getByName("roles", [])
                msgproc.log(f"found artist [{current_artist.getName()}] "
                            f"with roles [{roles}] "
                            f"artist art [{subsonic_util.get_artist_cover_art(current_artist)}]")
                entries.append(entry_creator.artist_to_entry(
                    objid=objid,
                    artist=current_artist))
                resultset_length += 1
    msgproc.log(f"Search for [{value}] as [{field}] with objkind [{objkind}] returned [{resultset_length}] entries")
    return _returnentries(entries, no_cache=without_cache)


subsonic_init.subsonic_init()
msgproc.log("Subsonic running")
msgproc.mainloop()
