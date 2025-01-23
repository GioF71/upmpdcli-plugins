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

from enum import Enum

plugin_name: str = "subsonic"
subsonic_plugin_release: str = "0.6.7"

default_dump_streaming_properties: int = 0


class ItemKey(Enum):

    BIT_DEPTH = "bitDepth"
    SAMPLING_RATE = "samplingRate"
    CHANNEL_COUNT = "channelCount"
    MUSICBRAINZ_ID = "musicBrainzId"
    MEDIA_TYPE = "mediaType"
    RELEASE_TYPES = "releaseTypes"
    ALBUM_ARTISTS = "albumArtists"
    ARTISTS = "artists"
    ORIGINAL_RELEASE_DATE = "originalReleaseDate"
    EXPLICIT_STATUS = "explicitStatus"


class Defaults(Enum):

    SUBSONIC_API_MAX_RETURN_SIZE = 500  # API Hard Limit
    DUMP_ACTION_ON_MB_ALBUM_CACHE = 0
    ADDITIONAL_ARTISTS_MAX = 15
    ALBUM_SEARCH_LIMIT = 50
    ARTIST_SEARCH_LIMIT = 25
    SONG_SEARCH_LIMIT = 100
    MAX_ARTISTS_PER_PAGE = 25
    ITEMS_PER_PAGE = 25
    CACHED_REQUEST_TIMEOUT_SEC = 600
    ALLOW_PREPEND_ARTIST_IN_ALBUM_LISTS = 1


class ExplicitInfo:

    def __init__(self, tag_value: str, display_value: str):
        self.__tag_value: str = tag_value
        self.__display_value: str = display_value

    @property
    def tag_value(self) -> str:
        return self.__tag_value

    @property
    def display_value(self) -> str:
        return self.__display_value


class ExplicitStatus(Enum):

    EXPLICIT = ExplicitInfo("explicit", "E")
    CLEAN = ExplicitInfo("clean", "C")


default_show_empty_favorites: int = 0
default_show_empty_playlists: int = 0
fallback_transcode_codec: str = "ogg"
default_debug_badge_mngmt: int = 0
default_debug_artist_albums: int = 0
