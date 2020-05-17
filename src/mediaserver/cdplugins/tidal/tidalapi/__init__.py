# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Thomas Amland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals, print_function

import sys
import re
import datetime
import json
import random
import logging
import requests
try:
    from requests.packages import urllib3
except:
    import urllib3
from collections import namedtuple
from .models import SubscriptionType, Quality
from .models import Artist, Album, Track, Playlist, SearchResult, Category
try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin

class MLog(object):
    def __init__(self):
        self.f = sys.stderr
        self.level = 1
    def isEnabledFor(self, l):
        return True
    def debug(self, msg):
        if self.level >= 3:
            print("%s" % msg, file=self.f)
    def info(self, msg):
        if self.level >= 2:
            print("%s" % msg, file=self.f)
    def error(self, msg):
        if self.level >= 1:
            print("%s" % msg, file=self.f)

#log = logging.getLogger(__name__)
log = MLog()

# See https://github.com/arnesongit/python-tidal/ for token descs
class Config(object):
    def __init__(self, quality=Quality.high, apitoken = 'pl4Vc0hemlAXD0mN'):
        self.quality = quality
        self.api_location = 'https://api.tidalhifi.com/v1/'
        self.api_token = apitoken
        self.preview_token = "8C7kRFdkaRp0dLBp" # Token for Preview Mode

