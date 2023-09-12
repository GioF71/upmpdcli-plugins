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

import json
import copy
import os

from datetime import datetime
from typing import Callable

import cmdtalkplugin
from upmplgutils import uplog, setidprefix, direntry, getOptionValue
from html import escape as htmlescape, unescape as htmlunescape
import xbmcplug

import codec
from tag_type import TagType
from tag_type import get_tag_Type_by_name
from element_type import ElementType
from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey
from option_key import OptionKey
import identifier_util
import upnp_util
import search_type

import tidalapi

plugin_name : str = "tidal"
# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = f"0${plugin_name}$"
setidprefix(plugin_name)

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

session : tidalapi.session.Session = None

default_image_sz_by_type : dict[str, int] = dict()
default_image_sz_by_type[tidalapi.artist.Artist.__name__] = [750, 480, 320, 160]
default_image_sz_by_type[tidalapi.album.Album.__name__] = [1280, 640, 320, 160, 80]
default_image_sz_by_type[tidalapi.playlist.Playlist.__name__] = [1080, 750, 640, 480, 320, 160]
default_image_sz_by_type[tidalapi.mix.Mix.__name__] = [1500, 640, 320]
default_image_sz_by_type[tidalapi.playlist.UserPlaylist.__name__] = default_image_sz_by_type[tidalapi.playlist.Playlist.__name__]

log_intermediate_url : bool = getOptionValue(f"{plugin_name}log_intermediate_url", "0") == "1"
log_unavailable_images_sizes : bool = getOptionValue(f"{plugin_name}log_unavailable_images_sizes", "0") == "1"
log_unavailable_image : bool = getOptionValue(f"{plugin_name}log_unavailable_image", "0") == "1"

def get_name_or_title(obj : any) -> str:
    if hasattr(obj, "name"):
        return obj.name
    if hasattr(obj, "title"):
        return obj.title
    return None

def get_image_dimension_list(obj : any) -> list[int]:
    key = type(obj).__name__
    return default_image_sz_by_type[key] if key in default_image_sz_by_type else list()

def get_image_url(obj : any) -> int:
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

def get_audio_quality(quality_desc : str) -> tidalapi.Quality:
    for _, member in tidalapi.Quality.__members__.items():
        if quality_desc == member.value:
            return member
    # fallback
    return tidalapi.Quality.high_lossless

def get_config_audio_quality() -> tidalapi.Quality:
    return get_audio_quality(getOptionValue(f"{plugin_name}audioquality", "LOSSLESS"))

def mp3_only() -> bool:
    q : tidalapi.Quality = get_config_audio_quality()
    return is_mp3(q)

def is_mp3(q : tidalapi.Quality) -> bool:
    return q == tidalapi.Quality.low_320k or q == tidalapi.Quality.low_96k

def create_session():
    global session
    res : bool = False
    if not session:
        new_session : tidalapi.session.Session = tidalapi.Session()
        token_type = getOptionValue(f"{plugin_name}tokentype")
        access_token : str = getOptionValue(f"{plugin_name}accesstoken")
        refresh_token : str = getOptionValue(f"{plugin_name}refreshtoken")
        expiry_time_timestamp_str : str = getOptionValue(f"{plugin_name}expirytime")
        expiry_time_timestamp : float = float(expiry_time_timestamp_str)
        expiry_time = datetime.fromtimestamp(expiry_time_timestamp)
        audio_quality : tidalapi.Quality = get_audio_quality(getOptionValue(f"{plugin_name}audioquality"))
        res : bool = new_session.load_oauth_session(token_type, access_token, refresh_token, expiry_time)
        new_session.audio_quality = audio_quality
        msgproc.log(f"Tidal session created: [{res}]")
        session = new_session
    else: res = True
    return res

def get_session() -> tidalapi.Session:
    global session
    if not create_session():
        msgproc.log("Cannot create Tidal session")
    else:
        return session

