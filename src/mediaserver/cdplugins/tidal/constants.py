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

from enum import Enum
from typing import Callable
from tidalapi import Quality as TidalQuality
import lafv_matcher


class PluginConstant(Enum):

    PLUGIN_RELEASE = "0.8.9.1"
    PLUGIN_NAME = "tidal"
    CACHED_IMAGES_DIRECTORY = "images"
    STATIC_IMAGES_DIRECTORY = "static-images"
    PLUGIN_IMAGES_DIRECTORY = "static-images"


class PluginImageDirectory(Enum):
    PAGES = "pages"
    BUTTONS = "buttons"


class _FunctionProxy:
    """Allow to mask a function as an Object."""
    def __init__(self, function):
        self.function = function

    def __call__(self, *args, **kwargs):
        return self.function(*args, **kwargs)


class UserAgentMatcher(Enum):
    EXACT = _FunctionProxy(lambda x, y: x == y)
    STARTS_WITH = _FunctionProxy(lambda x, y: x.startswith(y))
    ENDS_WITH = _FunctionProxy(lambda x, y: x.endswith(y))
    CONTAINS = _FunctionProxy(lambda x, y: x in y)


class UserAgentMatcherData:

    def __init__(self, user_agent_str: str, device_list: list[str], matcher: Callable[[str, str], bool]):
        self.__user_agent_str: str = user_agent_str
        self.__device_list: list[str] = device_list
        self.__matcher: Callable[[str, str], bool] = matcher

    @property
    def user_agent_str(self) -> str:
        return self.__user_agent_str

    @property
    def device_list(self) -> list[str]:
        return self.__device_list

    @property
    def matcher(self) -> Callable[[str, str], bool]:
        return self.__matcher


class UserAgentHiResWhitelist(Enum):
    MUSIC_PLAYER_DAEMON = UserAgentMatcherData(
        "Music Player Daemon",
        ["Music Player Daemon"],
        UserAgentMatcher.STARTS_WITH.value)
    LAVF_FFPROBE = UserAgentMatcherData(
        "Lavf/ffprobe",
        ["gmrender-resurrect", "BubbleUPnp Server"],
        UserAgentMatcher.EXACT.value)
    WIIM_FIRMWARE_GE_58_76_100 = UserAgentMatcherData(
        "Lavf/58.76.100",
        ["WiiM Device"],
        lambda x, y: lafv_matcher.match(
            to_match=x,
            pattern=y,
            match_mode=lafv_matcher.LavfMatchMode.GE))

    @property
    def user_agent_str(self) -> str:
        return self.value.user_agent_str

    @property
    def device_list(self) -> list[str]:
        return self.value.device_list

    @property
    def matcher(self) -> Callable[[str, str], bool]:
        return self.value.matcher


class EnvironmentVariableName(Enum):
    UPMPD_UPNPHOSTPORT = "UPMPD_UPNPHOSTPORT"


class _ConfigParamData:

    def __init__(self, key: str, default_value: any):
        self.__key: str = key
        self.__default_value: any = default_value

    @property
    def key(self) -> str:
        return self.__key

    @property
    def default_value(self) -> any:
        return self.__default_value


class ConfigParam(Enum):

    AUDIO_QUALITY = _ConfigParamData("audioquality", TidalQuality.high_lossless)

    ALLOW_FAVORITE_ACTIONS = _ConfigParamData("allowfavoriteactions", False)
    ALLOW_BOOKMARK_ACTIONS = _ConfigParamData("allowbookmarkactions", False)
    ALLOW_STATISTICS_ACTIONS = _ConfigParamData("allowstatisticsactions", False)
    ENABLE_USER_AGENT_WHITELIST = _ConfigParamData("enableuseragentwhitelist", True)
    ENABLE_READ_STREAM_METADATA = _ConfigParamData("enablereadstreammetadata", False)
    ENABLE_DUMP_STREAM_DATA = _ConfigParamData("enabledumpstreamdata", False)
    ENABLE_CACHED_IMAGE_AGE_LIMIT = _ConfigParamData("enablecachedimageagelimit", False)
    CACHED_IMAGE_MAX_AGE_DAYS = _ConfigParamData("cachedimagemaxagedays", 60)

    TRACK_URI_ENTRY_EXPIRATION_SEC = _ConfigParamData("trackurientryexpirationsec", 240)

    TRACK_ID_REGEX = _ConfigParamData("trackidregex", "^[0-9]+$")
    VERBOSE_LOGGING = _ConfigParamData("verboselogging", False)

    ALLOW_STATIC_IMAGES_FOR_PAGES = _ConfigParamData("allowstaticimagesforpages", False)

    @property
    def key(self) -> str:
        return self.value.key

    @property
    def default_value(self) -> any:
        return self.value.default_value


