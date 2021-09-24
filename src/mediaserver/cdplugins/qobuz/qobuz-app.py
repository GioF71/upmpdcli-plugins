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
import conftree
import cmdtalkplugin
from upmplgutils import *

# Using kodi plugin routing plugin: lets use reuse a lot of code from
# the addon.
from routing import Plugin
# Need bogus base_url value to avoid plugin trying to call xbmc to
# retrieve addon id
plugin = Plugin('') 
from session import Session

qobidprefix = '0$qobuz$'

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

session = Session()

_g_loginok = False

def maybelogin(a={}):
    global formatid
    global httphp
    global pathprefix
    global _g_loginok

    # Do this always
    setidprefix(qobidprefix)

    if _g_loginok:
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
    formatid = upconfig.get('qobuzformatid')
    appid = upconfig.get('qobuzappid')
    cfvalue = upconfig.get('qobuzcfvalue')
    if 'user' in a:
        username = a['user']
        password = a['password']
    else:
        username, password = getserviceuserpass(upconfig, 'qobuz')
      
    if formatid:
        formatid = int(formatid)
    else:
        formatid = 7
    
    if formatid == 5:
        setMimeAndSamplerate("audio/mpeg", "44100")
    else:
        setMimeAndSamplerate("application/flac", "44100")

    if not username or not password:
        raise Exception("maybelogin: qobuzuser and/or qobuzpass not set.")

    _g_loginok = session.login(username, password, appid, cfvalue)


# The following two (getappid and login) are not used by the media server, they're for use by the
# OpenHome Credentials service
@dispatcher.record('getappid')
def getappid(a):
    upconfig = conftree.ConfSimple(os.environ["UPMPD_CONFIG"])
    appid = upconfig.get('qobuzappid')
    if appid:
        return {'appid' : appid}
    appid = session.get_appid()
    return {'appid' : appid}
    
@dispatcher.record('login')
def login(a):
    maybelogin(a)
    appid, token = session.get_appid_and_token()
    if token is None:
        # login failed. cmdtalk does not like None values
        token = ''
    return {'appid': appid, 'token' : token}
    
    
@dispatcher.record('trackuri')
def trackuri(a):
    global formatid, pathprefix

    maybelogin()

    msgproc.log("trackuri: [%s]" % a)
    trackid = trackid_from_urlpath(pathprefix, a)

    media_url = session.get_media_url(trackid, formatid)
    if not media_url:
        media_url = ""
        
    #msgproc.log("%s" % media_url)
    if formatid == 5:
        mime = "audio/mpeg"
        kbs = "320"
    else:
        mime = "application/flac"
        kbs = "1410"
    return {'media_url' : media_url, 'mimetype' : mime, 'kbs' : kbs}


def add_directory(title, endpoint):
    if callable(endpoint):
        endpoint = plugin.url_for(endpoint)
    xbmcplugin.entries.append(direntry(qobidprefix + endpoint,
                                       xbmcplugin.objid, title))

def urls_from_id(view_func, items):
    #msgproc.log("urls_from_id: items: %s" % str([item.id for item in items]))
    return [plugin.url_for(view_func, item.id)
            for item in items if str(item.id).find('http') != 0]

def view(data_items, urls, end=True):
    for item, url in zip(data_items, urls):
        title = item.name

        maxsamprate = '44.1'
        maxbitdepth = '16'
        try:
            maxsamprate = item.maxsamprate
            maxbitdepth = item.maxbitdepth
        except:
            pass

        if maxsamprate != '44.1' or maxbitdepth != '16':
            title += ' (' + maxbitdepth + '/' +  maxsamprate + ')'

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
            direntry(qobidprefix + url, xbmcplugin.objid, title, arturi=image,
                     artist=artnm, upnpclass=upnpclass))

def track_list(tracks):
    xbmcplugin.entries += trackentries(httphp, pathprefix,
                                       xbmcplugin.objid, tracks)

