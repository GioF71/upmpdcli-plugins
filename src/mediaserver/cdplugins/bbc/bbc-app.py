#!/usr/bin/python3
#
# Almost completely copied from the Kodi BBC addon, which has an MIT license, retained for the modifications:
# https://github.com/jonjomckay/kodi-addon-bbcsounds
# Copyright 2020 Jonjo McKay
# 
# Additional code and modifications:
# Copyright (C) 2021 J.F.Dockes
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
# NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
# OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import datetime
import dateutil.parser
import json
import os
import re
import requests
import sys
import urllib

from bs4 import BeautifulSoup

import conftree
import cmdtalkplugin
from upmplgutils import *
from upmplgmodels import *

# Reusing the Tidal plugin routing module
from routing import Plugin
plugin = Plugin('') 

bbcidprefix = '0$bbc$'

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

stations = [
    {'id' : 'p00fzl68', 'name': 'BBC Asian Network', 'image': 'bbc_asian_network_colour'},
    {'id' : 'p00fzl78', 'name': 'BBC Coventry & Warwickshire', 'image': 'bbc_radio_coventry_warwickshire_colour'},
    {'id' : 'p00fzl7f', 'name': 'BBC Essex', 'image': 'bbc_radio_essex_colour'},
    {'id' : 'p00fzl7q', 'name': 'BBC Hereford & Worcester', 'image': 'bbc_radio_hereford_worcester_colour'},
    {'id' : 'p00fzl82', 'name': 'BBC Newcastle', 'image': 'bbc_radio_newcastle_colour'},
    {'id' : 'p00fzl86', 'name': 'BBC Radio 1', 'image': 'bbc_radio_one_colour'},
    {'id' : 'p00fzl64', 'name': 'BBC Radio 1Xtra', 'image': 'bbc_1xtra_colour'},
    {'id' : 'p00fzl8v', 'name': 'BBC Radio 2', 'image': 'bbc_radio_two_colour'},
    {'id' : 'p00fzl8t', 'name': 'BBC Radio 3', 'image': 'bbc_radio_three_colour'},
    {'id' : 'p00fzl7j', 'name': 'BBC Radio 4 FM', 'image': 'bbc_radio_fourfm_colour'},
    {'id' : 'p00fzl7k', 'name': 'BBC Radio 4 LW', 'image': 'bbc_radio_four_colour'},
    {'id' : 'p00fzl7l', 'name': 'BBC Radio 4 Extra', 'image': 'bbc_radio_four_extra_colour'},
    {'id' : 'p00fzl7g', 'name': 'BBC Radio 5 live', 'image': 'bbc_radio_five_live_colour'},
    {'id' : 'p00fzl7h', 'name': 'BBC Radio 5 live sports extra', 'image': 'bbc_radio_five_live_sports_extra_colour'},
    {'id' : 'p00fzl65', 'name': 'BBC Radio 6 Music', 'image': 'bbc_6music_colour'},
    {'id' : 'p00fzl74', 'name': 'BBC Radio Berkshire', 'image': 'bbc_radio_berkshire_colour'},
    {'id' : 'p00fzl75', 'name': 'BBC Radio Bristol', 'image': 'bbc_radio_bristol_colour'},
    {'id' : 'p00fzl76', 'name': 'BBC Radio Cambridgeshire', 'image': 'bbc_radio_cambridge_colour'},
    {'id' : 'p00fzl77', 'name': 'BBC Radio Cornwall', 'image': 'bbc_radio_cornwall_colour'},
    {'id' : 'p00fzl79', 'name': 'BBC Radio Cumbria', 'image': 'bbc_radio_cumbria_colour'},
    {'id' : 'p00fzl7b', 'name': 'BBC Radio Cymru', 'image': 'bbc_radio_cymru_colour'},
    {'id' : 'p00fzl7c', 'name': 'BBC Radio Derby', 'image': 'bbc_radio_derby_colour'},
    {'id' : 'p00fzl7d', 'name': 'BBC Radio Devon', 'image': 'bbc_radio_devon_colour'},
    {'id' : 'p00fzl7m', 'name': 'BBC Radio Foyle', 'image': 'bbc_radio_foyle_colour'},
    {'id' : 'p00fzl7n', 'name': 'BBC Radio Gloucestershire', 'image': 'bbc_radio_gloucestershire_colour'},
    {'id' : 'p00fzl7p', 'name': 'BBC Radio Guernsey', 'image': 'bbc_radio_guernsey_colour'},
    {'id' : 'p00fzl7r', 'name': 'BBC Radio Humberside', 'image': 'bbc_radio_humberside_colour'},
    {'id' : 'p00fzl7s', 'name': 'BBC Radio Jersey', 'image': 'bbc_radio_jersey_colour'},
    {'id' : 'p00fzl7t', 'name': 'BBC Radio Kent', 'image': 'bbc_radio_kent_colour'},
    {'id' : 'p00fzl7v', 'name': 'BBC Radio Lancashire', 'image': 'bbc_radio_lancashire_colour'},
    {'id' : 'p00fzl7w', 'name': 'BBC Radio Leeds', 'image': 'bbc_radio_leeds_colour'},
    {'id' : 'p00fzl7x', 'name': 'BBC Radio Leicester', 'image': 'bbc_radio_leicester_colour'},
    {'id' : 'p00fzl7y', 'name': 'BBC Radio Lincolnshire', 'image': 'bbc_radio_lincolnshire_colour'},
    {'id' : 'p00fzl6f', 'name': 'BBC Radio London', 'image': 'bbc_london_colour'},
    {'id' : 'p00fzl7z', 'name': 'BBC Radio Manchester', 'image': 'bbc_radio_manchester_colour'},
    {'id' : 'p00fzl80', 'name': 'BBC Radio Merseyside', 'image': 'bbc_radio_merseyside_colour'},
    {'id' : 'p00fzl81', 'name': 'BBC Radio Nan Gaidheal', 'image': 'bbc_radio_nan_gaidheal_colour'},
    {'id' : 'p00fzl83', 'name': 'BBC Radio Norfolk', 'image': 'bbc_radio_norfolk_colour'},
    {'id' : 'p00fzl84', 'name': 'BBC Radio Northampton', 'image': 'bbc_radio_northampton_colour'},
    {'id' : 'p00fzl85', 'name': 'BBC Radio Nottingham', 'image': 'bbc_radio_nottingham_colour'},
    {'id' : 'p00fzl8c', 'name': 'BBC Radio Oxford', 'image': 'bbc_radio_oxford_colour'},
    {'id' : 'p00fzl8d', 'name': 'BBC Radio Scotland (FM)', 'image': 'bbc_radio_scotland_fm_colour'},
    {'id' : 'p00fzl8g', 'name': 'BBC Radio Scotland (MW)', 'image': 'bbc_radio_scotland_colour'},
    {'id' : 'p00fzl8b', 'name': 'BBC Radio Scotland (Orkney)', 'image': 'bbc_radio_scotland_colour'},
    {'id' : 'p00fzl8j', 'name': 'BBC Radio Scotland (Shetland)', 'image': 'bbc_radio_scotland_colour'},
    {'id' : 'p00fzl8h', 'name': 'BBC Radio Sheffield', 'image': 'bbc_radio_sheffield_colour'},
    {'id' : 'p00fzl8k', 'name': 'BBC Radio Shropshire', 'image': 'bbc_radio_shropshire_colour'},
    {'id' : 'p00fzl8l', 'name': 'BBC Radio Solent', 'image': 'bbc_radio_solent_colour'},
    {'id' : 'p00fzl8n', 'name': 'BBC Radio Stoke', 'image': 'bbc_radio_stoke_colour'},
    {'id' : 'p00fzl8p', 'name': 'BBC Radio Suffolk', 'image': 'bbc_radio_suffolk_colour'},
    {'id' : 'p00fzl8w', 'name': 'BBC Radio Ulster', 'image': 'bbc_radio_ulster_colour'},
    {'id' : 'p00fzl8y', 'name': 'BBC Radio Wales (FM)', 'image': 'bbc_radio_wales_fm_colour'},
    {'id' : 'p00fzl8x', 'name': 'BBC Radio Wales (LW)', 'image': 'bbc_radio_wales_colour'},
    {'id' : 'p00fzl90', 'name': 'BBC Radio York', 'image': 'bbc_radio_york_colour'},
    {'id' : 'p00fzl8m', 'name': 'BBC Somerset', 'image': 'bbc_radio_somerset_sound_colour'},
    {'id' : 'p00fzl8q', 'name': 'BBC Surrey', 'image': 'bbc_radio_surrey_colour'},
    {'id' : 'p00fzl8r', 'name': 'BBC Sussex', 'image': 'bbc_radio_sussex_colour'},
    {'id' : 'p00fzl93', 'name': 'BBC Tees', 'image': 'bbc_tees_colour'},
    {'id' : 'p00fzl96', 'name': 'BBC Three Counties Radio', 'image': 'bbc_three_counties_radio_colour'},
    {'id' : 'p00fzl8z', 'name': 'BBC Wiltshire', 'image': 'bbc_radio_wiltshire_colour'},
    {'id' : 'p00fzl9f', 'name': 'BBC WM 95.6', 'image': 'bbc_wm_colour'},
    {'id' : 'p02zbmb3', 'name': 'BBC World Service', 'image': 'bbc_world_service_colour'},
    {'id' : 'p02jf21y', 'name': 'CBeebies Radio', 'image': 'cbeebies_radio_colour'},
]

