#!/usr/bin/env python3

'''
Dynamic art for Dutch Public Broadcasting Service (NPO) FunX internet radio stations:

# NPO FUNX

[radio NPO FunX]
url = http://icecast.omroep.nl/funx-bb-mp3			
artUrl = 
artScript = npo-funx-dynamic-art.py funx broadcast-info

[radio NPO FunX Dance]
url = http://icecast.omroep.nl/funx-dance-bb-mp3
artUrl = 
artScript = npo-funx-dynamic-art.py dance

[radio NPO Funx Slow Jamz]
url = http://icecast.omroep.nl/funx-slowjamz-bb-mp3
artUrl= 
artScript = npo-funx-dynamic-art.py slow-jamz

[radio NPO FunX Arab]
url = http://icecast.omroep.nl/funx-arab-bb-mp3
artUrl = 
artScript = npo-funx-dynamic-art.py amsterdam-arab

[radio NPO Funx Hip Hop]
url = http://icecast.omroep.nl/funx-hiphop-bb-mp3
artUrl = 
artScript = npo-funx-dynamic-art.py denhaag-hiphop

[radio NPO FunX Reggae]
url = http://icecast.omroep.nl/funx-reggae-bb-mp3
artUrl = 
artScript = npo-funx-dynamic-art.py rotterdam-afro

[radio NPO FunX Latin]
url = http://icecast.omroep.nl/funx-latin-bb-mp3
artUrl = 
artScript = npo-funx-dynamic-art.py utrecht-latin

[radio NPO FunX Amsterdam]
url = http://icecast.omroep.nl/funx-amsterdam-bb-mp3
artUrl = 
artScript = npo-funx-dynamic-art.py amsterdam broadcast-info

[radio NPO FunX Rotterdam]
url = http://icecast.omroep.nl/funx-rotterdam-bb-mp3
artUrl = 
artScript = npo-funx-dynamic-art.py rotterdam broadcast-info

[radio NPO FunX Den Haag]
url = http://icecast.omroep.nl/funx-denhaag-bb-mp3
artUrl = 
artScript = npo-funx-dynamic-art.py den-haag broadcast-info

[radio NPO FunX Utrecht]
url = http://icecast.omroep.nl/funx-utrecht-bb-mp3
artUrl = 
artScript = npo-funx-dynamic-art.py utrecht broadcast-info

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

def mkStr(elemStr):
  if elemStr:
    return str(elemStr)
  return ''


delay          = 0
offset         = 2
validtrack     = False
validtrackart  = False
validbroadcast = False


if len(sys.argv) > 1:
  if str(sys.argv[1]) == 'funx':
    channel  = ''
  else:
    channel  =  mkStr(sys.argv[1])
  time.sleep(delay)
  url_tracks = 'https://www.funx.nl/api/tracks/' + channel

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
		  
  if not validtrackart and len(sys.argv) > 2:

    if str(sys.argv[2]) == 'broadcast-info':
      url_broadcasts = 'https://www.funx.nl/api/broadcasts/' + channel

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