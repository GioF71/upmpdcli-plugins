# Copyright (C) 2024 Giovanni Fulco
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

from subsonic_connector.response import Response
from subsonic_connector.album_list import AlbumList
from subsonic_connector.artists import Artists
from subsonic_connector.genres import Genres
from subsonic_connector.starred import Starred

import config
import connector_provider

import cmdtalkplugin

import datetime

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


class CachedResponse:
    last_response_obj: Response = None
    last_response_time: datetime.datetime = None


cached_response_artists: CachedResponse = CachedResponse()
cached_response_random_firstpage: CachedResponse = CachedResponse()
cached_response_genres: CachedResponse = CachedResponse()
cached_starred_albums: CachedResponse = CachedResponse()
cached_starred: CachedResponse = CachedResponse()


def __is_older_than(date_time: datetime.datetime, delta_sec: int) -> bool:
    if date_time is None:
        return True
    cutoff: datetime.datetime = datetime.datetime.now() - datetime.timedelta(seconds=delta_sec)
    return date_time < cutoff


def __cached_response_is_expired(cached: CachedResponse, delta_sec: int) -> bool:
    return (cached is None or
            cached.last_response_obj is None or
            __is_older_than(
                cached.last_response_time
                if cached is not None
                else None,
                delta_sec))


def get_starred() -> Response[Artists]:
    global cached_starred
    if __cached_response_is_expired(cached_starred, config.get_cached_request_timeout_sec()):
        msgproc.log("subsonic_util.get_starred loading starred ...")
        # actually request starred
        res: Response[Starred] = connector_provider.get().getStarred()
        # store response along with timestamp
        cached_starred = CachedResponse()
        cached_starred.last_response_obj = res
        cached_starred.last_response_time = datetime.datetime.now()
        return res
    else:
        # msgproc.log("subsonic_util.get_starred using cached starred")
        return cached_starred.last_response_obj


def get_artists() -> Response[Artists]:
    global cached_response_artists
    if __cached_response_is_expired(cached_response_artists, config.get_cached_request_timeout_sec()):
        msgproc.log("subsonic_util.get_artists loading artists ...")
        # actually request artists
        res: Response[Artists] = connector_provider.get().getArtists()
        # store response along with timestamp
        cached_response_artists = CachedResponse()
        cached_response_artists.last_response_obj = res
        cached_response_artists.last_response_time = datetime.datetime.now()
        msgproc.log("subsonic_util.get_artists artists have been loaded.")
        return res
    else:
        # msgproc.log("subsonic_util.get_artists using cached artists!")
        return cached_response_artists.last_response_obj


def get_random_album_list(
        size=10,
        offset=0,
        fromYear=None,
        toYear=None,
        genre=None,
        musicFolderId=None) -> Response[AlbumList]:
    # cache first page
    if not (
            size == config.get_items_per_page() and
            int(offset) == 0 and
            genre is None and
            fromYear is None and
            toYear is None and
            musicFolderId is None):
        msgproc.log(f"request_cache.get_random_album_list cannot be cached "
                    f"size:[{size}] [{size == config.get_items_per_page()}] "
                    f"offset:[{offset}] [{int(offset) == 0}] "
                    f"fromYear:[{fromYear}] [{fromYear is None}] "
                    f"toYear:[{toYear}] [{toYear is None}] "
                    f"genre:[{genre}] [{genre is None}] "
                    f"musicFolderId:[{musicFolderId}] [{musicFolderId is None}]")
        return connector_provider.get().getRandomAlbumList(
            size=size,
            offset=offset,
            fromYear=fromYear,
            toYear=toYear,
            genre=genre,
            musicFolderId=musicFolderId)
    else:
        global cached_response_random_firstpage
        if __cached_response_is_expired(cached_response_random_firstpage, config.get_cached_request_timeout_sec()):
            msgproc.log("subsonic_util.get_random_album_list loading first random albums ...")
            # actually request first random albums
            res: Response[Artists] = connector_provider.get().getRandomAlbumList(size=config.get_items_per_page())
            cached_response_random_firstpage = CachedResponse()
            cached_response_random_firstpage.last_response_obj = res
            cached_response_random_firstpage.last_response_time = datetime.datetime.now()
            return res
        else:
            # use cached!
            # msgproc.log("subsonic_util.get_random_album_list using cached first random albums")
            return cached_response_random_firstpage.last_response_obj


def get_genres() -> Response[Genres]:
    global cached_response_genres
    if __cached_response_is_expired(cached_response_genres, config.get_cached_request_timeout_sec()):
        msgproc.log("subsonic_util.get_genres loading ...")
        # actually request genres
        res: Response[Genres] = connector_provider.get().getGenres()
        cached_response_genres = CachedResponse()
        cached_response_genres.last_response_obj = res
        cached_response_genres.last_response_time = datetime.datetime.now()
        return res
    else:
        # use cached!
        # msgproc.log("subsonic_util.get_genres using cached response")
        return cached_response_genres.last_response_obj
