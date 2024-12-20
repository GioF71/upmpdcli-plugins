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
from album_util import has_year
from album_util import get_album_year_str
from album_util import get_dir_from_path
from album_util import get_album_base_path

import art_retriever
import config
import connector_provider
import identifier_util
import upnp_util
import cache_manager_provider
import subsonic_util
import codec
import constants
import cache_actions

from option_key import OptionKey
from option_util import get_option

import upmplgutils

from msgproc_provider import msgproc

import secrets
import os

import persistence

__DICT_KEY_BITDEPTH: str = "BIT_DEPTH"
__DICT_KEY_SAMPLERATE: str = "SAMPLE_RATE"
__DICT_KEY_SUFFIX: str = "SUFFIX"
__DICT_KEY_BITRATE: str = "BITRATE"


__readable_sr: dict[int, str] = {
    44100: "44k",
    48000: "48k",
    88200: "88k",
    96000: "96k",
    176400: "176k",
    192000: "192k",
    352800: "352k",
    384000: "384k",
    705600: "705k",
    768000: "768k",
    1411200: "1411k",
    1536000: "1536k",
    2822400: "2.8M",
    5644800: "5.6M",
    11289600: "11.2M",
    22579200: "22.4M"
}

additional_lossy_prefix_set: set[str] = {}


class TrackInfo:

    def __init__(self):
        self.__trackId: str = None
        self.__bitrate: int = None
        self.__bit_depth: int = None
        self.__sampling_rate: int = None
        self.__suffix: str = None

    @property
    def trackId(self) -> str:
        return self.__trackId

    @trackId.setter
    def trackId(self, value: str):
        self.__trackId = value

    @property
    def bitrate(self) -> int:
        return self.__bitrate

    @bitrate.setter
    def bitrate(self, value: int):
        self.__bitrate = value

    @property
    def bit_depth(self) -> int:
        return self.__bit_depth

    @bit_depth.setter
    def bit_depth(self, value: int):
        self.__bit_depth = value

    @property
    def sampling_rate(self) -> int:
        return self.__sampling_rate

    @sampling_rate.setter
    def sampling_rate(self, value: int):
        self.__sampling_rate = value

    @property
    def suffix(self) -> str:
        return self.__suffix

    @suffix.setter
    def suffix(self, value: int):
        self.__suffix = value

    def is_lossy(self):
        if not self.bit_depth or self.bit_depth == 0:
            return True
        # also select suffix are lossy
        if self.__suffix:
            return self.__suffix in additional_lossy_prefix_set
        return False


def __maybe_append_to_dict_list(
        prop_dict: dict[str, list[any]],
        dict_key: str,
        new_value: any):
    if new_value is None:
        return
    item_list: list[any] = None
    if dict_key not in prop_dict:
        item_list = list()
        # list was not there, safe to add
        item_list.append(new_value)
        prop_dict[dict_key] = item_list
    else:
        item_list = prop_dict[dict_key]
        if new_value not in item_list:
            item_list.append(new_value)


def __get_track_info_list(track_list: list[Song]) -> list[TrackInfo]:
    result: list[TrackInfo] = list()
    song: Song
    for song in track_list:
        bit_depth: int = song.getItem().getByName(constants.ItemKey.BIT_DEPTH.value)
        sampling_rate: int = song.getItem().getByName(constants.ItemKey.SAMPLING_RATE.value)
        suffix: int = song.getSuffix()
        bitrate: int = song.getBitRate()
        current: TrackInfo = TrackInfo()
        current.bit_depth = bit_depth
        current.sampling_rate = sampling_rate
        current.suffix = suffix
        current.bitrate = bitrate
        result.append(current)
    return result


def __all_lossy(track_info_list: list[TrackInfo]) -> bool:
    current: TrackInfo
    for current in track_info_list if track_info_list else list():
        if not current.is_lossy():
            return False
    return True


