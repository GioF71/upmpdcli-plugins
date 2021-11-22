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
import threading
from time import mktime
import urllib

try:
    import feedparser
    hasfeedparser = True
except:
    hasfeedparser = False
from bs4 import BeautifulSoup

import conftree
import cmdtalkplugin
from upmplgutils import *
from upmplgmodels import *
from xbmcplug import *

# Reusing the Tidal plugin routing module
from routing import Plugin
plugin = Plugin('') 

bbcidprefix = '0$bbc$'

# Cmdtalk communication with our parent process
# Cmdtalk func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Cmdtalk pipe message handler
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

_g_initok = False
_g_fetchdays = 30

def maybeinit(a={}):
    global _g_initok

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

    global _g_fetchdays
    val = upconfig.get("bbcprogrammedays")
    if val:
        _g_fetchdays = int(val)

    setMimeAndSamplerate("audio/mpeg", "44100")

    _g_initok = True


# Download the source HTML for the page using requests and parse the page using BeautifulSoup
def get_page(url):
    return BeautifulSoup(requests.get(url).text, 'html.parser')


# The media URLs we obtain point to 2 levels of m3u playlists, the second of which is an Apple HTTP
# Live Streaming playlist.
# https://developer.apple.com/library/archive/documentation/NetworkingInternet/Conceptual/StreamingMediaGuide/DeployingHTTPLiveStreaming/DeployingHTTPLiveStreaming.html
# It happens that mpd deals with these fine, not sure that other renderers will. Mitigating this
# would be complicated. The only simple thing we could do is resolve the first level and hope that
# renderers can deal with the Apple part? Else we'd have to proxy the stream.
#
# Also, retrieving the programme details is slow and the listing can timeout when there are many
# entries (in station_date_view()). We'd need to send multiple requests in parallel, either with
# grequests (would need change of programmedetails/station_date_view() interaction), or with
# multiple explicit programmedetails() threads.
def _programmedetails(progid, resdata):
    maybeinit()
    resdata[progid] = None

    try:
        url = 'https://www.bbc.co.uk/programmes/' + progid + '.json'
        programme = requests.get(url, timeout=5)
    except:
        uplog("Timed out for %s" % url)
    programme_json = programme.json()["programme"]

    picked_url = None
    metadata = {}
    for version in programme_json["versions"]:
        url = \
           'https://open.live.bbc.co.uk/mediaselector/6/select/version/2.0/mediaset/iptv-all/vpid/'\
           + version["pid"] + '/format/json'
        uplog("DETAILS: getting: %s" % url, level=4)
        playlist = requests.get(url)
        playlist_json = playlist.json()

        if "media" not in playlist_json:
            # TODO
            continue

        # Filter by only audio items, and order with the highest bitrate first
        audio_items = [item for item in playlist_json['media'] if item['kind'] == 'audio']
        audio_items.sort(key=lambda x: x['bitrate'], reverse=True)

        uplog('Found {0} audio items for the programme version {1}'.
              format(len(audio_items), version['pid']), level=4)

        # Pick the first stream available for the highest bitrate item
        picked_stream = audio_items[0]
        picked_url = picked_stream["connection"][1]["href"]

        uplog('Picked {0} stream with bitrate {1}'.
              format(picked_stream['encoding'], picked_stream['bitrate']), level=4)

        encoding = 'audio/mpeg'
        if picked_stream['encoding'] == 'aac':
            encoding = 'audio/aac'
        #broadcast_date = dateutil.parser.parse(programme_json['first_broadcast_date'])
        #dte = broadcast_date.strftime('%Y-%m-%d, %H:%M') + " "
        dte = ""
        metadata = {
            'url': picked_url,
            'encoding' : encoding,
            'bitrate' : picked_stream['bitrate'],
            'thumb': 'https://ichef.bbci.co.uk/images/ic/480xn/' + \
            programme_json["image"]["pid"] + '.jpg',
            'icon': 'https://ichef.bbci.co.uk/images/ic/480xn/' + \
            programme_json["image"]["pid"] + '.jpg',
            'title': programme_json["display_title"]["title"],
            'artist': dte + programme_json["display_title"]["subtitle"],
            # Album is the station name.
            'album': programme_json["ownership"]["service"]["title"],
            'comment': programme_json["short_synopsis"]
        }
        #uplog("Metadata %s" % metadata, level=5)
        break

    if picked_url is None:
        uplog("Episode not available to stream")
    else:
        resdata[progid] = metadata


