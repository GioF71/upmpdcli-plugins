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

from subsonic_connector.album import Album
from subsonic_connector.album_list import AlbumList
from subsonic_connector.genre import Genre
from subsonic_connector.song import Song
from subsonic_connector.artist import Artist
from subsonic_connector.playlist import Playlist
from subsonic_connector.response import Response
from subsonic_connector.list_type import ListType

from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey
from element_type import ElementType

from album_util import MultiCodecAlbum
from album_util import AlbumTracks
from album_util import strip_codec_from_album
from album_util import get_last_path_element
from album_util import has_year
from album_util import get_album_year_str
from album_util import get_dir_from_path
from album_util import get_album_base_path

import art_retriever
import config
import connector_provider
import identifier_util
import upnp_util
import subsonic_util
import codec
import constants
import cache_actions
import cache_type
import album_util

from option_key import OptionKey
from option_util import get_option

import upmplgutils
import upmpdmeta

from msgproc_provider import msgproc

import os

import persistence


def artist_entry_for_album(objid, album: Album) -> dict[str, any]:
    msgproc.log(f"artist_entry_for_album creating artist entry for album with album_id: [{album.getId()}]")
    artist_identifier: ItemIdentifier = ItemIdentifier(
        name=ElementType.ARTIST.getName(),
        value=album.getArtistId())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(artist_identifier))
    artist_entry_title: str = album.getArtist()
    if album.getArtistId() and config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_ID):
        msgproc.log(f"artist_entry_for_album: Adding [{album.getArtistId()}] to [{artist_entry_title}]")
        artist_entry_title = f"{artist_entry_title} [{album.getArtistId()}]"
    artist: Artist = subsonic_util.try_get_artist(album.getArtistId())
    if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID):
        # we want the artist mb id, so we load the artist
        artist_mb_id: str = (subsonic_util.get_artist_musicbrainz_id(artist)
                             if artist
                             else None)
        if artist_mb_id:
            if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID_AS_PLACEHOLDER):
                artist_entry_title = f"{artist_entry_title} [mb]"
            else:
                artist_entry_title = f"{artist_entry_title} [mb:{artist_mb_id}]"
    # add album count
    album_count: int = artist.getAlbumCount() if artist else 0
    artist_entry_title = f"{artist_entry_title} [{album_count}]"
    artist_entry: dict[str, any] = (upmplgutils.direntry(
        id=id,
        pid=objid,
        title=artist_entry_title))
    if artist_entry:
        art_uri: str = None
        # does the artist has coverArt?
        artist_cover_art: str = subsonic_util.get_artist_cover_art(artist)
        # if not already found from the artist, we try to get an album cover for the artist entry
        if artist_cover_art:
            art_uri = subsonic_util.build_cover_art_url(item_id=artist_cover_art, force_save=True)
        else:
            art_uri = art_retriever.get_artist_art_url_using_albums_by_artist_id(artist_id=album.getArtistId())
        upnp_util.set_album_art_from_uri(album_art_uri=art_uri, target=artist_entry)
        cache_actions.on_album(album)
    return artist_entry


def get_album_quality_badge(album: Album, force_load: bool = False) -> str:
    if force_load:
        reloaded: Album = subsonic_util.try_get_album(album.getId())
        if not reloaded:
            raise Exception(f"Cannot find {Album.__name__} with album_id [{album.getId()}]")
        quality_badge: str = get_track_list_badge(
            track_list=reloaded.getSongs(),
            list_identifier=album.getId())
        msgproc.log(f"get_album_quality_badge for album_id: [{album.getId()}] "
                    f"force_load: [{force_load}] -> [{quality_badge}]")
        artist_id: str = album.getArtistId()
        album_mbid: str = subsonic_util.get_album_musicbrainz_id(album)
        # save
        persistence.save_album_metadata(
            album_metadata=persistence.AlbumMetadata(
                album_id=album.getId(),
                quality_badge=quality_badge,
                album_musicbrainz_id=album_mbid,
                album_artist_id=artist_id))
        return quality_badge
    else:
        album_metadata: persistence.AlbumMetadata = persistence.get_album_metadata(album_id=album.getId())
        return album_metadata.quality_badge if album_metadata else None


