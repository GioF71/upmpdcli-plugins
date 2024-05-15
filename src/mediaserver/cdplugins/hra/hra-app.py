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

# Using tidal Kodi addon routing module
from routing import Plugin
plugin = Plugin('')

import session

_rootid = '0$hra$'
_rootidre = r'0\$hra\$'

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

sess = session.Session()

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
    
    username,password = getserviceuserpass('hra')
    if not username or not password:
        raise Exception("hrauser and/or hrapass not set in configuration")
    lang = getOptionValue('hralang')
    if not lang:
        lang = 'en'
    setMimeAndSamplerate("application/flac", "44100")
    return sess.login(username, password, lang)
    

@dispatcher.record('trackuri')
def trackuri(a):
    global pathprefix
    msgproc.log("trackuri: [%s]" % a)
    trackid = trackid_from_urlpath(pathprefix, a)
    maybelogin()
    url = sess.get_media_url(trackid) or ""
    #msgproc.log("%s" % media_url)
    return {'media_url' : url}


def track_list(tracks):
    xbmcplugin.entries += trackentries(httphp, pathprefix, xbmcplugin.objid, tracks)


@dispatcher.record('browse')
def browse(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(_rootid, routeplugin=plugin)
    uplog("browse: [%s]" % a)
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    bflg = a['flag'] if 'flag' in a else 'children'
    
    if re.match(_rootidre, objid) is None:
        raise Exception("bad objid [%s]" % objid)
    maybelogin()

    xbmcplugin.objid = objid
    idpath = objid.replace(_rootid, '', 1)
    if bflg == 'meta':
        m = re.match(r'.*\$(.+)$', idpath)
        if m:
            trackid = m.group(1)
            track = sess.get_track(trackid)
            track_list([track])
    else:
        plugin.run([idpath])
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}

@plugin.route('/')
def root():
    if not maybelogin():
        xbmcplugin.add_directory('LOGIN FAILED', '/')
        return
    xbmcplugin.add_directory('Categories', allCategories)
    xbmcplugin.add_directory('Genres', allGenres)
# These seem mostly empty. The hra app uses alleditor
#    xbmcplugin.add_directory('Editor playlists: Moods', allEditorMoods)
#    xbmcplugin.add_directory('Editor playlists: Genres', allEditorGenres)
#    xbmcplugin.add_directory('Editor playlists: Themes', allEditorThemes)
    xbmcplugin.add_directory('Editor Playlists', allEditorPlaylists)
    xbmcplugin.add_directory('My Playlists', allUserPlaylists)
    xbmcplugin.add_directory('My Albums', allUserAlbums)
    xbmcplugin.add_directory('My Tracks', allUserTracks)


@plugin.route('/allcategories')
def allCategories():
    items = sess.get_categories()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(category_view, items))

@plugin.route('/allgenres')
def allGenres():
    items = sess.get_genres()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(category_view, items))

@plugin.route('/category/<catg_id>')
def category_view(catg_id):
    decoded = session.decode_prefix(catg_id)
    uplog("category_view: id [%s] decoded [%s]" % (catg_id, decoded))
    items = sess.get_catg_albums(decoded)
    xbmcplugin.view(items, xbmcplugin.urls_from_id(album_view, items))

@plugin.route('/alleditorgenres')
def allEditorGenres():
    items = sess.get_editorgenres()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(edplaylist_view, items))
@plugin.route('/alleditormoods')
def allEditorMoods():
    items = sess.get_editormoods()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(edplaylist_view, items))
@plugin.route('/alleditorthemes')
def allEditorThemes():
    items = sess.get_editorthemes()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(edplaylist_view, items))

@plugin.route('/alleditorplaylists')
def allEditorPlaylists():
    items = sess.get_alleditorplaylists()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(edplaylist_view, items))
    
@plugin.route('/editorplaylist/<id>')
def edplaylist_view(id):
    track_list(sess.get_editor_playlist(id))

    
@plugin.route('/alluserplaylists')
def allUserPlaylists():
    items = sess.get_alluserplaylists()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(userplaylist_view, items))
@plugin.route('/alluseralbums')
def allUserAlbums():
    items = sess.get_alluseralbums()
    xbmcplugin.view(items, xbmcplugin.urls_from_id(album_view, items))
@plugin.route('/allusertracks')
def allUserTracks():
    track_list(sess.get_allusertracks())

@plugin.route('/userplaylist/<id>')
def userplaylist_view(id):
    track_list(sess.get_user_playlist(id))

@plugin.route('/album/<album_id>')
def album_view(album_id):
    track_list(sess.get_album_tracks(album_id))


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

    idpath = objid.replace(_rootid, '', 1)

    catg = ""
    # Both genres and categories have an objid path beginning with category
    if idpath.startswith('/category'):
        catg = session.decode_prefix(idpath.replace('/category/', '', 1))

    # HRA search always returns albums anyway.
    if catg:
        albums = sess.searchCategory(value, catg)
    else:
        albums = sess.search(value)
    xbmcplugin.view(albums, xbmcplugin.urls_from_id(album_view, albums))
    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries": encoded}


msgproc.log("HighresAudio running")
msgproc.mainloop()