class Session(object):

    def __init__(self, config=Config()):
        """:type _config: :class:`Config`"""
        self._config = config
        self.session_id = None
        self.user = None
        self.country_code = 'US'   # Enable Trial Mode
        self.client_unique_key = None
        try:
            urllib3.disable_warnings() # Disable OpenSSL Warnings in URLLIB3
        except:
            pass

    def logout(self):
        self.session_id = None
        self.user = None

    def load_session(self, session_id, country_code, user_id=None,
                     subscription_type=None, unique_key=None):
        self.session_id = session_id
        self.client_unique_key = unique_key
        self.country_code = country_code
        if not self.country_code:
            # Set Local Country Code to enable Trial Mode 
            self.country_code = self.local_country_code()
        if user_id:
            self.user = self.init_user(user_id=user_id,
                                       subscription_type=subscription_type)
        else:
            self.user = None

    def generate_client_unique_key(self):
        return format(random.getrandbits(64), '02x')

    def login(self, username, password, subscription_type=None):
        self.logout()
        if not username or not password:
            return False
        if not subscription_type:
            # Set Subscription Type corresponding to the given playback quality
            subscription_type = SubscriptionType.hifi if \
                                self._config.quality == Quality.lossless else \
                                SubscriptionType.premium
        if not self.client_unique_key:
            # Generate a random client key if no key is given
            self.client_unique_key = self.generate_client_unique_key()
        url = urljoin(self._config.api_location, 'login/username')
        headers = { "X-Tidal-Token": self._config.api_token }
        payload = {
            'username': username,
            'password': password,
            'clientUniqueKey': self.client_unique_key
        }
        log.debug('Using Token "%s" with clientUniqueKey "%s"' %
                  (self._config.api_token, self.client_unique_key))
        r = requests.post(url, data=payload, headers=headers)
        if not r.ok:
            try:
                msg = r.json().get('userMessage')
            except:
                msg = r.reason
            log.error("Tidal login: %s" % msg)
        else:
            try:
                body = r.json()
                self.session_id = body['sessionId']
                self.country_code = body['countryCode']
                self.user = self.init_user(user_id=body['userId'],
                                           subscription_type=subscription_type)
            except Exception as err:
                log.error('Tidal login failed. err %s %s' % (err, body))
                self.logout()

        return self.is_logged_in

    def get_token_and_country(self):
        return self.session_id, self.country_code
    
    def init_user(self, user_id, subscription_type):
        return User(self, user_id=user_id, subscription_type=subscription_type)

    def local_country_code(self):
        url = urljoin(self._config.api_location, 'country/context')
        headers = { "X-Tidal-Token": self._config.api_token}
        r = requests.request('GET', url, params={'countryCode': 'WW'},
                             headers=headers)
        if not r.ok:
            return 'US'
        return r.json().get('countryCode')

    @property
    def is_logged_in(self):
        return True if self.session_id and self.country_code and self.user \
               else False
    
    def check_login(self):
        """ Returns true if current session is valid, false otherwise. """
        if not self.is_logged_in:
            return False
        self.user.subscription = self.get_user_subscription(self.user.id)
        return True if self.user.subscription != None else False

    def request(self, method, path, params=None, data=None, headers=None):
        request_headers = {}
        request_params = {
            'sessionId': self.session_id,
            'countryCode': self.country_code,
            'limit': '999',
        }
        if headers:
            request_headers.update(headers)
        if params:
            request_params.update(params)
        url = urljoin(self._config.api_location, path)
        if self.is_logged_in:
            # Request with API Session if SessionId is not given in headers parameter
            if not 'X-Tidal-SessionId' in request_headers:
                request_headers.update({'X-Tidal-SessionId': self.session_id})
        else:
            # Request with Preview-Token. Remove SessionId if given via headers parameter
            request_headers.pop('X-Tidal-SessionId', None)
            request_params.update({'token': self._config.preview_token})
        r = requests.request(method, url, params=request_params, data=data, headers=request_headers)
        log.debug("%s %s" % (method, r.request.url))
        if not r.ok:
            log.error(r.url)
            try:
                log.error(r.json().get('userMessage'))
            except:
                log.error(r.reason)
        r.raise_for_status()
        if r.content and log.isEnabledFor(logging.INFO):
            log.info("response: %s" % json.dumps(r.json(), indent=4))
        return r

    def get_user(self, user_id):
        return self._map_request('users/%s' % user_id, ret='user')

    def get_user_subscription(self, user_id):
        return self._map_request('users/%s/subscription' % user_id, ret='subscription')

    def get_user_playlists(self, user_id):
        return self._map_request('users/%s/playlists' % user_id, ret='playlists')

    def get_playlist(self, playlist_id):
        return self._map_request('playlists/%s' % playlist_id, ret='playlist')

    def get_playlist_tracks(self, playlist_id):
        return self._map_request('playlists/%s/tracks' % playlist_id, ret='tracks')

    def get_album(self, album_id):
        return self._map_request('albums/%s' % album_id, ret='album')

    def get_album_tracks(self, album_id):
        return self._map_request('albums/%s/tracks' % album_id, ret='tracks')

    def get_artist(self, artist_id):
        return self._map_request('artists/%s' % artist_id, ret='artist')

    def get_artist_albums(self, artist_id):
        return self._map_request('artists/%s/albums' % artist_id, ret='albums')

    def get_artist_albums_ep_singles(self, artist_id):
        params = {'filter': 'EPSANDSINGLES'}
        return self._map_request('artists/%s/albums' % artist_id, params, ret='albums')

    def get_artist_albums_other(self, artist_id):
        params = {'filter': 'COMPILATIONS'}
        return self._map_request('artists/%s/albums' % artist_id, params, ret='albums')

    def get_artist_top_tracks(self, artist_id):
        return self._map_request('artists/%s/toptracks' % artist_id, ret='tracks')

    def get_artist_bio(self, artist_id):
        return self.request('GET', 'artists/%s/bio' % artist_id).json()['text']

    def get_artist_similar(self, artist_id):
        return self._map_request('artists/%s/similar' % artist_id, ret='artists')

    def get_artist_radio(self, artist_id):
        return self._map_request('artists/%s/radio' % artist_id, params={'limit': 200}, ret='tracks')

    def get_featured(self):
        items = self.request('GET', 'promotions').json()['items']
        return [_parse_featured_playlist(item) for item in items if item['type'] == 'PLAYLIST']

    def get_featured_items(self, content_type, group):
        return self._map_request('/'.join(['featured', group, content_type]), ret=content_type)

    def get_moods(self):
        return list(map(_parse_moods, self.request('GET', 'moods').json()))

    def get_mood_playlists(self, mood_id):
        return self._map_request('/'.join(['moods', mood_id, 'playlists']), ret='playlists')

    def get_genres(self):
        return list(map(_parse_genres, self.request('GET', 'genres').json()))

    def get_genre_items(self, genre_id, content_type):
        return self._map_request('/'.join(['genres', genre_id, content_type]), ret=content_type)

    def get_track_radio(self, track_id):
        return self._map_request('tracks/%s/radio' % track_id, params={'limit': 200}, ret='tracks')

    def get_track(self, track_id):
        return self._map_request('tracks/%s' % track_id, ret='track')

    def _map_request(self, url, params=None, ret=None):
        json_obj = self.request('GET', url, params).json()
        parse = None
        if ret.startswith('artist'):
            parse = _parse_artist
        elif ret.startswith('album'):
            parse = _parse_album
        elif ret.startswith('track'):
            parse = _parse_track
        elif ret.startswith('user'):
            raise NotImplementedError()
        elif ret.startswith('playlist'):
            parse = _parse_playlist

        items = json_obj.get('items')
        if items is None:
            return parse(json_obj)
        elif len(items) > 0 and 'item' in items[0]:
            return list(map(parse, [item['item'] for item in items]))
        else:
            return list(map(parse, items))

    def get_media_url(self, track_id):
        params = {'soundQuality': self._config.quality}
        r = self.request('GET', 'tracks/%s/streamUrl' % track_id, params)
        return r.json()['url']

    def search(self, field, value):
        params = {
            'query': value,
            'limit': 200,
        }
        if field not in ['artist', 'album', 'playlist', 'track']:
            raise ValueError('Unknown field \'%s\'' % field)

        ret_type = field + 's'
        url = 'search/' + field + 's'
        result = self._map_request(url, params, ret=ret_type)
        return SearchResult(**{ret_type: result})


