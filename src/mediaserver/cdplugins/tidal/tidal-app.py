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

__tidal_plugin_release : str = "0.0.9"

import json
import copy
import os

import datetime
import secrets
from typing import Callable
from typing import Optional

import cmdtalkplugin
import upmplgutils
import html
import xbmcplug

import codec
import identifier_util
import upnp_util
import constants
import persistence
import tidal_util

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

from track_adapter import TrackAdapter
from tidal_track_adapter import TidalTrackAdapter
from played_track_adapter import PlayedTrackAdapter

from played_track import PlayedTrack
from played_album import PlayedAlbum
from played_track_request import PlayedTrackRequest
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

log_intermediate_url : bool = upmplgutils.getOptionValue(f"{plugin_name}log_intermediate_url", "0") == "1"

def album_retriever(album_id : str) -> TidalAlbum:
    return get_session().album(album_id)

def instance_tidal_track_adapter(track : TidalTrack) -> TidalTrackAdapter:
    return TidalTrackAdapter(
        track = track, 
        album_retriever = album_retriever)

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

def safe_get_image_url(obj : any) -> str:
    if has_image_method(obj): return tidal_util.get_image_url(obj)

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
    return tidal_util.is_mp3(q)

def __get_credentials_file_name() -> str:
    return os.path.join(upmplgutils.getcachedir(constants.plugin_name), constants.credentials_file_name)

def get_credentials_from_config() -> dict[str, str]:
    # static first
    token_type : str = upmplgutils.getOptionValue(f"{plugin_name}tokentype")
    access_token : str = upmplgutils.getOptionValue(f"{plugin_name}accesstoken")
    refresh_token : str = upmplgutils.getOptionValue(f"{plugin_name}refreshtoken")
    expiry_time_timestamp_str : str = upmplgutils.getOptionValue(f"{plugin_name}expirytime")
    if token_type and access_token and refresh_token and expiry_time_timestamp_str:
        msgproc.log(f"Credentials provided statically")
        res_dict : dict[str, any] = dict()
        res_dict[constants.key_token_type] = token_type
        res_dict[constants.key_access_token] = access_token
        res_dict[constants.key_refresh_token] = refresh_token
        res_dict[constants.key_expiry_time_timestamp_str] = expiry_time_timestamp_str
        return res_dict
    else:
        msgproc.log(f"Credentials not provided statically, looking for credentials file ...")
        # try json file
        cred_file_name : str = __get_credentials_file_name()
        if not os.path.exists(cred_file_name): return dict()
        msgproc.log(f"Credentials file found!")
        #read contents
        try:
            with open(cred_file_name, 'r') as cred_file:
                return json.load(cred_file)
        except Exception as ex:
            msgproc.log(f"Error loading configuration: [{ex}]")  
    return dict()

def get_cred_value(from_dict : dict[str, str], key_name : str) -> str:
    return from_dict[key_name] if from_dict and key_name in from_dict else None

def create_session():
    global session
    res : bool = False
    token_type : str = None
    access_token : str = None
    refresh_token : str = None
    expiry_time_timestamp_str : str = None
    if not session:
        res : bool = None
        new_session : TidalSession = TidalSession()
        # read from config
        credentials_dict : dict[str, str] = get_credentials_from_config()
        token_type = get_cred_value(credentials_dict, constants.key_token_type)
        access_token = get_cred_value(credentials_dict, constants.key_access_token)
        refresh_token = get_cred_value(credentials_dict, constants.key_refresh_token)
        expiry_time_timestamp_str = get_cred_value(credentials_dict, constants.key_expiry_time_timestamp_str)
        expiry_time_timestamp : float = float(expiry_time_timestamp_str) if expiry_time_timestamp_str else None
        expiry_time : datetime.datetime = (datetime.datetime.fromtimestamp(expiry_time_timestamp) 
                                           if expiry_time_timestamp 
                                           else None)
        # do we have a static configuration?
        if token_type and access_token and refresh_token and expiry_time:
            res = new_session.load_oauth_session(token_type, access_token, refresh_token, expiry_time)
        else: # provide link for authorization
            # show challenge url
            new_session.login_oauth_simple(function = msgproc.log)
            token_type = new_session.token_type
            access_token = new_session.access_token
            refresh_token = new_session.refresh_token
            expiry_time = new_session.expiry_time
            storable_expiry_time = datetime.datetime.timestamp(expiry_time)
            # try create session
            res = new_session.load_oauth_session(token_type, access_token, refresh_token, expiry_time)
            if res:
                # success, store credentials
                new_credentials : dict[str, str] = {
                    "token_type" : token_type,
                    "access_token" : access_token,
                    "refresh_token" : refresh_token,
                    "expiry_time_timestamp_str" : storable_expiry_time
                }
                with open(__get_credentials_file_name(), 'w') as wcf:
                    json.dump(new_credentials, wcf, indent = 4)
            else:
                msgproc.log(f"Tidal session NOT created")
        msgproc.log(f"Tidal session created: [{'yes' if res else 'no'}]")
        if res: 
            audio_quality : TidalQuality = get_audio_quality(upmplgutils.getOptionValue(f"{plugin_name}audioquality"))
            new_session.audio_quality = audio_quality
            session = new_session
    else: 
        res = True
    return res

def get_session() -> TidalSession:
    global session
    if not create_session():
        msgproc.log("Cannot create Tidal session")
    else:
        return session

def build_intermediate_url(track_id : str) -> str:
    http_host_port = os.environ["UPMPD_HTTPHOSTPORT"]
    url = f"http://{http_host_port}/{plugin_name}/track/version/1/trackId/{track_id}"
    if log_intermediate_url: msgproc.log(f"intermediate_url for track_id {track_id} -> [{url}]")
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
    media_url = build_streaming_url(track_id) or ""
    res : dict[str, any] = {} 
    res['media_url'] = media_url
    if media_url:
        track : TidalTrack = get_session().track(track_id)
        if track:
            played_track_request : PlayedTrackRequest = PlayedTrackRequest()
            played_track_request.track_id = track_id
            played_track_request.track_name = track.name
            played_track_request.track_duration = track.duration
            played_track_request.track_num = track.track_num
            played_track_request.volume_num = track.volume_num
            played_track_request.audio_quality = track.audio_quality.value
            played_track_request.explicit = track.explicit
            played_track_request.album_id = track.album.id
            played_track_request.artist_name = track.artist.name
            album : TidalAlbum = get_session().album(played_track_request.album_id)
            if album:
                played_track_request.album_track_count = album.num_tracks
                played_track_request.album_num_volumes = album.num_volumes
                played_track_request.album_duration = album.duration
                played_track_request.album_name = album.name
                played_track_request.album_artist_name = album.artist.name
                played_track_request.image_url = tidal_util.get_image_url(album)
                persistence.track_playback(played_track_request)
            res["mimetype"] = "audio/mpeg" if tidal_util.is_mp3(track.audio_quality) else "audio/flac"
            if tidal_util.is_mp3(track.audio_quality):
                res["kbs"] = "320" if TidalQuality.low_320k == track.audio_quality else "96"
            elif TidalQuality.high_lossless == track.audio_quality:
                res["kbs"] = "1411"
    return res

def _returnentries(entries):
    """Helper function: build plugin browse or search return value from items list"""
    return {"entries" : json.dumps(entries), "nocache" : "0"}

def _objidtopath(objid):
    if objid.find(_g_myprefix) != 0:
        raise Exception(f"tidal: bad objid {objid}: bad prefix")
    return objid[len(_g_myprefix):].lstrip("/")

