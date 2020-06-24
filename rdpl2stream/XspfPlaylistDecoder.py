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
from urllib.request import Request as UrlRequest
from urllib.request import urlopen as urlUrlopen
import xml.etree.ElementTree as ET
from io import BytesIO
import logging
from common import USER_AGENT

class XspfPlaylistDecoder:
    def __init__(self):
        self.log = logging.getLogger('upmpdcli')

    def isStreamValid(self, contentType, firstBytes):
        if 'application/xspf+xml' in contentType:
            self.log.info('Stream is readable by XSPF Playlist Decoder')
            return True
        else:
            return False


    def extractPlaylist(self,  url):
        self.log.info('XSPF: downloading playlist...')
        req = UrlRequest(url)
        req.add_header('User-Agent', USER_AGENT)
        f = urlUrlopen(req)
        str = f.read()
        f.close()
        self.log.info('XSPF: playlist downloaded, decoding...')

        root = ET.parse(BytesIO(str))
        ns = {'xspf':'http://xspf.org/ns/0/'}
        elements = root.findall(".//xspf:track/xspf:location", ns)

        result = []
        for r in elements:
            result.append(r.text)

        return result