def __get_track_list_streaming_properties(track_list: list[Song]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = dict()
    song: Song
    for song in track_list:
        # bit depth
        bit_depth: int = song.getItem().getByName(constants.ItemKey.BIT_DEPTH.value)
        __maybe_append_to_dict_list(result, __DICT_KEY_BITDEPTH, bit_depth)
        # sampling rate
        sampling_rate: int = song.getItem().getByName(constants.ItemKey.SAMPLING_RATE.value)
        __maybe_append_to_dict_list(result, __DICT_KEY_SAMPLERATE, sampling_rate)
        # suffix
        suffix: int = song.getSuffix()
        __maybe_append_to_dict_list(result, __DICT_KEY_SUFFIX, suffix)
        # bitrate
        bitrate: int = song.getBitRate()
        __maybe_append_to_dict_list(result, __DICT_KEY_BITRATE, bitrate)
    return result


def __get_unique_bitrate(prop_dict: dict[str, list[int]]) -> int:
    bitrate_list: list[int] = (prop_dict[__DICT_KEY_BITRATE]
                               if __DICT_KEY_BITRATE in prop_dict
                               else list())
    if len(bitrate_list) == 1:
        return bitrate_list[0]
    return None


def __get_avg_bitrate(track_info_list: list[TrackInfo]) -> float:
    sum: float = 0.0
    current: TrackInfo
    for current in track_info_list:
        sum += float(current.bitrate) if current.bitrate else 0.0
    return sum / float(len(track_info_list))


def __get_avg_bitrate_int(track_info_list: list[TrackInfo]):
    return int(__get_avg_bitrate(track_info_list))


def __get_unique_sampling_rate(prop_dict: dict[str, list[int]]) -> int:
    sampling_rate_list: list[int] = (prop_dict[__DICT_KEY_SAMPLERATE]
                                     if __DICT_KEY_SAMPLERATE in prop_dict
                                     else list())
    if len(sampling_rate_list) == 1:
        return sampling_rate_list[0]
    return None


def __get_unique_suffix(prop_dict: dict[str, list[int]]) -> str:
    suffix_list: list[str] = (prop_dict[__DICT_KEY_SUFFIX]
                              if __DICT_KEY_SUFFIX in prop_dict
                              else list())
    if len(suffix_list) == 1:
        return suffix_list[0]
    return None


def artist_entry_for_album(objid, album: Album) -> dict[str, any]:
    msgproc.log(f"artist_entry_for_album album_id: [{album.getId()}]")
    artist_identifier: ItemIdentifier = ItemIdentifier(
        name=ElementType.ARTIST.getName(),
        value=album.getArtistId())
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(artist_identifier))
    entry_title: str = album.getArtist()
    if config.show_artist_id() and album.getArtistId():
        msgproc.log(f"artist_entry_for_album: Adding [{album.getArtistId()}] to [{entry_title}]")
        entry_title = f"{entry_title} [{album.getArtistId()}]"
    if config.show_artist_mb_id():
        # we want the artist mb id, so we load the artist
        artist_res: Response[Artist] = connector_provider.get().getArtist(album.getArtistId())
        loaded_artist: Artist = artist_res.getObj() if artist_res and artist_res.isOk() else None
        artist_mb_id: str = (loaded_artist.getItem().getByName(constants.ItemKey.MUSICBRAINZ_ID.value)
                             if loaded_artist
                             else None)
        if artist_mb_id:
            entry_title = f"{entry_title} [mb:{artist_mb_id}]"
    artist_entry: dict[str, any] = upmplgutils.direntry(
        id,
        objid,
        title=entry_title)
    # get an album cover for the artist entry
    art_uri: str = (art_retriever.get_artist_art_url_using_albums(artist_id=album.getArtistId())
                    if album.getArtistId() else None)
    upnp_util.set_album_art_from_uri(album_art_uri=art_uri, target=artist_entry)
    cache_actions.on_album(album)
    return artist_entry


