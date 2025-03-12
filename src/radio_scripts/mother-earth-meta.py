#!/usr/bin/env python3

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

import requests
import json
import sys
import os

apiurl = "https://motherearth.streamserver24.com/api/nowplaying"

def msg(s):
    print(f"{s}", file=sys.stderr)
def usage():
    msg(f"Usage: {os.path.basename(sys.argv[0])} <station_shortcode>")
    msg(" Station shortcodes: motherearth_klassik, motherearth_instrumental, motherearth_jazz, motherearth\n")
    sys.exit(1)

if len(sys.argv) < 2:
    usage()
shortcode = sys.argv[1]

try:
    r = requests.get(apiurl)
    r.raise_for_status()
    jsd = r.json()
except:
    sys.exit(1)
      
for station in jsd:
    try:
        sc = station["station"]["shortcode"]
        #msg(sc)
        if sc == shortcode:
            nowplaying = station["now_playing"]
            data = {}
            data["title"] = nowplaying["song"]["title"]
            data["artist"] = nowplaying["song"]["artist"]
            data["artUrl"] = nowplaying["song"]["art"]
            data["reload"] = int(nowplaying["remaining"])
            print(f"{json.dumps(data)}")
    except:
        sys.exit(1)
