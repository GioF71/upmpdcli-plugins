'''
    qobuz.api.raw
    ~~~~~~~~~~~~~

    Our base api, all method are mapped like in <endpoint>_<method>
    see Qobuz API on GitHub (https://github.com/Qobuz/api-documentation)

    :part_of: xbmc-qobuz
    :copyright: (c) 2012 by Joachim Basmaison, Cyril Leclerc
    :license: GPLv3, see LICENSE for more details.
'''
import sys
import time
import math
import hashlib
import socket
import binascii
from itertools import cycle
import requests
from . import spoofbuz

socket.timeout = 5

_loglevel = 3
def debug(s):
    if _loglevel >= 4:
        print("%s" %s, file=sys.stderr)
def warn(s):
    if _loglevel >= 3:
        print("%s" %s, file=sys.stderr)

class RawApi(object):

    def __init__(self, appid, configvalue):
        if appid and configvalue:
            self.configvalue = configvalue
            self.appid = appid
            self.__set_s4()
        else:
            self.spoofer = spoofbuz.Spoofer()
            self.appid = self.spoofer.getAppId()
            
        self.version = '0.2'
        self.baseUrl = 'https://www.qobuz.com/api.json/'
        self.user_auth_token = None
        self.user_id = None
        self.error = None
        self.status_code = None
        self._baseUrl = self.baseUrl + self.version
        self.session = requests.Session()
        self.error = None

    def _api_error_string(self, request, url='', params={}, json=''):
        return '{reason} (code={status_code})\n' \
                'url={url}\nparams={params}' \
                '\njson={json}'.format(reason=request.reason, status_code=self.status_code,
                                       url=url,
                                       params=str(['%s: %s' % (k, v) for k, v in params.items() ]),
                                       json=str(json))

    def _check_ka(self, ka, mandatory, allowed=[]):
        '''Checking parameters before sending our request
        - if mandatory parameter is missing raise error
        - if a given parameter is neither in mandatory or allowed
        raise error
        '''
        for label in mandatory:
            if not label in ka:
                raise Exception("Qobuz: missing parameter [%s]" % label)
        for label in ka:
            if label not in mandatory and label not in allowed:
                raise Exception("Qobuz: invalid parameter [%s]" % label)
        # Having no parameters set triggers a problem in the pyrequests/Qobuz dialog, don't know
        # where the bug is, but it results in a 411 (length required). So set a very high limit if
        # nothing is set
        noparams=True
        for label in ka:
            if ka[label]:
                noparams=False
                break
        if noparams:
            ka['limit'] = '10000'
        
    def __set_s4(self):
        '''appid and associated secret is for this app usage only
        Any use of the API implies your full acceptance of the
        General Terms and Conditions
        (http://www.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf)
        '''
        s3b = self.configvalue.encode('ASCII')
        s3s = binascii.a2b_base64(s3b)
        bappid = self.appid.encode('ASCII')
        a = cycle(bappid)
        b = zip(s3s, a)
        self.s4 = b''.join((x ^ y).to_bytes(1, byteorder='big') for (x, y) in b)
        #print("S4: %s"% self.s4.decode('ASCII'), file=sys.stderr)
        
    def __unset_s4(self, id, sec):
        a = cycle(id)
        b = zip(sec, a)
        bs4 = b''.join((x ^ y).to_bytes(1, byteorder='big') for (x, y) in b)
        value = binascii.b2a_base64(bs4)
        return value

    def _api_request(self, params, uri, **opt):
        '''Qobuz API HTTP get request
            Arguments:
            params:    parameters dictionary
            uri   :    service/method
            opt   :    Optionnal named parameters
                        - noToken=True/False

            Return None if something went wrong
            Return raw data from qobuz on success as dictionary

            * on error you can check error and status_code

            Example:

                ret = api._api_request({'username':'foo',
                                  'password':'bar'},
                                 'user/login', noToken=True)
                print('Error: %s [%s]' % (api.error, api.status_code))

            This should produce something like:
            Error: [200]
            Error: Bad Request [400]
        '''
        self.error = ''
        self.status_code = None
        url = self._baseUrl + uri
        useToken = False if (opt and 'noToken' in opt) else True
        headers = {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0"
        }
        if useToken and self.user_auth_token:
            headers['X-User-Auth-Token'] = self.user_auth_token
        headers['X-App-Id'] = self.appid
        r = None
        debug("POST %s params %s headers %s" % (url, params, headers))
        try:
            r = self.session.post(url, data=params, headers=headers)
        except:
            self.error = 'Post request fail'
            warn(self.error)
            return None
        debug(f"status_code: {r.status_code}\nheaders: {r.headers}\ncontent: {r.content}")
        self.status_code = int(r.status_code)
        if self.status_code != 200:
            self.error = self._api_error_string(r, url, params)
            warn(self.error)
            return None
        if not r.content:
            self.error = 'Request return no content'
            warn(self.error)
            return None

        '''Retry get if connexion fail'''
        try:
            response_json = r.json()
        except Exception as e:
            warn('Json loads failed to load... retrying!\n{}', repr(e))
            try:
                response_json = r.json()
            except:
                self.error = "Failed to load json two times...abort"
                warn(self.error)
                return None
        status = None
        try:
            status = response_json['status']
        except:
            pass
        if status == 'error':
            self.error = self._api_error_string(r, url, params,
                                                response_json)
            warn(self.error)
            return None
        return response_json

    def set_user_data(self, user_id, user_auth_token):
        if not (user_id and user_auth_token):
            raise Exception("Qobuz: missing argument uid|token")
        self.logged_on = time.time()

    def logout(self):
        self.user_auth_token = None
        self.user_id = None
        self.logged_on = None

    def user_login(self, **ka):
        self._check_ka(ka, ['username', 'password'], ['email'])
        data = self._api_request(ka, '/user/login', noToken=True)
        if not data or not 'user' in data or not 'credential' in data['user'] \
           or not 'id' in data['user'] \
           or not 'parameters' in data['user']['credential']:
            warn("/user/login returns %s" % data)
            self.logout()
            return None
        if not data["user"]["credential"]["parameters"]:
            warn("Free accounts are not eligible to download tracks.")
            return None
        self.user_id = data['user']['id']
        self.user_auth_token = data["user_auth_token"]
        self.label = data["user"]["credential"]["parameters"]["short_label"]
        debug("Membership: {}".format(self.label))
        data['user']['email'] = ''
        data['user']['firstname'] = ''
        data['user']['lastname'] = ''
        self.setSec()
        return data

    def setSec(self):
        global _loglevel
        savedlevel = _loglevel
        _loglevel = 1
        for value in self.spoofer.getSecrets().values():
            self.s4 = value.encode('utf-8')
            if self.userlib_getAlbums(sec=self.s4) is not None:
                #debug("SECRET [%s]"%self.s4)
                _loglevel = savedloglevel
                return

    def user_update(self, **ka):
        self._check_ka(ka, [], ['player_settings'])
        return self._api_request(ka, '/user/update')

    def track_get(self, **ka):
        self._check_ka(ka, ['track_id'])
        return self._api_request(ka, '/track/get')

    def track_getFileUrl(self, intent="stream", **ka):
        self._check_ka(ka, ['format_id', 'track_id'])
        ts = str(time.time())
        track_id = str(ka['track_id'])
        fmt_id = str(ka['format_id'])
        stringvalue = 'trackgetFileUrlformat_id' + fmt_id \
                      + 'intent' + intent \
                      + 'track_id' + track_id + ts
        stringvalue = stringvalue.encode('ASCII')
        stringvalue  += self.s4
        rq_sig = str(hashlib.md5(stringvalue).hexdigest())
        params = {'format_id': fmt_id,
                  'intent': intent,
                  'request_ts': ts,
                  'request_sig': rq_sig,
                  'track_id': track_id
                  }
        return self._api_request(params, '/track/getFileUrl')

    def userlib_getAlbums(self, **ka):
        ts = str(time.time())
        r_sig = "userLibrarygetAlbumsList" + str(ts) + str(ka["sec"])
        r_sig_hashed = hashlib.md5(r_sig.encode("utf-8")).hexdigest()
        params = {
            "app_id": self.appid,
            "user_auth_token": self.user_auth_token,
            "request_ts": ts,
            "request_sig": r_sig_hashed,
        }
        return self._api_request(params, '/userLibrary/getAlbumsList')

    def track_search(self, **ka):
        self._check_ka(ka, ['query'], ['limit'])
        return self._api_request(ka, '/track/search')

    def catalog_search(self, **ka):
        # type may be 'tracks', 'albums', 'artists' or 'playlists'
        self._check_ka(ka, ['query'], ['type', 'offset', 'limit'])
        return self._api_request(ka, '/catalog/search')

    def catalog_getFeatured(self, **ka):
        return self._api_request(ka, '/catalog/getFeatured')

    def catalog_getFeaturedTypes(self, **ka):
        return self._api_request(ka, '/catalog/getFeaturedTypes')
    
    def track_resportStreamingStart(self, track_id):
        # Any use of the API implies your full acceptance
        # of the General Terms and Conditions
        # (http://www.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf)
        params = {'user_id': self.user_id, 'track_id': track_id}
        return self._api_request(params, '/track/reportStreamingStart')

    def track_resportStreamingEnd(self, track_id, duration):
        duration = math.floor(int(duration))
        if duration < 5:
            warn(self, 'Duration lesser than 5s, abort reporting')
            return None
        # @todo ???
        user_auth_token = ''  # @UnusedVariable
        try:
            user_auth_token = self.user_auth_token  # @UnusedVariable
        except:
            warn('No authentification token')
            return None
        params = {'user_id': self.user_id,
                  'track_id': track_id,
                  'duration': duration
                  }
        return self._api_request(params, '/track/reportStreamingEnd')

    def album_get(self, **ka):
        self._check_ka(ka, ['album_id'])
        return self._api_request(ka, '/album/get')

    def album_getFeatured(self, **ka):
        self._check_ka(ka, [], ['type', 'genre_id', 'limit', 'offset'])
        return self._api_request(ka, '/album/getFeatured')

    def purchase_getUserPurchases(self, **ka):
        self._check_ka(ka, [], ['order_id', 'order_line_id', 'flat', 'limit',
                                'offset'])
        return self._api_request(ka, '/purchase/getUserPurchases')

    def search_getResults(self, **ka):
        self._check_ka(ka, ['query', 'type'], ['limit', 'offset'])
        return self._api_request(ka, '/search/getResults')

    def favorite_getUserFavorites(self, **ka):
        self._check_ka(ka, [], ['user_id', 'type', 'limit', 'offset'])
        return self._api_request(ka, '/favorite/getUserFavorites')

    def favorite_create(self, **ka):
        mandatory = ['artist_ids', 'album_ids', 'track_ids']
        found = None
        for label in mandatory:
            if label in ka:
                found = label
        if not found:
           raise Exception("Qobuz: missing parameter: artist_ids|albums_ids|track_ids")
        return self._api_request(ka, '/favorite/create')

    def favorite_delete(self, **ka):
        mandatory = ['artist_ids', 'album_ids', 'track_ids']
        found = None
        for label in mandatory:
            if label in ka:
                found = label
        if not found:
            raise Exception("Qobuz: missing parameter: artist_ids|albums_ids|track_ids")
        return self._api_request(ka, '/favorite/delete')

    def playlist_get(self, **ka):
        self._check_ka(ka, ['playlist_id'], ['extra', 'limit', 'offset'])
        return self._api_request(ka, '/playlist/get')

    def playlist_getFeatured(self, **ka):
        # type is 'last-created' or 'editor-picks'
        self._check_ka(ka, ['type'], ['genre_id', 'limit', 'offset'])
        return self._api_request(ka, '/playlist/getFeatured')

    def playlist_getUserPlaylists(self, **ka):
        self._check_ka(ka, [], ['user_id', 'username', 'order', 'offset', 'limit'])
        if not 'user_id' in ka and not 'username' in ka:
            ka['user_id'] = self.user_id
        return self._api_request(ka, '/playlist/getUserPlaylists')

    def playlist_addTracks(self, **ka):
        self._check_ka(ka, ['playlist_id', 'track_ids'])
        return self._api_request(ka, '/playlist/addTracks')

    def playlist_deleteTracks(self, **ka):
        self._check_ka(ka, ['playlist_id'], ['playlist_track_ids'])
        return self._api_request(ka, '/playlist/deleteTracks')

    def playlist_subscribe(self, **ka):
        self._check_ka(ka, ['playlist_id'], ['playlist_track_ids'])
        return self._api_request(ka, '/playlist/subscribe')

    def playlist_unsubscribe(self, **ka):
        self._check_ka(ka, ['playlist_id'])
        return self._api_request(ka, '/playlist/unsubscribe')

    def playlist_create(self, **ka):
        self._check_ka(ka, ['name'], ['is_public',
                                      'is_collaborative', 'tracks_id', 'album_id'])
        if not 'is_public' in ka:
            ka['is_public'] = True
        if not 'is_collaborative' in ka:
            ka['is_collaborative'] = False
        return self._api_request(ka, '/playlist/create')

    def playlist_delete(self, **ka):
        self._check_ka(ka, ['playlist_id'])
        return self._api_request(ka, '/playlist/delete')

    def playlist_update(self, **ka):
        self._check_ka(ka, ['playlist_id'], ['name', 'description',
                                             'is_public', 'is_collaborative', 'tracks_id'])
        return self._api_request(ka, '/playlist/update')

    def playlist_getPublicPlaylists(self, **ka):
        self._check_ka(ka, [], ['type', 'limit', 'offset'])
        return self._api_request(ka, '/playlist/getPublicPlaylists')

    def artist_getSimilarArtists(self, **ka):
        self._check_ka(ka, ['artist_id'], ['limit', 'offset'])
        return self._api_request(ka, '/artist/getSimilarArtists')

    def artist_get(self, **ka):
        self._check_ka(ka, ['artist_id'], ['extra', 'limit', 'offset'])
        return self._api_request(ka, '/artist/get')

    def genre_list(self, **ka):
        self._check_ka(ka, [], ['parent_id', 'limit', 'offset'])
        return self._api_request(ka, '/genre/list')

    def label_list(self, **ka):
        self._check_ka(ka, [], ['limit', 'offset'])
        return self._api_request(ka, '/label/list')

    def article_listRubrics(self, **ka):
        self._check_ka(ka, [], ['extra', 'limit', 'offset'])
        return self._api_request(ka, '/article/listRubrics')

    def article_listLastArticles(self, **ka):
        self._check_ka(ka, [], ['rubric_ids', 'offset', 'limit'])
        return self._api_request(ka, '/article/listLastArticles')

    def article_get(self, **ka):
        self._check_ka(ka, ['article_id'])
        return self._api_request(ka, '/article/get')

    def collection_getAlbums(self, **ka):
        self._check_ka(ka, [], ['source', 'artist_id', 'query',
                                'limit', 'offset'])
        return self._api_request(ka, '/collection/getAlbums')

    def collection_getArtists(self, **ka):
        self._check_ka(ka, [], ['source', 'query',
                                'limit', 'offset'])
        return self._api_request(ka, '/collection/getArtists')

    def collection_getTracks(self, **ka):
        self._check_ka(ka, [], ['source', 'artist_id', 'album_id', 'query',
                                'limit', 'offset'])
        return self._api_request(ka, '/collection/getTracks')
