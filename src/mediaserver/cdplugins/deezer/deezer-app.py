#!/usr/bin/env python3
#
# A lot of code copied from the Kodi Tidal addon which is:
# Copyright (C) 2014 Thomas Amland
#
# Additional code and modifications:
# Copyright (C) 2020 J.F.Dockes
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

import sys
import os
import json
import re
import base64

import cmdtalkplugin
from upmplgutils import *
from xbmcplug import *

# Using Tidal Kodi addon routing plugin
from routing import Plugin
plugin = Plugin('')

import deezersession

_rootid = '0$deezer$'
_rootidre = '0\$deezer\$'

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

sess = deezersession.Session()

def maybelogin():
    if sess.isloggedin():
        return True

    global httphp
    if "UPMPD_HTTPHOSTPORT" not in os.environ:
        raise Exception("No UPMPD_HTTPHOSTPORT in environment")
    httphp = os.environ["UPMPD_HTTPHOSTPORT"]
    global pathprefix
    if "UPMPD_PATHPREFIX" not in os.environ:
        raise Exception("No UPMPD_PATHPREFIX in environment")
    pathprefix = os.environ["UPMPD_PATHPREFIX"]
    if "UPMPD_CONFIG" not in os.environ:
        raise Exception("No UPMPD_CONFIG in environment")
    
    username = getOptionValue('deezeruser')
    password = getOptionValue('deezerpass')
    if not username or not password:
        raise Exception("deezeruser and/or deezerpass not set in configuration")
    setMimeAndSamplerate("audio/mpeg", "44100")
    cachedir = getcachedir("deezer")
    return sess.login(cachedir, username, password)
    

def track_list(tracks):
    xbmcplugin.entries += trackentries(httphp, pathprefix, xbmcplugin.objid, tracks)


@plugin.route('/')
def root():
    if not maybelogin():
        return []
    xbmcplugin.add_directory('My Favourites Albums', my_favourite_albums)
    xbmcplugin.add_directory('My Favourites Playlists', my_favourite_playlists)
    xbmcplugin.add_directory('My Favourites Tracks', my_favourite_tracks)
    xbmcplugin.add_directory('My Favourites Artists', my_favourite_artists)
    xbmcplugin.add_directory('Family', my_family)

@plugin.route('/my_family')
def my_family():
    items = sess.get_followings()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(user_view, items))

@plugin.route('/my_favourite_albums')
def my_favourite_albums():
    items = sess.get_favourite_albums()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(album_view, items))

@plugin.route('/my_favourite_playlists')
def my_favourite_playlists():
    items = sess.get_favourite_playlists()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(playlist_view, items))

@plugin.route('/my_favourite_artists')
def my_favourite_artists():
    items = sess.get_favourite_artists()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(artist_view, items))

@plugin.route('/my_favourite_tracks')
def my_favourite_tracks():
    track_list(sess.get_favourite_tracks())
    

@plugin.route('/favourite_albums/<id>')
def favourite_albums(id):
    items = sess.get_favourite_albums(id)
    xbmcplugin.view(items, xbmcplugin.urls_from_id(album_view, items))

@plugin.route('/favourite_playlists/<id>')
def favourite_playlists(id):
    items = sess.get_favourite_playlists(id)
    xbmcplugin.view(items, xbmcplugin.urls_from_id(playlist_view, items))

@plugin.route('/favourite_artists/<id>')
def favourite_artists(id):
    items = sess.get_favourite_artists(id)
    xbmcplugin.view(items, xbmcplugin.urls_from_id(artist_view, items))

@plugin.route('/favourite_tracks/<id>')
def favourite_tracks(id):
    track_list(sess.get_favourite_tracks(id))

@plugin.route('/userplaylist/<id>')
def playlist_view(id):
    track_list(sess.get_user_playlist(id))

@plugin.route('/user/<id>')
def user_view(id):
    xbmcplugin.add_directory('Albums', plugin.url_for(favourite_albums, id))
    xbmcplugin.add_directory('Playlists', plugin.url_for(favourite_playlists, id))
    xbmcplugin.add_directory('Tracks', plugin.url_for(favourite_tracks, id))
    xbmcplugin.add_directory('Artists', plugin.url_for(favourite_artists, id))
    
@plugin.route('/artist/<artist_id>')
def artist_view(artist_id):
    albums = sess.get_artist_albums(artist_id) 
    xbmcplugin.view(albums, xbmcplugin.urls_from_id(album_view, albums))

@plugin.route('/album/<album_id>')
def album_view(album_id):
    track_list(sess.get_album_tracks(album_id))

@dispatcher.record('trackuri')
def trackuri(a):
    global pathprefix
    msgproc.log("trackuri: [%s]" % a)
    maybelogin()
    trackid = trackid_from_urlpath(pathprefix, a)
    url = sess.get_media_url(trackid) or ""
    #msgproc.log("%s" % media_url)
    return {'media_url' : url}

@dispatcher.record('browse')
def browse(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(_rootid, routeplugin=plugin)
    msgproc.log("browse: [%s]" % a)
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    bflg = a['flag'] if 'flag' in a else 'children'
    
    if re.match(_rootidre, objid) is None:
        raise Exception("bad objid [%s]" % objid)
    maybelogin()

    xbmcplugin.objid = objid
    idpath = objid.replace(_rootid, '', 1)
    plugin.run([idpath])
    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded, "total" : str(len(xbmcplugin.entries))}

@dispatcher.record('search')
def search(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(_rootid, routeplugin=plugin)

    msgproc.log("search: %s" % a)

    objid = a['objid']
    field = a['field'] if 'field' in a else None
    value = a['value']
    objkind = a['objkind'] if 'objkind' in a and a['objkind'] else None

    if re.match(_rootidre, objid) is None:
        raise Exception("bad objid [%s]" % objid)
    xbmcplugin.objid = objid
    maybelogin()

    if objkind and objkind not in ['album', 'artist', 'track']:
        objkind = 'album'

    # Deezer search takes a string and a 'filter' value which defines
    # the kind of results: 'album', 'artist', 'track'. We would like
    # to be able to search a specific field, but nope
    searchresults = sess.search(value, objkind)

    if (not objkind or objkind == 'artist') and searchresults.artists:
        xbmcplugin.view(searchresults.artists,
             xbmcplugin.urls_from_id(artist_view, searchresults.artists))
    if (not objkind or objkind == 'album') and searchresults.albums:
        xbmcplugin.view(searchresults.albums,
                        xbmcplugin.urls_from_id(album_view, searchresults.albums))
    if (not objkind or objkind == 'track') and searchresults.tracks:
        track_list(searchresults.tracks)

    #msgproc.log("search results: %s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded, "total" : str(len(xbmcplugin.entries))}


msgproc.log("Deezer running")
msgproc.mainloop()
