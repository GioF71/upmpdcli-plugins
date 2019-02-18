# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Thomas Amland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import unicode_literals

class Model(object):
    id = None
    name = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Album(Model):
    upnpclass = "object.container.album.musicAlbum"
    name = "Unknown"
    artist = None
    artists = []
    num_tracks = -1
    duration = -1
    release_date = None
    image = None
    available = True
    maxsamprate = "44.1"
    maxbitdepth = "16"
    maxchannels = "2"

class Artist(Model):
    upnpclass = "object.container.person.musicArtist"
    name = "Unknown"
    role = None


class Playlist(Model):
    upnpclass = "object.container.album"
    # Using the proper playlistContainer type this confuses e.g. Kazoo
    #upnpclass = "object.container.playlistContainer"
    name = None
    # We create a bogus artist with the playlist owner name when available
    artist = None
    description = None
    num_tracks = -1
    duration = -1
    # For spotify: wants an userid to retrieve a playlist's tracks
    userid = None


class Track(Model):
    upnpclass = "object.item.audioItem.musicTrack"
    duration = -1
    track_num = -1
    disc_num = 1
    popularity = -1
    artist = None
    artists = []
    album = None
    available = True
    maxsamprate = "44.1"
    maxbitdepth = "16"
    maxchannels = "2"


class SearchResult(Model):
    artists = []
    albums = []
    tracks = []
    playlists = []


class Category(Model):
    image = None


class Genre(Model):
    pass