def _parse_artist(json_obj):
    artist = Artist(id=json_obj['id'], name=json_obj['name'])
    return artist


def _parse_artists(json_obj):
    return list(map(_parse_artist, json_obj))


def _parse_album(json_obj, artist=None, artists=None):
    if artist is None:
        artist = _parse_artist(json_obj['artist'])
    if artists is None:
        artists = _parse_artists(json_obj['artists'])
    kwargs = {
        'id': json_obj['id'],
        'name': json_obj['title'],
        'num_tracks': json_obj.get('numberOfTracks'),
        'duration': json_obj.get('duration'),
        'artist': artist,
        'artists': artists,
    }
    if 'releaseDate' in json_obj:
        try:
            # Keep this as a string else we fail to json-reserialize it later
            kwargs['release_date'] = json_obj['releaseDate']
            #kwargs['release_date'] = datetime.datetime(*map(int, json_obj['releaseDate'].split('-')))
        except ValueError:
            pass
    return Album(**kwargs)


def _parse_featured_playlist(json_obj):
    kwargs = {
        'id': json_obj['artifactId'],
        'name': json_obj['header'],
        'description': json_obj['text'],
    }
    return Playlist(**kwargs)


def _parse_playlist(json_obj):
    kwargs = {
        'id': json_obj['uuid'],
        'name': json_obj['title'],
        'description': json_obj['description'],
        'num_tracks': int(json_obj['numberOfTracks']),
        'duration': int(json_obj['duration']),
        'is_public': json_obj['publicPlaylist'],
        #TODO 'creator': _parse_user(json_obj['creator']),
    }
    return Playlist(**kwargs)


def _parse_track(json_obj):
    artist = _parse_artist(json_obj['artist'])
    artists = _parse_artists(json_obj['artists'])
    album = _parse_album(json_obj['album'], artist, artists)
    kwargs = {
        'id': json_obj['id'],
        'name': json_obj['title'],
        'duration': json_obj['duration'],
        'track_num': json_obj['trackNumber'],
        'disc_num': json_obj['volumeNumber'],
        'popularity': json_obj['popularity'],
        'artist': artist,
        'artists': artists,
        'album': album,
        'available': bool(json_obj['streamReady']),
    }
    return Track(**kwargs)


def _parse_genres(json_obj):
    image = "http://resources.wimpmusic.com/images/%s/460x306.jpg" \
            % json_obj['image'].replace('-', '/')
    return Category(id=json_obj['path'], name=json_obj['name'], image=image)


def _parse_moods(json_obj):
    image = "http://resources.wimpmusic.com/images/%s/342x342.jpg" \
            % json_obj['image'].replace('-', '/')
    return Category(id=json_obj['path'], name=json_obj['name'], image=image)


class Favorites(object):

    def __init__(self, session, user_id):
        self._session = session
        self._base_url = 'users/%s/favorites' % user_id

    def add_artist(self, artist_id):
        return self._session.request('POST', self._base_url + '/artists', data={'artistId': artist_id}).ok

    def add_album(self, album_id):
        return self._session.request('POST', self._base_url + '/albums', data={'albumId': album_id}).ok

    def add_track(self, track_id):
        return self._session.request('POST', self._base_url + '/tracks', data={'trackId': track_id}).ok

    def remove_artist(self, artist_id):
        return self._session.request('DELETE', self._base_url + '/artists/%s' % artist_id).ok

    def remove_album(self, album_id):
        return self._session.request('DELETE', self._base_url + '/albums/%s' % album_id).ok

    def remove_track(self, track_id):
        return self._session.request('DELETE', self._base_url + '/tracks/%s' % track_id).ok

    def artists(self):
        return self._session._map_request(self._base_url + '/artists', ret='artists')

    def albums(self):
        return self._session._map_request(self._base_url + '/albums', ret='albums')

    def playlists(self):
        return self._session._map_request(self._base_url + '/playlists', ret='playlists')

    def tracks(self):
        r = self._session.request('GET', self._base_url + '/tracks')
        return [_parse_track(item['item']) for item in r.json()['items']]


class User(object):

    favorites = None

    def __init__(self, session, user_id, subscription_type=SubscriptionType.hifi):
        self._session = session
        self.id = user_id
        self.favorites = Favorites(session, self.id)
        
    def playlists(self):
        return self._session.get_user_playlists(self.id)