def load_tile_image_unexpired(
        tile_type : TileType, 
        tile_id : str,
        expiration_time_sec : int = constants.tile_image_expiration_time_sec) -> TileImage:
    tile_image : TileImage = persistence.load_tile_image(
        tile_type = tile_type, 
        tile_id = tile_id)
    return (tile_image 
        if tile_image and not is_tile_imaged_expired(
            tile_image = tile_image,
            expiration_time_sec = expiration_time_sec) 
        else None)
    
def is_tile_imaged_expired(
        tile_image : TileImage,
        expiration_time_sec : int = constants.tile_image_expiration_time_sec) -> bool:
    update_time : datetime.datetime = tile_image.update_time
    if not update_time: return True
    if update_time < (datetime.datetime.now() - datetime.timedelta(seconds = expiration_time_sec)):
        return True
    return False

def get_category_image_url(category : TidalItemList) -> str:
    category_tile_image : TileImage = persistence.load_tile_image(TileType.CATEGORY, category.title)
    tile_image_valid : bool = category_tile_image and not is_tile_imaged_expired(category_tile_image)
    category_image_url : str = category_tile_image.tile_image if tile_image_valid else None
    msgproc.log(f"category_to_entry category [{category.title}] type [{type(category).__name__}] cached [{'yes' if category_image_url else 'no'}]")
    if not category_image_url:
        # load category image
        if isinstance(category, TidalFeaturedItems):
            featured : TidalFeaturedItems = category
            first_featured = featured.items[0] if featured.items and len(featured.items) > 0 else None
            if not first_featured: msgproc.log(f"category_to_entry category [{category.title}] Featured: first_featured not found")
            has_type_attribute : bool = first_featured and has_type_attr(first_featured)
            if first_featured and not has_type_attribute: msgproc.log(f"category_to_entry category [{category.title}] Featured: first_featured no type attribute, type [{type(first_featured).__name__}]")
            if first_featured and has_type_attribute:
                msgproc.log(f"category_to_entry category [{category.title}] (TidalFeaturedItems) first item type [{first_featured.type if first_featured else None}]")
                if first_featured.type == constants.featured_type_name_playlist:
                    playlist : TidalPlaylist = get_session().playlist(first_featured.artifact_id)
                    image_url = safe_get_image_url(playlist) if playlist else None
                    if not image_url: msgproc.log(f"category_to_entry category [{category.title}] (TidalFeaturedItems) cannot get image for playlist")
                else:
                    msgproc.log(f"category_to_entry category [{category.title}] (TidalFeaturedItems): not processed item {first_featured.type}")
        else: # other than FeaturedItems ...
            first_item = category.items[0] if category.items and len(category.items) > 0 else None
            first_item_type : type = type(first_item) if first_item else None
            msgproc.log(f"category_to_entry starting load process for category [{category.title}] type of first_item [{first_item_type.__name__ if first_item_type else None}]")
            image_url : str = None
            if first_item:
                if isinstance(first_item, TidalTrack):
                    #msgproc.log(f"  processing as Track ...")
                    track : TidalTrack = first_item
                    album : TidalAlbum = get_session().album(track.album.id)
                    image_url = tidal_util.get_image_url(album) if album else None
                    #msgproc.log(f"Chosen image for category [{category.title}] using type [{type(first_item).__name__}] image_url [{image_url}]")
                elif isinstance(first_item, TidalMix):
                    #msgproc.log(f"  processing as Mix ...")
                    mix : TidalMix = first_item
                    image_url = tidal_util.get_image_url(mix) if mix else None
                    #msgproc.log(f"Chosen image for category [{category.title}] using type [{type(first_item).__name__}] image_url [{image_url}]")
                elif isinstance(first_item, TidalPlaylist):
                    #msgproc.log(f"  processing as Playlist ...")
                    playlist : TidalPlaylist = first_item
                    image_url = tidal_util.get_image_url(playlist) if playlist else None
                    #msgproc.log(f"Chosen image for category [{category.title}] using type [{type(first_item).__name__}] image_url [{image_url}]")
                elif isinstance(first_item, TidalAlbum):
                    #msgproc.log(f"  processing as Album ...")
                    album : TidalAlbum = first_item
                    image_url = tidal_util.get_image_url(album) if album else None
                    #msgproc.log(f"Chosen image for category [{category.title}] using type [{type(first_item).__name__}] image_url [{image_url}]")
                elif isinstance(first_item, TidalPageLink):
                    #msgproc.log(f"  processing as <PageLink> ...")
                    page_link : TidalPageLink = first_item
                    page_link_items : list[any] = get_items_in_page_link(page_link)
                    for current in page_link_items if page_link_items else list():
                        if (isinstance(current, TidalPlaylist) or
                            isinstance(current, TidalAlbum) or
                            isinstance(current, TidalArtist)):
                            # get an image from that
                            image_url = tidal_util.get_image_url(current)
                            #persistence.save_tile_image(TileType.PAGE_LINK, page_link.api_path, page_link_image_url)
                            # we only need the first
                            break
                        else:
                            msgproc.log(f"get_category_image_url got a [{type(current).__name__ if current else None}] in a [{TidalPageLink.__name__}]")
                else:
                    msgproc.log(f"category_to_entry category [{category.title}] type [{type(first_item).__name__}] has not been managed")
            else:
                image_url = safe_get_image_url(first_item) if first_item else None
        if image_url:
            persistence.save_tile_image(TileType.CATEGORY, category.title, image_url)
            category_image_url = image_url
        else:
            msgproc.log(f"category_to_entry could not get an image for category [{category.title}]")
    return category_image_url

def category_to_entry(
        objid, 
        category : TidalItemList) -> upmplgutils.direntry:
    title : str = category.title if category.title else "Other"
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.CATEGORY.getName(), 
        title)
    identifier.set(ItemIdentifierKey.CATEGORY_KEY, category.title)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, 
        objid, 
        title)
    # category image
    category_image_url : str = get_category_image_url(category)
    if category_image_url:
        upnp_util.set_album_art_from_uri(category_image_url, entry)
    else:
        msgproc.log(f"category_to_entry *Warning* category [{category.title}] type [{type(category)}] tile image not set.")
    return entry

def get_option(options : dict[str, any], option_key : OptionKey) -> any:
    return options[option_key.get_name()] if option_key.get_name() in options else option_key.get_default_value()

def set_option(options : dict[str, any], option_key : OptionKey, option_value : any) -> None:
    options[option_key.get_name()] = option_value

def get_album_track_num(track_adapter : TrackAdapter) -> str:
    if track_adapter.get_volume_num() and track_adapter.get_volume_num() > 1:
        return f"{track_adapter.get_volume_num()}.{track_adapter.get_track_num():02}"
    else:
        return track_adapter.get_track_num()

def track_apply_explicit(track_adapter : TrackAdapter, current_title : str = None, options : dict[str, any] = {}) -> str:
    title : str = current_title if current_title else track_adapter.get_name()
    if track_adapter.explicit():
        title : str = f"{title} [Explicit]"
    return title

