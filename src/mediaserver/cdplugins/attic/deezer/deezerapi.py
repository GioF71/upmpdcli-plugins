#
# Copyright (C) 2021 Jean-Francois Dockes
#
# A lot of code strongly inspired or copied from the Kodi Deezer API,
# https://github.com/Valentin271/DeezerKodi
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


# Deezer low level interface and session management. We return barely
# prepared json objects

##### *** NOTE: this is broken as of fall 2023. Deezer changed the "tv" host (URL updated here) and
#####     API (old one not working, no idea of new one). ***
# See https://github.com/Valentin271/DeezerKodi/issues/32

import sys
import time
import requests
import json
import hashlib

from upmplgutils import *

# For debugging the details of the HTTP transaction. Note that http.client
# logs to stdout by default, so you need to actually edit the module to log
# to stderr if you want these messages (else they mess up the communication
# with our parent).
#import logging
#import http.client as http_client
#http_client.HTTPConnection.debuglevel = 1
#logging.basicConfig(stream=sys.stderr)
#logging.getLogger().setLevel(logging.DEBUG)
#requests_log = logging.getLogger("requests.packages.urllib3")
#requests_log.setLevel(logging.DEBUG)
#requests_log.propagate = True


# Bogus logging class initially to avoid to change the qobuz module code. Could
# get rid of it here...
class MLog(object):
    def __init__(self):
        self.f = sys.stderr
        self.level = 3
    def _doprint(self, msg):
        print("DeezerAPI: %s" % msg, file=self.f)
    def debug(self, msg):
        if self.level >= 3:
            self._doprint(msg)
    def info(self, msg):
        if self.level >= 2:
            self._doprint(msg)
    def warn(self, msg):
        if self.level >= 1:
            self._doprint(msg)
log = MLog()


class DeezerAPI(object):

    def __init__(self):
        self.apiUrl = "http://api.deezer.com/2.0/{service}/{id}/{method}"
        self.streamingUrl = "https://tv2.deezer.com/smarttv/streaming.php"
        self.authUrl = "https://tv2.deezer.com/smarttv/authentication.php"
        self.username = None
        self.passmd5 = None
        self.access_token = None
        self.user_id = None
        self.error = None
        self.status_code = None
        self.session = requests.Session()

    def _check_ka(self, ka, mandatory, allowed=[]):
        for label in mandatory:
            if not label in ka:
                raise Exception("DeezerAPI: missing parameter %s" % label)
        for label in ka:
            if label not in mandatory and label not in allowed:
                raise Exception("DeezerAPI: invalid parameter %s" % label)


    def _api_request(self, service, id='', method='', params={}):
        self.error = ''
        self.status_code = None
        url = self.apiUrl.format(service=service,id=id,method=method)
        r = None
        iparams = {'output': 'json', 'access_token': self.access_token}
        params.update(iparams)
        log.info("Request: url [%s] params [%s]" % (url, params))
        time1 = time.time()
        try:
            r = self.session.get(url, params=params)
        except:
            self.error = 'HTTP request failed'
            log.warn(self.error)
            return None
        time2 = time.time()
        log.info('Request took {:.3f} ms'.format((time2-time1)*1000.0))
        log.debug("DeezerAPI: response: %s" % r.text)
        self.status_code = int(r.status_code)
        if self.status_code != 200:
            log.warn("status code !200. data: %s" % r.content)
            return None
        if not r.content:
            self.error = 'Request return no content'
            log.warn(self.error)
            return None
        js = r.json()
        if 'error' in js:
            code = js['error']['code']
            log.warn("Deezer returned error: %s" % r.content)
            # Do something if it is "need login again"
            return None
        return js

    def request_stream(self, id='', type='track'):
        response = self.session.get(self.streamingUrl, params={
            'access_token': self.access_token,
            "{}_id".format(type): id,
            'device': 'panasonic'
        })
        if type.startswith('radio') or type.startswith('artist'):
            return response.json()
        return response.text


    def isloggedin(self):
        log.debug("isloggedin(): username %s" % self.username)
        return self.access_token is not None
    

    def _clear_login(self):
        self.access_token = None
        self.user_id = None

    def user_login(self, cachedir, username, password):
        log.info("user_login")
        self.username = username
        self.passmd5 = hashlib.md5(password.encode('utf-8')).hexdigest()
        try:
            with open(os.path.join(cachedir, 'token'), "r") as f:
                self.access_token = f.read()
        except:
            data = self.session.get(self.authUrl, params={
                'login': self.username, 'password': self.passmd5,
                'device': 'panasonic'})
            log.info(f"data {data}")
            js = data.json()
            if 'access_token' not in js:
                log.warn("login failed")
                if data:
                    log.warn("deezer response %s" % data.content)
                self._clear_login()
                return False
            self.access_token = js['access_token']
            with open(os.path.join(cachedir, 'token'), "w") as f:
                 f.write(self.access_token)

        if not self.getUser():
            log.warn("getUser failed")
            return True
        return False


    def getUser(self):
        data = self._api_request('user', 'me')
        if 'id' in data:
            self.user_id = data['id']
            return True
        return False


    def getUserFollowings(self):
        if not self.isloggedin():
            return {}
        return self._api_request('user', self.user_id, 'followings')

    def getUserPlaylists(self, id='me', offset=0):
        if not self.isloggedin():
            return {}
        if id == 'me':
            id = self.user_id
        data = self._api_request('user', id, 'playlists',
                                 params={'index': offset})
        return data

    def getUserAlbums(self, id='me', offset=0):
        if not self.isloggedin():
            return {}
        if id == 'me':
            id = self.user_id
        data = self._api_request('user', id, 'albums',
                                 params={'index': offset})
        return data

    def getUserArtists(self, id='me', offset=0):
        if not self.isloggedin():
            return {}
        if id == 'me':
            id = self.user_id
        data = self._api_request('user', id, 'artists',
                                 params={'index': offset})
        return data

    def getUserTracks(self, id='me', offset=0):
        if not self.isloggedin():
            return {}
        if id == 'me':
            id = self.user_id
        data = self._api_request('user', id, 'tracks',
                                 params={'index': offset})
        return data

    def getArtistAlbums(self, artid, offset=0):
        if not self.isloggedin():
            return {}
        data = self._api_request('artist', artid, 'albums',
                                 params={'index': offset})
        return data

    def getUserPlaylist(self, id, offset=0):
        if not self.isloggedin():
            return None
        data = self._api_request('playlist', id, 'tracks',
                                 params={'index': offset})
        return data

    def search(self, query, filter, offset=0):
        if not self.isloggedin():
            return None
        data = self._api_request('search', method=filter,
                                 params={'q': query, 'index': offset})
        return data

    def getAlbum(self, id):
        data = self._api_request('album', id)
        return data
