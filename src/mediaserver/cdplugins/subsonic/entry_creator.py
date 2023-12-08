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
from album_util import get_display_artist
from album_util import strip_codec_from_album
from album_util import get_last_path_element
from album_util import get_album_year_str
from album_util import has_year

import config
import connector_provider
import identifier_util
import upnp_util
import caching
import cache_manager_provider
import subsonic_util
import subsonic_init_provider
import art_retriever
import artist_initial_cache_provider
import codec
import selector
import constants

from option_key import OptionKey
from option_util import get_option

from typing import Callable
from upmplgutils import direntry

from msgproc_provider import msgproc

import secrets
import os

def genre_artist_to_entry(
        objid, 
        genre : str,
        artist_id : str,
        artist_name : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ARTIST.getName(), 
        artist_id)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry = direntry(
        id, 
        objid, 
        artist_name)
    artist_art : str = selector.selector_artist_id_to_album_id(artist_id)
    upnp_util.set_album_art_from_uri(
        artist_art, 
        entry)
    return entry

def album_to_navigable_entry(
        objid, 
        current_album : Album,
        options : dict[str, any] = {}) -> direntry:
    title : str = current_album.getTitle()
    prepend_artist : bool = get_option(options = options, option_key = OptionKey.PREPEND_ARTIST_IN_ALBUM_TITLE)
    if prepend_artist:
        artist : str = current_album.getArtist()
        if artist: title = f"{artist} - {title}"
    prepend_number : int = get_option(options = options, option_key = OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE)
    if prepend_number: title = f"[{prepend_number:02}] {title}"
    artist : str = current_album.getArtist()
    identifier : ItemIdentifier = ItemIdentifier(ElementType.NAVIGABLE_ALBUM.getName(), current_album.getId())
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    if has_year(current_album):
        title = f"{title} [{get_album_year_str(current_album)}]"
    entry : dict = direntry(
        id = id, 
        pid = objid, 
        title = title, 
        artist = artist)
    upnp_util.set_album_art_from_album_id(
        current_album.getId(), 
        entry)
    upnp_util.set_album_id(
        current_album.getId(), 
        entry)
    return entry

def genre_to_entry(
        objid, 
        current_genre : Genre,
        converter_album_id_to_url : Callable[[str], str]) -> direntry:
    name : str = current_genre.getName()
    genre_art : str = None
    genre_album_set : set[str] = cache_manager_provider.get().get_cached_element(
        ElementType.GENRE,
        name)
    random_album_id : str = (secrets.choice(tuple(genre_album_set))
        if genre_album_set and len(genre_album_set) > 0
        else None)
    if random_album_id: genre_art = random_album_id
    if not genre_art:
        res : Response[AlbumList] = connector_provider.get().getAlbumList(
            ltype = ListType.BY_GENRE, 
            genre = name)
        if not res or not res.isOk(): msgproc.log(f"Cannot get albums by genre [{name}]")
        album_list : AlbumList = res.getObj()
        if album_list and len(album_list.getAlbums()) > 0:
            album : Album = secrets.choice(album_list.getAlbums())
            genre_art = album.getId()
            for album in album_list.getAlbums():
                cache_manager_provider.get().on_album_for_genre(
                    album = album,
                    genre = name)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE.getName(), 
        current_genre.getName())
    id : str = identifier_util.create_objid(
        objid, 
        identifier_util.create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        name)
    upnp_util.set_album_art_from_album_id(
        genre_art, 
        entry)
    return entry

def artist_to_entry(
        objid, 
        artist_id : str,
        entry_name : str,
        options : dict[str, any] = {}) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(), 
        artist_id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        entry_name)
    skip_art : bool = get_option(options = options, option_key = OptionKey.SKIP_ART)
    if not skip_art and artist_id:
        # find art
        art_album_id : str = cache_manager_provider.get().get_random_album_id(artist_id)
        if art_album_id: 
            upnp_util.set_album_art_from_album_id(
                album_id = art_album_id, 
                target = entry)
        else:
            # load artist
            try:
                res : Response[Artist] = connector_provider.get().getArtist(artist_id = artist_id)
                artist : Artist = res.getObj() if res and res.isOk() else None
                album_list : list[Album] = artist.getAlbumList() if artist else None
                select_album : Album = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
                if select_album:
                    cache_manager_provider.get().on_album(select_album)
                upnp_util.set_album_art_from_album_id(
                    album_id = select_album.getId() if select_album else None, 
                    target = entry)
            except Exception as ex:
                msgproc.log(f"artist_to_entry cannot load artist [{artist_id}] [{type(ex)}] [{ex}]")
    upnp_util.set_class_artist(entry)
    return entry

