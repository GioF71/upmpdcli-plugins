# Copyright (C) 2017 J.F.Dockes
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
#

from __future__ import print_function

import os
import time
import bottle
import mutagen
import re

from upmplgutils import uplog
from uprclutils import embedded_open
import uprclinit

# Checking for numeric HOST header
_hostre = re.compile('''[0-9]+\.[0-9]+\.[0-9]+\.[0-9]:[0-9]+|\[[0-9A-Fa-f:]+\]:[0-9]+''')
def _checkhost():
    if 'host' in bottle.request.headers:
        host = bottle.request.headers['host']
        if not _hostre.match(host):
            uplog("Streamer: Bad Host <%s>" % host)
            return False
    return True

@bottle.route('/')
@bottle.post('/')
@bottle.view('main')
def main():
    if not _checkhost():
        return bottle.HTTPResponse(status=404)
    what =  bottle.request.forms.get('what')
    #uplog("bottle:main: what value is %s" % what)

    status = uprclinit.updaterunning()
    if not status:
        status = 'Ready'

    reloadsecs='1'
    if what == 'Update Index':
        uprclinit.start_update()
    elif what == 'Reset Index':
        uprclinit.start_update(rebuild=True)
    elif what == 'Refresh Status':
        reloadsecs = ''
    elif not what:
        if status == 'Updating':
            reloadsecs = '2'
        elif status == 'Rebuilding':
            reloadsecs = '10'
        else:
            reloadsecs = ''

    return {'title':status, 'status':status, 'reloadsecs':reloadsecs,
            'friendlyname':uprclinit.getFriendlyname()}


@bottle.route('/static/<filepath:path>')
def static(filepath):
    #uplog("control: static: filepath %s datadir %s" % (filepath, datadir))
    if not _checkhost():
        return bottle.HTTPResponse(status=404)
    return bottle.static_file(filepath, root=os.path.join(datadir, 'static'))


# Object for streaming data from a given subtree (topdirs entry more
# or less). This is needed just because as far as I can see, a
# callback can't know the route it was called for, so we record it
# when creating the object.
class Streamer(object):
    def __init__(self, root):
        self.root = root

    def __call__(self, filepath):
        if not _checkhost():
            return bottle.HTTPResponse(status=404)
        embedded = True if 'embed' in bottle.request.query else False
        if embedded:
            # Embedded image urls have had a .jpg or .png
            # appended. Remove it to restore the track path name.
            i = filepath.rfind('.')
            filepath = filepath[:i]
            apath = os.path.join(self.root,filepath)
            ctype, size, f = embedded_open(apath)
            fs = os.stat(apath)
            lm = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(fs.st_mtime))
            bottle.response.set_header("Last-Modified", lm)
            bottle.response.set_header("Content-type", ctype)
            bottle.response.set_header("Content-Length", size)
            return f
        # Binary paths: transmitted as follows (See bottle._handle())
        #   binarypath->binarypath.decode('latin1')->urlquote()->NETWORK->
        #   urlunquote()->encode('latin1').decode('utf-8', 'ignore')
        # If there are non utf-8 characters in the path, the result is
        # missing them, and file access fails. However, we get the
        # binary result from urlunquote)_ in the 'bottle.raw_path'
        # request environment variable, and try to use it if the
        # normal path is not accessible.
        fullpath = os.path.join(self.root, filepath)
        root = '/'
        if not os.path.exists(fullpath):
            fullpath = bottle.request.environ.get('bottle.raw_path')
            fullpath = fullpath.encode('latin1')
            root = b'/'
            if not os.path.exists(fullpath):
                uplog("uprcl: no such file: %s" % fullpath)
                return bottle.HTTPResponse(status=404)
        uplog("Streaming: %s " % fullpath)
        mutf = mutagen.File(fullpath)
            
        if mutf:
            return bottle.static_file(fullpath, root=root,
                                      mimetype=mutf.mime[0])
        else:
            return bottle.static_file(fullpath, root=root)
    

# Bottle handle both the streaming and control requests.
def runbottle(host='0.0.0.0', port=9278, pthstr='', pathprefix=''):
    global datadir
    uplog("runbottle: version %s host %s port %d pthstr %s pathprefix %s" %
          (bottle.__version__, host, port, pthstr, pathprefix))
    datadir = os.path.dirname(__file__)
    datadir = os.path.join(datadir, 'bottle')
    bottle.TEMPLATE_PATH = (os.path.join(datadir, 'views'),)

    # All the file urls must be like /some/prefix/path where
    # /some/prefix must be in the path translation map (which I'm not
    # sure what the use of is). By default the map is an identical
    # translation of all topdirs entries. We create one route for each
    # prefix. As I don't know how a bottle method can retrieve the
    # route it was called from, we create a callable for each prefix.
    # Each route is built on the translation input, and the processor
    # uses the translated path as root
    lpth = pthstr.split(',')
    for ptt in lpth:
        l = ptt.split(':')
        rt = l[0]
        if rt[-1] != '/':
            rt += '/'
        rt += '<filepath:path>'
        uplog("runbottle: adding route for: %s"%rt)
        # We build the streamer with the translated 
        streamer = Streamer(l[1])
        bottle.route(rt, 'GET', streamer)

    bottle.run(server='waitress', host=host, port=port)
