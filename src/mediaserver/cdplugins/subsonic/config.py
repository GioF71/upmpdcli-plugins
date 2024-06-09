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

import constants

import upmplgutils
import libsonic
from subsonic_connector.configuration import ConfigurationInterface
from tag_type import TagType


def plugin_config_variable_name(name : str) -> str:
    return f"{constants.plugin_name}{name}"


def get_plugin_option_value(nm, dflt = None):
    return upmplgutils.getOptionValue(plugin_config_variable_name(nm), dflt)


items_per_page : int = min(
    constants.subsonic_max_return_size,
    get_plugin_option_value("itemsperpage", constants.default_items_per_page))

cached_request_timeout_sec : int = min(
    constants.subsonic_max_return_size,
    get_plugin_option_value("cachedrequesttimeoutsec", constants.default_cached_request_timeout_sec))


append_year_to_album : int = int(get_plugin_option_value("appendyeartoalbum", "1"))
append_codecs_to_album : int = int(get_plugin_option_value("appendcodecstoalbum", "1"))
whitelist_codecs : list[str] = str(get_plugin_option_value("whitelistcodecs", "alac,wav,flac,dsf")).split(",")
allow_blacklisted_codec_in_song : int = int(get_plugin_option_value("allowblacklistedcodecinsong", "1"))
disable_navigable_album : int = int(get_plugin_option_value("disablenavigablealbumview", "0"))
tag_initial_page_enabled_prefix : str = plugin_config_variable_name("taginitialpageenabled")
autostart : int = int(get_plugin_option_value("autostart", "0"))
log_intermediate_url : bool = get_plugin_option_value("logintermediateurl", "0") == "1"
skip_intermediate_url : bool = get_plugin_option_value("skipintermediateurl", "0") == "1"
allow_artist_art : bool = get_plugin_option_value("allowartistart", "0") == "1"
server_side_scrobbling : bool = get_plugin_option_value("serversidescrobbling", "0") == "1"
prepend_number_in_album_list : bool = get_plugin_option_value("prependnumberinalbumlist", "0") == "1"

configured_transcode_codec : str = get_plugin_option_value("transcodecodec", "")
configured_transcode_max_bitrate : str = get_plugin_option_value("transcodemaxbitrate", "")

max_artists_per_page: int = get_plugin_option_value("maxartistsperpage", constants.default_max_artists_per_page)

show_empty_favorites: bool = get_plugin_option_value("showemptyfavorites", constants.default_show_empty_favorites) == 1
show_empty_playlists: bool = get_plugin_option_value("showemptyplaylists", constants.default_show_empty_playlists) == 1

dump_streaming_properties : bool = (
    get_plugin_option_value(
        "dumpstreamingproperties",
        constants.default_dump_streaming_properties) == 1)

# supported unless initializer understands it is not
# begin
album_list_by_highest_supported : bool = True
internet_radio_stations_supported : bool = True
# end


def is_transcode_enabled() -> bool:
    return configured_transcode_codec or configured_transcode_max_bitrate


def get_transcode_codec() -> str:
    if configured_transcode_codec: return configured_transcode_codec
    if is_transcode_enabled(): return constants.fallback_transcode_codec
    return None


def get_transcode_max_bitrate() -> int:
    if configured_transcode_max_bitrate: return int(configured_transcode_max_bitrate)
    if configured_transcode_codec: return 320
    return None


def is_tag_supported(tag : TagType) -> bool:
    # true unless there are exceptions ...
    if tag == TagType.HIGHEST_RATED:
        return album_list_by_highest_supported
    elif tag == TagType.INTERNET_RADIOS:
        return internet_radio_stations_supported
    return True


class UpmpdcliSubsonicConfig(ConfigurationInterface):

    def getBaseUrl(self) -> str: return get_plugin_option_value("baseurl")

    def getPort(self) -> int: return get_plugin_option_value("port")

    def getUserName(self) -> str: return get_plugin_option_value("user")

    def getPassword(self) -> str: return get_plugin_option_value("password")

    def getLegacyAuth(Self) -> bool:
        legacy_auth_enabled_str : str = get_plugin_option_value("legacyauth", "false")
        if not legacy_auth_enabled_str.lower() in ["true", "false", "1", "0"]:
            raise Exception(f"Invalid value for SUBSONIC_LEGACYAUTH [{legacy_auth_enabled_str}]")
        return legacy_auth_enabled_str in ["true", "1"]

    def getApiVersion(self) -> str: return libsonic.API_VERSION
    def getAppName(self) -> str: return "upmpdcli"
