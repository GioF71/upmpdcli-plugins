'''
    Interface to highresaudio WEB API
'''
import sys
from time import time
import math
import hashlib
import binascii
from upmplgutils import *
import requests
import json

#import logging
#import http.client as http_client
#http_client.HTTPConnection.debuglevel = 1
#logging.basicConfig(stream=sys.stderr)
#logging.getLogger().setLevel(logging.DEBUG)
#requests_log = logging.getLogger("requests.packages.urllib3")
#requests_log.setLevel(logging.DEBUG)
#requests_log.propagate = True

class MLog(object):
    def __init__(self):
        self.f = sys.stderr
        self.level = 2
    def _doprint(self, msg):
        print("HRAAPI: %s" % msg, file=self.f)
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

class HRAAPI(object):

    def __init__(self):
        self.appid = '285473059'  # XBMC
        self.apiUrl = 'https://streaming.highresaudio.com:8182/vault3'
        self.session_id = None
        self.user_id = None
        self.user_data = None
        self.logged_on = None
        self.error = None
        self.status_code = None
        self.statContentSizeTotal = 0

        self.session = requests.Session()

    def _api_error_string(self, request, url='', params={}, json=''):
        return '{reason} (code={status_code})\n' \
                'url={url}\nparams={params}' \
                '\njson={json}'.format(
                    reason=request.reason, status_code=self.status_code,
                    url=url,
                    params=str(['%s: %s' % (k, v) for k, v in params.items() ]),
                    json=str(json))

    def _check_ka(self, ka, mandatory, allowed=[]):
        '''Checking parameters before sending our request
        - if mandatory parameter is missing raise error
        - if a given parameter is neither in mandatory or allowed
        raise error (Creating exception class like MissingParameter
        may be a good idea)
        '''
        for label in mandatory:
            if not label in ka:
                raise Exception("HRAAPI: missing parameter %s" % label)
        for label in ka:
            if label not in mandatory and label not in allowed:
                raise Exception("HRAAPI: invalid parameter %s" % label)

    def _api_request(self, iparams, uri, **opt):
        '''HighresAudio API HTTP get request
            Arguments:
            params:    parameters dictionary
            uri   :    service/method
            opt   :    Optional named parameters: method=GET/POST default GET

            Return None if something went wrong
            Return response data as dictionary on success
        '''
        self.error = ''
        self.status_code = None
        url = self.apiUrl + uri
        headers = {}
        params = {}
        dopost = False
        if 'method' in opt and opt['method'] == 'POST':
            dopost = True
        if self.user_data:
            params = {'userData' : self.user_data}
        params.update(iparams)

        log.debug('request: url {}, params: {}'.format(url, str(params)))
        r = None
        try:
            if dopost:
                r = self.session.post(url, data=params, headers=headers)
            else:
                r = self.session.get(url, params=params, headers=headers)
        except:
            self.error = 'HTTP request failed'
            log.warn(self.error)
            return None

        self.status_code = int(r.status_code)
        if self.status_code != 200:
            self.error = self._api_error_string(r, url, params)
            log.warn(self.error)
            return None
        if not r.content:
            self.error = 'Request return no content'
            log.warn(self.error)
            return None
        try:
            response_json = r.json()
        except Exception as e:
            log.warn('Json loads failed to load {}', repr(e))
        status = None
        try:
            status = response_json['response_status']
        except:
            pass
        if status != 'OK':
            self.error = self._api_error_string(r, url, params, response_json)
            log.warn(self.error)
            return None
        log.debug("HRAAPI: response: %s" % response_json)
        return response_json


    def logout(self):
        log.info("logout()")
        self._api_request({}, '/user/logout', method='POST')
        self._clear_login()


    def _renew_session(self):
        log.info("_renew_session()")
        data = self._api_request('/user/keepalive', method='POST')
        if not data or 'user_id' not in data or 'session_id' not in data or \
          not data['user_id'] or not data['session_id']:
            self.logged_on = None
            return None
        self.session_id = data['session_id']
        self.user_id = data['user_id']
        self.user_data = json.dumps({'user_id':self.user_id,
                                         'session_id':self.session_id})
        self.logged_on = time()
        return data


    def isloggedin(self):
        log.info("isloggedin(): user_id %s" % self.user_id)
        # Hra sessions expire after 30mn.
        if self.logged_on:
            now = time()
            if now - self.logged_on > 20 * 60:
                self._renew_session()
        return self.logged_on is not None
    

    def _clear_login(self):
        self.user_session_id = None
        self.user_id = None
        self.logged_on = None
        

    def user_login(self, **ka):
        self._check_ka(ka, ['username', 'password'])
        data = self._api_request(ka, '/user/login', method='POST')
        if not data or 'user_id' not in data or 'session_id' not in data or \
          not data['user_id'] or not data['session_id']:
          log.warn("login failed")
          self.clean_login()
          return None
        self.session_id = data['session_id']
        self.user_id = data['user_id']
        self.user_data = json.dumps(
            {'user_id':self.user_id, 'session_id':self.session_id})
        self.logged_on = time()
        return data


    def getAllCategories(self):
        if not self.isloggedin():
            return None
        data = self._api_request({}, '/vault/categories/ListAllCategories/')
        if not data or 'data' not in data or 'results' not in data['data']:
            return {}
        return [item[1] for item in data['data']['results'].items()]


    def getAllGenres(self):
        if not self.isloggedin():
            return None
        data = self._api_request({}, '/vault/categories/ListAllGenre')
        if not data or 'data' not in data or 'results' not in data['data']:
            return {}
        return data['data']['results']


    def listCategoryContent(self, **ka):
        if not self.isloggedin():
            return None
        self._check_ka(ka, ['category', 'limit', 'offset'])
        data = self._api_request(ka, '/vault/categories/ListCategorieContent/')
        if not data or 'data' not in data or 'results' not in data['data']:
            return {}
        return data['data']['results']


    def getAlbumDetails(self, **ka):
        if not self.isloggedin():
            return None
        self._check_ka(ka, ['album_id'])
        data = self._api_request(ka, '/vault/album/')
        if not data or 'data' not in data or 'results' not in data['data'] or \
          'tracks' not in data['data']['results']:
            return None
        return data['data']['results']
        

    def getTrackById(self, **ka):
        if not self.isloggedin():
            return None
        self._check_ka(ka, ['track_id'])
        params = ka
        data = self._api_request(params, '/vault/track/')
        if not data or 'data' not in data or 'results' not in data['data'] or \
          'tracks' not in data['data']['results']:
            return None
        return data['data']['results']['tracks']

    def quickSearch(self, **ka):
        self._check_ka(ka, ['search'])
        params = ka
        data = self._api_request(params, '/vault/search/quickSearch/')
        if not data or 'data' not in data:
            return {}
        # The data is a dict key:albumdata, the key can be used as album_id
        # with /vault/album
        return data['data']
        
    def searchCategory(self, **ka):
        self._check_ka(ka, ['search', 'category'])
        params = ka
        data = self._api_request(params, '/vault/SearchInCategory/')
        if not data or 'data' not in data or 'results' not in data['data']:
            return {}
        # The data is a dict key:albumdata, the key can be used as album_id
        # with /vault/album
        return data['data']['results']
        
    def listAllUserPlaylists(self, **ka):
        if not self.isloggedin():
            return {}
        params = ka
        return self._api_request(params, '/user/ListAllUserPlaylists')