def get_album_quality_badge(album: Album, force_load: bool = False) -> str:
    if force_load:
        msgproc.log(f"get_album_quality_badge for album_id: [{album.getId()}] force_load: [{force_load}]")
        res: Response[Album] = connector_provider.get().getAlbum(albumId=album.getId())
        reloaded: Album = res.getObj() if res and res.isOk() else None
        if not reloaded:
            raise Exception(f"Cannot find {Album.__name__} with album_id [{album.getId()}]")
        quality_badge: str = get_track_list_badge(
            track_list=reloaded.getSongs(),
            list_identifier=album.getId())
        return quality_badge
    else:
        album_metadata: persistence.AlbumMetadata = persistence.get_album_metadata(album_id=album.getId())
        if album_metadata:
            return album_metadata.quality_badge


def __store_album_badge(album_id: str, quality_badge: str) -> str:
    if album_id:
        persistence.save_quality_badge(album_id=album_id, quality_badge=quality_badge)
    return quality_badge


def get_track_list_badge(track_list: list[Song], list_identifier: str = None) -> str:
    quality_badge: str = __get_track_list_badge(track_list, list_identifier)
    if quality_badge and list_identifier:
        __store_album_badge(album_id=list_identifier, quality_badge=quality_badge)
    return quality_badge


def __get_track_list_badge(track_list: list[Song], list_identifier: str = None) -> str:
    prop_dict: dict[str, list[int]] = __get_track_list_streaming_properties(track_list)
    track_info_list: list[TrackInfo] = __get_track_info_list(track_list)
    if not track_info_list or len(track_info_list) == 0:
        raise Exception("No tracks were processed")
    if (__DICT_KEY_BITDEPTH not in prop_dict or
       __DICT_KEY_SAMPLERATE not in prop_dict):
        msgproc.log(f"No streaming information available in [{list_identifier}]")
        return None
    # information are available, go on ...
    # are they all lossy?
    all_lossy: bool = __all_lossy(track_info_list)
    # do they all have the same bitrate?
    unique_bitrate: int = __get_unique_bitrate(prop_dict)
    # do they all have the same suffix?
    unique_suffix: str = __get_unique_suffix(prop_dict)
    # do they all have the same sampling rate?
    unique_sampling_rate: int = __get_unique_sampling_rate(prop_dict)
    if all_lossy:
        # we always return from this branch
        if unique_bitrate and unique_suffix and unique_sampling_rate:
            return f"{unique_suffix}@{unique_bitrate}/{unique_sampling_rate}"
        else:
            avg_bitrate: int = __get_avg_bitrate_int(track_info_list)
            if (unique_suffix and unique_sampling_rate and
                    (avg_bitrate and avg_bitrate > 0)):
                # use avg bitrate rate
                return f"{unique_suffix}@{avg_bitrate}/{unique_sampling_rate}"
            elif unique_suffix and unique_sampling_rate:
                # no avg bitrate
                return f"{unique_suffix}/{unique_sampling_rate}"
            elif unique_suffix:
                return unique_suffix
            else:
                # fallback
                return "LOSSY"
    bit_depth_list: list[int] = prop_dict[__DICT_KEY_BITDEPTH]
    bit_depth_list.sort(reverse=True)
    sampling_rate_list: list[int] = prop_dict[__DICT_KEY_SAMPLERATE]
    sampling_rate_list.sort(reverse=True)
    if len(bit_depth_list) == 0 or len(sampling_rate_list) == 0:
        msgproc.log("Empty streaming info in [{list_identifier}]")
        return None
    best_bit_depth: int = bit_depth_list[0]
    best_sampling_rate: int = sampling_rate_list[0]
    if len(bit_depth_list) > 1 or len(sampling_rate_list) > 1:
        if best_bit_depth == 16 and best_sampling_rate == 44100:
            return "~CD"
        if best_bit_depth == 24 and best_sampling_rate >= 44100:
            return "~HD"
        if best_bit_depth == 0:
            return "LOSSY"
    else:
        # list sizes or bit_depth and sampling rate are 1
        sr: str = (__readable_sr[best_sampling_rate]
                   if best_sampling_rate in __readable_sr
                   else str(best_sampling_rate))
        if best_bit_depth == 0:
            # lossy
            suffix_list: list[str] = (prop_dict[__DICT_KEY_SUFFIX]
                                      if __DICT_KEY_SUFFIX in prop_dict
                                      else list())
            display_codec: str = (suffix_list[0]
                                  if len(suffix_list) == 1
                                  else "LOSSY")
            if unique_bitrate:
                display_codec = f"{display_codec}@{unique_bitrate}"
            return f"{display_codec}/{sr}"
        if unique_suffix and unique_suffix in config.whitelist_codecs:
            if best_bit_depth == 1:
                return f"DSD {sr}"
            else:
                return f"{best_bit_depth}/{sr}"
        elif unique_suffix:
            # mention suffix
            if best_bit_depth == 1:
                return f"{unique_suffix}@DSD/{sr}"
            else:
                return f"{unique_suffix}@{best_bit_depth}/{sr}"
        else:
            # use ~ as we don't have an unique suffix
            if best_bit_depth == 1:
                return f"~DSD {sr}"
            else:
                return f"~{best_bit_depth}/{sr}"
    return "LOSSY"