def find_station(id):
    for station in stations:
        if station['id'] == id:
            return station
    return None

_g_initok = False

def maybeinit(a={}):
    global httphp
    global pathprefix
    global _g_initok
    global upconfig

    # Do this always
    setidprefix(bbcidprefix)

    if _g_initok:
        return True

    if "UPMPD_HTTPHOSTPORT" not in os.environ:
        raise Exception("No UPMPD_HTTPHOSTPORT in environment")
    httphp = os.environ["UPMPD_HTTPHOSTPORT"]
    if "UPMPD_PATHPREFIX" not in os.environ:
        raise Exception("No UPMPD_PATHPREFIX in environment")
    pathprefix = os.environ["UPMPD_PATHPREFIX"]
    if "UPMPD_CONFIG" not in os.environ:
        raise Exception("No UPMPD_CONFIG in environment")
    upconfig = conftree.ConfSimple(os.environ["UPMPD_CONFIG"])
    
    setMimeAndSamplerate("audio/mpeg", "44100")
    _g_initok = True


def get_page(url):
    # download the source HTML for the page using requests
    # and parse the page using BeautifulSoup
    return BeautifulSoup(requests.get(url).text, 'html.parser')

def trackdetails(trackid):
    global pathprefix
    maybeinit()

    programme = requests.get('https://www.bbc.co.uk/programmes/' + trackid + '.json')
    programme_json = programme.json()["programme"]

    picked_url = None

    for version in programme_json["versions"]:
        url = \
           'https://open.live.bbc.co.uk/mediaselector/6/select/version/2.0/mediaset/iptv-all/vpid/'\
           + version["pid"] + '/format/json'
        uplog("DETAILS: getting: %s" % url)
        playlist = requests.get(url)
        playlist_json = playlist.json()

        if "media" not in playlist_json:
            # TODO
            continue

        # Filter by only audio items, and order with the highest bitrate first
        audio_items = [item for item in playlist_json['media'] if item['kind'] == 'audio']
        audio_items.sort(key=lambda x: x['bitrate'], reverse=True)

        uplog('Found {0} audio items for the programme version {1}'.
              format(len(audio_items), version['pid']))

        # Pick the first stream available for the highest bitrate item
        picked_stream = audio_items[0]
        picked_url = picked_stream["connection"][1]["href"]

        uplog('Picked {0} stream with bitrate {1}'.
              format(picked_stream['encoding'], picked_stream['bitrate']))

        encoding = 'audio/mpeg'
        if picked_stream['encoding'] == 'aac':
            encoding = 'audio/aac'
        metadata = {
            'url': picked_url,
            'encoding' : encoding,
            'bitrate' : picked_stream['bitrate'],
            'thumb': 'https://ichef.bbci.co.uk/images/ic/480xn/' + programme_json["image"]["pid"] + '.jpg',
            'icon': 'https://ichef.bbci.co.uk/images/ic/480xn/' + programme_json["image"]["pid"] + '.jpg',
            'title': programme_json["display_title"]["title"],
            'artist': programme_json["display_title"]["subtitle"],
            'album': programme_json["ownership"]["service"]["title"],
            'comment': programme_json["short_synopsis"]
        }

        uplog("Metadata %s" % metadata)
        break

    if picked_url is None:
        uplog("Episode not available to stream")
        return {}

    return metadata


