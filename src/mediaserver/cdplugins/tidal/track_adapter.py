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

from tidalapi import Quality as TidalQuality
from typing import Optional

class TrackAdapter:

    def get_id(self) -> int: pass
    def get_name(self) -> str: pass
    def get_duration(self) -> int: pass
    def get_track_num(self) -> int: pass
    def get_volume_num(self) -> int: pass
    def get_album_num_volumes(self) -> int: pass
    def get_album_track_count(self) -> int: pass
    def get_album_id(self) -> str: pass
    def get_album_name(self) -> str: pass
    def get_album_artist_name(self) -> str: pass
    def get_audio_quality(self) -> TidalQuality: pass
    def get_image_url(self) -> str: pass
    def explicit(self) -> bool: pass
    def get_artist_name(self) -> str: pass
