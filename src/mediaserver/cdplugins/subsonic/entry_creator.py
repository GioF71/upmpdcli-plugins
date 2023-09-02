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
from subsonic_connector.genre import Genre
from subsonic_connector.song import Song
from subsonic_connector.playlist import Playlist

from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey
from element_type import ElementType

from album_util import MultiCodecAlbum
from album_util import AlbumTracks
from album_util import get_display_artist
from album_util import strip_codec_from_album
from album_util import get_last_path_element

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

from typing import Callable
from upmplgutils import direntry

from msgproc_provider import msgproc

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
    upnp_util.set_album_art_from_album_id(
        artist_art, 
        entry)
    return entry

def album_to_navigable_entry(
        objid, 
        current_album : Album) -> direntry:
    title : str = current_album.getTitle()
    artist : str = current_album.getArtist()
    identifier : ItemIdentifier = ItemIdentifier(ElementType.NAVIGABLE_ALBUM.getName(), current_album.getId())
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    album_year : int = current_album.getYear()
    if album_year:
        title = f"{title} [{album_year}]"
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
    genre_art : str = cache_manager_provider.get().get_cached_element(ElementType.GENRE, current_genre.getName())
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.GENRE.getName(), 
        current_genre.getName())
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
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
        entry_name : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(), 
        artist_id)
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        entry_name)
    art_album_id : str = subsonic_util.get_artist_art(artist_id, subsonic_init_provider.initializer_callback)
    upnp_util.set_album_art_from_album_id(
        art_album_id, 
        entry)
    return entry

def artist_initial_to_entry(
        objid, 
        artist_initial : str) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_INITIAL.getName(), 
        artist_initial)
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    art_album_id : str = cache_manager_provider.get().get_cached_element(ElementType.ARTIST_INITIAL, artist_initial)
    if not art_album_id:
        # can be new
        identifier : ItemIdentifier = ItemIdentifier(ElementType.ARTIST_INITIAL, artist_initial)
        art_album_id = art_retriever.artist_initial_art_retriever(identifier)
        # store if found
        if art_album_id: cache_manager_provider.get().cache_element_value(ElementType.ARTIST_INITIAL, artist_initial, art_album_id)
    entry = direntry(id, 
        objid, 
        artist_initial)
    upnp_util.set_album_art_from_album_id(
        art_album_id, 
        entry)
    return entry

def song_to_entry(
        objid, 
        song: Song, 
        albumArtURI : str = None,
        multi_codec_album : MultiCodecAlbum = MultiCodecAlbum.NO,
        track_num : int = None) -> dict:
    entry = {}
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), song.getId())
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = song.getId()
    upnp_util.set_class_music_track(entry)
    song_uri : str = connector_provider.get().buildSongUrlBySong(song)
    entry['uri'] = song_uri
    title : str = song.getTitle()
    if MultiCodecAlbum.YES == multi_codec_album and config.allow_blacklisted_codec_in_song == 1 and (not song.getSuffix() in config.whitelist_codecs):
        title = "{} [{}]".format(title, song.getSuffix())
    upnp_util.set_album_title(title, entry)
    entry['tp']= 'it'
    entry['discnumber'] = song.getDiscNumber()
    track_num : str = str(track_num) if track_num is not None else song.getTrack()
    upnp_util.set_track_number(track_num, entry)
    upnp_util.set_artist(get_display_artist(song.getArtist()), entry)
    entry['upnp:album'] = song.getAlbum()
    entry['upnp:genre'] = song.getGenre()
    entry['res:mime'] = song.getContentType()
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

def album_to_entry(objid, current_album : Album) -> direntry:
    cache_manager : caching.CacheManager = cache_manager_provider.get()
    title : str = current_album.getTitle()
    if config.append_year_to_album == 1 and current_album.getYear() is not None:
        title = "{} [{}]".format(title, current_album.getYear())
    if config.append_codecs_to_album == 1:
        song_list : list[Song] = current_album.getSongs()
        # load album
        album_tracks : AlbumTracks = subsonic_util.get_album_tracks(current_album.getId())
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
    artist = current_album.getArtist()
    cache_manager.cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
    cache_manager.cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
    artist_initial : str = artist_initial_cache_provider.get().get(current_album.getArtistId())
    if artist_initial:
        cache_manager.cache_element_value(ElementType.ARTIST_INITIAL, artist_initial, current_album.getId())
    identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), current_album.getId())
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist)
    upnp_util.set_album_art_from_album_id(
        current_album.getId(), 
        entry)
    upnp_util.set_album_id(current_album.getId(), entry)
    return entry

def album_version_to_entry(
        objid, 
        current_album : Album, 
        version_number : int, 
        album_version_path : str,
        codec_set : set[str]) -> direntry:
    cache_manager : caching.CacheManager = cache_manager_provider.get()
    #msgproc.log(f"album_version_to_entry creating identifier for album_id {current_album.getId()}")
    identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), current_album.getId())
    avp_encoded : str = codec.encode(album_version_path)
    #msgproc.log(f"album_version_to_entry storing path [{album_version_path}] as [{avp_encoded}]")
    identifier.set(ItemIdentifierKey.ALBUM_VERSION_PATH_BASE64, avp_encoded)
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    #msgproc.log(f"album_version_to_entry caching artist_id {current_album.getArtistId()} to genre {current_album.getGenre()} [{cached}]")
    title : str = f"Version #{version_number}"
    if config.append_year_to_album == 1 and current_album.getYear() is not None:
        title = "{} [{}]".format(title, current_album.getYear())
    codecs_str : str = ",".join(codec_set)
    title = "{} [{}]".format(title, codecs_str)
    last_path : str = get_last_path_element(album_version_path)
    title = "{} [{}]".format(title, last_path)
    artist = current_album.getArtist()
    cache_manager.cache_element_value(ElementType.GENRE, current_album.getGenre(), current_album.getId())
    cache_manager.cache_element_value(ElementType.ARTIST, current_album.getArtistId(), current_album.getId())
    msgproc.log(f"album_version_to_entry searching initial for artist_id {current_album.getArtistId()}")
    artist_initial : str = artist_initial_cache_provider.get().get(current_album.getArtistId())
    if artist_initial:
        cache_manager.cache_element_value(ElementType.ARTIST_INITIAL, artist_initial, current_album.getId())
    entry : dict = direntry(id, 
        objid, 
        title = title, 
        artist = artist)
    upnp_util.set_album_art_from_album_id(
        current_album.getId(), 
        entry)
    return entry

