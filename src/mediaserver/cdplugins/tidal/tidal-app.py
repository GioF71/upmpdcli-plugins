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

import tidalapi
from tidalapi.models import Album, Artist
from tidalapi import Quality

# Using kodi plugin routing plugin: lets use reuse a lot of code from
# the addon.
from routing import Plugin
# Need bogus base_url value to avoid plugin trying to call xbmc to
# retrieve addon id
plugin = Plugin('') 

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

is_logged_in = False

tidalidprefix = '0$tidal$'

def maybelogin(a={}):
    global session
    global quality
    global httphp
    global pathprefix
    global is_logged_in
    
    # Do this always
    setidprefix(tidalidprefix)

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
    if 'user' in a:
        username = a['user']
        password = a['password']
    else:
        username, password = getserviceuserpass(upconfig, 'tidal')
    if not username or not password:
        raise Exception("tidaluser and/or tidalpass not set in configuration")

    qalstr = upconfig.get('tidalquality')
    if qalstr == 'lossless':
        quality = Quality.lossless
    elif qalstr == 'high':
        quality = Quality.high
    elif qalstr == 'low':
        quality = Quality.low
    elif not qalstr:
        quality = Quality.high
    else:
        raise Exception("Bad tidal quality string in config. "+
                        "Must be lossless/high/low")
    tidalconf = tidalapi.Config(quality)
    session = tidalapi.Session(config=tidalconf)
    session.login(username, password)
    is_logged_in = True
    if quality == Quality.lossless:
        setMimeAndSamplerate('audio/flac', "44100")
    else:
        setMimeAndSamplerate('audio/mpeg', "44100")


def get_mimeandkbs():
    if quality == Quality.lossless:
        return ('audio/flac', str(1411))
    elif quality == Quality.high:
        return ('audio/mpeg', str(320))
    else:
        return ('audio/mpeg', str(96))

# This is not used by the media server. It's for use by the OpenHome
# Credentials service
@dispatcher.record('login')
def login(a):
    maybelogin(a)
    session_id, country_code = session.get_token_and_country()
    return {'token' : session_id, 'country' : country_code}

@dispatcher.record('trackuri')
def trackuri(a):
    maybelogin()
    msgproc.log("trackuri: [%s]" % a)
    trackid = trackid_from_urlpath(pathprefix, a)
    
    media_url = session.get_media_url(trackid)
    msgproc.log("%s" % media_url)
    if not media_url.startswith('http://') and not \
           media_url.startswith('https://'):
        host, tail = media_url.split('/', 1)
        app, playpath = tail.split('/mp4:', 1)
        media_url = 'rtmp://%s app=%s playpath=mp4:%s' % (host, app, playpath)
    mime, kbs = get_mimeandkbs()
    return {'media_url' : media_url, 'mimetype' : mime, 'kbs' : kbs}

    
def add_directory(title, endpoint):
    if callable(endpoint):
        endpoint = plugin.url_for(endpoint)
    xbmcplugin.entries.append(direntry(tidalidprefix + endpoint,
                                       xbmcplugin.objid, title))

def urls_from_id(view_func, items):
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
            direntry(tidalidprefix + url, xbmcplugin.objid, title, arturi=image,
                     artist=artnm, upnpclass=upnpclass))

def track_list(tracks):
    xbmcplugin.entries += trackentries(httphp, pathprefix,
                                       xbmcplugin.objid, tracks)
       
