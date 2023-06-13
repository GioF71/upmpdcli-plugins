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

from upmplgutils import getOptionValue
import libsonic
from subsonic_connector.configuration import ConfigurationInterface

subsonic_max_return_size : int = 500 # hard limit
items_per_page : int = min(subsonic_max_return_size, int(getOptionValue("subsonicitemsperpage", "36")))
append_year_to_album : int = int(getOptionValue("subsonicappendyeartoalbum", "1"))
append_codecs_to_album : int = int(getOptionValue("subsonicappendcodecstoalbum", "1"))
whitelist_codecs : list[str] = str(getOptionValue("subsonicwhitelistcodecs", "alac,wav,flac,dsf")).split(",")
allow_blacklisted_codec_in_song : int = int(getOptionValue("subsonicallowblacklistedcodecinsong", "1"))
disable_sparse_album : int = int(getOptionValue("subsonicdisablesparsealbumview", "0"))
tag_enabled_prefix : str = "subsonictagenabled"
autostart : int = int(getOptionValue("subsonicautostart", "0"))

class UpmpdcliSubsonicConfig(ConfigurationInterface):
    
    def getBaseUrl(self) -> str: return getOptionValue('subsonicbaseurl')
    def getPort(self) -> int: return getOptionValue('subsonicport')
    def getUserName(self) -> str: return getOptionValue('subsonicuser')
    def getPassword(self) -> str: return getOptionValue('subsonicpassword')
    def getApiVersion(self) -> str: return libsonic.API_VERSION
    def getAppName(self) -> str: return "upmpdcli"