def get_track_name_for_track_container(
        track_adapter: TrackAdapter,
        options : dict[str, any] = {}) -> str:
    skip_track_artist : bool  = get_option(
        options = options, 
        option_key = OptionKey.SKIP_TRACK_ARTIST)
    title : str = track_adapter.get_name()
    if not skip_track_artist:
        title : str = f"{track_adapter.get_artist_name()} - {title}"
    skip_track_number : bool = get_option(
        options = options, 
        option_key = OptionKey.SKIP_TRACK_NUMBER)
    if not skip_track_number:
        forced_track_number : int = get_option(
            options = options, 
            option_key = OptionKey.FORCED_TRACK_NUMBER)
        track_number : str = (f"{forced_track_number:02}" 
            if forced_track_number 
            else get_album_track_num(track_adapter))
        title : str = f"[{track_number}] {title}"
    title = track_apply_explicit(
        track_adapter = track_adapter,
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
        track_adapter = instance_tidal_track_adapter(track = track),
        element_type = ElementType.MIX_NAVIGABLE_ITEM,
        options = options)

def track_to_navigable_playlist_item(
        objid, 
        track: TidalTrack,
        options : dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid = objid,
        track_adapter = instance_tidal_track_adapter(track = track),
        element_type = ElementType.PLAYLIST_NAVIGABLE_ITEM,
        options = options)

def track_to_navigable_track(
        objid, 
        track_adapter: TrackAdapter,
        options : dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid = objid,
        track_adapter = track_adapter,
        element_type = ElementType.NAVIGABLE_TRACK,
        options = options)

def track_to_navigable_track_by_element_type(
        objid, 
        track_adapter: TrackAdapter,
        element_type : ElementType,
        options : dict[str, any] = {}) -> dict:
    identifier : ItemIdentifier = ItemIdentifier(
        element_type.getName(), 
        track_adapter.get_id())
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
            track_adapter = track_adapter, 
            options = options)
    track_entry = upmplgutils.direntry(id,
        objid,
        title)
    upnp_util.set_album_art_from_uri(track_adapter.get_image_url(), track_entry)
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
            track_adapter = instance_tidal_track_adapter(track = track), 
            options = options)
    track_entry = upmplgutils.direntry(id,
        objid,
        title)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(track.album), track_entry)
    return track_entry

def track_to_entry(
        objid, 
        track_adapter : TrackAdapter,
        options : dict[str, any] = {}) -> dict:
    entry = {}
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), track_adapter.get_id())
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = track_adapter.get_id()
    upnp_util.set_class_music_track(entry)
    song_uri : str = build_intermediate_url(track_adapter.get_id())
    entry['uri'] = song_uri
    title : str = track_adapter.get_name()
    upnp_util.set_album_title(title, entry)
    entry['tp']= 'it'
    skip_track_num : bool = get_option(
        options = options,
        option_key = OptionKey.SKIP_TRACK_NUMBER)
    if not skip_track_num:
        forced_track_number : int = get_option(
            options = options,
            option_key = OptionKey.FORCED_TRACK_NUMBER)
        track_num = (forced_track_number 
            if forced_track_number 
            else get_album_track_num(track_adapter))
        upnp_util.set_track_number(str(track_num), entry)
    upnp_util.set_artist(track_adapter.get_album_artist_name(), entry)
    entry['upnp:album'] = track_adapter.get_album_name()
    entry['res:mime'] = tidal_util.get_mime_type(track_adapter.get_audio_quality())
    skip_art : bool = get_option(
        options = options,
        option_key = OptionKey.SKIP_ART)
    if not skip_art:
        art_url : str = get_option(
            options = options,
            option_key = OptionKey.OVERRIDDEN_ART_URI)
        if not art_url: art_url = track_adapter.get_image_url()
        upnp_util.set_album_art_from_uri(art_url, entry)
    entry['duration'] = str(track_adapter.get_duration())
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
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(artist), entry)
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
    if add_explicit and album.explicit and not "explicit" in album_title.lower():
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
    if not as_container: upnp_util.set_class_album(entry)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), entry)
    return entry

def pagelink_to_entry(
        objid,
        category : TidalItemList,
        page_link : TidalPageLink,
        page_list : list[str] = list()) -> upmplgutils.direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.PAGELINK.getName(), 
        page_link.title)
    identifier.set(ItemIdentifierKey.PAGE_LINK_API_PATH, page_link.api_path)
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
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(playlist), entry)
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
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(mix), entry)
    return entry

def get_categories() -> list[TidalItemList]:
    session : TidalSession = get_session()
    home = session.home()
    home.categories.extend(session.explore().categories)
    #home.categories.extend(session.videos().categories)
    return home.categories

def get_category(category_name : str):
    categories : list[TidalItemList] = get_categories()
    match_list : list = list()
    first = None
    for current in categories:
        if current.title == category_name: 
            if not first: first = current
            match_list.append(current)
    if len(match_list) > 1: msgproc.log(f"get_category: multiple matches for [{category_name}], returning first")
    return first
    
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
        next_button = create_next_button(
            objid = objid, 
            element_type = ElementType.TAG, 
            element_id = TagType.FAVORITE_ALBUMS.getTagName(),
            next_offset = offset + max_items)
        entries.append(next_button)
    return entries

def handler_tag_favorite_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    items : list[TidalArtist] = get_session().user.favorites.artists(limit = max_items, offset = offset)
    current : TidalArtist
    for current in items:
        entries.append(artist_to_entry(objid, artist = current))
    if len(items) >= max_items:
        next_button = create_next_button(
            objid = objid, 
            element_type = ElementType.TAG, 
            element_id = TagType.FAVORITE_ARTISTS.getTagName(),
            next_offset = offset + max_items)
        entries.append(next_button)
    return entries

def handler_tag_favorite_tracks(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    tuple_array = [
        (ElementType.FAVORITE_TRACKS_NAVIGABLE, "My Tracks (Navigable)"), 
        (ElementType.FAVORITE_TRACKS_LIST, "My Tracks (list)")]
    for current_tuple in tuple_array:
        identifier : ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(), 
            current_tuple[0].getName())
        id : str = identifier_util.create_objid(
            objid = objid, 
            id = identifier_util.create_id_from_identifier(identifier))
        entry = upmplgutils.direntry(id, 
            objid, 
            current_tuple[1])
        fav_tracks : list[TidalTrack] = get_session().user.favorites.tracks(limit = 10)
        random_track : TidalTrack = secrets.choice(fav_tracks) if fav_tracks else None
        select_album : TidalAlbum = get_session().album(random_track.album.id) if random_track else None
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(select_album) if select_album else None, entry)
        entries.append(entry)
    return entries