def get_track_list_badge(track_list: list[Song], list_identifier: str = None) -> str:
    quality_badge: str = subsonic_util.get_track_list_badge(track_list, list_identifier)
    if config.debug_badge_mngmt:
        msgproc.log(f"Quality badge for id: [{list_identifier}] len: [{len(track_list) if track_list else 0}] -> "
                    f"[{quality_badge}]")
    return quality_badge


def genre_artist_to_entry(
        objid,
        genre: str,
        artist_id: str,
        artist_name: str,
        album_cover_art: str = None) -> dict[str, any]:
    msgproc.log(f"genre_artist_to_entry genre:[{genre}] artist_id:[{artist_id}] artist_name:[{artist_name}]")
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ARTIST.getName(),
        artist_id)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(
        id,
        objid,
        artist_name)
    if artist_id:
        entry: dict[str, any] = artist_to_entry_raw(
            objid=objid,
            artist_id=artist_id,
            artist_entry_name=artist_name,
            album_cover_art=album_cover_art)
    return entry


def album_to_navigable_entry(
        objid,
        album: Album,
        options: dict[str, any] = {}) -> dict[str, any]:
    title: str = album.getTitle()
    artist_id: str = album.getArtistId()
    album_mbid: str = subsonic_util.get_album_musicbrainz_id(album=album)
    album_path_joined: str = album_util.get_album_path_list_joined(album=album)
    if artist_id or album_mbid or album_path_joined:
        persistence.save_album_metadata(album_metadata=persistence.AlbumMetadata(
            album_id=album.getId(),
            album_musicbrainz_id=album_mbid,
            album_artist_id=artist_id,
            album_path=album_path_joined))
    album_version: str = subsonic_util.get_album_version(album)
    # number of discs
    title = subsonic_util.append_number_of_discs_to_album_title(
        current_albumtitle=title,
        album=album,
        config_getter=lambda: config.get_config_param_as_bool(
            constants.ConfigParam.ALLOW_APPEND_DISC_CNT_IN_ALBUM_CONTAINER))
    # number of tracks
    title = subsonic_util.append_number_of_tracks_to_album_title(
        current_albumtitle=title,
        album=album,
        config_getter=lambda: config.get_config_param_as_bool(
            constants.ConfigParam.ALLOW_APPEND_TRACK_CNT_IN_ALBUM_CONTAINER))
    # explicit?
    title = subsonic_util.append_explicit_if_needed(title, album)
    album_date_for_sorting: str = subsonic_util.get_album_date_for_sorting(album)
    if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ALBUM_SORTABLE_DATE):
        msgproc.log(f"Album [{album.getId()}] [{album.getTitle()}] "
                    f"by [{album.getArtist()}] "
                    f"Sortable Date [{album_date_for_sorting}]")
    prepend_number: int = get_option(options=options, option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE)
    if prepend_number:
        title = f"[{prepend_number:02}] {title}"
    artist: str = album.getArtist()
    identifier: ItemIdentifier = ItemIdentifier(ElementType.NAVIGABLE_ALBUM.getName(), album.getId())
    # ask to skip artist?
    skip_artist_id: str = get_option(options=options, option_key=OptionKey.SKIP_ARTIST_ID)
    if skip_artist_id:
        identifier.set(ItemIdentifierKey.SKIP_ARTIST_ID, skip_artist_id)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    if has_year(album):
        if config.get_config_param_as_bool(constants.ConfigParam.APPEND_YEAR_TO_ALBUM_CONTAINER):
            title = f"{title} [{get_album_year_str(album)}]"
    else:
        msgproc.log(f"Cannot find year for album [{album.getId()}] [{album.getTitle()}] by [{album.getArtist()}]")
    # append genre if allowed
    title = subsonic_util.append_genre_to_artist_entry_name_if_allowed(
        entry_name=title,
        album=album,
        config_getter=(lambda: config.get_config_param_as_bool(constants.ConfigParam.ALLOW_GENRE_IN_ALBUM_CONTAINER)))
    album_quality_badge: str = get_album_quality_badge(album=album, force_load=False)
    title = subsonic_util.append_album_badge_to_album_title(
        current_albumtitle=title,
        album_quality_badge=album_quality_badge,
        album_entry_type=constants.AlbumEntryType.ALBUM_CONTAINER,
        is_search_result=False)
    title = subsonic_util.append_album_version_to_album_title(
        current_albumtitle=title,
        album_version=album_version,
        album_entry_type=constants.AlbumEntryType.ALBUM_CONTAINER,
        is_search_result=False)
    append_artist: bool = (config.get_config_param_as_bool(
                           constants.ConfigParam.ALLOW_APPEND_ARTIST_IN_ALBUM_CONTAINER) and
                           get_option(options=options, option_key=OptionKey.APPEND_ARTIST_IN_ALBUM_TITLE))
    if append_artist:
        artist: str = album.getArtist()
        if artist:
            title = f"{title} - {artist}"
    entry_title: str = title
    entry_title = subsonic_util.append_album_id_to_album_title(
        current_albumtitle=entry_title,
        album_id=album.getId(),
        album_entry_type=constants.AlbumEntryType.ALBUM_CONTAINER,
        is_search_result=False)
    if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ALBUM_MBID_IN_ALBUM_CONTAINER):
        # available here?
        album_mbid: str = subsonic_util.get_album_musicbrainz_id(album)
        if not album_mbid:
            # see if it's available in cache
            if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ACTION_ON_MB_ALBUM_CACHE):
                msgproc.log(f"Trying to got album_mbid from cache for [{album.getId()}] ...")
            album_metadata: persistence.AlbumMetadata = persistence.get_album_metadata(album_id=album.getId())
            album_mbid = album_metadata.album_musicbrainz_id if album_metadata else None
            if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ACTION_ON_MB_ALBUM_CACHE):
                msgproc.log(f"Got album_mbid from cache for [{album.getId()}] -> [mb:{album_mbid}]")
        else:
            if config.get_config_param_as_bool(constants.ConfigParam.DUMP_ACTION_ON_MB_ALBUM_CACHE):
                msgproc.log(f"Album album_mbid for [{album.getId()}] -> [{album_mbid}]")

        if album_mbid:
            # we can display it!
            if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ALBUM_MB_ID_AS_PLACEHOLDER):
                entry_title = f"{entry_title} [mb]"
            else:
                entry_title = f"{entry_title} [mb:{album_mbid}]"
    # anomalies
    show_album_genre_information(album)
    entry: dict[str, any] = upmplgutils.direntry(
        id=id,
        pid=objid,
        title=entry_title,
        artist=artist)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_QUALITY, album_quality_badge, entry)
    subsonic_util.set_album_metadata(album=album, target=entry)
    upnp_util.set_album_art_from_uri(subsonic_util.build_cover_art_url(album.getCoverArt()), entry)
    upnp_util.set_album_id(album.getId(), entry)
    if config.get_config_param_as_bool(constants.ConfigParam.SET_CLASS_TO_ALBUM_FOR_NAVIGABLE_ALBUM):
        upnp_util.set_class_album(entry)
    cache_actions.on_album(album)
    return entry


