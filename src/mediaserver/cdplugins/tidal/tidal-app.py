#!/usr/bin/python3

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

__tidal_plugin_release : str = "0.0.4"

import json
import copy
import os

import datetime
from typing import Callable

import cmdtalkplugin
import upmplgutils
import html
import xbmcplug

import codec
import identifier_util
import upnp_util
import constants
import persistence

from tag_type import TagType
from tag_type import get_tag_Type_by_name
from element_type import ElementType
from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey
from option_key import OptionKey
from search_type import SearchType
from tile_type import TileType
from tile_type import get_tile_type_by_name

from tidalapi import Quality as TidalQuality
from tidalapi.session import Session as TidalSession
from tidalapi.album import Album as TidalAlbum
from tidalapi.artist import Artist as TidalArtist
from tidalapi.mix import Mix as TidalMix
from tidalapi.playlist import Playlist as TidalPlaylist
from tidalapi.playlist import UserPlaylist as TidalUserPlaylist
from tidalapi.media import Track as TidalTrack
from tidalapi.page import Page as TidalPage
from tidalapi.page import PageItem as TidalPageItem
from tidalapi.page import ItemList as TidalItemList
from tidalapi.page import PageLink as TidalPageLink
from tidalapi.page import FeaturedItems as TidalFeaturedItems
from tidalapi.genre import Genre as TidalGenre

from played_track import PlayedTrack
from tile_image import TileImage

plugin_name : str = constants.plugin_name

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = f"0${plugin_name}$"
upmplgutils.setidprefix(plugin_name)

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

session : TidalSession = None

default_image_sz_by_type : dict[str, int] = dict()
default_image_sz_by_type[TidalArtist.__name__] = [750, 480, 320, 160]
default_image_sz_by_type[TidalAlbum.__name__] = [1280, 640, 320, 160, 80]
default_image_sz_by_type[TidalPlaylist.__name__] = [1080, 750, 640, 480, 320, 160]
default_image_sz_by_type[TidalMix.__name__] = [1500, 640, 320]
default_image_sz_by_type[TidalUserPlaylist.__name__] = default_image_sz_by_type[TidalPlaylist.__name__]

log_intermediate_url : bool = upmplgutils.getOptionValue(f"{plugin_name}log_intermediate_url", "0") == "1"
log_unavailable_images_sizes : bool = upmplgutils.getOptionValue(f"{plugin_name}log_unavailable_images_sizes", "0") == "1"
log_unavailable_image : bool = upmplgutils.getOptionValue(f"{plugin_name}log_unavailable_image", "0") == "1"

def has_type_attr(obj : any) -> str:
    if hasattr(obj, "type"):
        return True
    return False

def has_image_method(obj : any) -> str:
    if hasattr(obj, "image") and callable(obj.image):
        return True
    return False

def get_image_if_available(obj : any) -> str:
    if hasattr(obj, "image"):
        return obj.image
    return None

def get_name_or_title(obj : any) -> str:
    if hasattr(obj, "name"):
        return obj.name
    if hasattr(obj, "title"):
        return obj.title
    return None

def get_image_dimension_list(obj : any) -> list[int]:
    key = type(obj).__name__
    return default_image_sz_by_type[key] if key in default_image_sz_by_type else list()

def safe_get_image_url(obj : any) -> str:
    if has_image_method(obj): return get_image_url(obj)

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
                msgproc.log(f"Cannot find image for type [{type(obj).__name__}] id [{obj.id}] Name [{get_name_or_title(obj)}] with size [{current}]")
    if log_unavailable_image:
        msgproc.log(f"Cannot find image for type [{type(obj).__name__}] id [{obj.id}] Name [{get_name_or_title(obj)}] (any size)")
    return None

def get_audio_quality(quality_desc : str) -> TidalQuality:
    for _, member in TidalQuality.__members__.items():
        if quality_desc == member.value:
            return member
    # fallback
    return TidalQuality.high_lossless

def get_config_audio_quality() -> TidalQuality:
    return get_audio_quality(upmplgutils.getOptionValue(f"{plugin_name}audioquality", "LOSSLESS"))

def mp3_only() -> bool:
    q : TidalQuality = get_config_audio_quality()
    return is_mp3(q)

def is_mp3(q : TidalQuality) -> bool:
    return q == TidalQuality.low_320k or q == TidalQuality.low_96k

def create_session():
    global session
    res : bool = False
    if not session:
        new_session : TidalSession = TidalSession()
        token_type = upmplgutils.getOptionValue(f"{plugin_name}tokentype")
        access_token : str = upmplgutils.getOptionValue(f"{plugin_name}accesstoken")
        refresh_token : str = upmplgutils.getOptionValue(f"{plugin_name}refreshtoken")
        expiry_time_timestamp_str : str = upmplgutils.getOptionValue(f"{plugin_name}expirytime")
        expiry_time_timestamp : float = float(expiry_time_timestamp_str)
        expiry_time = datetime.datetime.fromtimestamp(expiry_time_timestamp)
        audio_quality : TidalQuality = get_audio_quality(upmplgutils.getOptionValue(f"{plugin_name}audioquality"))
        res : bool = new_session.load_oauth_session(token_type, access_token, refresh_token, expiry_time)
        new_session.audio_quality = audio_quality
        msgproc.log(f"Tidal session created: [{res}]")
        session = new_session
    else: res = True
    return res

def get_session() -> TidalSession:
    global session
    if not create_session():
        msgproc.log("Cannot create Tidal session")
    else:
        return session

def build_intermediate_url(track : TidalTrack) -> str:
    http_host_port = os.environ["UPMPD_HTTPHOSTPORT"]
    url = f"http://{http_host_port}/{plugin_name}/track/version/1/trackId/{track.id}"
    if log_intermediate_url: msgproc.log(f"intermediate_url for track_id {track.id} -> [{url}]")
    return url

def build_streaming_url(track_id : str) -> str:
    streaming_url : str = get_session().track(track_id).get_url()
    msgproc.log(f"build_streaming_url for track_id: [{track_id}] -> [{streaming_url}]")
    return streaming_url

@dispatcher.record('trackuri')
def trackuri(a):
    upmpd_pathprefix = os.environ["UPMPD_PATHPREFIX"]
    msgproc.log(f"UPMPD_PATHPREFIX: [{upmpd_pathprefix}] trackuri: [{a}]")
    track_id = xbmcplug.trackid_from_urlpath(upmpd_pathprefix, a)
    url = build_streaming_url(track_id) or ""
    if url:
        track : TidalTrack = get_session().track(track_id)
        if track:
            album_id : str = track.album.id
            album : TidalAlbum = get_session().album(album_id)
            if album:
                album_track_count : int = album.num_tracks
                persistence.track_playback(
                    track_id = track_id, 
                    album_id = album_id, 
                    album_track_count = album_track_count)
    return {'media_url' : url}

def _returnentries(entries):
    """Helper function: build plugin browse or search return value from items list"""
    return {"entries" : json.dumps(entries), "nocache" : "0"}

