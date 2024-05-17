#!/usr/bin/python3

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

import json
import os
import datetime
import time
import random
import secrets

from typing import Callable
from typing import Optional
from pathlib import Path

import cmdtalkplugin
import upmplgutils
import html

import codec
import identifier_util
import upnp_util
import constants
import config
import persistence
import tidal_util

from tag_type import TagType
from tag_type import get_tag_Type_by_name
from element_type import ElementType
from element_type import get_element_type_by_name
from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey
from option_key import OptionKey
from search_type import SearchType
from tile_type import TileType
from context import Context
from context_key import ContextKey

from tidalapi import Quality as TidalQuality
from tidalapi.session import Session as TidalSession
from tidalapi.album import Album as TidalAlbum
from tidalapi.artist import Artist as TidalArtist
from tidalapi.mix import Mix as TidalMix
from tidalapi.playlist import Playlist as TidalPlaylist
from tidalapi.playlist import UserPlaylist as TidalUserPlaylist
from tidalapi.media import Track as TidalTrack
from tidalapi.media import Video as TidalVideo
from tidalapi.page import Page as TidalPage
from tidalapi.page import PageItem as TidalPageItem
from tidalapi.page import ItemList as TidalItemList
from tidalapi.page import PageLink as TidalPageLink
from tidalapi.page import FeaturedItems as TidalFeaturedItems

from track_adapter import TrackAdapter
from tidal_track_adapter import TidalTrackAdapter
from played_track_adapter import PlayedTrackAdapter

from played_track import PlayedTrack
from played_album import PlayedAlbum
from played_track_request import PlayedTrackRequest
from tile_image import TileImage

from album_sort_criteria import AlbumSortCriteria
from artist_sort_criteria import ArtistSortCriteria

from functools import cmp_to_key

from authentication import AuthenticationType
from authentication import convert_authentication_type
from streaming_info import StreamingInfo

__tidal_plugin_release : str = constants.tidal_plugin_release


class ChangeHistoryEntry:

    def __init__(self, version: str, short_date : str, description : str):
        self.version = version
        self.short_date = short_date
        self.description = description

    @property
    def version(self) -> str:
        return self.__version

    @version.setter
    def version(self, v: str):
        self.__version : str = v

    @property
    def short_date(self) -> str:
        return self.__short_date

    @short_date.setter
    def short_date(self, v: str):
        self.__short_date : str = v

    @property
    def description(self) -> str:
        return self.__description

    @description.setter
    def description(self, v: str):
        self.__description : str = v


__change_history : list[ChangeHistoryEntry] = [
    ChangeHistoryEntry("0.3.0", "2024-04-20", "Tidal Hi-Res support"),
    ChangeHistoryEntry("0.2.1", "2024-01-23", "Calls to choose_track_adapter were missing the tidal session argument")
]

plugin_name : str = constants.plugin_name


class SessionStatus:

    def __init__(self, tidal_session : TidalSession):
        self.update(tidal_session)

    @property
    def tidal_session(self) -> TidalSession:
        return self._tidal_session

    @property
    def update_time(self) -> datetime.datetime:
        return self._update_time

    def update(self, tidal_session : TidalSession):
        self._tidal_session : TidalSession = tidal_session
        self._update_time : datetime.datetime = datetime.datetime.now()


credentials_dict : dict[str, str] = None
session_status : SessionStatus = None

# Prefix for object Ids. This must be consistent with what contentdirectory.cxx does
_g_myprefix = f"0${plugin_name}$"
upmplgutils.setidprefix(plugin_name)

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


def album_retriever(tidal_session : TidalSession, album_id : str) -> TidalAlbum:
    return tidal_session.album(album_id)


