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

import subsonic_util
import cache_manager_provider
import subsonic_init_provider

from element_type import ElementType

from typing import Callable

def __select_album_id_for_genre_artist(artist_id : str) -> str:
    artist_art : str = cache_manager_provider.get().get_cached_element(ElementType.GENRE_ARTIST, artist_id)
    if not artist_art:
        # fallback to art for artist in general
        artist_art : str = subsonic_util.get_artist_art(artist_id, subsonic_init_provider.initializer_callback)
    return artist_art

selector_artist_id_to_album_id : Callable[[str], str] = __select_album_id_for_genre_artist
