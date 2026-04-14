"""
    qobuz.api.raw
    ~~~~~~~~~~~~~

    Our base api, all method are mapped like in <endpoint>_<method>
    see Qobuz API on GitHub (https://github.com/Qobuz/api-documentation)

    :part_of: xbmc-qobuz
    :copyright: (c) 2012 by Joachim Basmaison, Cyril Leclerc
    :license: GPLv3, see LICENSE for more details.

    login_with_oauth_code(self, code) was copied from
    https://github.com/paulborile/qobuz-dl/tree/bug/newauth
    License: GPL-3.0
"""

import sys
import time
import math
import hashlib
import requests

try:
    import bundle
except:
    from qobuz.api import bundle

_loglevel = 3
def debug(s):
    if _loglevel >= 4:
        print("%s" % s, file=sys.stderr)
def warn(s):
    if _loglevel >= 3:
        print("%s" % s, file=sys.stderr)


class RawApi(object):

    def __init__(self):
        jsparse = bundle.Bundle()
        self.appid = jsparse.get_app_id()
        self.secrets = [
            secret for secret in jsparse.get_secrets().values() if secret
        ]
        self.private_key = jsparse.get_private_key()

        self.version = "0.2"
        self.user_auth_token = None
        self.user_id = None
        self.error = None
        self.status_code = None
        self.baseUrl = "https://www.qobuz.com/api.json/" + self.version
        self.session = requests.Session()
        self.error = None

    def _api_error_string(self, request, url="", params={}, json=""):
        return (
            "{reason} (code={status_code})\n"
            "url={url}\nparams={params}"
            "\njson={json}".format(
                reason=request.reason,
                status_code=self.status_code,
                url=url,
                params=str(["%s: %s" % (k, v) for k, v in params.items()]),
                json=str(json),
            )
        )

    def _check_ka(self, ka, mandatory, allowed=[]):
        """Checking parameters before sending our request
        - if mandatory parameter is missing raise error
        - if a given parameter is neither in mandatory or allowed
        raise error
        """
        for label in mandatory:
            if not label in ka:
                raise Exception("Qobuz: missing parameter [%s]" % label)
        for label in ka:
            if label not in mandatory and label not in allowed:
                raise Exception("Qobuz: invalid parameter [%s]" % label)
        # Having no parameters set triggers a problem in the pyrequests/Qobuz dialog, don't know
        # where the bug is, but it results in a 411 (length required). So set a very high limit if
        # nothing is set
        noparams = True
        for label in ka:
            if ka[label]:
                noparams = False
                break
        if noparams:
            ka["limit"] = "10000"


    def _api_request(self, params, uri, **opt):
        """Qobuz API HTTP get request
        Arguments:
        params:    parameters dictionary
        uri   :    service/method
        opt   :    Optional named parameters
                    - noToken=True/False
                    - useGet=True/False

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
        """
        self.error = ""
        self.status_code = None
        url = self.baseUrl + uri
        useToken = False if (opt and "noToken" in opt) else True
        useGet = True if (opt and "useGet" in opt) else False
        headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0"
        }
        if useToken and self.user_auth_token:
            headers["X-User-Auth-Token"] = self.user_auth_token
        headers["X-App-Id"] = self.appid
        params.update({"app_id": self.appid})
        r = None
        op = "GET" if useGet else "POST"
        # warn(f"{op} {url} params {params} headers {headers}")
        debug(f"{op} {url} params {params}")
        try:
            if useGet:
                r = self.session.get(url, params=params, headers=headers)
            else:
                r = self.session.post(url, data=params, headers=headers)
        except:
            self.error = "Post request fail"
            warn(self.error)
            return None
        debug(f"status_code: {r.status_code}\nheaders: {r.headers}\ncontent: {r.content}")
        self.status_code = int(r.status_code)
        if self.status_code != 200:
            self.error = self._api_error_string(r, url, params)
            warn(self.error)
            return None
        if not r.content:
            self.error = "Request return no content"
            warn(self.error)
            return None

        """Retry get if connexion fail"""
        try:
            response_json = r.json()
        except Exception as e:
            warn("Json loads failed to load... retrying!\n{}", repr(e))
            try:
                response_json = r.json()
            except:
                self.error = "Failed to load json two times...abort"
                warn(self.error)
                return None
        status = None
        try:
            status = response_json["status"]
        except:
            pass
        if status == "error":
            self.error = self._api_error_string(r, url, params, response_json)
            warn(self.error)
            return None
        return response_json

    def logout(self):
        self.user_auth_token = None
        self.user_id = None
        self.logged_on = None

    def user_login(self, **ka):
        self._check_ka(ka, ["user_id", "user_auth_token"])
        data = self._api_request(ka, "/user/login", noToken=True)
        if (not data or not "user" in data or not "credential" in data["user"]
            or not "id" in data["user"] or not "parameters" in data["user"]["credential"]):
            warn("/user/login returns %s" % data)
            self.logout()
            return None
        if not data["user"]["credential"]["parameters"]:
            warn("Free accounts are not eligible to download tracks.")
            return None
        self.user_id = data["user"]["id"]
        self.user_auth_token = data["user_auth_token"]
        self.session.headers.update({"X-User-Auth-Token": self.user_auth_token})
        self.label = data["user"]["credential"]["parameters"]["short_label"]
        debug("Membership: {}".format(self.label))
        data["user"]["email"] = ""
        data["user"]["firstname"] = ""
        data["user"]["lastname"] = ""
        self.setSec()
        return data


    # Initial login after browser-based fetching of oauth code which we exchange for a user token
    def login_with_oauth_code(self, code):
        # Step 1: Exchange code for token via /oauth/callback
        callback_url = self.baseUrl + "/oauth/callback"
        params = {
            "code": code,
            "private_key": self.private_key,
            "app_id": self.appid,
        }
        r = self.session.get(callback_url, params=params)
        r.raise_for_status()
        json_resp = r.json()
        token = json_resp.get("token")
        if not token:
            warn("No token in OAuth callback response")
            return None
        self.user_auth_token = token

        # Step 2: GET /user/login with X-User-Auth-Token to fetch full profile
        debug(f"login_with_oauth_code: got user token {self.user_auth_token}")
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0",
                "X-App-Id": self.appid,
                "Content-Type": "application/json;charset=UTF-8",
                "X-User-Auth-Token": self.user_auth_token
            }
        )
        login_url = self.baseUrl + "/user/login"
        r = self.session.post(
            login_url,
            headers={"Content-Type": "text/plain;charset=UTF-8"},
            data="extra=partner"
        )
        if r.status_code == 401:
            warn("OAuth token rejected")
            return None
        r.raise_for_status()
        usr_info = r.json()
        if not usr_info["user"]["credential"]["parameters"]:
            warn("Free accounts are not eligible to download tracks.")
            return None
        self.label = usr_info["user"]["credential"]["parameters"]["short_label"]
        debug(f"Membership: {self.label}")
        self.setSec()
        return usr_info


    def setSec(self):
        global _loglevel
        savedloglevel = _loglevel
        _loglevel = 1
        for value in self.secrets:
            self.secret = value.encode("utf-8")
            if self.userlib_getAlbums(sec=self.secret) is not None:
                # debug("SECRET [%s]"%self.secret)
                _loglevel = savedloglevel
                return
        _loglevel = savedloglevel


    def track_get(self, **ka):
        self._check_ka(ka, ["track_id"])
        return self._api_request(ka, "/track/get")


    def track_getFileUrl(self, intent="stream", **ka):
        self._check_ka(ka, ["format_id", "track_id"])
        ts = str(time.time())
        track_id = str(ka["track_id"])
        fmt_id = str(ka["format_id"])
        stringvalue = (
            "trackgetFileUrlformat_id" + fmt_id + "intent" + intent + "track_id" + track_id + ts
        )
        stringvalue = stringvalue.encode("ASCII")
        stringvalue += self.secret
        rq_sig = str(hashlib.md5(stringvalue).hexdigest())
        params = {
            "format_id": fmt_id,
            "intent": intent,
            "request_ts": ts,
            "request_sig": rq_sig,
            "track_id": track_id,
        }
        return self._api_request(params, "/track/getFileUrl")

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
        return self._api_request(params, "/userLibrary/getAlbumsList")

    # Currently unused. Check that it works ?
    def track_search(self, **ka):
        self._check_ka(ka, ["query"], ["limit"])
        return self._api_request(ka, "/track/search")

    def album_get(self, **ka):
        self._check_ka(ka, ["album_id"], ["extra", "limit", "offset"])
        # As of around sept 2024, using a POST for this does not work any more (always return the
        # same album, not the one requested. Probably an inadvertant change on the Qobuz side. The
        # WEB player uses a GET
        return self._api_request(ka, "/album/get", useGet=True)

    def album_getFeatured(self, **ka):
        self._check_ka(ka, [], ["type", "genre_ids", "limit", "offset"])
        return self._api_request(ka, "/album/getFeatured", useGet=True)

    def favorite_getUserFavorites(self, **ka):
        self._check_ka(ka, [], ["user_id", "type", "limit", "offset"])
        return self._api_request(ka, "/favorite/getUserFavorites")

    def playlist_get(self, **ka):
        self._check_ka(ka, ["playlist_id"], ["extra", "limit", "offset"])
        return self._api_request(ka, "/playlist/get", useGet=True)

    def playlist_getFeatured(self, **ka):
        # type is 'last-created' or 'editor-picks'
        self._check_ka(ka, ["type"], ["genre_ids", "tags", "limit", "offset"])
        for k in ("tags", "genre_ids"):
            if k in ka and ka[k] == "None":
                del ka[k]
        return self._api_request(ka, "/playlist/getFeatured", useGet=True)

    def playlist_getUserPlaylists(self, **ka):
        self._check_ka(ka, [], ["user_id", "username", "order", "offset", "limit"])
        if not "user_id" in ka and not "username" in ka:
            ka["user_id"] = self.user_id
        return self._api_request(ka, "/playlist/getUserPlaylists")

    def artist_getSimilarArtists(self, **ka):
        self._check_ka(ka, ["artist_id"], ["limit", "offset"])
        return self._api_request(ka, "/artist/getSimilarArtists", useGet=True)

    def artist_get(self, **ka):
        self._check_ka(ka, ["artist_id"], ["extra", "limit", "offset"])
        return self._api_request(ka, "/artist/get", useGet=True)

    def genre_list(self, **ka):
        self._check_ka(ka, [], ["parent_id", "limit", "offset"])
        return self._api_request(ka, "/genre/list")

    def label_list(self, **ka):
        self._check_ka(ka, [], ["limit", "offset"])
        return self._api_request(ka, "/label/list")

    def catalog_search(self, **ka):
        # type may be 'tracks', 'albums', 'artists' or 'playlists'
        self._check_ka(ka, ["query"], ["type", "offset", "limit"])
        return self._api_request(ka, "/catalog/search", useGet=True)

    #### 2024-10 Except for search the /catalog/ methods still work but they're not used by the site
    #### afaics, replaced by /albums/getFeatured, /playlists/getFeatured
    def catalog_getFeatured(self, **ka):
        return self._api_request(ka, "/catalog/getFeatured")

    def catalog_getFeaturedTypes(self, **ka):
        return self._api_request(ka, "/catalog/getFeaturedTypes")


if __name__ == "__main__":
    api = RawApi()
    
    
