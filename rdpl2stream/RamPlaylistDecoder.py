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
import logging
from common import USER_AGENT

class RamPlaylistDecoder:
    def __init__(self):
        self.log = logging.getLogger('upmpdcli')


    def isStreamValid(self, contentType, firstBytes):
        if 'audio/x-pn-realaudio' in contentType or \
           'audio/vnd.rn-realaudio' in contentType:
            self.log.info('Stream is readable by RAM Playlist Decoder')
            return True
        else:
            return False


    def extractPlaylist(self,  url):
        self.log.info('RAM: Downloading playlist...')
        req = UrlRequest(url)
        req.add_header('User-Agent', USER_AGENT)
        f = urUrlopen(req)
        str = f.read()
        f.close()

        self.log.info('RAM Playlist downloaded, decoding...')

        lines = str.splitlines()
        playlist = []
        for line in lines:
            if len(line) > 0 and not line.startswith(b"#"):
                tmp = line.strip()
                if len(tmp) > 0:
                    playlist.append(line.strip())

        return playlist