def show_album_genre_information(album: Album):
    if not config.get_config_param_as_bool(constants.ConfigParam.DUMP_ALBUM_GENRE):
        return
    genre_list: list[str] = album.getGenres()
    if not genre_list or len(genre_list) == 0:
        msgproc.log(f"WARN: Album [{album.getId()}] [{album.getTitle()}] by [{album.getArtist()}] has no genres")
    else:
        msgproc.log(f"Album [{album.getId()}] [{album.getTitle()}] by [{album.getArtist()}] has genres [{genre_list}]")


def genre_to_entry(
        objid,
        current_genre: Genre) -> dict[str, any]:
    genre_name: str = current_genre.getName()
    genre_art: str = None
    genre_art_url: str = None
    # first, try to look in kv cache
    kv_item_for_genre: persistence.KeyValueItem = persistence.get_kv_item(
        partition=cache_type.CacheType.GENRE_ALBUM_ART.getName(),
        key=genre_name)
    msgproc.log(f"genre_to_entry cache hit for [{genre_name}]: "
                f"[{'yes' if kv_item_for_genre and kv_item_for_genre.value else 'no'}] ")
    if kv_item_for_genre and kv_item_for_genre.value:
        genre_art = kv_item_for_genre.value
        genre_art_url = subsonic_util.build_cover_art_url(item_id=genre_art)
    if (not genre_art and
            config.get_config_param_as_bool(constants.ConfigParam.GENRE_VIEW_SEARCH_ALBUMS_FOR_COVER_ART)):
        # load up to 5 albums
        res: Response[AlbumList] = connector_provider.get().getAlbumList(
            ltype=ListType.BY_GENRE,
            genre=genre_name,
            size=5)
        if not res or not res.isOk():
            msgproc.log(f"Cannot get albums by genre [{genre_name}]")
        album_list: AlbumList = res.getObj()
        msgproc.log(f"Loaded [{len(album_list.getAlbums()) if album_list and album_list.getAlbums() else 0}] "
                    f"albums for genre [{genre_name}]")
        if album_list and len(album_list.getAlbums()) > 0:
            # look for one with a cover art
            album: Album
            for album in album_list.getAlbums():
                if not album.getCoverArt():
                    continue
                genre_art = album.getCoverArt()
                # store in kv cache!
                persistence.save_key_value_item(key_value_item=persistence.KeyValueItem(
                    partition=cache_type.CacheType.GENRE_ALBUM_ART.getName(),
                    key=genre_name,
                    value=genre_art))
                genre_art_url = subsonic_util.build_cover_art_url(item_id=genre_art)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.GENRE.getName(),
        current_genre.getName())
    id: str = identifier_util.create_objid(
        objid,
        identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, genre_name)
    upnp_util.set_album_art_from_uri(genre_art_url, entry)
    return entry