def instance_tidal_track_adapter(
        tidal_session : TidalSession,
        track : TidalTrack) -> TidalTrackAdapter:
    return TidalTrackAdapter(
        tidal_session = tidal_session,
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


def get_bit_depth_by_config_quality() -> int:
    return 24 if config.max_audio_quality in [TidalQuality.hi_res, TidalQuality.hi_res_lossless] else 16


def mp3_only() -> bool:
    q : TidalQuality = config.max_audio_quality
    return tidal_util.is_mp3(q)


def __get_credentials_file_name() -> str:
    return os.path.join(upmplgutils.getcachedir(constants.plugin_name), constants.credentials_file_name)


def __get_pkce_credentials_file_name() -> str:
    return os.path.join(upmplgutils.getcachedir(constants.plugin_name), constants.pkce_credentials_file_name)


def load_json(file_name : str):
    try:
        with open(file_name, 'r') as cred_file:
            json_dict = json.load(cred_file)
        msgproc.log(f"Loaded: [{file_name}]")
        return json_dict
    except Exception as ex:
        msgproc.log(f"Error loading configuration from file [{file_name}]: [{ex}]")


def get_from_pkce_dict(pkce_dict : dict[str, any], key : str) -> any:
    key_dict : dict[str, any] = pkce_dict[key] if key in pkce_dict else None
    return key_dict["data"] if key_dict and "data" in key_dict else None


def get_credentials_from_config_or_files() -> dict[str, str]:
    # pkce file first, static next, then challenge
    oauth2_static_loaded : bool = False
    pkce_static_loaded : bool = False
    res_dict : dict[str, str] = dict()
    if os.path.exists(__get_pkce_credentials_file_name()):
        msgproc.log("get_credentials_from_config_or_files pkce file available, using it")
        res_dict[constants.key_authentication_type] = AuthenticationType.PKCE.auth_type
        res_dict[constants.key_file_available] = True
        # READ contents of file
        pkce_json_dict : dict[str, any] = load_json(__get_pkce_credentials_file_name())
        # check pkce credentials are here
        file_pkce_token_type : str = get_from_pkce_dict(pkce_json_dict, constants.key_pkce_token_type_json)
        file_pkce_access_token : str = get_from_pkce_dict(pkce_json_dict, constants.key_pkce_access_token_json)
        file_pkce_refresh_token : str = get_from_pkce_dict(pkce_json_dict, constants.key_pkce_refresh_token_json)
        file_pkce_session_id : str = get_from_pkce_dict(pkce_json_dict, constants.key_pkce_session_id_json)
        file_pkce_is_pkce : bool = get_from_pkce_dict(pkce_json_dict, constants.key_pkce_is_pkce_json)
        if (file_pkce_token_type
                and file_pkce_access_token
                and file_pkce_refresh_token
                and file_pkce_session_id
                and file_pkce_is_pkce):
            msgproc.log("get_credentials_from_config_or_files pkce file contains the required data ...")
            # msgproc.log(f"pkce in file token_type: [{file_pkce_token_type}]")
            # msgproc.log(f"pkce in file access_token: [{file_pkce_access_token}]")
            # msgproc.log(f"pkce in file refresh_token: [{file_pkce_refresh_token}]")
            # msgproc.log(f"pkce in file session_id: [{file_pkce_session_id}]")
            # msgproc.log(f"pkce in file is_pkce: [{file_pkce_is_pkce}]")
            # store in dict
            res_dict[constants.key_pkce_token_type] = file_pkce_token_type
            res_dict[constants.key_pkce_access_token] = file_pkce_access_token
            res_dict[constants.key_pkce_refresh_token] = file_pkce_refresh_token
            res_dict[constants.key_pkce_session_id] = file_pkce_session_id
            res_dict[constants.key_pkce_is_pkce] = file_pkce_is_pkce
        else:
            # something is wrong with the file, log and go on
            msgproc.log("get_credentials_from_config_or_files pkce file is not valid")
        # return immediately
        return res_dict
    else:
        msgproc.log("get_credentials_from_config_or_files pkce file is not available")
    conf_oauth2_token_type : str = config.getPluginOptionValue(constants.key_token_type)
    conf_oauth2_access_token : str = config.getPluginOptionValue(constants.key_access_token)
    conf_oauth2_refresh_token : str = config.getPluginOptionValue(constants.key_refresh_token)
    conf_oauth2_expiry_time_timestamp_str : str = config.getPluginOptionValue(constants.key_expiry_time)
    # do I have auth elements for oauth2? if yes, store
    if conf_oauth2_token_type and conf_oauth2_access_token:
        msgproc.log("OAUTH2 Credentials provided statically")
        oauth2_static_loaded = True
        # res_dict : dict[str, any] = dict()
        res_dict[constants.key_token_type] = conf_oauth2_token_type
        res_dict[constants.key_access_token] = conf_oauth2_access_token
        if conf_oauth2_refresh_token: res_dict[constants.key_refresh_token] = conf_oauth2_refresh_token
        if conf_oauth2_expiry_time_timestamp_str:
            res_dict[constants.key_expiry_time_timestamp_str] = conf_oauth2_expiry_time_timestamp_str
        # return res_dict
    conf_pkce_token_type : str = config.getPluginOptionValue(constants.key_pkce_token_type)
    conf_pkce_access_token : str = config.getPluginOptionValue(constants.key_pkce_access_token)
    conf_pkce_refresh_token : str = config.getPluginOptionValue(constants.key_pkce_refresh_token)
    conf_pkce_session_id : str = config.getPluginOptionValue(constants.key_pkce_session_id)
    conf_pkce_is_pkce : bool = (
        True if
        conf_pkce_token_type and
        conf_pkce_access_token and
        conf_pkce_refresh_token and
        conf_pkce_session_id
        else False)
    # do I have auth elements for pkce? if yes, store
    if conf_pkce_token_type and conf_pkce_access_token and conf_pkce_refresh_token and conf_pkce_session_id:
        msgproc.log("PKCE Credentials provided statically")
        pkce_static_loaded = True
        res_dict[constants.key_pkce_token_type] = conf_pkce_token_type
        res_dict[constants.key_pkce_access_token] = conf_pkce_access_token
        res_dict[constants.key_pkce_refresh_token] = conf_pkce_refresh_token
        res_dict[constants.key_pkce_session_id] = conf_pkce_session_id
        res_dict[constants.key_pkce_is_pkce] = conf_pkce_is_pkce
        # TODO if file does not exists, create it
    # something missing? try json files
    if not oauth2_static_loaded:
        oauth2_cred_file_name : str = __get_credentials_file_name()
        if os.path.exists(oauth2_cred_file_name):
            try:
                with open(oauth2_cred_file_name, 'r') as cred_file:
                    oauth_dict = json.load(cred_file)
                    res_dict = {**res_dict, **oauth_dict}
                msgproc.log(f"Loaded: [{oauth2_cred_file_name}]")
            except Exception as ex:
                msgproc.log(f"Error loading configuration: [{ex}]")
        else:
            msgproc.log(f"File {oauth2_cred_file_name} not found")
    if not pkce_static_loaded:
        pkce_cred_file_name : str = __get_pkce_credentials_file_name()
        if os.path.exists(pkce_cred_file_name):
            try:
                with open(pkce_cred_file_name, 'r') as cred_file:
                    pkce_dict = json.load(cred_file)
                    res_dict = {**res_dict, **pkce_dict}
                msgproc.log(f"Loaded: [{pkce_cred_file_name}]")
            except Exception as ex:
                msgproc.log(f"Error loading configuration: [{ex}]")
        else:
            msgproc.log(f"File {pkce_cred_file_name} not found")
    return res_dict


def get_cred_value(from_dict : dict[str, str], key_name : str) -> any:
    return from_dict[key_name] if from_dict and key_name in from_dict else None


def get_pkce_credentials_dict_for_json(
        pkce_token_type : str,
        pkce_access_token : str,
        pkce_refresh_token : str,
        pkce_session_id : str,
        pkce_is_pkce : bool = True) -> dict[str, str]:
    return {
        constants.key_pkce_token_type_json : {"data" : pkce_token_type},
        constants.key_pkce_access_token_json : {"data" : pkce_access_token},
        constants.key_pkce_refresh_token_json : {"data" : pkce_refresh_token},
        constants.key_pkce_session_id_json : {"data": pkce_session_id},
        constants.key_pkce_is_pkce_json : {"data": pkce_is_pkce}
    }


def get_pkce_credentials_from_config_file() -> dict[str, any]:
    pkce_token_type : str = config.getPluginOptionValue(constants.key_pkce_token_type)
    pkce_access_token : str = config.getPluginOptionValue(constants.key_pkce_access_token)
    pkce_refresh_token : str = config.getPluginOptionValue(constants.key_pkce_refresh_token)
    pkce_session_id : str = config.getPluginOptionValue(constants.key_pkce_session_id)
    pkce_is_pkce : bool = (True
        if pkce_token_type and
            pkce_access_token and
            pkce_refresh_token and
            pkce_session_id
        else False)
    # msgproc.log(f"get_pkce_credentials_from_config_file - pkce_token_type [{pkce_token_type}]")
    # msgproc.log(f"get_pkce_credentials_from_config_file - pkce_access_token [{pkce_access_token}]")
    # msgproc.log(f"get_pkce_credentials_from_config_file - pkce_refresh_token [{pkce_refresh_token}]")
    # msgproc.log(f"get_pkce_credentials_from_config_file - pkce_session_id [{pkce_session_id}]")
    # msgproc.log(f"get_pkce_credentials_from_config_file - is_pkce [{pkce_is_pkce}]")
    return ({
        constants.key_pkce_token_type: pkce_token_type,
        constants.key_pkce_access_token: pkce_access_token,
        constants.key_pkce_refresh_token: pkce_refresh_token,
        constants.key_pkce_session_id: pkce_session_id,
        constants.key_pkce_is_pkce: pkce_is_pkce
    } if pkce_is_pkce else None)


def log_mismatch_file_vs_static(what : str):
    log_mismatch(what = what, where1 = "file", where2 = "static configuration")


def log_mismatch(what : str, where1 : str, where2 : str):
    msgproc.log(f"Mismatched [{what}] between [{where1}] and [{where2}]")


def load_credentials() -> dict[str, str]:
    # best first
    cred_dict : dict[str, str] = get_credentials_from_config_or_files()
    # is there a pkce file?
    file_available : bool = (cred_dict[constants.key_file_available]
        if constants.key_file_available in cred_dict
        else False)
    if file_available:
        # authentication type must be set
        auth_type : AuthenticationType = convert_authentication_type(cred_dict[constants.key_authentication_type])
        # is pkce?
        if AuthenticationType.PKCE == auth_type:
            if not config.enable_pkce_credential_match: return cred_dict
            msgproc.log("Comparing pkce credentials from file to static configuration ...")
            # must match credentials in configuration file, if set
            pkce_cred_from_conf : dict[str, any] = get_pkce_credentials_from_config_file()
            # not set, ok to use the file
            if not pkce_cred_from_conf:
                msgproc.log("No static configuration, ok to use the pkce credentials file.")
                return cred_dict
            # if set, they must match
            conf_file_pkce_token_type : str = get_cred_value(pkce_cred_from_conf, constants.key_pkce_token_type)
            conf_file_pkce_access_token  : str = get_cred_value(pkce_cred_from_conf, constants.key_pkce_access_token)
            conf_file_pkce_refresh_token : str = get_cred_value(pkce_cred_from_conf, constants.key_pkce_refresh_token)
            conf_file_pkce_session_id : str = get_cred_value(pkce_cred_from_conf, constants.key_pkce_session_id)
            conf_file_pkce_is_pkce : str = get_cred_value(pkce_cred_from_conf, constants.key_pkce_is_pkce)
            all_match : bool = True
            if not (conf_file_pkce_token_type == get_cred_value(cred_dict, constants.key_pkce_token_type)):
                log_mismatch_file_vs_static("token_type")
                all_match = False
            if (all_match and not (
                    conf_file_pkce_access_token == get_cred_value(cred_dict, constants.key_pkce_access_token))):
                log_mismatch_file_vs_static("access_token")
                all_match = False
            if (all_match and not (
                    conf_file_pkce_refresh_token == get_cred_value(cred_dict, constants.key_pkce_refresh_token))):
                log_mismatch_file_vs_static("refresh_token")
                all_match = False
            if (all_match and not (
                    conf_file_pkce_session_id == get_cred_value(cred_dict, constants.key_pkce_session_id))):
                log_mismatch_file_vs_static("session_id")
                all_match = False
            if (all_match and not (
                    conf_file_pkce_is_pkce == get_cred_value(cred_dict, constants.key_pkce_is_pkce))):
                log_mismatch_file_vs_static("is_pkce")
                all_match = False
            if all_match:
                msgproc.log("Credentials from pkce file match static configuration, the file is good to go!")
                return cred_dict
            else:
                msgproc.log("Credentials from pkce file don't match static configuration, the file is NOT good to go")
    # Static PKCE? (meaning that the credentials have NOT been loaded from the file)
    pkce_token_type : str = get_cred_value(cred_dict, constants.key_pkce_token_type)
    pkce_access_token : str = get_cred_value(cred_dict, constants.key_pkce_access_token)
    pkce_refresh_token : str = get_cred_value(cred_dict, constants.key_pkce_refresh_token)
    pkce_session_id : str = get_cred_value(cred_dict, constants.key_pkce_session_id)
    pkce_is_pkce : bool = (True
        if pkce_token_type
            and pkce_access_token
            and pkce_refresh_token
            and pkce_session_id
        else False)
    # msgproc.log(f"load_credentials static pkce - pkce_token_type [{pkce_token_type}]")
    # msgproc.log(f"load_credentials static pkce - pkce_access_token [{pkce_access_token}]")
    # msgproc.log(f"load_credentials static pkce - pkce_refresh_token [{pkce_refresh_token}]")
    # msgproc.log(f"load_credentials static pkce - pkce_session_id [{pkce_session_id}]")
    # msgproc.log(f"load_credentials static pkce - is_pkce [{pkce_is_pkce}]")
    if pkce_token_type and pkce_access_token and pkce_refresh_token and pkce_session_id:
        # save credentials file if it does not exist
        if not os.path.exists(__get_pkce_credentials_file_name()):
            pkce_credentials_json_dict : dict[str, str] = get_pkce_credentials_dict_for_json(
                pkce_token_type = pkce_token_type,
                pkce_access_token = pkce_access_token,
                pkce_refresh_token = pkce_refresh_token,
                pkce_session_id = pkce_session_id,
                pkce_is_pkce = pkce_is_pkce)
            with open(__get_pkce_credentials_file_name(), 'w') as wcf:
                json.dump(pkce_credentials_json_dict, wcf, indent = 4)
            msgproc.log(f"PKCE credentials stored to [{__get_pkce_credentials_file_name()}]")
        return {
            constants.key_authentication_type: AuthenticationType.PKCE.auth_type,
            constants.key_pkce_token_type: pkce_token_type,
            constants.key_pkce_access_token: pkce_access_token,
            constants.key_pkce_refresh_token: pkce_refresh_token,
            constants.key_pkce_session_id: pkce_session_id,
            constants.key_pkce_is_pkce: pkce_is_pkce
        }
    else:
        msgproc.log("PKCE credentials not statically available")
    # OATH2?
    token_type : str = get_cred_value(cred_dict, constants.key_token_type)
    access_token : str = get_cred_value(cred_dict, constants.key_access_token)
    refresh_token : str = get_cred_value(cred_dict, constants.key_refresh_token)
    expiry_time_timestamp_str : str = get_cred_value(cred_dict, constants.key_expiry_time_timestamp_str)
    if token_type and access_token:
        oauth2_credentials : dict[str, str] = {
            constants.key_authentication_type: AuthenticationType.OAUTH2.auth_type,
            constants.key_token_type : token_type,
            constants.key_access_token : access_token
        }
        if refresh_token: oauth2_credentials[constants.key_refresh_token] = refresh_token
        if expiry_time_timestamp_str:
            oauth2_credentials[constants.key_expiry_time_timestamp_str] = expiry_time_timestamp_str
        return oauth2_credentials
    else:
        msgproc.log("OAUTH2 credentials not statically available")
    # nothing available, challenge time!
    auth_challenge_type : AuthenticationType = convert_authentication_type(config.auth_challenge_type)
    new_session : TidalSession = TidalSession()
    if AuthenticationType.OAUTH2 == auth_challenge_type:
        # show challenge url
        new_session.login_oauth_simple(function = msgproc.log)
        token_type = new_session.token_type
        access_token = new_session.access_token
        refresh_token = new_session.refresh_token
        expiry_time = new_session.expiry_time
        storable_expiry_time = datetime.datetime.timestamp(expiry_time)
        new_oauth2_credentials : dict[str, str] = {
            constants.key_authentication_type: AuthenticationType.OAUTH2.auth_type,
            constants.key_token_type : token_type,
            constants.key_access_token : access_token,
            constants.key_refresh_token : refresh_token,
            constants.key_expiry_time_timestamp_str : storable_expiry_time
        }
        with open(__get_credentials_file_name(), 'w') as wcf:
            json.dump(new_oauth2_credentials, wcf, indent = 4)
        return new_oauth2_credentials
    else:
        # PKCE
        new_session.login_pkce(fn_print = msgproc.log)
        pkce_token_type : str = new_session.token_type
        pkce_access_token : str = new_session.access_token
        pkce_refresh_token : str = new_session.refresh_token
        pkce_session_id : str = new_session.session_id
        pkce_is_pkce : bool = new_session.is_pkce
        new_pkce_credentials : dict[str, str] = {
            constants.key_authentication_type : AuthenticationType.PKCE.auth_type,
            constants.key_pkce_token_type : pkce_token_type,
            constants.key_pkce_access_token : pkce_access_token,
            constants.key_pkce_refresh_token : pkce_refresh_token,
            constants.key_pkce_session_id : pkce_session_id,
            constants.key_pkce_is_pkce : pkce_is_pkce
        }
        with open(__get_pkce_credentials_file_name(), 'w') as wcf:
            pkce_credentials_json_dict : dict[str, str] = get_pkce_credentials_dict_for_json(
                pkce_token_type = pkce_token_type,
                pkce_access_token = pkce_access_token,
                pkce_refresh_token = pkce_refresh_token,
                pkce_session_id = pkce_session_id,
                pkce_is_pkce = pkce_is_pkce)
            json.dump(pkce_credentials_json_dict, wcf, indent = 4)
        # inform that file is available!
        new_pkce_credentials[constants.key_file_available] = True
        return new_pkce_credentials


def build_session() -> TidalSession:
    global credentials_dict
    if not credentials_dict:
        msgproc.log("Loading credentials ...")
        credentials_dict = load_credentials()
        msgproc.log("Credentials loaded")
    # msgproc.log(f"build_session Configuration loaded")
    auth_type : AuthenticationType = convert_authentication_type(credentials_dict[constants.key_authentication_type])
    file_available : bool = (credentials_dict[constants.key_file_available]
        if constants.key_file_available in credentials_dict
        else False)
    if file_available and AuthenticationType.PKCE == auth_type:
        msgproc.log(f"PKCE file [{__get_pkce_credentials_file_name()}] available, building a new session ...")
        # return pkce session
        session_file = Path(__get_pkce_credentials_file_name())
        session : TidalSession = TidalSession()
        # Load session from file; create a new session if necessary
        res : bool = session.login_session_file(session_file, do_pkce = True)
        if not res:
            msgproc.log("build pkce session failed")
            return None
        session.audio_quality = config.max_audio_quality
        msgproc.log(f"Built a pkce session successfully, using audio_quality [{session.audio_quality}]")
        return session
    if AuthenticationType.OAUTH2 == auth_type:
        msgproc.log("Building a new oauth2 session ...")
        # return OAUTH2 session
        token_type : str = credentials_dict[constants.key_token_type]
        access_token : str = credentials_dict[constants.key_access_token]
        refresh_token : str = credentials_dict[constants.key_refresh_token]
        expiry_time_timestamp_str : str = credentials_dict[constants.key_expiry_time_timestamp_str]
        session : TidalSession = TidalSession()
        expiry_time_timestamp : float = float(expiry_time_timestamp_str) if expiry_time_timestamp_str else None
        expiry_time : datetime.datetime = (datetime.datetime.fromtimestamp(expiry_time_timestamp)
            if expiry_time_timestamp
            else None)
        res : bool = session.load_oauth_session(token_type, access_token, refresh_token, expiry_time)
        if not res:
            msgproc.log("build session failed")
            return None
        session.audio_quality = config.max_audio_quality
        msgproc.log(f"Built an oauth2 session successfully, using audio_quality [{session.audio_quality}]")
        return session
    else:
        # return pkce session
        session_file = Path(__get_pkce_credentials_file_name())
        session : TidalSession = TidalSession()
        # Load session from file; create a new session if necessary
        res : bool = session.login_session_file(session_file, do_pkce=True)
        if not res:
            msgproc.log("build session failed")
            return None
        session.audio_quality = config.max_audio_quality
        return session


def is_session_too_old(session_status : SessionStatus, delta_sec : int):
    cutoff : datetime.datetime = datetime.datetime.now() - datetime.timedelta(seconds = delta_sec)
    return session_status.update_time < cutoff


def get_session(force_recreate : bool = False) -> TidalSession:
    global session_status
    if not session_status or force_recreate:
        session_status = SessionStatus(build_session())
    else:
        # needs updating?
        if is_session_too_old(session_status = session_status, delta_sec = config.session_max_duration_sec):
            # re-authenticate
            session_status.update(build_session())
    return session_status.tidal_session


def compose_docroot_url(right : str) -> str:
    host_port : str = os.environ['UPMPD_UPNPHOSTPORT']
    doc_root : str = os.environ['UPMPD_UPNPDOCROOT']
    if not host_port and not doc_root: return None
    return f"http://{host_port}/{right}"


def build_intermediate_url(track_id : str) -> str:
    http_host_port = os.environ["UPMPD_HTTPHOSTPORT"]
    url = f"http://{http_host_port}/{plugin_name}/track/version/1/trackId/{track_id}"
    if config.log_intermediate_url: msgproc.log(f"intermediate_url for track_id {track_id} -> [{url}]")
    return url


def ensure_directory(base_dir : str, sub_dir_list : list[str]) -> str:
    curr_sub_dir : str
    curr_dir : str = base_dir
    for curr_sub_dir in sub_dir_list:
        new_dir : str = os.path.join(curr_dir, curr_sub_dir)
        # msgproc.log(f"checking dir [{new_dir}] ...")
        if not os.path.exists(new_dir):
            msgproc.log(f"creating dir [{new_dir}] ...")
            os.mkdir(new_dir)
        # else:
        #     msgproc.log(f"dir [{new_dir}] already exists.")
        curr_dir = new_dir
    return curr_dir


def remove_older_files(files_path : str, delta_sec : int):
    now = time.time()
    for f in os.listdir(files_path):
        # msgproc.log(f"Found [{files_path}] [{f}]")
        if os.stat(os.path.join(files_path, f)).st_mtime < (now - delta_sec):
            # msgproc.log(f"Deleting file: [{os.path.join(files_path, f)}]")
            os.remove(os.path.join(files_path, f))


def build_streaming_url(tidal_session : TidalSession, track_id : str) -> StreamingInfo:
    track : TidalTrack = tidal_session.track(track_id)
    streaming_url : str = None
    document_root_dir : str = upmplgutils.getOptionValue("webserverdocumentroot")
    stream = track.get_stream()
    quality : TidalQuality = stream.audio_quality
    audio_mode : str = stream.audio_mode
    bit_depth = stream.bit_depth
    sample_rate = stream.sample_rate
    msgproc.log(f"build_streaming_url is_pkce [{tidal_session.is_pkce}] "
                f"track_id [{track_id}] "
                f"session_quality [{tidal_session.audio_quality}] "
                f"bit_depth [{bit_depth}] "
                f"sample_rate [{sample_rate}] "
                f"audio_mode [{audio_mode}]")
    mimetype : str = stream.manifest_mime_type
    manifest = stream.get_stream_manifest()
    codecs : any = manifest.get_codecs()
    if stream.is_MPD:
        data = stream.get_manifest_data()
        file_ext : str
        file_dir : str
        if "mpd" == config.serve_mode:
            file_ext = "mpd"
            file_dir = "mpd-files"
        else:
            file_ext = "hls"
            file_dir = "hls-files"
        sub_dir_list : list[str] = [constants.plugin_name, file_dir]
        write_dir : str = ensure_directory(document_root_dir, sub_dir_list)
        file_name : str = "dash_{}.{}".format(track.id, file_ext)
        with open(os.path.join(write_dir, file_name), "w") as my_file:
            my_file.write(data)
        remove_older_files(files_path = write_dir, delta_sec = config.max_file_age_seconds)
        path : list[str] = list()
        path.extend([constants.plugin_name, file_dir])
        path.append(file_name)
        streaming_url = compose_docroot_url("/".join(path))
    elif stream.is_BTS:
        streaming_url = manifest.get_urls()
    result : StreamingInfo = StreamingInfo()
    result.url = streaming_url
    result.mimetype = mimetype
    result.codecs = codecs
    result.sample_rate = sample_rate
    result.audio_quality = quality
    result.audio_mode = audio_mode
    result.bit_depth = bit_depth
    msgproc.log(f"build_streaming_url for track_id: [{track_id}] "
                f"streamtype [{'MPD' if stream.is_MPD else 'BTS'}] title [{track.name}] "
                f"from [{track.album.name}] by [{track.artist.name}] -> "
                f"[{streaming_url}] Q:[{quality}] M:[{audio_mode}] "
                f"MT:[{mimetype}] SR:[{sample_rate}] B:[{bit_depth}]")
    return result


def calc_bitrate(tidal_quality : TidalQuality, bit_depth : int, sample_rate : int) -> int:
    if tidal_util.is_mp3(tidal_quality):
        return 320 if TidalQuality.low_320k == tidal_quality else 96
    if bit_depth and sample_rate:
        return int((2 * bit_depth * sample_rate) / 1000)
    else:
        # fallback to redbook (might be wrong!)
        return 1411


@dispatcher.record('trackuri')
def trackuri(a):
    upmpd_pathprefix = os.environ["UPMPD_PATHPREFIX"]
    msgproc.log(f"UPMPD_PATHPREFIX: [{upmpd_pathprefix}] trackuri: [{a}]")
    track_id = upmplgutils.trackid_from_urlpath(upmpd_pathprefix, a)
    tidal_session : TidalSession = get_session()
    streaming_info : StreamingInfo = build_streaming_url(
        tidal_session = tidal_session,
        track_id = track_id) or ("", "")
    res : dict[str, any] = {}
    res['media_url'] = streaming_info.url
    upnp_util.set_mime_type(streaming_info.mimetype, res)
    if streaming_info.url:
        track : TidalTrack = tidal_session.track(track_id)
        if track:
            played_track_request : PlayedTrackRequest = PlayedTrackRequest()
            played_track_request.track_id = track_id
            played_track_request.track_name = track.name
            played_track_request.track_duration = track.duration
            played_track_request.track_num = track.track_num
            played_track_request.volume_num = track.volume_num
            played_track_request.audio_quality = streaming_info.audio_quality
            played_track_request.explicit = track.explicit
            played_track_request.album_id = track.album.id
            played_track_request.artist_name = track.artist.name
            played_track_request.bit_depth = streaming_info.bit_depth
            played_track_request.sample_rate = streaming_info.sample_rate
            album : TidalAlbum = tidal_session.album(played_track_request.album_id)
            if album:
                played_track_request.album_track_count = album.num_tracks
                played_track_request.album_num_volumes = album.num_volumes
                played_track_request.album_duration = album.duration
                played_track_request.album_name = album.name
                played_track_request.album_artist_name = album.artist.name
                played_track_request.image_url = tidal_util.get_image_url(album)
                persistence.track_playback(played_track_request)
            upnp_util.set_bit_rate(
                str(calc_bitrate(
                    track.audio_quality,
                    streaming_info.bit_depth,
                    streaming_info.sample_rate)),
                res)
    return res


def tidal_track_to_played_track_request(
        track_adapter : TrackAdapter,
        tidal_session : TidalSession) -> PlayedTrackRequest:
    played_track_request : PlayedTrackRequest = PlayedTrackRequest()
    played_track_request.track_id = track_adapter.get_id()
    played_track_request.track_name = track_adapter.get_name()
    played_track_request.track_duration = track_adapter.get_duration()
    played_track_request.track_num = track_adapter.get_track_num()
    played_track_request.volume_num = track_adapter.get_volume_num()
    played_track_request.audio_quality = track_adapter.get_audio_quality()
    played_track_request.explicit = track_adapter.explicit()
    played_track_request.album_id = track_adapter.get_album_id()
    played_track_request.artist_name = track_adapter.get_artist_name()
    played_track_request.bit_depth = track_adapter.get_bit_depth()
    played_track_request.sample_rate = track_adapter.get_sample_rate()
    album : TidalAlbum = tidal_session.album(played_track_request.album_id)
    if album:
        played_track_request.album_track_count = album.num_tracks
        played_track_request.album_num_volumes = album.num_volumes
        played_track_request.album_duration = album.duration
        played_track_request.album_name = album.name
        played_track_request.album_artist_name = album.artist.name
        played_track_request.image_url = tidal_util.get_image_url(album)
    return played_track_request


def get_cached_audio_quality(album_id : str) -> tidal_util.CachedTidalQuality:
    played_track_list : list[PlayedTrack] = persistence.get_played_album_entries(album_id)
    if not played_track_list or len(played_track_list) == 0: return None
    # get first
    played_track : PlayedTrack = played_track_list[0]
    # audio_mode : str = played_track.audio_mode
    audio_quality : TidalQuality = played_track.audio_quality
    # audio quality not available? fix when possible
    if not audio_quality:
        # identify hi_res_lossless
        if ((played_track.bit_depth and played_track.bit_depth > 16) and
           (played_track.sample_rate and played_track.sample_rate > 48000)):
            return tidal_util.CachedTidalQuality(
                bit_depth = played_track.bit_depth,
                sample_rate = played_track.sample_rate,
                audio_quality = TidalQuality.hi_res_lossless)
        # identify hi_res
        if played_track.bit_depth and played_track.bit_depth > 16:
            # just hires
            return tidal_util.CachedTidalQuality(
                bit_depth = played_track.bit_depth,
                sample_rate = played_track.sample_rate,
                audio_quality = TidalQuality.hi_res)
    # catch invalid combinations
    bit_depth : int = played_track.bit_depth
    sample_rate : int = played_track.sample_rate
    if bit_depth == 16 and sample_rate in [44100, 48000]:
        if audio_quality in [TidalQuality.hi_res, TidalQuality.hi_res_lossless]:
            # invalid!
            # reset audio_quality to None to avoid false hires identification
            audio_quality = None
    return tidal_util.CachedTidalQuality(
        bit_depth = bit_depth,
        sample_rate = sample_rate,
        audio_quality = audio_quality)


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


def get_category_image_url(
        tidal_session : TidalSession,
        category : TidalItemList) -> str:
    category_tile_image : TileImage = persistence.load_tile_image(TileType.CATEGORY, category.title)
    tile_image_valid : bool = category_tile_image and not is_tile_imaged_expired(category_tile_image)
    category_image_url : str = category_tile_image.tile_image if tile_image_valid else None
    msgproc.log(f"get_category_image_url category [{category.title}] "
                f"type [{type(category).__name__}] "
                f"cached [{'yes' if category_image_url else 'no'}]")
    if not category_image_url:
        # load category image
        image_url : str = None
        if isinstance(category, TidalFeaturedItems):
            featured : TidalFeaturedItems = category
            first_featured = featured.items[0] if featured.items and len(featured.items) > 0 else None
            if not first_featured:
                msgproc.log(f"get_category_image_url category "
                            f"[{category.title}] Featured: first_featured not found")
            has_type_attribute : bool = first_featured and has_type_attr(first_featured)
            if first_featured and not has_type_attribute:
                msgproc.log(f"get_category_image_url category "
                            f"[{category.title}] Featured: first_featured no type attribute, "
                            f"type [{type(first_featured).__name__}]")
            if first_featured and has_type_attribute:
                msgproc.log(f"get_category_image_url category [{category.title}] (TidalFeaturedItems) "
                            f"first item type [{first_featured.type if first_featured else None}]")
                if first_featured.type == constants.featured_type_name_playlist:
                    playlist : TidalPlaylist = tidal_session.playlist(first_featured.artifact_id)
                    image_url = safe_get_image_url(playlist) if playlist else None
                    if not image_url:
                        msgproc.log(f"get_category_image_url category [{category.title}]"
                                    f"(TidalFeaturedItems) cannot get image for playlist")
                else:
                    msgproc.log(f"get_category_image_url category [{category.title}] (TidalFeaturedItems): "
                                f"not processed item {first_featured.type}")
        else:  # other than FeaturedItems ...
            first_item = category.items[0] if category.items and len(category.items) > 0 else None
            first_item_type : type = type(first_item) if first_item else None
            msgproc.log(f"get_category_image_url starting load process for "
                        f"category [{category.title}] type of first_item "
                        f"[{first_item_type.__name__ if first_item_type else None}]")
            if first_item:
                if isinstance(first_item, TidalTrack):
                    # msgproc.log(f"  processing as Track ...")
                    track : TidalTrack = first_item
                    album : TidalAlbum = tidal_session.album(track.album.id)
                    image_url = tidal_util.get_image_url(album) if album else None
                elif isinstance(first_item, TidalMix):
                    # msgproc.log(f"  processing as Mix ...")
                    mix : TidalMix = first_item
                    image_url = tidal_util.get_image_url(mix) if mix else None
                elif isinstance(first_item, TidalPlaylist):
                    # msgproc.log(f"  processing as Playlist ...")
                    playlist : TidalPlaylist = first_item
                    image_url = tidal_util.get_image_url(playlist) if playlist else None
                elif isinstance(first_item, TidalAlbum):
                    # msgproc.log(f"  processing as Album ...")
                    album : TidalAlbum = first_item
                    image_url = tidal_util.get_image_url(album) if album else None
                elif isinstance(first_item, TidalArtist):
                    # msgproc.log(f"  processing as Artist ...")
                    artist : TidalAlbum = first_item
                    image_url = tidal_util.get_image_url(artist) if artist else None
                elif isinstance(first_item, TidalPageLink):
                    # msgproc.log(f"  processing as <PageLink> ...")
                    page_link : TidalPageLink = first_item
                    page_link_items : list[any] = get_items_in_page_link(page_link)
                    for current in page_link_items if page_link_items else list():
                        if (isinstance(current, TidalPlaylist) or
                                isinstance(current, TidalAlbum) or
                                isinstance(current, TidalArtist)):
                            # get an image from that
                            image_url = tidal_util.get_image_url(current)
                            # we only need the first
                            break
                        else:
                            msgproc.log(f"get_category_image_url got a [{type(current).__name__ if current else None}] "
                                        f"in a [{TidalPageLink.__name__}]")
                else:
                    msgproc.log(f"get_category_image_url category [{category.title}] "
                                f"type [{type(first_item).__name__}] has not been managed")
            else:
                image_url = safe_get_image_url(first_item) if first_item else None
        if image_url:
            persistence.save_tile_image(TileType.CATEGORY, category.title, image_url)
            category_image_url = image_url
        else:
            msgproc.log(f"get_category_image_url could not get an image for category [{category.title}]")
    return category_image_url


def category_to_entry(
        objid,
        tidal_session : TidalSession,
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
    category_image_url : str = get_category_image_url(
        tidal_session = tidal_session,
        category = category)
    if category_image_url:
        upnp_util.set_album_art_from_uri(category_image_url, entry)
    else:
        msgproc.log(f"category_to_entry *Warning* category [{category.title}] "
                    f"type [{type(category)}] tile image not set.")
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


def track_apply_explicit(
        track_adapter : TrackAdapter,
        current_title : str = None,
        options : dict[str, any] = {}) -> str:
    title : str = current_title if current_title else track_adapter.get_name()
    if track_adapter.explicit():
        title : str = f"{title} [Explicit]"
    return title


def get_track_name_for_track_container(
        track_adapter: TrackAdapter,
        options : dict[str, any] = {}) -> str:
    title : str = track_adapter.get_name()
    skip_track_artist : bool = get_option(
        options = options,
        option_key = OptionKey.SKIP_TRACK_ARTIST)
    if not skip_track_artist:
        track_omittable_artist_name : str = get_option(
            options = options,
            option_key = OptionKey.TRACK_OMITTABLE_ARTIST_NAME)
        if not track_omittable_artist_name or track_omittable_artist_name != track_adapter.get_artist_name():
            title = f"{track_adapter.get_artist_name()} - {title}"
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
        title = f"[{track_number:02}] {title}"
    title = track_apply_explicit(
        track_adapter = track_adapter,
        current_title = title,
        options = options)
    return title


# Possibly the same #1 occ #1
def track_to_navigable_mix_item(
        objid,
        tidal_session : TidalSession,
        track: TidalTrack,
        options : dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid = objid,
        track_adapter = instance_tidal_track_adapter(
            tidal_session = tidal_session,
            track = track),
        element_type = ElementType.MIX_NAVIGABLE_ITEM,
        options = options)


def track_to_navigable_playlist_item(
        objid,
        tidal_session : TidalSession,
        track: TidalTrack,
        options : dict[str, any] = {}) -> dict:
    return track_to_navigable_track_by_element_type(
        objid = objid,
        track_adapter = instance_tidal_track_adapter(
            tidal_session = tidal_session,
            track = track),
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
        tidal_session : TidalSession,
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
            track_adapter = instance_tidal_track_adapter(
                tidal_session = tidal_session,
                track = track),
            options = options)
    track_entry = upmplgutils.direntry(id,
        objid,
        title)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(track.album), track_entry)
    return track_entry


def track_to_entry(
        objid,
        track_adapter : TrackAdapter,
        options : dict[str, any] = {},
        context : Context = Context()) -> dict:
    entry = {}
    identifier : ItemIdentifier = ItemIdentifier(ElementType.TRACK.getName(), track_adapter.get_id())
    id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(identifier))
    entry['id'] = id
    entry['pid'] = track_adapter.get_id()
    upnp_util.set_object_type_item(entry)
    upnp_util.set_class_music_track(entry)
    # channels. I could use AudioMode but I can't exactly say how many channels are delivered
    # so I am assuming two, looks like a decent fallback for now
    upnp_util.set_channels(2, entry)
    song_uri: str = build_intermediate_url(track_adapter.get_id())
    upnp_util.set_uri(song_uri, entry)
    title : str = track_adapter.get_name()
    upnp_util.set_track_title(title, entry)
    upnp_util.set_album_title(track_adapter.get_album_name(), entry)
    upnp_util.set_artist(track_adapter.get_album_artist_name(), entry)
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
    skip_art : bool = get_option(
        options = options,
        option_key = OptionKey.SKIP_ART)
    if not skip_art:
        art_url : str = get_option(
            options = options,
            option_key = OptionKey.OVERRIDDEN_ART_URI)
        if not art_url: art_url = track_adapter.get_image_url()
        upnp_util.set_album_art_from_uri(art_url, entry)
    upnp_util.set_duration(track_adapter.get_duration(), entry)
    set_track_stream_information(
        entry = entry,
        track_adapter = track_adapter,
        context = context)
    get_stream_failed : bool = context.get(key = ContextKey.CANNOT_GET_STREAM_INFO)
    if not get_stream_failed:
        # update success count
        context.increment(key = ContextKey.SUCCESS_COUNT)
    context.increment(key = ContextKey.PROCESS_COUNT)
    if config.dump_track_to_entry_result:
        known : bool = context.dict_get(
            dict_key = ContextKey.KNOWN_TRACK_DICT,
            entry_key = track_adapter.get_id(),
            default_value = False)
        guessed : bool = context.dict_get(
            dict_key = ContextKey.GUESSED_TRACK_DICT,
            entry_key = track_adapter.get_id(),
            default_value = False)
        assumed_by_first : bool = context.dict_get(
            dict_key = ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_DICT,
            entry_key = track_adapter.get_id(),
            default_value = False)
        get_stream : bool = context.dict_get(
            dict_key = ContextKey.GET_STREAM_DICT,
            entry_key = track_adapter.get_id(),
            default_value = False)
        msgproc.log(f"Track [{track_adapter.get_id()}] Title [{track_adapter.get_name()}] "
            f"from [{track_adapter.get_album_name()}] "
            f"by [{track_adapter.get_artist_name()}] "
            f"known: [{'yes' if known else 'no'}] "
            f"guessed: [{'yes' if guessed else 'no'}] "
            f"assumed from first: [{'yes' if assumed_by_first else 'no'}] "
            f"get_stream: [{'yes' if get_stream else 'no'}]")
        # f"stream info obtained: [{stream_info_obtained}] "
        # f"bit_depth [{bit_depth if known else None}] "
        # f"sample_rate [{sample_rate if known else None}] "
        # f"guessed from album track: [{guessed_from_album_track}] "
        # f"assumed from first track: [{assumed_from_first}] "
        # f"assumed by config quality: [{assumed_by_config_quality}]")
    return entry