def handler_tag_all_playlists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    playlists : list[TidalPlaylist] = get_session().user.playlist_and_favorite_playlists(offset = offset)
    current : TidalPlaylist
    for current in playlists:
        try:
            entries.append(playlist_to_playlist_container(
                objid = objid, 
                playlist = current))
        except Exception as ex:
            msgproc.log(f"Cannot create playlist entry for playlist_id [{current.id}] Exception [{ex}]")
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
    last_played_tracks : list[PlayedTrack] = persistence.get_last_played_tracks(max_tracks = 20)
    most_played_tracks : list[PlayedTrack] = persistence.get_most_played_tracks(max_tracks = 20)
    most_played_albums : list[PlayedAlbum] = persistence.get_most_played_albums(max_albums = 10)
    random_most_played_album : PlayedAlbum = secrets.choice(most_played_albums) if most_played_albums and len(most_played_albums) > 0 else None
    most_played_album : TidalAlbum = get_session().album(random_most_played_album.album_id) if random_most_played_album else None
    most_played_album_url : str = tidal_util.get_image_url(most_played_album) if most_played_album else None
    last_played_albums : list[str] = get_last_played_album_id_list(max_tracks = 10)
    random_last_played_album_id : str = secrets.choice(last_played_albums) if last_played_albums and len(last_played_albums) > 0 else None
    random_last_played_album : TidalAlbum = get_session().album(random_last_played_album_id) if random_last_played_album_id else None
    random_last_played_album_url : str = tidal_util.get_image_url(random_last_played_album) if random_last_played_album else None
    get_url_of_random : Callable[[list[TidalAlbum]], str] = lambda album_list: secrets.choice(album_list).image_url if album_list and len(album_list) > 0 else None
    tuple_array = [
        (ElementType.RECENTLY_PLAYED_ALBUMS, "Recently played albums", random_last_played_album_url),
        (ElementType.MOST_PLAYED_ALBUMS, "Most Played Albums", most_played_album_url),
        (ElementType.RECENTLY_PLAYED_TRACKS_NAVIGABLE, "Recently played tracks (Navigable)", get_url_of_random(last_played_tracks)),
        (ElementType.RECENTLY_PLAYED_TRACKS_LIST, "Recently played tracks (List)", get_url_of_random(last_played_tracks)),
        (ElementType.MOST_PLAYED_TRACKS_NAVIGABLE, "Most played tracks (Navigable)", get_url_of_random(most_played_tracks)),
        (ElementType.MOST_PLAYED_TRACKS_LIST, "Most played tracks (List)", get_url_of_random(most_played_tracks))]
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
        art_url : str = current_tuple[2]
        if art_url: upnp_util.set_album_art_from_uri(art_url, entry)
        entries.append(entry)
    return entries

def handler_tag_categories(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    current : TidalItemList
    category_index : int = 0
    for current in get_categories():
        msgproc.log(f"handler_tag_categories processing category[{category_index}]: [{current.title}] type [{type(current).__name__ if current else None}]")
        title : str = current.title
        entry = category_to_entry(objid, current)
        entries.append(entry)
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
            track_adapter = instance_tidal_track_adapter(track = track), 
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
        #msgproc.log(f"follow_page_link type of next is [{type(next).__name__}]")
        if isinstance(next, TidalPageLink):
            try:
                next = next.get()
            except Exception as next_exc:
                msgproc.log(f"Cannot execute next, exc [{next_exc}]")
                next = None
            #msgproc.log(f"  next found: [{'yes' if next else 'no'}] type: [{type(next).__name__ if next else None}]")
        else:
            break
    return next

def get_items_in_page_link(page_link : TidalPageLink) -> list[any]:
    items : list[any] = list()
    linked = follow_page_link(page_link)
    #msgproc.log(f"get_items_in_page_link linked_object is [{type(linked).__name__ if linked else None}]")
    if not linked: return items
    if isinstance(linked, TidalPage):
        #msgproc.log(f"get_items_in_page_link: found a Page")
        for current in linked:
            #msgproc.log(f"get_items_in_page_link: iterating Page, got a [{type(current).__name__ if current else None}]")
            if isinstance(current, TidalPageLink):
                new_page_link : TidalPageLink = current
                items.extend(get_items_in_page_link(new_page_link))
            else:
                items.append(current)
    else:
        msgproc.log(f"get_items_in_page_link[{page_link.api_path}]: found a [{type(linked).__name__}], not handled")
    return items

def handler_element_pagelink(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    thing_name : str = item_identifier.get(ItemIdentifierKey.THING_NAME)
    thing_value : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    api_path : str = item_identifier.get(ItemIdentifierKey.PAGE_LINK_API_PATH)
    category_title : str = item_identifier.get(ItemIdentifierKey.CATEGORY_TITLE)
    msgproc.log(f"handler_element_pagelink name [{thing_name}] value [{thing_value}] category_title [{category_title}] api_path [{api_path}]")
    try:
        page : TidalPage = get_session().page.get(api_path)
        if not page: 
            msgproc.log(f"handler_element_pagelink page not found")
            return entries
        if page: page_to_entries(objid, page, entries)
    except Exception as ex:
        msgproc.log(f"handler_element_pagelink could not retrieve page at api_path [{api_path}] [{ex}]")
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
        try:
            #msgproc.log(f"page_to_entries type of current_page_item [{type(current_page_item).__name__}]")
            new_entry : dict = convert_page_item_to_entry(
                objid = objid, 
                page_item = current_page_item)
            if new_entry: entries.append(new_entry)
            # set an image?
            if isinstance(current_page_item, TidalPageLink):
                item_list : list[any] = get_items_in_page_link(page_link = current_page_item)
                first_item : any = item_list[0] if item_list and len(item_list) > 0 else None
                #msgproc.log(f"page_to_entries type of current_page_item [{type(current_page_item).__name__}] first_item [{type(first_item).__name__ if first_item else None}]")
                if isinstance(first_item, TidalPlaylist):
                    image_url : str = tidal_util.get_image_url(first_item)
                    upnp_util.set_album_art_from_uri(album_art_uri = image_url, target = new_entry)
                else:
                    msgproc.log(f"page_to_entries type of current_page_item [{type(current_page_item).__name__}] first_item [{type(first_item).__name__ if first_item else None}] not handled")
            else:
                msgproc.log(f"page_to_entries type of current_page_item [{type(current_page_item).__name__}] first_item [{type(first_item).__name__ if first_item else None}] not handled")
        except Exception as ex:
            msgproc.log(f"page_to_entries could not convert type [{type(current_page_item).__name__ if current_page_item else None}] Exception [{ex}]")
    return entries

def convert_page_item_to_entry(objid, page_item : TidalPageItem) -> any:
    if isinstance(page_item, TidalPlaylist):
        return playlist_to_playlist_container(
            objid = objid, 
            playlist = page_item)
    elif isinstance(page_item, TidalAlbum):
        return album_to_album_container(
            objid = objid, 
            album = page_item)
    elif isinstance(page_item, TidalArtist):
        return artist_to_entry(objid, artist = page_item)
    elif isinstance(page_item, TidalTrack):
        track : TidalTrack = page_item
        options : dict[str, any] = dict()
        set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
        return track_to_navigable_track(
            objid = objid, 
            track_adapter = instance_tidal_track_adapter(track = track), 
            options = options)
    elif isinstance(page_item, TidalPageLink):
        page_link : TidalPageLink = page_item
        return page_to_entry(
            objid = objid,
            api_path = page_link.api_path,
            page_title = page_link.title)
    else:
        msgproc.log(f"convert_page_item_to_entry item of type {type(page_item) if page_item else None} not handled")
    return None

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
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(mix), entry)
        entries.append(entry)
    return entries

def handler_element_album_container(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album : TidalAlbum = get_session().album(album_id)
    album_name : str = album.name
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM.getName(), 
        album_id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id, 
        objid, 
        "Album")
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), entry)
    entries.append(entry)
    # add Artists
    artist_list : list[TidalArtist] = get_artist_list(album.artist, album.artists)
    for current in artist_list:
        artist : TidalArtist = get_session().artist(current.id)
        entries.append(artist_to_entry(objid = objid, artist = artist))
    in_favorites : bool = album_id in get_favorite_album_id_list()
    fav_action_elem : ElementType
    fav_action_text : str
    fav_action_elem, fav_action_text = (
        (ElementType.FAV_ALBUM_DEL, "Remove from Favories") if in_favorites 
        else (ElementType.FAV_ALBUM_ADD, "Add to Favorites"))
    msgproc.log(f"Album with id [{album_id}] name [{album_name}] is in favorites: [{'yes' if in_favorites else 'no'}]")
    fav_action : ItemIdentifier = ItemIdentifier(
        fav_action_elem.getName(), 
        album_id)
    fav_action_id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(fav_action))
    entry = upmplgutils.direntry(fav_action_id, 
        objid, 
        fav_action_text)
    entries.append(entry)
    has_been_played : bool = persistence.album_has_been_played(album_id)
    msgproc.log(f"Album with id [{album_id}] name [{album_name}] has been played: [{'yes' if has_been_played else 'no'}]")
    if has_been_played:
        # add entry for removing from stats
        rm_stats : ItemIdentifier = ItemIdentifier(
            ElementType.REMOVE_ALBUM_FROM_STATS.getName(), 
            album_id)
        rm_stats_id : str = identifier_util.create_objid(
            objid = objid, 
            id = identifier_util.create_id_from_identifier(rm_stats))
        rm_entry = upmplgutils.direntry(rm_stats_id, 
            objid, 
            "Remove album from Statistics")
        entries.append(rm_entry)
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
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(playlist), entry)
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
        entries.append(album_to_album_container(
            objid = objid, 
            album = album))
    # add remove from stats if needed
    entries = add_remove_track_from_stats_if_needed(objid, track, entries)
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
        track_entry : dict = None
        try:
            track_entry = track_to_navigable_playlist_item(
                objid, 
                track = track, 
                options = options)
        except Exception as ex:
            msgproc.log(f"Cannot create track entry for track_id [{track.id}] num [{track_number}] [{track.name}] [{track.album.id}] [{track.album.name}] Exception [{ex}]")
        track_number += 1
        if track_entry: entries.append(track_entry)
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
        track_entry : dict = None
        try:
            track_entry = track_to_entry(
                objid, 
                track_adapter = instance_tidal_track_adapter(track = track), 
                options = options)
        except Exception as ex:
            msgproc.log(f"Cannot create track entry for track_id [{track.id}] num [{track_number}] [{track.name}] [{track.album.id}] [{track.album.name}] Exception [{ex}]")
        # let use know some tracks are missing
        track_number += 1
        if track_entry: entries.append(track_entry)
    return entries

