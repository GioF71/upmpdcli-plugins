#!/usr/bin/python3
# Metadata getter for French radio stations (Radio France)
# Script based on meta-fip.py script (https://www.lesbonscomptes.com)
#
# 'stationid' is first parameter (set in config file)

import requests
import json
import sys
import time

def firstvalid(a, names):
    for nm in names:
        if nm in a and a[nm]:
            return a[nm]
    return ''

# def titlecase(t):
#     return " ".join([s.capitalize() for s in t.split()])

stationid = ''
if len(sys.argv) > 1:
    stationid = sys.argv[1]
    # Make sure this not one of the upmpdcli param names, but a number
    try:
        bogus = int(stationid)
    except:
        stationid = ''

r = requests.get('https://api.radiofrance.fr/livemeta/pull/' + stationid)
r.raise_for_status()
newjsd = r.json()

songs = newjsd['steps']
now = time.time()

metadata = {}
for song in songs.values():
    if song['embedType'] == 'song' and song['end'] >= now and song['start'] <= now:
        artist = firstvalid(song, ('performers', 'authors'))
        # For radio streams Linn's Kazoo app displays artist as title,
        # in order to display artist as well, join 'title' and 'artist'
        title  = artist + ' – ' + song['title']
        metadata = {'title'  : title,
                    'artist' : artist,
		    'album'  : song['titreAlbum'],
                    'artUrl' : song['visual'],
                    'reload' : int(song['end'] - now + 1)}
        print("%s"% json.dumps(metadata))
        sys.exit(0)
print("%s"% json.dumps(metadata))
sys.exit(0)