# Parallel fetching of programme data. Threads return their result by setting a dictionary entry
_nthreads = 20
def _fetchdetails(resdata, reqcount):
    thrcount = 0
    ths=[]
    datacount = 0
    nthreads = _nthreads
    for progid in resdata.keys():
        th=threading.Thread(target=_programmedetails, args=(progid, resdata))
        th.start() 
        ths.append(th)
        thrcount += 1
        if thrcount == nthreads:
            thrcount = 0
            for th in ths:
                th.join()
        datacount = len([k for k in resdata.keys() if resdata[k] is not None])
        if nthreads > reqcount - datacount:
            nthreads = reqcount - datacount
        if datacount >= reqcount:
            break
    for th in ths:
        th.join()
    
@plugin.route('/')
def root():
    xbmcplugin.add_directory('Stations', root_stations)
    if hasfeedparser:
        xbmcplugin.add_directory('Podcasts', root_podcasts)

@plugin.route('/root_stations')
def root_stations():
    items = []
    for station in stations:
        kwargs = {
            'id': station['id'],
            'name': station['name'],
            #'image': station['image']
        }
        items.append(Playlist(**kwargs))
    xbmcplugin.view(items, xbmcplugin.urls_from_id(station_view, items))


@plugin.route('/station/<station_id>')
def station_view(station_id):
    base = datetime.datetime.today()

    # Create a range of the last 30 days
    for delta in range(_g_fetchdays):
        date = base - datetime.timedelta(days=delta)

        year = '%04d' % date.year
        month = '%02d' % date.month
        day = '%02d' % date.day
        title = date.strftime('%Y-%m-%d (%A)')
        xbmcplugin.add_directory(
            title, plugin.url_for(station_date_view, station_id=station_id,
                                  year=year, month=month, day=day))


@plugin.route('/station/<station_id>/<year>/<month>/<day>')
def station_date_view(station_id, year, month, day):
    # Load the schedules for the station. Input date is like 2021/11/08
    url = 'https://www.bbc.co.uk/schedules/' + station_id + '/' + year + '/' + month + '/' + day
    uplog("station_date_view: fetching %s" % url, level=5)
    schedule = get_page(url)

    result = None

    for tag in schedule.find_all('script', type='application/ld+json'):
        if 'RadioEpisode' in tag.contents[0]:
            result = json.loads(tag.contents[0])

    if result is None:
        uplog("Something went wrong parsing the station's schedule")
        return

    reqcount = xbmcplugin.count
    reqoffs = xbmcplugin.offset
    xbmcplugin.total = len(result["@graph"])

    resdata = {}
    offset = 0
    for episode in result["@graph"]:
        if offset < reqoffs:
            offset += 1
            continue
        progid = episode["identifier"]
        resdata[progid] = None
    _fetchdetails(resdata, reqcount)
    
    offset = 0
    tracks = []
    trackno = 1 + reqoffs
    for episode in result["@graph"]:
        if offset < reqoffs:
            offset += 1
            continue
        progid = episode["identifier"]
        if not progid in resdata or resdata[progid] is None:
            continue
        trackdata = resdata[progid]

        # We ignore the details title as the one in the episode data is fine.
        date = dateutil.parser.parse(episode["publication"]["startDate"])
        time = date.strftime('%Y-%m-%d, %H:%M')
        if "partOfSeries" in episode:
            title = time + ": " + episode["partOfSeries"]["name"] + " - " + episode["name"]
        else:
            title = time + ": " + episode["name"]

        track = {
            'pid' : xbmcplugin.objid,
            'id' :  xbmcplugin.objid + '$' + '%s' % progid,
            'tt' : title,
            'dc:title' : title,
            'uri' : trackdata['url'],
            'tp' : 'it',
            'upnp:albumArtURI' : trackdata['thumb'],
            'upnp:originalTrackNumber' :  str(trackno),
            # artist has the subtitle, which is already in the title obtained from the episode
#            'upnp:artist' : trackdata['artist'],
            'duration' : '0',
            'upnp:class' : 'object.item.audioItem.musicTrack',
            'res:mime' : trackdata['encoding'],
            'res:samplefreq' : '48000',
            'res:bitrate' : trackdata['bitrate']
        }
        xbmcplugin.entries.append(track)
        trackno += 1
        if len(xbmcplugin.entries) >= reqcount:
            break