def handler_element_album(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    album_id : int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album : TidalAlbum = get_session().album(album_id)
    is_multidisc_album : bool = tidal_util.is_multidisc_album(album)
    msgproc.log(f"Album {album_id} is multidisc {is_multidisc_album}")
    tracks : list[TidalTrack] = album.tracks()
    options : dict[str, any] = {}
    set_option(options, OptionKey.SKIP_TRACK_ARTIST, True)
    track_num : int = 1 
    track : TidalTrack
    for track in tracks:
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_num)
        track_entry = track_to_entry(
            objid = objid, 
            track_adapter = instance_tidal_track_adapter(track = track),
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
        entries.append(album_to_album_container(objid, current))
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

def get_top_tracks(
        artist : TidalArtist, 
        limit: Optional[int] = None, 
        offset: int = 0) -> list[TidalTrack]:
    try:
        return artist.get_top_tracks(
            limit = limit, 
            offset = offset)
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
            track_adapter = instance_tidal_track_adapter(track = current),
            options = options))
    return entries

def add_track_as_list_to_entries(objid, items : list[TidalTrack], entries : list) -> list:
    current : TidalTrack
    track_num : int = 1
    for current in items if items else list():
        options : dict[str, any] = dict()
        set_option(options = options, option_key = OptionKey.FORCED_TRACK_NUMBER, option_value = track_num)
        entries.append(track_to_entry(
            objid = objid, 
            track_adapter = instance_tidal_track_adapter(track = current),
            options = options))
        track_num += 1
    return entries

def handler_element_favorite_tracks_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    items : list[TidalTrack] = get_session().user.favorites.tracks(limit = max_items, offset = offset)
    entries = add_tracks_to_entries(objid, items, entries)
    if len(items) == max_items:
        next_button = create_next_button(
            objid = objid, 
            element_type = ElementType.FAVORITE_TRACKS_NAVIGABLE, 
            element_id = ElementType.FAVORITE_TRACKS_NAVIGABLE.getName(),
            next_offset = offset + max_items)
        entries.append(next_button)
    return entries

def handler_element_favorite_tracks_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    items : list[TidalTrack] = get_session().user.favorites.tracks()
    return add_track_as_list_to_entries(objid, items, entries)    

def handler_element_artist_top_tracks_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    items : list[TidalTrack] = get_top_tracks(
        artist = artist,
        limit = max_items,
        offset = offset)
    entries = add_tracks_to_entries(objid, items, entries)
    if len(items) == max_items:
        next_button = create_next_button(
            objid = objid, 
            element_type = ElementType.ARTIST_TOP_TRACKS_NAVIGABLE, 
            element_id = artist_id,
            next_offset = offset + max_items)
        entries.append(next_button)
    return entries

def handler_element_artist_top_tracks_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    items : list[TidalTrack] = get_top_tracks(artist)
    return add_track_as_list_to_entries(objid, items, entries)

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

def get_favorite_artist_id_list() -> list[str]:
    item_list : list[str] = list()
    fav_list : list[TidalArtist] = get_session().user.favorites.artists()
    current : TidalArtist
    for current in fav_list:
        item_list.append(current.id)
    return item_list

def get_favorite_album_id_list() -> list[str]:
    item_list : list[str] = list()
    fav_list : list[TidalAlbum] = get_session().user.favorites.albums()
    current : TidalAlbum
    for current in fav_list:
        item_list.append(current.id)
    return item_list

