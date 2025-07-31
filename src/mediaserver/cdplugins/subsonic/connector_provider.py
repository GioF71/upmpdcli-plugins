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

from subsonic_connector.connector import Connector
from config import UpmpdcliSubsonicConfig
from msgproc_provider import msgproc

msgproc.log(f"base_url/port: [{UpmpdcliSubsonicConfig().getBaseUrl()}]:[{UpmpdcliSubsonicConfig().getPort()}]")
msgproc.log(f"server_path: [{UpmpdcliSubsonicConfig().getServerPath()}]")
msgproc.log(f"User Agent: [{UpmpdcliSubsonicConfig().getUserAgent()}]")

connector: Connector = Connector(UpmpdcliSubsonicConfig())


def get():
    return connector
