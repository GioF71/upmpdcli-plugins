#!/usr/bin/python3
from __future__ import print_function

# Metadata getter for Radio Paradiase stations
# Script based on meta-fip.py script (https://www.lesbonscomptes.com/upmpdcli/)
#
# 'channelid' is first parameter (set in config file)

import json
import requests
import sys
import time

def elemNumber(objN, elemN):
  if elemN in objN:
      r = int(objN[elemN])
      if r >= 0:
        return r
  return 0

def elemText(objT, elemT):
  if elemT in objT:
    return str(objT[elemT])
  return None

def return_metadata(title, artist, album, year, artUrl, reload):
  metadata = {'title'  : display_title,
              'artist' : artist,
              'album'  : album,
              'year'   : year,
              'artUrl' : artUrl,
              'reload' : reload}
  print("%s"% json.dumps(metadata))
  return

def return_no_metadata(reload):
  metadata = {'title'  : None,
              'artist' : None,
              'album'  : None,
              'year'   : None,
              'artUrl' : None,
              'reload' : reload}
  print("%s"% json.dumps(metadata))
  return

def disp_title(artist, title, year, album):
  ab = ''
  yr = ''
  dt = ''

  if year:
    yr += ' (' + str(year) + ')'

  if album:
    ab += ' [' + album + ']'

  if   title and artist and year:
    dt = artist + ' – ' + title + yr + ab
  elif title and artist:
    dt = artist + ' – ' + title + ab
  elif title and year:
    dt = title + yr + ab
  elif title:
    dt = title + ab
  elif artist and album:
    dt = artist + + ' – Album: ' + ab + yr
  elif artist:
    dt = artist + yr
  elif album:
    dt = 'Album: ' + ab + yr
  return dt



if len(sys.argv) > 1:
  channelid = int(sys.argv[1])
else:
  sys.exit(1)

try:
  r = requests.get('https://api.radioparadise.com/api/now_playing?chan=' +
                   str(channelid))
  r.raise_for_status()
except:
  return_no_metadata(10)

try:
  song = r.json()
except:
  return_no_metadata(120)


now  = int(time.time())
time = elemNumber(song, 'time')
#print('now %d time %d' % (now, time), file=sys.stderr)
if time > 2 :
  title   = elemText(song, 'title')
  artist  = elemText(song, 'artist')
  album   = elemText(song, 'album')
  year    = elemText(song, 'year')
  artUrl  = elemText(song, 'cover')

  # For radio streams title is displayed twice (in both artist
  # and title fields),
  # in order to display artist as well, join 'title' and 'artist'
  display_title = disp_title(artist, title, year, album)
  return_metadata(display_title, artist, album, year, artUrl, time + 1)
else:
  return_no_metadata(time + 1)
