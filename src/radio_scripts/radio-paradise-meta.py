#!/usr/bin/python3
from __future__ import print_function

# Metadata getter for Radio Paradiase stations
# Script based on meta-fip.py script (https://www.lesbonscomptes.com/upmpdcli/)
#
# 'channelid' is first parameter (set in config file)

import requests
import json
import sys
import os
import time

channelid = ''
if len(sys.argv) > 1:
    channelid = sys.argv[1]
    # Make sure this not one of the upmpdcli param names, but a number
    try:
        bogus = int(channelid)
    except:
        channelid = ''

r = requests.get('https://api.radioparadise.com/api/now_playing?chan=' + channelid)
r.raise_for_status()

song = r.json()
now = time.time()

if song['time'] > 0 :
        # For radio streams Linn's Kazoo app displays artist as title,
        # in order to display artist as well, join 'title' and 'artist'
	title = song['artist'] + ' – ' + song['title']
	metadata = {'title'  : title,
                    'artist' : song['artist'],
                    'album'  : song['album'],
                    'artUrl' : song['cover'],
                    'reload' : int(song['time'] + 1)}
	print("%s"% json.dumps(metadata))
