#!/usr/bin/env python3
# Copyright (C) 2023,2024 Giovanni Fulco
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
import html
import upmplgutils
import os

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

import config

from tag_type import TagType, get_tag_type_by_name
from element_type import ElementType, get_element_type_by_name
from search_type import SearchType

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

from album_util import sort_song_list
from album_util import get_album_base_path
from album_util import get_dir_from_path
from album_util import MultiCodecAlbum
from album_util import AlbumTracks
from album_util import get_display_artist
from album_util import get_album_year_str
from album_util import has_year

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

from msgproc_provider import msgproc
from msgproc_provider import dispatcher

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = f"0${constants.plugin_name}$"
upmplgutils.setidprefix(constants.plugin_name)

__tag_initial_page_enabled_default: dict[str, bool] = {
    TagType.RECENTLY_ADDED_ALBUMS.getTagName(): False,
    TagType.NEWEST_ALBUMS.getTagName(): False,
    TagType.RECENTLY_PLAYED_ALBUMS.getTagName(): False,
    TagType.HIGHEST_RATED_ALBUMS.getTagName(): False,
    TagType.MOST_PLAYED_ALBUMS.getTagName(): False,
    TagType.RANDOM.getTagName(): False,
    TagType.FAVOURITE_ALBUMS.getTagName(): False,
    TagType.ALL_ARTISTS.getTagName(): False,
    TagType.ALL_ARTISTS_INDEXED.getTagName(): False,
    TagType.FAVOURITE_ARTISTS.getTagName(): False,
    TagType.RANDOM_SONGS.getTagName(): False,
    TagType.RANDOM_SONGS_LIST.getTagName(): False,
    TagType.FAVOURITE_SONGS.getTagName(): False,
    TagType.FAVOURITE_SONGS_LIST.getTagName(): False,
    TagType.INTERNET_RADIOS.getTagName(): False
}


def __tag_playlists_precondition() -> bool:
    if config.show_empty_playlists:
        return True
    response: Response[Playlists] = connector_provider.get().getPlaylists()
    if not response or not response.isOk():
        return False
    return len(response.getObj().getPlaylists()) > 0


__tag_show_precondition: dict[str, Callable[[], bool]] = {
    TagType.PLAYLISTS.getTagName(): __tag_playlists_precondition
}


def tag_enabled_in_initial_page(tag_type: TagType) -> bool:
    enabled_default: bool = (__tag_initial_page_enabled_default[tag_type.getTagName()]
                             if tag_type.getTagName() in __tag_initial_page_enabled_default
                             else True)
    # msgproc.log(f"Tag enabling key for {tag_type}: [{config.tag_initial_page_enabled_prefix}{tag_type.getTagName()}]")
    enabled_int: int = (int(upmplgutils.getOptionValue(
        f"{config.tag_initial_page_enabled_prefix}{tag_type.getTagName()}",
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
    msgproc.log(f"Subsonic Plugin Release {constants.subsonic_plugin_release}")
    _g_init = True
    return True


def build_streaming_url(track_id: str) -> str:
    streaming_url: str = connector_provider.get().buildSongUrl(
        song_id=track_id,
        format=config.get_transcode_codec(),
        max_bitrate=config.get_transcode_max_bitrate())
    msgproc.log(f"build_streaming_url for track_id: [{track_id}] -> [{streaming_url}]")
    return streaming_url


@dispatcher.record('trackuri')
def trackuri(a):
    msgproc.log(f"trackuri --- {a} ---")
    upmpd_pathprefix = os.environ["UPMPD_PATHPREFIX"]
    # msgproc.log(f"UPMPD_PATHPREFIX: [{upmpd_pathprefix}] trackuri: [{a}]")
    track_id = upmplgutils.trackid_from_urlpath(upmpd_pathprefix, a)
    http_host_port = os.environ["UPMPD_HTTPHOSTPORT"]
    orig_url: str = f"http://{http_host_port}/{constants.plugin_name}/track/version/1/trackId/{track_id}"
    res: Response[Song] = connector_provider.get().getSong(song_id=track_id)
    song: Song = res.getObj() if res else None
    if not song:
        return {'media_url': ""}
    song_suffix: str = song.getSuffix()
    # scrobble if allowed
    scrobble_msg: str = "no"
    if config.server_side_scrobbling:
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
    media_url: str = connector_provider.get().buildSongUrlBySong(
        song=song,
        format=config.get_transcode_codec(),
        max_bitrate=config.get_transcode_max_bitrate())
    # media_url is now set, we can now start collecting information
    # just to show metadata from the subsonic server
    mime_type: str = song.getContentType()
    suffix: str = config.get_transcode_codec() if config.get_transcode_codec() else song_suffix
    kbs: str = (str(config.get_transcode_max_bitrate())
                if config.get_transcode_max_bitrate()
                else (str(song.getBitRate())
                      if song.getBitRate()
                      else None))
    duration: str = str(song.getDuration()) if song.getDuration() else None
    msgproc.log(f"trackuri intermediate_url [{orig_url}] media_url [{media_url}] "
                f"mimetype [{mime_type}] suffix [{suffix}] kbs [{kbs}] "
                f"duration [{duration}] scrobble [{scrobble_msg}]")
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
        ElementType.INTERNET_RADIO.getName(),
        station.getId())
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry: dict[str, any] = {}
    entry['id'] = id
    entry['pid'] = station.getId()
    upnp_util.set_class('object.item.audioItem.audioBroadcast', entry)
    entry['uri'] = stream_url
    upnp_util.set_album_title(station.getName(), entry)
    entry['tp'] = 'it'
    upnp_util.set_artist("Internet Radio", entry)
    guess_mimetype_tuple = mimetypes.guess_type(stream_url)
    mime_type: str = guess_mimetype_tuple[0] if guess_mimetype_tuple else None
    msgproc.log(f"_station_to_entry guessed mimetype [{mime_type}] for stream_url [{stream_url}]")
    if not mime_type:
        mime_type = "audio/mpeg"
    entry['res:mime'] = mime_type
    return entry


def _song_data_to_entry(objid, entry_id: str, song: Song) -> dict:
    msgproc.log("entering _song_data_to_entry ...")
    entry: dict[str, any] = {}
    entry['id'] = entry_id
    entry['pid'] = song.getId()
    upnp_util.set_class_music_track(entry)
    entry['uri'] = entry_creator.build_intermediate_url(track_id=song.getId())
    title: str = song.getTitle()
    upnp_util.set_album_title(title, entry)
    entry['tp'] = 'it'
    entry['discnumber'] = song.getDiscNumber()
    upnp_util.set_track_number(song.getTrack(), entry)
    upnp_util.set_artist(get_display_artist(song.getArtist()), entry)
    entry['upnp:album'] = song.getAlbum()
    entry['upnp:genre'] = song.getGenre()
    entry['res:mime'] = song.getContentType()
    albumArtURI: str = connector_provider.get().buildCoverArtUrl(song.getId())
    upnp_util.set_album_art_from_uri(albumArtURI, entry)
    entry['duration'] = str(song.getDuration())
    return entry


def _load_album_tracks(
        objid,
        album_id: str,
        album_version_path: str,
        entries: list) -> list:
    # msgproc.log(f"_load_album_tracks with album_version_path [{album_version_path}]")
    album_tracks: AlbumTracks = get_album_tracks(album_id)
    album_quality_badge: str = entry_creator.get_track_list_badge(
        track_list=album_tracks.getSongList(),
        list_identifier=album_id)
    if config.debug_badge_mngmt:
        msgproc.log(f"Quality badge for [{album_id}] -> [{album_quality_badge}]")
    if album_quality_badge:
        persistence.save_quality_badge(
            album_id=album_id,
            quality_badge=album_quality_badge)
    song_list: list[Song] = album_tracks.getSongList()
    albumArtURI: str = album_tracks.getArtUri()
    multi_codec_album: MultiCodecAlbum = album_tracks.getMultiCodecAlbum()
    current_base_path: str = None
    track_num: int = 0
    album_path_set: set[str] = set()
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
            # Wait for a test case to make suie it still works...
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
                option_key=OptionKey.ALBUM_ART_URI,
                option_value=albumArtURI)
            option_util.set_option(
                options=options,
                option_key=OptionKey.MULTI_CODEC_ALBUM,
                option_value=multi_codec_album)
            entry = entry_creator.song_to_entry(
                objid=objid,
                song=current_song,
                options=options)
            entries.append(entry)
    # show paths if requested
    if config.show_paths_in_album():
        curr_album_path: str
        cnt: int = 1
        for curr_album_path in album_path_set:
            msgproc.log(f"_load_album_tracks album_paths for [{album_id}] "
                        f"-> [{curr_album_path}] [{cnt}/{len(album_path_set)}]")
            cnt += 1
    return entries


def _load_albums_by_type(
        objid: any,
        entries: list,
        tag_type: TagType,
        offset: int = 0,
        size: int = config.items_per_page,
        fromYear: any = None,
        toYear: any = None,
        options: dict[str, any] = dict()) -> list:
    use_last_for_next: bool = option_util.get_option(options=options, option_key=OptionKey.USE_LAST_FOR_NEXT)
    request_size: int = size + 1 if use_last_for_next else size
    albumList: list[Album] = subsonic_util.get_albums(
        tag_type.getQueryType(),
        size=request_size,
        offset=str(offset),
        fromYear=fromYear,
        toYear=toYear)
    msgproc.log(f"Requested [{request_size}] albums from offset [{offset}], got [{len(albumList)}]")
    current_album: Album
    tag_cached: bool = False
    counter: int = offset
    to_show: list[Album] = albumList[0:min(len(albumList), size)]
    add_next: bool = len(albumList) == request_size
    iteration: int = 0
    for current_album in to_show:
        iteration += 1
        counter += 1
        if config.prepend_number_in_album_list:
            option_util.set_option(
                options=options,
                option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE,
                option_value=counter)
        cache_actions.on_album(current_album)
        if tag_type and (not tag_cached) and (offset == 0):
            cache_manager_provider.get().cache_element_value(
                ElementType.TAG,
                tag_type.getTagName(),
                current_album.getId())
            tag_cached = True
        if config.disable_navigable_album == 1:
            entries.append(entry_creator.album_to_entry(
                objid=objid,
                album=current_album,
                options=options))
        else:
            entries.append(entry_creator.album_to_navigable_entry(
                objid=objid,
                album=current_album,
                options=options))
    if add_next:
        for_next: Album = albumList[len(albumList) - 1]
        next_page: dict[str, any] = _create_tag_next_entry(
            objid=objid,
            tag=tag_type,
            offset=offset + len(entries))
        upnp_util.set_album_art_from_album_id(
            album_id=for_next.getId(),
            target=next_page)
        entries.append(next_page)
    return entries


def _load_albums_by_artist(artist_id: str) -> list[Album]:
    artist_response: Response[Artist] = connector_provider.get().getArtist(artist_id)
    if not artist_response.isOk():
        raise Exception(f"Cannot get albums for artist_id {artist_id}")
    return artist_response.getObj().getAlbumList()


def _albums_by_artist_to_entries(
        objid: any,
        artist_id: str,
        album_list: list[Album],
        offset: int,
        entries: list) -> list:
    current_album: Album
    counter: int = offset
    for current_album in album_list:
        counter += 1
        if current_album.getArtistId():
            cache_actions.on_album(current_album)
        genre_list: list[str] = current_album.getGenres()
        for curr in genre_list:
            # what do I do with these genres?
            pass
        options: dict[str, any] = {}
        option_util.set_option(
            options=options,
            option_key=OptionKey.PREPEND_ARTIST_IN_ALBUM_TITLE,
            option_value=False)
        option_util.set_option(
            options=options,
            option_key=OptionKey.SKIP_ARTIST_ID,
            option_value=artist_id)
        if config.prepend_number_in_album_list:
            option_util.set_option(
                options=options,
                option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE,
                option_value=counter)
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
                    artist_id=current_artist.getId(),
                    entry_name=current_artist.getName())
                # if artist has art, set that art for artists by initial tile
                if counter < offset:
                    counter += 1
                    continue
                if counter >= offset + config.items_per_page:
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
            element_type.getName(),
            codec.encode(artist_initial))
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.items_per_page)
        next_id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        entries.append(next_entry)
    return entries