def _objidtopath(objid):
    if objid.find(_g_myprefix) != 0:
        raise Exception(f"subsonic: bad objid {objid}: bad prefix")
    return objid[len(_g_myprefix):].lstrip("/")

def is_tile_imaged_expired(tile_image : TileImage) -> bool:
    update_time : datetime.datetime = tile_image.update_time
    if not update_time: return True
    if update_time < (datetime.datetime.now() - datetime.timedelta(seconds = constants.tile_image_expiration_time_sec)):
        return True
    return False

def get_category_image_url(category : TidalItemList) -> str:
    category_tile_image : TileImage = persistence.load_tile_image(TileType.CATEGORY, category.title)
    tile_image_valid : bool = category_tile_image and not is_tile_imaged_expired(category_tile_image)
    category_image_url : str = category_tile_image.tile_image if tile_image_valid else None
    msgproc.log(f"Category [{category.title}] type: [{type(category)}] cached: [{'yes' if category_image_url else 'no'}]")
    if not category_image_url:
        # load category image
        if isinstance(category, TidalFeaturedItems):
            featured : TidalFeaturedItems = category
            first_featured = featured.items[0] if featured.items and len(featured.items) > 0 else None
            if not first_featured: msgproc.log(f"Category [{category.title}] Featured: first_featured not found")
            has_type_attribute : bool = first_featured and has_type_attr(first_featured)
            if first_featured and not has_type_attribute: msgproc.log(f"Category [{category.title}] Featured: first_featured no type attribute, type [{type(first_featured)}]")
            if first_featured and has_type_attribute:
                msgproc.log(f"Category [{category.title}] (TidalFeaturedItems) first item type [{first_featured.type if first_featured else None}]")
                if first_featured.type == constants.featured_type_name_playlist:
                    playlist : TidalPlaylist = get_session().playlist(first_featured.artifact_id)
                    image_url = safe_get_image_url(playlist) if playlist else None
                    if not image_url: msgproc.log(f"Category [{category.title}] (TidalFeaturedItems): cannot get image for playlist")
                else:
                    msgproc.log(f"Category [{category.title}] (TidalFeaturedItems): not processed item {first_featured.type}")
        else: # other than FeaturedItems ...
            first_item = category.items[0] if category.items and len(category.items) > 0 else None
            first_item_type : type = type(first_item) if first_item else None
            msgproc.log(f"Starting load process for category [{category.title}], type of first_item [{first_item_type.__name__ if first_item_type else None}]")
            image_url : str = None
            if first_item:
                if isinstance(first_item, TidalTrack):
                    msgproc.log(f"  processing as Track ...")
                    track : TidalTrack = first_item
                    album : TidalAlbum = get_session().album(track.album.id)
                    image_url = get_image_url(album) if album else None
                    msgproc.log(f"Chosen image for category [{category.title}] using type [{type(first_item)}] image_url [{image_url}]")
                elif isinstance(first_item, TidalMix):
                    msgproc.log(f"  processing as Mix ...")
                    mix : TidalMix = first_item
                    image_url = get_image_url(mix) if mix else None
                    msgproc.log(f"Chosen image for category [{category.title}] using type [{type(first_item)}] image_url [{image_url}]")
                elif isinstance(first_item, TidalPlaylist):
                    msgproc.log(f"  processing as Playlist ...")
                    playlist : TidalPlaylist = first_item
                    image_url = get_image_url(playlist) if playlist else None
                    msgproc.log(f"Chosen image for category [{category.title}] using type [{type(first_item)}] image_url [{image_url}]")
                elif isinstance(first_item, TidalAlbum):
                    msgproc.log(f"  processing as Album ...")
                    album : TidalAlbum = first_item
                    image_url = get_image_url(album) if album else None
                    msgproc.log(f"Chosen image for category [{category.title}] using type [{type(first_item)}] image_url [{image_url}]")
                elif isinstance(first_item, TidalPageLink):
                    msgproc.log(f"  processing as <PageLink> ...")
                    page_link : TidalPageLink = first_item
                    first_item = get_first_item_in_page_link(page_link)
                    msgproc.log(f"    followed <PageLink>, got: {type(first_item) if first_item else None} ...")
                    if isinstance(first_item, TidalPageItem) or isinstance(first_item, TidalFeaturedItems):
                        msgproc.log(f"Category [{category.title}] type [{type(first_item)}] after following a PageLink, has not been managed")
                    else:
                        image_url = safe_get_image_url(first_item) if first_item else None
                else:
                    msgproc.log(f"Category [{category.title}] type [{type(first_item)}] has not been managed")
            else:
                image_url = safe_get_image_url(first_item) if first_item else None
        if image_url:
            persistence.save_tile_image(TileType.CATEGORY, category.title, image_url)
            category_image_url = image_url
        else:
            msgproc.log(f"Could not get an image for category [{category.title}]")
    return category_image_url

def category_to_entry(
        objid, 
        category : TidalItemList) -> upmplgutils.direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.CATEGORY.getName(), 
        category.title)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, 
        objid, 
        category.title)
    # category image
    category_image_url : str = get_category_image_url(category)
    if category_image_url:
        upnp_util.set_album_art_from_uri(category_image_url, entry)
    else:
        msgproc.log(f"Category [{category.title}] type: [{type(category)}] tile image not set.")
    return entry

def get_option(options : dict[str, any], option_key : OptionKey) -> any:
    return options[option_key.get_name()] if option_key.get_name() in options else option_key.get_default_value()

def set_option(options : dict[str, any], option_key : OptionKey, option_value : any) -> None:
    options[option_key.get_name()] = option_value

def get_album_track_num(track : TidalTrack) -> str:
    if is_multidisc_album(track.album):
        return f"{track.volume_num}.{track.track_num:02}"
    else:
        return track.track_num

def track_apply_explicit(track : TidalTrack, current_title : str = None, options : dict[str, any] = {}) -> str:
    title : str = current_title if current_title else track.name
    if track.explicit:
        title : str = f"{title} [Explicit]"
    return title

def get_track_name_for_track_container(
        track: TidalTrack,
        options : dict[str, any] = {}) -> str:
    skip_track_artist : bool  = get_option(
        options = options, 
        option_key = OptionKey.SKIP_TRACK_ARTIST)
    title : str = track.name
    if not skip_track_artist:
        title : str = f"{track.artist.name} - {title}"
    skip_track_number : bool = get_option(
        options = options, 
        option_key = OptionKey.SKIP_TRACK_NUMBER)
    if not skip_track_number:
        forced_track_number : int = get_option(
            options = options, 
            option_key = OptionKey.FORCED_TRACK_NUMBER)
        track_number : str = f"{forced_track_number:02}" if forced_track_number else get_album_track_num(track)
        title : str = f"[{track_number}] {title}"
    title = track_apply_explicit(
        track = track,
        current_title = title,
        options = options)
    return title

