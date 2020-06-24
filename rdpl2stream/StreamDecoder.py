##########################################################################
# Copyright 2009 Carlos Ribeiro
#
# This file is part of Radio Tray
#
# Radio Tray is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 1 of the License, or
# (at your option) any later version.
#
# Radio Tray is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Radio Tray.  If not, see <http://www.gnu.org/licenses/>.
#
##########################################################################
import sys
import ssl
from urllib.request import Request as UrlRequest
import urllib.request, urllib.error, urllib.parse
from urllib.error import HTTPError as HTTPError
from urllib.error import URLError as URLError
from urllib.request import HTTPRedirectHandler
from http.client import BadStatusLine as BadStatusLine
from urllib.request import build_opener as urlBuild_opener
from urllib.request import HTTPSHandler
if sys.version_info < (3,5):
    def my_ssl_create_unverified_context():
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        return ssl_ctx
else:
    my_ssl_create_unverified_context = ssl._create_unverified_context
from common import USER_AGENT
from PlsPlaylistDecoder import PlsPlaylistDecoder
from M3uPlaylistDecoder import M3uPlaylistDecoder
from AsxPlaylistDecoder import AsxPlaylistDecoder
from XspfPlaylistDecoder import XspfPlaylistDecoder
from AsfPlaylistDecoder import AsfPlaylistDecoder
from RamPlaylistDecoder import RamPlaylistDecoder
from UrlInfo import UrlInfo
import logging


class DummyMMSHandler(HTTPRedirectHandler):
    def __init__(self):
        self.log = logging.getLogger('upmpdcli')

    # Handle mms redirection, or let the standard code deal with it.
    def http_error_302(self, req, fp, code, msg, headers):
        #self.log.info("http_error_302: code %s headers %s" % (code, headers))
        if 'location' in headers:
            newurl = headers['location']
            if newurl.startswith('mms:'):
                raise URLError("MMS REDIRECT:" + headers["Location"])
        return HTTPRedirectHandler.http_error_302(self, req, fp, code,
                                                  msg, headers)

class StreamDecoder:

    def __init__(self, cfg_provider):
        plsDecoder = PlsPlaylistDecoder()
        m3uDecoder = M3uPlaylistDecoder()
        asxDecoder = AsxPlaylistDecoder()
        xspfDecoder = XspfPlaylistDecoder()
        asfDecoder = AsfPlaylistDecoder()
        ramDecoder = RamPlaylistDecoder()

        self.log = logging.getLogger('upmpdcli')
        
        self.decoders = [plsDecoder, asxDecoder, asfDecoder, xspfDecoder, ramDecoder, m3uDecoder]

        self.url_timeout = None

        try:
            self.url_timeout = cfg_provider.getConfigValue("url_timeout")
            if (self.url_timeout == None):
                self.log.warn("Couldn't find url_timeout configuration")
                self.url_timeout = 100
                cfg_provider.setConfigValue("url_timeout", str(self.url_timeout))
        except Exception as e:
            self.log.warn("Couldn't find url_timeout configuration")
            self.url_timeout = 100
            cfg_provider.setConfigValue("url_timeout", str(self.url_timeout))

        self.log.info('Using url timeout = %s'% str(self.url_timeout))


    def getMediaStreamInfo(self, url):
        if type(url) != type(u""):
            url = url.decode('utf-8')
        if url.startswith("http") == False:
            self.log.info('Not an HTTP url. Maybe direct stream...')
            return UrlInfo(url, False, None)

        self.log.info('Requesting stream... %s'% url)
        req = UrlRequest(url)
        req.add_header('User-Agent', USER_AGENT)

        try:
            opener = urlBuild_opener(
                DummyMMSHandler(),
                HTTPSHandler(context = my_ssl_create_unverified_context()))
            f = opener.open(req, timeout=float(self.url_timeout))
        except HTTPError as e:
            self.log.warn('HTTP Error for %s: %s' % (url, e))
            return None
        except URLError as e:
            self.log.info('URLError for %s: %s ' % (url, e))
            if str(e.reason).startswith('MMS REDIRECT'):
                newurl = e.reason.split("MMS REDIRECT:",1)[1]
                self.log.info('Found mms redirect for: %s' % newurl)
                return UrlInfo(newurl, False, None)
            else:
                return None
        except BadStatusLine as e:
            if str(e).startswith('ICY 200'):
                self.log.info('Found ICY stream')
                return UrlInfo(url, False, None)
            else:
                return None
        except Exception as e:
            print('%s: for %s: %s' % (type(e), url, e),file=sys.stderr)
            self.log.warn('%s: for %s: %s' % (type(e), url, e))
            return None

        metadata = f.info()
        firstbytes = f.read(500)
        f.close()

        try:            
            contentType = metadata["content-type"]
            self.log.info('Content-Type: %s'% contentType)
        except Exception as e:
            self.log.info("Couldn't read content-type. Maybe direct stream...")
            return UrlInfo(url, False, None)

        for decoder in self.decoders:
                
            self.log.info('Checking decoder')
            if decoder.isStreamValid(contentType, firstbytes):
                return UrlInfo(url, True, contentType, decoder)
            
        # no playlist decoder found. Maybe a direct stream
        self.log.info('No playlist decoder could handle the stream. Maybe direct stream...')
        return UrlInfo(url, False, contentType)
        

    def getPlaylist(self, urlInfo):
        return urlInfo.getDecoder().extractPlaylist(urlInfo.getUrl())