@dispatcher.record('browse')
def browse(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(qobidprefix)
    msgproc.log("browse: [%s]" % a)
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    bflg = a['flag'] if 'flag' in a else 'children'
    
    if re.match('0\$qobuz\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    maybelogin()

    xbmcplugin.objid = objid
    idpath = objid.replace(qobidprefix, '', 1)
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
    add_directory('Discover Catalog', whats_new)
    add_directory('Discover Genres', root_genres)
    add_directory('Favourites', my_music)

@plugin.route('/root_genres')
def root_genres():
    items = session.get_genres()
    view(items, urls_from_id(genre_view, items))

@plugin.route('/genre/<genre_id>')
def genre_view(genre_id):
    add_directory('New Releases', plugin.url_for(genre_view_type,
                                                 genre_id=genre_id,
                                                 type='new-releases'))
    add_directory('Qobuz Playlists', plugin.url_for(genre_view_playlists,
                                                    genre_id=genre_id))
    add_directory('Most Streamed', plugin.url_for(genre_view_type,
                                                  genre_id=genre_id,
                                                  type='most-streamed'))
    add_directory('Most Downloaded', plugin.url_for(genre_view_type,
                                                    genre_id=genre_id,
                                                    type='best-sellers'))
    add_directory('Editor Picks', plugin.url_for(genre_view_type,
                                                 genre_id=genre_id,
                                                 type='editor-picks'))
    add_directory('Press Awards', plugin.url_for(genre_view_type,
                                                 genre_id=genre_id,
                                                 type='press-awards'))
    items = session.get_featured_albums(genre_id)
    view(items, urls_from_id(album_view, items))

@plugin.route('/featured/<genre_id>/<type>')
def genre_view_type(genre_id, type):
    items = session.get_featured_albums(genre_id=genre_id, type=type)
    view(items, urls_from_id(album_view, items))

# This used to be /featured/<genre_id>/playlist, but this path can be
# matched by the one for genre_view_type, and the wrong function may
# be called, depending on the rules ordering (meaning we had the
# problem on an rpi, but not ubuntu...)
@plugin.route('/featured_playlists/<genre_id>')
def genre_view_playlists(genre_id):
    items = session.get_featured_playlists(genre_id=genre_id)
    view(items, urls_from_id(playlist_view, items))

@plugin.route('/whats_new')
def whats_new():
    add_directory('Playlists', plugin.url_for(featured,
                                              content_type='playlists'))
    add_directory('Albums', plugin.url_for(featured, content_type='albums'))
    add_directory('Artists', plugin.url_for(featured, content_type='artists'))
    xbmcplugin.endOfDirectory(plugin.handle)

@plugin.route('/featured/<content_type>')
def featured(content_type=None):
    items = session.get_featured_items(content_type)
    if content_type == 'artists':
        view(items, urls_from_id(artist_view, items))
    elif content_type == 'albums':
        view(items, urls_from_id(album_view, items))
    elif content_type == 'playlists':
        view(items, urls_from_id(playlist_view, items))
    else:
        print("qobuz-app bad featured type %s" % content_type, file=sys.stderr)


@plugin.route('/my_music')
def my_music():
    add_directory('Albums', favourite_albums)
    add_directory('Tracks', favourite_tracks)
    add_directory('Artists', favourite_artists)
    add_directory('Playlists', favourite_playlists)
    xbmcplugin.endOfDirectory(plugin.handle)
    pass

@plugin.route('/album/<album_id>')
def album_view(album_id):
    track_list(session.get_album_tracks(album_id))


@plugin.route('/playlist/<playlist_id>')
def playlist_view(playlist_id):
    track_list(session.get_playlist_tracks(playlist_id))

def ListItem(tt):
    return tt

@plugin.route('/artist/<artist_id>')
def artist_view(artist_id):
    xbmcplugin.addDirectoryItem(
        plugin.handle, plugin.url_for(similar_artists, artist_id),
        ListItem('Similar Artists'), True
    )
    albums = session.get_artist_albums(artist_id) 
    view(albums, urls_from_id(album_view, albums))


@plugin.route('/artist/<artist_id>/similar')
def similar_artists(artist_id):
    artists = session.get_artist_similar(artist_id)
    view(artists, urls_from_id(artist_view, artists))


@plugin.route('/favourite_tracks')
def favourite_tracks():
    track_list(session.user.favorites.tracks())


@plugin.route('/favourite_artists')
def favourite_artists():
    try:
        items = session.user.favorites.artists()
    except Exception as err:
        msgproc.log("session.user.favorite.artists failed: %s" % err)
        return
    if items:
        msgproc.log("First artist name %s"% items[0].name)
        view(items, urls_from_id(artist_view, items))


@plugin.route('/favourite_albums')
def favourite_albums():
    items = session.user.favorites.albums()
    view(items, urls_from_id(album_view, items))


@plugin.route('/favourite_playlists')
def favourite_playlists():
    items = session.user.favorites.playlists()
    view(items, urls_from_id(playlist_view, items))

@dispatcher.record('search')
def search(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(qobidprefix)
    msgproc.log("search: [%s]" % a)
    objid = a['objid']
    field = a['field'] if 'field' in a else None
    value = a['value']
    objkind = a['objkind'] if 'objkind' in a and a['objkind'] else None
    
    if re.match('0\$qobuz\$', objid) is None:
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
        # Kazoo and bubble only search for object.container.album, not
        # playlists. So if we want these to be findable, need to send
        # them with the albums
        if objkind == 'album':
            searchresults = session.search(value, 'playlists')
            objkind = 'playlist'
            # Fallthrough to view playlists
    if objkind is None or objkind == 'playlist':
        view(searchresults.playlists,
             urls_from_id(playlist_view, searchresults.playlists), end=False)
    if objkind is None or objkind == 'track':
        track_list(searchresults.tracks)

    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}

msgproc.log("Qobuz running")
msgproc.mainloop()