@plugin.route('/root_podcasts')
def root_podcasts():
    podcasts = requests.get('https://www.bbc.co.uk/podcasts.json')
    podcasts_json = podcasts.json()["podcasts"]

    # Sort the podcasts by title
    podcasts_ordered = sorted(podcasts_json, key=lambda x: x["title"])

    for podcast in podcasts_ordered:
        arturi=None
        if "imageUrl" in podcast:
            arturi = podcast["imageUrl"].replace('{recipe}', '624x624')
            xbmcplugin.add_directory(podcast["title"],
                      plugin.url_for(podcast_view, podcast_id=podcast["shortTitle"]), arturi=arturi)


@plugin.route('/podcast/<podcast_id>')
def podcast_view(podcast_id):
    podcast = feedparser.parse('https://podcasts.files.bbci.co.uk/' + podcast_id + '.rss')

    image_url = ''
    if "image" in podcast.feed:
        image_url = podcast.feed.image.url

    reqcount = xbmcplugin.count
    reqoffs = xbmcplugin.offset
    xbmcplugin.total = len(podcast.entries)
    resdata = {}
    offset = 0
    for entry in podcast.entries:
        if offset < reqoffs:
            offset += 1
            continue
        entry_pid = entry.ppg_canonical.split('/')
        if len(entry_pid) <= 2:
            uplog('No pid could be found for the item at ' + entry.link)
            continue
        progid = entry_pid[2]
        resdata[progid] = None
    _fetchdetails(resdata, reqcount)

    trackno = 1 + reqoffs
    offset = 0
    for entry in podcast.entries:
        if offset < reqoffs:
            offset += 1
            continue
        entry_pid = entry.ppg_canonical.split('/')
        if len(entry_pid) <= 2:
            uplog("bad entry_pid for offset %d : %s" % (offset, entry_pid))
            continue
        progid = entry_pid[2]
        if not progid in resdata or resdata[progid] is None:
            uplog("No data for progid %s" % progid)
            continue
        trackdata = resdata[progid]
        entry_date = datetime.datetime.fromtimestamp(
            mktime(entry.published_parsed)).strftime('%Y-%m-%d')
        entry_title = entry_date + ": " + entry.title
        track = {
            'pid' : xbmcplugin.objid,
            'id' :  xbmcplugin.objid + '$' + '%s' % progid,
            'tt' : entry_title,
            'uri' : trackdata['url'],
            'tp' : 'it',
            'upnp:albumArtURI' : image_url,
            'upnp:originalTrackNumber' :  str(trackno),
            'dc:title' : entry_title,
            'duration' : '0',
            'upnp:class' : 'object.item.audioItem.musicTrack',
            'res:mime' : trackdata['encoding'],
            'res:samplefreq' : '48000',
            'res:bitrate' : trackdata['bitrate']
        }
        xbmcplugin.entries.append(track)
        trackno += 1
        if len(xbmcplugin.entries) >= reqcount:
            break

@dispatcher.record('browse')
def browse(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(bbcidprefix, routeplugin=plugin)
    msgproc.log("browse: [%s]" % a)
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    if re.match('0\$bbc\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    maybeinit()

    if 'offset' in a:
        xbmcplugin.offset = int(a['offset'])
    if 'count' in a:
        xbmcplugin.count = int(a['count'])

    xbmcplugin.objid = objid
    idpath = objid.replace(bbcidprefix, '', 1)
    plugin.run([idpath])
    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    ret = {"entries" : encoded}
    if xbmcplugin.total:
        ret["total"] = str(xbmcplugin.total)
        ret["offset"] = str(xbmcplugin.offset)
    return ret

@dispatcher.record('search')
def search(a):
    msgproc.log("search: [%s]" % a)
    global xbmcplugin
    xbmcplugin = XbmcPlugin(bbcidprefix, routeplugin=plugin)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}

msgproc.log("BBC running")
msgproc.mainloop()
