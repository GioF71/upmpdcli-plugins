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

import constants

import upmplgutils
#from upmplgutils import getOptionValue
import libsonic
from subsonic_connector.configuration import ConfigurationInterface

def plugin_config_variable_name(name : str) -> str:
    return f"{constants.plugin_name}{name}"

def get_plugin_option_value(nm, dflt = None):
    return upmplgutils.getOptionValue(plugin_config_variable_name(nm), dflt)

subsonic_max_return_size : int = 500 # hard limit
items_per_page : int = min(subsonic_max_return_size, int(get_plugin_option_value("itemsperpage", "36")))
append_year_to_album : int = int(get_plugin_option_value("appendyeartoalbum", "1"))
append_codecs_to_album : int = int(get_plugin_option_value("appendcodecstoalbum", "1"))
whitelist_codecs : list[str] = str(get_plugin_option_value("whitelistcodecs", "alac,wav,flac,dsf")).split(",")
allow_blacklisted_codec_in_song : int = int(get_plugin_option_value("allowblacklistedcodecinsong", "1"))
disable_navigable_album : int = int(get_plugin_option_value("disablenavigablealbumview", "0"))
#tag_initial_page_enabled_prefix : str = plugin_config_variable_name("taginitialpageenabled")
autostart : int = int(get_plugin_option_value("autostart", "0"))
log_intermediate_url : bool = get_plugin_option_value("log_intermediate_url", "0") == "1"

class UpmpdcliSubsonicConfig(ConfigurationInterface):
    
    def getBaseUrl(self) -> str: return get_plugin_option_value("baseurl")
    def getPort(self) -> int: return get_plugin_option_value("port")
    def getUserName(self) -> str: return get_plugin_option_value("user")
    def getPassword(self) -> str: return get_plugin_option_value("password")
    def getApiVersion(self) -> str: return libsonic.API_VERSION
    def getAppName(self) -> str: return "upmpdcli"
