# Copyright (C) 2023,2024 Giovanni Fulco
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


def set_track_number(track_number: str, target: dict):
    target['upnp:originalTrackNumber'] = track_number


def set_album_art_from_uri(album_art_uri: str, target: dict):
    target['upnp:albumArtURI'] = album_art_uri


def set_uri(uri: str, target: dict):
    target['uri'] = uri


def set_duration(duration: int, target: dict):
    target['duration'] = str(duration)


def set_disc_number(disc_number: int, target: dict):
    target['discnumber'] = str(disc_number)


def set_channels(channel_count: int, target: dict):
    target['res:channels'] = str(channel_count)


def set_track_title(track_title: str, target: dict):
    target['tt'] = track_title


def set_album_title(album_title: str, target: dict):
    target['upnp:album'] = album_title


def set_album_id(album_id: str, target: dict):
    target['album_id'] = album_id


def set_class(upnp_class: str, target: dict):
    target['upnp:class'] = upnp_class


def set_artist(artist: str, target: dict):
    target['upnp:artist'] = artist


def set_class_music_track(target: dict):
    target['upnp:class'] = upmplgmodels.Track.upnpclass


def set_class_album(target: dict):
    target['upnp:class'] = upmplgmodels.Album.upnpclass


def set_mime_type(mime_type: str, target: dict):
    target['res:mime'] = mime_type


def set_bit_depth(bit_depth: int, target: dict):
    target['res:bitsPerSample'] = str(bit_depth)


def set_sample_rate(sample_rate: int, target: dict):
    target['res:samplefreq'] = str(sample_rate)


def set_bit_rate(bit_rate: int, target: dict):
    target['kbs'] = str(bit_rate)


def set_object_type_container(target: dict):
    set_object_type('ct', target)


def set_object_type_item(target: dict):
    set_object_type('it', target)


def set_object_type(container_type: str, target: dict):
    target['tp'] = container_type


def set_class_artist(target: dict):
    target['upnp:class'] = upmplgmodels.Artist.upnpclass