# Possibly the same #1 occ #1
def track_to_navigable_mix_item(
        objid, 
        track: TidalTrack,
        options : dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid = objid,
        track = track,
        element_type = ElementType.MIX_NAVIGABLE_ITEM,
        options = options)

def track_to_navigable_playlist_item(
        objid, 
        track: TidalTrack,
        options : dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid = objid,
        track = track,
        element_type = ElementType.PLAYLIST_NAVIGABLE_ITEM,
        options = options)

def track_to_navigable_track(
        objid, 
        track: TidalTrack,
        options : dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid = objid,
        track = track,
        element_type = ElementType.NAVIGABLE_TRACK,
        options = options)

def track_to_navigable_track_by_element_type(
        objid, 
        track: TidalTrack,
        element_type : ElementType,
        options : dict[str, any] = {}) -> dict:
    identifier : ItemIdentifier = ItemIdentifier(
        element_type.getName(), 
        track.id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    overridden_track_name : str = get_option(
        options = options,
        option_key = OptionKey.OVERRIDDEN_TRACK_NAME)
    if overridden_track_name:
        title = overridden_track_name
    else:
        title = get_track_name_for_track_container(
            track = track, 
            options = options)
    track_entry = upmplgutils.direntry(id,
        objid,
        title)
    upnp_util.set_album_art_from_uri(get_image_url(track.album), track_entry)
    return track_entry

def track_to_track_container(
        objid, 
        track: TidalTrack,
        options : dict[str, any] = {}) -> dict:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.TRACK_CONTAINER.getName(), 
        track.id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    overridden_track_name : str = get_option(
        options = options,
        option_key = OptionKey.OVERRIDDEN_TRACK_NAME)
    if overridden_track_name:
        title = overridden_track_name
    else:
        title = get_track_name_for_track_container(
            track = track, 
            options = options)
    track_entry = upmplgutils.direntry(id,
        objid,
        title)
    upnp_util.set_album_art_from_uri(get_image_url(track.album), track_entry)
    return track_entry

def get_mime_type(track : TidalTrack) -> str:
    if is_mp3(track.audio_quality):
        return "audio/mp3"
    else:
        return "audio/flac"

def track_to_entry(
        objid, 
        track: TidalTrack,
        options : dict[str, any] = {}) -> dict:
    entry = {}
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), track.id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = track.id
    upnp_util.set_class_music_track(entry)
    song_uri : str = build_intermediate_url(track)
    entry['uri'] = song_uri
    title : str = track.name
    upnp_util.set_album_title(title, entry)
    entry['tp']= 'it'
    forced_track_number : int = get_option(
        options = options,
        option_key = OptionKey.FORCED_TRACK_NUMBER)
    track_num = (forced_track_number 
        if forced_track_number 
        else get_album_track_num(track))
    upnp_util.set_track_number(str(track_num), entry)
    upnp_util.set_artist(track.album.artist.name, entry)
    entry['upnp:album'] = track.album.name
    entry['res:mime'] = get_mime_type(track)
    skip_art : bool = get_option(
        options = options,
        option_key = OptionKey.SKIP_ART)
    if not skip_art:
        art_url : str = get_option(
            options = options,
            option_key = OptionKey.OVERRIDDEN_ART_URI)
        if not art_url: art_url = get_image_url(track.album)
        upnp_util.set_album_art_from_uri(art_url, entry)
    entry['duration'] = str(track.duration)
    return entry

def artist_to_entry(
        objid,
        artist : TidalArtist) -> upmplgutils.direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(), 
        artist.id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, 
        objid, 
        title = artist.name)
    upnp_util.set_class_artist(entry)
    upnp_util.set_album_art_from_uri(get_image_url(artist), entry)
    return entry

def album_to_album_container(
        objid,
        album : TidalAlbum) -> upmplgutils.direntry:
    options : dict[str, any] = dict()
    set_option(
        options = options,
        option_key = OptionKey.ENTRY_AS_CONTAINER,
        option_value = True)
    set_option(
        options = options,
        option_key = OptionKey.ADD_ARTIST_TO_ALBUM_ENTRY,
        option_value = True)
    return album_to_entry(
        objid = objid,
        album = album,
        options = options)

def album_to_entry(
        objid,
        album : TidalAlbum,
        options : dict[str, any] = {}) -> upmplgutils.direntry:
    as_container : bool = get_option(
        options = options,
        option_key = OptionKey.ENTRY_AS_CONTAINER)
    element_type : ElementType = (
        ElementType.ALBUM_CONTAINER if as_container 
        else ElementType.ALBUM)
    identifier : ItemIdentifier = ItemIdentifier(
        element_type.getName(), 
        album.id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    album_title : str = album.name
    add_artist : bool = get_option(
        options = options, 
        option_key = OptionKey.ADD_ARTIST_TO_ALBUM_ENTRY)
    if add_artist:
        album_title = f"{album.artist.name} - {album_title}"
    add_explicit : bool = get_option(
        options = options, 
        option_key = OptionKey.ADD_EXPLICIT)
    if add_explicit and album.explicit and not "explicit".lower() in album_title.lower():
        album_title = f"{album_title} [Explicit]"
    add_album_year : bool = get_option(
        options = options, 
        option_key = OptionKey.ADD_ALBUM_YEAR)
    if add_album_year and album.year:
        album_title = f"{album_title} [{album.year}]"
    entry = upmplgutils.direntry(id, 
        objid, 
        title = album_title,
        artist = album.artist.name)
    upnp_util.set_class_album(entry)
    upnp_util.set_album_art_from_uri(get_image_url(album), entry)
    return entry

def pagelink_to_entry(
        objid,
        category : TidalItemList,
        page_link : TidalPageLink,
        page_list : list[str] = list()) -> upmplgutils.direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.PAGELINK.getName(), 
        page_link.title)
    identifier.set(ItemIdentifierKey.CATEGORY_TITLE, category.title)
    identifier.set(ItemIdentifierKey.PAGE_LIST, page_list)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, 
        objid, 
        title = page_link.title)
    return entry

def page_to_entry(
        objid,
        api_path : str,
        page_title : str) -> upmplgutils.direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.PAGE.getName(), 
        api_path)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, 
        objid, 
        title = page_title)
    return entry

def playlist_to_playlist_container(
        objid,
        playlist : TidalPlaylist) -> upmplgutils.direntry:
    return raw_playlist_to_entry(
        objid = objid,
        playlist = playlist,
        element_type = ElementType.PLAYLIST_CONTAINER)

def playlist_to_entry(
        objid,
        playlist : TidalPlaylist) -> upmplgutils.direntry:
    return raw_playlist_to_entry(
        objid = objid,
        playlist = playlist,
        element_type = ElementType.PLAYLIST)

def raw_playlist_to_entry(
        objid,
        playlist : TidalPlaylist,
        element_type : ElementType = ElementType.PLAYLIST) -> upmplgutils.direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        element_type.getName(), 
        playlist.id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, 
        objid, 
        title = playlist.name)
    upnp_util.set_album_art_from_uri(get_image_url(playlist), entry)
    return entry