def artist_initial_to_entry(
        objid, 
        artist_initial : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_INITIAL.getName(), 
        artist_initial)
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    artist_set : set[str] = cache_manager_provider.get().get_cached_element(
        ElementType.ARTIST_INITIAL, 
        artist_initial)
    msgproc.log(f"artist_initial_to_entry initial [{artist_initial}] set length [{len(artist_set) if artist_set else 0}]")
    random_artist_id : str = secrets.choice(tuple(artist_set)) if artist_set and len(artist_set) > 0 else None
    art_album_id : str = cache_manager_provider.get().get_random_album_id(random_artist_id) if random_artist_id else None
    msgproc.log(f"artist_initial_to_entry initial [{artist_initial}] -> random artist_id [{random_artist_id}] album_id [{art_album_id}]")
    entry = direntry(id, 
        objid, 
        artist_initial)
    upnp_util.set_album_art_from_album_id(
        art_album_id, 
        entry)
    return entry

def build_intermediate_url(track_id : str) -> str:
    #msgproc.log(f"build_intermediate_url track_id [{track_id}] skip_intermediate_url [{config.skip_intermediate_url}]")
    if not config.skip_intermediate_url:
        http_host_port = os.environ["UPMPD_HTTPHOSTPORT"]
        url = f"http://{http_host_port}/{constants.plugin_name}/track/version/1/trackId/{track_id}"
        if config.log_intermediate_url: msgproc.log(f"intermediate_url for track_id {track_id} -> [{url}]")
        return url
    else:
        return connector_provider.get().buildSongUrl(
            song_id = track_id,
            format = config.get_transcode_codec(),
            max_bitrate = config.get_transcode_max_bitrate())

def song_to_entry(
        objid, 
        song: Song, 
        options : dict[str, any] = {}) -> dict:
    entry = {}
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), song.getId())
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = song.getId()
    upnp_util.set_class_music_track(entry)
    song_uri : str = build_intermediate_url(track_id = song.getId())
    entry['uri'] = song_uri
    title : str = song.getTitle()
    multi_codec_album : MultiCodecAlbum = get_option(options = options, option_key = OptionKey.MULTI_CODEC_ALBUM)
    if MultiCodecAlbum.YES == multi_codec_album and config.allow_blacklisted_codec_in_song == 1 and (not song.getSuffix() in config.whitelist_codecs):
        title = "{} [{}]".format(title, song.getSuffix())
    upnp_util.set_album_title(title, entry)
    entry['tp']= 'it'
    entry['discnumber'] = song.getDiscNumber()
    track_num : str = song.getTrack()
    force_track_number : int = get_option(options = options, option_key = OptionKey.FORCE_TRACK_NUMBER)
    if force_track_number:
        track_num = str(force_track_number)
    upnp_util.set_track_number(track_num, entry)
    upnp_util.set_artist(get_display_artist(song.getArtist()), entry)
    entry['upnp:album'] = song.getAlbum()
    entry['upnp:genre'] = song.getGenre()
    entry['res:mime'] = song.getContentType()
    albumArtURI : str = get_option(options = options, option_key = OptionKey.ALBUM_ART_URI)
    if not albumArtURI:
        albumArtURI = connector_provider.get().buildCoverArtUrl(song.getId())
    upnp_util.set_album_art_from_uri(albumArtURI, entry)
    entry['duration'] = str(song.getDuration())
    return entry

