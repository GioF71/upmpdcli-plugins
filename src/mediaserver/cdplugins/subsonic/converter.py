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

from subsonic_connector.artist_cover import ArtistCover
from retrieved_art import RetrievedArt
from typing import Callable

import connector_provider
import config

def __album_id_converter(album_id : str) -> str:
    return connector_provider.get().buildCoverArtUrl(album_id) if album_id else None

def __artist_id_converter(artist_id : str, albums_only : bool = False) -> RetrievedArt:
    artist_cover : ArtistCover = connector_provider.get().getCoverByArtistId(artist_id)
    if not artist_cover: return None
    return (RetrievedArt(art_url = artist_cover.getArtistArtUrl())
        if artist_cover.getArtistArtUrl() and config.allow_artist_art
        else RetrievedArt(cover_art = artist_cover.getAlbumId()))

converter_album_id_to_url : Callable[[str], str] = __album_id_converter
converter_artist_id_to_url : Callable[[str, bool], RetrievedArt] = __artist_id_converter

