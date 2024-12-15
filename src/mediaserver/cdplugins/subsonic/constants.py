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

plugin_name: str = "subsonic"
subsonic_plugin_release: str = "0.6.4"

subsonic_max_return_size: int = 500  # hard limit

default_dump_streaming_properties: int = 0

item_key_bit_depth: str = "bitDepth"
item_key_sampling_rate: str = "samplingRate"
item_key_channel_count: str = "channelCount"
item_key_musicbrainz_id: str = "musicBrainzId"
item_key_release_types: str = "releaseTypes"

default_max_artists_per_page: int = 25
default_show_empty_favorites: int = 0
default_show_empty_playlists: int = 0
default_items_per_page: int = 25
default_cached_request_timeout_sec: int = 600
fallback_transcode_codec: str = "ogg"
default_debug_badge_mngmt: int = 0
default_debug_artist_albums: int = 0
