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


##### AFAIRE
# Track arturi
# Track format
# User playlists
# search
# ,,,

import sys
import os
import json
import re
import base64

import conftree
import cmdtalkplugin
from upmplgutils import *
from upmplgmodels import Artist, Album, Track, Playlist, SearchResult, \
     Category, Genre, Model

# Using kodi plugin routing plugin: lets use reuse a lot of code from
# the addon.
from routing import Plugin
# Need bogus base_url value to avoid plugin trying to call xbmc to
# retrieve addon id
plugin = Plugin('')

from session import Session
import session

def msg(s):
    print("%s" % s, file=sys.stderr)
    
# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

sess = Session()

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
    
    username = upconfig.get('hrauser')
    password = upconfig.get('hrapass')
    if not username or not password:
        raise Exception("hrauser and/or hrapass " +
                            "not set in configuration")
    setMimeAndSamplerate("application/flac", "44100")
    return sess.login(username, password)
    
@dispatcher.record('trackuri')
def trackuri(a):
    global pathprefix
    msgproc.log("trackuri: [%s]" % a)
    trackid = trackid_from_urlpath(pathprefix, a)
    maybelogin()
    media_url = sess.get_media_url(trackid)
    if not media_url:
        media_url = ""
    #msgproc.log("%s" % media_url)
    formatid = 7
    if formatid == 5:
        mime = "audio/mpeg"
        kbs = "320"
    else:
        mime = "application/flac"
        kbs = "1410"
    uplog({'media_url' : media_url, 'mimetype' : mime, 'kbs' : kbs})
    return {'media_url' : media_url, 'mimetype' : mime, 'kbs' : kbs}


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
            direntry('0$hra$' + url, xbmcplugin.objid, title, arturi=image,
                     artist=artnm, upnpclass=upnpclass))

def track_list(tracks):
    xbmcplugin.entries += trackentries(httphp, pathprefix,
                                       xbmcplugin.objid, tracks)

@dispatcher.record('browse')
def browse(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin('0$hra$')
    msgproc.log("browse: [%s]" % a)
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    bflg = a['flag'] if 'flag' in a else 'children'
    
    if re.match('0\$hra\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    maybelogin()

    xbmcplugin.objid = objid
    idpath = objid.replace('0$hra$', '', 1)
    if bflg == 'meta':
        m = re.match('.*\$(.+)$', idpath)
        if m:
            trackid = m.group(1)
            track = sess.get_track(trackid)
            track_list([track])
    else:
        plugin.run([idpath])
    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}

@plugin.route('/')
def root():
    if not maybelogin():
        add_directory('LOGIN FAILED', '/')
        return
    add_directory('Categories', allCategories)
    add_directory('Genres', allGenres)
    add_directory('My Playlists', allUserPlaylists)


@plugin.route('/allcategories')
def allCategories():
    items = sess.get_categories()
    view(items, urls_from_id(category_view, items))


@plugin.route('/allgenres')
def allGenres():
    items = sess.get_genres()
    view(items, urls_from_id(category_view, items))

@plugin.route('/alluserplaylists')
def allUserPlaylists():
    items = sess.get_alluserplaylists()
    view(items, urls_from_id(category_view, items))


@plugin.route('/category/<catg_id>')
def category_view(catg_id):
    decoded = session.decode_prefix(catg_id)
    msg("category_view: id [%s] decoded [%s]" % (catg_id, decoded))
    items = sess.get_catg_albums(decoded)
    view(items, urls_from_id(album_view, items))

def track_list(tracks):
    xbmcplugin.entries += trackentries(httphp, pathprefix,
                                       xbmcplugin.objid, tracks)

@plugin.route('/album/<album_id>')
def album_view(album_id):
    track_list(sess.get_album_tracks(album_id))


@dispatcher.record('search')
def search(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin('0$hra$')

    msgproc.log("search: [%s]" % a)

    objid = a['objid']
    field = a['field'] if 'field' in a else None
    value = a['value']
    objkind = a['objkind'] if 'objkind' in a and a['objkind'] else None

    if re.match('0\$hra\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    xbmcplugin.objid = objid
    maybelogin()
    
    if field and field not in ['artist', 'album', 'playlist', 'track']:
        msgproc.log('Unknown field \'%s\'' % field)
        field = 'track'

    if objkind and objkind not in ['artist', 'album', 'playlist', 'track']:
        msgproc.log('Unknown objkind \'%s\'' % objkind)
        objkind = 'track'

    # type may be 'tracks', 'albums', 'artists' or 'playlists'
    qkind = objkind + "s" if objkind else None
    searchresults = session.search(value, qkind)

    if objkind is None or objkind == 'artist':
        view(searchresults.artists,
             urls_from_id(artist_view, searchresults.artists), end=False)
    if objkind is None or objkind == 'album':
        view(searchresults.albums,
             urls_from_id(album_view, searchresults.albums), end=False)
    if objkind is None or objkind == 'playlist':
        view(searchresults.playlists,
             urls_from_id(playlist_view, searchresults.playlists), end=False)
    if objkind is None or objkind == 'track':
        track_list(searchresults.tracks)

    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries": encoded}

msgproc.log("HighresAudio running")
msgproc.mainloop()
