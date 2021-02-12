# defined to emulate the session object from the tidal module, which is
# defined in the tidalapi part (we want to keep the qobuz api/ dir as
# much alone as possible.
from __future__ import print_function

import sys
import json
from upmplgmodels import Artist, Album, Track, Playlist, SearchResult, \
     Category, Genre, Model
from upmplgutils import *
import deezerapi
import urllib
import datetime
import traceback
import base64

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
    

    def get_alluserplaylists(self):
        data = self.api.getAllUserPlaylists()
        if not data:
            return []
        return [_parse_playlist(p) for p in data['data']]


    def get_user_playlist(self, id):
        data = self.api.getUserPlaylist(playlist_id=id)
        if not data:
            return []
        return [_parse_track(t) for t in data]

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

    
def encode_prefix(p):
    return base64.urlsafe_b64encode(p.encode('utf-8')).decode('utf-8')

def decode_prefix(p):
    return base64.urlsafe_b64decode(p.encode('utf-8')).decode('utf-8')

def _parse_category(data):
    return Category(id=encode_prefix(data['prefix']), name=data['title'], iid = data['id'])

def _parse_genre(data):
    return Genre(id=encode_prefix(data['prefix']), name=data['title'], iid = data['id'])


def _parse_artist(data):
    return Artist(id=data['id'], name=data['name'])


def _parse_album(data):
    #uplog(data)
    #uplog("-_"*30)

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
        'available': True
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

