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

import constants

import upmplgutils
import libsonic
from subsonic_connector.configuration import ConfigurationInterface
from tag_type import TagType


def get_plugin_config_variable_name(name: str) -> str:
    return f"{constants.PluginConstant.PLUGIN_NAME.value}{name}"


def get_option_value_as_bool(nm: str, default_value: int) -> bool:
    return get_option_value(nm, default_value) == 1


def get_option_value(nm, dflt: any = None):
    return upmplgutils.getOptionValue(get_plugin_config_variable_name(nm), dflt)


def get_cached_request_timeout_sec() -> int:
    return get_option_value(
        "cachedrequesttimeoutsec",
        constants.Defaults.CACHED_REQUEST_TIMEOUT_SEC.value)


whitelist_codecs: list[str] = str(get_option_value("whitelistcodecs", "alac,wav,flac,dsf")).split(",")
allow_blacklisted_codec_in_song: int = int(get_option_value("allowblacklistedcodecinsong", "1"))
tag_initial_page_enabled_prefix: str = get_plugin_config_variable_name("taginitialpageenabled")
autostart: int = int(get_option_value("autostart", "0"))
log_intermediate_url: bool = get_option_value("logintermediateurl", "0") == "1"
skip_intermediate_url: bool = get_option_value("skipintermediateurl", "0") == "1"
server_side_scrobbling: bool = get_option_value("serversidescrobbling", "0") == "1"
prepend_number_in_album_list: bool = get_option_value("prependnumberinalbumlist", "0") == "1"

configured_transcode_max_bitrate: str = get_option_value("transcodemaxbitrate", "")

debug_badge_mngmt: bool = get_option_value_as_bool("debugbadgemanagement", constants.default_debug_badge_mngmt)
debug_artist_albums: bool = get_option_value_as_bool("debugartistalbums", constants.default_debug_artist_albums)


# supported unless initializer understands it is not
# begin
album_list_by_highest_supported: bool = True
internet_radio_stations_supported: bool = True
# end


def is_transcode_enabled() -> bool:
    return (get_config_param_as_str(constants.ConfigParam.TRANSCODE_CODEC) or
            configured_transcode_max_bitrate)


def get_transcode_codec() -> str:
    transcode_codec: str = get_config_param_as_str(constants.ConfigParam.TRANSCODE_CODEC)
    if transcode_codec:
        return transcode_codec
    if is_transcode_enabled():
        return constants.Defaults.FALLBACK_TRANSCODE_CODEC.value
    return None


def get_transcode_max_bitrate() -> int:
    transcode_codec: str = get_config_param_as_str(constants.ConfigParam.TRANSCODE_CODEC)
    if transcode_codec:
        return int(configured_transcode_max_bitrate)
    if transcode_codec:
        return 320
    return None


def is_tag_supported(tag: TagType) -> bool:
    # true unless there are exceptions ...
    if tag == TagType.HIGHEST_RATED_ALBUMS:
        return album_list_by_highest_supported
    elif tag == TagType.INTERNET_RADIOS:
        return internet_radio_stations_supported
    return True


def get_config_param_as_str(configuration_parameter: constants.ConfigParam) -> str:
    dv: str | None = configuration_parameter.default_value
    if dv is not None and not isinstance(dv, str):
        raise Exception(f"Invalid default value for [{configuration_parameter.key}]")
    v: any = get_option_value(configuration_parameter.key, dv)
    if v is None:
        return None
    # v is set, check type!
    if isinstance(v, str):
        return v
    # try to convert to string
    return str(v)


def get_config_param_as_int(configuration_parameter: constants.ConfigParam) -> str:
    dv: int | None = configuration_parameter.default_value
    if dv is not None and not isinstance(dv, int):
        raise Exception(f"Invalid default value for [{configuration_parameter.key}]")
    v: any = get_option_value(configuration_parameter.key, dv)
    if v is None:
        return None
    # v is set, check type!
    if isinstance(v, int):
        return v
    # try to convert to int
    return int(v)


def get_config_param_as_bool(configuration_parameter: constants.ConfigParam) -> bool:
    default_value_as_int: int = 0
    dv: any = configuration_parameter.default_value
    if isinstance(dv, int):
        default_value_as_int = 1 if dv == 1 else 0
    elif isinstance(dv, bool):
        default_value_as_int = 1 if dv else 0
    return get_option_value_as_bool(
        configuration_parameter.key,
        default_value_as_int)


def get_items_per_page() -> int:
    return min(
        constants.Defaults.SUBSONIC_API_MAX_RETURN_SIZE.value,
        get_config_param_as_int(constants.ConfigParam.ITEMS_PER_PAGE))


def getWebServerDocumentRoot() -> str:
    return upmplgutils.getUpnpWebDocRoot(constants.PluginConstant.PLUGIN_NAME.value)


class UpmpdcliSubsonicConfig(ConfigurationInterface):

    def getBaseUrl(self) -> str: return get_option_value("baseurl")

    def getPort(self) -> int: return get_option_value("port")

    def getUserName(self) -> str: return get_option_value("user")

    def getPassword(self) -> str: return get_option_value("password")

    def getLegacyAuth(Self) -> bool:
        legacy_auth_enabled_str: str = get_option_value("legacyauth", "false")
        if not legacy_auth_enabled_str.lower() in ["true", "false", "1", "0"]:
            raise Exception(f"Invalid value for SUBSONIC_LEGACYAUTH [{legacy_auth_enabled_str}]")
        return legacy_auth_enabled_str in ["true", "1"]

    def getApiVersion(self) -> str: return libsonic.API_VERSION
    def getAppName(self) -> str: return "upmpdcli"
