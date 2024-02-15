#!/usr/bin/python3

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