def report_get_stream_exception(
        ex : Exception,
        track_adapter : TrackAdapter,
        context : Context):
    success_count : int = context.get(key = ContextKey.SUCCESS_COUNT)
    msgproc.log(
        f"getting stream info failed for track_id [{track_adapter.get_id()}] "
        f"Title [{track_adapter.get_name()}] from [{track_adapter.get_album_name()}] "
        f"by [{track_adapter.get_artist_name()}], "
        f"setting CANNOT_GET_STREAM_INFO for context to True "
        f"after [{success_count}] successes "
        f"due to [{type(ex)}] [{ex}]")
    context.add(ContextKey.CANNOT_GET_STREAM_INFO, True)


def set_track_stream_information(
        entry : dict[str, any],
        track_adapter : TrackAdapter,
        context : Context):
    is_album : bool = context.get(key = ContextKey.IS_ALBUM)
    is_playlist : bool = context.get(key = ContextKey.IS_PLAYLIST)
    is_mix : bool = context.get(key = ContextKey.IS_MIX)
    is_mix_or_playlist : bool = is_playlist or is_mix
    if is_album:
        set_stream_information_for_album_entry(
            entry = entry,
            track_adapter = track_adapter,
            context = context)
    elif is_mix_or_playlist:
        set_stream_information_for_mix_or_playlist_entry(
            entry = entry,
            track_adapter = track_adapter,
            context = context)
    else:
        # we do the same as fallback
        # TODO evaluate if we can so ignore is_mix, is_playlist
        set_stream_information_for_mix_or_playlist_entry(
            entry = entry,
            track_adapter = track_adapter,
            context = context)


def __played_track_has_stream_info(played_track : PlayedTrack) -> bool:
    return (played_track and
        played_track.bit_depth and
        played_track.sample_rate and
        played_track.audio_quality)


def __context_contains_first_track_data(context : Context) -> bool:
    return (
        context.contains(ContextKey.ALBUM_FIRST_TRACK_BIT_DEPTH) and
        context.contains(ContextKey.ALBUM_FIRST_TRACK_SAMPLE_RATE) and
        context.contains(ContextKey.ALBUM_FIRST_TRACK_AUDIO_QUALITY))


def _context_increment_and_store_dict_of_bool(
        context : Context,
        counter_key : ContextKey,
        dict_key : ContextKey,
        track_id : str):
    context.increment(key = counter_key)
    context.dict_add(
        dict_key = dict_key,
        entry_key = track_id,
        entry_value = True)


def __select_played_track(played_tracks : list[PlayedTrack]) -> PlayedTrack:
    select : PlayedTrack
    for select in played_tracks if played_tracks else list():
        if (select.audio_quality and
                select.bit_depth and
                select.sample_rate):
            return select
    # none is good, so let's return first if available
    return played_tracks[0] if played_tracks and len(played_tracks) > 0 else None


def set_stream_information_for_mix_or_playlist_entry(
        entry : dict[str, any],
        track_adapter : TrackAdapter,
        context : Context):
    bit_depth : int = None
    sample_rate : int = None
    audio_quality : str = None
    # do we know the track from our played tracks?
    played_album_tracks : list[PlayedTrack] = get_or_load_played_album_tracks(
        context = context,
        album_id = track_adapter.get_album_id())
    played = get_played_track(
        played_album_tracks = played_album_tracks,
        track_id = track_adapter.get_id())
    got_from_played : bool = False
    if __played_track_has_stream_info(played):
        got_from_played = True
        _context_increment_and_store_dict_of_bool(
            context = context,
            counter_key = ContextKey.KNOWN_TRACKS_COUNT,
            dict_key = ContextKey.KNOWN_TRACK_DICT,
            track_id = track_adapter.get_id())
    # ok, we don't have the current track, but do we have
    # a track from the same album?
    elif len(played_album_tracks) > 0 and config.allow_guess_stream_info_from_other_album_track:
        # take first know track, and assume that stream info is the same for all
        # of the tracks in the same albums, which most of the times is true
        got_from_played = True
        _context_increment_and_store_dict_of_bool(
            context = context,
            counter_key = ContextKey.GUESSED_TRACKS_COUNT,
            dict_key = ContextKey.GUESSED_TRACK_DICT,
            track_id = track_adapter.get_id())
        played = __select_played_track(played_album_tracks)
    if not got_from_played:
        # get from first?
        if (__context_contains_first_track_data(context = context)):
            bit_depth = context.get(key = ContextKey.ALBUM_FIRST_TRACK_BIT_DEPTH, allow_empty = False)
            sample_rate = context.get(key = ContextKey.ALBUM_FIRST_TRACK_SAMPLE_RATE, allow_empty = False)
            audio_quality = context.get(key = ContextKey.ALBUM_FIRST_TRACK_AUDIO_QUALITY, allow_empty = False)
            #  assumed_from_first = True
            _context_increment_and_store_dict_of_bool(
                context = context,
                counter_key = ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_COUNT,
                dict_key = ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_DICT,
                track_id = track_adapter.get_id())
    else:  # got from played
        bit_depth = played.bit_depth
        sample_rate = played.sample_rate
        audio_quality = correct_audio_quality(
            bit_depth = bit_depth,
            sample_rate = sample_rate,
            audio_quality = played.audio_quality)
    # still nothing? read stream info a max number of times
    if not bit_depth and not sample_rate and not audio_quality:
        get_stream_failed : bool = context.get(key = ContextKey.CANNOT_GET_STREAM_INFO)
        if not get_stream_failed:
            limit : int = config.max_get_stream_info_mix_or_playlist
            get_stream_count : int = context.get(key = ContextKey.GET_STREAM_COUNT)
            if get_stream_count < limit:
                try:
                    if config.dump_track_to_entry_result:
                        msgproc.log(f"Trying to get stream info for track_id [{track_adapter.get_id()}]")
                    bit_depth = track_adapter.get_bit_depth()
                    sample_rate = track_adapter.get_sample_rate()
                    audio_quality = track_adapter.get_audio_quality()
                    _context_increment_and_store_dict_of_bool(
                        context = context,
                        counter_key = ContextKey.GET_STREAM_COUNT,
                        dict_key = ContextKey.GET_STREAM_DICT,
                        track_id = track_adapter.get_id())
                    # store ghost playback
                    persistence.track_ghost_playback(
                        played_track_request = tidal_track_to_played_track_request(
                            track_adapter = track_adapter,
                            tidal_session = get_session()))
                except Exception as ex:
                    report_get_stream_exception(
                        ex = ex,
                        track_adapter = track_adapter,
                        context = context)
    if not bit_depth and config.enable_assume_bitdepth:
        #  last fallback for bit depth
        bit_depth = get_bit_depth_by_config_quality()
        # assume redbook
        if not audio_quality: audio_quality = TidalQuality.high_lossless
        if not bit_depth: bit_depth = 16
        if not sample_rate: sample_rate = 44100
        #  increment ASSUMED_BY_MAX_AUDIO_QUALITY_COUNT
        context.increment(key = ContextKey.ASSUMED_BY_MAX_AUDIO_QUALITY_COUNT)
    if not bit_depth or not sample_rate or not audio_quality:
        msgproc.log(f"No info for [{track_adapter.get_name()}] "
                    f"from [{track_adapter.get_album_name()}] "
                    f"by [{track_adapter.get_artist_name()}] "
                    f"bit_depth [{bit_depth}] "
                    f"sample_rate [{sample_rate}] "
                    f"audio_quality [{audio_quality}]")
    if bit_depth: upnp_util.set_bit_depth(bit_depth, entry)
    if sample_rate: upnp_util.set_sample_rate(sample_rate, entry)
    if audio_quality: upnp_util.set_mime_type(tidal_util.get_mime_type(audio_quality), entry)


def set_stream_information_for_album_entry(
        entry : dict[str, any],
        track_adapter : TrackAdapter,
        context : Context):
    bit_depth : int = None
    sample_rate : int = None
    audio_quality : str = None
    # guessed_from_album_track : bool = False
    # do we know the track from our played tracks?
    played_album_tracks : list[PlayedTrack] = get_or_load_played_album_tracks(
        context = context,
        album_id = track_adapter.get_album_id())
    played = get_played_track(
        played_album_tracks = played_album_tracks,
        track_id = track_adapter.get_id())
    got_from_played : bool = False
    if __played_track_has_stream_info(played):
        got_from_played = True
        _context_increment_and_store_dict_of_bool(
            context = context,
            counter_key = ContextKey.KNOWN_TRACKS_COUNT,
            dict_key = ContextKey.KNOWN_TRACK_DICT,
            track_id = track_adapter.get_id())
    # ok, we don't have the current track, but do we have
    # a track from the same album?
    elif len(played_album_tracks) > 0 and config.allow_guess_stream_info_from_other_album_track:
        # take first know track, and assume that stream info is the same for all
        # of the tracks in the same albums, which most of the times is true
        # guessed_from_album_track = True
        got_from_played = True
        played = __select_played_track(played_album_tracks)
        _context_increment_and_store_dict_of_bool(
            context = context,
            counter_key = ContextKey.GUESSED_TRACKS_COUNT,
            dict_key = ContextKey.GUESSED_TRACK_DICT,
            track_id = track_adapter.get_id())
    if not got_from_played:
        # get from first?
        if (__context_contains_first_track_data(context = context)):
            bit_depth = context.get(key = ContextKey.ALBUM_FIRST_TRACK_BIT_DEPTH, allow_empty = False)
            sample_rate = context.get(key = ContextKey.ALBUM_FIRST_TRACK_SAMPLE_RATE, allow_empty = False)
            audio_quality = context.get(key = ContextKey.ALBUM_FIRST_TRACK_AUDIO_QUALITY, allow_empty = False)
            #  assumed_from_first = True
            _context_increment_and_store_dict_of_bool(
                context = context,
                counter_key = ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_COUNT,
                dict_key = ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_DICT,
                track_id = track_adapter.get_id())
    else:  # got from played
        bit_depth = played.bit_depth
        sample_rate = played.sample_rate
        audio_quality = correct_audio_quality(
            bit_depth = bit_depth,
            sample_rate = sample_rate,
            audio_quality = played.audio_quality)
    # still nothing? read from first track
    if not bit_depth and not sample_rate and not audio_quality:
        get_stream_failed : bool = context.get(key = ContextKey.CANNOT_GET_STREAM_INFO)
        if not get_stream_failed:
            try:
                if config.dump_track_to_entry_result:
                    msgproc.log(f"Trying to get stream info for track_id [{track_adapter.get_id()}]")
                bit_depth = track_adapter.get_bit_depth()
                sample_rate = track_adapter.get_sample_rate()
                audio_quality = track_adapter.get_audio_quality()
                _context_increment_and_store_dict_of_bool(
                    context = context,
                    counter_key = ContextKey.GET_STREAM_COUNT,
                    dict_key = ContextKey.GET_STREAM_DICT,
                    track_id = track_adapter.get_id())
                # store in context
                context.add(key = ContextKey.ALBUM_FIRST_TRACK_BIT_DEPTH, value = bit_depth)
                context.add(key = ContextKey.ALBUM_FIRST_TRACK_SAMPLE_RATE, value = sample_rate)
                context.add(key = ContextKey.ALBUM_FIRST_TRACK_AUDIO_QUALITY, value = audio_quality)
                # store obtained information
                persistence.track_ghost_playback(
                    played_track_request = tidal_track_to_played_track_request(
                        track_adapter = track_adapter,
                        tidal_session = get_session()))
            except Exception as ex:
                report_get_stream_exception(
                    ex = ex,
                    track_adapter = track_adapter,
                    context = context)
    if not bit_depth and config.enable_assume_bitdepth:
        #  last fallback for bit depth
        bit_depth = get_bit_depth_by_config_quality()
        # assume redbook
        if not audio_quality: audio_quality = TidalQuality.high_lossless
        if not bit_depth: bit_depth = 16
        if not sample_rate: sample_rate = 44100
        #  increment ASSUMED_BY_MAX_AUDIO_QUALITY_COUNT
        context.increment(key = ContextKey.ASSUMED_BY_MAX_AUDIO_QUALITY_COUNT)
    if not bit_depth or not sample_rate or not audio_quality:
        msgproc.log(f"No info for [{track_adapter.get_name()}] "
                    f"from [{track_adapter.get_album_name()}] "
                    f"by [{track_adapter.get_artist_name()}] "
                    f"bit_depth [{bit_depth}] "
                    f"sample_rate [{sample_rate}] "
                    f"audio_quality [{audio_quality}]")
    if bit_depth: upnp_util.set_bit_depth(bit_depth, entry)
    if sample_rate: upnp_util.set_sample_rate(sample_rate, entry)
    if audio_quality: upnp_util.set_mime_type(tidal_util.get_mime_type(audio_quality), entry)


def correct_audio_quality(
        bit_depth : int,
        sample_rate : int,
        audio_quality : TidalQuality) -> TidalQuality:
    # can we evaluate bit available data?
    if bit_depth and sample_rate:
        if bit_depth > 16 and sample_rate > 48000: return TidalQuality.hi_res_lossless
        if bit_depth > 16: return TidalQuality.hi_res
        if bit_depth == 16 and sample_rate in [44100, 48000]:
            if not audio_quality:
                return TidalQuality.high_lossless
            else:
                # can't be hires or hi_res_lossless
                if audio_quality not in [TidalQuality.hi_res, TidalQuality.hi_res_lossless]:
                    return audio_quality
                else:  # invalid!
                    return None
    else:
        # no bit_depth, no sample_rate
        # assume redbook if missing
        return audio_quality if audio_quality else TidalQuality.high_lossless


def get_or_load_played_album_tracks(context : Context, album_id : str) -> list[PlayedTrack]:
    played_album_tracks_dict : dict[str, list[PlayedTrack]] = context.get(ContextKey.PLAYED_ALBUM_TRACKS_DICT)
    played_tracks_list : list[PlayedTrack] = (played_album_tracks_dict[album_id]
        if album_id in played_album_tracks_dict
        else None)
    if not played_tracks_list:
        played_tracks_list = persistence.get_played_album_entries(album_id = str(album_id))
        played_album_tracks_dict[album_id] = played_tracks_list
        context.update(key = ContextKey.PLAYED_ALBUM_TRACKS_DICT, value = played_album_tracks_dict)
    return played_tracks_list


def get_played_track(played_album_tracks : list[PlayedTrack], track_id : str) -> PlayedTrack:
    played_track : PlayedTrack
    for played_track in played_album_tracks:
        if str(played_track.track_id) == str(track_id):
            return played_track
    return None


def artist_to_entry(
        objid,
        artist : TidalArtist) -> upmplgutils.direntry:
    art_uri : str = tidal_util.get_image_url(artist)
    # msgproc.log(f"artist_to_entry art_uri = [{art_uri}]")
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(),
        artist.id)
    identifier.set(ItemIdentifierKey.MISSING_ARTIST_ART, art_uri is None)
    id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(identifier))
    entry = upmplgutils.direntry(id,
        objid,
        title = artist.name)
    upnp_util.set_class_artist(entry)
    upnp_util.set_album_art_from_uri(art_uri, entry)
    return entry


