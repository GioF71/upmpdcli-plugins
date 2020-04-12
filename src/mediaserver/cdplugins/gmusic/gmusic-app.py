#!/usr/bin/python3
#
# A lot of code copied from the Kodi Tidal addon which is:
# Copyright (C) 2014 Thomas Amland
#
# Additional code and modifications:
# Copyright (C) 2016 J.F.Dockes
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
import sys
import os
import posixpath
import json
import re
import conftree
import cmdtalkplugin
from upmplgutils import *
import upmplgutils

# Using kodi plugin routing plugin: lets use reuse a lot of code from
# the addon. And much convenient in general
from routing import Plugin
# Need bogus base_url value to avoid plugin trying to call xbmc to
# retrieve addon id
plugin = Plugin('') 
from session import Session

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

is_logged_in = False

def maybelogin():
    global quality
    global httphp
    global pathprefix
    global is_logged_in
    global session
    
    if is_logged_in:
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

    cachedir = upmplgutils.getcachedir(upconfig, "gmusic")

    session = Session(cachedir)

    username = upconfig.get('gmusicuser')
    password = upconfig.get('gmusicpass')
    quality = upconfig.get('gmusicquality')
    if quality not in ('hi', 'med', 'low'):
        raise Exception("gmusic bad quality value: " + quality)
    deviceid = upconfig.get('gmusicdeviceid')
    if not deviceid:
        deviceid = None

    # Note that, if using oauth username can be bogus and password None
    is_logged_in = session.login(username, password, deviceid)
    
    if not is_logged_in:
        raise Exception("gmusic login failed")

    setMimeAndSamplerate('audio/mpeg', "44100")


def get_mimeandkbs():
    if quality == 'hi':
        return ('audio/mpeg', str(320))
    elif quality == 'med':
        return ('audio/mpeg', str(160))
    elif quality == 'low':
        return ('audio/mpeg', str(128))
    else:
        return ('audio/mpeg', str(128))


@dispatcher.record('trackuri')
def trackuri(a):
    global quality
    msgproc.log("trackuri: [%s]" % a)
    trackid = trackid_from_urlpath(pathprefix, a)
    maybelogin()
    media_url = session.get_media_url(trackid, quality)
    mime, kbs = get_mimeandkbs()
    return {'media_url' : media_url, 'mimetype' : mime, 'kbs' : kbs}


def add_directory(title, endpoint):
    if callable(endpoint):
        endpoint = plugin.url_for(endpoint)
    xbmcplugin.entries.append(direntry('0$gmusic$' + endpoint,
                                       xbmcplugin.objid, title))

def urls_from_id(view_func, items):
    return [plugin.url_for(view_func, item.id) for item in items
            if str(item.id).find('http') != 0]

def view(data_items, urls, end=True):
    for item, url in zip(data_items, urls):
        title = item.name
        try:
            image = item.image if item.image else None
        except:
            image = None
        try:
            artnm = item.artist.name if item.artist.name else None
        except:
            artnm = None
        try:
            upnpclass = item.upnpclass if item.upnpclass else None
        except:
            upnpclass = None
        xbmcplugin.entries.append(
            direntry('0$gmusic$' + url, xbmcplugin.objid, title, arturi=image,
                     artist=artnm, upnpclass=upnpclass))

def track_list(tracks):
    xbmcplugin.entries += trackentries(httphp, pathprefix,
                                       xbmcplugin.objid, tracks)