def handler_element_artist_add_to_fav(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    if not artist_id in get_favorite_artist_id_list():
        get_session().user.favorites.add_artist(artist_id = artist_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(), 
        artist_id)
    return handler_element_artist(objid, item_identifier = identifier, entries = entries)

def handler_element_album_add_to_fav(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    if not album_id in get_favorite_album_id_list():
        get_session().user.favorites.add_album(album_id = album_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_CONTAINER.getName(), 
        album_id)
    return handler_element_album_container(objid, item_identifier = identifier, entries = entries)

def handler_element_artist_del_from_fav(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    if artist_id in get_favorite_artist_id_list():
        get_session().user.favorites.remove_artist(artist_id = artist_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(), 
        artist_id)
    return handler_element_artist(objid, item_identifier = identifier, entries = entries)

def handler_element_album_del_from_fav(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    if album_id in get_favorite_album_id_list():
        get_session().user.favorites.remove_album(album_id = album_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_CONTAINER.getName(), 
        album_id)
    return handler_element_album_container(objid, item_identifier = identifier, entries = entries)

def get_artist_image_url(artist_id : str) -> str:
    artist : TidalArtist = get_session().artist(artist_id)
    return tidal_util.get_image_url(artist) if artist else None

def get_artist_albums_image_url(artist_id : str) -> str:
    return get_artist_albums_by_album_extractor_image_url(
        artist_id = artist_id, 
        extractor = lambda artist: artist.get_albums())

def get_artist_albums_ep_singles_image_url(artist_id : str) -> str:
    return get_artist_albums_by_album_extractor_image_url(
        artist_id = artist_id, 
        extractor = lambda artist: artist.get_albums_ep_singles())

def get_artist_albums_others_image_url(artist_id : str) -> str:
    return get_artist_albums_by_album_extractor_image_url(
        artist_id = artist_id, 
        extractor = lambda artist: artist.get_albums_other())

def get_artist_albums_by_album_extractor_image_url(
        artist_id : str, 
        extractor : Callable[[TidalArtist], list[TidalAlbum]]) -> str:
    try:
        artist : TidalArtist = get_session().artist(artist_id)
        album_list : list[TidalAlbum] = extractor(artist)
        return choose_album_image_url(album_list)
    except Exception as ex:
        msgproc.log(f"Cannot get albums for artist_id [{artist.id}]")

def get_artist_top_tracks_image_url(artist_id : str) -> str:
    try:
        artist : TidalArtist = get_session().artist(artist_id)
        tracks : list[TidalTrack] = artist.get_top_tracks() if artist else None
        select : TidalTrack = secrets.choice(tracks) if tracks and len(tracks) > 0 else None
        album : TidalAlbum = get_session().album(select.album.id) if select else None
        return tidal_util.get_image_url(album) if album else None
    except Exception as ex:
        msgproc.log(f"Cannot get top tracks image for artist_id [{artist.id}]")

def get_artist_radio_image_url(artist_id : str) -> str:
    try:
        artist : TidalArtist = get_session().artist(artist_id)
        tracks : list[TidalTrack] = artist.get_radio() if artist else None
        select : TidalTrack = secrets.choice(tracks) if tracks and len(tracks) > 0 else None
        album : TidalAlbum = get_session().album(select.album.id) if select else None
        return tidal_util.get_image_url(album) if album else None
    except Exception as ex:
        msgproc.log(f"Cannot get artist radio image for artist_id [{artist.id}]")

def choose_album_image_url(album_list : list[TidalAlbum]) -> str:
    select : TidalAlbum = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
    return tidal_util.get_image_url(select) if select else None

def get_similar_artists_image_url(artist_id : str) -> str:
    try:
        artist : TidalArtist = get_session().artist(artist_id)
        similar_artist_list : list[TidalArtist] = artist.get_similar() if artist else None
        select : TidalArtist = secrets.choice(similar_artist_list) if similar_artist_list and len(similar_artist_list) > 0 else None
        return tidal_util.get_image_url(select) if select else None
    except Exception as ex:
        msgproc.log(f"Cannot get similar artists for artist_id [{artist.id}]")

def handler_element_artist(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : TidalArtist = get_session().artist(artist_id)
    artist_name : str = artist.name
    if not artist: 
        msgproc.log(f"Artist with id {artist_id} not found")
        return entries
    msgproc.log(f"Loading page for artist_id: [{artist_id}] artist.id: [{artist.id}] artist.name: [{artist.name}]")
    album_tuple_array = [
        (ElementType.ARTIST_ALBUM_ALBUMS, "Albums", get_artist_albums_image_url), 
        (ElementType.ARTIST_ALBUM_EP_SINGLES, "EP and Singles", get_artist_albums_ep_singles_image_url),
        (ElementType.ARTIST_ALBUM_OTHERS, "Other Albums", get_artist_albums_others_image_url),
        (ElementType.SIMILAR_ARTISTS, "Similar Artists", get_similar_artists_image_url),
        (ElementType.ARTIST_TOP_TRACKS_NAVIGABLE, "Top Tracks", get_artist_top_tracks_image_url),
        (ElementType.ARTIST_TOP_TRACKS_LIST, "Top Tracks (List)", get_artist_top_tracks_image_url),
        (ElementType.ARTIST_RADIO_NAVIGABLE, "Radio", get_artist_radio_image_url),
        (ElementType.ARTIST_RADIO_LIST, "Radio (List)", get_artist_radio_image_url)]
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
        upnp_util.set_album_art_from_uri(album_tuple[2](artist_id), entry)
        entries.append(entry)
    in_favorites : bool = artist.id in get_favorite_artist_id_list()
    fav_action_elem : ElementType
    fav_action_text : str
    fav_action_elem, fav_action_text = (
        (ElementType.FAV_ARTIST_DEL, "Remove from Favories") if in_favorites 
        else (ElementType.FAV_ARTIST_ADD, "Add to Favorites"))
    msgproc.log(f"Artist with id [{artist_id}] name [{artist_name}] is in favorites: [{'yes' if in_favorites else 'no'}]")
    fav_action : ItemIdentifier = ItemIdentifier(
        fav_action_elem.getName(), 
        artist_id)
    fav_action_id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(fav_action))
    entry = upmplgutils.direntry(fav_action_id, 
        objid, 
        fav_action_text)
    entries.append(entry)
    return entries

def add_remove_track_from_stats_if_needed(objid, track : TidalTrack, entries : list) -> list:
    has_been_played : bool = persistence.track_has_been_played(track.id)
    msgproc.log(f"Track with id [{track.id}] name [{track.name}] has been played: [{'yes' if has_been_played else 'no'}]")
    if has_been_played:
        # add entry for removing from stats
        rm_stats : ItemIdentifier = ItemIdentifier(
            ElementType.REMOVE_TRACK_FROM_STATS.getName(), 
            track.id)
        rm_stats_id : str = identifier_util.create_objid(
            objid = objid, 
            id = identifier_util.create_id_from_identifier(rm_stats))
        rm_entry = upmplgutils.direntry(rm_stats_id, 
            objid, 
            "Remove track from Statistics")
        entries.append(rm_entry)
    return entries

def handler_element_track_container(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    track_id : int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    track : TidalTrack = get_session().track(track_id)
    track_entry = track_to_entry(
        objid = objid, 
        track_adapter = instance_tidal_track_adapter(track = track))
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
    select_category : str = item_identifier.get(ItemIdentifierKey.CATEGORY_KEY)
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
            item_type : str = type(item).__name__
            item_name : str = tidal_util.get_name_or_title(item)
            msgproc.log(f"handler_element_category [{category.title}] [{index}] [{item_type}] [{item_name}]")
            #msgproc.log(f"handler_element_category categories[{select_category}].item[{index}] type is [{item_type}]")
            if isinstance(item, TidalPageLink):
                page_link : TidalPageLink = item
                msgproc.log(f"handler_element_category [{category.title}] [{index}] [{item_type}] [{item_name}] [{page_link.api_path}]")
                page_link_entry : dict = pagelink_to_entry(objid, category = category, page_link = item)
                entries.append(page_link_entry)
                # TODO maybe extract method for getting image for a PageLink
                tile_image : TileImage = load_tile_image_unexpired(TileType.PAGE_LINK, page_link.api_path)
                page_link_image_url : str = tile_image.tile_image if tile_image else None
                if not page_link_image_url:
                    items_in_page : list = get_items_in_page_link(page_link)
                    for current in items_in_page if items_in_page else list():
                        if (isinstance(current, TidalPlaylist) or
                            isinstance(current, TidalAlbum) or
                            isinstance(current, TidalArtist)):
                            # get an image from that
                            page_link_image_url = tidal_util.get_image_url(current)
                            persistence.save_tile_image(TileType.PAGE_LINK, page_link.api_path, page_link_image_url)
                            # we only need the first
                            break
                        else:
                            msgproc.log(f"handler_element_category [{category.title}] [{index}] [{item_type}] [{item_name}] [{page_link.api_path}] num_items [{len(items_in_page)}] current [{type(current).__name__ if current else None}]")
                upnp_util.set_album_art_from_uri(page_link_image_url, page_link_entry)
            elif isinstance(item, TidalMix):
                msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                entries.append(mix_to_mix_container(objid, mix = item))
            elif isinstance(item, TidalTrack):
                msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                options : dict[str, any] = dict()
                set_option(options, OptionKey.SKIP_TRACK_NUMBER, True)
                entries.append(track_to_track_container(
                    objid = objid, 
                    track = item,
                    options = options))
            elif isinstance(item, TidalPlaylist):
                msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                entries.append(playlist_to_playlist_container(
                    objid = objid,
                    playlist = item))
            elif isinstance(item, TidalAlbum):
                album : TidalAlbum = item
                msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                options : dict[str, any] = dict()
                entries.append(album_to_album_container(objid, album = album))
            else:
                msgproc.log(f"handler_element_category [{category.title}] [{index}] [{item_type}] [{item_name}] was not handled!")
            index += 1
    return entries

# this allows kodi to work with the plugin
def track_data_to_entry(objid, entry_id : str, track : TidalTrack) -> dict:
    entry : dict = {}
    entry['id'] = entry_id
    entry['pid'] = track.id
    upnp_util.set_class_music_track(entry)
    entry['uri'] = build_intermediate_url(track.id)
    title : str = track.name
    upnp_util.set_album_title(title, entry)
    entry['tp']= 'it'
    entry['discnumber'] = track.volume_num
    upnp_util.set_track_number(track.track_num, entry)
    upnp_util.set_artist(track.artist.name, entry)
    entry['upnp:album'] = track.album.name
    entry['res:mime'] = tidal_util.get_mime_type(track.audio_quality)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(track.album), entry)
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

def is_played_track_complete(played_track : PlayedTrack) -> bool:
    return (
        not played_track.track_id is None and
        not played_track.album_id is None and
        not played_track.album_track_count is None and
        not played_track.track_name is None and
        not played_track.track_duration is None and
        not played_track.track_num is None and
        not played_track.volume_num is None and
        not played_track.album_num_volumes is None and
        not played_track.album_name is None and
        not played_track.audio_quality is None and
        not played_track.album_artist_name is None and
        not played_track.image_url is None and
        not played_track.explicit is None and
        not played_track.artist_name is None) 

def played_track_list_to_entries(objid, played_tracks : list[PlayedTrack], entries : list) -> list:
    current : PlayedTrack
    options : dict[str, any] = dict()
    set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
    track_num : int = 1
    for current in played_tracks if played_tracks else list():
        track_adapter : TrackAdapter = choose_track_adapter(current)
        set_option(options = options, option_key = OptionKey.FORCED_TRACK_NUMBER, option_value = track_num)
        track_entry : dict = track_to_navigable_track(
            objid = objid, 
            track_adapter = track_adapter,
            options = options)
        entries.append(track_entry)
        track_num += 1
    return entries

def handler_element_recently_played_tracks_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return played_track_list_to_list_entries(objid, persistence.get_last_played_tracks(), entries)

def handler_element_most_played_tracks_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return played_track_list_to_list_entries(objid, persistence.get_most_played_tracks(), entries)

def get_unique_album_id_list(track_list : list[PlayedTrack]) -> list[str]:
    album_id_list : list[str] = list()
    album_id_set : set[str] = set()
    current : PlayedTrack
    for current in track_list if track_list else []:
        current_album_id : str = current.album_id
        if not current_album_id in album_id_set:
            album_id_list.append(current_album_id)
            album_id_set.add(current_album_id)
    return album_id_list

def get_last_played_album_id_list(max_tracks : int) -> list[str]:
    track_list : list[PlayedTrack] = persistence.get_last_played_tracks(max_tracks = max_tracks)
    return get_unique_album_id_list(track_list)

def handler_element_remove_track_from_stats(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    track_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    if not track_id: return entries
    msgproc.log(f"Removing {track_id} from playback statistics ...")
    persistence.delete_track_from_played_tracks(track_id)
    msgproc.log(f"Removed {track_id} from playback statistics.")
    track : TidalTrack = get_session().track(track_id)
    entries.append(track_to_navigable_track(objid, track_adapter = instance_tidal_track_adapter(track = track)))
    return entries

def handler_element_remove_album_from_stats(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    if not album_id: return entries
    msgproc.log(f"Removing {album_id} from playback statistics ...")
    persistence.delete_album_from_played_tracks(album_id)
    msgproc.log(f"Removed {album_id} from playback statistics.")
    album : TidalAlbum = get_session().album(album_id)
    entries.append(album_to_album_container(objid = objid, album = album))
    return entries

def handler_element_recently_played_albums(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_tracks : int = 10000
    albums_per_page : int = 25
    next_needed : bool = False
    album_id_list : list[str] = get_last_played_album_id_list(max_tracks = max_tracks)
    from_offset_album_id_list : list[str] = album_id_list[offset:]
    if len(from_offset_album_id_list) >= albums_per_page: next_needed = True
    page_album_id_list : list[str] = from_offset_album_id_list[0:albums_per_page]
    current_album_id : str
    for current_album_id in page_album_id_list:
        album : TidalAlbum = get_session().album(current_album_id)
        entries.append(album_to_album_container(
            objid = objid, 
            album = album))
    if next_needed:
        next_button = create_next_button(
            objid = objid, 
            element_type = ElementType.RECENTLY_PLAYED_ALBUMS, 
            element_id = ElementType.RECENTLY_PLAYED_ALBUMS.getName(),
            next_offset = offset + albums_per_page)
        entries.append(next_button)
    return entries

def handler_element_most_played_albums(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    albums_per_page : int = 25
    max_albums : int = 1000
    next_needed : bool = False
    items : list[PlayedAlbum] = persistence.get_most_played_albums(max_albums = max_albums)
    from_offset_album_list : list[PlayedAlbum] = items[offset:]
    if len(from_offset_album_list) >= albums_per_page: next_needed = True
    page_played_album_list : list[PlayedAlbum] = from_offset_album_list[0:albums_per_page]
    current : PlayedAlbum
    for current in page_played_album_list:
        album : TidalAlbum = get_session().album(current.album_id)
        entries.append(album_to_album_container(objid = objid, album = album))
    if next_needed:
        next_button = create_next_button(
            objid = objid, 
            element_type = ElementType.MOST_PLAYED_ALBUMS, 
            element_id = ElementType.MOST_PLAYED_ALBUMS.getName(),
            next_offset = offset + albums_per_page)
        entries.append(next_button)
    return entries

def load_tidal_track_adapter(track_id : str) -> TidalTrackAdapter:
    msgproc.log(f"Loading track details from Tidal for track_id: [{track_id}]")
    adapter : TidalTrackAdapter = TidalTrackAdapter(get_session().track(track_id), album_retriever)
    # maybe update on db?
    current : PlayedTrack = persistence.get_played_track_entry(track_id = track_id)
    if current:
        msgproc.log(f"Updating played_track for track_id [{track_id}] ...")
        # update using adapter
        request : PlayedTrackRequest = PlayedTrackRequest()
        request.album_track_count = adapter.get_album_track_count()
        request.album_num_volumes = adapter.get_album_num_volumes() if adapter.get_album_num_volumes() else 1
        request.album_id = adapter.get_album_id()
        request.album_artist_name = adapter.get_album_artist_name()
        request.album_name = adapter.get_album_name()
        request.artist_name = adapter.get_artist_name()
        request.audio_quality = adapter.get_audio_quality().value
        request.explicit = adapter.explicit()
        request.track_duration = adapter.get_duration()
        request.track_id = track_id
        request.track_name = adapter.get_name()
        request.track_num = adapter.get_track_num()
        request.volume_num = adapter.get_volume_num()
        request.image_url = adapter.get_image_url()
        request.explicit = 1 if adapter.explicit() else 0
        persistence.update_playback(request, current.play_count, current.last_played)
    return adapter

def choose_track_adapter(played_track : PlayedTrack) -> TrackAdapter:
    played_track_complete : bool = is_played_track_complete(played_track)
    return PlayedTrackAdapter(played_track) if played_track_complete else load_tidal_track_adapter(played_track.track_id)

def played_track_list_to_list_entries(objid, played_tracks : list[PlayedTrack], entries : list) -> list:
    current : PlayedTrack
    track_number : int = 1
    for current in played_tracks if played_tracks else list():
        track_adapter : TrackAdapter = choose_track_adapter(current)
        options : dict[str, any] = dict()
        set_option(
            options = options, 
            option_key = OptionKey.FORCED_TRACK_NUMBER, 
            option_value = track_number)
        track_entry : dict = track_to_entry(
            objid = objid, 
            track_adapter = track_adapter,
            options = options)
        track_number += 1
        entries.append(track_entry)
    return entries

def image_retriever_categories(tag_type : TagType) -> str:
    categories = get_categories()
    first = categories[0] if categories and len(categories) > 0 else None
    return get_category_image_url(first) if first else None

def image_retriever_cached(tag_type : TagType, loader) -> str:
    tile_image : TileImage = load_tile_image_unexpired(
        tile_type = TileType.TAG, 
        tile_id = tag_type.getTagName())
    image_url : str = tile_image.tile_image if tile_image else None
    msgproc.log(f"Image for tag [{tag_type.getTagName()}] cached [{'yes' if image_url else 'no'}]")
    if not image_url:
        image_url = loader(tag_type)
        if image_url: persistence.save_tile_image(TileType.TAG, tag_type.getTagName(), image_url)
    return image_url

def image_retriever_my_playlists(tag_type : TagType) -> str:
    playlists : list[TidalUserPlaylist] = get_session().user.playlists()
    first : TidalUserPlaylist = playlists[0] if playlists and len(playlists) > 0 else None
    return tidal_util.get_image_url(first) if first else None

def image_retriever_all_playlists(tag_type : TagType) -> str:
    playlists : list[TidalPlaylist] = get_session().user.playlist_and_favorite_playlists()
    first : TidalPlaylist = playlists[0] if playlists and len(playlists) > 0 else None
    return tidal_util.get_image_url(first) if first else None

def image_retriever_favorite_albums(tag_type : TagType) -> str:
    items : list[TidalAlbum] = get_session().user.favorites.albums(limit = 1, offset = 0)
    first : TidalAlbum = items[0] if items and len(items) > 0 else None
    return tidal_util.get_image_url(first) if first else None

def image_retriever_favorite_artists(tag_type : TagType) -> str:
    items : list[TidalArtist] = get_session().user.favorites.artists(limit = 1, offset = 0)
    first : TidalArtist = items[0] if items and len(items) > 0 else None
    return tidal_util.get_image_url(first) if first else None

def image_retriever_favorite_tracks(tag_type : TagType) -> str:
    items : list[TidalTrack] = get_session().user.favorites.tracks(limit = 1, offset = 0)
    first : TidalTrack = items[0] if items and len(items) > 0 else None
    album : TidalAlbum = get_session().album(first.album.id) if first else None
    return tidal_util.get_image_url(album) if album else None

def image_retriever_playback_statistics(tag_type : TagType) -> str:
    items : list[PlayedTrack] = persistence.get_last_played_tracks(max_tracks = 10)
    first : PlayedTrack = secrets.choice(items) if items and len(items) > 0 else None
    album : TidalAlbum = get_session().album(first.album_id) if first else None
    return tidal_util.get_image_url(album) if album else None

__tag_image_retriever : dict = {
    TagType.CATEGORIES.getTagName(): image_retriever_categories,
    TagType.MY_PLAYLISTS.getTagName(): image_retriever_my_playlists,
    TagType.ALL_PLAYLISTS.getTagName(): image_retriever_all_playlists,
    TagType.FAVORITE_ALBUMS.getTagName(): image_retriever_favorite_albums,
    TagType.FAVORITE_ARTISTS.getTagName(): image_retriever_favorite_artists,
    TagType.FAVORITE_TRACKS.getTagName(): image_retriever_favorite_tracks,
    TagType.PLAYBACK_STATISTICS.getTagName(): image_retriever_playback_statistics
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
        msgproc.log(f"show_tags found handler for tag [{tag.getTagName()}]: [{'yes' if curr_tag_img_retriever else 'no'}]")
        curr_tag_img : str = image_retriever_cached(tag, curr_tag_img_retriever) if curr_tag_img_retriever else None
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
        limit = limit,
        offset = offset,
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
    origsearch : str = a["origsearch"] if "origsearch" in a else None
    #if not objkind or len(objkind) == 0: objkind = field
    
    msgproc.log(f"Searching for [{value}] as [{field}] objkind [{objkind}] origsearch [{origsearch}] ...")
    resultset_length : int = 0

    if not objkind or len(objkind) == 0:
        if SearchType.ARTIST.get_name() == field:
            # search artists by specified value
            item_list : list[TidalArtist] = tidal_search(SearchType.ARTIST, value)
            resultset_length = len(item_list) if item_list else 0
            for item in item_list:
                entries.append(artist_to_entry(
                    objid = objid, 
                    artist = item))
        elif SearchType.ALBUM.get_name() == field:
            # search albums by specified value
            item_list : list[TidalAlbum] = tidal_search(SearchType.ALBUM, value)
            resultset_length = len(item_list) if item_list else 0
            for item in item_list:
                entries.append(album_to_entry(
                    objid = objid, 
                    album = item))
        elif SearchType.TRACK.get_name() == field:
            # search tracks by specified value
            item_list : list[TidalTrack] = tidal_search(SearchType.TRACK, value)
            resultset_length = len(item_list) if item_list else 0
            options : dict[str, any] = dict()
            set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
            for item in item_list:
                entries.append(track_to_entry(
                    objid = objid, 
                    track_adapter = instance_tidal_track_adapter(item), 
                    options = options))
    else:
        # objkind is set
        model_map : dict[str, SearchType] = dict()
        model_map["track"] = SearchType.TRACK
        model_map["album"] = SearchType.ALBUM
        model_map["artist"] = SearchType.ARTIST
        search_type_list : list[SearchType] = list()
        if objkind in model_map.keys():
            search_type_list.append(model_map[objkind])
        track_options : dict[str, any] = dict()
        set_option(options = track_options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
        st : SearchType
        for st in search_type_list:
            # perform search
            item_list = tidal_search(
                search_type = st, 
                value = value)
            resultset_length += len(item_list) if item_list else 0
            for item in item_list:
                if st.get_model() == TidalArtist:
                    entries.append(artist_to_entry(
                        objid = objid, 
                        artist = item))
                elif st.get_model() == TidalAlbum:
                    entries.append(album_to_entry(
                        objid = objid, 
                        album = item))
                elif st.get_model() == TidalTrack:
                    entries.append(track_to_entry(
                        objid = objid, 
                        track_adapter = instance_tidal_track_adapter(item), 
                        options = track_options))

    msgproc.log(f"Search for [{value}] as [{field}] with objkind [{objkind}] returned [{resultset_length}] entries")
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

    cache_dir : str = upmplgutils.getcachedir(constants.plugin_name)
    msgproc.log(f"Cache dir for [{plugin_name}] is [{cache_dir}]")
    msgproc.log(f"DB version for [{plugin_name}] is [{persistence.get_db_version()}]")

    _g_init = create_session()

    return True

msgproc.mainloop()