def genre_artist_to_entry(
        objid,
        genre: str,
        artist_id: str,
        artist_name: str) -> dict[str, any]:
    msgproc.log(f"genre_artist_to_entry genre:[{genre}] artist_id:[{artist_id}] artist_name:[{artist_name}]")
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.GENRE_ARTIST.getName(),
        artist_id)
    identifier.set(ItemIdentifierKey.GENRE_NAME, genre)
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(
        id,
        objid,
        artist_name)
    if artist_id:
        entry = artist_to_entry(
            objid=objid,
            artist_id=artist_id,
            entry_name=artist_name)
    return entry


def album_to_navigable_entry(
        objid,
        album: Album,
        options: dict[str, any] = {}) -> dict[str, any]:
    title: str = album.getTitle()
    prepend_artist: bool = get_option(options=options, option_key=OptionKey.PREPEND_ARTIST_IN_ALBUM_TITLE)
    if prepend_artist:
        artist: str = album.getArtist()
        if artist:
            title = f"{artist} - {title}"
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
        title = f"{title} [{get_album_year_str(album)}]"
    album_badge: str = get_album_quality_badge(album=album, force_load=False)
    # msgproc.log(f"album_to_navigable_entry album [{album.getId()}] -> badge [{album_badge}]")
    if album_badge:
        title = f"{title} [{album_badge}]"
        # msgproc.log(f"album_to_navigable_entry title [{title}]")
    entry_title: str = title
    if config.show_album_id_in_navigable_album() and album.getId():
        # msgproc.log(f"album_to_navigable_entry Adding [{album.getId()}] to [{entry_title}]")
        entry_title = f"{entry_title} [{album.getId()}]"
    if config.show_album_mb_id_in_album():
        # available here?
        mb_id: str = album.getItem().getByName(constants.ItemKey.MUSICBRAINZ_ID.value)
        if not mb_id:
            # see if it's available in cache
            mb_id = cache_actions.get_album_mb_id(album.getId())
            msgproc.log(f"Got album mb_id from cache for [{album.getId()}] -> [{mb_id}]")
        else:
            msgproc.log(f"Album mb_id for [{album.getId()}] -> [{mb_id}]")

        if mb_id:
            # we can display it!
            entry_title = f"{entry_title} [{mb_id}]"
    entry: dict[str, any] = upmplgutils.direntry(
        id=id,
        pid=objid,
        title=entry_title,
        artist=artist)
    upnp_util.set_album_art_from_uri(connector_provider.get().buildCoverArtUrl(album.getCoverArt()), entry)
    upnp_util.set_album_id(album.getId(), entry)
    return entry


