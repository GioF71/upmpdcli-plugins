# Copyright (C) 2016 J.F.Dockes
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the
#   Free Software Foundation, Inc.,
#   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
from __future__ import print_function

import sys
import json
import datetime
import time
import os
import traceback

import spotipy
import spotipy.util as spotutil

from upmplgmodels import Artist, Album, Track, Playlist, SearchResult, \
     Category, Genre
from upmplgutils import uplog

import upmspotid

class Session(object):
    def __init__(self):
        self.api = None
        self.user = None
        
    def dmpdata(self, who, data):
        uplog("%s: %s" % (who, json.dumps(data, indent=4)))

    def login(self, user, cachepath):
        self.user = user
        scope = upmspotid.SCOPE
        sp_oauth = spotipy.oauth2.SpotifyOAuth(
            upmspotid.CLIENT_ID, upmspotid.CLIENT_SECRET,
            upmspotid.REDIRECT_URI, scope=upmspotid.SCOPE, cache_path=cachepath)
        self.api = spotipy.Spotify(auth=sp_oauth)
        return True
    
    def recent_tracks(self):
        if not self.api:
            uplog("Not logged in")
            return []
        data = self.api.current_user_recently_played()
        #self.dmpdata('user_recently_played', data)
        return [_parse_track(i['track']) for i in data['items']]

    def favourite_tracks(self):
        if not self.api:
            uplog("Not logged in")
            return []
        data = self.api.current_user_saved_tracks(limit=50, offset=0)
        self.dmpdata('favourite_tracks', data)
        return [_parse_track(item['track']) for item in data['items']]
        
    def favourite_albums(self):
        if not self.api:
            uplog("Not logged in")
            return []
        data = self.api.current_user_saved_albums(limit=50)
        albums = data['items']
        while data['next']:
            data = self.api.next(data)
            albums.extend(data['items'])
        #self.dmpdata('favourite_albums', data)
        results = []
        for item in albums:
            album = _parse_album(item['album'])
            if album:
                results.append(album)
        return results

    def my_playlists(self):
        if not self.api:
            uplog("Not logged in")
            return []
        data = self.api.current_user_playlists()
        #self.dmpdata('user_playlists', data)
        try:
            return [_parse_playlist(item) for item in data['items']]
        except:
            uplog("my_playlists: _parse_playlist failed")
            return []

    def featured_playlists(self):
        if not self.api:
            uplog("Not logged in")
            return []
        data = self.api.featured_playlists()
        #self.dmpdata('featured_playlists', data)
        try:
            return [_parse_playlist(item) for item in data['playlists']['items']]
        except:
            uplog("featured_playlists: _parse_playlist failed")
            return []

    def favourite_artists(self):
        if not self.api:
            uplog("Not logged in")
            return []
        data = self.api.current_user_followed_artists(limit=50)
        artists = data['artists']['items']
        while data['artists']['next']:
            data['artists'] = self.api.next(data['artists'])
            artists.extend(data['artists']['items'])
        #self.dmpdata('favourite_artists', data)
        return [_parse_artist(item) for item in artists]

    def get_categories(self):
        data = self.api.categories(limit=50)
        #self.dmpdata('get_categories', data)
        return [Category(id=item['id'],name=item['name'])
                for item in data['categories']['items']]

    def get_category_playlists(self, catgid):
        data = self.api.category_playlists(catgid)
        #self.dmpdata('category_playlists', data)
        return [_parse_playlist(item) for item in data['playlists']['items']]
    
    def get_artist_albums(self, id):
        data = self.api.artist_albums(id, limit=50)
        albums = data['items']
        while data['next']:
            data = self.api.next(data)
            albums.extend(data['items'])
        results = []
        for item in albums:
            result = _parse_album(item)
            if result:
                results.append(result)
        return results
        
    def new_releases(self):
        if not self.api:
            uplog("Not logged in")
            return []
        data = self.api.new_releases()
        #self.dmpdata('new_releases', data)
        results = []
        for data in data['albums']['items']:
            album = _parse_album(data)
            if album:
                results.append(album)
        return results

    def get_album_tracks(self, albid):
        data = self.api.album(album_id = albid)
        album = _parse_album(data)
        if not album:
            return []
        track_data = self.api.album_tracks(album_id = albid, limit=50)
        tracks = track_data['items']
        while track_data['next']:
            track_data = self.api.next(track_data)
            tracks.extend(track_data['items'])
        return [_parse_track(t, album) for t in tracks]


    def user_playlist_tracks(self, userid, plid):
        data = self.api.user_playlist_tracks(userid, plid)
        #self.dmpdata('playlist_tracks', data)
        return [_parse_track(item['track']) for item in data['items']]
        
    def _search1(self, query, tp):
        uplog("_search1: query [%s] tp [%s]" % (query, tp))

        # Limit is max count we return, slice unit query size
        limit = 150
        slice = 50
        if tp == 'artist':
            limit = 20
            slice = 20
        elif tp == 'album' or tp == 'playlist':
            limit = 50
            slice = 50
        offset = 0
        all = []
        while offset < limit:
            uplog("_search1: call api.search, offset %d" % offset)
            data = self.api.search(query, type=tp, offset=offset, limit=slice)
            ncnt = 0
            ndata = []
            try:
                if tp == 'artist':
                    ncnt = len(data['artists']['items'])
                    ndata = [_parse_artist(i) for i in data['artists']['items']]
                elif tp == 'album':
                    ncnt = len(data['albums']['items'])
                    ndata = [_parse_album(i) for i in data['albums']['items']]
                    ndata = [alb for alb in ndata if (alb and alb.available)]
                elif tp == 'playlist':
                    #uplog("PLAYLISTS: %s" % json.dumps(data, indent=4))
                    ncnt = len(data['playlists']['items'])
                    ndata = [_parse_playlist(i) for i in \
                             data['playlists']['items']]
                elif tp == 'track':
                    ncnt = len(data['tracks']['items'])
                    ndata = [_parse_track(i) for i in data['tracks']['items']]
            except Exception as err:
                uplog("_search1: exception while parsing result for %s: %s" % (tp, err))
                break
            all.extend(ndata)
            #uplog("Got %d more (slice %d)" % (ncnt, slice))
            if ncnt < slice:
                break
            offset += slice

        if tp == 'artist':
            return SearchResult(artists=all)
        elif tp == 'album':
            return SearchResult(albums=all)
        elif tp == 'playlist':
            return SearchResult(playlists=all)
        elif tp == 'track':
            return SearchResult(tracks=all)

    def search(self, query, tp):
        if tp:
            return self._search1(query, tp)
        else:
            cplt = SearchResult()
            res = self._search1(query, 'artist')
            cplt.artists = res.artists
            res = self._search1(query, 'album')
            cplt.albums = res.albums
            res = self._search1(query, 'track')
            cplt.tracks = res.tracks
            res = self._search1(query, 'playlist')
            cplt.playlists = res.playlists
            return cplt



