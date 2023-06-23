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

import connector_provider
from subsonic_connector.artist_cover import ArtistCover
from typing import Callable

def __album_id_converter(album_id : str) -> str:
    return connector_provider.get().buildCoverArtUrl(album_id) if album_id else None

def __artist_id_converter(artist_id : str) -> str:
    artist_cover : ArtistCover = connector_provider.get().getCoverByArtistId(artist_id)
    if not artist_cover: return None
    return artist_cover.getCoverArt()

converter_album_id_to_url : Callable[[str], str] = __album_id_converter
converter_artist_id_to_url : Callable[[str], str] = __artist_id_converter