def mix_to_entry(
        objid,
        mix : TidalMix) -> upmplgutils.direntry:
    options : dict[str, any] = dict()
    set_option(
        options = options, 
        option_key = OptionKey.ENTRY_AS_CONTAINER, 
        option_value = False)
    return raw_mix_to_entry(
        objid = objid,
        mix = mix,
        options = options)

def mix_to_mix_container(
        objid,
        mix : TidalMix) -> upmplgutils.direntry:
    options : dict[str, any] = dict()
    set_option(
        options = options, 
        option_key = OptionKey.ENTRY_AS_CONTAINER, 
        option_value = True)
    return raw_mix_to_entry(
        objid = objid,
        mix = mix,
        options = options)

def raw_mix_to_entry(
        objid,
        mix : TidalMix,
        options : dict[str, any] = {}) -> upmplgutils.direntry:
    as_container : bool = get_option(
        options = options,
        option_key = OptionKey.ENTRY_AS_CONTAINER)
    element_type : ElementType = ElementType.MIX_CONTAINER if as_container else ElementType.MIX
    identifier : ItemIdentifier = ItemIdentifier(
        element_type.getName(), 
        mix.id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, 
        objid, 
        title = mix.title)
    upnp_util.set_album_art_from_uri(get_image_url(mix), entry)
    return entry

def get_categories() -> list[TidalItemList]:
    session : TidalSession = get_session()
    home = session.home()
    home.categories.extend(session.explore().categories)
    #home.categories.extend(session.videos().categories)
    return home.categories

def get_category(category_name : str):
    categories : list[TidalItemList] = get_categories()
    for current in categories:
        if current.title == category_name: return current
    
