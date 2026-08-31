# Copyright (C) 2026 Giovanni Fulco
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


from enum import Enum


class TableName(Enum):
    ALBUM_METADATA_CACHE_V1 = "album_metadata_cache_v1"
    TRACK_METADATA_CACHE_V1 = "track_metadata_cache_v1"
    TILE_IMAGE_V1 = "tile_image_v1"
    LISTEN_ALBUM_QUEUE_V1 = "listen_album_queue_v1"
    LISTEN_ARTIST_QUEUE_V1 = "listen_artist_queue_v1"
    LISTEN_TRACK_QUEUE_V1 = "listen_track_queue_v1"
    PLAYED_TRACK_V1 = "played_track_v1"
    DB_VERSION = "db_version"