def album_to_album_container(
        objid,
        album : TidalAlbum,
        options : dict[str, any] = dict()) -> upmplgutils.direntry:
    out_options : dict[str, any] = dict()
    item_num : int = get_option(
        options = options,
        option_key = OptionKey.PREPEND_ENTRY_NUMBER_IN_ENTRY_NAME)
    if item_num: set_option(
        options = out_options,
        option_key = OptionKey.PREPEND_ENTRY_NUMBER_IN_ENTRY_NAME,
        option_value = item_num)
    omit_artist_unless_different : bool = get_option(
        options = options,
        option_key = OptionKey.OMIT_ARTIST_TO_ALBUM_ENTRY_UNLESS_DIFFERENT)
    set_option(
        options = out_options,
        option_key = OptionKey.OMIT_ARTIST_TO_ALBUM_ENTRY_UNLESS_DIFFERENT,
        option_value = omit_artist_unless_different)
    omittable_artist_id : str = get_option(
        options = options,
        option_key = OptionKey.ALBUM_OMITTABLE_ARTIST_ID)
    if omittable_artist_id:
        set_option(
            options = out_options,
            option_key = OptionKey.ALBUM_OMITTABLE_ARTIST_ID,
            option_value = omittable_artist_id)
    set_option(
        options = out_options,
        option_key = OptionKey.ENTRY_AS_CONTAINER,
        option_value = True)
    set_option(
        options = out_options,
        option_key = OptionKey.ADD_ARTIST_TO_ALBUM_ENTRY,
        option_value = True)
    return album_to_entry(
        objid = objid,
        album = album,
        options = out_options)


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
    current_artist_id : str = album.artist.id
    allow_omittable : bool = get_option(
        options = options,
        option_key = OptionKey.OMIT_ARTIST_TO_ALBUM_ENTRY_UNLESS_DIFFERENT)
    if allow_omittable:
        omittable : str = get_option(
            options = options,
            option_key = OptionKey.ALBUM_OMITTABLE_ARTIST_ID)
        if omittable == current_artist_id:
            # avoid to prepend artist in this case
            add_artist = False
    if add_artist:
        album_title = f"{album.artist.name} - {album_title}"
    entry_number : int = get_option(
        options = options,
        option_key = OptionKey.PREPEND_ENTRY_NUMBER_IN_ENTRY_NAME)
    if entry_number: album_title = f"[{entry_number:02}] {album_title}"
    add_explicit : bool = get_option(
        options = options,
        option_key = OptionKey.ADD_EXPLICIT)
    if add_explicit and album.explicit and "explicit" not in album_title.lower():
        album_title = f"{album_title} [Explicit]"
    add_album_year : bool = get_option(
        options = options,
        option_key = OptionKey.ADD_ALBUM_YEAR)
    if add_album_year and album.year:
        album_title = f"{album_title} [{album.year}]"
    # add badge?
    cached_tidal_quality : tidal_util.CachedTidalQuality = get_cached_audio_quality(album_id = album.id)
    badge : str = tidal_util.get_quality_badge(
        album = album,
        cached_tidal_quality = cached_tidal_quality)
    if badge: album_title = f"{album_title} [{badge}]"
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


def get_categories(tidal_session : TidalSession) -> list[TidalItemList]:
    home = tidal_session.home()
    home.categories.extend(tidal_session.explore().categories)
    # home.categories.extend(tidal_session.videos().categories)
    return home.categories


def get_category(
        tidal_session : TidalSession,
        category_name : str):
    categories : list[TidalItemList] = get_categories(tidal_session = tidal_session)
    match_list : list = list()
    first = None
    for current in categories:
        if current.title == category_name:
            if not first: first = current
            match_list.append(current)
    if len(match_list) > 1: msgproc.log(f"get_category: multiple matches for [{category_name}], returning first")
    return first


def compare_favorite_album_by_criteria_list(
        criteria_list : list[AlbumSortCriteria],
        left : TidalAlbum,
        right : TidalAlbum) -> int:
    cmp : int = 0
    current : AlbumSortCriteria
    for current in criteria_list:
        cmp = current.compare(left, right)
        if cmp != 0: break
    return cmp


def compare_favorite_artist_by_criteria_list(
        criteria_list : list[ArtistSortCriteria],
        left : TidalArtist,
        right : TidalArtist) -> int:
    cmp : int = 0
    current : ArtistSortCriteria
    for current in criteria_list:
        cmp = current.compare(left, right)
        if cmp != 0: break
    return cmp


def build_album_sort_criteria_by_artist(descending : bool = False) -> list[AlbumSortCriteria]:
    criteria_list : list[AlbumSortCriteria] = list()
    multiplier : int = -1 if descending else 1
    artist_extractor : Callable[[TidalAlbum], str] = (lambda a :
        a.artist.name.upper() if a.artist and a.artist.name else "")
    artist_comparator : Callable[[str, str], int] = (lambda left, right:
        multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(artist_extractor, artist_comparator))

    rd_extractor : Callable[[TidalAlbum], float] = (lambda a :
        a.available_release_date.timestamp() if a.available_release_date else 0.0)
    rd_comparator : Callable[[float, float], int] = (lambda left, right:
        multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(rd_extractor, rd_comparator))

    t_extractor : Callable[[TidalAlbum], str] = lambda a : a.name.upper() if a.name else ""
    t_comparator : Callable[[str, str], int] = (lambda left, right:
        multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(t_extractor, t_comparator))

    return criteria_list


def build_album_sort_criteria_by_release_date(descending : bool = False) -> list[AlbumSortCriteria]:
    criteria_list : list[AlbumSortCriteria] = list()
    multiplier : int = -1 if descending else 1
    extractor : Callable[[TidalAlbum], float] = (lambda a :
        a.available_release_date.timestamp() if a.available_release_date else 0.0)
    comparator : Callable[[float, float], int] = (lambda left, right:
        multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(extractor, comparator))
    return criteria_list


def build_album_sort_criteria_by_user_date_added(descending : bool = False) -> list[AlbumSortCriteria]:
    criteria_list : list[AlbumSortCriteria] = list()
    multiplier : int = -1 if descending else 1
    extractor : Callable[[TidalAlbum], float] = lambda a : a.user_date_added.timestamp() if a.user_date_added else 0.0
    comparator : Callable[[float, float], int] = (lambda left, right:
        multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(extractor, comparator))
    return criteria_list


