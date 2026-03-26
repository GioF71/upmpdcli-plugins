#!/usr/bin/env python3

'''
Dynamic art for Dutch Public Broadcasting Service (NPO) internet radio stations:

# NPO

[radio NPO Radio 1]
url = http://icecast.omroep.nl/radio1-bb-mp3
artUrl = 
artScript = npo-dynamic-art.py nporadio1

[radio NPO Radio 2]
url = http://icecast.omroep.nl/radio2-bb-mp3
artUrl = 
artScript = npo-dynamic-art.py nporadio2

[radio NPO 3FM]
url = http://icecast.omroep.nl/3fm-bb-mp3
artUrl = 
artScript = npo-dynamic-art.py npo3fm

[radio NPO 3FM Alternative]
url = http://icecast.omroep.nl/3fm-alternative-mp3
artUrl = 
artScript = npo-dynamic-art.py npo3fm alternative
 
[radio NPO 3FM KXradio]
url = http://icecast.omroep.nl/3fm-serioustalent-mp3
artUrl = 
artScript = npo-dynamic-art.py npo3fm kx

[radio NPO Radio 4]
url = http://icecast.omroep.nl/radio4-bb-mp3
artUrl = 
artScript = npo-dynamic-art.py nporadio4

[radio NPO Radio 4 Concerten]
url = http://icecast.omroep.nl/radio4-eigentijds-mp3
artUrl = 
artScript = npo-dynamic-art.py nporadio4 concerten

[radio NPO Radio 5]
url = http://icecast.omroep.nl/radio5-bb-mp3
artUrl = 
artScript = npo-dynamic-art.py nporadio5

[radio NPO Soul & Jazz]
url = http://icecast.omroep.nl/radio6-bb-mp3
artUrl = 
artScript = npo-dynamic-art.py nporadio2 soulenjazz

[radio NPO Sterren NL]
url = http://icecast.omroep.nl/radio2-sterrennl-mp3
artUrl = 
artScript = npo-dynamic-art.py nporadio5 sterrennl

'''


import json
import requests
import sys
import time
from datetime import datetime


def elemExists(obj, elem):
  if elem in obj:
    return True
  return False

def mkStr(elemT):
  if elemT:
    return str(elemT)
  return ''


delay          = 0
offset         = 2
validtrack     = False
validtrackart  = False
validbroadcast = False


if len(sys.argv) == 2:
  time.sleep(delay)
  url_tracks     = 'https://www.' + str(sys.argv[1]) + '.nl/api//tracks'
elif len(sys.argv) > 2:
  time.sleep(delay)
  url_tracks     = 'https://www.' + str(sys.argv[1]) + '.nl/api/' + str(sys.argv[2]) + '/tracks'

if len(sys.argv) > 1:
  # First, check if there's valid track art, if not check for valid broadcast art
  try:
    r2 = requests.get(url_tracks)
    r2.raise_for_status()
  except:
    pass
  else:
    try:
      newjsd_tracks = r2.json()
    except:
      pass
    else:
      if elemExists(newjsd_tracks, 'data'):
        now = int(time.time())
        # Assumption: tracks are listed in descending order (start time)
        for track in newjsd_tracks['data']:
          if elemExists(track, 'startdatetime'):
            trackstart = int(datetime.timestamp(datetime.strptime(track['startdatetime'], '%Y-%m-%dT%H:%M:%S')))
            trackend   = int(datetime.timestamp(datetime.strptime(track['stopdatetime'],   '%Y-%m-%dT%H:%M:%S')))
            if trackstart < now + offset and (trackend > now + offset - 1 or trackstart == trackend):
              validtrack = True
              break
            if trackstart < now + offset and trackend < now + offset:
              break
        if validtrack:
          artUrl = mkStr(track['image_url']).replace('{format}', 'w_1080,h_1080')
          if artUrl:
            validtrackart = True
            print(artUrl)

  if not validtrackart:

    if len(sys.argv) == 2:
      url_broadcasts = 'https://www.' + str(sys.argv[1]) + '.nl/api/broadcasts'
    elif len(sys.argv) > 2:
      url_broadcasts = 'https://www.' + str(sys.argv[1]) + '.nl/api/' + str(sys.argv[2]) + '/broadcasts'

    try:
      r1 = requests.get(url_broadcasts)
      r1.raise_for_status()
    except:
      pass
    else:
      try:
        newjsd_broadcasts = r1.json()
      except:
        pass
      else:
        if elemExists(newjsd_broadcasts, 'data'):
          # Assumption: broadcasts are listed in descending order (start time)
          for broadcast in newjsd_broadcasts['data']:
            if elemExists(broadcast, 'startdatetime'):
              trackstart = int(datetime.timestamp(datetime.strptime(broadcast['startdatetime'], '%Y-%m-%dT%H:%M:%S')))
              trackend   = int(datetime.timestamp(datetime.strptime(broadcast['stopdatetime'],   '%Y-%m-%dT%H:%M:%S')))
              if trackstart < now + offset and (trackend > now + offset - 1 or trackstart == trackend):
                validbroadcast = True
                break
            if trackstart < now + offset and trackend < now + offset:
              break
          if validbroadcast:
            artUrl = mkStr(broadcast['image_url']).replace('{format}', 'w_1080,h_1080')
            if artUrl:
              print(artUrl)