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
import json
import re
import pwd
import errno

import conftree
import cmdtalkplugin
from upmplgutils import *

from session import Session
session = Session()

# Using kodi plugin routing plugin: lets use reuse a lot of code from
# the addon. And much convenient in general
from routing import Plugin
# Need bogus base_url value to avoid plugin trying to call xbmc to
# retrieve addon id
plugin = Plugin('') 


spotidprefix = '0$spotify$'
servicename = 'spotify'

# Func name to method mapper for talking with our parent
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

is_logged_in = False

def maybelogin(a={}):

    # Do this always
    setidprefix(spotidprefix)

    global is_logged_in
    if is_logged_in:
        return True

    if "UPMPD_HTTPHOSTPORT" not in os.environ:
        raise Exception("No UPMPD_HTTPHOSTPORT in environment")
    global httphp
    httphp = os.environ["UPMPD_HTTPHOSTPORT"]
    if "UPMPD_PATHPREFIX" not in os.environ:
        raise Exception("No UPMPD_PATHPREFIX in environment")
    global pathprefix
    pathprefix = os.environ["UPMPD_PATHPREFIX"]

    if "UPMPD_CONFIG" not in os.environ:
        raise Exception("No UPMPD_CONFIG in environment")
    upconfig = conftree.ConfSimple(os.environ["UPMPD_CONFIG"])

    global cachedir
    cachedir = upconfig.get('cachedir')
    if not cachedir:
        me = pwd.getpwuid(os.getuid()).pw_name
        uplog("me: %s"%me)
        if me == 'upmpdcli':
            cachedir = '/var/cache/upmpdcli/'
        else:
            cachedir = os.path.expanduser('~/.cache/upmpdcli/')
    cachedir = os.path.join(cachedir, servicename)
    try:
        os.makedirs(cachedir)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(cachedir):
            pass
        else:
            raise
    uplog("cachedir: %s"%cachedir)

    if 'user' in a:
        username = a['user']
    else:
        username = upconfig.get(servicename + 'user')
    if not username:
        raise Exception("spotifyuser not set in configuration")

    is_logged_in = session.login(username, os.path.join(cachedir, "token"))
    setMimeAndSamplerate("audio/mpeg", "44100")
    
    if not is_logged_in:
        raise Exception("spotify login failed")


@dispatcher.record('trackuri')
def trackuri(a):
    global formatid, pathprefix

    maybelogin()

    msgproc.log("trackuri: [%s]" % a)
    # we use the trackid as "url". The spotify proxy module will manage
    media_url = trackid_from_urlpath(pathprefix, a)
    mime = "application/flac"
    kbs = "1410"
    return {'media_url' : media_url, 'mimetype' : mime, 'kbs' : kbs}


def add_directory(title, endpoint):
    if callable(endpoint):
        endpoint = plugin.url_for(endpoint)
    xbmcplugin.entries.append(direntry(spotidprefix + endpoint,
                                       xbmcplugin.objid, title))

def urls_from_id(view_func, items):
    #msgproc.log("urls_from_id: items: %s" % str([item.id for item in items]))
    return [plugin.url_for(view_func, item.id)
            for item in items if str(item.id).find('http') != 0]

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
            direntry(spotidprefix + url, xbmcplugin.objid, title, arturi=image,
                     artist=artnm, upnpclass=upnpclass))

def track_list(tracks):
    xbmcplugin.entries += trackentries(httphp, pathprefix,
                                       xbmcplugin.objid, tracks)