def _create_list_of_genres(objid, entries: list) -> list:
    genres_response: Response[Genres] = request_cache.get_genres()
    if not genres_response.isOk():
        return entries
    genre_list = genres_response.getObj().getGenres()
    genre_list.sort(key=lambda x: x.getName())
    current_genre: Genre
    for current_genre in genre_list:
        if current_genre.getAlbumCount() > 0:
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
    msgproc.log(f"__load_artists started at offset [{offset}] tag [{tag}]")
    counter: int = 0
    artists_response: Response[Artists] = request_cache.get_artists()
    if not artists_response.isOk():
        return entries
    artists_initial: list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial: ArtistsInitial
    broke_out: bool = False
    for current_artists_initial in artists_initial:
        current_artist: ArtistListItem
        for current_artist in current_artists_initial.getArtistListItems():
            if counter < offset:
                counter += 1
                continue
            if counter >= offset + config.items_per_page:
                broke_out = True
                break
            counter += 1
            entries.append(entry_creator.artist_to_entry(
                objid=objid,
                artist_id=current_artist.getId(),
                entry_name=current_artist.getName(),
                options=options))
    if broke_out:
        next_entry: dict[str, any] = _create_tag_next_entry(
            objid=objid,
            tag=tag,
            offset=offset + config.items_per_page)
        entries.append(next_entry)
    msgproc.log(f"__load_artists complete with [{len(entries)}] entries")
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
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), playlist_entry.getId())
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = playlist_entry.getId()
    upnp_util.set_class_music_track(entry)
    song_uri: str = entry_creator.build_intermediate_url(track_id=playlist_entry.getId())
    entry['uri'] = song_uri
    title: str = playlist_entry.getTitle()
    entry['tt'] = title
    entry['tp'] = 'it'
    upnp_util.set_track_number(playlist_entry.getTrack(), entry)
    upnp_util.set_artist(get_display_artist(playlist_entry.getArtist()), entry)
    entry['upnp:album'] = playlist_entry.getAlbum()
    entry['res:mime'] = playlist_entry.getContentType()
    albumArtURI: str = connector_provider.get().buildCoverArtUrl(playlist_entry.getId())
    if albumArtURI:
        upnp_util.set_album_art_from_uri(albumArtURI, entry)
    entry['duration'] = str(playlist_entry.getDuration())
    return entry


def _create_list_of_playlist_entries(objid, playlist_id: str, entries: list) -> list:
    response: Response[Playlist] = connector_provider.get().getPlaylist(playlist_id)
    if not response.isOk():
        return entries
    entry_list: list[PlaylistEntry] = response.getObj().getEntries()
    playlist_entry: PlaylistEntry
    for playlist_entry in entry_list:
        entry: dict[str, any] = _playlist_entry_to_entry(
            objid,
            playlist_entry)
        entries.append(entry)
    return entries


def _create_list_of_artist_initials(
        objid,
        entries: list,
        options: dict[str, any] = dict()) -> list:
    artists_response: Response[Artists] = request_cache.get_artists()
    if not artists_response.isOk():
        return entries
    # msgproc.log(f"_create_list_of_artist_initials artists loaded ...")
    artists_initial: list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial: ArtistsInitial
    for current_artists_initial in artists_initial:
        # msgproc.log(f"_create_list_of_artist_initials processing [{current_artists_initial.getName()}] ...")
        entry: dict[str, any] = entry_creator.artist_initial_to_entry(
            objid=objid,
            artist_initial=current_artists_initial.getName(),
            options=options)
        entries.append(entry)
        # populate cache of artist by initial
    return entries


