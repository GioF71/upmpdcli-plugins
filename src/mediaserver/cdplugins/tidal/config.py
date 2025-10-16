# Copyright (C) 2024,2025 Giovanni Fulco
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

import upmplgutils
import constants
from tidalapi import Quality as TidalQuality


def get_plugin_config_variable_name(name: str) -> str:
    return f"{constants.PluginConstant.PLUGIN_NAME.value}{name}"


def get_option_value_as_bool(nm: str, default_value: int) -> bool:
    return get_option_value(nm, default_value) == 1


def get_option_value(nm, dflt: any = None):
    return upmplgutils.getOptionValue(get_plugin_config_variable_name(nm), dflt)


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


def __getPluginOptionAsBool(plugin_param_name: str, default_value: bool | int = None) -> bool:
    sanitized_default_value: int | bool = 0 if not default_value else default_value
    if type(sanitized_default_value) is bool:
        sanitized_default_value = 1 if default_value else 0
    elif type(sanitized_default_value) is int:
        if sanitized_default_value not in [0, 1]:
            raise Exception(f"Invalid boolean value for [{plugin_param_name}], should be 0 or 1")
    return (getPluginOptionValue(plugin_param_name, sanitized_default_value) == 1)


def getPluginOptionValue(option_key: str, dflt=None):
    return upmplgutils.getOptionValue(
        nm=f"{constants.PluginConstant.PLUGIN_NAME.value}{option_key}",
        dflt=dflt)


def getWebServerDocumentRoot() -> str:
    # return getUpnpWebDocRoot(constants.plugin_name)
    return upmplgutils.getOptionValue("webserverdocumentroot")


enable_read_stream_metadata: bool = get_config_param_as_bool(constants.ConfigParam.ENABLE_READ_STREAM_METADATA)

enable_assume_bitdepth: bool = __getPluginOptionAsBool(
    "enableassumebitdepth",
    constants.default_enable_assume_bitdepth)


tracks_per_page: int = getPluginOptionValue(
    "tracksperpage",
    constants.default_tracks_per_page)


mix_items_per_page: int = getPluginOptionValue(
    "mixitemsperpage",
    constants.default_mix_items_per_page)


playlist_items_per_page: int = getPluginOptionValue(
    "playlistitemsperpage",
    constants.default_playlist_items_per_page)


dump_track_to_entry_result: bool = getPluginOptionValue(
    "dumptracktoentryresult",
    constants.default_dump_track_to_entry_result)


allow_guess_stream_info_from_other_album_track: bool = getPluginOptionValue(
    "allowguessstreaminfofromotheralbumtrack",
    constants.default_allow_guess_stream_info_from_other_album_track)


max_file_age_seconds: int = getPluginOptionValue(
    "maxfileageseconds",
    constants.default_max_file_age_seconds)


max_get_stream_info_mix_or_playlist: bool = getPluginOptionValue(
    "maxgetstreaminfomixorplaylist",
    constants.default_max_get_stream_info_mix_or_playlist)


page_items_per_page: int = getPluginOptionValue(
    "pageitemsperpage",
    constants.default_page_items_per_page)


albums_per_page: int = getPluginOptionValue(
    "albumsperpage",
    constants.default_albums_per_page)


artists_per_page: int = getPluginOptionValue(
    "artistsperpage",
    constants.default_artists_per_page)


show_album_id: bool = getPluginOptionValue(
    "showalbumid",
    constants.default_show_album_id)


badge_favorite_album: bool = getPluginOptionValue(
    "badgefavoritealbum",
    constants.default_badge_favorite_album)


titleless_single_album_view: bool = getPluginOptionValue(
    "titlelesssinglealbumview",
    constants.default_titleless_single_album_view)


skip_non_stereo: bool = __getPluginOptionAsBool(
    "skipnonstereo",
    constants.default_skip_non_stereo)


log_intermediate_url: bool = __getPluginOptionAsBool(
    "logintermediateurl",
    constants.default_log_intermediate_url)


prepend_number_in_album_list: bool = __getPluginOptionAsBool(
    "prependnumberinitemlist",
    constants.default_prepend_number_in_item_list)


serve_mode: str = getPluginOptionValue(
    "servemode",
    constants.default_serve_mode)


max_playlist_or_mix_items_per_page: int = getPluginOptionValue(
    "maxplaylistitemsperpage",
    constants.default_max_playlist_or_mix_items_per_page)


listen_queue_playlist_name: str = getPluginOptionValue(
    "listenqueueplaylistname",
    constants.default_listen_queue_playlist_name)


display_quality_badge: bool = __getPluginOptionAsBool(
    "displayqualitybadge",
    constants.default_display_quality_badge)


def get_enable_image_caching() -> bool:
    return __getPluginOptionAsBool("enableimagecaching", constants.default_enable_image_caching)


__fallback_for_missing_quality: dict[str, str] = {
    TidalQuality.hi_res_lossless: TidalQuality.high_lossless,
    TidalQuality.high_lossless: TidalQuality.high_lossless,
    TidalQuality.low_320k: TidalQuality.low_320k,
    TidalQuality.low_96k: TidalQuality.low_96k
}


def get_fallback_quality_when_missing() -> str:
    max_audio_quality: str = get_config_param_as_str(constants.ConfigParam.AUDIO_QUALITY)
    if not max_audio_quality or max_audio_quality not in __fallback_for_missing_quality:
        return None
    return __fallback_for_missing_quality[max_audio_quality]


def get_dump_image_caching() -> bool:
    return __getPluginOptionAsBool(
        "dumpimagecaching",
        constants.default_dump_image_caching)


def get_override_country_code() -> str:
    return getPluginOptionValue("overridecountrycode")


def get_tile_image_expiration_time_sec() -> int:
    return getPluginOptionValue(
        "tileimageexpirationtimesec",
        constants.tile_image_expiration_time_sec)


def get_allow_favorite_actions() -> bool:
    return __getPluginOptionAsBool(
        constants.ConfigParam.ALLOW_FAVORITE_ACTIONS.key,
        constants.ConfigParam.ALLOW_FAVORITE_ACTIONS.default_value)


def get_allow_bookmark_actions() -> bool:
    return __getPluginOptionAsBool(
        constants.ConfigParam.ALLOW_BOOKMARK_ACTIONS.key,
        constants.ConfigParam.ALLOW_BOOKMARK_ACTIONS.default_value)


def get_allow_statistics_actions() -> bool:
    return __getPluginOptionAsBool(
        constants.ConfigParam.ALLOW_STATISTICS_ACTIONS.key,
        constants.ConfigParam.ALLOW_STATISTICS_ACTIONS.default_value)
