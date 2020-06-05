# defined to emulate the session object from the tidal module, which is
# defined in the tidalapi part (we want to keep the qobuz api/ dir as
# much alone as possible.
from __future__ import print_function

import sys
import json
from upmplgmodels import Artist, Album, Track, Playlist, SearchResult, \
     Category, Genre, Model
from upmplgutils import *
import hraapi
import urllib
import datetime
import traceback
import base64

class Session(object):
    def __init__(self):
        self.api = hraapi.HRAAPI()

    def login(self, username, password):
        data = self.api.user_login(username=username, password=password)
        if data:
            return True
        else:
            return False


    def isloggedin(self):
        return self.api.isloggedin()
    

    def get_categories(self):
        return list(map(_parse_category, self.api.getAllCategories()))


    def get_genres(self, parent=None):
        data = self.api.getAllGenres()
        return [_parse_genre(g) for g in data]


    def get_catg_albums(self, prefix):
        data = self.api.listCategoryContent(category=prefix, offset=0, limit=30)
        return [_parse_album(a) for a in data]

    
    def get_alluserplaylists(self):
        data = self.api.listAllUserPlaylists()
        if not data:
            return []
        return [_parse_playlist(p) for p in data]
        
    def get_alluseralbums(self):
        data = self.api.listAllUserAlbums()
        if not data:
            return []
        return [_parse_album(p) for p in data]

    def get_allusertracks(self):
        data = self.api.listAllUserTracks()
        if not data:
            return []
        uplog(data)
        return [_parse_track(p) for p in data]
        

    def get_album_tracks(self, albid):
        data = self.api.getAlbumDetails(album_id=albid)
        if not data:
            return {}
        # Apart from the tracks array, sata contains a copy of the album
        # metadata. Parse it like an album.
        album = _parse_album(data)
        return [_parse_track(t, album) for t in data['tracks']]


    def get_media_url(self, trackid):
        data = self.api.getTrackById(track_id=trackid)
        if not data or 'url' not in data or data['url'] is None:
            uplog("get_media_url: no url for [%s]" % trackid)
            return None
        return data['url']

    def get_editormoods(self):
        data = self.api.getAvailableMoods()
        return [_parse_album(a) for a in data]
    def get_editorgenres(self):
        data = self.api.getAvailableGenres()
        return [_parse_album(a) for a in data]
    def get_editorthemes(self):
        data = self.api.getAvailableThemes()
        return [_parse_album(a) for a in data]

    def get_editor_playlist(self, id):
        data = self.api.getEditorPlaylist(id=id)
        if not data:
            return []
        album = _parse_album(data)
        return [_parse_track(t, album) for t in data['tracks']]
        
    def get_playlist_tracks(self, plid):
        data = self.api.playlist_get(playlist_id = plid, extra = 'tracks')
        return [_parse_track(t) for t in data['tracks']['items']]


    def search(self, value):
        data = self.api.quickSearch(search=value)
        albums = []
        for key,value in data.items():
            value['id'] = key
            albums.append(value)
        return [_parse_album(a) for a in albums]


    def searchCategory(self, value, prefix):
        data = self.api.searchCategory(category=prefix, search=value)
        return [_parse_album(a) for a in data]

    
def encode_prefix(p):
    return base64.urlsafe_b64encode(p.encode('utf-8')).decode('utf-8')

def decode_prefix(p):
    return base64.urlsafe_b64decode(p.encode('utf-8')).decode('utf-8')

def _parse_category(data):
    return Category(id=encode_prefix(data['prefix']), name=data['title'], iid = data['id'])

def _parse_genre(data):
    return Genre(id=encode_prefix(data['prefix']), name=data['title'], iid = data['id'])


def _parse_artist(json_obj):
    artist = Artist(id=json_obj['id'], name=json_obj['title'].encode())
    return artist


def _parse_album(data):
    #uplog(data)
    #uplog("-_"*30)

    kwargs = {
        'id': data['id'],
        'name': data['title']
    }
    if 'artist' in data:
        kwargs['artist'] = data['artist']
    if 'cover' in data:
        if isinstance(data['cover'], dict):
            for key in ('preview', 'master', 'thumbnail'):
                if key in data['cover']:
                    kwargs['image'] = 'https://'+data['cover'][key]['file_url']
                    break
        else:
            kwargs['image'] = data['cover']
    a = Album(**kwargs)
    return a


def _parse_track(data, albumarg = None):
    artist = Artist(name=data['artist'])

    kwargs = {
        'id': data['playlistAdd'],
        'name': data['title'],
        'duration': data['playtime'],
        'format': data['format'],
        'artist': artist,
        'available': True
    }

    if 'trackNumber' in data:
        kwargs['track_num'] = data['trackNumber']
    else:
        kwargs['track_num'] = 0

    if albumarg:
        kwargs['album'] = albumarg
    elif 'cover' in data and 'album' in data:
        kwargs['album'] = Album(image=data['cover'], name=data['album'])
            
    return Track(**kwargs)


def _parse_playlist(json_obj, artist=None, artists=None):
    kwargs = {
        'id': json_obj['id'],
        'name': json_obj['name'],
        'num_tracks': json_obj.get('tracks_count'),
        'duration': json_obj.get('duration'),
    }
    return Playlist(**kwargs)