def maybe_append_roles(entry_name: str, artist: Artist) -> str:
    if config.get_config_param_as_bool(constants.ConfigParam.APPEND_ROLES_TO_ARTIST):
        artist_roles: list[str] = subsonic_util.get_artist_roles(artist=artist)
        disp: list[str] = list(map(subsonic_util.name_key_to_display, artist_roles))
        return f"{entry_name} [{', '.join(disp)}]"
    else:
        return entry_name


def artist_to_entry(
        objid,
        artist: Artist,
        entry_name: str = None,
        additional_identifier_properties: dict[ItemIdentifierKey, any] = {},
        options: dict[str, any] = {}) -> dict[str, any]:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    cover_art: str = subsonic_util.get_artist_cover_art(artist)
    artist_roles: list[str] = subsonic_util.get_artist_roles(artist=artist)
    if verbose:
        msgproc.log(f"artist_to_entry artist [{artist.getId()}] [{artist.getName()}] -> "
                    f"roles [{artist_roles}] "
                    f"coverArt [{cover_art}]")
    select_artist_entry_name: str = entry_name if entry_name else maybe_append_roles(artist.getName(), artist)
    artist_entry: dict[str, any] = artist_to_entry_raw(
        objid=objid,
        artist_id=artist.getId(),
        artist_entry_name=select_artist_entry_name,
        artist_cover_art=cover_art,
        additional_identifier_properties=additional_identifier_properties,
        options=options)
    subsonic_util.set_artist_metadata(artist=artist, target=artist_entry)
    return artist_entry


