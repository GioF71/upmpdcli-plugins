#
# Copyright (C) 2021 Jean-Francois Dockes
#
# A lot of code strongly inspired or copied from the Kodi Deezer API,
# the copyright of which is not too clear (but it's GPL):
#     Copyright (C) 2016 Jakub Gawron
#     Copyright (C) 2020 Valentin271 (Github.com)
# 
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the
#  Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


#
# Performs some massaging of the data out from the lower level api
# interface and creates objects defined in the upmplgmodels.py module.
#

from __future__ import print_function

import sys
from upmplgmodels import Artist, Album, Track, Playlist, SearchResult, \
     Category, Genre, Model, User
from upmplgutils import *
import deezerapi

class Session(object):
    def __init__(self):
        self.api = deezerapi.DeezerAPI()

    def login(self, cachedir, username, password):
        data = self.api.user_login(cachedir, username, password)
        if data:
            return True
        else:
            return False

    def isloggedin(self):
        return self.api.isloggedin()
    
    def get_media_url(self, trackid):
        return self.api.request_stream(id=trackid)

    def get_followings(self):
        data = self.api.getUserFollowings()
        return [_parse_user(p) for p in data['data']]
    
    def get_favourite_playlists(self, id='me'):
        data = self.api.getUserPlaylists(id=id)
        if not data:
            return []
        return [_parse_playlist(p) for p in data['data']]

    def get_favourite_albums(self, id='me'):
        data = self.api.getUserAlbums(id=id)
        return [_parse_album(p) for p in data['data']]

    def get_favourite_artists(self, id='me'):
        data = self.api.getUserArtists(id=id)
        return [_parse_artist(p) for p in data['data']]

    def get_favourite_tracks(self, id='me'):
        data = self.api.getUserTracks(id=id)
        return [_parse_track(p) for p in data['data']]

    def get_artist_albums(self, artid):
        data = self.api.getArtistAlbums(artid)
        return [_parse_album(p) for p in data['data']]

    def get_user_playlist(self, id):
        data = self.api.getUserPlaylist(id)
        if not data:
            return []
        return [_parse_track(t) for t in data['data']]

    def get_album_tracks(self, albumid):
        data = self.api.getAlbum(albumid)
        album = _parse_album(data)
        if 'tracks' in data:
            tracks = [_parse_track(t, album) for t in data['tracks']['data']]
            for i in range(len(tracks)):
                if tracks[i].track_num == 0:
                    tracks[i].track_num = i+1
            return tracks


    def _search1(self, query, tp):
        uplog("_search1: query [%s] tp [%s]" % (query, tp))

        limit = 200
        if tp == 'artist':
            limit = 20
        elif tp == 'album' or tp == 'playlist':
            limit = 50
        offset = 0
        all = []
        while offset < limit:
            uplog("_search1: call api.search, offset %d" % offset)
            data = self.api.search(query, tp, offset=offset)
            uplog("_search1: got %d results" % len(data['data']))
            ncnt = 0
            ndata = []
            try:
                if tp == 'artist':
                    ncnt = len(data['data'])
                    ndata = [_parse_artist(i) for i in data['data']]
                elif tp == 'album':
                    ncnt = len(data['data'])
                    ndata = [_parse_album(i) for i in data['data']]
                elif tp == 'track':
                    ncnt = len(data['data'])
                    ndata = [_parse_track(i) for i in data['data']]
            except Exception as err:
                uplog("_search1: exception while parsing result: %s" % err)
                break
            all.extend(ndata)
            if ncnt == 0:
                break
            offset += ncnt

        if tp == 'artist':
            return SearchResult(artists=all)
        elif tp == 'album':
            return SearchResult(albums=all)
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
            return cplt





def _parse_playlist(data, artist=None, artists=None):
    kwargs = {
        'id': data['id'],
        'name': data['title'],
        'num_tracks': data.get('nb_tracks'),
        'duration': data.get('duration')
    }
    return Playlist(**kwargs)

    
def _parse_artist(data):
    return Artist(id=data['id'], name=data['name'])

def _parse_user(data):
    return User(id=data['id'], name=data['name'], image=data['picture'])


def _parse_album(data):
    kwargs = {
        'id': data['id'],
        'name': data['title']
    }
    if 'artist' in data:
        kwargs['artist'] = data['artist']['name']
    k = 'cover'
    if 'cover_big' in data:
        k = 'cover_big'
    if k in data:
            kwargs['image'] = data[k]
    a = Album(**kwargs)
    return a


def _parse_track(data, albumarg = None):
    artist = Artist(id=data['artist']['id'], name=data['artist']['name'])

    kwargs = {
        'id': data['id'],
        'name': data['title'],
        'duration': data['duration'],
        'artist': artist,
        'available': data['readable']
    }

    if 'track_position' in data:
        kwargs['track_num'] = data['track_position']
    else:
        kwargs['track_num'] = 0
        
    if albumarg:
        kwargs['album'] = albumarg
    elif 'album' in data:
        alb = data['album']
        kwargs['album'] = Album(image=alb['cover_big'], name=alb['title'])

    # If track has own cover, use it (e.g. for multialbum playlists)
    if 'picture_big' in data:
        kwargs['image'] = data['picture_big']

    return Track(**kwargs)