@dispatcher.record('browse')
def browse(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(tidalidprefix)
    msgproc.log("browse: [%s]" % a)
    if 'objid' not in a:
        raise Exception("No objid in args")
    objid = a['objid']
    bflg = a['flag'] if 'flag' in a else 'children'
    
    if re.match('0\$tidal\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    maybelogin()

    xbmcplugin.objid = objid
    idpath = objid.replace(tidalidprefix, '', 1)
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
    add_directory('My Music', my_music)
    add_directory('Featured Playlists', featured_playlists)
    add_directory("What's New", whats_new)
    add_directory('Genres', genres)
    add_directory('Moods', moods)


@plugin.route('/track_radio/<track_id>')
def track_radio(track_id):
    track_list(session.get_track_radio(track_id))


@plugin.route('/moods')
def moods():
    items = session.get_moods()
    view(items, urls_from_id(moods_playlists, items))


@plugin.route('/moods/<mood>')
def moods_playlists(mood):
    items = session.get_mood_playlists(mood)
    view(items, urls_from_id(playlist_view, items))


@plugin.route('/genres')
def genres():
    items = session.get_genres()
    view(items, urls_from_id(genre_view, items))


@plugin.route('/genre/<genre_id>')
def genre_view(genre_id):
    add_directory('Playlists', plugin.url_for(genre_playlists,
                                              genre_id=genre_id))
    add_directory('Albums', plugin.url_for(genre_albums, genre_id=genre_id))
    add_directory('Tracks', plugin.url_for(genre_tracks, genre_id=genre_id))
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route('/genre/<genre_id>/playlists')
def genre_playlists(genre_id):
    items = session.get_genre_items(genre_id, 'playlists')
    view(items, urls_from_id(playlist_view, items))


@plugin.route('/genre/<genre_id>/albums')
def genre_albums(genre_id):
    xbmcplugin.setContent(plugin.handle, 'albums')
    items = session.get_genre_items(genre_id, 'albums')
    view(items, urls_from_id(album_view, items))

@plugin.route('/genre/<genre_id>/tracks')
def genre_tracks(genre_id):
    items = session.get_genre_items(genre_id, 'tracks')
    track_list(items)


@plugin.route('/featured_playlists')
def featured_playlists():
    items = session.get_featured()
    view(items, urls_from_id(playlist_view, items))


@plugin.route('/whats_new')
def whats_new():
    add_directory('Recommended Playlists', plugin.url_for(featured, group='recommended', content_type='playlists'))
    add_directory('Recommended Albums', plugin.url_for(featured, group='recommended', content_type='albums'))
    add_directory('Recommended Tracks', plugin.url_for(featured, group='recommended', content_type='tracks'))
    add_directory('New Playlists', plugin.url_for(featured, group='new', content_type='playlists'))
    add_directory('New Albums', plugin.url_for(featured, group='new', content_type='albums'))
    add_directory('New Tracks', plugin.url_for(featured, group='new', content_type='tracks'))
    add_directory('Top Albums', plugin.url_for(featured, group='top', content_type='albums'))
    add_directory('Top Tracks', plugin.url_for(featured, group='top', content_type='tracks'))
    if session.country_code != 'US':
        add_directory('Local Playlists', plugin.url_for(featured, group='local', content_type='playlists'))
        add_directory('Local Albums', plugin.url_for(featured, group='local', content_type='albums'))
        add_directory('Local Tracks', plugin.url_for(featured, group='local', content_type='tracks'))
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route('/featured/<group>/<content_type>')
def featured(group=None, content_type=None):
    items = session.get_featured_items(content_type, group)
    if content_type == 'tracks':
        track_list(items)
    elif content_type == 'albums':
        xbmcplugin.setContent(plugin.handle, 'albums')
        view(items, urls_from_id(album_view, items))
    elif content_type == 'playlists':
        view(items, urls_from_id(playlist_view, items))


@plugin.route('/my_music')
def my_music():
    add_directory('My Playlists', my_playlists)
    add_directory('Favourite Playlists', favourite_playlists)
    add_directory('Favourite Artists', favourite_artists)
    add_directory('Favourite Albums', favourite_albums)
    add_directory('Favourite Tracks', favourite_tracks)
    xbmcplugin.endOfDirectory(plugin.handle)


@plugin.route('/album/<album_id>')
def album_view(album_id):
    xbmcplugin.addSortMethod(plugin.handle, xbmcplugin.SORT_METHOD_TRACKNUM)
    track_list(session.get_album_tracks(album_id))


def ListItem(tt):
    return tt

@plugin.route('/artist/<artist_id>')
def artist_view(artist_id):
    xbmcplugin.setContent(plugin.handle, 'albums')
    xbmcplugin.addDirectoryItem(
        plugin.handle, plugin.url_for(top_tracks, artist_id),
        ListItem('Top Tracks'), True
    )
    xbmcplugin.addDirectoryItem(
        plugin.handle, plugin.url_for(artist_radio, artist_id),
        ListItem('Artist Radio'), True
    )
    xbmcplugin.addDirectoryItem(
        plugin.handle, plugin.url_for(similar_artists, artist_id),
        ListItem('Similar Artists'), True
    )
    albums = session.get_artist_albums(artist_id) + \
             session.get_artist_albums_ep_singles(artist_id) + \
             session.get_artist_albums_other(artist_id)
    view(albums, urls_from_id(album_view, albums))


@plugin.route('/artist/<artist_id>/radio')
def artist_radio(artist_id):
    track_list(session.get_artist_radio(artist_id))


@plugin.route('/artist/<artist_id>/top')
def top_tracks(artist_id):
    track_list(session.get_artist_top_tracks(artist_id))


@plugin.route('/artist/<artist_id>/similar')
def similar_artists(artist_id):
    xbmcplugin.setContent(plugin.handle, 'artists')
    artists = session.get_artist_similar(artist_id)
    view(artists, urls_from_id(artist_view, artists))


@plugin.route('/playlist/<playlist_id>')
def playlist_view(playlist_id):
    track_list(session.get_playlist_tracks(playlist_id))


@plugin.route('/user_playlists')
def my_playlists():
    items = session.user.playlists()
    view(items, urls_from_id(playlist_view, items))


@plugin.route('/favourite_playlists')
def favourite_playlists():
    items = session.user.favorites.playlists()
    view(items, urls_from_id(playlist_view, items))


@plugin.route('/favourite_artists')
def favourite_artists():
    xbmcplugin.setContent(plugin.handle, 'artists')
    try:
        items = session.user.favorites.artists()
        if len(items):
            msgproc.log("First artist name %s"% items[0].name)
    except Exception as err:
        msgproc.log("session.user.favorite.artists failed: %s" % err)
        items = []
    view(items, urls_from_id(artist_view, items))


@plugin.route('/favourite_albums')
def favourite_albums():
    xbmcplugin.setContent(plugin.handle, 'albums')
    items = session.user.favorites.albums()
    view(items, urls_from_id(album_view, items))


@plugin.route('/favourite_tracks')
def favourite_tracks():
    track_list(session.user.favorites.tracks())


@dispatcher.record('search')
def search(a):
    global xbmcplugin
    xbmcplugin = XbmcPlugin(tidalidprefix)
    msgproc.log("search: [%s]" % a)
    objid = a['objid']
    field = a['field'] if 'field' in a else None
    objkind = a['objkind'] if 'objkind' in a else None

    value = a['value']
    if re.match('0\$tidal\$', objid) is None:
        raise Exception("bad objid [%s]" % objid)
    xbmcplugin.objid = objid
    maybelogin()
    
    # objkind is mandatory and maybe 'artist', 'album', 'playlist', 'track'
    # If our caller does not set it, we run multiple searches
    if not objkind or objkind == 'artist':
        searchresults = session.search('artist', value)
        view(searchresults.artists,
             urls_from_id(artist_view, searchresults.artists), end=False)
    if not objkind or objkind == 'album':
        searchresults = session.search('album', value)
        view(searchresults.albums,
             urls_from_id(album_view, searchresults.albums), end=False)
    if not objkind or objkind == 'playlist':
        searchresults = session.search('playlist', value)
        view(searchresults.playlists,
             urls_from_id(playlist_view, searchresults.playlists), end=False)
    if not objkind or objkind == 'track':
        searchresults = session.search('track', value)
        track_list(searchresults.tracks)
    #msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries" : encoded}


msgproc.log("Tidal running")
msgproc.mainloop()