def artist_to_entry_raw(
        objid,
        artist_id: str,
        artist_entry_name: str,
        artist_cover_art: str = None,
        album_cover_art: str = None,
        additional_identifier_properties: dict[ItemIdentifierKey, any] = {},
        options: dict[str, any] = {}) -> dict[str, any]:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(),
        artist_id)
    k: ItemIdentifierKey
    for k, v in additional_identifier_properties.items() if additional_identifier_properties else {}.items():
        msgproc.log(f"Adding [{k}]: [{v}]")
        identifier.set(k, v)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id=id, pid=objid, title=artist_entry_name)
    skip_art: bool = get_option(options=options, option_key=OptionKey.SKIP_ART)
    album_art_uri: str = (subsonic_util.build_cover_art_url(artist_cover_art)
                          if artist_cover_art is not None
                          else None)
    if verbose:
        msgproc.log(f"artist_to_entry_raw for artist_id [{artist_id}] [{artist_entry_name}] -> "
                    f"artist_cover_art [{artist_cover_art}]")
    if not album_art_uri and (not skip_art and artist_id):
        # first we try in the cache ...
        if verbose:
            msgproc.log(f"artist_to_entry_raw retrieving cover art for artist_id [{artist_id}] in metadata cache ...")
        artist_metadata: persistence.ArtistMetadata = persistence.get_artist_metadata(artist_id=artist_id)
        if artist_metadata and artist_metadata.artist_cover_art:
            if verbose:
                msgproc.log(f"artist_to_entry_raw artist_id [{artist_id}] "
                            f"metadata item found -> cover_art [{artist_metadata.artist_cover_art}]")
            album_art_uri = subsonic_util.build_cover_art_url(item_id=artist_metadata.artist_cover_art)
            if verbose:
                msgproc.log(f"artist_to_entry_raw artist_id [{artist_id}] -> album_art_uri [{album_art_uri}]")
            if verbose:
                msgproc.log(f"artist_to_entry_raw found cached cover_art for artist_id [{artist_id}] -> "
                            f"[{artist_metadata.artist_cover_art}] -> "
                            f"album_art_uri [{album_art_uri}]")
        else:
            # was the function argument album_cover_art provided?
            if album_cover_art:
                if verbose:
                    msgproc.log(f"artist_to_entry_raw for artist_id [{artist_id}] "
                                f"we are using album cover art [{album_cover_art}] ...")
                    album_art_uri = subsonic_util.build_cover_art_url(item_id=album_cover_art)
            else:
                # find art from albums
                if verbose:
                    msgproc.log("artist_to_entry_raw retrieving cover art for "
                                f"artist_id [{artist_id}] from albums, this is slow ...")
                album_art_uri = art_retriever.get_album_art_uri_for_artist_id(artist_id)
    if album_art_uri:
        upnp_util.set_album_art_from_uri(
            album_art_uri=album_art_uri,
            target=entry)
    upnp_util.set_class_artist(entry)
    subsonic_util.set_artist_metadata_by_artist_id(
        artist_id=artist_id,
        target=entry)
    return entry


def artist_initial_to_entry(
        objid,
        artist_initial: str,
        options: dict[str, any] = dict()) -> dict[str, any]:
    encoded_artist_initial: str = codec.encode(artist_initial)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_BY_INITIAL.getName(),
        encoded_artist_initial)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry: dict[str, any] = upmplgutils.direntry(id, objid, artist_initial)
    return entry


def build_intermediate_url(track_id: str) -> str:
    if not config.skip_intermediate_url:
        http_host_port = os.environ["UPMPD_HTTPHOSTPORT"]
        url = (f"http://{http_host_port}/{constants.PluginConstant.PLUGIN_NAME.value}"
               f"/track/version/1/trackId/{track_id}")
        if config.log_intermediate_url:
            msgproc.log(f"intermediate_url for track_id {track_id} -> [{url}]")
        return url
    else:
        return connector_provider.get().buildSongUrl(
            song_id=track_id,
            format=config.get_transcode_codec(),
            max_bitrate=config.get_transcode_max_bitrate())