def genre_to_entry(
        objid,
        current_genre: Genre) -> dict[str, any]:
    name: str = current_genre.getName()
    genre_art: str = None
    genre_album_set: set[str] = cache_manager_provider.get().get_cached_element(
        ElementType.GENRE,
        name)
    random_album_id: str = (secrets.choice(tuple(genre_album_set))
                            if genre_album_set and len(genre_album_set) > 0
                            else None)
    if random_album_id:
        # load the album
        random_res: Response[Album] = connector_provider.get().getAlbum(albumId=random_album_id)
        random_album: Album = random_res.getObj() if random_res.isOk() else None
        # get album art
        genre_art = random_album.getCoverArt() if random_album else None
    if not genre_art:
        res: Response[AlbumList] = connector_provider.get().getAlbumList(
            ltype=ListType.BY_GENRE,
            genre=name)
        if not res or not res.isOk():
            msgproc.log(f"Cannot get albums by genre [{name}]")
        album_list: AlbumList = res.getObj()
        msgproc.log(f"Loaded [{len(album_list.getAlbums()) if album_list and album_list.getAlbums() else 0}] "
                    f"albums for genre [{name}]")
        if album_list and len(album_list.getAlbums()) > 0:
            album: Album = secrets.choice(album_list.getAlbums())
            genre_art = album.getCoverArt()
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.GENRE.getName(),
        current_genre.getName())
    id: str = identifier_util.create_objid(
        objid,
        identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, name)
    upnp_util.set_album_art_from_uri(connector_provider.get().buildCoverArtUrl(genre_art), entry)
    return entry


def artist_to_entry(
        objid,
        artist_id: str,
        entry_name: str,
        options: dict[str, any] = {}) -> dict[str, any]:
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(),
        artist_id)
    id: str = identifier_util.create_objid(
        objid=objid,
        id=identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, entry_name)
    skip_art: bool = get_option(options=options, option_key=OptionKey.SKIP_ART)
    if not skip_art and artist_id:
        # find art
        art_album_id: str = cache_actions.get_cached_random_album_id_by_artist_id(artist_id=artist_id)
        if art_album_id:
            msgproc.log(f"artist_to_entry cache hit for [{artist_id}] -> [{art_album_id}]")
            art_album_res: Response[Album] = connector_provider.get().getAlbum(art_album_id)
            art_album: Album = art_album_res.getObj() if art_album_res.isOk() else None
            art_album_cover_art_uri: str = (connector_provider.get().buildCoverArtUrl(art_album.getCoverArt())
                                            if art_album
                                            else None)
            upnp_util.set_album_art_from_uri(album_art_uri=art_album_cover_art_uri, target=entry)
        else:
            msgproc.log(f"artist_to_entry loading artist by id [{artist_id}] ...")
            # load artist
            try:
                res: Response[Artist] = connector_provider.get().getArtist(artist_id=artist_id)
                artist: Artist = res.getObj() if res and res.isOk() else None
                album_list: list[Album] = artist.getAlbumList() if artist else None
                select_album: Album = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
                cache_actions.on_album_for_artist_id(artist_id=artist_id, album=select_album)
                cache_actions.on_album(album=select_album)
                upnp_util.set_album_art_from_uri(
                    album_art_uri=connector_provider.get().buildCoverArtUrl(select_album.getCoverArt())
                    if select_album
                    else None,
                    target=entry)
            except Exception as ex:
                msgproc.log(f"artist_to_entry cannot load artist [{artist_id}] [{type(ex)}] [{ex}]")
    upnp_util.set_class_artist(entry)
    return entry


def artist_initial_to_entry(
        objid,
        artist_initial: str,
        options: dict[str, any] = dict()) -> dict[str, any]:
    encoded_artist_initial: str = codec.encode(artist_initial)
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_BY_INITIAL.getName(),
        encoded_artist_initial)
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry: dict[str, any] = upmplgutils.direntry(id, objid, artist_initial)
    return entry


