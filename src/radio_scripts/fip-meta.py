#!/usr/bin/python3
from __future__ import print_function

# metadata getter for French radio FIP stations, we get the station
# number as first parameter (set in config file).

import requests
import json
import sys
import os
import time

def firstvalid(a, names):
    for nm in names:
        if nm in a and a[nm]:
            return a[nm]
    return ''

def titlecase(t):
    return " ".join([s.capitalize() for s in t.split()])

stationid = ''
if len(sys.argv) > 1:
    stationid = sys.argv[1]
    # Make sure this not one of the upmpdcli param namess, but a number
    try:
        bogus = int(stationid)
    except:
        stationid = ''

r = requests.get('https://www.fip.fr/livemeta/pull/' + stationid)
r.raise_for_status()
newjsd = r.json()

songs = newjsd['steps']
now = time.time()

for song in songs.values():
    song_end = song['end']
    if song['embedType'] == 'song' and song_end >= now and song['start'] <= now:
        title = titlecase(firstvalid(song, ('title',)))
        artist = titlecase(firstvalid(song, ('performers', 'authors')))
        metadata = {'title' : title,
                    'artist': artist,
                    'artUrl' : song['visual'],
                    'reload' : int(song_end - now + 1)}
        print("%s"% json.dumps(metadata))