def song_to_entry(
        objid,
        song: Song,
        force_cover_art_save: bool = False,
        options: dict[str, any] = {}) -> dict:
    entry = {}
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), song.getId())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = song.getId()
    upnp_util.set_class_music_track(entry)
    song_uri: str = build_intermediate_url(track_id=song.getId())
    entry['uri'] = song_uri
    title: str = song.getTitle()
    multi_codec_album: MultiCodecAlbum = get_option(options=options, option_key=OptionKey.MULTI_CODEC_ALBUM)
    if (MultiCodecAlbum.YES == multi_codec_album and
        config.allow_blacklisted_codec_in_song == 1 and
            (not song.getSuffix().lower() in config.whitelist_codecs)):
        title = "{} [{}]".format(title, song.getSuffix())
    upnp_util.set_album_title(title, entry)
    entry['tp'] = 'it'
    entry['discnumber'] = song.getDiscNumber()
    track_num: str = song.getTrack()
    force_track_number: int = get_option(options=options, option_key=OptionKey.FORCE_TRACK_NUMBER)
    if force_track_number:
        track_num = str(force_track_number)
    upnp_util.set_track_number(track_num, entry)
    upnp_util.set_artist(subsonic_util.join_with_comma(subsonic_util.get_song_artists(song)), entry)
    entry['upnp:album'] = song.getAlbum()
    entry['upnp:genre'] = song.getGenre()
    entry['res:mime'] = song.getContentType()
    album_art_uri: str = subsonic_util.build_cover_art_url(item_id=song.getCoverArt(), force_save=force_cover_art_save)
    upnp_util.set_album_art_from_uri(album_art_uri=album_art_uri, target=entry)
    entry['duration'] = str(song.getDuration())
    # channel count, bit depth, sample rate and bit rate
    cc: int = 2
    bd: int = 0
    sr: int = 0
    br: int = 0
    if song.getItem().hasName(constants.ItemKey.CHANNEL_COUNT.value):
        cc = song.getItem().getByName(constants.ItemKey.CHANNEL_COUNT.value)
        upnp_util.set_channel_count(cc, entry)
    if subsonic_util.get_song_bit_depth(song):
        bd = subsonic_util.get_song_bit_depth(song)
        upnp_util.set_bit_depth(bd, entry)
    if song.getItem().hasName(constants.ItemKey.SAMPLING_RATE.value):
        sr = song.getItem().getByName(constants.ItemKey.SAMPLING_RATE.value)
        upnp_util.set_sample_rate(sr, entry)
    br = song.getBitRate()
    if br:
        upnp_util.set_bit_rate(br, entry)
    if config.get_config_param_as_bool(constants.ConfigParam.DUMP_STREAMING_PROPERTIES):
        msgproc.log(f"Song [{song.getId()}] -> bitDepth [{bd}] "
                    f"samplingRate [{sr}] bitRate [{br}] "
                    f"channelCount [{cc}] "
                    f"mimetype [{song.getContentType()}] "
                    f"duration [{song.getDuration()}]")
    subsonic_util.set_song_metadata(song=song, target=entry)
    return entry


def playlist_to_entry(
        objid,
        playlist: Playlist) -> dict[str, any]:
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.PLAYLIST.getName(),
        playlist.getId())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, playlist.getName())
    art_uri: str = (subsonic_util.build_cover_art_url(playlist.getCoverArt())
                    if playlist.getCoverArt() else None)
    upnp_util.set_album_art_from_uri(album_art_uri=art_uri, target=entry)
    return entry


def get_allow_disc_count_in_album_entry(is_search_result: bool) -> bool:
    if is_search_result:
        return config.get_config_param_as_bool(constants.ConfigParam.ALLOW_APPEND_DISC_CNT_IN_ALBUM_SEARCH_RESULT)
    else:
        return config.get_config_param_as_bool(constants.ConfigParam.ALLOW_APPEND_DISC_CNT_IN_ALBUM_VIEW)


def get_allow_track_count_in_album_entry(is_search_result: bool) -> bool:
    if is_search_result:
        return config.get_config_param_as_bool(constants.ConfigParam.ALLOW_APPEND_TRACK_CNT_IN_ALBUM_SEARCH_RESULT)
    else:
        return config.get_config_param_as_bool(constants.ConfigParam.ALLOW_APPEND_TRACK_CNT_IN_ALBUM_VIEW)