def build_intermediate_url(track : tidalapi.media.Track) -> str:
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
    trackid = xbmcplug.trackid_from_urlpath(upmpd_pathprefix, a)
    url = build_streaming_url(trackid) or ""
    return {'media_url' : url}

def _returnentries(entries):
    """Helper function: build plugin browse or search return value from items list"""
    return {"entries" : json.dumps(entries), "nocache" : "0"}

def _objidtopath(objid):
    if objid.find(_g_myprefix) != 0:
        raise Exception(f"subsonic: bad objid {objid}: bad prefix")
    return objid[len(_g_myprefix):].lstrip("/")

def category_to_entry(
        objid, 
        category : tidalapi.page.ItemList) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.CATEGORY.getName(), 
        category.title)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        category.title)
    return entry

def get_option(options : dict[str, any], option_key : OptionKey) -> any:
    return options[option_key.get_name()] if option_key.get_name() in options else option_key.get_default_value()

def set_option(options : dict[str, any], option_key : OptionKey, option_value : any) -> None:
    options[option_key.get_name()] = option_value

def get_album_track_num(track : tidalapi.media.Track) -> str:
    if is_multidisc_album(track.album):
        return f"{track.volume_num}.{track.track_num:02}"
    else:
        return track.track_num

def track_apply_explicit(track : tidalapi.media.Track, current_title : str = None, options : dict[str, any] = {}) -> str:
    title : str = current_title if current_title else track.name
    if track.explicit:
        title : str = f"{title} [Explicit]"
    return title

def get_track_name_for_track_container(
        track: tidalapi.media.Track,
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
        track: tidalapi.media.Track,
        options : dict[str, any] = {}) -> dict:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.MIX_NAVIGABLE_ITEM.getName(), 
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
    track_entry = direntry(id,
        objid,
        title)
    album_art_uri = get_image_url(track.album)
    upnp_util.set_album_art_from_uri(album_art_uri, track_entry)
    return track_entry

# Possibly the same #1 occ #2
def track_to_navigable_playlist_item(
        objid, 
        track: tidalapi.media.Track,
        options : dict[str, any] = {}) -> dict:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.PLAYLIST_NAVIGABLE_ITEM.getName(), 
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
    track_entry = direntry(id,
        objid,
        title)
    album_art_uri = get_image_url(track.album)
    upnp_util.set_album_art_from_uri(album_art_uri, track_entry)
    return track_entry

def track_to_track_container(
        objid, 
        track: tidalapi.media.Track,
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
    track_entry = direntry(id,
        objid,
        title)
    upnp_util.set_album_art_from_uri(get_image_url(track.album), track_entry)
    return track_entry

def get_mime_type(track : tidalapi.media.Track) -> str:
    if is_mp3(track.audio_quality):
        return "audio/mp3"
    else:
        return "audio/flac"

def track_to_entry(
        objid, 
        track: tidalapi.media.Track,
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
        option_key = OptionKey.SKIP_TRACK_ARTIST)
    if not skip_art:
        art_uri : str = get_option(
            options = options,
            option_key = OptionKey.OVERRIDDEN_ART_URI)
        if not art_uri: art_uri = get_image_url(track.album)
        upnp_util.set_album_art_from_uri(art_uri, entry)
    entry['duration'] = str(track.duration)
    return entry

def artist_to_entry(
        objid,
        artist : tidalapi.artist.Artist) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(), 
        artist.id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        title = artist.name)
    art_uri = get_image_url(artist)
    upnp_util.set_class_artist(entry)
    upnp_util.set_album_art_from_uri(art_uri, entry)
    return entry

def album_to_album_container(
        objid,
        album : tidalapi.album.Album) -> direntry:
    options : dict[str, any] = dict()
    set_option(
        options = options,
        option_key = OptionKey.ENTRY_AS_CONTAINER,
        option_value = True)
    return album_to_entry(
        objid = objid,
        album = album,
        options = options)

