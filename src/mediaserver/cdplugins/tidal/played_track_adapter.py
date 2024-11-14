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

from track_adapter import TrackAdapter
from played_track import PlayedTrack


class PlayedTrackAdapter(TrackAdapter):

    def __init__(self, track: PlayedTrack):
        self._track: PlayedTrack = track

    def get_id(self) -> str:
        return self._track.track_id

    def get_name(self) -> str:
        return self._track.track_name

    def get_duration(self) -> int:
        return self._track.track_duration

    def get_track_num(self) -> int:
        return self._track.track_num

    def get_volume_num(self) -> int:
        return self._track.volume_num

    def get_album_num_volumes(self) -> int:
        return self._track.album_num_volumes

    def get_album_track_count(self) -> int:
        return self._track.album_track_count

    def get_album_name(self) -> str:
        return self._track.album_name

    def get_album_id(self) -> str:
        return self._track.album_id

    def get_album_artist_name(self) -> str:
        return self._track.album_artist_name

    def get_audio_quality(self) -> str:
        return self._track.audio_quality

    def get_image_url(self) -> str:
        return self._track.image_url

    def explicit(self) -> bool:
        return True if self._track.explicit == 1 else False

    def get_artist_name(self) -> str:
        return self._track.artist_name

    def get_bit_depth(self) -> int:
        return self._track.bit_depth

    def get_sample_rate(self) -> int:
        return self._track.sample_rate