def build_intermediate_url(track_id: str) -> str:
    if not config.skip_intermediate_url:
        http_host_port = os.environ["UPMPD_HTTPHOSTPORT"]
        url = f"http://{http_host_port}/{constants.plugin_name}/track/version/1/trackId/{track_id}"
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
        options: dict[str, any] = {}) -> dict:
    entry = {}
    identifier: ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), song.getId())
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = song.getId()
    upnp_util.set_class_music_track(entry)
    song_uri: str = build_intermediate_url(track_id=song.getId())
    entry['uri'] = song_uri
    title: str = song.getTitle()
    multi_codec_album: MultiCodecAlbum = get_option(options=options, option_key=OptionKey.MULTI_CODEC_ALBUM)
    if (MultiCodecAlbum.YES == multi_codec_album and
        config.allow_blacklisted_codec_in_song == 1 and
            (not song.getSuffix() in config.whitelist_codecs)):
        title = "{} [{}]".format(title, song.getSuffix())
    upnp_util.set_album_title(title, entry)
    entry['tp'] = 'it'
    entry['discnumber'] = song.getDiscNumber()
    track_num: str = song.getTrack()
    force_track_number: int = get_option(options=options, option_key=OptionKey.FORCE_TRACK_NUMBER)
    if force_track_number:
        track_num = str(force_track_number)
    upnp_util.set_track_number(track_num, entry)
    upnp_util.set_artist(get_display_artist(song.getArtist()), entry)
    entry['upnp:album'] = song.getAlbum()
    entry['upnp:genre'] = song.getGenre()
    entry['res:mime'] = song.getContentType()
    album_id: str = song.getAlbumId()
    # prefer album for cover art
    # album_art_uri: str = connector_provider.get().buildCoverArtUrl(album_id if album_id else song.getId())
    album_art_uri: str = connector_provider.get().buildCoverArtUrl(song.getCoverArt())
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
    if song.getItem().hasName(constants.ItemKey.BIT_DEPTH.value):
        bd = song.getItem().getByName(constants.ItemKey.BIT_DEPTH.value)
        upnp_util.set_bit_depth(bd, entry)
    if song.getItem().hasName(constants.ItemKey.SAMPLING_RATE.value):
        sr = song.getItem().getByName(constants.ItemKey.SAMPLING_RATE.value)
        upnp_util.set_sample_rate(sr, entry)
    br = song.getBitRate()
    if br:
        upnp_util.set_bit_rate(br, entry)
    if config.dump_streaming_properties:
        msgproc.log(f"Song [{song.getId()}] -> bitDepth [{bd}] "
                    f"samplingRate [{sr}] bitRate [{br}] "
                    f"channelCount [{cc}] "
                    f"mimetype [{song.getContentType()}] "
                    f"duration [{song.getDuration()}]")
    return entry


def playlist_to_entry(
        objid,
        playlist: Playlist) -> dict[str, any]:
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.PLAYLIST.getName(),
        playlist.getId())
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, objid, playlist.getName())
    art_uri: str = (connector_provider.get().buildCoverArtUrl(playlist.getCoverArt())
                    if playlist.getCoverArt() else None)
    upnp_util.set_album_art_from_uri(album_art_uri=art_uri, target=entry)
    return entry


