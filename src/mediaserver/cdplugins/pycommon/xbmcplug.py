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

"""Shared code for the tidal, qobuz, etc. plugins which reused the routing module from the Tidal
Kodi plugin. Most also use the object models in upmpmodels.py, on which depend the trackentries
method, and the special form URLs used in playlists before translation to service temporary URLs
"""

import re
import posixpath

from upmplgutils import *


default_mime = "audio/mpeg"
default_samplerate = "44100"


# Bogus class instanciated as global object for helping with reusing kodi addon code
class XbmcPlugin:
    def __init__(self, idprefix, routeplugin=None):
        self.idprefix=idprefix
        setidprefix(idprefix)
        self.routeplug = routeplugin
        self.entries = []
        self.objid = ''
        self.offset = 0
        self.count = 0
        self.total = 0


    def add_directory(self, title, endpoint, arturi=None):
        if callable(endpoint):
            endpoint = self.routeplug.url_for(endpoint)
        self.entries.append(direntry(self.idprefix + endpoint, self.objid, title, arturi=arturi))


    def urls_from_id(self, view_func, items):
        uplog("urls_from_id: items: %s" % str([item.id for item in items]), level=5)
        return [self.routeplug.url_for(view_func, item.id)
                for item in items if str(item.id).find('http') != 0]


    def view(self, data_items, urls, end=True):
        for item, url in zip(data_items, urls):
            title = item.name
            maxsamprate = '44.1'
            maxbitdepth = '16'
            try:
                maxsamprate = item.maxsamprate
                maxbitdepth = item.maxbitdepth
            except:
                pass
            if maxsamprate != '44.1' or maxbitdepth != '16':
                title += ' (' + maxbitdepth + '/' +  maxsamprate + ')'
            try:
                image = item.image if item.image else None
            except:
                image = None
            try:
                upnpclass = item.upnpclass if item.upnpclass else None
            except:
                upnpclass = None
            try:
                artnm = item.artist.name if item.artist.name else None
            except:
                artnm = None
            try:
                description = item.description if item.description else None
            except:
                description = None
            
            self.entries.append(
                direntry(self.idprefix + url, self.objid, title,
                         arturi=image, artist=artnm, upnpclass=upnpclass, description=description))

    

# For now, we pretend that all tracks have the same format (for the resource record). For some
# services this may not be true, we'll see if it can stay this way.
def setMimeAndSamplerate(m, s):
    global default_mime, default_samplerate
    default_mime = m
    default_samplerate = s
    

# Translate an upmplgmodels Tracks array into output expected by plgwithslave. The URLs are
# constructed for future redirection/proxying by our HTTP server.
def trackentries(httphp, pathprefix, objid, tracks):
    """
    Transform a list of Track objects to the format expected by the parent

    Args:
        objid (str):  objid for the browsed object (the parent container)
        tracks is the array of Track objects to be translated
        tracks: a list of Track objects.
        
    Returns:
        A list of dicts, each representing an UPnP item, with the
        keys as expected in the plgwithslave.cxx resultToEntries() function. 

        The permanent URIs, are of the following form, based on the
        configured host:port and pathprefix arguments and track Id:

            http://host:port/pathprefix/track?version=1&trackId=<trackid>
    
    """
    global default_mime, default_samplerate
    
    entries = []
    for track in tracks:
        if not track.available:
            if 1:
                uplog("NOT AVAILABLE")
                try:
                    uplog("%s by %s" % (track.name, track.artist.name))
                except:
                    pass
            continue
        li = {}
        li['pid'] = objid
        li['id'] = objid + '$' + "%s" % track.id
        li['tt'] = track.name
        li['uri'] = 'http://%s' % httphp + \
                    posixpath.join(pathprefix, 'track?version=1&trackId=%s' % track.id)
        li['tp'] = 'it'
        image = getattr(track, 'image', None)
        if image:
            li['upnp:albumArtURI'] = image
        if track.album:
            li['upnp:album'] = track.album.name
            if not track.image and track.album.image:
                li['upnp:albumArtURI'] = track.album.image
            if track.album.release_date:
                li['releasedate'] = track.album.release_date
            # Do we really want to do this ? This would currently be the only way to display the,
            # e.gh. Qobuz album description in upplay (because the description is not set in album
            # lists used by the dir browser, only when querying a specific album), but it does not
            # seem quite write to set it on each track. Longer discussion in notes.
            #if not 'dc:description' in li and track.album.description:
                #uplog(f"trackentries: setting dc:description on track: {track.album.description}")
                #li['dc:description'] = track.album.description
        li['upnp:originalTrackNumber'] =  str(track.track_num)
        li['upnp:artist'] = track.artist.name
        li['dc:title'] = track.name
        li['discnumber'] = str(track.disc_num)
        li['duration'] = str(track.duration)
        li['upnp:class'] = track.upnpclass
        li['res:mime'] = default_mime
        li['res:samplefreq'] = default_samplerate
           
        entries.append(li)
    return entries


# Extract trackid from one of our special form URLs. This is called from the HTTP server to
# translate the permanent trackid-based URL into a temporary service URL for redirecting or fetching
# the data
def trackid_from_urlpath(pathprefix, a):
    """
    Extract track id from a permanent URL path part.

    This supposes that the input URL has the format produced by the
    trackentries() method: <pathprefix>/track?version=1&trackId=<trackid>

    Args:
        pathprefix (str): our configured path prefix (e.g. /qobuz/)
        a (dict): the argument dict out of cmdtalk with a 'path' key
    Returns:
        str: the track Id.
    """
    
    if 'path' not in a:
        raise Exception("trackuri: no 'path' in args")
    path = a['path']

    # pathprefix + 'track?version=1&trackId=trackid
    exp = posixpath.join(pathprefix, '''track\?version=1&trackId=(.+)$''')
    m = re.match(exp, path)
    if m is None:
        raise Exception("trackuri: path [%s] does not match [%s]" % (path, exp))
    trackid = m.group(1)
    return trackid
