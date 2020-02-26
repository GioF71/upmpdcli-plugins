#!/usr/bin/python3
from __future__ import print_function

'''
(inspired by meta-fip.py script (https://www.lesbonscomptes.com/upmpdcli))

Metadata getter for 'Radio France' internet radio stations:

 France Inter
 France Info
 France Culture
 France Bleu
 France Musique
 Fip
 Mouv'

 usage:

 upmpdcli radiolist:

 ...

 [radio '<radiostation name>']
 url          = <stream url>
 artUrl       = <url to artwork>
 metaScript   = <[path to/]filename> stationid
 preferScript = 1

 ...

 stationid = integer identifying radiostation

 example:

  [radio FIP]
  url          = https://stream.radiofrance.fr/fip/fip_hifi.m3u8?id=radiofrance
  artUrl       = http://dietpi/radio-logo/fip.png
  metaScript   = radio-france-meta.py 7
  preferScript = 1


 to do:
   include discjockey, composers, label in metadata
   include description, expressionDescription
   optimisations


  'Radio France' stationid's

  radio station			     stationid
  --------------------------------------------
  France Inter			             1
  France Info                                2
  France Culture                             5
  France Bleu Paris                         68
  France Bleu ...
  France Bleu Pays d'Auvergne               40
  France Bleu ...
  France Musique                             4
  France Musique Easy Classique            401
  France Musique Easy                      402
  France Musique Concerts Radio France     403
  France Musique Musiques du Monde Ocora   404
  France Musique La Jazz                   405
  France Musique La Contemporaine          406
  France Musique La B.O. Musiques de Films 407
  Fip                                        7
  Fip Rock                                  64
  Fip Jazz                                  65
  Fip Groove                                66
  Fip Monde                                 69
  Fip Tout Nouveau                          70
  Fip Reggae                                71
  Fip Electro                               74
  Mouv'                                      6
  Mouv' Classics                           601
  Mouv' DanceHall                          602
  Mouv' RnB & Soul                         603
  Mouv' Rap US                             604
  Mouv' Rap Français                       605
  Mouv' Kids 'n Family                     606
  Mouv' 100% Mix                            75

'''

import json
import requests
import sys
import time

def elemExists(obj, elem):
  if elem in obj:
    return True
  return False

def elemNumber(objN, elemN):
  if elemN in objN:
    return int(objN[elemN])
  return None

def elemText(objT, elemT):
  if elemT in objT:
    return str(objT[elemT])
  return None

def validArtists(a, names):
  for nm in names:
    if nm in a and a[nm]:
      return ' & '.join(a[nm]) if type((a[nm])) is list else a[nm]
  return None

def disp_title(artist, title, year, album):
  ab = ''
  yr = ''

  if year:
    yr += ' (' + str(year) + ')'

  if album:
    ab += ' [' + album + ']'

  if title and artist and year:
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

def return_metadata(title, artist, album, year, artUrl, reload):
  metadata = {'title'  : display_title,
              'artist' : artist,
              'album'  : album,
              'year'   : year,
              'artUrl' : artUrl,
              'reload' : reload}
  print("%s"% json.dumps(metadata))
  return

def return_no_metadata (reload):
  metadata = {'title'  : None,
              'artist' : None,
              'album'  : None,
              'year'   : None,
              'artUrl' : None,
              'reload' : reload}
  print("%s"% json.dumps(metadata))
  return


try:
  if len(sys.argv) > 1:
    stationid = int(sys.argv[1])

  else:
    stationid = int(sys.argv)

except:
  return_no_metadata(99999999)

else:
  try:
    r = requests.get('https://api.radiofrance.fr/livemeta/pull/' + str(stationid))
    r.raise_for_status()
  except:
    return_no_metadata(99999999)

  else:
    try:
      newjsd = r.json()

    except:
      return_no_metadata(120)

    else:
      if elemExists(newjsd, 'levels'):
        metadata_levels = newjsd['levels']
        levels = []

        for level in metadata_levels:
          if elemExists(level, 'position') and elemExists(level, 'items'):

            if level['items'][int(level['position'])]:
              levels.append(level['items'][int(level['position'])])

        if elemExists(newjsd, 'steps'):
          metadata_steps = newjsd['steps']
          playing_items  = []

          for level in levels:
            playing_items.append((metadata_steps[level]))

          if playing_items:
            item      = playing_items[-1]
            embedType = elemText(item, 'embedType')
            title     = elemText(item, 'title')
            end       = elemNumber(item, 'end')
            now       = int(time.time())

            if end:
              if end > now:
                reload = end - now + 1

              else:
                reload = 10

              if embedType == 'song':
                artist        = validArtists(item, ('highlightedArtists', 'performers', 'authors'))
                year          = elemText(item, 'anneeEditionMusique')
                album         = elemText(item, 'titreAlbum')
                artUrl        = elemText(item, 'visual')
              # For radio streams title is displayed twice (in both artist and title fields),
              # in order to display artist as well, join 'title' and 'artist'
                display_title = disp_title(artist, title, year, album)

                return_metadata(display_title, artist, album, year, artUrl, reload)

              else:
                titles = []

                if len(playing_items) == 1 :
                  if elemText(playing_items[0], 'titleConcept') != elemText(playing_items[0], 'title'):
                    titles.append(elemText(playing_items[0], 'titleConcept'))
                    titles.append(elemText(playing_items[0], 'title'))
                  else:
                    titles.append(elemText(playing_items[0], 'title'))

                else:
                  for i in playing_items:
                    if elemText(i, 'title'):
                      titles.append(i['title'])

                if titles:
                 #dtitles = sorted(set(titles), key=titles.index), list(dict(dict.fromkeys(titles)) seems faster:
                  dtitles = list(dict.fromkeys(titles))
                  display_title = ' – '.join(dtitles)

                  return_metadata(display_title, None, None, None, None, reload)

                else:
                  return_no_metadata(reload)

            else:
              return_no_metadata(None)

          else:
            return_no_metadata(None)

        else:
          return_no_metadata(None)

      else:
        return_no_metadata(None)
