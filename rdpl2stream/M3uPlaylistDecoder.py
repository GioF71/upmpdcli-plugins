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
from urllib.parse import urljoin as urlJoin

import logging    
from common import USER_AGENT

class M3uPlaylistDecoder:
    def __init__(self):
        self.log = logging.getLogger('upmpdcli')
        #self.log.setLevel(logging.DEBUG)


    def isStreamValid(self, contentType, firstBytes):
        contentType = contentType.lower()

        # Apple live streaming special case: we do not try to process these, there is no permanent
        # media url to extract (only an ever changing list of short segments). We reject them and
        # let mpd deal with the playlist itself (which it does well, even if I could not find out by
        # looking at the code how it worked).
        if 'audio/mpegurl' in contentType or 'application/vnd.apple.mpegurl' in contentType:
            lines = firstBytes.splitlines()
            if not len(lines) or lines[0].startswith(b"#EXTM3U"):
                return False
        
        if 'audio/mpegurl' in contentType or 'audio/x-mpegurl' in contentType \
           or 'application/x-mpegurl' in contentType or \
           'application/vnd.apple.mpegurl' in contentType:
            # we tested for EXTM3U above, so this must be a regular playlist
            self.log.debug('Stream is readable by M3U Playlist Decoder')
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
                if line.startswith(b"http"):
                    playlist.append(line)
                else:
                    playlist.append(urlJoin(url.encode('utf-8'), line))

        return playlist