def album_to_entry(
        objid,
        album : tidalapi.album.Album,
        options : dict[str, any] = {}) -> direntry:
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
    entry = direntry(id, 
        objid, 
        title = album_title,
        artist = album.artist.name)
    upnp_util.set_class_album(entry)
    upnp_util.set_album_art_from_uri(get_image_url(album), entry)
    return entry

def pagelink_to_entry(
        objid,
        category : tidalapi.page.ItemList,
        page_link : tidalapi.page.PageLink,
        page_list : list[str] = list()) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.PAGELINK.getName(), 
        page_link.title)
    identifier.set(ItemIdentifierKey.CATEGORY_TITLE, category.title)
    identifier.set(ItemIdentifierKey.PAGE_LIST, page_list)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        title = page_link.title)
    return entry

def playlist_to_playlist_container(
        objid,
        playlist : tidalapi.playlist.Playlist) -> direntry:
    return raw_playlist_to_entry(
        objid = objid,
        playlist = playlist,
        element_type = ElementType.PLAYLIST_CONTAINER)

def playlist_to_entry(
        objid,
        playlist : tidalapi.playlist.Playlist) -> direntry:
    return raw_playlist_to_entry(
        objid = objid,
        playlist = playlist,
        element_type = ElementType.PLAYLIST)

def raw_playlist_to_entry(
        objid,
        playlist : tidalapi.playlist.Playlist,
        element_type : ElementType = ElementType.PLAYLIST) -> direntry:
    identifier : ItemIdentifier = ItemIdentifier(
        element_type.getName(), 
        playlist.id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        title = playlist.name)
    upnp_util.set_album_art_from_uri(get_image_url(playlist), entry)
    return entry

def mix_to_entry(
        objid,
        mix : tidalapi.mix.Mix) -> direntry:
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
        mix : tidalapi.mix.Mix) -> direntry:
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
        mix : tidalapi.mix.Mix,
        options : dict[str, any] = {}) -> direntry:
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
    entry = direntry(id, 
        objid, 
        title = mix.title)
    art_uri = get_image_url(mix)
    upnp_util.set_album_art_from_uri(art_uri, entry)
    return entry

def get_categories() -> list[tidalapi.page.ItemList]:
    session : tidalapi.Session = get_session()
    home = session.home()
    home.categories.extend(session.explore().categories)
    #home.categories.extend(session.videos().categories)
    return home.categories

def get_category(category_name : str):
    categories : list[tidalapi.page.ItemList] = get_categories()
    for current in categories:
        if current.title == category_name: return current
    