def _present_album(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album_version_path: str = None
    if item_identifier.has(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64):
        avp_encoded: str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64)
        album_version_path = codec.decode(avp_encoded)
    return _load_album_tracks(objid, album_id, album_version_path, entries)


def _create_tag_next_entry(
        objid,
        tag: TagType,
        offset: int) -> dict:
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TAG.getName(), tag.getTagName())
    identifier.set(ItemIdentifierKey.OFFSET, offset)
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
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
        if config.prepend_number_in_album_list:
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
        msgproc.log(f"Cannot handle tag [{tag_type.getTagName()}] [{type(ex)}] [{ex}]")
        return list()


def handler_tag_recently_added_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.RECENTLY_ADDED_ALBUMS, entries)


def handler_tag_newest_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.NEWEST_ALBUMS, entries)


def handler_tag_most_played(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.MOST_PLAYED_ALBUMS, entries)


def handler_tag_favourites(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return __handler_tag_album_listype(objid, item_identifier, TagType.FAVOURITE_ALBUMS, entries)


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
    item_identifier.set(ItemIdentifierKey.SONG_AS_ENTRY, False)
    return _get_random_songs(objid, item_identifier, entries)


def handler_tag_favourite_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    item_identifier.set(ItemIdentifierKey.SONG_AS_ENTRY, True)
    return _get_favourite_songs(objid, item_identifier, entries)


def handler_tag_favourite_songs_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    item_identifier.set(ItemIdentifierKey.SONG_AS_ENTRY, False)
    return _get_favourite_songs(objid, item_identifier, entries)


def handler_element_next_random_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return _get_random_songs(objid, item_identifier, entries)


def handler_element_song_entry_song(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    msgproc.log("handler_element_song_entry_song start")
    song_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_element_song_entry_song start song_id {song_id}")
    song: Song = connector_provider.get().getSong(song_id).getObj()
    if song:
        entries.append(entry_creator.song_to_entry(objid=objid, song=song))
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
    art_id = song.getAlbumId()
    select_element: ElementType = (
        ElementType.SONG_ENTRY_NAVIGABLE if song_as_entry else
        ElementType.SONG_ENTRY_THE_SONG)
    identifier: ItemIdentifier = ItemIdentifier(
        select_element.getName(),
        song.getId())
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, name)
    upnp_util.set_album_art_from_album_id(
        art_id,
        entry)
    return entry


def handler_element_song_entry(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    msgproc.log("handler_element_song_entry start")
    song_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_element_song_entry start song_id {song_id}")
    song: Song = connector_provider.get().getSong(song_id).getObj()
    song_identifier: ItemIdentifier = ItemIdentifier(ElementType.SONG_ENTRY_THE_SONG.getName(), song_id)
    song_entry_id: str = identifier_util.create_objid(
        objid,
        identifier_util.create_id_from_identifier(song_identifier))
    song_entry = upmplgutils.direntry(song_entry_id, objid, "Song")
    upnp_util.set_album_art_from_album_id(song.getAlbumId(), song_entry)
    entries.append(song_entry)
    msgproc.log(f"handler_element_song_entry start song_id {song_id} go on with album")
    album: Album = connector_provider.get().getAlbum(song.getAlbumId()).getObj()
    options: dict[str, any] = dict()
    option_util.set_option(options=options, option_key=OptionKey.FORCE_LOAD_QUALITY_BADGE, option_value=True)
    entries.append(entry_creator.album_to_entry(objid=objid, album=album, options=options))
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
                artist_id=artist.getId(),
                entry_name=artist.getName()))
    return entries


def _get_favourite_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    song_as_entry: bool = item_identifier.get(ItemIdentifierKey.SONG_AS_ENTRY, True)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    response: Response[Starred] = request_cache.get_starred()
    if not response.isOk():
        raise Exception("Cannot retrieve starred items")
    song_list: list[Song] = response.getObj().getSongs()
    need_next: bool = song_list and len(song_list) > (offset + config.items_per_page)
    song_slice: list[Song] = song_list[offset:min(len(song_list), offset + config.items_per_page)]
    current_song: Song
    for current_song in song_slice if song_slice and len(song_slice) > 0 else []:
        entry: dict[str, any] = _song_to_song_entry(
            objid=objid,
            song=current_song,
            song_as_entry=song_as_entry)
        entries.append(entry)
    if need_next:
        next_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.TAG.getName(),
            TagType.FAVOURITE_SONGS_LIST.getTagName())
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.items_per_page)
        next_id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        entries.append(next_entry)
    return entries


def _get_random_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    song_as_entry: bool = item_identifier.get(ItemIdentifierKey.SONG_AS_ENTRY, True)
    response: Response[RandomSongs] = connector_provider.get().getRandomSongs(size=config.items_per_page)
    if not response.isOk():
        raise Exception("Cannot get random songs")
    song_list: list[Song] = response.getObj().getSongs()
    song: Song
    for song in song_list:
        song_entry = _song_to_song_entry(
            objid=objid,
            song=song,
            song_as_entry=song_as_entry)
        entries.append(song_entry)
    # no offset, so we always add next
    next_identifier: ItemIdentifier = ItemIdentifier(ElementType.NEXT_RANDOM_SONGS.getName(), "some_random_song")
    next_identifier.set(ItemIdentifierKey.SONG_AS_ENTRY, song_as_entry)
    next_id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(next_identifier))
    next_entry: dict[str, any] = upmplgutils.direntry(
        id=next_id,
        pid=objid,
        title="Next")
    entries.append(next_entry)
    return entries


def handler_tag_genres(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    return _create_list_of_genres(objid, entries)


def _genre_add_artists_node(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    genre: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_genre_add_artists_node genre {genre}")
    identifier: ItemIdentifier = ItemIdentifier(ElementType.GENRE_ARTIST_LIST.getName(), genre)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    name: str = "Artists"  # TODO parametrize maybe?
    artists_entry = upmplgutils.direntry(id, objid, name)
    art_id: str = get_random_art_by_genre(genre)
    if art_id:
        upnp_util.set_album_art_from_album_id(
            art_id,
            artists_entry)
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
        ElementType.GENRE_ALBUM_LIST.getName(),
        genre)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    identifier.set(ItemIdentifierKey.OFFSET, offset)
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    name: str = "Albums" if offset == 0 else "Next"  # TODO parametrize maybe?
    artists_entry = upmplgutils.direntry(id, objid, name)
    if offset == 0:
        art_id: str = get_random_art_by_genre(genre)
        if art_id:
            upnp_util.set_album_art_from_album_id(
                art_id,
                artists_entry)
    entries.append(artists_entry)
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
    artist_id_list: list[subsonic_util.ArtistIdAndName] = subsonic_util.load_artists_by_genre(
        genre=genre,
        artist_offset=offset,
        max_artists=config.max_artists_per_page)
    # present the list of artists
    item_count: int = 0
    needs_next: bool = False
    current: subsonic_util.ArtistIdAndName
    for current in artist_id_list:
        # load artist if it has an id
        if current.id:
            msgproc.log(f"executing entry_creator.genre_artist_to_entry with artist_id [{current.id}] [{current.name}]")
            entries.append(entry_creator.genre_artist_to_entry(
                objid=objid,
                genre=genre,
                artist_id=current.id,
                artist_name=current.name))
            item_count += 1
            if item_count >= config.max_artists_per_page:
                # we need the next button
                needs_next = True
                break
    if needs_next:
        next_offset: int = offset + config.max_artists_per_page
        msgproc.log(f"handler_element_genre_artists for [{genre}] next offset is [{next_offset}] ...")
        # add the next button
        next_identifier: ItemIdentifier = ItemIdentifier(ElementType.GENRE_ARTIST_LIST.getName(), genre)
        next_identifier.set(ItemIdentifierKey.OFFSET, next_offset)
        next_identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
        next_id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
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
    need_next: bool = album_list and len(album_list) > (offset + config.items_per_page)
    album_slice: list[Album] = album_list[offset:min(len(album_list), offset + config.items_per_page)]
    current_album: Album
    counter: int = offset
    for current_album in album_slice if album_slice and len(album_slice) > 0 else []:
        counter += 1
        options: dict[str, any] = {}
        if config.prepend_number_in_album_list:
            option_util.set_option(
                options=options,
                option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE,
                option_value=counter)
        option_util.set_option(
            options=options,
            option_key=OptionKey.PREPEND_ARTIST_IN_ALBUM_TITLE,
            option_value=False)
        entry: dict[str, any] = entry_creator.album_to_entry(
            objid=objid,
            album=current_album,
            options=options)
        entries.append(entry)
    if need_next:
        next_identifier: ItemIdentifier = ItemIdentifier(ElementType.GENRE_ARTIST_ALBUMS.getName(), artist_id)
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.items_per_page)
        next_identifier.set(ItemIdentifierKey.GENRE_NAME, genre_name)
        next_id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
        entries.append(next_entry)
    return entries


