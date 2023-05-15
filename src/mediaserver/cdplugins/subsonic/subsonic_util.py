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

# this should contain all methods which interact directly with the subsonic server

from subsonic_connector.connector import Connector
from subsonic_connector.list_type import ListType
from subsonic_connector.response import Response
from subsonic_connector.album_list import AlbumList
from subsonic_connector.album import Album

import secrets

import cmdtalkplugin

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

def get_random_art_by_genre(
        connector : Connector,
        genre : str,
        max_items : int = 100) -> str:
    response : Response[AlbumList] = connector.getAlbumList(
        ltype = ListType.BY_GENRE,
        genre = genre,
        size = max_items)
    if not response.isOk(): return None
    album : Album = secrets.choice(response.getObj().getAlbums())
    if album: return album.getId()
    return None