def album_to_entry(
        objid,
        album: Album,
        options: dict[str, any] = {}) -> dict[str, any]:
    is_search_result: bool = get_option(options=options, option_key=OptionKey.SEARCH_RESULT)
    title: str = album.getTitle()
    album_version: str = subsonic_util.get_album_version(album)
    # number of discs
    title = subsonic_util.append_number_of_discs_to_album_title(
        current_albumtitle=title,
        album=album,
        config_getter=lambda: get_allow_disc_count_in_album_entry(is_search_result))
    # number of tracks
    title = subsonic_util.append_number_of_tracks_to_album_title(
        current_albumtitle=title,
        album=album,
        config_getter=lambda: get_allow_track_count_in_album_entry(is_search_result))
    # explicit?
    title = subsonic_util.append_explicit_if_needed(title, album)
    append_artist: bool = (config.get_config_param_as_bool(
                           constants.ConfigParam.ALLOW_APPEND_ARTIST_IN_ALBUM_VIEW) and
                           get_option(options=options, option_key=OptionKey.APPEND_ARTIST_IN_ALBUM_TITLE)
                           if not is_search_result
                           else config.get_config_param_as_bool(constants.ConfigParam.ALLOW_APPEND_ARTIST_IN_SEARCH_RES))
    if append_artist:
        artist: str = album.getArtist()
        if artist:
            title = f"{artist} - {title}"
    prepend_number: int = get_option(options=options, option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE)
    if prepend_number:
        title = f"[{prepend_number:02}] {title}"
    append_year: bool = (config.get_config_param_as_bool(constants.ConfigParam.APPEND_YEAR_TO_ALBUM_SEARCH_RES)
                         if is_search_result
                         else config.get_config_param_as_bool(constants.ConfigParam.APPEND_YEAR_TO_ALBUM_VIEW))
    if append_year and has_year(album):
        title = "{} [{}]".format(title, get_album_year_str(album))
    force_load: bool = get_option(options=options, option_key=OptionKey.FORCE_LOAD_QUALITY_BADGE)
    album_quality_badge: str = get_album_quality_badge(album=album, force_load=force_load)
    if force_load and config.get_config_param_as_bool(constants.ConfigParam.APPEND_CODEC_TO_ALBUM):
        msgproc.log(f"album_to_entry for "
                    f"album_id: [{album.getId()}] "
                    f"badge [{album_quality_badge if album_quality_badge else 'not available'}] "
                    "loading songs ...")
        song_list: list[Song] = album.getSongs()
        # load album
        album_tracks: AlbumTracks
        _, album_tracks = subsonic_util.get_album_tracks(album.getId())
        if album_tracks is None:
            return None
        song_list: list[Song] = album_tracks.getSongList()
        codecs: list[str] = []
        whitelist_count: int = 0
        blacklist_count: int = 0
        song: Song
        for song in song_list:
            if not song.getSuffix().lower() in codecs:
                codecs.append(song.getSuffix().lower())
                if not song.getSuffix().lower() in config.whitelist_codecs:
                    blacklist_count += 1
                else:
                    whitelist_count += 1
        # show version count if count > 1
        if album_tracks.getAlbumVersionCount() > 1:
            title = "{} [{} versions]".format(title, album_tracks.getAlbumVersionCount())
        # show or not?
        all_whitelisted: bool = len(codecs) == whitelist_count
        if len(codecs) > 1 or not all_whitelisted:
            codecs.sort()
            if len(codecs) == 1:
                title = strip_codec_from_album(title, codecs)
            codecs_str: str = ",".join(codecs)
            # add codecs if more than one or there is no quality_badge
            if (len(codecs) > 1) or (not album_quality_badge or len(album_quality_badge) == 0):
                title = "{} [{}]".format(title, codecs_str)
    # set badge
    title = subsonic_util.append_album_badge_to_album_title(
        current_albumtitle=title,
        album_quality_badge=album_quality_badge,
        album_entry_type=constants.AlbumEntryType.ALBUM_VIEW,
        is_search_result=is_search_result)
    title = subsonic_util.append_album_version_to_album_title(
        current_albumtitle=title,
        album_version=album_version,
        album_entry_type=constants.AlbumEntryType.ALBUM_VIEW,
        is_search_result=is_search_result)
    # show album id
    title = subsonic_util.append_album_id_to_album_title(
        current_albumtitle=title,
        album_id=album.getId(),
        album_entry_type=constants.AlbumEntryType.ALBUM_VIEW,
        is_search_result=is_search_result)
    # musicbrainz?
    album_mbid: str = subsonic_util.get_album_musicbrainz_id(album)
    msgproc.log(f"Found album_mbid [{album_mbid}] for album [{album.getId()}] [{album.getTitle()}] by [{album.getArtist()}]")
    show_mbid: bool = config.get_config_param_as_bool(
        constants.ConfigParam.SHOW_ALBUM_MBID_IN_ALBUM_SEARCH_RES
        if is_search_result
        else constants.ConfigParam.SHOW_ALBUM_MBID_IN_ALBUM_VIEW)
    if album_mbid and show_mbid:
        if config.get_config_param_as_bool(constants.ConfigParam.SHOW_ARTIST_MB_ID_AS_PLACEHOLDER):
            title = f"{title} [mb]"
        else:
            title = f"{title} [{album_mbid}]"
    artist = album.getArtist()
    cache_actions.on_album(album)
    identifier: ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), album.getId())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry: dict[str, any] = upmplgutils.direntry(id, objid, title=title, artist=artist)
    # we save the cover art even if it's already there
    cover_art_url: str = subsonic_util.build_cover_art_url(item_id=album.getCoverArt(), force_save=True)
    upnp_util.set_album_art_from_uri(cover_art_url, entry)
    upnp_util.set_album_id(album.getId(), entry)
    upnp_util.set_artist(artist=album.getArtist(), target=entry)
    upnp_util.set_date_from_album(album=album, target=entry)
    upnp_util.set_class_album(entry)
    upnp_util.set_upmpd_meta(upmpdmeta.UpMpdMeta.ALBUM_QUALITY, album_quality_badge, entry)
    subsonic_util.set_album_metadata(album=album, target=entry)
    return entry


