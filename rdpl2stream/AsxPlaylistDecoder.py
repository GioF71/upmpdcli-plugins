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
from common import USER_AGENT
import xml.etree.ElementTree as ET
from io import BytesIO
import re
import logging

class AsxPlaylistDecoder:
    def __init__(self):
        self.log = logging.getLogger('upmpdcli')


    def isStreamValid(self, contentType, firstBytes):
        if ('audio/x-ms-wax' in contentType or \
            'video/x-ms-wvx' in contentType or \
            'video/x-ms-asf' in contentType or \
            'video/x-ms-wmv' in contentType) and \
            firstBytes.strip().lower().startswith(b'<asx'):
            self.log.info('Stream is readable by ASX Playlist Decoder')
            return True
        else:
            return False

        
    def extractPlaylist(self,  url):
        self.log.info('ASX: Downloading playlist...')

        req = UrlRequest(url)
        req.add_header('User-Agent', USER_AGENT)
        f = urlUrlopen(req)
        str = f.read()
        f.close()

        self.log.info('ASX: playlist downloaded, decoding...')

        try:
            root = ET.parse(BytesIO(str))
        except:
            # Last ditch: try to fix docs with mismatched tag name case
            str = re.sub('''<([A-Za-z0-9/]+)''', \
                         lambda m: "<" + m.group(1).lower(),
                         str)
            root = ET.parse(BytesIO(str))
            
        #ugly hack to normalize the XML
        for element in root.iter():
            tmp = element.tag
            element.tag = tmp.lower()

            keys = element.attrib.keys()
            for key in keys:
                element.attrib[key.lower()] = element.attrib[key]

        elts = root.findall(".//ref/[@href]")

        result = []
        for elt in elts:
            tmp = elt.attrib['href']
            if (tmp.endswith("?MSWMExt=.asf")):
                tmp = tmp.replace("http", "mms")
            result.append(tmp)

        return result
