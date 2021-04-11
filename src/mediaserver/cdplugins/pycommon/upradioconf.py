# Copyright (C) 2021 J.F.Dockes
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the
#   Free Software Foundation, Inc.,
#   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

import os
import subprocess

from upmplgutils import uplog, direntry
import conftree

class UpmpdcliRadios(object):
    def __init__(self, upconfig):
        datadir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if not os.path.isabs(datadir):
            datadir = "/usr/share/upmpdcli"
        self.fetchstream = os.path.join(datadir, "rdpl2stream", "fetchStream.py")
        self._radios = []
        self._readRadios(upconfig)
        #uplog("Radios: %s" % self._radios)

    def _readRadiosFromConf(self, conf):
        '''Read radio definitions from a config file (either main file or radiolist)'''
        keys = conf.getSubKeys_unsorted()
        for k in keys:
            if k.startswith("radio"):
                title = k[6:]
                uri = conf.get("url", k)
                artUri = conf.get("artUrl", k)
                streamUri = None
                try:
                    streamUri = subprocess.check_output([self.fetchstream, uri])
                    streamUri = streamUri.decode('utf-8').strip("\r\n")
                except Exception as ex:
                    uplog("fetchStream.py failed for %s: %s" % (title, ex))
                if streamUri:
                    self._radios.append((title, streamUri, uri, artUri))
        
    def _readRadios(self, upconfig):
        '''Read radio definitions from main config file, then possible radiolist'''
        self._radios = []
        self._readRadiosFromConf(upconfig)
        radiolist = upconfig.get("radiolist")
        if radiolist:
            radioconf = conftree.ConfSimple(radiolist)
            self._readRadiosFromConf(radioconf)


    def __iter__(self):
       return RadioIterator(self)


class RadioIterator:
   def __init__(self, radios):
       self._radios = radios
       self._index = 0

   def __next__(self):
       if self._index < (len(self._radios._radios)):
           radio = self._radios._radios[self._index]
           result = {"title" : radio[0], "streamUri" : radio[1],
                     "uri" : radio[2], "artUri" : radio[3]}
           self._index +=1
           return result

       raise StopIteration            


def radioToEntry(pid, idx, radio):
    id = pid + '$e' + str(idx)
    return {
        'pid': pid,
        'id': id,
        'uri': radio["streamUri"],
        'tp': 'it',
        'res:mime': "audio/mpeg",
        'upnp:class': 'object.item.audioItem.musicTrack',
        'upnp:albumArtURI': radio["artUri"],
        'tt': radio["title"]
    }


if __name__ == "__main__":
    conf = conftree.ConfSimple("/etc/upmpdcli.conf")
    radios = UpmpdcliRadios(conf)
    for radio in radios:
        print("%s" % radio)

        
