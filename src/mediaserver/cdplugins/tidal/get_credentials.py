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

import tidalapi
from datetime import datetime
import argparse
import json

tidal_plugin_name : str = "tidal"


def print_setting(name : str, value : str):
    print(f"{tidal_plugin_name}{name} = {value}")


def main():
    parser = argparse.ArgumentParser(description='Tidal Credentials Retriever')
    parser.add_argument(
        '--f',
        type=str,
        help='Optionally write credentials to the specified file')
    args = parser.parse_args()
    if args.f:
        print(f"Credentials will be written to [{args.f}]")
    session = tidalapi.Session()
    # Will run until you visit the printed url and link your account
    session.login_oauth_simple()
    token_type = session.token_type
    access_token = session.access_token
    refresh_token = session.refresh_token
    expiry_time = session.expiry_time
    storable_expiry_time = datetime.timestamp(expiry_time)
    print("Settings for upmpdcli below, to be set in upmpdcli.conf")
    print_setting("tokentype", token_type)
    print_setting("accesstoken", access_token)
    print_setting("refreshtoken", refresh_token)
    print_setting("expirytime", storable_expiry_time)
    if args.f:
        print(f"Writing the credentials to file [{args.f}] ...")
        # write a new json file
        cred_dict : dict[str, str] = {
            "authentication_type": "oauth2",
            "tokentype": token_type,
            "accesstoken": access_token,
            "refreshtoken": refresh_token,
            "expirytimetimestampstr": storable_expiry_time
        }
        with open(args.f, 'w') as cred_file:
            json.dump(cred_dict, cred_file, indent = 4)
        print(f"Credentials written to [{args.f}]")


if __name__ == "__main__":
    main()