def handler_tag_favorite_albums(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    items : list[TidalAlbum] = get_session().user.favorites.albums(limit = max_items, offset = offset)
    current : TidalAlbum
    for current in items:
        entries.append(album_to_album_container(
            objid = objid, 
            album = current))
    if len(items) >= max_items:
        create_next_button(
            objid = objid, 
            element_type = ElementType.TAG, 
            element_id = TagType.FAVORITE_ALBUMS.getTagName(),
            next_offset = offset + max_items)
    return entries

def handler_tag_favorite_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    items : list[TidalArtist] = get_session().user.favorites.artists(limit = max_items, offset = offset)
    current : TidalArtist
    for current in items:
        entries.append(artist_to_entry(objid, artist = current))
    if len(items) >= max_items:
        create_next_button(
            objid = objid, 
            element_type = ElementType.TAG, 
            element_id = TagType.FAVORITE_ARTISTS.getTagName(),
            next_offset = offset + max_items)
    return entries

def handler_tag_favorite_tracks(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    tuple_array = [
        (ElementType.FAVORITE_TRACKS_NAVIGABLE, "My Tracks (Navigable)"), 
        (ElementType.FAVORITE_TRACKS_LIST, "My Tracks (list)")]
    for current_tuple in tuple_array:
        identifier : ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(), 
            current_tuple[1])
        id : str = identifier_util.create_objid(
            objid = objid, 
            id = identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, 
            objid, 
            current_tuple[1])
        entries.append(entry)
    return entries

def handler_tag_all_playlists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    playlists : list[TidalPlaylist] = get_session().user.playlist_and_favorite_playlists(offset = offset)
    current : TidalPlaylist
    for current in playlists:
        entries.append(playlist_to_playlist_container(
            objid = objid, 
            playlist = current))
    if len(playlists) >= max_items:
        create_next_button(
            objid = objid, 
            element_type = ElementType.TAG, 
            element_id = TagType.ALL_PLAYLISTS.getTagName(),
            next_offset = offset + max_items)
    return entries

def handler_tag_my_playlists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    playlists : list[TidalUserPlaylist] = get_session().user.playlists()
    current : TidalUserPlaylist
    for current in playlists:
        entries.append(playlist_to_playlist_container(
            objid = objid, 
            playlist = current))
    return entries

def handler_tag_playback_statistics(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    tuple_array = [
        (ElementType.RECENTLY_PLAYED_TRACKS_NAVIGABLE, "Recently played tracks"),
        (ElementType.RECENTLY_PLAYED_TRACKS_LIST, "Recently played tracks (List)"),
        (ElementType.MOST_PLAYED_TRACKS_NAVIGABLE, "Most played tracks"),
        (ElementType.MOST_PLAYED_TRACKS_LIST, "Most played tracks (List)")]
    for current_tuple in tuple_array:
        identifier : ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(), 
            current_tuple[1])
        id : str = identifier_util.create_objid(
            objid = objid, 
            id = identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, 
            objid, 
            current_tuple[1])
        entries.append(entry)
    return entries

def handler_tag_categories(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    current : TidalItemList
    category_index : int = 0
    for current in get_categories():
        msgproc.log(f"Found category[{category_index}]: [{current.title}] type is [{type(current)}]")
        title : str = current.title
        if title and len(title) > 0:
            entry = category_to_entry(objid, current)
            entries.append(entry)
        else:
            msgproc.log(f"  category at index [{category_index}] has no title, skipped.")
        category_index += 1
    return entries

def create_next_button(
        objid,
        element_type : ElementType,
        element_id : any,
        next_offset : int) -> dict:
    next_identifier : ItemIdentifier = ItemIdentifier(element_type.getName(), element_id)
    next_identifier.set(ItemIdentifierKey.OFFSET, next_offset)
    next_id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(next_identifier))
    next_entry : dict = upmplgutils.direntry(
        next_id, 
        objid, 
        title = "Next")
    return next_entry

def handler_element_mix(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    mix_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    mix : TidalMix = get_session().mix(mix_id)
    tracks : list[TidalTrack] = mix.items()
    track_number : int = 1
    for track in tracks:
        options : dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry = track_to_entry(
            objid, 
            track = track, 
            options = options)
        track_number += 1
        entries.append(track_entry)
    return entries

def get_genres() -> list[TidalGenre]:
    return get_session().genre.get_genres()

def get_genre(genre_name : str) -> TidalGenre:
    genres_list : list[TidalGenre] = get_session().genre.get_genres()
    selected : TidalGenre
    for selected in genres_list:
        msgproc.log(f"get_genre inspecting [{selected.name}] path [{selected.path}]")
        if selected.name in genre_name:
            return selected

def navigate(category_name : str, page_list : list[str] = list()):
    category : TidalItemList = get_category(category_name = category_name)
    if not category: return None
    result = category
    current_page : str
    for current_page in page_list:
        msgproc.log(f"navigate searching {current_page}")
        if not result: return None
        current_item : TidalPageLink
        for current_item in result.items:
            msgproc.log(f"navigate searching {current_page} current_item {current_item.title}, looking for {current_page}")
            if current_page == current_item.title:
                result = current_item
                break            
    return result

def follow_page_link(page_link : TidalPageLink) -> any:
    next = page_link
    while next:
        msgproc.log(f"follow_page_link: type of next is [{type(next)}]")
        if isinstance(next, TidalPageLink):
            next = next.get()
            msgproc.log(f"  next found: [{'yes' if next else 'no'}] type: [{type(next) if next else None}]")
        else:
            break
    return next

def get_first_item_in_page_link(page_link : TidalPageLink) -> any:
    item = None
    current_link : TidalPageLink = page_link
    while not item:
        next_thing = follow_page_link(current_link)
        if isinstance(next_thing, TidalPage):
            # see if there is a link, if so, follow
            msgproc.log(f"get_first_item_in_page_link: found a Page")
            first_page_item = next(iter(next_thing))
            msgproc.log(f"get_first_item_in_page_link: first_item found: [{'yes' if first_page_item else 'no'}], type: [{type(first_page_item) if first_page_item else None}]")
            if not first_page_item: raise Exception("get_first_item_in_page_link failed")
            if isinstance(first_page_item, TidalPageLink):
                current_link = first_page_item
            else:
                item = first_page_item
        else:
            item = next_thing
    return item

def handler_element_pagelink(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    thing_name : str = item_identifier.get(ItemIdentifierKey.THING_NAME)
    thing_value : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    category_title : str = item_identifier.get(ItemIdentifierKey.CATEGORY_TITLE)
    page_list : list[str] = item_identifier.get(ItemIdentifierKey.PAGE_LIST, list())
    msgproc.log(f"handler_element_pagelink name: {thing_name} value: {thing_value} category_title {category_title} page_list {page_list}")
    full_page_list : list[str] = copy.deepcopy(page_list)
    full_page_list.append(thing_value)
    selected_pagelink = navigate(category_title, full_page_list)
    if not selected_pagelink: return entries
    msgproc.log(f"handler_element_pagelink found pagelink [{selected_pagelink.title}] type {type(selected_pagelink)}")
    # get items from pagelink
    page : TidalPage = selected_pagelink.get()
    if not page: 
        msgproc.log(f"handler_element_pagelink page not found")
        return entries
    if page: page_to_entries(objid, page, entries)
    return entries

def handler_element_page(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    thing_value : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    page : TidalPage = session.page.get(thing_value)
    for page_item in page:
        if isinstance(page_item, TidalPlaylist):
            entries.append(playlist_to_playlist_container(
                objid = objid, 
                playlist = page_item))
        elif isinstance(page_item, TidalAlbum):
            entries.append(album_to_album_container(
                objid = objid,
                album = page_item))
        else:
            msgproc.log(f"handler_element_page: page_item of type [{type(page_item)}] not handled")
    return entries

def page_to_entries(objid, page : TidalPage, entries : list) -> list:
    # extracting items from page
    for current_page_item in page:
        entries = convert_page_item_to_entries(
            objid = objid, 
            page_item = current_page_item, 
            entries = entries)
    return entries

def convert_page_item_to_entries(objid, page_item : TidalPageItem, entries : list) -> list:
    if isinstance(page_item, TidalPlaylist):
        entries.append(playlist_to_playlist_container(
            objid = objid, 
            playlist = page_item))
    elif isinstance(page_item, TidalAlbum):
        entries.append(album_to_album_container(
            objid = objid, 
            album = page_item))
    elif isinstance(page_item, TidalArtist):
        entries.append(artist_to_entry(objid, artist = page_item))
    elif isinstance(page_item, TidalPageLink):
        page_link : TidalPageLink = page_item
        entries.append(page_to_entry(
            objid = objid,
            api_path = page_link.api_path,
            page_title = page_link.title))
    else:
        msgproc.log(f"convert_page_item_to_entries item of type {type(page_item) if page_item else None} not handled")
    return entries

def handler_element_mix_container(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    mix_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    mix : TidalPlaylist = get_session().mix(mix_id)
    pl_tuple_array = [
        (ElementType.MIX_NAVIGABLE, "Navigable"), 
        (ElementType.MIX, "Mix Items")]
    for current_tuple in pl_tuple_array:
        identifier : ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(), 
            mix_id)
        id : str = identifier_util.create_objid(
            objid = objid, 
            id = identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, 
            objid, 
            current_tuple[1])
        upnp_util.set_album_art_from_uri(get_image_url(mix), entry)
        entries.append(entry)
    return entries

def handler_element_album_container(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album : TidalAlbum = get_session().album(album_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM.getName(), 
        album_id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, 
        objid, 
        "Album")
    upnp_util.set_album_art_from_uri(get_image_url(album), entry)
    entries.append(entry)
    # add Artists
    artist_list : list[TidalArtist] = get_artist_list(album.artist, album.artists)
    for current in artist_list:
        artist : TidalArtist = get_session().artist(current.id)
        entries.append(artist_to_entry(objid = objid, artist = artist))
    return entries

def handler_element_playlist_container(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    playlist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    playlist : TidalPlaylist = get_session().playlist(playlist_id)
    pl_tuple_array = [
        (ElementType.PLAYLIST_NAVIGABLE, "Navigable"), 
        (ElementType.PLAYLIST, "Tracks")]
    for current_tuple in pl_tuple_array:
        identifier : ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(), 
            playlist_id)
        id : str = identifier_util.create_objid(
            objid = objid, 
            id = identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, 
            objid, 
            current_tuple[1])
        upnp_util.set_album_art_from_uri(get_image_url(playlist), entry)
        entries.append(entry)
    return entries

def get_artist_list(
        artist : TidalArtist, 
        artists : list[TidalArtist]) -> list[TidalArtist]:
    result : list[TidalArtist] = list()
    artist_id_set : set[str] = set()
    result.append(artist)
    artist_id_set.add(artist.id)
    for other in artists if artists else list():
        if other.id in artist_id_set: break
        result.append(other)
        artist_id_set.add(other.id)
    return result

def handler_element_mix_navigable_item(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    return handler_element_mix_playlist_toptrack_navigable_item(
        objid = objid, 
        item_identifier = item_identifier,
        entries = entries)

def handler_element_navigable_track(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    return handler_element_mix_playlist_toptrack_navigable_item(
        objid = objid, 
        item_identifier = item_identifier,
        entries = entries)

def handler_element_playlist_navigable_item(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    return handler_element_mix_playlist_toptrack_navigable_item(
        objid = objid, 
        item_identifier = item_identifier,
        entries = entries)

def handler_element_mix_playlist_toptrack_navigable_item(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    track_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    track : TidalTrack = get_session().track(track_id)
    track_options : dict[str, any] = dict()
    set_option(
        options = track_options,
        option_key = OptionKey.OVERRIDDEN_TRACK_NAME, 
        option_value = "Track")
    entries.append(track_to_track_container(
        objid = objid, 
        track = track,
        options = track_options))
    # add link to artists
    artist_list : list[TidalArtist] = get_artist_list(track.artist, track.artists)
    for current in artist_list:
        artist : TidalArtist = get_session().artist(current.id)
        entries.append(artist_to_entry(
            objid = objid, 
            artist = artist))
    # add link to album
    if track.album and track.album.id:
        album : TidalAlbum = get_session().album(track.album.id)
        entries.append(album_to_entry(
            objid = objid, 
            album = album))
    return entries

def handler_element_mix_navigable(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    mix_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    mix : TidalMix = get_session().mix(mix_id)
    tracks : list[TidalTrack] = mix.items()
    max_items_per_page : int = 100
    remaining_tracks = tracks[offset:]
    tracks = remaining_tracks[0:max_items_per_page]
    track_number : int = offset + 1
    for track in tracks:
        options : dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry = track_to_navigable_mix_item(
            objid, 
            track = track, 
            options = options)
        track_number += 1
        entries.append(track_entry)
    if (len(remaining_tracks) > max_items_per_page):
        next_entry : dict[str, any] = create_next_button(
            objid = objid,
            element_type = ElementType.MIX_NAVIGABLE,
            element_id = mix_id,
            next_offset = offset + max_items_per_page)
        entries.append(next_entry)
    return entries

def handler_element_playlist_navigable(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    playlist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    playlist : TidalPlaylist = get_session().playlist(playlist_id)
    tracks : list[TidalTrack] = playlist.tracks()
    max_items_per_page : int = 100
    remaining_tracks = tracks[offset:]
    tracks = remaining_tracks[0:max_items_per_page]
    track_number : int = offset + 1
    for track in tracks:
        options : dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry = track_to_navigable_playlist_item(
            objid, 
            track = track, 
            options = options)
        track_number += 1
        entries.append(track_entry)
    if (len(remaining_tracks) > max_items_per_page):
        next_entry : dict[str, any] = create_next_button(
            objid = objid,
            element_type = ElementType.PLAYLIST_NAVIGABLE,
            element_id = playlist_id,
            next_offset = offset + max_items_per_page)
        entries.append(next_entry)
    return entries

def handler_element_playlist(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    return playlist_to_entries(
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)

def playlist_to_entries(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    playlist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    playlist : TidalPlaylist = get_session().playlist(playlist_id)
    tracks : list[TidalTrack] = playlist.tracks()
    track_number : int = offset + 1
    for track in tracks:
        options : dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry = track_to_entry(
            objid, 
            track = track, 
            options = options)
        track_number += 1
        entries.append(track_entry)
    return entries

def is_multidisc_album(album : TidalAlbum) -> bool:
    return album.num_volumes and album.num_volumes > 1

def handler_element_album(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    album_id : int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album : TidalAlbum = get_session().album(album_id)
    is_multidisc : bool = is_multidisc_album(album)
    msgproc.log(f"Album {album_id} is multidisc {is_multidisc}")
    tracks : list[TidalTrack] = album.tracks()
    options : dict[str, any] = {}
    set_option(options, OptionKey.SKIP_TRACK_ARTIST, True)
    track_num : int = 1 
    track : TidalTrack
    for track in tracks:
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_num)
        track_entry = track_to_entry(
            objid = objid, 
            track = track,
            options = options)
        entries.append(track_entry)
        track_num += 1
    return entries

def handler_element_artist_album_catch_all(
        objid, 
        item_identifier : ItemIdentifier, 
        album_extractor : Callable[[], list[TidalAlbum]], 
        entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    if not artist: msgproc.log(f"Artist with id {artist_id} not found")
    current : TidalAlbum
    for current in album_extractor(artist):
        entries.append(album_to_entry(objid, current))
    return entries

def handler_element_artist_album_albums(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_element_artist_album_catch_all(
        objid,
        item_identifier = item_identifier,
        album_extractor = lambda x : x.get_albums(),
        entries = entries)

def handler_element_artist_album_ep_singles(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_element_artist_album_catch_all(
        objid,
        item_identifier = item_identifier,
        album_extractor = lambda x : x.get_albums_ep_singles(),
        entries = entries)

def handler_element_artist_album_others(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_element_artist_album_catch_all(
        objid,
        item_identifier = item_identifier,
        album_extractor = lambda x : x.get_albums_other(),
        entries = entries)

def get_similar_artists(artist : TidalArtist) -> list[TidalArtist]:
    try:
        return artist.get_similar()
    except Exception as ex:
        msgproc.log(f"Cannot get similar artists for artist id [{artist.id}] name [{artist.name}] Exception [{ex}]")
    return list()

def get_top_tracks(artist : TidalArtist) -> list[TidalTrack]:
    try:
        return artist.get_top_tracks()
    except Exception as ex:
        msgproc.log(f"Cannot get top tracks for artist id [{artist.id}] name [{artist.name}] Exception [{ex}]")
    return list()

def get_radio(artist : TidalArtist) -> list[TidalTrack]:
    try:
        return artist.get_radio()
    except Exception as ex:
        msgproc.log(f"Cannot get radio for artist id [{artist.id}] name [{artist.name}] Exception [{ex}]")
    return list()

def handler_element_similar_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    items : list[TidalArtist] = get_similar_artists(artist)
    current : TidalArtist
    for current in items if items else list():
        entries.append(artist_to_entry(objid = objid, artist = current))
    return entries

def add_tracks_to_entries(objid, items : list[TidalTrack], entries : list) -> list:
    current : TidalTrack
    for current in items if items else list():
        options : dict[str, any] = dict()
        set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
        entries.append(track_to_navigable_track(
            objid = objid, 
            track = current,
            options = options))
    return entries

def add_track_as_list_to_entries(objid, items : list[TidalTrack], entries : list) -> list:
    current : TidalTrack
    for current in items if items else list():
        options : dict[str, any] = dict()
        set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
        entries.append(track_to_entry(
            objid = objid, 
            track = current,
            options = options))
    return entries

def handler_element_favorite_tracks_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    items : list[TidalTrack] = get_session().user.favorites.tracks()
    return add_tracks_to_entries(objid, items, entries)

def handler_element_favorite_tracks_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    items : list[TidalTrack] = get_session().user.favorites.tracks()
    return add_track_as_list_to_entries(objid, items, entries)    

def handler_element_artist_top_tracks_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    items : list[TidalTrack] = get_top_tracks(artist)
    return add_tracks_to_entries(objid, items, entries)

def handler_element_artist_top_tracks_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    items : list[TidalTrack] = get_top_tracks(artist)
    current : TidalTrack
    for current in items if items else list():
        options : dict[str, any] = dict()
        set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
        entries.append(track_to_entry(
            objid = objid, 
            track = current,
            options = options))
    return entries

def handler_element_artist_radio_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    items : list[TidalTrack] = get_radio(artist)
    return add_track_as_list_to_entries(objid, items, entries)

def handler_element_artist_radio_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    items : list[TidalTrack] = get_radio(artist)
    return add_tracks_to_entries(objid, items, entries)

def handler_element_artist(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    if not artist: msgproc.log(f"Artist with id {artist_id} not found")
    album_tuple_array = [
        (ElementType.ARTIST_ALBUM_ALBUMS, "Albums"), 
        (ElementType.ARTIST_ALBUM_EP_SINGLES, "EP and Singles"),
        (ElementType.ARTIST_ALBUM_OTHERS, "Other Albums"),
        (ElementType.SIMILAR_ARTISTS, "Similar Artists"),
        (ElementType.ARTIST_TOP_TRACKS_NAVIGABLE, "Top Tracks"),
        (ElementType.ARTIST_TOP_TRACKS_LIST, "Top Tracks (List)"),
        (ElementType.ARTIST_RADIO_NAVIGABLE, "Radio"),
        (ElementType.ARTIST_RADIO_LIST, "Radio (List)")]
    for album_tuple in album_tuple_array:
        identifier : ItemIdentifier = ItemIdentifier(
            album_tuple[0].getName(), 
            artist_id)
        id : str = identifier_util.create_objid(
            objid = objid, 
            id = identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, 
            objid, 
            album_tuple[1])
        upnp_util.set_album_art_from_uri(get_image_url(artist), entry)
        entries.append(entry)
    return entries

def handler_element_track_container(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    track_id : int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    track : TidalTrack = get_session().track(track_id)
    track_entry = track_to_entry(
        objid = objid, 
        track = track)
    entries.append(track_entry)
    return entries

def get_category_items(category_name : str) -> list[any]:
    category : TidalItemList = get_category(category_name)
    item_list : list[any] = list()
    if category:
        for item in category.items:
            item_list.append(item)
    return item_list

def handler_element_category(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    select_category : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    category : TidalItemList = get_category(select_category)
    if not category: 
        msgproc.log(f"handler_element_category category not set")
        return entries
    obj = get_category(select_category)
    if not obj: 
        msgproc.log(f"handler_element_category cannot load category [{select_category}]")
        return entries
    if isinstance(obj, TidalFeaturedItems):
        msgproc.log(f"handler_element_category category [{select_category}] as TidalFeaturedItems")
        featured_items : TidalFeaturedItems = obj
        for fi_item in featured_items.items:
            msgproc.log(f"handler_element_category Processing category {select_category} as {type(obj)} Item type {fi_item.type}")
            if fi_item.type == constants.featured_type_name_playlist:
                playlist : TidalPlaylist = get_session().playlist(fi_item.artifact_id)
                entries.append(playlist_to_playlist_container(
                    objid = objid, 
                    playlist = playlist))
            else:
                msgproc.log(f"handler_element_category not processed Item type {fi_item.type}")
    else:
        index : int = 0
        for item in category.items:
            msgproc.log(f"handler_element_category categories[{select_category}].item[{index}] type is [{type(item)}]")
            if isinstance(item, TidalPageItem):
                msgproc.log(f"handler_element_category PageItem (Category {category.title}) Item type {type(item)} [{item}] not handled")
            elif isinstance(item, TidalPageLink):
                msgproc.log(f"handler_element_category PageLink (Category {category.title}) Item type {type(item)} [{item}]")
                entries.append(pagelink_to_entry(objid, category = category, page_link = item))
            elif isinstance(item, TidalMix):
                msgproc.log(f"handler_element_category Mix - Item type {type(item)} [{item}]")
                entries.append(mix_to_mix_container(objid, mix = item))
            elif isinstance(item, TidalTrack):
                msgproc.log(f"handler_element_category Track - Item type {type(item)} [{item}]")
                options : dict[str, any] = dict()
                set_option(options, OptionKey.SKIP_TRACK_NUMBER, True)
                entries.append(track_to_track_container(
                    objid = objid, 
                    track = item,
                    options = options))
            elif isinstance(item, TidalPlaylist):
                msgproc.log(f"handler_element_category Playlist - Item type {type(item)} [{item}]")
                entries.append(playlist_to_playlist_container(
                    objid = objid, 
                    playlist = item))
            elif isinstance(item, TidalAlbum):
                album : TidalAlbum = item
                msgproc.log(f"handler_element_category Album [{album.name}] [{item}]")
                options : dict[str, any] = dict()
                entries.append(album_to_album_container(objid, album = album))
            else:
                msgproc.log(f"handler_element_category UNHANDLED - Item type {type(item)} [{item}]")
        index += 1
    return entries

# this allows kodi to work with the plugin
def track_data_to_entry(objid, entry_id : str, track : TidalTrack) -> dict:
    entry : dict = {}
    entry['id'] = entry_id
    entry['pid'] = track.id
    upnp_util.set_class_music_track(entry)
    entry['uri'] = build_intermediate_url(track)
    title : str = track.name
    upnp_util.set_album_title(title, entry)
    entry['tp']= 'it'
    entry['discnumber'] = track.volume_num
    upnp_util.set_track_number(track.track_num, entry)
    upnp_util.set_artist(track.artist.name, entry)
    entry['upnp:album'] = track.album.name
    entry['res:mime'] = get_mime_type(track)
    upnp_util.set_album_art_from_uri(get_image_url(track.album), entry)
    entry['duration'] = str(track.duration)
    return entry

def handler_element_track_simple(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    track_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    track : TidalTrack = get_session().track(track_id)
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), track_id)
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    track_entry : dict = track_data_to_entry(objid, id, track)
    entries.append(track_entry)
    return entries

def handler_element_recently_played_tracks_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return played_track_list_to_entries(objid, persistence.get_last_played_tracks(), entries)

def handler_element_most_played_tracks_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return played_track_list_to_entries(objid, persistence.get_most_played_tracks(), entries)

def played_track_list_to_entries(objid, played_tracks : list[PlayedTrack], entries : list) -> list:
    current : PlayedTrack
    options : dict[str, any] = dict()
    set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
    for current in played_tracks if played_tracks else list():
        track : TidalTrack = get_session().track(current.track_id)
        track_entry : dict = track_to_navigable_track(
            objid = objid, 
            track = track,
            options = options)
        entries.append(track_entry)
    return entries

def handler_element_recently_played_tracks_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return played_track_list_to_list_entries(objid, persistence.get_last_played_tracks(), entries)

def handler_element_most_played_tracks_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return played_track_list_to_list_entries(objid, persistence.get_most_played_tracks(), entries)

def played_track_list_to_list_entries(objid, played_tracks : list[PlayedTrack], entries : list) -> list:
    current : PlayedTrack
    track_number : int = 1
    for current in played_tracks if played_tracks else list():
        track : TidalTrack = get_session().track(current.track_id)
        options : dict[str, any] = dict()
        set_option(
            options = options, 
            option_key = OptionKey.FORCED_TRACK_NUMBER, 
            option_value = track_number)
        track_entry : dict = track_to_entry(
            objid = objid, 
            track = track,
            options = options)
        track_number += 1
        entries.append(track_entry)
    return entries

def image_retriever_categories(tag_type : TagType) -> str:
    categories = get_categories()
    first_category = categories[0] if categories and len(categories) > 0 else None
    return get_category_image_url(first_category) if first_category else None

__tag_image_retriever : dict = {
    TagType.CATEGORIES.getTagName(): image_retriever_categories
}
    
__tag_action_dict : dict = {
    TagType.CATEGORIES.getTagName(): handler_tag_categories,
    TagType.MY_PLAYLISTS.getTagName(): handler_tag_my_playlists,
    TagType.ALL_PLAYLISTS.getTagName(): handler_tag_all_playlists,
    TagType.FAVORITE_ALBUMS.getTagName(): handler_tag_favorite_albums,
    TagType.FAVORITE_ARTISTS.getTagName(): handler_tag_favorite_artists,
    TagType.FAVORITE_TRACKS.getTagName(): handler_tag_favorite_tracks,
    TagType.PLAYBACK_STATISTICS.getTagName(): handler_tag_playback_statistics
}
    
__elem_action_dict : dict = {
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
    ElementType.PAGELINK.getName(): handler_element_pagelink,
    ElementType.PAGE.getName(): handler_element_page,
    ElementType.ARTIST.getName(): handler_element_artist,
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
    ElementType.MOST_PLAYED_TRACKS_LIST.getName(): handler_element_most_played_tracks_list
}

def tag_list_to_entries(objid, tag_list : list[TagType]) -> list[dict[str, any]]:
    entry_list : list[dict[str, any]] = list()
    tag : TagType
    for tag in tag_list:
        entry : dict[str, any] = tag_to_entry(objid, tag)
        entry_list.append(entry)
    return entry_list

def tag_to_entry(objid, tag : TagType) -> dict[str, any]:
    tagname : str = tag.getTagName()
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TAG.getName(), tagname)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry : dict = upmplgutils.direntry(
        id = id, 
        pid = objid, 
        title = get_tag_Type_by_name(tag.getTagName()).getTagTitle())
    return entry

def show_tags(objid, entries : list) -> list:
    for tag in TagType:
        curr_tag_img_retriever = __tag_image_retriever[tag.getTagName()] if tag.getTagName() in __tag_image_retriever else None
        curr_tag_img : str = curr_tag_img_retriever(tag) if curr_tag_img_retriever else None
        tag_entry : dict[str, any] = tag_to_entry(objid, tag)
        if curr_tag_img and len(curr_tag_img) > 0: upnp_util.set_album_art_from_uri(curr_tag_img, tag_entry)
        entries.append(tag_entry)
    return entries

@dispatcher.record('browse')
def browse(a):
    msgproc.log(f"browse: args: --{a}--")
    _inittidal()
    if 'objid' not in a: raise Exception("No objid in args")
    objid = a['objid']
    path = html.unescape(_objidtopath(objid))
    msgproc.log(f"browse: path: --{path}--")
    path_list : list[str] = objid.split("/")
    curr_path : str
    for curr_path in path_list:
        if not _g_myprefix == curr_path:
            msgproc.log(f"browse: current_path [{curr_path}] decodes to [{codec.decode(curr_path)}]")
    last_path_item : str = path_list[len(path_list) - 1] if path_list and len(path_list) > 0 else None
    msgproc.log(f"browse: path_list: --{path_list}-- last: --{last_path_item}--")
    entries = []
    if len(path_list) == 1 and _g_myprefix == last_path_item:
        # show tags
        entries = show_tags(objid, entries)
    else:
        # decode
        decoded_path : str = codec.decode(last_path_item)
        item_dict : dict[str, any] = json.loads(decoded_path)
        item_identifier : ItemIdentifier = ItemIdentifier.from_dict(item_dict)
        thing_name : str = item_identifier.get(ItemIdentifierKey.THING_NAME)
        thing_value : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
        msgproc.log(f"browse: item_identifier name: --{thing_name}-- value: --{thing_value}--")
        if ElementType.TAG.getName() == thing_name:
            tag_handler = __tag_action_dict[thing_value] if thing_value in __tag_action_dict else None
            msgproc.log(f"browse: should serve tag [{thing_value}], handler found: [{'yes' if tag_handler else 'no'}]")
            if tag_handler:
                entries = tag_handler(objid, item_identifier, entries)
                return _returnentries(entries)
        else: # it's an element
            elem_handler = __elem_action_dict[thing_name] if thing_name in __elem_action_dict else None
            msgproc.log(f"browse: should serve element [{thing_name}], handler found: [{'yes' if elem_handler else 'no'}]")
            if elem_handler:
                entries = elem_handler(objid, item_identifier, entries)
    return _returnentries(entries)

def tidal_search(
        search_type : SearchType,
        value : str,
        limit : int = 50, 
        offset : int = 0) -> list:
    search_result : dict = get_session().search(
        query = value,
        models = [search_type.get_model()])
    item_list : list = search_result[search_type.get_dict_entry()]
    return item_list

@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    _inittidal()
    objid = a["objid"]
    entries = []

    # Run the search and build a list of entries in the expected format. See for example
    # ../radio-browser/radiotoentry for an example
    value : str = a["value"]
    field : str = a["field"]
    objkind : str = a["objkind"] if "objkind" in a else None
    if not objkind or len(objkind) == 0: objkind = field
    
    msgproc.log(f"Searching for [{value}] as [{field}] objkind [{objkind}]...")
    resultset_length : int = 0

    if SearchType.ALBUM.get_name() == objkind:
        # search albums by specified value
        item_list : list[TidalAlbum] = tidal_search(SearchType.ALBUM, value)
        resultset_length = len(item_list) if item_list else 0
        for item in item_list:
            entries.append(album_to_album_container(
                objid = objid, 
                album = item))
    elif SearchType.TRACK.get_name() == objkind:
        # search tracks by specified value
        item_list : list[TidalTrack] = tidal_search(SearchType.TRACK, value)
        resultset_length = len(item_list) if item_list else 0
        options : dict[str, any] = dict()
        set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
        for item in item_list:
            entries.append(track_to_entry(
                objid = objid, 
                track = item, 
                options = options))
    elif SearchType.ARTIST.get_name() == objkind:
        # search artists by specified value
        item_list : list[TidalArtist] = tidal_search(SearchType.ARTIST, value)
        resultset_length = len(item_list) if item_list else 0
        for item in item_list:
            entries.append(artist_to_entry(
                objid = objid, 
                artist = item))
    msgproc.log(f"Search for [{value}] as [{field}] returned [{resultset_length}] entries")
    return _returnentries(entries)

# Possible once initialisation. Always called by browse() or search(), should remember if it has
# something to do (e.g. the _g_init thing, but this could be something else).
_g_init = False
def _inittidal():
    global _g_init
    if _g_init:
        return True

    # Do whatever is needed here
    msgproc.log(f"Tidal Plugin Release {__tidal_plugin_release}")

    cache_dir : str = upmplgutils.getcachedir("tidal")
    msgproc.log(f"Cache dir for [{plugin_name}] is [{cache_dir}]")
    msgproc.log(f"DB version for [{plugin_name}] is [{persistence.get_db_version()}]")

    _g_init = create_session()

    return True

msgproc.mainloop()