def add_directory(title, endpoint):
    if callable(endpoint):
        endpoint = plugin.url_for(endpoint)
    xbmcplugin.entries.append(direntry(bbcidprefix + endpoint, xbmcplugin.objid, title))

def urls_from_id(view_func, items):
    #msgproc.log("urls_from_id: items: %s" % str([item.id for item in items]))
    return [plugin.url_for(view_func, item.id) for item in items if str(item.id).find('http') != 0]

def view(data_items, urls, end=True):
    for item, url in zip(data_items, urls):
        title = item.name

        try:
            image = item.image if item.image else None
        except:
            image = None
        try:
            upnpclass = item.upnpclass if item.upnpclass else None
        except:
            upnpclass = None
        try:
            artnm = item.artist.name if item.artist.name else None
        except:
            artnm = None
        xbmcplugin.entries.append(
            direntry(bbcidprefix + url, xbmcplugin.objid, title, arturi=image, artist=artnm, upnpclass=upnpclass))

@plugin.route('/')
def root():
    add_directory('Stations', root_stations)
    add_directory('Podcasts', root_podcasts)

@plugin.route('/root_stations')
def root_stations():
    #uplog("_parse_playlist: data %s" % data)
    items = []
    for station in stations:
        kwargs = {
            'id': station['id'],
            'name': station['name'],
            #'image': station['image']
        }
        items.append(Playlist(**kwargs))
    view(items, urls_from_id(station_view, items))