def handler_element_genre_album_list(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    msgproc.log("handler_element_genre_album_list")
    genre: str = item_identifier.get(ItemIdentifierKey.GENRE_NAME)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET)
    msgproc.log(f"handler_element_genre_album_list genre {genre} offset {offset}")
    album_list_response: Response[AlbumList] = connector_provider.get().getAlbumList(
        ltype=ListType.BY_GENRE,
        genre=genre,
        offset=offset,
        size=config.items_per_page)
    if not album_list_response.isOk():
        return entries
    album_list: list[Album] = album_list_response.getObj().getAlbums()
    msgproc.log(f"got {len(album_list)} albums for genre {genre} from offset {offset}")
    counter: int = offset
    current_album: Album
    for current_album in album_list:
        counter += 1
        options: dict[str, any] = dict()
        if config.prepend_number_in_album_list:
            option_util.set_option(
                options=options,
                option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE,
                option_value=counter)
        entries.append(entry_creator.album_to_entry(
            objid=objid,
            album=current_album,
            options=options))
    if len(album_list) == config.items_per_page:
        # create next button
        entries = _genre_add_albums_node(
            objid=objid,
            item_identifier=item_identifier,
            offset=offset + config.items_per_page,
            entries=entries)
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


def handler_tag_artists_favourite(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    response: Response[Starred] = request_cache.get_starred()
    if not response.isOk():
        raise Exception("Cannot retrieve starred items")
    artist_list: list[Artist] = response.getObj().getArtists()
    need_next: bool = artist_list and len(artist_list) > (offset + config.items_per_page)
    artist_slice: list[Artist] = artist_list[offset:min(len(artist_list), offset + config.items_per_page)]
    current_artist: Artist
    for current_artist in artist_slice if artist_slice and len(artist_slice) > 0 else []:
        entry: dict[str, any] = entry_creator.artist_to_entry(
            objid=objid,
            artist_id=current_artist.getId(),
            entry_name=current_artist.getName())
        entries.append(entry)
    if need_next:
        next_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.TAG.getName(),
            TagType.FAVOURITE_ARTISTS.getTagName())
        next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.items_per_page)
        next_id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(next_identifier))
        next_entry: dict[str, any] = upmplgutils.direntry(
            next_id,
            objid,
            title="Next")
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
    artist_initial: str = codec.decode(encoded_artist_initial)
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
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset: int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    if config.debug_artist_albums:
        msgproc.log(f"handler_element_artist_albums artist_id {artist_id} offset {offset}")
    album_list: list[Album]
    try:
        album_list = _load_albums_by_artist(artist_id)
    except Exception as ex:
        msgproc.log(f"Cannot get albums for artistId {artist_id} [{type(ex)}] [{ex}]")
        album_list = list()
    if config.debug_artist_albums:
        msgproc.log(f"handler_element_artist_albums artist_id {artist_id} found {len(album_list)} albums")
    next_needed: bool = len(album_list) > (config.items_per_page + offset)
    num_albums_to_show: int = (config.items_per_page
                               if next_needed or len(album_list) == config.items_per_page
                               else len(album_list) % config.items_per_page)
    if config.debug_artist_albums:
        msgproc.log(f"handler_element_artist_albums artist_id {artist_id} "
                    f"next_needed {next_needed} num_albums_to_show {num_albums_to_show}")
    if num_albums_to_show > 0:
        to_show: list[Album] = album_list[offset: offset + num_albums_to_show]
        entries = _albums_by_artist_to_entries(
            objid=objid,
            artist_id=artist_id,
            album_list=to_show,
            offset=offset,
            entries=entries)
        if config.debug_artist_albums:
            msgproc.log(f"Found {len(entries)} albums for artist_id {artist_id}")
        if next_needed:
            next_identifier: ItemIdentifier = ItemIdentifier(ElementType.ARTIST_ALBUMS.getName(), artist_id)
            next_identifier.set(ItemIdentifierKey.OFFSET, offset + config.items_per_page)
            next_id: str = identifier_util.create_objid(
                objid,
                identifier_util.create_id_from_identifier(next_identifier))
            next_entry: dict[str, any] = upmplgutils.direntry(
                next_id,
                objid,
                title="Next")
            next_album: Album = album_list[offset + num_albums_to_show]
            upnp_util.set_album_art_from_album_id(album_id=next_album.getId(), target=next_entry)
            entries.append(next_entry)
    return entries


