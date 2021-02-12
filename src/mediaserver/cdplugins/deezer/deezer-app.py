#!/usr/bin/python3
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

import conftree
import cmdtalkplugin
from upmplgutils import *

# Using kodi plugin routing plugin: lets use reuse a lot of code from
# the addon.
from routing import Plugin
# Need bogus base_url value to avoid plugin trying to call xbmc to
# retrieve addon id
plugin = Plugin('')

import deezersession

_rootid = '0$deezer$'
_rootidre = '0\$deezer\$'

def msg(s):
    print("%s" % s, file=sys.stderr)
    
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
    upconfig = conftree.ConfSimple(os.environ["UPMPD_CONFIG"])
    
    username = upconfig.get('deezeruser')
    password = upconfig.get('deezerpass')
    if not username or not password:
        raise Exception("deezeruser and/or deezerpass " +
                            "not set in configuration")
    setMimeAndSamplerate("audio/mpeg", "44100")
    cachedir = getcachedir(upconfig, "deezer")
    return sess.login(cachedir, username, password)
    

def add_directory(title, endpoint):
    if callable(endpoint):
        endpoint = plugin.url_for(endpoint)
    xbmcplugin.addDirectoryItem(None, endpoint, title)


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
            artnm = item.artist if item.artist else None
        except:
            artnm = None
        xbmcplugin.entries.append(
            direntry(_rootid + url, xbmcplugin.objid, title, arturi=image,
                     artist=artnm, upnpclass=upnpclass))


def track_list(tracks):
    xbmcplugin.entries += trackentries(httphp, pathprefix,
                                       xbmcplugin.objid, tracks)


@plugin.route('/')
def root():
    if not maybelogin():
        return []
    add_directory('Favourites', my_music)

@plugin.route('/my_music')
def my_music():
    add_directory('Albums', favourite_albums)
    add_directory('Playlists', favourite_playlists)
    xbmcplugin.endOfDirectory(plugin.handle)

@plugin.route('/favourite_playlists')
def favourite_playlists():
    items = sess.get_favourite_playlists()
    view(items, urls_from_id(userplaylist_view, items))

@plugin.route('/favourite_albums')
def favourite_albums():
    items = sess.get_favourite_albums()
    view(items, urls_from_id(album_view, items))

@plugin.route('/userplaylist/<id>')
def userplaylist_view(id):
    track_list(sess.get_user_playlist(id))

@plugin.route('/artist/<artist_id>')
def artist_view(artist_id):
    albums = sess.get_artist_albums(artist_id) 
    view(albums, urls_from_id(album_view, albums))

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
    xbmcplugin = XbmcPlugin(_rootid)
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
    return {"entries" : encoded}

@dispatcher.record('search')
def search(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(_rootid)

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
        view(searchresults.artists,
             urls_from_id(artist_view, searchresults.artists), end=False)
    if (not objkind or objkind == 'album') and searchresults.albums:
        view(searchresults.albums,
             urls_from_id(album_view, searchresults.albums), end=False)
    if (not objkind or objkind == 'track') and searchresults.tracks:
        track_list(searchresults.tracks)

    #msgproc.log("search results: %s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}


msgproc.log("Deezer running")
msgproc.mainloop()
