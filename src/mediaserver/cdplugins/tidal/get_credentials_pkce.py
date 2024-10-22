#!/usr/bin/python3

"""Use this program to obtain pkce credentials."""

# Copyright (C) 2024 Giovanni Fulco
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
from pathlib import Path
import tidalapi

tidal_plugin_name : str = "tidal"


def print_setting(name: str, value: str):
    """Print function for script settings."""
    print(f"{name}={value}")


tmp_directory : str = "generated"
file_path : str = os.path.join("/tmp", tmp_directory)
if not os.path.exists(file_path):
    os.makedirs(file_path)

file_name = f"{file_path}/pkce.credentials.json"

session = tidalapi.Session()
session_file1 = Path(file_name)
# Will run until you complete the login process
session.login_session_file(session_file1, do_pkce=True)

token_type = session.token_type
session_id = session.session_id
access_token = session.access_token
refresh_token = session.refresh_token

print("PKCE credentials file, stored as /var/cache/upmpdcli/tidal/pkce.credentials.json")
cred_file = open(file=file_name, mode="r", encoding="utf-8")
cred_dict = json.load(cred_file)
print(json.dumps(cred_dict, indent = 4, sort_keys = True))
