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

from typing import Callable
from track_adapter import TrackAdapter
from tidalapi.session import Session as TidalSession
from tidalapi.media import Track as TidalTrack
from tidalapi.album import Album as TidalAlbum
import cmdtalkplugin
import tidal_util


# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


class TidalTrackAdapter(TrackAdapter):

    def __init__(
            self,
            tidal_session: TidalSession,
            track: TidalTrack,
            album_retriever: Callable[[TidalSession, str], TidalAlbum]):
        self._tidal_session: TidalSession = tidal_session
        self._track: TidalTrack = track
        self._album_retriever: Callable[[TidalSession, str], TidalAlbum] = album_retriever
        self._album: TidalAlbum = None
        self._album_load_failed: bool = False
        self._stream = None
        self._stream_load_failed: bool = False

    def __get_album(self):
        if not self._album_load_failed and not self._album:
            try:
                self._album = self._album_retriever(self._tidal_session, self._track.album.id)
            except Exception as ex:
                msgproc.log(f"Cannot get album for id [{self._track.album.id}] due to [{type(ex)}] [{ex}]")
                self._album_load_failed = True
                raise ex
        return self._album

    def __load_stream(self):
        if not self._stream_load_failed and not self._stream:
            try:
                self._stream = self._track.get_stream()
            except Exception as ex:
                msgproc.log(f"Cannot get stream for track id [{self._track.id}] due to [{type(ex)}] [{ex}]")
                self._stream_load_failed = True
                raise ex
        return self._stream

    def get_id(self) -> str:
        return str(self._track.id)

    def get_name(self) -> str:
        return self._track.name

    def get_duration(self) -> int:
        return self._track.duration

    def get_track_num(self) -> int:
        return self._track.track_num

    def get_volume_num(self) -> int:
        return self._track.volume_num

    def get_album_num_volumes(self) -> int:
        album: TidalAlbum = self.__get_album()
        try:
            return album.num_volumes
        except Exception:
            # no info for num_volumes
            return None

    def get_album_track_count(self) -> int:
        return self.__get_album().num_tracks

    def get_album_name(self) -> str:
        return self._track.album.name

    def get_album_id(self) -> str:
        return self._track.album.id

    def get_album_artist_name(self) -> str:
        return self._track.album.artist.name

    def get_image_url(self) -> str:
        album: TidalAlbum = None
        try:
            album = self.__get_album()
        except Exception as ex:
            msgproc.log(f"Cannot load album with album_id [{self._track.album.id}] "
                        f"due to [{type(ex)}] [{ex}]")
        return tidal_util.get_image_url(album) if album else None

    def explicit(self) -> bool:
        return self._track.explicit

    def get_artist_name(self) -> str:
        return self._track.artist.name

    def get_bit_depth(self) -> int:
        return self.__load_stream().bit_depth

    def get_sample_rate(self) -> int:
        return self.__load_stream().sample_rate

    def get_audio_quality(self) -> str:
        return self.__load_stream().audio_quality