def handler_element_artist(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist_response: Response[Artist] = None
    try:
        artist_response = connector_provider.get().getArtist(artist_id)
    except Exception as ex:
        msgproc.log(f"Cannot get artist with id {artist_id} [{type(ex)}] [{ex}]")
    if not artist_response or not artist_response.isOk():
        msgproc.log(f"Cannot retrieve artist by id {artist_id}")
        return entries
    artist: Artist = artist_response.getObj()
    artist_mb_id: str = artist.getItem().getByName(constants.item_key_musicbrainz_id)
    if artist_mb_id:
        # at least the musicbrainz artist id is logged
        msgproc.log(f"Artist [{artist_id}] -> [{artist.getName()}] [{artist_mb_id}]")
        # cache it!
        cache_actions.store_artist_mbid(artist_id, artist_mb_id)
    artist_album_identifier: ItemIdentifier = ItemIdentifier(ElementType.ARTIST_ALBUMS.getName(), artist_id)
    artist_album_id: str = identifier_util.create_objid(
        objid,
        identifier_util.create_id_from_identifier(artist_album_identifier))
    albums_entry: dict[str, any] = upmplgutils.direntry(
        artist_album_id,
        objid,
        title="Albums")
    # use one album for this entry image
    album_list: list[Album] = artist.getAlbumList()
    appearance_album_list: list[Album] = subsonic_util.get_artist_albums_as_appears_on(
        artist_id=artist_id,
        album_list=album_list)
    msgproc.log(f"Artist [{artist_id}] has \"Appears on\" albums: [{len(appearance_album_list)}]")
    artist_release_types: dict[subsonic_util.AlbumReleaseTypes, int] = subsonic_util.get_release_types(album_list)
    msgproc.log(f"Artist [{artist_id}] release types counters are: [{artist_release_types}]")
    uncategorized_only: bool = subsonic_util.uncategorized_releases_only(artist_release_types)
    msgproc.log(f"Artist [{artist_id}] uncategorized releases only: [{uncategorized_only}]")
    select_album: Album = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
    upnp_util.set_album_art_from_album_id(
        select_album.getId() if select_album else None,
        albums_entry)
    msgproc.log(f"handler_element_artist for "
                f"{artist_id} -> album_id: {select_album.getId() if select_album else None}")
    entries.append(albums_entry)
    # add artist focus ...
    artist_focus_entry = entry_creator.artist_id_to_artist_focus(objid, artist_id)
    # possibly select another album for artist focus
    select_album = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
    upnp_util.set_album_art_from_album_id(
        select_album.getId() if select_album else None,
        artist_focus_entry)
    entries.append(artist_focus_entry)
    return entries


def handler_element_artist_focus(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    artist_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist_response: Response[Artist] = None
    try:
        artist_response = connector_provider.get().getArtist(artist_id)
    except Exception as ex:
        msgproc.log(f"handler_element_artist_focus Cannot get artist with id {artist_id} [{type(ex)}] [{ex}]")
    if not artist_response or not artist_response.isOk():
        msgproc.log(f"handler_element_artist_focus Cannot retrieve artist by id {artist_id}")
        return entries
    artist: Artist = artist_response.getObj()
    try:
        top_songs_entry_list: list[dict[str, any]] = _artist_to_top_songs_entry(
            objid,
            artist_id,
            artist.getName())
        top_songs_entry: dict[str, any]
        for top_songs_entry in top_songs_entry_list:
            entries.append(top_songs_entry)
    except Exception as ex:
        msgproc.log(f"Cannot get top songs for artist_id [{artist_id}] [{type(ex)}] [{ex}]")
    similar_artists_entry: dict[str, any] = _similar_artists_for_artist(objid, artist_id)
    if similar_artists_entry:
        entries.append(similar_artists_entry)
    radio_entry_list: list[dict[str, any]] = _radio_entry(
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
    # artist_name: str = f"Artist: {artist.getName()}"
    artist_name: str = artist.getName()
    artist_entry: dict[str, any] = entry_creator.artist_to_entry(
        objid=objid,
        artist_id=artist.getId(),
        entry_name=artist_name)
    # select first cover from album selection for artist within genre
    artist_entry_album_id: str = album_list[0].getId() if album_list and len(album_list) > 0 else None
    upnp_util.set_album_art_from_album_id(artist_entry_album_id, artist_entry)
    entries.append(artist_entry)
    # entry for albums from artist within genre
    album_list_identifier: ItemIdentifier = ItemIdentifier(ElementType.GENRE_ARTIST_ALBUMS.getName(), artist_id)
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
    upnp_util.set_album_art_from_album_id(
        album_list_entry_album_id,
        album_list_entry)
    entries.append(album_list_entry)
    return entries


def handler_element_album_focus(
        objid,
        item_identifier: ItemIdentifier,
        entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album_res: Response[Album] = connector_provider.get().getAlbum(album_id)
    album: Album = album_res.getObj() if album_res and album_res.isOk() else None
    if not album:
        msgproc.log(f"Cannot retrieve album with id [{album_id}]")
        return entries
    start_time: float = time.time()
    get_top_songs_elapsed_time: float = 0
    get_top_songs_start_time: float = time.time()
    get_top_songs_elapsed_time: float = None
    if album.getArtistId():
        try:
            top_songs_entry_list: list[dict[str, any]] = _artist_to_top_songs_entry(
                objid,
                album.getArtistId(),
                album.getArtist())
            top_songs_entry: dict[str, any]
            get_top_songs_elapsed_time = time.time() - get_top_songs_start_time
            for top_songs_entry in top_songs_entry_list:
                entries.append(top_songs_entry)
        except Exception as ex:
            msgproc.log(f"handler_element_navigable_album cannot add top songs entry [{type(ex)}] [{ex}]")
    else:
        msgproc.log("handler_element_navigable_album no artistId for "
                    f"album [{album.getId()}] [{album.getTitle()}], "
                    "not creating top songs entry")
    get_similar_artists_start_time: float = time.time()
    get_similar_artists_elapsed_time: float = None
    if album.getArtistId():
        similar_artist_entry: dict[str, any] = _similar_artists_for_artist(objid, album.getArtistId())
        get_similar_artists_elapsed_time = time.time() - get_similar_artists_start_time
        if similar_artist_entry:
            entries.append(similar_artist_entry)
    else:
        msgproc.log(f"handler_element_navigable_album no artistId for "
                    f"album [{album.getId()}] [{album.getTitle()}], "
                    "not creating similar artists entry")
    get_radio_entry_list_start_time: float = time.time()
    get_radio_entry_list_elapsed_time: float = None
    _radio_entry_list: list[dict[str, any]] = _radio_entry(
        objid=objid,
        iid=album.getId(),
        radio_entry_type=RadioEntryType.ALBUM_RADIO)
    get_radio_entry_list_elapsed_time = time.time() - get_radio_entry_list_start_time
    radio_entry: dict[str, any]
    for radio_entry in _radio_entry_list if _radio_entry_list else []:
        entries.append(radio_entry)
    elapsed_time: float = time.time() - start_time
    msgproc.log(f"handler_element_navigable_album for album_id {album_id} took [{elapsed_time:.3f}] seconds")
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
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    response: Response[Album] = connector_provider.get().getAlbum(album_id)
    if not response.isOk():
        raise Exception(f"Cannot load album with album_id {album_id}")
    album: Album = response.getObj()
    album_mb_id: str = album.getItem().getByName(constants.item_key_musicbrainz_id)
    media_type: str = album.getItem().getByName("mediaType")
    release_types: str = album.getItem().getByName(constants.item_key_release_types, [])
    msgproc.log(f"album [{album_id}] -> "
                f"mb_id: [{album_mb_id}] "
                f"mediaType: [{media_type}] "
                f"releaseTypes: [{release_types}]")
    album_entry: dict[str, any] = entry_creator.album_to_entry(objid=objid, album=album)
    # which album art?
    album_art_uri: str = upnp_util.get_album_art_uri(album_entry)
    msgproc.log(f"handler_element_navigable_album for album: {album_id} -> [{album_art_uri}]")
    # set title a little differently here ...
    title: str = album.getTitle()
    # album year if available
    if has_year(album):
        title = f"{title} [{get_album_year_str(album)}]"
    # badge if available
    album_quality_badge: str = entry_creator.get_album_quality_badge(album=album, force_load=True)
    if album_quality_badge:
        title = f"{title} [{album_quality_badge}]"
    if config.show_album_id_in_album():
        title = f"{title} [{album_id}]"
    if album_mb_id and config.show_album_mb_id_in_album():
        title = f"{title} [{album_mb_id}]"
    upnp_util.set_album_title(title, album_entry)
    entries.append(album_entry)
    # add artist if needed
    skip_artist_id: str = item_identifier.get(ItemIdentifierKey.SKIP_ARTIST_ID)
    skip_artist_id_set: set[str] = set()
    if skip_artist_id:
        skip_artist_id_set.add(skip_artist_id)
    if album.getArtistId():
        if album.getArtistId() not in skip_artist_id_set:
            artist_entry: dict[str, any] = entry_creator.artist_entry_for_album(objid, album)
            entries.append(artist_entry)
            skip_artist_id_set.add(album.getArtistId())
        # additional...
        additional: list[subsonic_util.ArtistsOccurrence] = subsonic_util.get_artists_in_album(album=album)
        curr_additional: subsonic_util.ArtistsOccurrence
        for curr_additional in additional:
            msgproc.log(f"For album_id [{album.getId()}] "
                        f"found artist id:[{curr_additional.id}] "
                        f"name:[{curr_additional.name}]")
        curr_artist: subsonic_util.ArtistsOccurrence
        for curr_artist in additional:
            if curr_artist.id not in skip_artist_id_set:
                entry_name: str = curr_artist.name
                if config.show_artist_id():
                    entry_name = f"{entry_name} [{curr_artist.id}]"
                # do we know the artist mb id?
                if config.show_artist_mb_id():
                    # see if we have it cached.
                    artist_mb_id: str = cache_actions.get_artist_mb_id(curr_artist.id)
                    if artist_mb_id:
                        msgproc.log(f"Found mbid for artist_id [{curr_artist.id}] -> [{artist_mb_id}]")
                        entry_name = f"{entry_name} [{artist_mb_id}]"
                    else:
                        msgproc.log(f"Cannot find mbid for artist_id [{curr_artist.id}]")
                entries.append(entry_creator.artist_to_entry(
                    objid=objid,
                    artist_id=curr_artist.id,
                    entry_name=entry_name))
                skip_artist_id_set.add(curr_artist.id)
    else:
        if not album.getArtistId():
            # we skip the artist because we have no artist_id
            msgproc.log(f"handler_element_navigable_album no artistId for "
                        f"album [{album.getId()}] [{album.getTitle()}], "
                        "not creating artist entry")
    entry: dict[str, any] = entry_creator.album_id_to_album_focus(
        objid,
        album_id=album.getId())
    entries.append(entry)
    return entries


def __getSimilarSongs(iid: str, count: int = 10) -> list[dict[str, any]]:
    try:
        res: Response[SimilarSongs] = connector_provider.get().getSimilarSongs(iid=iid, count=count)
        if not res.isOk():
            raise Exception(f"Cannot get similar songs for iid {iid}")
        return res
    except Exception as ex:
        msgproc.log(f"Cannot execute getSimilarSongs for iid [{iid}] [{type(ex)}] [{ex}]")


def _radio_entry(objid, iid: str, radio_entry_type: RadioEntryType) -> list[dict[str, any]]:
    msgproc.log(f"_radio_entry for {iid} [{radio_entry_type}]")
    radio_identifier: ItemIdentifier = ItemIdentifier(ElementType.RADIO.getName(), iid)
    radio_id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(radio_identifier))
    radio_entry: dict[str, any] = upmplgutils.direntry(
        radio_id,
        objid,
        title="Radio")
    radio_song_list_identifier: ItemIdentifier = ItemIdentifier(ElementType.RADIO_SONG_LIST.getName(), iid)
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
        upnp_util.set_album_art_from_album_id(first_art_album.getId() if first_art_album else None, radio_entry)
        upnp_util.set_album_art_from_album_id(
            second_art_album.getId() if second_art_album else None,
            radio_song_list_entry)
    else:
        upnp_util.set_album_art_from_album_id(iid, radio_entry)
        upnp_util.set_album_art_from_album_id(iid, radio_song_list_entry)
    return [radio_entry, radio_song_list_entry]


def _similar_artists_for_artist(objid, artist_id: str) -> dict[str, any]:
    res_artist_info: Response[ArtistInfo] = connector_provider.get().getArtistInfo(artist_id)
    if not res_artist_info.isOk():
        raise Exception(f"Cannot get artist info for artist_id {artist_id}")
    if len(res_artist_info.getObj().getSimilarArtists()) > 0:
        # ok to add similar artists entry
        similar_artist_identifier: ItemIdentifier = ItemIdentifier(ElementType.ARTIST_SIMILAR.getName(), artist_id)
        similar_artist_id: str = identifier_util.create_objid(
            objid,
            identifier_util.create_id_from_identifier(similar_artist_identifier))
        similar_artists_entry: dict[str, any] = upmplgutils.direntry(
            similar_artist_id,
            objid,
            title="Similar Artists")
        # artist_art
        similar_artist_id: str = res_artist_info.getObj().getSimilarArtists()[0].getId()
        similar_artist_art: str = cache_actions.get_cached_random_album_id_by_artist_id(similar_artist_id)
        if similar_artist_art:
            upnp_util.set_album_art_from_album_id(
                similar_artist_art,
                similar_artists_entry)
        return similar_artists_entry


def _artist_to_top_songs_entry(objid, artist_id: str, artist: str) -> list[dict[str, any]]:
    result: list[dict[str, any]] = list()
    res_top_songs: Response[TopSongs] = connector_provider.get().getTopSongs(artist)
    if not res_top_songs.isOk():
        raise Exception(f"Cannot load top songs for artist {artist}")
    if len(res_top_songs.getObj().getSongs()) > 0:
        # ok to create top songs entry, else None
        top_songs_identifier: ItemIdentifier = ItemIdentifier(ElementType.ARTIST_TOP_SONGS.getName(), artist_id)
        top_songs_id: str = identifier_util.create_objid(
            objid,
            identifier_util.create_id_from_identifier(top_songs_identifier))
        top_songs_entry: dict[str, any] = upmplgutils.direntry(
            top_songs_id,
            objid,
            title=f"Top Songs by {artist}")
        art_select_song: Song = secrets.choice(res_top_songs.getObj().getSongs())
        upnp_util.set_album_art_from_album_id(
            art_select_song.getAlbumId(),
            top_songs_entry)
        result.append(top_songs_entry)
        top_songs_list_identifier: ItemIdentifier = ItemIdentifier(
            ElementType.ARTIST_TOP_SONGS_LIST.getName(),
            artist_id)
        top_songs_list_id: str = identifier_util.create_objid(
            objid,
            identifier_util.create_id_from_identifier(top_songs_list_identifier))
        top_songs_list_entry: dict[str, any] = upmplgutils.direntry(
            top_songs_list_id,
            objid,
            title=f"Top Songs (List) by {artist}")
        art_select_song = secrets.choice(res_top_songs.getObj().getSongs())
        upnp_util.set_album_art_from_album_id(
            art_select_song.getAlbumId(),
            top_songs_list_entry)
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
        entries.append(entry_creator.artist_to_entry(
            objid=objid,
            artist_id=sim_artist.getId(),
            entry_name=sim_artist.getName()))
    return entries


def handler_element_album(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    album_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    avp_enc: str = item_identifier.get(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, None)
    msgproc.log(f"handler_element_album for album_id {album_id} avp_enc {avp_enc}")
    album_version_path: str = codec.decode(avp_enc) if avp_enc else None
    album_tracks: AlbumTracks = get_album_tracks(album_id) if not album_version_path else None
    if album_tracks and album_tracks.getAlbumVersionCount() > 1:
        version_counter: int = 0
        album_version_path: str
        codec_set: set[str]
        for album_version_path in album_tracks.getCodecSetByPath().keys():
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
    return _present_album(objid, item_identifier, entries)


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


def handler_element_track(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    song_id: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_element_track should serve song_id {song_id}")
    song_response: Response[Song] = connector_provider.get().getSong(song_id)
    if not song_response.isOk():
        raise Exception(f"Cannot find song with id {song_id}")
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), song_id)
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    song_entry: dict[str, any] = _song_data_to_entry(objid, id, song_response.getObj())
    entries.append(song_entry)
    return entries


def handler_tag_group_albums(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tag_list: list[TagType] = [
        TagType.NEWEST_ALBUMS,
        TagType.RECENTLY_ADDED_ALBUMS,
        TagType.RECENTLY_PLAYED_ALBUMS,
        TagType.HIGHEST_RATED_ALBUMS,
        TagType.MOST_PLAYED_ALBUMS,
        TagType.RANDOM]
    add_fav: bool = config.show_empty_favorites
    if not add_fav:
        res: Response[Starred] = request_cache.get_starred()
        if res.isOk:
            fav_albums: list[Album] = res.getObj().getAlbums()
            if fav_albums and len(fav_albums) > 0:
                # add fav tags
                add_fav = True
    if add_fav:
        tag_list.append(TagType.FAVOURITE_ALBUMS)
    current: TagType
    for current in tag_list:
        if config.is_tag_supported(current):
            try:
                entry: dict[str, any] = tag_to_entry(
                    objid,
                    current)
                entries.append(entry)
            except Exception as ex:
                msgproc.log(f"Cannot create entry for tag [{current.getTagName()}] "
                            f"[{type(ex)}] [{ex}]")
        else:
            msgproc.log(f"handler_tag_group_albums skipping unsupported [{current}]")
    return entries


def handler_tag_group_artists(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tag_list: list[TagType] = [
        TagType.ALL_ARTISTS,
        TagType.ALL_ARTISTS_INDEXED]
    current_tag: TagType
    for current_tag in tag_list:
        entry: dict[str, any] = create_entry_for_tag(objid, current_tag)
        # pick random song for image
        res: Response[RandomSongs] = connector_provider.get().getRandomSongs(size=1)
        random_song: Song = res.getObj().getSongs()[0] if res and len(res.getObj().getSongs()) > 0 else None
        album_id: str = random_song.getAlbumId()
        upnp_util.set_album_art_from_album_id(
            album_id=album_id,
            target=entry)
        entries.append(entry)
    fav_artists: list[Artist] = list()
    select_fav: Artist = None
    fav_res: Response[Starred] = request_cache.get_starred()
    fav_artists = fav_res.getObj().getArtists() if fav_res and fav_res.isOk() else None
    msgproc.log(f"handler_tag_group_artists favorite artists count: [{len(fav_artists)}]")
    select_fav: Artist = secrets.choice(fav_artists) if fav_artists and len(fav_artists) > 0 else None
    add_fav: bool = config.show_empty_favorites or select_fav is not None
    if add_fav:
        fav_artist_entry: dict[str, any] = create_entry_for_tag(objid, TagType.FAVOURITE_ARTISTS)
        if select_fav:
            msgproc.log(f"handler_tag_group_artists fav_artist [{select_fav.getId()}] "
                        f"[{select_fav.getName() if select_fav else None}]")
            fav_art: str = art_retriever.get_artist_art_url_using_albums(artist_id=select_fav.getId())
            upnp_util.set_album_art_from_uri(
                album_art_uri=fav_art,
                target=fav_artist_entry)
        entries.append(fav_artist_entry)
    return entries


def handler_tag_group_songs(objid, item_identifier: ItemIdentifier, entries: list) -> list:
    tag_list: list[TagType] = [
        TagType.RANDOM_SONGS,
        TagType.RANDOM_SONGS_LIST]
    add_fav: bool = config.show_empty_favorites
    if not add_fav:
        res: Response[Starred] = request_cache.get_starred()
        if res.isOk:
            fav_songs: list[Album] = res.getObj().getAlbums()
            if fav_songs and len(fav_songs) > 0:
                # add fav tags
                add_fav = True
    if add_fav:
        tag_list.extend([
            TagType.FAVOURITE_SONGS,
            TagType.FAVOURITE_SONGS_LIST])
    entry_list: list[dict[str, any]] = tag_list_to_entries(
        objid,
        tag_list)
    entries.extend(entry_list)
    return entries


__tag_action_dict: dict = {
    TagType.ALBUMS.getTagName(): handler_tag_group_albums,
    TagType.ARTISTS.getTagName(): handler_tag_group_artists,
    TagType.SONGS.getTagName(): handler_tag_group_songs,
    TagType.RECENTLY_ADDED_ALBUMS.getTagName(): handler_tag_recently_added_albums,
    TagType.NEWEST_ALBUMS.getTagName(): handler_tag_newest_albums,
    TagType.RECENTLY_PLAYED_ALBUMS.getTagName(): handler_tag_recently_played,
    TagType.HIGHEST_RATED_ALBUMS.getTagName(): handler_tag_highest_rated,
    TagType.MOST_PLAYED_ALBUMS.getTagName(): handler_tag_most_played,
    TagType.FAVOURITE_ALBUMS.getTagName(): handler_tag_favourites,
    TagType.RANDOM.getTagName(): handler_tag_random,
    TagType.GENRES.getTagName(): handler_tag_genres,
    TagType.ALL_ARTISTS.getTagName(): handler_tag_all_artists,
    TagType.ALL_ARTISTS_INDEXED.getTagName(): handler_tag_all_artists_indexed,
    TagType.FAVOURITE_ARTISTS.getTagName(): handler_tag_artists_favourite,
    TagType.PLAYLISTS.getTagName(): handler_tag_playlists,
    TagType.INTERNET_RADIOS.getTagName(): handler_tag_internet_radios,
    TagType.RANDOM_SONGS.getTagName(): handler_tag_random_songs,
    TagType.RANDOM_SONGS_LIST.getTagName(): handler_tag_random_songs_list,
    TagType.FAVOURITE_SONGS.getTagName(): handler_tag_favourite_songs,
    TagType.FAVOURITE_SONGS_LIST.getTagName(): handler_tag_favourite_songs_list,
}

__elem_action_dict: dict = {
    ElementType.GENRE.getName(): handler_element_genre,
    ElementType.ARTIST_BY_INITIAL.getName(): handler_element_artists_by_initial,
    ElementType.ARTIST.getName(): handler_element_artist,
    ElementType.ARTIST_FOCUS.getName(): handler_element_artist_focus,
    ElementType.GENRE_ARTIST.getName(): handler_element_genre_artist,
    ElementType.ALBUM.getName(): handler_element_album,
    ElementType.NAVIGABLE_ALBUM.getName(): handler_element_navigable_album,
    ElementType.ALBUM_FOCUS.getName(): handler_element_album_focus,
    ElementType.GENRE_ARTIST_LIST.getName(): handler_element_genre_artists,
    ElementType.GENRE_ALBUM_LIST.getName(): handler_element_genre_album_list,
    ElementType.GENRE_ARTIST_ALBUMS.getName(): handler_element_genre_artist_albums,
    ElementType.PLAYLIST.getName(): handler_element_playlist,
    ElementType.TRACK.getName(): handler_element_track,
    ElementType.SONG_ENTRY_NAVIGABLE.getName(): handler_element_song_entry,
    ElementType.SONG_ENTRY_THE_SONG.getName(): handler_element_song_entry_song,
    ElementType.NEXT_RANDOM_SONGS.getName(): handler_element_next_random_songs,
    ElementType.INTERNET_RADIO.getName(): handler_element_radio_station,
    ElementType.ARTIST_TOP_SONGS.getName(): handler_element_artist_top_songs_navigable,
    ElementType.ARTIST_TOP_SONGS_LIST.getName(): handler_element_artist_top_songs_song_list,
    ElementType.ARTIST_SIMILAR.getName(): handler_element_similar_artists,
    ElementType.ARTIST_ALBUMS.getName(): handler_element_artist_albums,
    ElementType.RADIO.getName(): handler_radio,
    ElementType.RADIO_SONG_LIST.getName(): handler_radio_song_list
}


def tag_list_to_entries(objid, tag_list: list[TagType]) -> list[dict[str, any]]:
    entry_list: list[dict[str, any]] = list()
    tag: TagType
    for tag in tag_list:
        entry: dict[str, any] = tag_to_entry(objid, tag)
        entry_list.append(entry)
    return entry_list


def create_entry_for_tag(objid, tag: TagType) -> dict[str, any]:
    tagname: str = tag.getTagName()
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TAG.getName(), tagname)
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry: dict[str, any] = upmplgutils.direntry(
        id=id,
        pid=objid,
        title=get_tag_type_by_name(tag.getTagName()).getTagTitle())
    return entry


def tag_to_entry(objid, tag: TagType) -> dict[str, any]:
    entry: dict[str, any] = create_entry_for_tag(objid, tag)
    retrieved_art: RetrievedArt = art_retriever.execute_art_retriever(tag)
    upnp_util.set_album_art_from_uri(
        album_art_uri=retrieved_art.art_url if retrieved_art and retrieved_art.art_url else None,
        target=entry)
    return entry


def show_tag_entries(objid, entries: list) -> list:
    msgproc.log("show_tag_entries starting ...")
    for tag in TagType:
        if config.is_tag_supported(tag):
            if tag_enabled_in_initial_page(tag):
                msgproc.log(f"show_tag_entries adding tag [{tag}] ...")
                start_time: float = time.time()
                # is there a precondition?
                precondition: Callable[[], bool] = (
                    __tag_show_precondition[tag.getTagName()]
                    if tag.getTagName() in __tag_show_precondition
                    else None)
                do_show: bool = not precondition or precondition()
                if do_show:
                    msgproc.log(f"show_tag_entries actually showing tag [{tag}] ...")
                    entries.append(tag_to_entry(objid, tag))
                    msgproc.log(f"show_tag_entries finished showing tag [{tag}].")
                elapsed: float = time.time() - start_time
                msgproc.log(f"show_tag_entries adding tag [{tag}] took [{elapsed:.3f}].")
        # else:
        #     msgproc.log(f"show_tag_entries skipping unsupported [{tag}]")
    msgproc.log("show_tag_entries finished.")
    return entries


@dispatcher.record('browse')
def browse(a):
    msgproc.log(f"browse: args: --{a}--")
    _initsubsonic()
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    path = html.unescape(_objidtopath(objid))
    msgproc.log(f"browse: path: --{path}--")
    path_list: list[str] = objid.split("/")
    curr_path: str
    for curr_path in path_list:
        if not _g_myprefix == curr_path:
            decoded: str = None
            try:
                decoded = codec.decode(curr_path)
            except Exception as ex:
                msgproc.log(f"Could not decode [{curr_path}] [{type(ex)}] [{ex}]")
                decoded = "<decode failed>"
            msgproc.log(f"browse: path: [{curr_path}] decodes to {decoded}")
    last_path_item: str = path_list[len(path_list) - 1] if path_list and len(path_list) > 0 else None
    msgproc.log(f"browse: path_list: --{path_list}-- last: --{last_path_item}--")
    entries = []
    if len(path_list) == 1 and _g_myprefix == last_path_item:
        # show tags
        entries = show_tag_entries(objid, entries)
        return _returnentries(entries, no_cache=True)
    else:
        # decode
        decoded_path: str = codec.decode(last_path_item)
        item_dict: dict[str, any] = json.loads(decoded_path)
        item_identifier: ItemIdentifier = ItemIdentifier.from_dict(item_dict)
        thing_name: str = item_identifier.get(ItemIdentifierKey.THING_NAME)
        thing_value: str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
        msgproc.log(f"browse: item_identifier name: --{thing_name}-- value: --{thing_value}--")
        if ElementType.TAG.getName() == thing_name:
            msgproc.log(f"browse: should serve tag: --{thing_value}--")
            tag_handler = __tag_action_dict[thing_value] if thing_value in __tag_action_dict else None
            if tag_handler:
                msgproc.log(f"browse: found tag handler for: --{get_tag_type_by_name(thing_value)}--")
                entries = tag_handler(objid, item_identifier, entries)
                return _returnentries(entries)
            else:
                msgproc.log(f"browse: tag handler for: --{thing_value}-- not found")
        else:  # it's an element
            msgproc.log(f"browse: should serve element: --{thing_name}-- [{thing_value}]")
            elem_handler = __elem_action_dict[thing_name] if thing_name in __elem_action_dict else None
            if elem_handler:
                msgproc.log(f"browse: found elem handler for: --{get_element_type_by_name(thing_name)}--")
                entries = elem_handler(objid, item_identifier, entries)
            else:
                msgproc.log(f"browse: element handler for: --{thing_name}-- not found")
        return _returnentries(entries)


def _objidtopath(objid):
    if objid.find(_g_myprefix) != 0:
        raise Exception(f"subsonic: bad objid {objid}: bad prefix")
    return objid[len(_g_myprefix):].lstrip("/")


@dispatcher.record('search')
def search(a):
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
    resultset_length: int = 0
    if not objkind or len(objkind) == 0:
        if SearchType.ALBUM.getName() == field:
            # search albums by specified value
            if not value:
                return _returnentries(entries)
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=0,
                songCount=0,
                albumCount=config.items_per_page)
            album_list: list[Album] = search_result.getAlbums()
            current_album: Album
            filters: dict[str, str] = {}
            msgproc.log(f"search: filters = {filters}")
            for current_album in album_list:
                cache_actions.on_album(current_album)
                entries.append(entry_creator.album_to_entry(
                    objid=objid,
                    album=current_album))
                resultset_length += 1
        elif SearchType.TRACK.getName() == field:
            # search tracks by specified value
            if not value:
                return _returnentries(entries)
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=0,
                songCount=config.items_per_page,
                albumCount=0)
            song_list: list[Song] = search_result.getSongs()
            sorted_song_list: list[Song] = sort_song_list(song_list).getSongList()
            current_song: Song
            for current_song in sorted_song_list:
                entries.append(entry_creator.song_to_entry(
                    objid=objid,
                    song=current_song))
                resultset_length += 1
        elif SearchType.ARTIST.getName() == field:
            # search artists
            if not value:
                return _returnentries(entries)
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=config.items_per_page,
                songCount=0,
                albumCount=0)
            artist_list: list[Artist] = search_result.getArtists()
            current_artist: Artist
            for current_artist in artist_list:
                roles: list[str] = current_artist.getItem().getByName("roles", [])
                msgproc.log(f"found artist [{current_artist.getName()}] with roles [{roles}]")
                entry_title: str = current_artist.getName()
                if roles and len(roles) > 0:
                    entry_title = f"{entry_title} [{', '.join(roles)}]"
                if config.show_artist_id() and current_artist.getId():
                    msgproc.log(f"Adding [{current_artist.getId()}] to [{entry_title}]")
                    entry_title = f"{entry_title} [{current_artist.getId()}]"
                artist_mb_id: str = current_artist.getItem().getByName(constants.item_key_musicbrainz_id)
                if artist_mb_id and config.show_artist_mb_id():
                    msgproc.log(f"Adding [{artist_mb_id}] to [{entry_title}]")
                    entry_title = f"{entry_title} [mb:{artist_mb_id}]"
                entries.append(entry_creator.artist_to_entry(
                    objid=objid,
                    artist_id=current_artist.getId(),
                    entry_name=entry_title))
                resultset_length += 1
    else:
        # objkind is set
        if SearchType.ALBUM.getName() == objkind:
            # search albums by specified value
            if not value:
                return _returnentries(entries)
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=0,
                songCount=0,
                albumCount=config.items_per_page)
            album_list: list[Album] = search_result.getAlbums()
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
                entries.append(entry_creator.album_to_entry(
                    objid=objid,
                    album=current_album))
                resultset_length += 1
        elif SearchType.TRACK.getName() == objkind:
            # search tracks by specified value
            if not value:
                return _returnentries(entries)
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=0,
                songCount=config.items_per_page,
                albumCount=0)
            song_list: list[Song] = search_result.getSongs()
            sorted_song_list: list[Song] = sort_song_list(song_list).getSongList()
            current_song: Song
            for current_song in sorted_song_list:
                entries.append(entry_creator.song_to_entry(
                    objid=objid,
                    song=current_song))
                resultset_length += 1
        elif SearchType.ARTIST.getName() == objkind:
            # search artists
            if not value:
                return _returnentries(entries)
            search_result: SearchResult = connector_provider.get().search(
                query=value,
                artistCount=config.items_per_page,
                songCount=0,
                albumCount=0)
            artist_list: list[Artist] = search_result.getArtists()
            current_artist: Artist
            for current_artist in artist_list:
                msgproc.log(f"found artist {current_artist.getName()}")
                entries.append(entry_creator.artist_to_entry(
                    objid=objid,
                    artist_id=current_artist.getId(),
                    entry_name=current_artist.getName()))
                resultset_length += 1
    msgproc.log(f"Search for [{value}] as [{field}] with objkind [{objkind}] returned [{resultset_length}] entries")
    return _returnentries(entries)


subsonic_init.subsonic_init()
msgproc.log("Subsonic running")
msgproc.mainloop()
