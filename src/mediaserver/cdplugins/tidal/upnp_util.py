# Copyright (C) 2023 Giovanni Fulco
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import upmplgmodels

def set_track_number(track_number : str, target : dict):
    target['upnp:originalTrackNumber'] = track_number

def set_album_art_from_uri(album_art_uri : str, target : dict):
    target['upnp:albumArtURI'] = album_art_uri

def set_album_title(album_title : str, target : dict):
    target['tt'] = album_title

def set_album_id(album_id : str, target : dict):
    target['album_id'] = album_id

def set_class(upnp_class : str, target : dict):
    target['upnp:class'] = upnp_class

def set_artist(artist : str, target : dict):
    target['upnp:artist'] = artist

def set_class_music_track(target : dict):
    target['upnp:class'] = upmplgmodels.Track.upnpclass

def set_class_album(target : dict):
    target['upnp:class'] = upmplgmodels.Album.upnpclass

def set_class_artist(target : dict):
    target['upnp:class'] = upmplgmodels.Artist.upnpclass