def build_artist_sort_criteria_by_user_date_added(descending : bool = False) -> list[ArtistSortCriteria]:
    criteria_list : list[ArtistSortCriteria] = list()
    multiplier : int = -1 if descending else 1
    extractor : Callable[[TidalArtist], float] = (lambda a :
        a.user_date_added.timestamp() if a.user_date_added else 0.0)
    comparator : Callable[[float, float], int] = (lambda left, right:
        multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(ArtistSortCriteria(extractor, comparator))
    return criteria_list


def build_album_sort_criteria_by_name(descending : bool = False) -> list[AlbumSortCriteria]:
    criteria_list : list[AlbumSortCriteria] = list()
    multiplier : int = -1 if descending else 1
    t_extractor : Callable[[TidalAlbum], str] = lambda a : a.name.upper() if a.name else ""
    t_comparator : Callable[[str, str], int] = (lambda left, right:
        multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(AlbumSortCriteria(t_extractor, t_comparator))
    return criteria_list


def build_artist_sort_criteria_by_name(descending : bool = False) -> list[ArtistSortCriteria]:
    criteria_list : list[ArtistSortCriteria] = list()
    multiplier : int = -1 if descending else 1
    t_extractor : Callable[[TidalArtist], str] = lambda a : a.name.upper() if a.name else ""
    t_comparator : Callable[[str, str], int] = (lambda left, right:
        multiplier * (-1 if left < right else 0 if left == right else 1))
    criteria_list.append(ArtistSortCriteria(t_extractor, t_comparator))
    return criteria_list


def get_favorite_albums_by_artist(
        tidal_session : TidalSession,
        descending : bool,
        limit : int,
        offset : int = 0) -> list[TidalAlbum]:
    items : list[TidalAlbum] = tidal_session.user.favorites.albums()
    sc_list : list[AlbumSortCriteria] = build_album_sort_criteria_by_artist(descending = descending)
    items.sort(key = cmp_to_key(lambda x, y : compare_favorite_album_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_albums_by_title(
        tidal_session : TidalSession,
        descending : bool,
        limit : int,
        offset : int = 0) -> list[TidalAlbum]:
    items : list[TidalAlbum] = tidal_session.user.favorites.albums()
    sc_list : list[AlbumSortCriteria] = build_album_sort_criteria_by_name(descending = descending)
    items.sort(key = cmp_to_key(lambda x, y : compare_favorite_album_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_albums_by_release_date(
        tidal_session : TidalSession,
        descending : bool,
        limit : int,
        offset : int = 0) -> list[TidalAlbum]:
    items : list[TidalAlbum] = tidal_session.user.favorites.albums()
    sc_list : list[AlbumSortCriteria] = build_album_sort_criteria_by_release_date(descending = descending)
    items.sort(key = cmp_to_key(lambda x, y : compare_favorite_album_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_albums_by_user_date_added(
        tidal_session : TidalSession,
        descending : bool,
        limit : int,
        offset : int = 0) -> list[TidalAlbum]:
    items : list[TidalAlbum] = tidal_session.user.favorites.albums()
    sc_list : list[AlbumSortCriteria] = build_album_sort_criteria_by_user_date_added(descending = descending)
    items.sort(key = cmp_to_key(lambda x, y : compare_favorite_album_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_artists_by_name(
        tidal_session : TidalSession,
        descending : bool,
        limit : int,
        offset : int = 0) -> list[TidalArtist]:
    items : list[TidalArtist] = tidal_session.user.favorites.artists()
    sc_list : list[ArtistSortCriteria] = build_artist_sort_criteria_by_name(descending = descending)
    items.sort(key = cmp_to_key(lambda x, y : compare_favorite_artist_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def get_favorite_artists_by_user_date_added(
        tidal_session : TidalSession,
        descending : bool,
        limit : int,
        offset : int = 0) -> list[TidalArtist]:
    items : list[TidalArtist] = tidal_session.user.favorites.artists()
    sc_list : list[ArtistSortCriteria] = build_artist_sort_criteria_by_user_date_added(descending = descending)
    items.sort(key = cmp_to_key(lambda x, y : compare_favorite_artist_by_criteria_list(sc_list, x, y)))
    return items[offset:offset + limit] if items else []


def __handler_element_favorite_albums_common(
        descending : bool,
        element_type : ElementType,
        list_retriever : Callable[[TidalSession, bool, int, int], list[TidalAlbum]],
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session : TidalSession = get_session()
    counter : int = offset
    max_items : int = config.albums_per_page
    items : list[TidalAlbum] = list_retriever(tidal_session, descending, max_items, offset)
    current : TidalAlbum
    for current in items:
        counter += 1
        options : dict[str, any] = dict()
        if config.prepend_number_in_album_list:
            set_option(
                options = options,
                option_key = OptionKey.PREPEND_ENTRY_NUMBER_IN_ENTRY_NAME,
                option_value = counter)
        if config.skip_non_stereo and not tidal_util.is_stereo(current):
            msgproc.log(tidal_util.not_stereo_skipmessage(current))
            continue
        entries.append(album_to_album_container(
            objid = objid,
            album = current,
            options = options))
    if len(items) >= max_items:
        next_button = create_next_button(
            objid = objid,
            element_type = element_type,
            element_id = element_type.getName(),
            next_offset = offset + max_items)
        entries.append(next_button)
    return entries


def handler_element_favorite_albums_by_artist_asc(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_element_favorite_albums_common(
        descending = False,
        element_type = ElementType.FAVORITE_ALBUMS_BY_ARTIST_ASC,
        list_retriever = get_favorite_albums_by_artist,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_element_favorite_albums_by_artist_desc(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_element_favorite_albums_common(
        descending = True,
        element_type = ElementType.FAVORITE_ALBUMS_BY_ARTIST_DESC,
        list_retriever = get_favorite_albums_by_artist,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_element_favorite_albums_by_title_asc(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_element_favorite_albums_common(
        descending = False,
        element_type = ElementType.FAVORITE_ALBUMS_BY_TITLE_ASC,
        list_retriever = get_favorite_albums_by_title,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_element_favorite_albums_by_title_desc(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return __handler_element_favorite_albums_common(
        descending = True,
        element_type = ElementType.FAVORITE_ALBUMS_BY_TITLE_DESC,
        list_retriever = get_favorite_albums_by_title,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_element_favorite_albums_by_release_date_asc(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    return __handler_element_favorite_albums_common(
        descending = False,
        element_type = ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_ASC,
        list_retriever = get_favorite_albums_by_release_date,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_element_favorite_albums_by_release_date_desc(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    return __handler_element_favorite_albums_common(
        descending = True,
        element_type = ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_DESC,
        list_retriever = get_favorite_albums_by_release_date,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_element_favorite_albums_by_user_added_asc(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    return __handler_element_favorite_albums_common(
        descending = False,
        element_type = ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_ASC,
        list_retriever = get_favorite_albums_by_user_date_added,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_element_favorite_albums_by_user_added_desc(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    return __handler_element_favorite_albums_common(
        descending = True,
        element_type = ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_DESC,
        list_retriever = get_favorite_albums_by_user_date_added,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_tag_favorite_albums(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    tuple_array = [
        (
            ElementType.FAVORITE_ALBUMS_BY_ARTIST_ASC,
            "By Artist (Asc)",
            build_album_sort_criteria_by_artist,
            False),
        (
            ElementType.FAVORITE_ALBUMS_BY_ARTIST_DESC,
            "By Artist (Desc)",
            build_album_sort_criteria_by_artist,
            True),
        (
            ElementType.FAVORITE_ALBUMS_BY_TITLE_ASC,
            "By Title (Asc)",
            build_album_sort_criteria_by_name,
            False),
        (
            ElementType.FAVORITE_ALBUMS_BY_TITLE_DESC,
            "By Title (Desc)",
            build_album_sort_criteria_by_name,
            True),
        (
            ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_ASC,
            "By Release Date (Asc)",
            build_album_sort_criteria_by_release_date,
            False),
        (
            ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_DESC,
            "By Release Date (Desc)",
            build_album_sort_criteria_by_release_date,
            True),
        (
            ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_ASC,
            "By Date Added (Asc)",
            build_album_sort_criteria_by_user_date_added,
            False),
        (
            ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_DESC,
            "By Date Added (Desc)",
            build_album_sort_criteria_by_user_date_added,
            True)]
    tidal_session : TidalSession = get_session()
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
        entries.append(entry)
        descending : bool = current_tuple[3]
        sc_list_builder : Callable[[bool], list[AlbumSortCriteria]] = current_tuple[2]
        sc_list : list[AlbumSortCriteria] = sc_list_builder(descending)
        favorite_list : list[TidalAlbum] = tidal_session.user.favorites.albums()
        favorite_list.sort(key = cmp_to_key(lambda x, y : compare_favorite_album_by_criteria_list(sc_list, x, y)))
        first : TidalAlbum = favorite_list[0] if favorite_list and len(favorite_list) > 0 else None
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(first) if first else None, entry)
    return entries


def handler_favorite_artists_by_name_asc(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_favorite_artists_common(
        descending = False,
        element_type = ElementType.FAVORITE_ARTISTS_BY_NAME_ASC,
        list_retriever = get_favorite_artists_by_name,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_favorite_artists_by_name_desc(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_favorite_artists_common(
        descending = True,
        element_type = ElementType.FAVORITE_ARTISTS_BY_NAME_DESC,
        list_retriever = get_favorite_artists_by_name,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_favorite_artists_by_user_date_added_asc(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_favorite_artists_common(
        descending = False,
        element_type = ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_ASC,
        list_retriever = get_favorite_artists_by_user_date_added,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_favorite_artists_by_user_date_added_desc(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_favorite_artists_common(
        descending = True,
        element_type = ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_DESC,
        list_retriever = get_favorite_artists_by_user_date_added,
        objid = objid,
        item_identifier = item_identifier,
        entries = entries)


def handler_favorite_artists_common(
        descending : bool,
        element_type : ElementType,
        list_retriever : Callable[[TidalSession, bool, int, int], list[TidalArtist]],
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session : TidalSession = get_session()
    max_items : int = config.artists_per_page
    items : list[TidalArtist] = list_retriever(tidal_session, descending, max_items, offset)
    current : TidalArtist
    for current in items:
        entries.append(artist_to_entry(objid, artist = current))
    if len(items) >= max_items:
        next_button = create_next_button(
            objid = objid,
            element_type = element_type,
            element_id = element_type.getName(),
            next_offset = offset + max_items)
        entries.append(next_button)
    return entries


def handler_tag_favorite_artists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    tuple_array = [
        (
            ElementType.FAVORITE_ARTISTS_BY_NAME_ASC,
            "By Name (Asc)",
            build_artist_sort_criteria_by_name, False),
        (
            ElementType.FAVORITE_ARTISTS_BY_NAME_DESC,
            "By Name (Desc)",
            build_artist_sort_criteria_by_name, True),
        (
            ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_ASC,
            "By Date Added (Asc)",
            build_artist_sort_criteria_by_user_date_added, False),
        (
            ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_DESC,
            "By Date Added (Desc)",
            build_artist_sort_criteria_by_user_date_added, True)]
    tidal_session : TidalSession = get_session()
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
        entries.append(entry)
        descending : bool = current_tuple[3]
        sc_list_builder : Callable[[bool], list[ArtistSortCriteria]] = current_tuple[2]
        sc_list : list[ArtistSortCriteria] = sc_list_builder(descending)
        favorite_list : list[TidalArtist] = tidal_session.user.favorites.artists()
        favorite_list.sort(key = cmp_to_key(lambda x, y : compare_favorite_artist_by_criteria_list(sc_list, x, y)))
        first : TidalArtist = favorite_list[0] if favorite_list and len(favorite_list) > 0 else None
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(first) if first else None, entry)
    return entries


def handler_tag_favorite_tracks(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    tuple_array = [
        (ElementType.FAVORITE_TRACKS_NAVIGABLE, "My Tracks (Navigable)"),
        (ElementType.FAVORITE_TRACKS_LIST, "My Tracks (list)")]
    tidal_session : TidalSession = get_session()
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
        fav_tracks : list[TidalTrack] = tidal_session.user.favorites.tracks(limit = 10)
        random_track : TidalTrack = secrets.choice(fav_tracks) if fav_tracks else None
        select_album : TidalAlbum = tidal_session.album(random_track.album.id) if random_track else None
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(select_album) if select_album else None, entry)
        entries.append(entry)
    return entries


def handler_tag_all_playlists(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session : TidalSession = get_session()
    max_items : int = config.playlist_items_per_page
    playlists : list[TidalPlaylist] = tidal_session.user.playlist_and_favorite_playlists(offset = offset)
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
    tidal_session : TidalSession = get_session()
    playlists : list[TidalUserPlaylist] = tidal_session.user.playlists()
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
    tidal_session : TidalSession = get_session()
    last_played_tracks : list[PlayedTrack] = persistence.get_last_played_tracks(max_tracks = 20)
    most_played_tracks : list[PlayedTrack] = persistence.get_most_played_tracks(max_tracks = 20)
    most_played_albums : list[PlayedAlbum] = persistence.get_most_played_albums(max_albums = 10)
    random_most_played_album : PlayedAlbum = (
        secrets.choice(most_played_albums)
        if most_played_albums and len(most_played_albums) > 0
        else None)
    most_played_album : TidalAlbum = (tidal_util.try_get_album(
        tidal_session = tidal_session,
        album_id = random_most_played_album.album_id)
        if random_most_played_album
        else None)
    most_played_album_url : str = tidal_util.get_image_url(most_played_album) if most_played_album else None
    last_played_albums : list[str] = get_last_played_album_id_list(max_tracks = 10)
    random_last_played_album_id : str = (secrets.choice(last_played_albums)
        if last_played_albums and len(last_played_albums) > 0
        else None)
    random_last_played_album : TidalAlbum = (tidal_util.try_get_album(
        tidal_session = tidal_session,
        album_id = random_last_played_album_id)
        if random_last_played_album_id
        else None)
    random_last_played_album_url : str = (tidal_util.get_image_url(random_last_played_album)
        if random_last_played_album
        else None)
    get_url_of_random : Callable[[list[TidalAlbum]], str] = (lambda album_list:
        secrets.choice(album_list).image_url if album_list and len(album_list) > 0 else None)
    tuple_array = [
        (
            ElementType.RECENTLY_PLAYED_ALBUMS,
            "Recently played albums",
            random_last_played_album_url),
        (
            ElementType.MOST_PLAYED_ALBUMS,
            "Most Played Albums",
            most_played_album_url),
        (
            ElementType.RECENTLY_PLAYED_TRACKS_NAVIGABLE,
            "Recently played tracks (Navigable)",
            get_url_of_random(last_played_tracks)),
        (
            ElementType.RECENTLY_PLAYED_TRACKS_LIST,
            "Recently played tracks (List)",
            get_url_of_random(last_played_tracks)),
        (
            ElementType.MOST_PLAYED_TRACKS_NAVIGABLE,
            "Most played tracks (Navigable)",
            get_url_of_random(most_played_tracks)),
        (
            ElementType.MOST_PLAYED_TRACKS_LIST,
            "Most played tracks (List)",
            get_url_of_random(most_played_tracks))]
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


def handler_tag_listening_queue(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    tuple_array = [
        (ElementType.ALBUM_LISTEN_QUEUE, "Listening Queue: Albums")
    ]
    for current_tuple in tuple_array:
        identifier : ItemIdentifier = ItemIdentifier(
            current_tuple[0].getName(),
            current_tuple[1])
        id : str = identifier_util.create_objid(
            objid = objid,
            id = identifier_util.create_id_from_identifier(identifier))
        entry : dict[str, any] = upmplgutils.direntry(id,
            objid,
            current_tuple[1])
        select_album_id : str = __get_random_album_id_from_listen_queue()
        select_album : TidalAlbum = (tidal_util.try_get_album(get_session(), select_album_id)
                                     if select_album_id else None)
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(select_album) if select_album else None, entry)
        entries.append(entry)
    return entries


def handler_tag_categories(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    current : TidalItemList
    category_index : int = 0
    tidal_session : TidalSession = get_session()
    for current in get_categories(tidal_session = tidal_session):
        msgproc.log(f"handler_tag_categories processing category[{category_index}]: [{current.title}] "
                    f"type [{type(current).__name__ if current else None}]")
        entry = category_to_entry(
            objid = objid,
            tidal_session = tidal_session,
            category = current)
        entries.append(entry)
        category_index += 1
    return entries


def create_next_button(
        objid,
        element_type : ElementType,
        element_id : any,
        next_offset : int,
        other_keys : dict[ItemIdentifierKey, any] = {}) -> dict:
    next_identifier : ItemIdentifier = ItemIdentifier(element_type.getName(), element_id)
    next_identifier.set(ItemIdentifierKey.OFFSET, next_offset)
    k : ItemIdentifierKey
    for k, v in other_keys.items():
        next_identifier.set(k, v)
    next_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(next_identifier))
    next_entry : dict = upmplgutils.direntry(
        next_id,
        objid,
        title = "Next")
    return next_entry


def handler_element_mix(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    tidal_session : TidalSession = get_session()
    mix_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    mix : TidalMix = tidal_session.mix(mix_id)
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = item_identifier.get(
        ItemIdentifierKey.MAX_ITEMS,
        config.max_playlist_or_mix_items_per_page)
    tracks : list = mix.items()[offset:offset + max_items]
    track_number : int = offset + 1
    context : Context = Context()
    context.add(key = ContextKey.IS_MIX, value = True)
    for track in tracks:
        if not isinstance(track, TidalTrack): continue
        options : dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry = track_to_entry(
            objid,
            track_adapter = instance_tidal_track_adapter(
                tidal_session = tidal_session,
                track = track),
            options = options,
            context = context)
        track_number += 1
        entries.append(track_entry)
    success_count : int = context.get(ContextKey.SUCCESS_COUNT)
    known_tracks_count : int = context.get(ContextKey.KNOWN_TRACKS_COUNT)
    guessed_tracks_count : int = context.get(ContextKey.GUESSED_TRACKS_COUNT)
    get_stream_count : int = context.get(ContextKey.GET_STREAM_COUNT)
    msgproc.log(f"handler_element_mix finished with success_count [{success_count}] "
                f"Known [{known_tracks_count}] Guessed [{guessed_tracks_count}] "
                f"Get Stream Count [{get_stream_count}]")
    return entries


def follow_page_link(page_link : TidalPageLink) -> any:
    next = page_link
    while next:
        # msgproc.log(f"follow_page_link type of next is [{type(next).__name__}]")
        if isinstance(next, TidalPageLink):
            try:
                next = next.get()
            except Exception as next_exc:
                msgproc.log(f"Cannot execute next, exc [{next_exc}]")
                next = None
            # msgproc.log(f"  next found: [{'yes' if next else 'no'}] type: [{type(next).__name__ if next else None}]")
        else:
            break
    return next


def get_items_in_page_link(page_link : TidalPageLink) -> list[any]:
    items : list[any] = list()
    linked = follow_page_link(page_link)
    # msgproc.log(f"get_items_in_page_link linked_object is [{type(linked).__name__ if linked else None}]")
    if not linked: return items
    if isinstance(linked, TidalPage):
        # msgproc.log(f"get_items_in_page_link: found a Page")
        for current in linked:
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
    msgproc.log(f"handler_element_pagelink name [{thing_name}] "
                f"value [{thing_value}] category_title [{category_title}] "
                f"api_path [{api_path}]")
    tidal_session : TidalSession = get_session()
    try:
        page : TidalPage = tidal_session.page.get(api_path)
        if not page:
            msgproc.log("handler_element_pagelink page not found")
            return entries
        if page: page_to_entries(
            objid = objid,
            tidal_session = tidal_session,
            page = page,
            entries = entries)
    except Exception as ex:
        msgproc.log(f"handler_element_pagelink could not retrieve page at api_path [{api_path}] [{ex}]")
    return entries


def handler_element_page(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    thing_value : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    page : TidalPage = tidal_session.page.get(thing_value)
    for page_item in page:
        if isinstance(page_item, TidalPlaylist):
            entries.append(playlist_to_playlist_container(
                objid = objid,
                playlist = page_item))
        elif isinstance(page_item, TidalAlbum):
            if config.skip_non_stereo and not tidal_util.is_stereo(page_item):
                msgproc.log(tidal_util.not_stereo_skipmessage(page_item))
                continue
            entries.append(album_to_album_container(
                objid = objid,
                album = page_item))
        else:
            msgproc.log(f"handler_element_page: page_item of type [{type(page_item)}] not handled")
    return entries


def page_to_entries(objid, tidal_session : TidalSession, page : TidalPage, entries : list) -> list:
    # extracting items from page
    for current_page_item in page:
        try:
            # msgproc.log(f"page_to_entries type of current_page_item [{type(current_page_item).__name__}]")
            new_entry : dict = convert_page_item_to_entry(
                objid = objid,
                tidal_session = tidal_session,
                page_item = current_page_item)
            if new_entry: entries.append(new_entry)
            # set an image?
            if isinstance(current_page_item, TidalPageLink):
                item_list : list[any] = get_items_in_page_link(page_link = current_page_item)
                first_item : any = item_list[0] if item_list and len(item_list) > 0 else None
                if isinstance(first_item, TidalPlaylist):
                    image_url : str = tidal_util.get_image_url(first_item)
                    upnp_util.set_album_art_from_uri(album_art_uri = image_url, target = new_entry)
                else:
                    msgproc.log(f"page_to_entries type of current_page_item [{type(current_page_item).__name__}] "
                                f"first_item [{type(first_item).__name__ if first_item else None}] not handled")
            else:
                msgproc.log(f"page_to_entries type of current_page_item "
                            f"[{type(current_page_item).__name__}] "
                            f"first_item [{type(first_item).__name__ if first_item else None}] not handled")
        except Exception as ex:
            msgproc.log(f"page_to_entries could not convert type "
                        f"[{type(current_page_item).__name__ if current_page_item else None}] "
                        f"Exception [{ex}]")
    return entries


def convert_page_item_to_entry(objid, tidal_session : TidalSession, page_item : TidalPageItem) -> any:
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
            track_adapter = instance_tidal_track_adapter(
                tidal_session = tidal_session,
                track = track),
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


def get_first_not_stereo(audio_modes) -> str:
    msgproc.log(f"get_first_not_stereo [{audio_modes}] is_list "
                f"[{'yes' if isinstance(audio_modes, list) else 'no'}]")
    if not audio_modes:
        msgproc.log("audio_modes is None")
        return None
    if isinstance(audio_modes, list):
        msgproc.log("audio_modes is list")
        ml : list[str] = audio_modes
        m : str
        for m in ml if len(ml) > 0 else []:
            msgproc.log(f"  array comparing with {m} ...")
            if m != "STEREO":
                msgproc.log(f"  {m} different from 'STEREO'")
                return m
        return None
    # else it's a string
    msgproc.log(f"audio_modes is string {audio_modes}")
    return audio_modes if "STEREO" != audio_modes else None


def handler_element_album_container(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    album : TidalAlbum = None
    try:
        album = tidal_session.album(album_id)
    except Exception as ex:
        msgproc.log(f"Cannot load album with id [{album_id}] due to [{type(ex)}] [{ex}]")
        return entries
    album_name : str = album.name
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM.getName(),
        album_id)
    id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(identifier))
    in_favorites : bool = album_id in get_favorite_album_id_list(tidal_session = tidal_session)
    in_listen_queue : bool = persistence.is_in_album_listen_queue(album_id)
    album_entry_title : str = "Album" if config.titleless_single_album_view else album.name
    cached_tidal_quality : tidal_util.CachedTidalQuality = get_cached_audio_quality(album_id = album.id)
    badge : str = tidal_util.get_quality_badge(album = album, cached_tidal_quality = cached_tidal_quality)
    msgproc.log(f"handler_element_album_container album_id [{album_id}] "
                f"badge [{badge}] in_favorites [{in_favorites}] "
                f"in_listen_queue [{in_listen_queue}]")
    if badge:
        album_entry_title = f"{album_entry_title} [{badge}]"
    if in_favorites and config.badge_favorite_album:
        album_entry_title = f"{album_entry_title} [F]"
    if config.show_album_id:
        album_entry_title = f"{album_entry_title} [{album_id}]"
    entry = upmplgutils.direntry(id,
        objid,
        album_entry_title)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), entry)
    entries.append(entry)
    # add Album track entry
    album_tracks : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_TRACKS.getName(),
        album_id)
    album_tracks_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(album_tracks))
    album_tracks_entry : dict[str, any] = upmplgutils.direntry(album_tracks_id,
        objid,
        "Tracks")
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), album_tracks_entry)
    entries.append(album_tracks_entry)
    # add Artists
    artist_list : list[TidalArtist] = get_artist_list(album.artist, album.artists)
    for current in artist_list:
        artist : TidalArtist = tidal_session.artist(current.id)
        entries.append(artist_to_entry(objid = objid, artist = artist))
    fav_action_elem : ElementType
    fav_action_text : str
    fav_action_elem, fav_action_text = (
        (ElementType.FAV_ALBUM_DEL, "Remove from Favorites") if in_favorites else
        (ElementType.FAV_ALBUM_ADD, "Add to Favorites"))
    # msgproc.log(f"Album with id [{album_id}] name [{album_name}] "
    #             f"is in favorites: [{'yes' if in_favorites else 'no'}]")
    fav_action : ItemIdentifier = ItemIdentifier(
        fav_action_elem.getName(),
        album_id)
    fav_action_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(fav_action))
    fav_entry : dict[str, any] = upmplgutils.direntry(fav_action_id,
        objid,
        fav_action_text)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), fav_entry)
    entries.append(fav_entry)
    # button for listen queue action
    listen_queue_action_dict : dict[str, str] = (constants.listening_queue_action_del_dict
                                            if in_listen_queue
                                            else constants.listening_queue_action_add_dict)
    listen_queue_action : str = listen_queue_action_dict[constants.listening_queue_action_key]
    listen_queue_button_name : str = listen_queue_action_dict[constants.listening_queue_button_title_key]
    lqb_identifier : ItemIdentifier = ItemIdentifier(ElementType.ALBUM_LISTEN_QUEUE_ACTION.getName(), album_id)
    lqb_identifier.set(ItemIdentifierKey.LISTEN_QUEUE_ACTION, listen_queue_action)
    lqb_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(lqb_identifier))
    lqb_entry : dict = upmplgutils.direntry(
        lqb_id,
        objid,
        title = listen_queue_button_name)
    # use same album image for this button
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), lqb_entry)
    entries.append(lqb_entry)
    # end button for listen queue
    has_been_played : bool = persistence.album_has_been_played(album_id)
    msgproc.log(f"Album with id [{album_id}] name [{album_name}] has been played: "
                f"[{'yes' if has_been_played else 'no'}]")
    if has_been_played:
        # add entry for removing from stats
        rm_stats : ItemIdentifier = ItemIdentifier(
            ElementType.REMOVE_ALBUM_FROM_STATS.getName(),
            album_id)
        rm_stats_id : str = identifier_util.create_objid(
            objid = objid,
            id = identifier_util.create_id_from_identifier(rm_stats))
        rm_entry : dict[str, any] = upmplgutils.direntry(rm_stats_id,
            objid,
            "Remove from Statistics")
        # use same album image for this button
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album), rm_entry)
        entries.append(rm_entry)
    return entries


def handler_element_mix_container(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    mix_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    mix : TidalMix = tidal_session.mix(mix_id)
    return handle_element_mix_or_playlist_container(
        objid = objid,
        mix_or_playlist = mix,
        mix_or_playlist_size = len(mix.items()),
        element_type = ElementType.MIX,
        navigable_element_type = ElementType.MIX_NAVIGABLE,
        entries = entries)


def handler_element_playlist_container(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    playlist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    playlist : TidalPlaylist = tidal_session.playlist(playlist_id)
    return handle_element_mix_or_playlist_container(
        objid = objid,
        mix_or_playlist = playlist,
        mix_or_playlist_size = playlist.num_tracks,
        element_type = ElementType.PLAYLIST,
        navigable_element_type = ElementType.PLAYLIST_NAVIGABLE,
        entries = entries)


def handle_element_mix_or_playlist_container(
        objid,
        mix_or_playlist : any,
        mix_or_playlist_size : int,
        navigable_element_type : ElementType,
        element_type : ElementType,
        entries : list) -> list:
    # add navigable version
    navigable_identifier : ItemIdentifier = ItemIdentifier(
        navigable_element_type.getName(),
        mix_or_playlist.id)
    navigable_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(navigable_identifier))
    navigable_entry = upmplgutils.direntry(navigable_id,
        objid,
        "Navigable")
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(mix_or_playlist), navigable_entry)
    entries.append(navigable_entry)
    # BEGIN add artists in mix or playlist
    artists_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTISTS_IN_MIX_OR_PLAYLIST.getName(),
        mix_or_playlist.id)
    # store if it's a playlist or a mix
    artists_identifier.set(key = ItemIdentifierKey.UNDERLYING_TYPE, value = element_type.getName())
    artists_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(artists_identifier))
    artists_entry = upmplgutils.direntry(artists_id,
        objid,
        "Artists")
    # same art as the playlist/mix itself
    # we must try to avoid expensive calls here
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(mix_or_playlist), artists_entry)
    entries.append(artists_entry)
    # BEGIN add albums in mix or playlist
    albums_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUMS_IN_MIX_OR_PLAYLIST.getName(),
        mix_or_playlist.id)
    # store if it's a playlist or a mix
    albums_identifier.set(key = ItemIdentifierKey.UNDERLYING_TYPE, value = element_type.getName())
    albums_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(albums_identifier))
    albums_entry = upmplgutils.direntry(albums_id,
        objid,
        "Albums")
    # same art as the playlist/mix itself
    # we must try to avoid expensive calls here
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(mix_or_playlist), albums_entry)
    entries.append(albums_entry)
    # END add albums in mix or playlist
    # add segmented entries
    playlist_size : int = mix_or_playlist_size
    modulo : int = playlist_size % config.max_playlist_or_mix_items_per_page
    tile_count = int(playlist_size / config.max_playlist_or_mix_items_per_page) + (1 if modulo > 0 else 0)
    tile_idx : int
    for tile_idx in range(0, tile_count):
        segment_identifier : ItemIdentifier = ItemIdentifier(
            element_type.getName(),
            mix_or_playlist.id)
        offset : int = tile_idx * config.max_playlist_or_mix_items_per_page
        max_items : int = (config.max_playlist_or_mix_items_per_page
                           if modulo == 0 or tile_idx < (tile_count - 1)
                           else modulo)
        segment_identifier.set(ItemIdentifierKey.OFFSET, offset)
        segment_identifier.set(ItemIdentifierKey.MAX_ITEMS, max_items)
        segment_id : str = identifier_util.create_objid(
            objid = objid,
            id = identifier_util.create_id_from_identifier(segment_identifier))
        entry = upmplgutils.direntry(segment_id,
            objid,
            f"Items [{offset + 1} to {offset + max_items}]")
        # select a random item
        random_item_index : int = random.randint(offset, offset + max_items)
        random_item = None
        tile_0_track_list : list[TidalTrack] = list() if tile_idx == 0 else None
        if isinstance(mix_or_playlist, TidalPlaylist):
            playlist : TidalPlaylist = mix_or_playlist
            random_list = playlist.items(limit = 1, offset = random_item_index)
            random_item = random_list[0] if random_list and len(random_list) > 0 else None
            if tile_idx == 0:
                # prepare tile_0_track_list
                track_list : list[TidalTrack] = playlist.tracks()
                tile_0_track_list.extend(track_list)
        elif isinstance(mix_or_playlist, TidalMix):
            mix : TidalMix = mix_or_playlist
            random_item = mix.items()[random_item_index] if len(mix.items()) > random_item_index else None
            if tile_idx == 0:
                # prepare tile_0_track_list
                item_list : list[TidalTrack | TidalVideo] = mix.items()
                for item in item_list:
                    if isinstance(item, TidalTrack):
                        tile_0_track_list.append(item)
        if tile_idx == 0:
            # get two random items fromtile_0_track_list one for artists and one for albums
            rnd_artists : TidalTrack = secrets.choice(tile_0_track_list) if len(tile_0_track_list) else None
            rnd_albums : TidalTrack = secrets.choice(tile_0_track_list) if len(tile_0_track_list) else None
            if rnd_artists:
                upnp_util.set_album_art_from_uri(tidal_util.get_image_url(rnd_artists.album), artists_entry)
            if rnd_albums:
                upnp_util.set_album_art_from_uri(tidal_util.get_image_url(rnd_albums.album), albums_entry)
        if random_item:
            if isinstance(random_item, TidalTrack):
                random_track : TidalTrack = random_item
                random_item = random_track.album
            upnp_util.set_album_art_from_uri(tidal_util.get_image_url(random_item), entry)
        else:
            upnp_util.set_album_art_from_uri(tidal_util.get_image_url(mix_or_playlist), entry)
        entries.append(entry)
    return entries


def handler_element_albums_in_mix_or_playlist(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    mix_or_playlist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    initial_offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    prev_page_last_found_id : int = item_identifier.get(ItemIdentifierKey.LAST_FOUND_ID, None)
    underlying_type_str : str = item_identifier.get(ItemIdentifierKey.UNDERLYING_TYPE)
    underlying_type : ElementType = get_element_type_by_name(element_name = underlying_type_str)
    max_items_per_page : int = config.artists_per_page
    msgproc.log(f"handler_element_albums_in_mix_or_playlist for [{mix_or_playlist_id}] "
                f"of type [{underlying_type}] from offset [{initial_offset}]")
    tidal_session : TidalSession = get_session()
    tidal_obj : any = (tidal_session.playlist(mix_or_playlist_id)
        if ElementType.PLAYLIST == underlying_type
        else tidal_session.mix(mix_or_playlist_id))
    msgproc.log(f"handler_element_albums_in_mix_or_playlist tidal_obj [{type(tidal_obj)}]")
    id_extractor : Callable[[any], str] = lambda x : x.album.id if x and x.album else None
    album_list : list[str]
    last_offset : int
    finished : bool
    last_found_id : str
    album_list, last_offset, finished, last_found_id = tidal_util.load_unique_ids_from_mix_or_playlist(
        tidal_session = tidal_session,
        tidal_obj_id = mix_or_playlist_id,
        tidal_obj_type = underlying_type_str,
        id_extractor = id_extractor,
        max_id_list_length = max_items_per_page,
        previous_page_last_found_id = prev_page_last_found_id,
        initial_offset = initial_offset)
    needs_next : bool = not finished
    msgproc.log(f"handler_element_albums_in_mix_or_playlist for [{mix_or_playlist_id}] "
                f"of type [{underlying_type}] from offset [{initial_offset}] "
                f"got [{len(album_list)}] albums (needs_next [{needs_next}])")
    # create entries for albums
    for album_id in album_list:
        try:
            album : TidalAlbum = tidal_session.album(album_id)
            entries.append(album_to_album_container(
                objid = objid,
                album = album))
        except Exception as ex:
            msgproc.log(f"Cannot add album with id [{album_id}] [{type(ex)}] [{ex}]")
    if needs_next:
        # create next
        next_entry : dict[str, any] = create_next_button(
            objid = objid,
            element_type = ElementType.ALBUMS_IN_MIX_OR_PLAYLIST,
            element_id = mix_or_playlist_id,
            next_offset = last_offset + 1,
            other_keys = {
                ItemIdentifierKey.UNDERLYING_TYPE: underlying_type_str,
                ItemIdentifierKey.LAST_FOUND_ID: last_found_id
            })
        entries.append(next_entry)
    return entries


def handler_element_artists_in_mix_or_playlist(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    mix_or_playlist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    initial_offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    prev_page_last_found_id : int = item_identifier.get(ItemIdentifierKey.LAST_FOUND_ID, None)
    underlying_type_str : str = item_identifier.get(ItemIdentifierKey.UNDERLYING_TYPE)
    underlying_type : ElementType = get_element_type_by_name(element_name = underlying_type_str)
    max_items_per_page : int = config.artists_per_page
    msgproc.log(f"handler_element_albums_in_mix_or_playlist for [{mix_or_playlist_id}] "
                f"of type [{underlying_type}] from offset [{initial_offset}]")
    tidal_session : TidalSession = get_session()
    id_extractor : Callable[[any], str] = lambda x : x.artist.id if x and x.artist else None
    artist_list : list[str]
    last_offset : int
    finished : bool
    last_found_id : str
    artist_list, last_offset, finished, last_found_id = tidal_util.load_unique_ids_from_mix_or_playlist(
        tidal_session = tidal_session,
        tidal_obj_id = mix_or_playlist_id,
        tidal_obj_type = underlying_type_str,
        id_extractor = id_extractor,
        max_id_list_length = max_items_per_page,
        previous_page_last_found_id = prev_page_last_found_id,
        initial_offset = initial_offset)
    needs_next : bool = not finished
    msgproc.log(f"handler_element_artists_in_mix_or_playlist for [{mix_or_playlist_id}] "
                f"of type [{underlying_type}] from offset [{initial_offset}] "
                f"got [{len(artist_list)}] artists (needs_next [{needs_next}])")
    # create entries for artists
    for artist_id in artist_list:
        try:
            artist : TidalArtist = tidal_session.artist(artist_id)
            entries.append(artist_to_entry(
                objid = objid,
                artist = artist))
        except Exception as ex:
            msgproc.log(f"Cannot add artist with id [{artist_id}] [{type(ex)}] [{ex}]")
    if needs_next:
        # create next
        next_entry : dict[str, any] = create_next_button(
            objid = objid,
            element_type = ElementType.ARTISTS_IN_MIX_OR_PLAYLIST,
            element_id = mix_or_playlist_id,
            next_offset = last_offset + 1,
            other_keys = {
                ItemIdentifierKey.UNDERLYING_TYPE: underlying_type_str,
                ItemIdentifierKey.LAST_FOUND_ID: last_found_id
            })
        entries.append(next_entry)
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
    tidal_session : TidalSession = get_session()
    track : TidalTrack = tidal_session.track(track_id)
    track_options : dict[str, any] = dict()
    set_option(
        options = track_options,
        option_key = OptionKey.OVERRIDDEN_TRACK_NAME,
        option_value = "Track")
    entries.append(track_to_track_container(
        objid = objid,
        tidal_session = tidal_session,
        track = track,
        options = track_options))
    # favorite?
    in_fav : bool = is_favorite_track_id(tidal_session = tidal_session, track_id = track_id)
    msgproc.log(f"handler_element_mix_playlist_toptrack_navigable_item track [{track_id}] "
                f"favorite: [{in_fav}]")
    # add button to add or remove from favorites
    fav_button_action : str = constants.fav_action_del if in_fav else constants.fav_action_add
    fav_button_text : str = constants.fav_action_dict[fav_button_action][constants.fav_button_title_key]
    fav_action_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.TRACK_FAVORITE_ACTION.getName(),
        track_id)
    fav_action_identifier.set(ItemIdentifierKey.FAVORITE_ACTION, fav_button_action)
    fav_action_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(fav_action_identifier))
    fav_entry : dict[str, any] = upmplgutils.direntry(fav_action_id,
        objid,
        fav_button_text)
    album : TidalAlbum = tidal_util.try_get_album(tidal_session = tidal_session, album_id = track.album.id)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album) if album else None, fav_entry)
    entries.append(fav_entry)
    # add link to artists
    artist_list : list[TidalArtist] = get_artist_list(track.artist, track.artists)
    for current in artist_list:
        artist : TidalArtist = tidal_session.artist(current.id)
        entries.append(artist_to_entry(
            objid = objid,
            artist = artist))
    # add link to album
    if album:
        entries.append(album_to_album_container(
            objid = objid,
            album = album))
    # add remove from stats if needed
    entries = add_remove_track_from_stats_if_needed(
        objid=objid,
        track=track,
        album=album,
        entries=entries)
    return entries


def handler_element_mix_navigable(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    mix_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session : TidalSession = get_session()
    mix : TidalMix = tidal_session.mix(mix_id)
    tracks : list[TidalTrack] = mix.items()
    max_items_per_page : int = config.mix_items_per_page
    remaining_tracks = tracks[offset:]
    tracks = remaining_tracks[0:max_items_per_page]
    track_number : int = offset + 1
    for track in tracks:
        options : dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry = track_to_navigable_mix_item(
            objid,
            tidal_session = tidal_session,
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
    tidal_session : TidalSession = get_session()
    playlist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    playlist : TidalPlaylist = tidal_session.playlist(playlist_id)
    tracks : list[TidalTrack] = playlist.tracks()
    max_items_per_page : int = config.mix_items_per_page
    remaining_tracks = tracks[offset:]
    msgproc.log(f"handler_element_playlist_navigable count from offset [{offset}] is: [{len(remaining_tracks)}]")
    tracks = remaining_tracks[0:max_items_per_page]
    track_number : int = offset + 1
    for track in tracks:
        options : dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry : dict = None
        try:
            track_entry = track_to_navigable_playlist_item(
                objid,
                tidal_session = tidal_session,
                track = track,
                options = options)
        except Exception as ex:
            msgproc.log(f"handler_element_playlist_navigable Cannot create track entry for track_id [{track.id}] "
                        f"num [{track_number}] [{track.name}] [{track.album.id}] "
                        f"[{track.album.name}] Exception [{ex}]")
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
    max_items : int = item_identifier.get(
        ItemIdentifierKey.MAX_ITEMS,
        config.max_playlist_or_mix_items_per_page)
    tidal_session : TidalSession = get_session()
    playlist : TidalPlaylist = tidal_session.playlist(playlist_id)
    tracks : list[TidalTrack] = playlist.tracks(offset = offset, limit = max_items)
    track_number : int = offset + 1
    counter : int = 0
    context : Context = Context()
    context.add(key = ContextKey.IS_PLAYLIST, value = True)
    for track in tracks:
        options : dict[str, any] = dict()
        set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_number)
        track_entry : dict = None
        try:
            track_adapter : TrackAdapter = choose_track_adapter_by_tidal_track(
                tidal_session = tidal_session,
                track = track)
            track_entry = track_to_entry(
                objid = objid,
                track_adapter = track_adapter,
                options = options,
                context = context)
        except Exception as ex:
            msgproc.log(f"playlist_to_entries Cannot create track entry for track_id [{track.id}] "
                        f"num [{track_number}] [{track.name}] [{track.album.id}] "
                        f"[{track.album.name}] Exception [{ex}]")
        # let user know some tracks are missing
        track_number += 1
        counter += 1
        if track_entry: entries.append(track_entry)
        if max_items and counter == max_items: break
    success_count : int = context.get(ContextKey.SUCCESS_COUNT)
    known_tracks_count : int = context.get(ContextKey.KNOWN_TRACKS_COUNT)
    guessed_tracks_count : int = context.get(ContextKey.GUESSED_TRACKS_COUNT)
    get_stream_count : int = context.get(ContextKey.GET_STREAM_COUNT)
    msgproc.log(f"playlist_to_entries finished with success_count [{success_count}] "
                f"Known [{known_tracks_count}] Guessed [{guessed_tracks_count}] "
                f"Get Stream Count [{get_stream_count}]")
    return entries


def handler_element_album(
        objid,
        item_identifier : ItemIdentifier,
        entries : list) -> list:
    album_id : int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    page : int = item_identifier.get(ItemIdentifierKey.ALBUM_PAGE, None)
    offset : int = page * constants.default_max_album_tracks_per_page if page else 0
    tidal_session : TidalSession = get_session()
    album : TidalAlbum = tidal_session.album(album_id)
    is_multidisc_album : bool = tidal_util.is_multidisc_album(album)
    tracks : list[TidalTrack] = album.tracks()
    track_count : int = len(tracks)
    paged : bool = False
    if track_count > constants.default_max_album_tracks_per_page:
        paged = True
    msgproc.log(f"Album [{album_id}] multidisc: [{is_multidisc_album}] "
                f"num_tracks: [{len(tracks)}] paged: [{paged}] "
                f"page: [{page if page else 'None'}] "
                f"offset: [{offset}]")
    # msgproc.log("handler_element_album creating Context ...")
    context : Context = Context()
    context.add(key = ContextKey.IS_ALBUM, value = True)
    options : dict[str, any] = {}
    set_option(options, OptionKey.SKIP_TRACK_ARTIST, True)
    track_num : int = offset + 1
    track : TidalTrack
    try:
        for track in tracks:
            # msgproc.log(f"handler_element_album track {track_num}")
            set_option(options, OptionKey.FORCED_TRACK_NUMBER, track_num)
            tidal_track_adapter : TrackAdapter = choose_track_adapter_by_tidal_track(
                tidal_session = tidal_session,
                track = track)
            track_entry = track_to_entry(
                objid = objid,
                track_adapter = tidal_track_adapter,
                options = options,
                context = context)
            entries.append(track_entry)
            track_num += 1
    except Exception as ex:
        msgproc.log(f"handler_element_album add track failed due to [{type(ex)}] [{ex}]")
    success_count : int = context.get(ContextKey.SUCCESS_COUNT)
    known_tracks_count : int = context.get(ContextKey.KNOWN_TRACKS_COUNT)
    guessed_tracks_count : int = context.get(ContextKey.GUESSED_TRACKS_COUNT)
    assumed_from_first_count : int = context.get(ContextKey.ASSUMED_FROM_FIRST_ALBUM_TRACK_COUNT)
    get_stream_count : int = context.get(ContextKey.GET_STREAM_COUNT)
    msgproc.log(f"handler_element_album for id [{album_id}] finished with "
                f"success_count [{success_count}] out of [{track_count}] "
                f"Known [{known_tracks_count}] Guessed [{guessed_tracks_count}] "
                f"Assumed by first [{assumed_from_first_count}] Get Stream Count [{get_stream_count}]")
    return entries


def handler_element_artist_album_catch_all(
        objid,
        item_identifier : ItemIdentifier,
        album_extractor : Callable[[Optional[int], int], list[TidalAlbum]],
        entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = config.albums_per_page
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    artist : TidalArtist = tidal_session.artist(artist_id)
    if not artist: msgproc.log(f"Artist with id {artist_id} not found")
    current : TidalAlbum
    album_list : list[TidalAlbum] = album_extractor(artist, max_items, offset)
    options : dict[str, any] = dict()
    set_option(
        options = options,
        option_key = OptionKey.OMIT_ARTIST_TO_ALBUM_ENTRY_UNLESS_DIFFERENT,
        option_value = True)
    set_option(
        options = options,
        option_key = OptionKey.ALBUM_OMITTABLE_ARTIST_ID,
        option_value = artist_id)
    for current in album_list:
        if config.skip_non_stereo and not tidal_util.is_stereo(current):
            msgproc.log(tidal_util.not_stereo_skipmessage(current))
            continue
        entries.append(album_to_album_container(
            objid = objid,
            album = current,
            options = options))
    if album_list and len(album_list) == max_items:
        # add next button
        entries.append(create_next_button(
            objid = objid,
            element_type = get_element_type_by_name(item_identifier.get(ItemIdentifierKey.THING_NAME)),
            element_id = item_identifier.get(ItemIdentifierKey.THING_VALUE),
            next_offset = offset + max_items))
    return entries


def handler_element_artist_album_albums(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_element_artist_album_catch_all(
        objid,
        item_identifier = item_identifier,
        album_extractor = lambda x, limit, offset : x.get_albums(limit, offset),
        entries = entries)


def handler_element_artist_album_ep_singles(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_element_artist_album_catch_all(
        objid,
        item_identifier = item_identifier,
        album_extractor = lambda x, limit, offset : x.get_ep_singles(limit, offset),
        entries = entries)


def handler_element_artist_album_others(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    return handler_element_artist_album_catch_all(
        objid,
        item_identifier = item_identifier,
        album_extractor = lambda x, limit, offset : x.get_other(limit, offset),
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
    tidal_session : TidalSession = get_session()
    artist : TidalArtist = tidal_session.artist(artist_id)
    items : list[TidalArtist] = get_similar_artists(artist)
    current : TidalArtist
    for current in items if items else list():
        entries.append(artist_to_entry(objid = objid, artist = current))
    return entries


def add_tracks_to_navigable_entries(
        objid,
        tidal_session : TidalSession,
        items : list[TidalTrack],
        entries : list) -> list:
    current : TidalTrack
    for current in items if items else list():
        options : dict[str, any] = dict()
        set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
        entries.append(track_to_navigable_track(
            objid = objid,
            track_adapter = choose_track_adapter_by_tidal_track(
                tidal_session = tidal_session,
                track = current),
            options = options))
    return entries


def add_track_as_list_to_entries(
        objid,
        tidal_session : TidalSession,
        items : list[TidalTrack],
        entries : list) -> list:
    context : Context = Context()
    context.add(key = ContextKey.IS_PLAYLIST, value = True)
    current : TidalTrack
    track_num : int = 1
    for current in items if items else list():
        options : dict[str, any] = dict()
        set_option(options = options, option_key = OptionKey.FORCED_TRACK_NUMBER, option_value = track_num)
        entries.append(track_to_entry(
            objid = objid,
            track_adapter = choose_track_adapter_by_tidal_track(
                tidal_session = tidal_session,
                track = current),
            options = options,
            context = context))
        track_num += 1
    return entries


def handler_element_favorite_tracks_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    tidal_session : TidalSession = get_session()
    items : list[TidalTrack] = tidal_session.user.favorites.tracks(limit = max_items, offset = offset)
    entries = add_tracks_to_navigable_entries(
        objid = objid,
        tidal_session = tidal_session,
        items = items,
        entries = entries)
    if len(items) == max_items:
        next_button = create_next_button(
            objid = objid,
            element_type = ElementType.FAVORITE_TRACKS_NAVIGABLE,
            element_id = ElementType.FAVORITE_TRACKS_NAVIGABLE.getName(),
            next_offset = offset + max_items)
        entries.append(next_button)
    return entries


def handler_element_favorite_tracks_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    tidal_session : TidalSession = get_session()
    items : list[TidalTrack] = list()
    offset : int = 0
    limit : int = 100
    while True:
        tracks : list[TidalTrack] = tidal_session.user.favorites.tracks(offset = offset, limit = limit)
        current : TidalTrack
        for current in tracks if tracks else list():
            items.append(current)
        if not tracks or len(tracks) < limit: break
        offset += limit
    return add_track_as_list_to_entries(
        objid = objid,
        tidal_session = tidal_session,
        items = items,
        entries = entries)


def handler_element_artist_top_tracks_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    max_items : int = 50
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    artist : TidalArtist = tidal_session.artist(artist_id)
    items : list[TidalTrack] = get_top_tracks(
        artist = artist,
        limit = max_items,
        offset = offset)
    entries = add_tracks_to_navigable_entries(
        objid = objid,
        tidal_session = tidal_session,
        items = items,
        entries = entries)
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
    tidal_session : TidalSession = get_session()
    artist : TidalArtist = tidal_session.artist(artist_id)
    items : list[TidalTrack] = get_top_tracks(artist)
    return add_track_as_list_to_entries(
        objid = objid,
        tidal_session = tidal_session,
        items = items,
        entries = entries)


def handler_element_artist_radio_list(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    artist : TidalArtist = tidal_session.artist(artist_id)
    items : list[TidalTrack] = get_radio(artist)
    return add_track_as_list_to_entries(
        objid = objid,
        tidal_session = tidal_session,
        items = items,
        entries = entries)


def handler_element_artist_radio_navigable(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    artist : TidalArtist = tidal_session.artist(artist_id)
    items : list[TidalTrack] = get_radio(artist)
    return add_tracks_to_navigable_entries(
        objid = objid,
        tidal_session = tidal_session,
        items = items,
        entries = entries)


def get_favorite_artist_id_list(tidal_session : TidalSession) -> list[str]:
    item_list : list[str] = list()
    offset : int = 0
    limit : int = 100
    while True:
        fav_list : list[TidalArtist] = tidal_session.user.favorites.artists(limit = limit, offset = offset)
        current : TidalArtist
        for current in fav_list:
            item_list.append(current.id)
        if not fav_list or len(fav_list) < limit: break
        offset += limit
    return item_list


def get_favorite_album_id_list(tidal_session : TidalSession) -> list[str]:
    item_list : list[str] = list()
    offset : int = 0
    limit : int = 100
    while True:
        fav_list : list[TidalAlbum] = tidal_session.user.favorites.albums(limit = limit, offset = offset)
        current : TidalAlbum
        for current in fav_list if fav_list else list():
            item_list.append(current.id)
        if not fav_list or len(fav_list) < limit: break
        offset += limit
    return item_list


def get_favorite_track_id_list(tidal_session : TidalSession) -> list[int]:
    item_list : list[str] = list()
    offset : int = 0
    limit : int = 100
    while True:
        fav_list : list[TidalTrack] = tidal_session.user.favorites.tracks(limit = limit, offset = offset)
        current : TidalTrack
        for current in fav_list if fav_list else list():
            item_list.append(current.id)
        if not fav_list or len(fav_list) < limit: break
        offset += limit
    return item_list


def is_favorite_track_id(tidal_session : TidalSession, track_id : any) -> bool:
    if not track_id: return False
    fav_list : list[int] = get_favorite_track_id_list(tidal_session)
    if isinstance(track_id, int): return track_id in fav_list
    if isinstance(track_id, str):
        current : int
        for current in fav_list:
            if str(current) == track_id: return True
    return False


def handler_element_artist_add_to_fav(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    if artist_id not in get_favorite_artist_id_list(tidal_session = tidal_session):
        tidal_session.user.favorites.add_artist(artist_id = artist_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(),
        artist_id)
    return handler_element_artist(objid, item_identifier = identifier, entries = entries)


def handler_element_album_add_to_fav(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    if album_id not in get_favorite_album_id_list(tidal_session = tidal_session):
        tidal_session.user.favorites.add_album(album_id = album_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_CONTAINER.getName(),
        album_id)
    return handler_element_album_container(objid, item_identifier = identifier, entries = entries)


def handler_element_artist_del_from_fav(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    if artist_id in get_favorite_artist_id_list(tidal_session = tidal_session):
        tidal_session.user.favorites.remove_artist(artist_id = artist_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST.getName(),
        artist_id)
    return handler_element_artist(objid, item_identifier = identifier, entries = entries)


def handler_element_album_del_from_fav(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    if album_id in get_favorite_album_id_list(tidal_session = tidal_session):
        tidal_session.user.favorites.remove_album(album_id = album_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_CONTAINER.getName(),
        album_id)
    return handler_element_album_container(objid, item_identifier = identifier, entries = entries)


def get_artist_albums_image_url(tidal_session : TidalSession, artist_id : str) -> str:
    return get_artist_albums_by_album_extractor_image_url(
        tidal_session = tidal_session,
        artist_id = artist_id,
        extractor = lambda artist: artist.get_albums())


def get_artist_albums_ep_singles_image_url(tidal_session : TidalSession, artist_id : str) -> str:
    return get_artist_albums_by_album_extractor_image_url(
        tidal_session = tidal_session,
        artist_id = artist_id,
        extractor = lambda artist: artist.get_ep_singles())


def get_artist_albums_others_image_url(tidal_session : TidalSession, artist_id : str) -> str:
    return get_artist_albums_by_album_extractor_image_url(
        tidal_session = tidal_session,
        artist_id = artist_id,
        extractor = lambda artist: artist.get_other())


def get_artist_albums_by_album_extractor_image_url(
        tidal_session : TidalSession,
        artist_id : str,
        extractor : Callable[[TidalArtist], list[TidalAlbum]]) -> str:
    try:
        artist : TidalArtist = tidal_session.artist(artist_id)
        album_list : list[TidalAlbum] = extractor(artist)
        return choose_album_image_url(album_list)
    except Exception:
        msgproc.log(f"Cannot get albums for artist_id [{artist.id}]")


def get_artist_top_tracks_image_url(tidal_session : TidalSession, artist_id : str) -> str:
    try:
        artist : TidalArtist = tidal_session.artist(artist_id)
        tracks : list[TidalTrack] = artist.get_top_tracks() if artist else None
        select : TidalTrack = secrets.choice(tracks) if tracks and len(tracks) > 0 else None
        album : TidalAlbum = tidal_session.album(select.album.id) if select else None
        return tidal_util.get_image_url(album) if album else None
    except Exception:
        msgproc.log(f"Cannot get top tracks image for artist_id [{artist.id}]")


def get_artist_radio_image_url(tidal_session : TidalSession, artist_id : str) -> str:
    try:
        artist : TidalArtist = tidal_session.artist(artist_id)
        tracks : list[TidalTrack] = artist.get_radio() if artist else None
        select : TidalTrack = secrets.choice(tracks) if tracks and len(tracks) > 0 else None
        album : TidalAlbum = tidal_session.album(select.album.id) if select else None
        return tidal_util.get_image_url(album) if album else None
    except Exception:
        msgproc.log(f"Cannot get artist radio image for artist_id [{artist.id}]")


def choose_album_image_url(album_list : list[TidalAlbum]) -> str:
    select : TidalAlbum = secrets.choice(album_list) if album_list and len(album_list) > 0 else None
    return tidal_util.get_image_url(select) if select else None


def get_similar_artists_image_url(tidal_session : TidalSession, artist_id : str) -> str:
    try:
        artist : TidalArtist = tidal_session.artist(artist_id)
        similar_artist_list : list[TidalArtist] = artist.get_similar() if artist else None
        select : TidalArtist = (secrets.choice(similar_artist_list)
            if similar_artist_list and len(similar_artist_list) > 0
            else None)
        return tidal_util.get_image_url(select) if select else None
    except Exception:
        msgproc.log(f"Cannot get similar artists for artist_id [{artist.id}]")


def handler_element_artist_related(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    missing_artist_art : bool = item_identifier.get(ItemIdentifierKey.MISSING_ARTIST_ART)
    tidal_session : TidalSession = get_session()
    artist : TidalArtist = tidal_session.artist(artist_id)
    # artist_name : str = artist.name
    if not artist:
        msgproc.log(f"Artist with id {artist_id} not found")
        return entries
    msgproc.log(f"Loading page for artist_id: [{artist_id}] artist.id: [{artist.id}] artist.name: [{artist.name}]")
    album_tuple_array = [
        (ElementType.ARTIST_TOP_TRACKS_NAVIGABLE, "Top Tracks", get_artist_top_tracks_image_url),
        (ElementType.ARTIST_TOP_TRACKS_LIST, "Top Tracks (List)", get_artist_top_tracks_image_url),
        (ElementType.ARTIST_RADIO_NAVIGABLE, "Radio", get_artist_radio_image_url),
        (ElementType.ARTIST_RADIO_LIST, "Radio (List)", get_artist_radio_image_url),
        (ElementType.SIMILAR_ARTISTS, "Similar Artists", get_similar_artists_image_url),
    ]
    for album_tuple in album_tuple_array:
        msgproc.log(f"handler_element_artist - artist_id {artist_id} current tuple [{album_tuple[0]}]")
        if missing_artist_art: continue
        try:
            album_art_uri : str = album_tuple[2](tidal_session, artist_id) if album_tuple[2] else None
            identifier : ItemIdentifier = ItemIdentifier(
                album_tuple[0].getName(),
                artist_id)
            id : str = identifier_util.create_objid(
                objid = objid,
                id = identifier_util.create_id_from_identifier(identifier))
            entry = upmplgutils.direntry(id,
                objid,
                album_tuple[1])
            upnp_util.set_album_art_from_uri(album_art_uri, entry)
            entries.append(entry)
        except Exception:
            msgproc.log(f"handler_element_artist_related - cannot create [{album_tuple[0]}]")
    return entries


def handler_element_artist(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    missing_artist_art : bool = item_identifier.get(ItemIdentifierKey.MISSING_ARTIST_ART)
    tidal_session : TidalSession = get_session()
    artist : TidalArtist = tidal_session.artist(artist_id)
    artist_name : str = artist.name
    if not artist:
        msgproc.log(f"Artist with id {artist_id} not found")
        return entries
    msgproc.log(f"Loading page for artist_id: [{artist_id}] artist.id: [{artist.id}] artist.name: [{artist.name}]")
    album_tuple_array = [
        (ElementType.ARTIST_ALBUM_ALBUMS, "Albums", get_artist_albums_image_url),
        (ElementType.ARTIST_ALBUM_EP_SINGLES, "EP and Singles", get_artist_albums_ep_singles_image_url),
        (ElementType.ARTIST_ALBUM_OTHERS, "Other Albums", get_artist_albums_others_image_url)]
    for album_tuple in album_tuple_array:
        msgproc.log(f"handler_element_artist - artist_id {artist_id} current tuple [{album_tuple[0]}]")
        try:
            album_art_uri : str = album_tuple[2](tidal_session, artist_id) if album_tuple[2] else None
            # if there is no album_art_uri, it means there are no albums in the category
            if not album_art_uri: continue
            identifier : ItemIdentifier = ItemIdentifier(
                album_tuple[0].getName(),
                artist_id)
            id : str = identifier_util.create_objid(
                objid = objid,
                id = identifier_util.create_id_from_identifier(identifier))
            entry = upmplgutils.direntry(id,
                objid,
                album_tuple[1])
            upnp_util.set_album_art_from_uri(album_art_uri, entry)
            entries.append(entry)
        except Exception:
            msgproc.log(f"handler_element_artist - cannot create [{album_tuple[0]}]")
    # add related node
    related_identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ARTIST_FOCUS.getName(),
        artist_id)
    related_identifier.set(ItemIdentifierKey.MISSING_ARTIST_ART, missing_artist_art)
    related_identifier_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(related_identifier))
    entry = upmplgutils.direntry(
        related_identifier_id,
        objid,
        "Focus")
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(artist), entry)
    entries.append(entry)
    in_favorites : bool = artist.id in get_favorite_artist_id_list(tidal_session = tidal_session)
    fav_action_elem : ElementType
    fav_action_text : str
    fav_action_elem, fav_action_text = (
        (ElementType.FAV_ARTIST_DEL, "Remove from Favorites") if in_favorites
        else (ElementType.FAV_ARTIST_ADD, "Add to Favorites"))
    msgproc.log(f"Artist with id [{artist_id}] name [{artist_name}] is in favorites: "
                f"[{'yes' if in_favorites else 'no'}]")
    fav_action : ItemIdentifier = ItemIdentifier(
        fav_action_elem.getName(),
        artist_id)
    fav_action_id : str = identifier_util.create_objid(
        objid = objid,
        id = identifier_util.create_id_from_identifier(fav_action))
    fav_entry : dict[str, any] = upmplgutils.direntry(fav_action_id,
        objid,
        fav_action_text)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(artist), fav_entry)
    entries.append(fav_entry)
    return entries


def add_remove_track_from_stats_if_needed(
        objid,
        track : TidalTrack,
        album: TidalAlbum,
        entries : list) -> list:
    has_been_played : bool = persistence.track_has_been_played(track.id)
    msgproc.log(f"Track with id [{track.id}] name [{track.name}] has been tracked: "
                f"[{'yes' if has_been_played else 'no'}]")
    if has_been_played:
        # add entry for removing from stats
        rm_stats : ItemIdentifier = ItemIdentifier(
            ElementType.REMOVE_TRACK_FROM_STATS.getName(),
            track.id)
        rm_stats_id : str = identifier_util.create_objid(
            objid = objid,
            id = identifier_util.create_id_from_identifier(rm_stats))
        rm_entry : dict[str, any] = upmplgutils.direntry(rm_stats_id,
            objid,
            "Remove from Statistics")
        entries.append(rm_entry)
        upnp_util.set_album_art_from_uri(tidal_util.get_image_url(album) if album else None, rm_entry)
    return entries


def handler_element_track_container(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    track_id : int = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    track : TidalTrack = tidal_session.track(track_id)
    track_entry = track_to_entry(
        objid = objid,
        track_adapter = instance_tidal_track_adapter(
            tidal_session = tidal_session,
            track = track))
    entries.append(track_entry)
    return entries


def handler_element_category(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    tidal_session : TidalSession = get_session()
    select_category : str = item_identifier.get(ItemIdentifierKey.CATEGORY_KEY)
    category : TidalItemList = get_category(
        tidal_session = tidal_session,
        category_name = select_category)
    if not category:
        msgproc.log("handler_element_category category not set")
        return entries
    obj = get_category(
        tidal_session = tidal_session,
        category_name = select_category)
    if not obj:
        msgproc.log(f"handler_element_category cannot load category [{select_category}]")
        return entries
    if isinstance(obj, TidalFeaturedItems):
        # msgproc.log(f"handler_element_category category [{select_category}] as TidalFeaturedItems")
        featured_items : TidalFeaturedItems = obj
        for fi_item in featured_items.items:
            if fi_item.type == constants.featured_type_name_playlist:
                playlist : TidalPlaylist = tidal_session.playlist(fi_item.artifact_id)
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
            # msgproc.log(f"handler_element_category [{category.title}] [{index}] [{item_type}] [{item_name}]")
            # msgproc.log(f"handler_element_category categories[{select_category}].item[{index}] type is [{item_type}]")
            if isinstance(item, TidalPageLink):
                page_link : TidalPageLink = item
                page_link_entry : dict = pagelink_to_entry(objid, category = category, page_link = item)
                entries.append(page_link_entry)
                # TODO maybe extract method for getting image for a PageLink
                tile_image : TileImage = load_tile_image_unexpired(TileType.PAGE_LINK, page_link.api_path)
                page_link_image_url : str = tile_image.tile_image if tile_image else None
                if not page_link_image_url:
                    items_in_page : list = get_items_in_page_link(page_link)
                    for current in items_in_page if items_in_page else list():
                        if (
                                isinstance(current, TidalPlaylist) or
                                isinstance(current, TidalAlbum) or
                                isinstance(current, TidalArtist)):
                            # get an image from that
                            page_link_image_url = tidal_util.get_image_url(current)
                            persistence.save_tile_image(TileType.PAGE_LINK, page_link.api_path, page_link_image_url)
                            # we only need the first
                            break
                        else:
                            msgproc.log(f"handler_element_category [{category.title}] [{index}] "
                                        f"[{item_type}] [{item_name}] [{page_link.api_path}] "
                                        f"num_items [{len(items_in_page)}] "
                                        f"current [{type(current).__name__ if current else None}]")
                upnp_util.set_album_art_from_uri(page_link_image_url, page_link_entry)
            elif isinstance(item, TidalMix):
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                entries.append(mix_to_mix_container(objid, mix = item))
            elif isinstance(item, TidalTrack):
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                options : dict[str, any] = dict()
                set_option(options, OptionKey.SKIP_TRACK_NUMBER, True)
                entries.append(track_to_track_container(
                    objid = objid,
                    tidal_session = tidal_session,
                    track = item,
                    options = options))
            elif isinstance(item, TidalPlaylist):
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                entries.append(playlist_to_playlist_container(
                    objid = objid,
                    playlist = item))
            elif isinstance(item, TidalAlbum):
                album : TidalAlbum = item
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                options : dict[str, any] = dict()
                entries.append(album_to_album_container(objid, album = album))
            elif isinstance(item, TidalArtist):
                # msgproc.log(f"handler_element_category [{category.title}] [{item_type}] [{item_name}]")
                entries.append(artist_to_entry(objid, artist = item))
            else:
                msgproc.log(f"handler_element_category [{category.title}] [{index}] [{item_type}] "
                            f"[{item_name}] was not handled!")
            index += 1
    return entries


# this allows kodi to work with the plugin
def track_data_to_entry(objid, entry_id : str, track : TidalTrack) -> dict:
    entry : dict = {}
    entry['id'] = entry_id
    entry['pid'] = track.id
    upnp_util.set_class_music_track(entry)
    upnp_util.set_uri(build_intermediate_url(track.id), entry)
    track_adapter : TrackAdapter = choose_track_adapter_by_tidal_track(
        tidal_session = get_session(),
        track = track)
    if config.enable_read_stream_metadata:
        bit_depth : int = track_adapter.get_bit_depth()
        sample_rate : int = track_adapter.get_sample_rate()
        upnp_util.set_bit_depth(bit_depth, entry)
        upnp_util.set_sample_rate(sample_rate, entry)
        upnp_util.set_bit_rate(
            bitrate=calc_bitrate(
                tidal_quality=track.audio_quality,
                bit_depth=bit_depth,
                sample_rate=sample_rate),
            target=entry)
    # channels. I could use AudioMode but I can't exactly say how many channels are delivered
    # so I am assuming two, looks like a decent fallback for now
    upnp_util.set_channels(2, entry)
    title : str = track.name
    upnp_util.set_track_title(title, entry)
    upnp_util.set_album_title(track.album.name, entry)
    upnp_util.set_object_type_item(entry)
    upnp_util.set_disc_number(track.volume_num, entry)
    upnp_util.set_track_number(track.track_num, entry)
    upnp_util.set_artist(track.artist.name, entry)
    upnp_util.set_mime_type(tidal_util.get_mime_type(track.audio_quality), entry)
    upnp_util.set_album_art_from_uri(tidal_util.get_image_url(track.album), entry)
    upnp_util.set_duration(track.duration, entry)
    return entry


def handler_element_track_simple(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    track_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    track : TidalTrack = tidal_session.track(track_id)
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
        played_track.track_id is not None and
        played_track.album_id is not None and
        played_track.album_track_count is not None and
        played_track.track_name is not None and
        played_track.track_duration is not None and
        played_track.track_num is not None and
        played_track.volume_num is not None and
        played_track.album_num_volumes is not None and
        played_track.album_name is not None and
        played_track.audio_quality is not None and
        played_track.album_artist_name is not None and
        played_track.image_url is not None and
        played_track.explicit is not None and
        played_track.artist_name is not None and
        played_track.bit_depth is not None and
        played_track.sample_rate is not None)


def played_track_list_to_entries_raw(
        objid,
        played_tracks : list[PlayedTrack],
        options : dict[str, any],
        entries : list) -> list:
    tidal_session : TidalSession = get_session()
    context : Context = Context()
    current : PlayedTrack
    set_option(
        options = options,
        option_key = OptionKey.SKIP_TRACK_NUMBER,
        option_value = True)
    track_num : int = 1
    # limit maximum number of reload from tidal when some data is missing
    max_reload_count : int = 10
    reload_count : int = 0
    for current in played_tracks if played_tracks else list():
        track_adapter : TrackAdapter = (
            choose_track_adapter(
                tidal_session = tidal_session,
                played_track = current)
            if reload_count < max_reload_count
            else PlayedTrackAdapter(current))
        if isinstance(track_adapter, TidalTrackAdapter):
            # a reload has happened
            reload_count += 1
        out_options : dict[str, any] = dict()
        set_option(
            options = out_options,
            option_key = OptionKey.FORCED_TRACK_NUMBER,
            option_value = track_num)
        as_container : bool = get_option(
            options = options,
            option_key = OptionKey.ENTRY_AS_CONTAINER)
        if as_container:
            track_entry : dict = track_to_navigable_track(
                objid = objid,
                track_adapter = track_adapter,
                options = out_options)
            entries.append(track_entry)
        else:
            track_entry : dict = track_to_entry(
                objid = objid,
                track_adapter = track_adapter,
                options = out_options,
                context = context)
            entries.append(track_entry)
        track_num += 1
    return entries


def played_track_list_to_entries(objid, played_tracks : list[PlayedTrack], entries : list) -> list:
    options : dict[str, any] = dict()
    set_option(
        options = options,
        option_key = OptionKey.ENTRY_AS_CONTAINER,
        option_value = True)
    return played_track_list_to_entries_raw(
        objid = objid,
        played_tracks = played_tracks,
        options = options,
        entries = entries)


def played_track_list_to_list_entries(objid, played_tracks : list[PlayedTrack], entries : list) -> list:
    options : dict[str, any] = dict()
    set_option(
        options = options,
        option_key = OptionKey.ENTRY_AS_CONTAINER,
        option_value = False)
    return played_track_list_to_entries_raw(
        objid = objid,
        played_tracks = played_tracks,
        options = options,
        entries = entries)


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
        if current_album_id not in album_id_set:
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
    persistence.remove_track_from_played_tracks(track_id)
    msgproc.log(f"Removed {track_id} from playback statistics.")
    tidal_session : TidalSession = get_session()
    track : TidalTrack = tidal_session.track(track_id)
    entries.append(track_to_navigable_track(
        objid = objid,
        track_adapter = instance_tidal_track_adapter(
            tidal_session = tidal_session,
            track = track)))
    return entries


def handler_element_remove_album_from_stats(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    if not album_id: return entries
    msgproc.log(f"Removing {album_id} from playback statistics ...")
    persistence.remove_album_from_played_tracks(album_id)
    msgproc.log(f"Removed {album_id} from playback statistics.")
    album : TidalAlbum = tidal_session.album(album_id)
    entries.append(album_to_album_container(objid = objid, album = album))
    return entries


def handler_element_recently_played_albums(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    offset : int = item_identifier.get(ItemIdentifierKey.OFFSET, 0)
    tidal_session : TidalSession = get_session()
    # TODO remove hardcoded value
    max_tracks : int = 10000
    albums_per_page : int = config.albums_per_page
    next_needed : bool = False
    album_id_list : list[str] = get_last_played_album_id_list(max_tracks = max_tracks)
    from_offset_album_id_list : list[str] = album_id_list[offset:]
    if len(from_offset_album_id_list) >= albums_per_page: next_needed = True
    page_album_id_list : list[str] = from_offset_album_id_list[0:albums_per_page]
    current_album_id : str
    for current_album_id in page_album_id_list:
        try:
            album : TidalAlbum = tidal_session.album(current_album_id)
            if (config.skip_non_stereo and
                    not tidal_util.is_stereo(album)):
                msgproc.log(tidal_util.not_stereo_skipmessage(album))
                continue
            entries.append(album_to_album_container(
                objid = objid,
                album = album))
        except Exception as ex:
            msgproc.log(f"Cannot add album with id [{current_album_id}] due to [{type(ex)}] [{ex}]")
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
    tidal_session : TidalSession = get_session()
    albums_per_page : int = config.albums_per_page
    # TODO remove hardcoded value
    max_albums : int = 1000
    next_needed : bool = True
    items : list[PlayedAlbum] = persistence.get_most_played_albums(max_albums = max_albums)
    from_offset_album_list : list[PlayedAlbum] = items[offset:]
    if len(from_offset_album_list) < albums_per_page: next_needed = False
    page_played_album_list : list[PlayedAlbum] = from_offset_album_list[0:albums_per_page]
    current : PlayedAlbum
    for current in page_played_album_list:
        try:
            album : TidalAlbum = tidal_session.album(current.album_id)
            if config.skip_non_stereo and not tidal_util.is_stereo(album):
                msgproc.log(tidal_util.not_stereo_skipmessage(album))
                continue
            entries.append(album_to_album_container(objid = objid, album = album))
        except Exception as ex:
            msgproc.log(f"Cannot add album with id [{current.album_id}] due to [{type(ex)}] [{ex}]")
    if next_needed:
        next_button = create_next_button(
            objid = objid,
            element_type = ElementType.MOST_PLAYED_ALBUMS,
            element_id = ElementType.MOST_PLAYED_ALBUMS.getName(),
            next_offset = offset + albums_per_page)
        entries.append(next_button)
    return entries


def handler_album_tracks_action(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    tidal_session : TidalSession = get_session()
    album : TidalAlbum = tidal_util.try_get_album(tidal_session = tidal_session, album_id = album_id)
    if not album: return entries
    options: dict[str, any] = dict()
    set_option(
        options = options,
        option_key = OptionKey.TRACK_OMITTABLE_ARTIST_NAME,
        option_value = album.artist.name)
    track : TidalTrack
    for track in album.tracks():
        try:
            track_entry : dict[str, any] = track_to_navigable_track(
                objid = objid,
                track_adapter = instance_tidal_track_adapter(
                    tidal_session = tidal_session,
                    track = track),
                options = options)
            if track_entry: entries.append(track_entry)
        except Exception as ex:
            msgproc.log(f"handler_album_tracks_action cannot load "
                        f"track_id [{track.id}] from album_id [{album_id}] "
                        f"[{type(ex)}] [{ex}]")
    return entries


def handler_album_listen_queue(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_list : list[str] = persistence.get_album_listen_queue()
    tidal_session : TidalSession = get_session()
    album_id : str
    for album_id in album_list:
        try:
            album : TidalAlbum = tidal_session.album(album_id)
            entries.append(album_to_album_container(objid, album))
        except Exception as ex:
            msgproc.log(f"handler_album_listen_queue cannot load album [{album_id}] [{type(ex)}] [{ex}]")
    return entries


def handler_album_listen_queue_action(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    album_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    listen_queue_action : str = item_identifier.get(ItemIdentifierKey.LISTEN_QUEUE_ACTION)
    msgproc.log(f"handler_album_listen_queue_action on [{album_id} -> [{listen_queue_action}]")
    # perform requested action
    if constants.listening_queue_action_add == listen_queue_action:
        persistence.add_to_album_listen_queue(album_id)
        pass
    if constants.listening_queue_action_del == listen_queue_action:
        persistence.remove_from_album_listen_queue(album_id)
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.ALBUM_CONTAINER.getName(),
        album_id)
    return handler_element_album_container(objid, item_identifier = identifier, entries = entries)


def handler_track_favorite_action(objid, item_identifier : ItemIdentifier, entries : list) -> list:
    track_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    action : str = item_identifier.get(ItemIdentifierKey.FAVORITE_ACTION)
    if constants.fav_action_add == action:
        msgproc.log(f"handler_track_favorite_action adding track [{track_id}] to favorites ...")
        get_session().user.favorites.add_track(track_id)
    elif constants.fav_action_del == action:
        msgproc.log(f"handler_track_favorite_action removing track [{track_id}] from favorites ...")
        get_session().user.favorites.remove_track(track_id)
    else:
        msgproc.log(f"handler_track_favorite_action invalid action [{action}]")
    identifier : ItemIdentifier = ItemIdentifier(
        ElementType.NAVIGABLE_TRACK.getName(),
        track_id)
    return handler_element_navigable_track(objid, item_identifier = identifier, entries = entries)


def choose_track_adapter(tidal_session : TidalSession, played_track : PlayedTrack) -> TrackAdapter:
    played_track_complete : bool = played_track and is_played_track_complete(played_track)
    return (PlayedTrackAdapter(played_track)
        if played_track_complete
        else __load_tidal_track_adapter_by_track_id(
            tidal_session = tidal_session,
            track_id = played_track.track_id))


def choose_track_adapter_by_tidal_track(
        tidal_session : TidalSession,
        track : TidalTrack) -> TrackAdapter:
    return (__choose_track_adapter_by_track_id(
        tidal_session = tidal_session,
        track_id = track.id) if config.enable_read_stream_metadata
        else __load_tidal_track_adapter_by_track(
            tidal_session = tidal_session,
            track = track))


def __load_tidal_track_adapter_by_track(
        tidal_session : TidalSession,
        track : TidalTrack) -> TidalTrackAdapter:
    # msgproc.log(f"Loading track details from Tidal for track_id: [{track_id}]")
    adapter : TidalTrackAdapter = TidalTrackAdapter(
        tidal_session = tidal_session,
        track = track,
        album_retriever = album_retriever)
    return adapter


def __load_tidal_track_adapter_by_track_id(
        tidal_session : TidalSession,
        track_id : str) -> TidalTrackAdapter:
    # msgproc.log(f"Loading track details from Tidal for track_id: [{track_id}]")
    adapter : TidalTrackAdapter = TidalTrackAdapter(
        tidal_session = tidal_session,
        track = tidal_session.track(track_id),
        album_retriever = album_retriever)
    # maybe update on db?
    if config.enable_read_stream_metadata:
        current : PlayedTrack = persistence.get_played_track_entry(track_id = track_id)
        request : PlayedTrackRequest = PlayedTrackRequest()
        request.track_id = track_id
        request.album_track_count = adapter.get_album_track_count()
        request.album_num_volumes = adapter.get_album_num_volumes() if adapter.get_album_num_volumes() else 1
        request.album_id = adapter.get_album_id()
        request.album_artist_name = adapter.get_album_artist_name()
        request.album_name = adapter.get_album_name()
        request.artist_name = adapter.get_artist_name()
        try:
            request.audio_quality = adapter.get_audio_quality()
        except Exception as ex:
            msgproc.log(f"Cannot get audio_quality for track [{track_id}] due to [{type(ex)}] [{ex}]")
        request.explicit = adapter.explicit()
        request.track_duration = adapter.get_duration()
        request.track_name = adapter.get_name()
        request.track_num = adapter.get_track_num()
        request.volume_num = adapter.get_volume_num()
        request.image_url = adapter.get_image_url()
        request.explicit = 1 if adapter.explicit() else 0
        try:
            request.bit_depth = adapter.get_bit_depth()
        except Exception:
            msgproc.log(f"Cannot get bit_depth for track [{track_id}]")
        try:
            request.sample_rate = adapter.get_sample_rate()
        except Exception:
            msgproc.log(f"Cannot get sample_rate for track [{track_id}]")
        if current:
            # msgproc.log(f"Updating played_track for track_id [{track_id}] ...")
            # update using adapter
            persistence.update_playback(
                played_track_request = request,
                last_played = None)
        else:
            # msgproc.log(f"Inserting played_track for track_id [{track_id}] without a play_count ...")
            persistence.insert_playback(
                played_track_request = request,
                last_played = None)
    return adapter


def __choose_track_adapter_by_track_id(
        tidal_session : TidalSession,
        track_id : str) -> TrackAdapter:
    played_track : PlayedTrack = (persistence.get_played_track_entry(track_id = track_id)
        if config.enable_read_stream_metadata
        else None)
    return (choose_track_adapter(
            tidal_session = tidal_session,
            played_track = played_track)
        if played_track
        else __load_tidal_track_adapter_by_track_id(
            tidal_session = tidal_session,
            track_id = track_id))


def image_retriever_categories(
        tidal_session : TidalSession,
        tag_type : TagType) -> str:
    categories = get_categories(tidal_session = tidal_session)
    first = categories[0] if categories and len(categories) > 0 else None
    return get_category_image_url(
        tidal_session = tidal_session,
        category = first) if first else None


def image_retriever_cached(tidal_session : TidalSession, tag_type : TagType, loader) -> str:
    tile_image : TileImage = load_tile_image_unexpired(
        tile_type = TileType.TAG,
        tile_id = tag_type.getTagName())
    image_url : str = tile_image.tile_image if tile_image else None
    msgproc.log(f"Image for tag [{tag_type.getTagName()}] cached [{'yes' if image_url else 'no'}]")
    if not image_url:
        image_url = loader(tidal_session, tag_type)
        if image_url: persistence.save_tile_image(TileType.TAG, tag_type.getTagName(), image_url)
    return image_url


def image_retriever_my_playlists(
        tidal_session : TidalSession,
        tag_type : TagType) -> str:
    playlists : list[TidalUserPlaylist] = tidal_session.user.playlists()
    first : TidalUserPlaylist = playlists[0] if playlists and len(playlists) > 0 else None
    return tidal_util.get_image_url(first) if first else None


def image_retriever_all_playlists(
        tidal_session : TidalSession,
        tag_type : TagType) -> str:
    playlists : list[TidalPlaylist] = tidal_session.user.playlist_and_favorite_playlists()
    first : TidalPlaylist = playlists[0] if playlists and len(playlists) > 0 else None
    return tidal_util.get_image_url(first) if first else None


def image_retriever_favorite_albums(
        tidal_session : TidalSession,
        tag_type : TagType) -> str:
    items : list[TidalAlbum] = tidal_session.user.favorites.albums(limit = 1, offset = 0)
    first : TidalAlbum = items[0] if items and len(items) > 0 else None
    return tidal_util.get_image_url(first) if first else None


def image_retriever_favorite_artists(
        tidal_session : TidalSession,
        tag_type : TagType) -> str:
    items : list[TidalArtist] = tidal_session.user.favorites.artists(limit = 1, offset = 0)
    first : TidalArtist = items[0] if items and len(items) > 0 else None
    return tidal_util.get_image_url(first) if first else None


def image_retriever_favorite_tracks(
        tidal_session : TidalSession,
        tag_type : TagType) -> str:
    items : list[TidalTrack] = tidal_session.user.favorites.tracks(limit = 1, offset = 0)
    first : TidalTrack = items[0] if items and len(items) > 0 else None
    album : TidalAlbum = tidal_session.album(first.album.id) if first else None
    return tidal_util.get_image_url(album) if album else None


def image_retriever_playback_statistics(
        tidal_session : TidalSession,
        tag_type : TagType) -> str:
    items : list[PlayedTrack] = persistence.get_last_played_tracks(max_tracks = 10)
    first : PlayedTrack = secrets.choice(items) if items and len(items) > 0 else None
    album : TidalAlbum = tidal_session.album(first.album_id) if first else None
    return tidal_util.get_image_url(album) if album else None


def __get_random_album_id_from_listen_queue() -> str:
    album_id_list : list[str] = persistence.get_album_listen_queue()
    return secrets.choice(album_id_list) if album_id_list and len(album_id_list) > 0 else None


def image_retriever_listen_queue(
        tidal_session : TidalSession,
        tag_type : TagType) -> str:
    select_album_id : str = __get_random_album_id_from_listen_queue()
    select_album : TidalAlbum = tidal_session.album(select_album_id) if select_album_id else None
    return tidal_util.get_image_url(select_album) if select_album else None


__tag_image_retriever : dict = {
    TagType.CATEGORIES.getTagName(): image_retriever_categories,
    TagType.MY_PLAYLISTS.getTagName(): image_retriever_my_playlists,
    TagType.ALL_PLAYLISTS.getTagName(): image_retriever_all_playlists,
    TagType.FAVORITE_ALBUMS.getTagName(): image_retriever_favorite_albums,
    TagType.FAVORITE_ARTISTS.getTagName(): image_retriever_favorite_artists,
    TagType.FAVORITE_TRACKS.getTagName(): image_retriever_favorite_tracks,
    TagType.PLAYBACK_STATISTICS.getTagName(): image_retriever_playback_statistics,
    TagType.LISTENING_QUEUE.getTagName(): image_retriever_listen_queue
}


__tag_action_dict : dict = {
    TagType.CATEGORIES.getTagName(): handler_tag_categories,
    TagType.MY_PLAYLISTS.getTagName(): handler_tag_my_playlists,
    TagType.ALL_PLAYLISTS.getTagName(): handler_tag_all_playlists,
    TagType.FAVORITE_ALBUMS.getTagName(): handler_tag_favorite_albums,
    TagType.FAVORITE_ARTISTS.getTagName(): handler_tag_favorite_artists,
    TagType.FAVORITE_TRACKS.getTagName(): handler_tag_favorite_tracks,
    TagType.PLAYBACK_STATISTICS.getTagName(): handler_tag_playback_statistics,
    TagType.LISTENING_QUEUE.getTagName(): handler_tag_listening_queue
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
    ElementType.ALBUMS_IN_MIX_OR_PLAYLIST.getName(): handler_element_albums_in_mix_or_playlist,
    ElementType.ARTISTS_IN_MIX_OR_PLAYLIST.getName(): handler_element_artists_in_mix_or_playlist,
    ElementType.PAGELINK.getName(): handler_element_pagelink,
    ElementType.PAGE.getName(): handler_element_page,
    ElementType.ARTIST.getName(): handler_element_artist,
    ElementType.ARTIST_FOCUS.getName(): handler_element_artist_related,
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
    ElementType.FAVORITE_ALBUMS_BY_ARTIST_ASC.getName(): handler_element_favorite_albums_by_artist_asc,
    ElementType.FAVORITE_ALBUMS_BY_ARTIST_DESC.getName(): handler_element_favorite_albums_by_artist_desc,
    ElementType.FAVORITE_ALBUMS_BY_TITLE_ASC.getName(): handler_element_favorite_albums_by_title_asc,
    ElementType.FAVORITE_ALBUMS_BY_TITLE_DESC.getName(): handler_element_favorite_albums_by_title_desc,
    ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_ASC.getName(): handler_element_favorite_albums_by_release_date_asc,
    ElementType.FAVORITE_ALBUMS_BY_RELEASE_DATE_DESC.getName(): handler_element_favorite_albums_by_release_date_desc,
    ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_ASC.getName(): handler_element_favorite_albums_by_user_added_asc,
    ElementType.FAVORITE_ALBUMS_BY_USER_DATE_ADDED_DESC.getName(): handler_element_favorite_albums_by_user_added_desc,
    ElementType.FAVORITE_ARTISTS_BY_NAME_ASC.getName(): handler_favorite_artists_by_name_asc,
    ElementType.FAVORITE_ARTISTS_BY_NAME_DESC.getName(): handler_favorite_artists_by_name_desc,
    ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_ASC.getName(): handler_favorite_artists_by_user_date_added_asc,
    ElementType.FAVORITE_ARTISTS_BY_USER_DATE_ADDED_DESC.getName(): handler_favorite_artists_by_user_date_added_desc,
    ElementType.ALBUM_LISTEN_QUEUE.getName(): handler_album_listen_queue,
    ElementType.ALBUM_LISTEN_QUEUE_ACTION.getName(): handler_album_listen_queue_action,
    ElementType.ALBUM_TRACKS.getName(): handler_album_tracks_action,
    ElementType.TRACK_FAVORITE_ACTION.getName(): handler_track_favorite_action
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
    tidal_session : TidalSession = get_session()
    for tag in TagType:
        curr_tag_img_retriever = (__tag_image_retriever[tag.getTagName()]
            if tag.getTagName() in __tag_image_retriever
            else None)
        msgproc.log(f"show_tags found handler for tag [{tag.getTagName()}]: "
                    f"[{'yes' if curr_tag_img_retriever else 'no'}]")
        curr_tag_img : str = (image_retriever_cached(
            tidal_session = tidal_session,
            tag_type = tag,
            loader = curr_tag_img_retriever) if curr_tag_img_retriever else None)
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
        else:  # it's an element
            elem_handler = __elem_action_dict[thing_name] if thing_name in __elem_action_dict else None
            msgproc.log(f"browse: should serve element [{thing_name}], handler found: "
                        f"[{'yes' if elem_handler else 'no'}]")
            if elem_handler:
                entries = elem_handler(objid, item_identifier, entries)
    return _returnentries(entries)


def tidal_search(
        tidal_session : TidalSession,
        search_type : SearchType,
        value : str,
        limit : int = 50,
        offset : int = 0) -> list:
    search_result : dict = tidal_session.search(
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
    # if not objkind or len(objkind) == 0: objkind = field

    msgproc.log(f"Searching for [{value}] as [{field}] objkind [{objkind}] origsearch [{origsearch}] ...")
    resultset_length : int = 0

    tidal_session : TidalSession = get_session()

    if not objkind or len(objkind) == 0:
        if SearchType.ARTIST.get_name() == field:
            # search artists by specified value
            item_list : list[TidalArtist] = tidal_search(
                tidal_session = tidal_session,
                search_type = SearchType.ARTIST,
                value = value)
            resultset_length = len(item_list) if item_list else 0
            for item in item_list:
                entries.append(artist_to_entry(
                    objid = objid,
                    artist = item))
        elif SearchType.ALBUM.get_name() == field:
            # search albums by specified value
            item_list : list[TidalAlbum] = tidal_search(
                tidal_session = tidal_session,
                search_type = SearchType.ALBUM,
                value = value)
            resultset_length = len(item_list) if item_list else 0
            for item in item_list:
                entries.append(album_to_entry(
                    objid = objid,
                    album = item))
        elif SearchType.TRACK.get_name() == field:
            # search tracks by specified value
            item_list : list[TidalTrack] = tidal_search(
                tidal_session = tidal_session,
                search_type = SearchType.TRACK,
                value = value)
            resultset_length = len(item_list) if item_list else 0
            options : dict[str, any] = dict()
            context : Context = Context()
            set_option(options = options, option_key = OptionKey.SKIP_TRACK_NUMBER, option_value = True)
            for item in item_list:
                entries.append(track_to_entry(
                    objid = objid,
                    track_adapter = instance_tidal_track_adapter(
                        tidal_session = tidal_session,
                        track = item),
                    options = options,
                    context = context))
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
                tidal_session = tidal_session,
                search_type = st,
                value = value)
            resultset_length += len(item_list) if item_list else 0
            context : Context = Context()
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
                        track_adapter = instance_tidal_track_adapter(
                            tidal_session = tidal_session,
                            track = item),
                        options = track_options,
                        context = context))
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
    msgproc.log(f"enable_read_stream_metadata=[{config.enable_read_stream_metadata}]")
    msgproc.log(f"enable_assume_bitdepth=[{config.enable_assume_bitdepth}]")
    cache_dir : str = upmplgutils.getcachedir(constants.plugin_name)
    msgproc.log(f"Cache dir for [{plugin_name}] is [{cache_dir}]")
    msgproc.log(f"DB version for [{plugin_name}] is [{persistence.get_db_version()}]")
    _g_init = True
    return True


msgproc.mainloop()
