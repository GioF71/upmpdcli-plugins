# Copyright (C) 2024,2025 Giovanni Fulco
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
from subsonic_connector.playlists import Playlists
from subsonic_connector.artist import Artist
from subsonic_connector.search_result import SearchResult
from subsonic_connector.list_type import ListType
from msgproc_provider import msgproc
import config
import constants
import connector_provider
import datetime
import time


class CachedResponse:
    last_response_obj: Response = None
    last_response_time: datetime.datetime = None


class CachedArtistList:
    last_Artist_List: list[Artist] = None
    last_response_time: datetime.datetime = None


cached_response_artists: CachedResponse = CachedResponse()
cached_response_random_firstpage: CachedResponse = CachedResponse()
cached_response_genres: CachedResponse = CachedResponse()
cached_starred_albums: CachedResponse = CachedResponse()
cached_starred: CachedResponse = CachedResponse()
cached_playlists: CachedResponse = CachedResponse()
cached_response_newest: CachedResponse = CachedResponse()

cached_all_artist_list: CachedArtistList = CachedArtistList()


def __is_older_than(date_time: datetime.datetime, delta_sec: int) -> bool:
    if date_time is None:
        return True
    cutoff: datetime.datetime = datetime.datetime.now() - datetime.timedelta(seconds=delta_sec)
    return date_time < cutoff


def __cached_list_is_expired(cached: CachedArtistList, delta_sec: int) -> bool:
    return (cached is None or
            cached.last_Artist_List is None or
            __is_older_than(
                cached.last_response_time
                if cached is not None
                else None,
                delta_sec))


def __cached_response_is_expired(cached: CachedResponse, delta_sec: int) -> bool:
    return (cached is None or
            cached.last_response_obj is None or
            __is_older_than(
                cached.last_response_time
                if cached is not None
                else None,
                delta_sec))


def get_playlists() -> Response[Artists]:
    global cached_playlists
    if __cached_response_is_expired(
            cached=cached_playlists,
            delta_sec=config.get_config_param_as_int(constants.ConfigParam.CACHED_REQUEST_TIMEOUT_SEC)):
        msgproc.log("subsonic_util.get_playlists loading playlists ...")
        # actually request starred
        res: Response[Playlists] = connector_provider.get().getPlaylists()
        # store response along with timestamp
        cached_playlists = CachedResponse()
        cached_playlists.last_response_obj = res
        cached_playlists.last_response_time = datetime.datetime.now()
        return res
    else:
        return cached_playlists.last_response_obj


def get_starred() -> Response[Starred]:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    global cached_starred
    if __cached_response_is_expired(
            cached=cached_starred,
            delta_sec=config.get_config_param_as_int(constants.ConfigParam.CACHED_REQUEST_TIMEOUT_SEC)):
        msgproc.log("subsonic_util.get_starred loading starred ...")
        # actually request starred
        start: float = time.time()
        res: Response[Starred] = connector_provider.get().getStarred()
        # store response along with timestamp
        cached_starred = CachedResponse()
        cached_starred.last_response_obj = res
        cached_starred.last_response_time = datetime.datetime.now()
        if verbose:
            msgproc.log(f"request_cache.get_starred took [{(time.time() - start):.3f}] sec")
        return res
    else:
        if verbose:
            msgproc.log("request_cache.get_starred is using cached data")
        return cached_starred.last_response_obj


def get_all_artists() -> list[Artist]:
    global cached_all_artist_list
    if __cached_list_is_expired(
            cached=cached_all_artist_list,
            delta_sec=config.get_config_param_as_int(constants.ConfigParam.CACHED_ARTIST_LIST_CACHE_TIMEOUT_SEC)):
        msgproc.log("subsonic_util.get_all_artists loading all artists ...")
        all_artists: list[Artist] = _load_all_artists()
        cached_all_artist_list = CachedArtistList()
        cached_all_artist_list.last_Artist_List = all_artists
        cached_all_artist_list.last_response_time = datetime.datetime.now()
        return all_artists
    else:
        return cached_all_artist_list.last_Artist_List


def _load_all_artists() -> list[Artist]:
    all_artist: list[Artist] = []
    finished: bool = False
    search_size: int = 1000
    search_offset: int = 0
    while not finished:
        msgproc.log(f"Executing search with offset [{search_offset}]")
        search_result: SearchResult = connector_provider.get().search(
            "",
            artistCount=search_size,
            songCount=0,
            albumCount=0,
            artistOffset=search_offset)
        artists: list[Artist] = search_result.getArtists()
        all_artist.extend(artists)
        ac: int = len(artists)
        search_offset += ac
        if ac < search_size:
            finished = True
    msgproc.log(f"Sorting [{len(all_artist)}] artists ...")
    return all_artist


def get_artists() -> Response[Artists]:
    global cached_response_artists
    if __cached_response_is_expired(
            cached=cached_response_artists,
            delta_sec=config.get_config_param_as_int(constants.ConfigParam.CACHED_REQUEST_TIMEOUT_SEC)):
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
        if __cached_response_is_expired(
                cached=cached_response_random_firstpage,
                delta_sec=config.get_config_param_as_int(constants.ConfigParam.CACHED_REQUEST_TIMEOUT_SEC)):
            msgproc.log(f"subsonic_util.get_random_album_list loading first [{config.get_items_per_page()}] random albums ...")
            # actually request first random albums
            res: Response[AlbumList] = connector_provider.get().getRandomAlbumList(size=config.get_items_per_page())
            cached_response_random_firstpage = CachedResponse()
            cached_response_random_firstpage.last_response_obj = res
            cached_response_random_firstpage.last_response_time = datetime.datetime.now()
            return res
        else:
            # use cached!
            msgproc.log(f"subsonic_util.get_random_album_list returning first [{config.get_items_per_page()}] using cached data.")
            return cached_response_random_firstpage.last_response_obj


def get_genres() -> Response[Genres]:
    global cached_response_genres
    if __cached_response_is_expired(
            cached=cached_response_genres,
            delta_sec=config.get_config_param_as_int(constants.ConfigParam.CACHED_REQUEST_TIMEOUT_SEC)):
        msgproc.log("subsonic_util.get_genres loading ...")
        # actually request genres
        res: Response[Genres] = connector_provider.get().getGenres()
        cached_response_genres = CachedResponse()
        cached_response_genres.last_response_obj = res
        cached_response_genres.last_response_time = datetime.datetime.now()
        msgproc.log(f"subsonic_util.get_genres finished loading [{len(res.getObj().getGenres())}] genres")
        return res
    else:
        # use cached!
        return cached_response_genres.last_response_obj


def get_first_newest_album_list() -> list[AlbumList]:
    global cached_response_newest
    if __cached_response_is_expired(
            cached=cached_response_newest,
            delta_sec=config.get_config_param_as_int(constants.ConfigParam.CACHED_REQUEST_TIMEOUT_SEC)):
        msgproc.log("subsonic_util.get_first_newest_album_list loading ...")
        # actually request genres
        res: Response[AlbumList] = connector_provider.get().getAlbumList(
            ltype=ListType.BY_YEAR,
            size=config.get_items_per_page(),
            fromYear=datetime.datetime.now().year,
            toYear=0)
        cached_response_newest = CachedResponse()
        cached_response_newest.last_response_obj = res
        cached_response_newest.last_response_time = datetime.datetime.now()
        msgproc.log(f"subsonic_util.get_first_newest_album_list finished loading [{len(res.getObj().getAlbums())}] albums")
        return res
    else:
        # use cached!
        msgproc.log("subsonic_util.get_first_newest_album_list using cached response")
        return cached_response_newest.last_response_obj
