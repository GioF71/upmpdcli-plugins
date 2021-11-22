# Copyright (C) 2016-2021 J.F.Dockes
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
#
"""
Shared code for the tidal, qobuz, etc. plugins.

   - Uses the interface for the entity objects (track, album...)
     concretely defined in models.py, but duck-typed.
   - Defines and uses the format for the permanent URLs

The module implements utility functions for translating to/from what
our parent expects or sends on the pipe.
"""

import sys
import os
import subprocess
import pwd
import errno

import conftree

# This is only used for log messages
_idprefix = '0$UNKNOWN'


def setidprefix(idprefix):
    global _idprefix
    _idprefix = idprefix


def direntry(id, pid, title, arturi=None, artist=None, upnpclass=None, searchable='1', date=None):
    """ Create container entry in format expected by parent """
    #uplog("rcldirentry: id %s pid %s tt %s dte %s clss %s artist %s arturi %s" %
    #      (id,pid,title,date,upnpclass,artist,arturi))
    ret = {'id':id, 'pid':pid, 'tt':title, 'tp':'ct', 'searchable':searchable}
    if arturi:
        ret['upnp:albumArtURI'] = arturi
    if artist:
        ret['upnp:artist'] = artist
    if date:
        ret['dc:date'] = date
    if upnpclass:
        ret['upnp:class'] = upnpclass
    else:
        ret['upnp:class'] = 'object.container.storageFolder'
    return ret


# Get user and password from service, from the main configuration
# file, or possibly from the ohcredentials scratchpad. In both files,
# the entries are like:
#    qobuzuser=xxx
#    qobuzpass=yyy
def getserviceuserpass(upconfig, servicename):
    username = upconfig.get(servicename + 'user')
    password = upconfig.get(servicename + 'pass')
    if not username or not password:
        credsfile = os.path.join(getcachedir(upconfig, ''), 'ohcreds', 'screds')
        uplog("Retrieving user/pass from %s" % credsfile)
        altconf = conftree.ConfSimple(credsfile)
        username = altconf.get(servicename + 'user')
        password = altconf.get(servicename + 'pass')
    return username, password


_loglevel = 3
def uplog(s, level=3):
    if level > _loglevel:
        return
    if not type(s) == type(b''):
        s = ("%s: %s" % (_idprefix, s)).encode('utf-8')
        sys.stderr.buffer.write(s + b'\n')
    sys.stderr.flush()


def getcachedir(config, servicename):
    cachedir = config.get('cachedir')
    if not cachedir:
        me = pwd.getpwuid(os.getuid()).pw_name
        uplog("getcachedir: me: %s" % me)
        if me == 'upmpdcli':
            cachedir = '/var/cache/upmpdcli/'
        else:
            cachedir = os.path.expanduser('~/.cache/upmpdcli/')
    cachedir = os.path.join(cachedir, servicename)
    try:
        os.makedirs(cachedir)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(cachedir):
            pass
        else:
            raise
    return cachedir


# Find first non loopback ip. This is surprisingly
# difficult. Executing "ip addr" actually seems to be the simplest
# approach, only works on Linux though (maybe bsd too ?)
def findmyip():
    data = subprocess.check_output(["ip", "addr"]).decode('utf-8')
    l = data.split()
    ips = []
    chosenip = ""
    for i in range(len(l)):
        k = l[i]
        if k == 'inet':
            ipmask = l[i+1]
            if ipmask.find('127.') == 0:
                continue
            return ipmask.split('/')[0]
    return '127.0.0.1'
