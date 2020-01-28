#!/usr/bin/python3
from __future__ import print_function

# Metadata getter for French radio stations (Radio France)
# Script based on meta-fip.py script (https://www.lesbonscomptes.com)
#
# 'stationid' is first parameter (set in config file)

import requests
import json
import sys
import os
import time


def elemExists(obj, elem):
    if elem in obj:
        return True
    return False

def elemNumber(objN, elemN):
    if elemN in objN:
        return objN[elemN]
    return 0

def elemText(objT, elemT):
    if elemT in objT:
        return objT[elemT]
    return ''

def firstvalid(a, names):
    for nm in names:
        if nm in a and a[nm]:
            return a[nm]
    return ''


# def titlecase(t):
#     return " ".join([s.capitalize() for s in t.split()])


try:
    if len(sys.argv) > 1:
        stationid = int(sys.argv[1])
    else:
        stationid = int(sys.argv)
except:
    sys.exit(1)

else:
    try:
        r = requests.get('https://api.radiofrance.fr/livemeta/pull/' + str(stationid))
        r.raise_for_status()
    except:
        sys.exit(1)

    else:
        try:
            newjsd = r.json()

        except:
            sys.exit(1)

        else:
            now      = time.time()
            metadata = False

            if elemExists(newjsd, 'steps'):
                metadata_in = newjsd['steps']
                valid_items = list([])

                # Sort items, give priority to items that have not elapsed.
                for step in metadata_in.values():
                    stepId = elemText(step, 'stepId')
                    depth  = elemNumber(step, 'depth')
                    start  = elemNumber(step, 'start')
                    end    = elemNumber(step, 'end')

                    if end >= now and start <= now:
                        prio = 1
                    else:
                        prio = 2

                    valid_items.append((stepId, -depth, -start, end, prio))

                if valid_items:
                    valid_items.sort(key=lambda x:(x[4],x[2],x[1],x[3]))

                   # For debug purposes
                   # for element in valid_items:
                   #      print('stepId', 'prio', element[4], element[0], 'depth', -element[1], 'start', -element[2], 'end', element[3], 'duration :', element[3] - now)

                    stepId   = (valid_items[0])[0]
                    item     = metadata_in[stepId]

                    if elemText(item, 'title'):
                        metadata = True

            else:
                if elemNumber(newjsd, 'end') >= now and elemNumber(newjsd, 'start') <= now and elemText(newjsd, 'title'):
                    item = newjsd
                    metadata = True

            if metadata:
                title         = item['title']
                display_title = title
                artist        = ''
                album         = ''
                artUrl        = ''

                if item['end']:
                    if(item['end'] - now) > 29:
                        reload = 30
                    else:
                        reload = item['end'] - now
                else:
                    reload = 30

                embedType = elemText(item, 'embedType')

                if embedType == 'song':
                    artist = firstvalid(item, ('performers', 'authors', 'discJockey'))
                    album  = elemText(item, 'titreAlbum')
                    artUrl = elemText(item, 'visual')

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

                    reload = int(item['end'] - now + 1)

                elif embedType == 'expression':
                    titleConcept = elemText(item, 'titleConcept')

                    # For radio streams Linn's Kazoo app displays artist as title,
                    # in order to display artist as well, join 'title' and 'artist'
                    if title and titleConcept:
                        display_title = titleConcept + ' – ' + title

                    elif titleConcept:
                        display_title = titleConcept

                    else:
                        display_title = title

                else:
                    display_title = title

                metadata_out = {'title'  : display_title,
                                'artist' : artist,
                                'album'  : album,
                                'artUrl' : artUrl,
                                'reload' : reload}
                print("%s"% json.dumps(metadata_out))

