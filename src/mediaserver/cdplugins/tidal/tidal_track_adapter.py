from track_adapter import TrackAdapter
from tidalapi import Quality as TidalQuality
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

from tidalapi.media import Track as TidalTrack
from tidalapi.album import Album as TidalAlbum

from typing import Callable

import tidal_util

class TidalTrackAdapter(TrackAdapter):

    def __init__(self, track : TidalTrack, album_retriever : Callable[[str], TidalAlbum]):
        self._track : TidalTrack = track
        self._album_retriever : Callable[[str], TidalAlbum] = album_retriever
        self._loaded_album : TidalAlbum = None

    def __get_album(self): 
        if not self._loaded_album:
            self._loaded_album = self._album_retriever(self._track.album.id)
        return self._loaded_album

    def get_id(self) -> int: return self._track.id
    def get_name(self) -> str: return self._track.name
    def get_duration(self) -> int: return self._track.duration
    def get_track_num(self) -> int: return self._track.track_num
    def get_volume_num(self) -> int: return self._track.volume_num
    def get_album_num_volumes(self) -> int: return self.__get_album().num_volumes
    def get_album_track_count(self) -> int: return self.__get_album().num_tracks
    def get_album_name(self) -> str: return self._track.album.name
    def get_album_id(self) -> str: return self._track.album.id
    def get_album_artist_name(self) -> str: return self._track.album.artist.name
    def get_audio_quality(self) -> TidalQuality: return self._track.audio_quality
    def get_image_url(self) -> str: return tidal_util.get_image_url(self.__get_album())
    def explicit(self) -> bool: return self._track.explicit
    def get_artist_name(self) -> str: return self._track.artist.name