def _parse_playlist(data, artist=None, artists=None):
    display_name = None
    id = None
    if 'display_name' in data['owner'] and data['owner']['display_name']:
        display_name = data['owner']['display_name']
    elif 'id' in data['owner']:
        display_name = data['owner']['id']
    #uplog("_parse_playlist: name: %s User: %s" % (data['name'], display_name))

    artist = Artist(id=id, name=display_name)        

    kwargs = {
        'id': data['id'],
        'userid': data['owner']['id'],
        'artist': artist,
        'name': data['name'],
        'num_tracks': data['tracks']['total'],
    }
    return Playlist(**kwargs)

def _parse_album(data, artist=None, artists=None):
    try:
        #uplog("_parse_album: %s" % data)
        if artist is None and 'artists' in data:
            artist = _parse_artist(data['artists'][0])
        available = True
        #if not available:
        #    uplog("Album not streamable: %s " % data['title'])
        kwargs = {
            'id': data['id'],
            'name': data['name'],
            #'num_tracks': data.get('tracks_count'),
            #'duration': data.get('duration'),
            'artist': artist,
            'available': available,
            #'artists': artists,
        }
        
        if 'images' in data and data['images']:
            kwargs['image'] = data['images'][0]['url']
        
        if 'releaseDate' in data:
            try:
                # Keep this as a string else we fail to json-reserialize it later
                kwargs['release_date'] = data['releaseDate']
            except ValueError:
                pass
        return Album(**kwargs)
    except Exception as err:
        uplog("parse_album: [%s]" % err)
        traceback.print_exc()
        uplog("parse_album: %s" % json.dumps(data, indent=4))
        return False

def _parse_track(data, albumarg = None):
    artist = Artist()
    if 'artists' in data:
        artist = _parse_artist(data['artists'][0])
    elif albumarg and albumarg.artist:
        artist = albumarg.artist

    available = True
    duration = 0
    if 'duration_ms' in data:
        duration = str(int(data['duration_ms'])//1000)
    kwargs = {
        'id': data['id'],
        'name': data['name'],
        'duration': duration,
        'track_num': data['track_number'],
        'disc_num': data['disc_number'],
        'artist': artist,
        'available': available
    }
    if albumarg:
        kwargs['album'] = albumarg
    elif 'album' in data:
        kwargs['album'] = _parse_album(data['album'])
    return Track(**kwargs)


def _parse_artist(data):
    artist = Artist(id=data['id'], name=data['name'])
    return artist