@dispatcher.record('browse')
def browse(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin('0$gmusic$')
    msgproc.log("browse: [%s]" % a)
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    bflg = a['flag'] if 'flag' in a else 'children'
    
    if re.match('0\$gmusic\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    maybelogin()

    xbmcplugin.objid = objid
    idpath = objid.replace('0$gmusic$', '', 1)
    if bflg == 'meta':
        m = re.match('.*\$(.+)$', idpath)
        if m:
            trackid = m.group(1)
            track = session.get_track(trackid)
            track_list([track])
    else:
        plugin.run([idpath])
    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}

@plugin.route('/')
def root():
    add_directory('Library', my_music)
    add_directory('Genres', root_genres)
    add_directory('Listen now', listen_now)
    add_directory('Thematic', root_situations)
    
@plugin.route('/root_genres')
def root_genres():
    items = session.get_genres()
    view(items, urls_from_id(genre_view, items))

@plugin.route('/root_situations')
def root_situations():
    items = session.get_situation_content()
    sits = items['situations']
    if sits:
        view(sits, urls_from_id(situation_view, sits))
    sts = items['stations']
    if sts:
        view(sts, urls_from_id(dynstation_view, sts))

@plugin.route('/situation/<situation_id>')
def situation_view(situation_id):
    items = session.get_situation_content(situation_id)
    sits = items['situations']
    if sits:
        view(sits, urls_from_id(situation_view, sits))
    sts = items['stations']
    if sts:
        view(sts, urls_from_id(dynstation_view, sts))
    
@plugin.route('/dynstation/<radio_id>')
def dynstation_view(radio_id):
    track_list(session.create_curated_and_get_tracks(radio_id))

@plugin.route('/listen_now')
def listen_now():
    data = session.listen_now()
    items = data['albums']
    if len(items):
        view(items, urls_from_id(album_view, items))
    items = data['stations']
    if len(items):
        view(items, urls_from_id(station_view, items))

@plugin.route('/station/<radio_id>')
def station_view(radio_id):
    track_list(session.get_station_tracks(radio_id))

@plugin.route('/genre/<genre_id>')
def genre_view(genre_id):
    items = session.get_genres(genre_id)
    if len(items) != 0:
        # List subgenres
        view(items, urls_from_id(genre_view, items))
    else:
        id = session.create_station_for_genre(genre_id)
        track_list(session.get_station_tracks(id))
        session.delete_user_station(id)
        
@plugin.route('/my_music')
def my_music():
    add_directory('Albums', user_albums)
    add_directory('Artists', user_artists)
    add_directory('Promoted Tracks', promoted_tracks)
    add_directory('Playlists', user_playlists)
    add_directory('Radios Stations', user_stations)

@plugin.route('/user_stations')
def user_stations():
    items = session.get_user_stations()
    view(items, urls_from_id(station_view, items))

@plugin.route('/promoted_tracks')
def promoted_tracks():
    track_list(session.get_promoted_tracks())

@plugin.route('/user_playlists')
def user_playlists():
    items = session.get_user_playlists()
    view(items, urls_from_id(playlist_view, items))

@plugin.route('/user_albums')
def user_albums():
    items = session.get_user_albums()
    view(items, urls_from_id(album_view, items))

@plugin.route('/user_artists')
def user_artists():
    try:
        items = session.get_user_artists()
    except Exception as err:
        msgproc.log("session.get_user_artists failed: %s" % err)
        return
    if items:
        #msgproc.log("First artist name %s"% items[0].name)
        view(items, urls_from_id(artist_view, items))

@plugin.route('/album/<album_id>')
def album_view(album_id):
    track_list(session.get_album_tracks(album_id))

@plugin.route('/playlist/<playlist_id>')
def playlist_view(playlist_id):
    track_list(session.get_user_playlist_tracks(playlist_id))

def ListItem(tt):
    return tt

@plugin.route('/artist/<artist_id>')
def artist_view(artist_id):
    xbmcplugin.addDirectoryItem(
        plugin.handle, plugin.url_for(related_artists, artist_id),
        ListItem('Related Artists'), True
    )
    data = session.get_artist_info(artist_id)
    albums = data["albums"]
    view(albums, urls_from_id(album_view, albums))
    track_list(data["toptracks"])
    
@plugin.route('/artist/<artist_id>/related')
def related_artists(artist_id):
    artists = session.get_artist_related(artist_id)
    view(artists, urls_from_id(artist_view, artists))

@dispatcher.record('search')
def search(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin('0$gmusic$')
    msgproc.log("search: [%s]" % a)
    objid = a['objid']
    field = a['field'] if 'field' in a else None
    value = a['value']
    objkind = a['objkind'] if 'objkind' in a else None

    if re.match('0\$gmusic\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    xbmcplugin.objid = objid
    maybelogin()
    
    searchresults = session.search(value)

    if objkind and objkind not in ['artist', 'album', 'playlist', 'track']:
        msgproc.log('Unknown objkind \'%s\'' % objkind)
        objkind = None
    if (not objkind or objkind == 'artist') and searchresults.artists:
        view(searchresults.artists,
             urls_from_id(artist_view, searchresults.artists), end=False)
    if (not objkind or objkind == 'album') and searchresults.albums:
        view(searchresults.albums,
             urls_from_id(album_view, searchresults.albums), end=False)
    if (not objkind or objkind == 'playlist') and searchresults.playlists:
        view(searchresults.playlists,
             urls_from_id(playlist_view, searchresults.playlists), end=False)
    if (not objkind or objkind == 'track') and searchresults.tracks:
        track_list(searchresults.tracks)

    #msgproc.log("search results: %s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}

msgproc.log("Gmusic running")
msgproc.mainloop()