class ListeningQueueKey(Enum):
    ACTION_KEY = "action"
    BUTTON_TITLE_KEY = "button_title"


class Action(Enum):
    ADD = "add"
    DEL = "del"


class ListeningQueueAction(Enum):
    ADD = Action.ADD.value
    DEL = Action.DEL.value


class ActionButtonTitle(Enum):

    BOOKMARK_ADD = "Bookmarks (+)"
    BOOKMARK_RMV = "Bookmarks (-)"
    FAVORITE_ADD = "Favorites (+)"
    FAVORITE_RMV = "Favorites (-)"


listening_queue_action_add_dict: dict[str, str] = {
    ListeningQueueKey.ACTION_KEY.value: ListeningQueueAction.ADD.value,
    ListeningQueueKey.BUTTON_TITLE_KEY.value: ActionButtonTitle.BOOKMARK_ADD.value}

listening_queue_action_del_dict: dict[str, str] = {
    ListeningQueueKey.ACTION_KEY.value: ListeningQueueAction.DEL.value,
    ListeningQueueKey.BUTTON_TITLE_KEY.value: ActionButtonTitle.BOOKMARK_RMV.value}

fav_action_key: str = "action"
fav_button_title_key: str = "button_title"

fav_action_add: str = Action.ADD.value
fav_action_del: str = Action.DEL.value

fav_action_add_dict: dict[str, str] = {
    fav_action_key: fav_action_add,
    fav_button_title_key: ActionButtonTitle.FAVORITE_ADD.value}

fav_action_del_dict: dict[str, str] = {
    fav_action_key: fav_action_del,
    fav_button_title_key: ActionButtonTitle.FAVORITE_RMV.value}

fav_action_dict: dict[str, any] = {
    fav_action_add: fav_action_add_dict,
    fav_action_del: fav_action_del_dict
}

featured_type_name_playlist: str = "PLAYLIST"
tile_image_expiration_time_sec: int = 86400

oauth2_credentials_file_name: str = "oauth2.credentials.json"
pkce_credentials_file_name: str = "pkce.credentials.json"
# remove if not really used
default_max_album_tracks_per_page: int = 30

default_max_playlist_or_mix_items_per_page: int = 25

default_enable_assume_bitdepth: int = 1
default_playlist_items_per_page: int = 25
default_tracks_per_page: int = 25
default_mix_items_per_page: int = 25
default_albums_per_page: int = 25
default_artists_per_page: int = 25
default_page_items_per_page: int = 20

default_page_items_for_tile_image: int = 1

# this one should be disabled by default for the release
default_dump_track_to_entry_result: int = 0

default_allow_guess_stream_info_from_other_album_track: int = 1

default_max_file_age_seconds: int = 3600

default_max_get_stream_info_mix_or_playlist: int = 5

default_show_album_id: bool = True

default_badge_favorite_album: bool = True

default_titleless_single_album_view: bool = False

default_skip_non_stereo: bool = True

default_log_intermediate_url: bool = False

default_prepend_number_in_item_list: bool = False

default_serve_mode: str = "mpd"

default_listen_queue_playlist_name: str = "Listening Queue"

default_display_quality_badge: bool = False

default_enable_image_caching: bool = False

default_search_limit: int = 15

default_dump_image_caching: bool = False