def handler_tag_favorite_albums(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    items : list[tidalapi.album.Album] = get_session().user.favorites.albums(limit = max_items, offset = offset)
    current : tidalapi.album.Album
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
    items : list[tidalapi.artist.Artist] = get_session().user.favorites.artists(limit = max_items, offset = offset)
    current : tidalapi.artist.Artist
    for current in items:
        entries.append(artist_to_entry(objid, artist = current))
    if len(items) >= max_items:
        create_next_button(
            objid = objid, 
            element_type = ElementType.TAG, 
            element_id = TagType.FAVORITE_ARTISTS.getTagName(),
            next_offset = offset + max_items)
    return entries

def handler_tag_all_playlists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    playlists : list[tidalapi.playlist.PlayList] = get_session().user.playlist_and_favorite_playlists(offset = offset)
    current : tidalapi.playlist.Playlist
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
    playlists : list[tidalapi.playlist.PlayList] = get_session().user.playlists()
    current : tidalapi.playlist.Playlist
    for current in playlists:
        entries.append(playlist_to_playlist_container(
            objid = objid, 
            playlist = current))
    return entries

def handler_tag_categories(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    current : tidalapi.page.ItemList
    category_index : int = 0
    for current in get_categories():
        msgproc.log(f"Found category[{category_index}] [{current.title}] typeof(title) is [{type(current.title)}]")
        title : str = current.title
        if title and len(title) > 0:
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
    next_entry : dict = direntry(
        next_id, 
        objid, 
        title = "Next")
    return next_entry

def handler_element_mix(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    mix_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    mix : tidalapi.mix.Mix = get_session().mix(mix_id)
    tracks : list[tidalapi.media.Track] = mix.items()
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

def get_genres() -> list[tidalapi.genre.Genre]:
    return get_session().genre.get_genres()

def get_genre(genre_name : str) -> tidalapi.genre.Genre:
    genres_list : list[tidalapi.genre.Genre] = get_session().genre.get_genres()
    selected : tidalapi.genre.Genre
    for selected in genres_list:
        msgproc.log(f"get_genre inspecting [{selected.name}] path [{selected.path}]")
        if selected.name in genre_name:
            return selected

def navigate(category_name : str, page_list : list[str] = list()):
    category : tidalapi.page.ItemList = get_category(category_name = category_name)
    if not category: return None
    result = category
    current_page : str
    for current_page in page_list:
        msgproc.log(f"navigate searching {current_page}")
        if not result: return None
        current_item : tidalapi.page.PageLink
        for current_item in result.items:
            msgproc.log(f"navigate searching {current_page} current_item {current_item.title}, looking for {current_page}")
            if current_page == current_item.title:
                result = current_item
                break            
    return result

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
    page : tidalapi.page.Page = selected_pagelink.get()
    if not page: 
        msgproc.log(f"handler_element_pagelink page not found")
        return entries
    if page: page_to_entries(objid, page, entries)
    return entries

def page_to_entries(objid, page : tidalapi.page.Page, entries : list) -> list:
    # extracting items from page
    for current_page_item in page:
        entry : dict = convert_pageitem_to_entry(objid, page_item = current_page_item)
        if entry: entries.append(entry)
    return entries

def convert_pageitem_to_entry(objid, page_item : tidalapi.page.PageItem) -> dict:
    msgproc.log(f"convert_pageitem_to_entry processing a {type(page_item)}")
    if isinstance(page_item, tidalapi.playlist.Playlist):
        return playlist_to_playlist_container(
            objid = objid, 
            playlist = page_item)
    elif isinstance(page_item, tidalapi.album.Album):
        return album_to_album_container(
            objid = objid, 
            album = page_item)
    elif isinstance(page_item, tidalapi.artist.Artist):
        return artist_to_entry(objid, artist = page_item)
    elif isinstance(page_item, tidalapi.page.FeaturedItems):
        msgproc.log(f"Item of type (FeaturedItems) {type(page_item)} not handled")
        return None
    msgproc.log(f"Item of type {type(page_item)} not handled")
    return None

def handler_element_mix_container(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    mix_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    mix : tidalapi.playlist.Playlist = get_session().mix(mix_id)
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
        entry = direntry(id, 
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
    album : tidalapi.album.Album = get_session().album(album_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM.getName(), 
        album_id)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry = direntry(id, 
        objid, 
        "Album")
    upnp_util.set_album_art_from_uri(get_image_url(album), entry)
    entries.append(entry)
    # add Artists
    artist_list : list[tidalapi.artist.Artist] = get_artist_list(album.artist, album.artists)
    for current in artist_list:
        artist : tidalapi.artist.Artist = get_session().artist(current.id)
        entries.append(artist_to_entry(objid = objid, artist = artist))
    return entries

def handler_element_playlist_container(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    playlist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    playlist : tidalapi.playlist.Playlist = get_session().playlist(playlist_id)
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
        entry = direntry(id, 
            objid, 
            current_tuple[1])
        upnp_util.set_album_art_from_uri(get_image_url(playlist), entry)
        entries.append(entry)
    return entries

def get_artist_list(
        artist : tidalapi.artist.Artist, 
        artists : list[tidalapi.artist.Artist]) -> list[tidalapi.artist.Artist]:
    result : list[tidalapi.artist.Artist] = list()
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
    return handler_element_mix_or_playlist_navigable_item(
        objid = objid, 
        item_identifier = item_identifier,
        entries = entries)

def handler_element_playlist_navigable_item(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    return handler_element_mix_or_playlist_navigable_item(
        objid = objid, 
        item_identifier = item_identifier,
        entries = entries)

def handler_element_mix_or_playlist_navigable_item(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    track_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    track : tidalapi.media.Track = get_session().track(track_id)
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
    artist_list : list[tidalapi.artist.Artist] = get_artist_list(track.artist, track.artists)
    for current in artist_list:
        artist : tidalapi.artist.Artist = get_session().artist(current.id)
        entries.append(artist_to_entry(
            objid = objid, 
            artist = artist))
    # add link to album
    if track.album and track.album.id:
        album : tidalapi.album.Album = get_session().album(track.album.id)
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
    mix : tidalapi.mix.Mix = get_session().mix(mix_id)
    tracks : list[tidalapi.media.Track] = mix.items()
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
    playlist : tidalapi.playlist.Playlist = get_session().playlist(playlist_id)
    tracks : list[tidalapi.media.Track] = playlist.tracks()
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
    playlist : tidalapi.playlist.Playlist = get_session().playlist(playlist_id)
    tracks : list[tidalapi.media.Track] = playlist.tracks()
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

def is_multidisc_album(album : tidalapi.album.Album) -> bool:
    return album.num_volumes and album.num_volumes > 1

def handler_element_album(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    album_id : int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    album : tidalapi.album.Album = get_session().album(album_id)
    is_multidisc : bool = is_multidisc_album(album)
    msgproc.log(f"Album {album_id} is multidisc {is_multidisc}")
    tracks : list[tidalapi.media.Track] = album.tracks()
    options : dict[str, any] = {}
    set_option(options, OptionKey.SKIP_TRACK_ARTIST, True)
    track_num : int = 1 
    track : tidalapi.media.Track
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
        album_extractor : Callable[[], list[tidalapi.album.Album]], 
        entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : tidalapi.artist.Artist = get_session().artist(artist_id)
    if not artist: msgproc.log(f"Artist with id {artist_id} not found")
    current : tidalapi.album.Album
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

def get_similar_artists(artist : tidalapi.artist.Artist) -> list[tidalapi.artist.Artist]:
    try:
        return artist.get_similar()
    except Exception as ex:
        msgproc.log(f"Cannot get similar artists for artist id [{artist.id}] name [{artist.name}] Exception [{ex}]")
    return list()

def handler_element_similar_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : tidalapi.artist.Artist = get_session().artist(artist_id)
    items : list[tidalapi.artist.Artist] = get_similar_artists(artist)
    current : tidalapi.artist.Artist
    for current in items if items else list():
        entries.append(artist_to_entry(objid = objid, artist = current))
    return entries

def handler_element_artist(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    artist : tidalapi.artist.Artist = get_session().artist(artist_id)
    if not artist: msgproc.log(f"Artist with id {artist_id} not found")
    album_tuple_array = [
        (ElementType.ARTIST_ALBUM_ALBUMS, "Albums"), 
        (ElementType.ARTIST_ALBUM_EP_SINGLES, "EP and Singles"),
        (ElementType.ARTIST_ALBUM_OTHERS, "Other Albums"),
        (ElementType.SIMILAR_ARTISTS, "Similar Artists")]
    for album_tuple in album_tuple_array:
        identifier : ItemIdentifier = ItemIdentifier(
            album_tuple[0].getName(), 
            artist_id)
        id : str = identifier_util.create_objid(
            objid = objid, 
            id = identifier_util.create_id_from_identifier(identifier))
        entry = direntry(id, 
            objid, 
            album_tuple[1])
        upnp_util.set_album_art_from_uri(get_image_url(artist), entry)
        entries.append(entry)
    return entries

def handler_element_track_container(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    track_id : int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    track : tidalapi.media.Track = get_session().track(track_id)
    track_entry = track_to_entry(
        objid = objid, 
        track = track)
    entries.append(track_entry)
    return entries

def handler_element_category(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    select_category : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    category : tidalapi.page.ItemList = get_category(select_category)
    if category:
        for item in category.items:
            if isinstance(item, tidalapi.page.PageItem):
                msgproc.log(f"PageItem (Category {category.title}) Item type {type(item)} [{item}]")
                obj = get_category(select_category)
                if obj and isinstance(obj, tidalapi.page.FeaturedItems):
                    msgproc.log(f"Processing category {select_category} as {type(obj)}")
                    featured_items : tidalapi.page.FeaturedItems = obj
                    for fi_item in featured_items.items:
                        msgproc.log(f"Processing category {select_category} as {type(obj)} Item type {fi_item.type}")
                        if fi_item.type == "PLAYLIST":
                            playlist : tidalapi.playlist.Playlist = get_session().playlist(fi_item.artifact_id)
                            entries.append(playlist_to_playlist_container(
                                objid = objid, 
                                playlist = playlist))
                        else:
                            msgproc.log(f"Not processed Item type {fi_item.type}")
            elif isinstance(item, tidalapi.page.PageLink):
                msgproc.log(f"PageLink (Category {category.title}) Item type {type(item)} [{item}]")
                entries.append(pagelink_to_entry(objid, category = category, page_link = item))
            elif isinstance(item, tidalapi.mix.Mix):
                msgproc.log(f"Mix - Item type {type(item)} [{item}]")
                entries.append(mix_to_mix_container(objid, mix = item))
            elif isinstance(item, tidalapi.media.Track):
                msgproc.log(f"Track - Item type {type(item)} [{item}]")
                options : dict[str, any] = dict()
                set_option(options, OptionKey.SKIP_TRACK_NUMBER, True)
                entries.append(track_to_track_container(
                    objid = objid, 
                    track = item,
                    options = options))
            elif isinstance(item, tidalapi.playlist.Playlist):
                msgproc.log(f"Playlist - Item type {type(item)} [{item}]")
                entries.append(playlist_to_playlist_container(
                    objid = objid, 
                    playlist = item))
            elif isinstance(item, tidalapi.album.Album):
                album : tidalapi.album.Album = item
                msgproc.log(f"Album [{album.name}] [{item}]")
                options : dict[str, any] = dict()
                entries.append(album_to_album_container(objid, album = album))
            else:
                msgproc.log(f"UNHANDLED - Item type {type(item)} [{item}]")
    return entries

# this allows kodi to work with the plugin
def track_data_to_entry(objid, entry_id : str, track : tidalapi.media.Track) -> dict:
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
    art_url : str = get_image_url(track.album)
    upnp_util.set_album_art_from_uri(art_url, entry)
    entry['duration'] = str(track.duration)
    return entry

def _handler_element_track(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    track_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"_handler_element_track should serve track_id {track_id}")
    track : tidalapi.media.Track = get_session().track(track_id)
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), track_id)
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    track_entry : dict = track_data_to_entry(objid, id, track)
    entries.append(track_entry)
    return entries

__tag_action_dict : dict = {
    TagType.CATEGORIES.getTagName(): handler_tag_categories,
    TagType.MY_PLAYLISTS.getTagName(): handler_tag_my_playlists,
    TagType.ALL_PLAYLISTS.getTagName(): handler_tag_all_playlists,
    TagType.FAVORITE_ALBUMS.getTagName(): handler_tag_favorite_albums,
    TagType.FAVORITE_ARTISTS.getTagName(): handler_tag_favorite_artists
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
    ElementType.ARTIST.getName(): handler_element_artist,
    ElementType.ARTIST_ALBUM_ALBUMS.getName(): handler_element_artist_album_albums,
    ElementType.ARTIST_ALBUM_EP_SINGLES.getName(): handler_element_artist_album_ep_singles,
    ElementType.ARTIST_ALBUM_OTHERS.getName(): handler_element_artist_album_others,
    ElementType.TRACK_CONTAINER.getName(): handler_element_track_container,
    ElementType.TRACK.getName(): _handler_element_track,
    ElementType.SIMILAR_ARTISTS.getName(): handler_element_similar_artists
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
    entry : dict = direntry(
        id = id, 
        pid = objid, 
        title = get_tag_Type_by_name(tag.getTagName()).getTagTitle())
    return entry

def _show_tags(objid, entries : list) -> list:
    for tag in TagType:
        entries.append(tag_to_entry(objid, tag))
    return entries

@dispatcher.record('browse')
def browse(a):
    msgproc.log(f"browse: args: --{a}--")
    _inittidal()
    if 'objid' not in a: raise Exception("No objid in args")
    objid = a['objid']
    path = htmlunescape(_objidtopath(objid))
    msgproc.log(f"browse: path: --{path}--")
    path_list : list[str] = objid.split("/")
    curr_path : str
    for curr_path in path_list:
        if not _g_myprefix == curr_path:
            msgproc.log(f"browse: path: [{curr_path}] decodes to {codec.decode(curr_path)}")
    last_path_item : str = path_list[len(path_list) - 1] if path_list and len(path_list) > 0 else None
    msgproc.log(f"browse: path_list: --{path_list}-- last: --{last_path_item}--")
    entries = []
    if len(path_list) == 1 and _g_myprefix == last_path_item:
        # show tags
        entries = _show_tags(objid, entries)
    else:
        # decode
        decoded_path : str = codec.decode(last_path_item)
        item_dict : dict[str, any] = json.loads(decoded_path)
        item_identifier : ItemIdentifier = ItemIdentifier.from_dict(item_dict)
        thing_name : str = item_identifier.get(ItemIdentifierKey.THING_NAME)
        thing_value : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
        msgproc.log(f"browse: item_identifier name: --{thing_name}-- value: --{thing_value}--")
        if ElementType.TAG.getName() == thing_name:
            msgproc.log(f"browse: should serve tag: --{thing_value}--")
            tag_handler = __tag_action_dict[thing_value] if thing_value in __tag_action_dict else None
            if tag_handler:
                msgproc.log(f"browse: found tag handler for: --{thing_value}--")
                entries = tag_handler(objid, item_identifier, entries)
                return _returnentries(entries)
            else:
                msgproc.log(f"browse: tag handler for: --{thing_value}-- not found")
        else: # it's an element
            msgproc.log(f"browse: should serve element: --{thing_name}-- [{thing_value}]")
            elem_handler = __elem_action_dict[thing_name] if thing_name in __elem_action_dict else None
            if elem_handler:
                msgproc.log(f"browse: found elem handler for: --{thing_name}--")
                entries = elem_handler(objid, item_identifier, entries)
            else:
                msgproc.log(f"browse: element handler for: --{thing_name}-- not found")
    return _returnentries(entries)

def tidal_search(
        search_type : search_type.SearchType,
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

    if search_type.SearchType.ALBUM.get_name() == objkind:
        # search albums by specified value
        item_list : list[tidalapi.album.Album] = tidal_search(search_type.SearchType.ALBUM, value)
        resultset_length = len(item_list) if item_list else 0
        for item in item_list:
            entries.append(album_to_album_container(
                objid = objid, 
                album = item))
    elif search_type.SearchType.TRACK.get_name() == objkind:
        # search tracks by specified value
        item_list : list[tidalapi.media.Track] = tidal_search(search_type.SearchType.TRACK, value)
        resultset_length = len(item_list) if item_list else 0
        options : dict[str, any] = dict()
        set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
        for item in item_list:
            entries.append(track_to_entry(
                objid = objid, 
                track = item, 
                options = options))
    elif search_type.SearchType.ARTIST.get_name() == objkind:
        # search artists by specified value
        item_list : list[tidalapi.artist.Artist] = tidal_search(search_type.SearchType.ARTIST, value)
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
    _g_init = create_session()
    return True

msgproc.mainloop()