@plugin.route('/station/<station_id>')
def station_view(station_id):
    base = datetime.datetime.today()

    # Create a range of the last 30 days
    for delta in range(30):
        date = base - datetime.timedelta(days=delta)

        year = '%04d' % date.year
        month = '%02d' % date.month
        day = '%02d' % date.day
        title = date.strftime('%Y-%m-%d (%A)')
        add_directory(title, plugin.url_for(station_date_view,
                                            station_id=station_id,
                                            year=year, month=month, day=day))


@plugin.route('/station/<station_id>/<year>/<month>/<day>')
def station_date_view(station_id, year, month, day):
    # Load the schedules for the station. Input date is like 2021/11/08
    url = 'https://www.bbc.co.uk/schedules/' + station_id + '/' + year + '/' + month + '/' + day
    uplog("Fetching %s" % url)
    schedule = get_page(url)

    result = None

    for tag in schedule.find_all('script', type='application/ld+json'):
        if 'RadioEpisode' in tag.contents[0]:
            result = json.loads(tag.contents[0])

    if result is None:
        uplog("Something went wrong parsing the station's schedule")
        return

    tracks = []
    trackno = 1
    for episode in result["@graph"]:
        date = dateutil.parser.parse(episode["publication"]["startDate"])

        time = date.strftime('%Y-%m-%d, %H:%M')

        if "partOfSeries" in episode:
            title = time + ": " + episode["partOfSeries"]["name"] + " - " + episode["name"]
        else:
            title = time + ": " + episode["name"]

        station = find_station(station_id)
        station_name = station['name'] if station else 'Unknown'
        trackid = episode["identifier"]
        trackdata = trackdetails(trackid)
        if not trackdata:
            continue
        track = {
            'pid' : xbmcplugin.objid,
            'id' :  xbmcplugin.objid + '$' + '%s' % trackid,
            'tt' : trackdata['title'],
            'uri' : trackdata['url'],
            'tp' : 'it',
            'upnp:albumArtURI' : trackdata['thumb'],
            'upnp:originalTrackNumber' :  str(trackno),
            'upnp:artist' : trackdata['artist'],
            'dc:title' : trackdata['title'],
            'duration' : '0',
            'upnp:class' : 'object.item.audioItem.musicTrack',
            'res:mime' : trackdata['encoding'],
            'res:samplefreq' : '48000',
            'res:bitrate' : trackdata['bitrate']
        }
        xbmcplugin.entries.append(track)
        trackno += 1


@plugin.route('/root_podcasts')
def root_podcasts():
    items = []
    view(items, urls_from_id(podcast_view, items))
@plugin.route('/podcast/<podcast_id>')
def podcast_view(podcast_id):
    return

@dispatcher.record('browse')
def browse(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(bbcidprefix)
    msgproc.log("browse: [%s]" % a)
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    bflg = a['flag'] if 'flag' in a else 'children'
    
    if re.match('0\$bbc\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    maybeinit()

    xbmcplugin.objid = objid
    idpath = objid.replace(bbcidprefix, '', 1)
    if bflg == 'meta':
        m = re.match('.*\$(.+)$', idpath)
        if m:
            trackid = m.group(1)
            track = Track()
            track_list([track])
    else:
        plugin.run([idpath])
    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}

@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    global xbmcplugin
    xbmcplugin = XbmcPlugin(bbcidprefix)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}

msgproc.log("BBC running")
msgproc.mainloop()