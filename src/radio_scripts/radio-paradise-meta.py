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

def elemText(objT, elemT):
    if elemT in objT:
        return objT[elemT]
    return ''

def elemNumber(objN, elemN):
    if elemN in objN:
        return objN[elemN]
    return 0

try:
    if len(sys.argv) > 1:
        channelid = int(sys.argv[1])
    else:
        channelid = int(sys.argv)
except:
    sys.exit(1)

else:
    try:
        r = requests.get('https://api.radioparadise.com/api/now_playing?chan=' + str(channelid))
        r.raise_for_status()
    except:
        sys.exit(1)

    else:
        try:
            song = r.json()
        except:
            sys.exit(1)
        else:
            now = time.time()
            time = int(elemNumber(song, 'time'))

            if time > 0 :
                title   = elemText(song, 'title')
                artist  = elemText(song, 'artist')
                album   = elemText(song, 'album')
                artUrl  = elemText(song, 'cover')

                # For radio streams Linn's Kazoo app displays artist as title,
                # in order to display artist as well, join 'title' and 'artist'
                if title and artist and album:
                    display_title = artist + ' – ' + title + ' (from the album: ' + album + ')'

                elif title and artist and not album:
                    display_title = artist + ' – ' + title

                elif title and album and not artist:
                    display_title = title + ' (from the album: ' + album + ')'

                else:
                    display_title = title

                metadata_out = {'title'  : display_title,
                                'artist' : artist,
                                'album'  : album,
                                'artUrl' : artUrl,
                                'reload' : time + 1}
                print("%s"% json.dumps(metadata_out))
