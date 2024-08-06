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

from tidalapi import Quality as TidalQuality

plugin_name : str = "tidal"

tidal_plugin_release : str = "0.7.3"

listening_queue_action_key : str = "action"
listening_queue_button_title_key : str = "button_title"

__add_action : str = "add"
__del_action : str = "del"

listening_queue_action_add : str = __add_action
listening_queue_action_del : str = __del_action

listening_queue_action_add_dict : dict[str, str] = {
    listening_queue_action_key: listening_queue_action_add,
    listening_queue_button_title_key: "Add to Bookmarks"}

listening_queue_action_del_dict : dict[str, str] = {
    listening_queue_action_key: listening_queue_action_del,
    listening_queue_button_title_key: "Rmv from Bookmarks"}

fav_action_key : str = "action"
fav_button_title_key : str = "button_title"

button_title_add_to_favorites : str = "Add to Favorites"
button_title_remove_from_favorites : str = "Rmv from Favorites"

button_title_add_album_to_favorites : str = button_title_add_to_favorites
button_title_remove_album_from_favorites : str = button_title_remove_from_favorites

button_title_add_artist_to_favorites : str = button_title_add_to_favorites
button_title_remove_artist_from_favorites : str = button_title_remove_from_favorites

button_title_add_song_to_favorites : str = button_title_add_to_favorites
button_title_remove_song_from_favorites : str = button_title_remove_from_favorites

fav_action_add : str = __add_action
fav_action_del : str = __del_action

fav_action_add_dict : dict[str, str] = {
    fav_action_key: fav_action_add,
    fav_button_title_key: "Add to Favorites"}

fav_action_del_dict : dict[str, str] = {
    fav_action_key: fav_action_del,
    fav_button_title_key: "Rmv from Favorites"}

fav_action_dict : dict[str, any] = {
    fav_action_add : fav_action_add_dict,
    fav_action_del : fav_action_del_dict
}

featured_type_name_playlist : str = "PLAYLIST"
tile_image_expiration_time_sec : int = 86400

auth_challenge_type_oauth2 : str = "oauth2"
auth_challenge_type_pkce : str = "pkce"

default_auth_challenge_type : str = auth_challenge_type_oauth2

oauth2_credentials_file_name : str = "credentials.json"
pkce_credentials_file_name : str = "pkce.credentials.json"

key_authentication_type : str = "authentication_type"
key_pkce_file_available : str = "pkce_file_available"
key_oauth2_file_available : str = "oauth2_file_available"

key_token_type : str = "tokentype"
key_access_token : str = "accesstoken"
key_refresh_token : str = "refreshtoken"
key_expiry_time : str = "expirytime"
key_expiry_time_timestamp_str : str = "expirytimetimestampstr"

key_pkce_token_type : str = "pkcetokentype"
key_pkce_access_token : str = "pkceaccesstoken"
key_pkce_refresh_token : str = "pkcerefreshtoken"
key_pkce_session_id : str = "pkcesessionid"
key_pkce_is_pkce : str = "pkceispkce"

key_pkce_token_type_json : str = "token_type"
key_pkce_access_token_json : str = "access_token"
key_pkce_refresh_token_json : str = "refresh_token"
key_pkce_session_id_json : str = "session_id"
key_pkce_is_pkce_json : str = "is_pkce"

# remove if not really used
default_max_album_tracks_per_page : int = 30

default_max_playlist_or_mix_items_per_page : int = 25

default_enable_read_stream_metadata : int = 0
default_enable_assume_bitdepth : int = 1
default_playlist_items_per_page : int = 25
default_tracks_per_page : int = 25
default_mix_items_per_page : int = 25
default_albums_per_page : int = 25
default_artists_per_page : int = 25
default_page_items_per_page : int = 35

default_page_items_for_tile_image: int = 3

# this one should be disabled by default for the release
default_dump_track_to_entry_result : int = 0

default_allow_guess_stream_info_from_other_album_track : int = 1

default_max_file_age_seconds : int = 3600

default_max_get_stream_info_mix_or_playlist : int = 5

default_max_audio_quality : str = TidalQuality.high_lossless

default_session_max_duration_sec : int = 300

default_show_album_id : bool = True

default_badge_favorite_album : bool = True

default_titleless_single_album_view : bool = False

default_skip_non_stereo : bool = True

default_log_intermediate_url : bool = False

default_prepend_number_in_item_list : bool = False

default_serve_mode : str = "mpd"

default_listen_queue_playlist_name : str = "Listening Queue"

default_display_quality_badge : bool = False

default_enable_image_caching : bool = False

default_search_limit: int = 15

default_dump_image_caching: bool = False