def album_to_entry(
        objid,
        album: Album,
        options: dict[str, any] = {}) -> dict[str, any]:
    title: str = album.getTitle()
    prepend_artist: bool = get_option(options=options, option_key=OptionKey.PREPEND_ARTIST_IN_ALBUM_TITLE)
    if prepend_artist:
        artist: str = album.getArtist()
        if artist:
            title = f"{artist} - {title}"
    prepend_number: int = get_option(options=options, option_key=OptionKey.PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE)
    if prepend_number:
        title = f"[{prepend_number:02}] {title}"
    if config.append_year_to_album == 1 and has_year(album):
        title = "{} [{}]".format(title, get_album_year_str(album))
    force_load: bool = get_option(options=options, option_key=OptionKey.FORCE_LOAD_QUALITY_BADGE)
    album_badge: str = get_album_quality_badge(album=album, force_load=force_load)
    msgproc.log(f"album_to_entry album_badge for [{album.getId()}] is [{album_badge}] force_load was [{force_load}]")
    if force_load and config.append_codecs_to_album == 1:
        msgproc.log(f"album_to_entry for "
                    f"album_id: [{album.getId()}] "
                    f"badge [{album_badge if album_badge else 'not available'}] "
                    "loading songs ...")
        song_list: list[Song] = album.getSongs()
        # load album
        album_tracks: AlbumTracks = subsonic_util.get_album_tracks(album.getId())
        song_list: list[Song] = album_tracks.getSongList()
        codecs: list[str] = []
        whitelist_count: int = 0
        blacklist_count: int = 0
        song: Song
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
        all_whitelisted: bool = len(codecs) == whitelist_count
        if len(codecs) > 1 or not all_whitelisted:
            codecs.sort()
            if len(codecs) == 1:
                title = strip_codec_from_album(title, codecs)
            codecs_str: str = ",".join(codecs)
            # add codecs if more than one or there is no quality_badge
            if (len(codecs) > 1) or (not album_badge or len(album_badge) == 0):
                title = "{} [{}]".format(title, codecs_str)
    # msgproc.log(f"album_to_entry album [{album.getId()}] -> badge [{album_badge}]")
    if album_badge:
        title = f"{title} [{album_badge}]"
        # msgproc.log(f"album_to_entry title [{title}]")
    artist = album.getArtist()
    cache_actions.on_album(album)
    identifier: ItemIdentifier = ItemIdentifier(ElementType.ALBUM.getName(), album.getId())
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    entry: dict[str, any] = upmplgutils.direntry(id, objid, title=title, artist=artist)
    cover_art_url: str = connector_provider.get().buildCoverArtUrl(album.getCoverArt())
    upnp_util.set_album_art_from_uri(cover_art_url, entry)
    upnp_util.set_album_id(album.getId(), entry)
    upnp_util.set_class_album(entry)
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
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    art_uri = connector_provider.get().buildCoverArtUrl(item_id=album.getCoverArt())
    entry = upmplgutils.direntry(id, objid, "Focus")
    upnp_util.set_album_art_from_uri(album_art_uri=art_uri, target=entry)
    return entry


def artist_id_to_artist_focus(
        objid,
        artist_id: str) -> dict[str, any]:
    identifier: ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_FOCUS.getName(),
        artist_id)
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
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
    id: str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    title: str = f"Version #{version_number}"
    if config.append_year_to_album == 1 and has_year(current_album):
        title = "{} [{}]".format(title, get_album_year_str(current_album))
    codecs_str: str = ",".join(codec_set)
    title = "{} [{}]".format(title, codecs_str)
    last_path: str = get_last_path_element(album_version_path)
    title = "{} [{}]".format(title, last_path)
    # album badge on the list of tracks
    track_list: list[Song] = _load_album_version_tracks(
        album=current_album,
        album_version_path=album_version_path)
    album_badge: str = get_track_list_badge(track_list)
    msgproc.log(f"album_version_to_entry album [{current_album.getId()}] -> badge [{album_badge}]")
    if album_badge:
        title = f"{title} [{album_badge}]"
        msgproc.log(f"album_version_to_entry title [{title}]")
    artist = current_album.getArtist()
    cache_actions.on_album(current_album)
    entry: dict[str, any] = upmplgutils.direntry(id, objid, title=title, artist=artist)
    current_album_cover_art: str = connector_provider.get().buildCoverArtUrl(item_id=current_album.getCoverArt())
    upnp_util.set_album_art_from_uri(current_album_cover_art, entry)
    return entry
