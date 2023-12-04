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
default_bits = "16"
default_channels = "2"

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

    # item_num is the number to be prepended to the title, if different from None
    # this is for the benefit of kodi which always sort entries by name
    def add_directory(self, title, endpoint, arturi=None, item_num = None):
        if callable(endpoint):
            endpoint = self.routeplug.url_for(endpoint)
        if item_num: title = f"[{item_num:02}] {title}"
        e = direntry(self.idprefix + endpoint, self.objid, title, arturi=arturi)
        self.entries.append(e)


    def urls_from_id(self, view_func, items):
        if not items: return []
        uplog("urls_from_id: items: %s" % str([item.id for item in items]), level=5)
        return [self.routeplug.url_for(view_func, item.id)
                for item in items if str(item.id).find('http') != 0]


    # initial_item_num is the start number to be prepended to the title, if 
    # different from None
    # This is for the benefit of kodi which always sort entries by name
    def view(self, data_items, urls, end=True, initial_item_num = None):
        if not data_items or not urls: return
        for item, url in zip(data_items, urls):
            title = item.name
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
            
            if initial_item_num:
                title = f"[{initial_item_num:02}] {title}"
                initial_item_num += 1 
            self.entries.append(
                direntry(self.idprefix + url, self.objid, title,
                         arturi=image, artist=artnm, upnpclass=upnpclass, description=description))

    

# For now, we pretend that all tracks have the same format (for the resource record). For some
# services this may not be true, we'll see if it can stay this way.
def setMimeAndSamplerate(m, s, bits=None, channels=None):
    global default_mime, default_samplerate, default_bits, default_channels
    default_mime = m
    default_samplerate = s
    if bits:
        default_bits = str(bits)
    if channels:
        default_channels = str(channels)

# Translate an upmplgmodels Tracks array into output expected by plgwithslave. The URLs are
# constructed for future redirection/proxying by our HTTP server.
# optionally, using argument generate_track_nums set to True, tracknumbers can be generated by counting 
# the presented elements, so that the control points which decide to apply track sorting will
# still present the tracks in the correct order in the case of playlists and, 
# most importantly, multi-disc albums
# This is afaik to the benefit of kodi mostly
def trackentries(httphp, pathprefix, objid, tracks, generate_track_nums = False):
    """
    Transform a list of Track objects to the format expected by the parent

    Args:
        objid (str):  objid for the browsed object (the parent container)
        tracks is the array of Track objects to be translated
        tracks: a list of Track objects.
        generate_track_nums: boolean values, if set, the tracknumber is generated
        
    Returns:
        A list of dicts, each representing an UPnP item, with the
        keys as expected in the plgwithslave.cxx resultToEntries() function. 

        The permanent URIs, are of the following form, based on the
        configured host:port and pathprefix arguments and track Id:

            http://host:port/pathprefix/track/version/1/trackId/<trackid>
    
    """
    entries = []
    track_counter : int = 0
    for track in tracks:
        if not track.available:
            if 1:
                uplog("NOT AVAILABLE")
                try:
                    uplog("%s by %s" % (track.name, track.artist.name))
                except:
                    pass
            continue
        track_counter += 1
        li = {}
        li['pid'] = objid
        li['id'] = objid + '$' + "%s" % track.id
        li['tt'] = track.name
        li['uri'] = 'http://%s' % httphp + \
                    posixpath.join(pathprefix, 'track/version/1/trackId/%s' % track.id)
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
        # if generate_track_nums, we use the counter instead of the metadata
        li['upnp:originalTrackNumber'] = str(track_counter) if generate_track_nums else str(track.track_num)
        li['upnp:artist'] = track.artist.name
        li['dc:title'] = track.name
        # if generate_track_nums, we can skip the discnumber
        if not generate_track_nums: li['discnumber'] = str(track.disc_num)
        li['upnp:class'] = track.upnpclass

        li['duration'] = str(track.duration)
        li['res:mime'] = track.mime if track.mime else default_mime
        li['res:samplefreq'] = track.samplefreq if track.samplefreq else default_samplerate
        li['res:bitsPerSample'] = track.bitdepth if track.bitdepth else default_bits
        li['res:channels'] = track.channels if track.channels else default_channels
           
        entries.append(li)
    return entries


# Extract trackid from one of our special form URLs. This is called from the HTTP server to
# translate the permanent trackid-based URL into a temporary service URL for redirecting or fetching
# the data
def trackid_from_urlpath(pathprefix, a):
    """
    Extract track id from a permanent URL path part.

    This supposes that the input URL has the format produced by the
    trackentries() method: <pathprefix>/track/version/1/trackId/<trackid>

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
