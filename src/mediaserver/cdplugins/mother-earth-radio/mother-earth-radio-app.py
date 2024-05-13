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
import os

from typing import Callable

import html
import cmdtalkplugin
import upmplgutils

import codec
import identifier_util
import radio_stations
import upnp_util

from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey
from tag_type import TagType, get_tag_type_by_name
from element_type import ElementType

from radio_station_entry import RadioStationEntry

import constants

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = f"0${constants.plugin_name}$"
upmplgutils.setidprefix(constants.plugin_name)

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

# Possible once initialisation. Always called by browse() or search(), should remember if it has
# something to do (e.g. the _g_init thing, but this could be something else).
_g_init = False
def _init_mother_earth_radio():
    global _g_init
    if _g_init:
        return True

    # Do whatever is needed here
    msgproc.log(f"Mother Earth Radio Plugin Release {constants.plugin_version}")

    _g_init = True
    return True

def build_intermediate_url(rp_id : int) -> str:
    http_host_port = os.environ["UPMPD_HTTPHOSTPORT"]
    url = f"http://{http_host_port}/{constants.plugin_name}/track/version/1/trackId/{str(rp_id)}"
    msgproc.log(f"intermediate_url for rp_id {rp_id} -> [{url}]")
    return url

def build_streaming_url(station_id : str) -> str:
    current : RadioStationEntry
    for current in radio_stations.radio_station_list:
        msgproc.log(f"build_streaming_url current.id: [{current.id}] station_id [{station_id}] [{type(station_id)}]")
        if str(current.id) == station_id:
            msgproc.log(f"build_streaming_url for station_id: [{station_id}] -> [{current.url}]")
            return current.url
    msgproc.log(f"build_streaming_url not found for station_id: [{station_id}]")
    return None

@dispatcher.record('trackuri')
def trackuri(a):
    upmpd_pathprefix = os.environ["UPMPD_PATHPREFIX"]
    msgproc.log(f"UPMPD_PATHPREFIX: [{upmpd_pathprefix}] trackuri: [{a}]")
    rp_id = upmplgutils.trackid_from_urlpath(upmpd_pathprefix, a)
    url = build_streaming_url(rp_id) or ""
    msgproc.log(f"intermediate_url for rp_id {rp_id} -> [{url}]")
    return {'media_url' : url}

def _returnentries(entries):
    """Helper function: build plugin browse or search return value from items list"""
    return {"entries" : json.dumps(entries), "nocache" : "0"}

def _objidtopath(objid):
    if objid.find(_g_myprefix) != 0:
        raise Exception(f"subsonic: bad objid {objid}: bad prefix")
    return objid[len(_g_myprefix):].lstrip("/")

def radio_entry_data_to_entry(objid, entry_id : str, radio_station_entry : RadioStationEntry) -> dict:
    entry : dict = {}
    entry['id'] = entry_id
    entry['pid'] = radio_station_entry.id
    entry['tp']= 'it'
    entry['uri'] = build_intermediate_url(radio_station_entry.id)
    upnp_util.set_class('object.item.audioItem.audioBroadcast', entry)
    title : str = f"{radio_station_entry.title} [{radio_station_entry.codec}]"
    upnp_util.set_album_title(title, entry)
    upnp_util.set_artist(radio_station_entry.title, entry)
    entry['upnp:album'] = radio_station_entry.codec
    entry['res:mime'] = radio_station_entry.mimetype
    upnp_util.set_bit_depth(radio_station_entry.bit_depth, entry)
    upnp_util.set_sample_rate(radio_station_entry.sampling_rate, entry)
    upnp_util.set_channel_count(radio_station_entry.channel_count, entry)
    upnp_util.set_bit_rate(
        upnp_util.calc_bitrate(
            radio_station_entry.channel_count,
            radio_station_entry.bit_depth,
            radio_station_entry.sampling_rate),
        entry)
    return entry

def radio_station_to_entry(objid, radio_station_entry : RadioStationEntry) -> dict:
    identifier : ItemIdentifier = ItemIdentifier(ElementType.RADIO_ENTRY.getName(), str(radio_station_entry.id))
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    return radio_entry_data_to_entry(objid = objid, entry_id = id, radio_station_entry = radio_station_entry)

def get_radio_by_id(radio_id : str) -> RadioStationEntry:
    current : RadioStationEntry
    for current in radio_stations.radio_station_list:
        if radio_id == str(current.id): return current
    return None