def playlist_to_entry(
        objid, 
        playlist : Playlist) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.PLAYLIST.getName(), 
        playlist.getId())
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    art_uri = connector_provider.get().buildCoverArtUrl(playlist.getCoverArt()) if playlist.getCoverArt() else None
    entry = direntry(id, 
        objid, 
        playlist.getName())
    if art_uri:
        upnp_util.set_album_art_from_uri(art_uri, entry)
    return entry

def album_to_entry(
        objid, 
        album : Album, 
        options : dict[str, any] = {}) -> direntry:
    cache_manager : caching.CacheManager = cache_manager_provider.get()
    title : str = album.getTitle()
    prepend_artist : bool = get_option(options = options, option_key = OptionKey.PREPEND_ARTIST_IN_ALBUM_TITLE)
    if prepend_artist:
        artist : str = album.getArtist()
        if artist: title = f"{artist} - {title}"
    prepend_number : int = get_option(options = options, option_key = OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE)
    if prepend_number: title = f"[{prepend_number:02}] {title}"
    if config.append_year_to_album == 1 and has_year(album):
        title = "{} [{}]".format(title, get_album_year_str(album))
    if config.append_codecs_to_album == 1:
        song_list : list[Song] = album.getSongs()
        # load album
        album_tracks : AlbumTracks = subsonic_util.get_album_tracks(album.getId())
        song_list : list[Song] = album_tracks.getSongList()
        codecs : list[str] = []
        whitelist_count : int = 0
        blacklist_count : int = 0
        song : Song
        for song in song_list:
            if not song.getSuffix() in codecs:
                codecs.append(song.getSuffix())
                if not song.getSuffix() in config.whitelist_codecs:
                    blacklist_count += 1
                else:
                    whitelist_count += 1
        # show version count if count > 1
        if album_tracks.getAlbumVersionCount() > 1:
            title = "{} [{} versions]".format(title, album_tracks.getAlbumVersionCount())
        # show or not?
        all_whitelisted : bool = len(codecs) == whitelist_count
        if len(codecs) > 1 or not all_whitelisted:
            codecs.sort()
            if len(codecs) == 1:
                title = strip_codec_from_album(title, codecs)
            codecs_str : str = ",".join(codecs)
            title = "{} [{}]".format(title, codecs_str)
    artist = album.getArtist()
    cache_manager_provider.get().on_album(album)
    artist_initial : str = artist_initial_cache_provider.get().get(album.getArtistId())
    if artist_initial and album.getArtistId():
        cache_manager.cache_element_multi_value(
            ElementType.ARTIST_INITIAL, 
            artist_initial, 
            album.getArtistId())
    identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), album.getId())
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist)
    upnp_util.set_album_art_from_album_id(
        album.getId(), 
        entry)
    upnp_util.set_album_id(album.getId(), entry)
    upnp_util.set_class_album(entry)
    return entry

def album_version_to_entry(
        objid, 
        current_album : Album, 
        version_number : int, 
        album_version_path : str,
        codec_set : set[str]) -> direntry:
    cache_manager : caching.CacheManager = cache_manager_provider.get()
    identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), current_album.getId())
    avp_encoded : str = codec.encode(album_version_path)
    identifier.set(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, avp_encoded)
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    title : str = f"Version #{version_number}"
    if config.append_year_to_album == 1 and has_year(current_album):
        title = "{} [{}]".format(title, get_album_year_str(current_album))
    codecs_str : str = ",".join(codec_set)
    title = "{} [{}]".format(title, codecs_str)
    last_path : str = get_last_path_element(album_version_path)
    title = "{} [{}]".format(title, last_path)
    artist = current_album.getArtist()
    cache_manager_provider.get().on_album(current_album)
    if current_album.getArtistId():
        #msgproc.log(f"album_version_to_entry searching initial for artist_id {current_album.getArtistId()}")
        artist_initial : str = artist_initial_cache_provider.get().get(current_album.getArtistId())
        if artist_initial and current_album.getArtistId():
            cache_manager.cache_element_multi_value(
                ElementType.ARTIST_INITIAL, 
                artist_initial, 
                current_album.getArtistId())
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist)
    upnp_util.set_album_art_from_album_id(
        current_album.getId(), 
        entry)
    return entry