@dispatcher.record('browse')
def browse(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(spotidprefix)
    msgproc.log("browse: [%s]" % a)
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    bflg = a['flag'] if 'flag' in a else 'children'
    
    if re.match('0\$spotify\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    maybelogin()

    xbmcplugin.objid = objid
    idpath = objid.replace(spotidprefix, '', 1)
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
    add_directory('Your Library', my_music)
    add_directory('New Releases', new_releases)
    add_directory('Featured Playlists', featured_playlists)
    add_directory('Genres and Moods', genres_and_moods)
    
@plugin.route('/my_music')
def my_music():
    add_directory('Recently Played', recently_played)
    add_directory('Songs', favourite_tracks)
    add_directory('Albums', favourite_albums)
    add_directory('Artists', favourite_artists)
    add_directory('Playlists', my_playlists)
    
@plugin.route('/album/<album_id>')
def album_view(album_id):
    track_list(session.get_album_tracks(album_id))

@plugin.route('/playlist/<playlist_id>/<user_id>')
def playlist_view(playlist_id, user_id):
    track_list(session.user_playlist_tracks(user_id, playlist_id))

@plugin.route('/category/<category_id>')
def category_view(category_id):
    playlists = session.get_category_playlists(category_id)
    view(playlists,
         [plugin.url_for(playlist_view, playlist_id=p.id, user_id=p.userid)
          for p in playlists], end=False)

@plugin.route('/artist/<artist_id>')
def artist_view(artist_id):
    # Might want to add a 'related artists' list?
    albums = session.get_artist_albums(artist_id)
    view(albums, urls_from_id(album_view, albums))

@plugin.route('/new_releases')
def new_releases():
    items = session.new_releases()
    view(items, urls_from_id(album_view, items))

@plugin.route('/recently_played')
def recently_played():
    track_list(session.recent_tracks())

@plugin.route('/favourite_tracks')
def favourite_tracks():
    track_list(session.favourite_tracks())

@plugin.route('/favourite_albums')
def favourite_albums():
    items = session.favourite_albums()
    view(items, urls_from_id(album_view, items))

@plugin.route('/featured_playlists')
def featured_playlists():
    items = session.featured_playlists()
    view(items,
         [plugin.url_for(playlist_view,
                         playlist_id=p.id,
                         user_id=p.userid) for p in items], end=False)
@plugin.route('/genres_and_moods')
def genres_and_moods():
    items = session.get_categories()
    view(items, urls_from_id(category_view, items))
    
@plugin.route('/my_playlists')
def my_playlists():
    items = session.my_playlists()
    view(items,
         [plugin.url_for(playlist_view,
                         playlist_id=p.id,
                         user_id=p.userid) for p in items], end=False)

@plugin.route('/favourite_artists')
def favourite_artists():
    items = session.favourite_artists()
    view(items, urls_from_id(artist_view, items))

@dispatcher.record('search')
def search(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(spotidprefix)
    msgproc.log("search: [%s]" % a)
    objid = a['objid']
    field = a['field'] if 'field' in a else None
    value = a['value']
    objkind = a['objkind'] if 'objkind' in a and a['objkind'] else None
    
    if re.match('0\$spotify\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    xbmcplugin.objid = objid
    maybelogin()
    
    if field and field not in ['artist', 'album', 'playlist', 'track']:
        msgproc.log('Unknown field \'%s\'' % field)
        field = 'track'

    if objkind and objkind not in ['artist', 'album', 'playlist', 'track']:
        msgproc.log('Unknown objkind \'%s\'' % objkind)
        objkind = 'track'

    searchresults = session.search(value, objkind)

    if objkind is None or objkind == 'artist':
        view(searchresults.artists,
             urls_from_id(artist_view, searchresults.artists), end=False)
    if objkind is None or objkind == 'album':
        view(searchresults.albums,
             urls_from_id(album_view, searchresults.albums), end=False)
        # Kazoo and bubble only search for object.container.album, not
        # playlists. So if we want these to be findable, need to send
        # them with the albums
        if objkind == 'album':
            searchresults = session.search(value, 'playlist')
            objkind = 'playlist'
            # Fallthrough to view playlists
    if objkind is None or objkind == 'playlist':
        view(searchresults.playlists,
             [plugin.url_for(playlist_view,
                             playlist_id=p.id,
                             user_id=p.userid) for p in
              searchresults.playlists], end=False)
    if objkind is None or objkind == 'track':
        track_list(searchresults.tracks)

    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}

msgproc.log("Spotify running")
msgproc.mainloop()
