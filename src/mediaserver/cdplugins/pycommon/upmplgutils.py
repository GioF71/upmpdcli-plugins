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
import pwd
import errno
import inspect
import posixpath
import re

import conftree

# This is only used for log messages
_idprefix = '0$UNKNOWN'


def setidprefix(idprefix):
    global _idprefix
    _idprefix = idprefix


def direntry(id, pid, title, arturi=None, artist=None, upnpclass=None, searchable='1', date=None,
             description=None):
    """ Create container entry in format expected by parent """
    #uplog(f"rcldirentry: id {id} pid {pid} tt {title} date {date} clss {upnpclass} artist {artist} arturi {arturi}")
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
    if description:
        ret['dc:description'] = description
    return ret


# Generate an permanent URL in the form which can be used trackid_from_urlpath
def urlpath_from_trackid(httphp, pathprefix, trackid):
    return f"http://{httphp}" + posixpath.join(pathprefix, f"track/version/1/trackId/{trackid}")
                    

# Extract the service (qobuz,tidal...) trackid from one of our special form permanent URLs.
# 
# This typically gets called from the plugin trackuri() method, which is used for translating from
# our permanent URLs to a service temporary URL when the renderer tries to fetch the stream.
def trackid_from_urlpath(pathprefix, a):
    """
    Extract track id from a permanent URL path part.

    This supposes that the input URL has the format produced by urlpath_from_trackid()
    (called from, e.g., trackentries()): <pathprefix>/track/version/1/trackId/<trackid>

    Args:
        pathprefix (str): our configured path prefix (e.g. /qobuz/)
        a (dict): the argument dict out of cmdtalk with a 'path' key
    Returns:
        str: the track Id.
    """
    
    if 'path' not in a:
        raise Exception("trackuri: no 'path' in args")
    path = a['path']

    # pathprefix + 'track/version/1/trackId/trackid
    exp = posixpath.join(pathprefix, '''track/version/1/trackId/(.+)$''')
    m = re.match(exp, path)
    if m is None:
        exp_old = posixpath.join(pathprefix, '''track\?version=1&trackId=(.+)$''')        
        m = re.match(exp_old, path)
    if m is None:
        raise Exception(f"trackuri: path [{path}] does not match [{exp}]")
    trackid = m.group(1)
    return trackid


_g_upconfig = None
def getOptionValue(nm, dflt = None):
    global _g_upconfig
    if _g_upconfig is None:
        members = dict(inspect.getmembers(conftree.ConfSimple.__init__.__code__))
        var_names = members['co_varnames']
        if "casesensitive" in var_names:
            _g_upconfig = conftree.ConfSimple(os.environ["UPMPD_CONFIG"], casesensitive=False)
        else:
            _g_upconfig = conftree.ConfSimple(os.environ["UPMPD_CONFIG"])
    value = _g_upconfig.get(nm)
    if value is None:
        envar = "UPMPD_" + nm.upper()
        try:
            value = os.environ[envar]
        except:
            value = dflt

    if dflt is not None and type(dflt) != type(""):
        # Try to convert the value to the type of the provided default
        try:
            # Bool("0") is true, so special-case the bool type
            if type(dflt) == type(True):
                value = conftree.valToBool(value)
            else:
                t = type(dflt)
                value = t(value)
        except Exception as ex:
            uplog(f"Config: type conversion failed for {nm}")

    return value


def getConfigObject():
    if _g_upconfig is None:
        getOptionValue("somebogusvalue")
    return _g_upconfig

# Get user and password from service, from the main configuration
# file, or possibly from the ohcredentials scratchpad. In both files,
# the entries are like:
#    qobuzuser=xxx
#    qobuzpass=yyy
def getserviceuserpass(servicename):
    username = getOptionValue(servicename + 'user')
    password = getOptionValue(servicename + 'pass')
    if not username or not password:
        credsfile = os.path.join(getcachedir(''), 'ohcreds', 'screds')
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


def getcachedir(servicename, forcedpath=None):
    if forcedpath:
        cachedir = forcedpath
    else:
        cachedir = getOptionValue("cachedir")
        if not cachedir:
            me = pwd.getpwuid(os.getuid()).pw_name
            uplog("getcachedir: me: %s" % me)
            if me == "upmpdcli":
                cachedir = "/var/cache/upmpdcli/"
            else:
                cachedir = os.path.expanduser("~/.cache/upmpdcli/")
        cachedir = os.path.join(cachedir, servicename)
    try:
        os.makedirs(cachedir)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(cachedir):
            pass
        else:
            raise
    return cachedir