def _load_album_version_tracks(
        album: Album,
        album_version_path: str) -> list[Song]:
    track_list: list[Song] = list()
    current_song: Song
    for current_song in album.getSongs():
        song_path: str = get_dir_from_path(current_song.getPath())
        song_path = get_album_base_path(song_path)
        if album_version_path == song_path:
            track_list.append(current_song)
    return track_list


def album_id_to_album_focus(
        objid,
        album: Album) -> dict[str, any]:
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_FOCUS.getName(),
        album.getId())
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    art_uri = subsonic_util.build_cover_art_url(item_id=album.getCoverArt())
    entry = upmplgutils.direntry(id, objid, "Focus")
    upnp_util.set_album_art_from_uri(album_art_uri=art_uri, target=entry)
    return entry


def artist_id_to_artist_focus(
        objid,
        artist_id: str) -> dict[str, any]:
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_FOCUS.getName(),
        artist_id)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, "Focus")
    return entry


def album_version_to_entry(
        objid,
        current_album: Album,
        version_number: int,
        album_version_path: str,
        codec_set: set[str]) -> dict[str, any]:
    identifier: ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), current_album.getId())
    avp_encoded: str = codec.encode(album_version_path)
    identifier.set(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, avp_encoded)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    title: str = f"Version #{version_number}"
    if (config.get_config_param_as_bool(constants.ConfigParam.APPEND_YEAR_TO_ALBUM_VIEW) and
            has_year(current_album)):
        title = "{} [{}]".format(title, get_album_year_str(current_album))
    codecs_str: str = ",".join(codec_set)
    title = "{} [{}]".format(title, codecs_str)
    last_path: str = get_last_path_element(album_version_path)
    title = "{} [{}]".format(title, last_path)
    # album badge on the list of tracks
    track_list: list[Song] = _load_album_version_tracks(
        album=current_album,
        album_version_path=album_version_path)
    album_quality_badge: str = get_track_list_badge(track_list)
    msgproc.log(f"album_version_to_entry album [{current_album.getId()}] -> badge [{album_quality_badge}]")
    if album_quality_badge:
        title = f"{title} [{album_quality_badge}]"
        msgproc.log(f"album_version_to_entry title [{title}]")
    artist = current_album.getArtist()
    cache_actions.on_album(current_album)
    entry: dict[str, any] = upmplgutils.direntry(id, objid, title=title, artist=artist)
    current_album_cover_art: str = subsonic_util.build_cover_art_url(item_id=current_album.getCoverArt())
    upnp_util.set_album_art_from_uri(current_album_cover_art, entry)
    upnp_util.set_class_album(entry)
    return entry
