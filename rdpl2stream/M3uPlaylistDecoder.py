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

class M3uPlaylistDecoder:
    def __init__(self):
        self.log = logging.getLogger('upmpdcli')


    def isStreamValid(self, contentType, firstBytes):
        if 'audio/mpegurl' in contentType or 'audio/x-mpegurl' in contentType:
            self.log.info('Stream is readable by M3U Playlist Decoder')
            return True
        else:
            lines = firstBytes.splitlines()
            for line in lines:
                if line.startswith(b"http://"):
                    return True
        return False


    def extractPlaylist(self,  url):
        self.log.info('M3u: downloading playlist...')
        req = UrlRequest(url)
        req.add_header('User-Agent', USER_AGENT)
        f = urlUrlopen(req)
        str = f.read()
        f.close()

        self.log.info('M3U: playlist downloaded, decoding... ')

        lines = str.splitlines()
        playlist = []

        for line in lines:
            if line.startswith(b"#") == False and len(line) > 0:
                playlist.append(line)

        return playlist