def handler_tag_by_something(
        objid, 
        thing_extractor : Callable[[RadioStationEntry], str],
        element_to_be_created : ElementType,
        entries : list) -> list:
    thing_set : set[str] = set()
    current : RadioStationEntry
    for current in radio_stations.radio_station_list:
        curr_thing : str = thing_extractor(current)
        if not curr_thing in thing_set:
            # add entry
            identifier : ItemIdentifier = ItemIdentifier(element_to_be_created.getName(), curr_thing)
            id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
            entry : dict = upmplgutils.direntry(
                id = id, 
                pid = objid, 
                title = curr_thing)
            entries.append(entry)
            # store in set
            thing_set.add(curr_thing)
    return entries

def handler_tag_by_codec(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    thing_extractor : Callable[[RadioStationEntry], str] = lambda x : x.codec
    return handler_tag_by_something(
        objid = objid,
        thing_extractor = thing_extractor,
        element_to_be_created = ElementType.ENTRY_BY_CODEC,
        entries = entries)

def handler_tag_by_name(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    thing_extractor : Callable[[RadioStationEntry], str] = lambda x : x.title
    return handler_tag_by_something(
        objid = objid,
        thing_extractor = thing_extractor,
        element_to_be_created = ElementType.ENTRY_BY_TITLE,
        entries = entries)

def handler_tag_all_streams(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    current : RadioStationEntry
    for current in radio_stations.radio_station_list:
        entries.append(radio_station_to_entry(objid, current))
    return entries

def handler_element_by_something(
        objid, 
        selected : str, 
        thing_extractor : Callable[[RadioStationEntry], str],
        entries : list) -> list:
    current : RadioStationEntry
    for current in radio_stations.radio_station_list:
        if thing_extractor(current) == selected:
            entries.append(radio_station_to_entry(objid, current))
    return entries

def handler_element_by_title(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    select_thing : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    thing_extractor : Callable[[RadioStationEntry], str] = lambda x : x.title
    return handler_element_by_something(objid = objid, selected = select_thing, thing_extractor = thing_extractor, entries = entries)

def handler_element_by_codec(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    select_thing : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    thing_extractor : Callable[[RadioStationEntry], str] = lambda x : x.codec
    return handler_element_by_something(objid = objid, selected = select_thing, thing_extractor = thing_extractor, entries = entries)

def handler_element_radio_entry(
        objid, 
        item_identifier : ItemIdentifier, 
        entries : list) -> list:
    radio_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    msgproc.log(f"handler_element_radio_entry radio_id {radio_id}")
    radio_entry : RadioStationEntry = get_radio_by_id(radio_id)
    msgproc.log(f"handler_element_radio_entry radio_entry found [{'yes' if radio_entry else 'no'}]")
    if not radio_entry: return entries
    identifier : ItemIdentifier = ItemIdentifier(ElementType.RADIO_ENTRY.getName(), radio_id)
    id : str = identifier_util.create_objid(objid, identifier_util.create_id_from_identifier(identifier))
    track_entry : dict = radio_entry_data_to_entry(objid, id, radio_entry)
    entries.append(track_entry)
    return entries

__tag_action_dict : dict = {
    TagType.ALL_STREAMS.getTagName(): handler_tag_all_streams,
    TagType.BY_CODEC.getTagName(): handler_tag_by_codec,
    TagType.BY_TITLE.getTagName(): handler_tag_by_name,
}

__elem_action_dict : dict = {
    ElementType.ENTRY_BY_TITLE.getName(): handler_element_by_title,
    ElementType.ENTRY_BY_CODEC.getName(): handler_element_by_codec,
    ElementType.RADIO_ENTRY.getName(): handler_element_radio_entry
}

def tag_to_entry(objid, tag : TagType) -> dict[str, any]:
    tagname : str = tag.getTagName()
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TAG.getName(), tagname)
    id : str = identifier_util.create_objid(
        objid = objid, 
        id = identifier_util.create_id_from_identifier(identifier))
    entry : dict = upmplgutils.direntry(
        id = id, 
        pid = objid, 
        title = get_tag_type_by_name(tag.getTagName()).getTagTitle())
    return entry

def show_tags(objid, entries : list) -> list:
    for tag in TagType:
        tag_entry : dict[str, any] = tag_to_entry(objid, tag)
        entries.append(tag_entry)
    return entries

@dispatcher.record('browse')
def browse(a):
    msgproc.log(f"browse: args: --{a}--")
    _init_mother_earth_radio()
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


@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    _init_mother_earth_radio()
    objid = a["objid"]
    entries = []

    # Run the search and build a list of entries in the expected format. See for example
    # ../radio-browser/radiotoentry for an example
    
    # msgproc.log(f"browse: returning --{entries}--")
    return _returnentries(entries)


msgproc.mainloop()
