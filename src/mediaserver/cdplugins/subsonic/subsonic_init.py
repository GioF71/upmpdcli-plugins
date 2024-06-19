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

from tag_type import TagType
from element_type import ElementType

import config
import subsonic_util
import request_cache

from subsonic_connector.response import Response
from subsonic_connector.list_type import ListType
from subsonic_connector.artist_list_item import ArtistListItem
from subsonic_connector.album_list import AlbumList
from subsonic_connector.artists_initial import ArtistsInitial
from subsonic_connector.album import Album
from subsonic_connector.genres import Genres
from subsonic_connector.artists import Artists
from subsonic_connector.internet_radio_stations import InternetRadioStations

import connector_provider
import cache_manager_provider
from msgproc_provider import msgproc

import secrets
import constants
import upmplgutils
import persistence


def subsonic_init():
    msgproc.log(f"Subsonic [{constants.subsonic_plugin_release}] Initializing ...")
    init_success : bool = False
    try:
        cache_dir : str = upmplgutils.getcachedir(constants.plugin_name)
        msgproc.log(f"Cache dir for [{constants.plugin_name}] is [{cache_dir}]")
        msgproc.log(f"DB version for [{constants.plugin_name}] is [{persistence.get_db_version()}]")
        initial_caching()
        check_supports()
        detect_anomalies()
        init_success = True
    except Exception as e:
        msgproc.log(f"Subsonic [{constants.subsonic_plugin_release}] Initialization failed [{e}]")
    msgproc.log(f"Subsonic [{constants.subsonic_plugin_release}] Initialization success: [{init_success}]")


def detect_anomalies():
    detect_multiple_artists()


class ArtistOccurrence:
    artist_id: str
    mb_id: str
    artist_name: str


def detect_multiple_artists():
    res: Response[Artists] = request_cache.get_artists()
    initial_list: list[ArtistsInitial] = res.getObj().getArtistListInitials() if res and res.isOk() else None
    if initial_list is None:
        msgproc.log(f"No [{ArtistsInitial.__name__}]")
        return
    artist_dict: dict[str, list[ArtistOccurrence]] = dict()
    curr_initial: ArtistsInitial
    for curr_initial in initial_list:
        msgproc.log(f"Processing [{ArtistsInitial.__name__}] [{curr_initial.getName()}]")
        ali_list: list[ArtistListItem] = curr_initial.getArtistListItems()
        curr_artist: ArtistListItem
        for curr_artist in ali_list:
            artist_id: str = curr_artist.getId()
            artist_name: str = curr_artist.getName().lower()
            mb_id = curr_artist.getItem().getByName("musicBrainzId")
            existing: list[ArtistOccurrence] = artist_dict[artist_name] if artist_name in artist_dict else list()
            # there must not be artist_id duplicates!
            if artist_id in existing:
                raise Exception(f"Multiple artist_id [{artist_id}]")
            occ: ArtistOccurrence = ArtistOccurrence()
            occ.artist_id = artist_id
            occ.artist_name = artist_name
            occ.mb_id = mb_id
            existing.append(occ)
            artist_dict[artist_name] = existing
    # count by name
    k: str
    v_occ_list: list[ArtistOccurrence]
    for k, v_occ_list in artist_dict.items():
        if len(v_occ_list) > 1:
            msgproc.log(f"Duplicate artists for artist_name:[{k}]")
            occ: ArtistOccurrence
            for occ in v_occ_list:
                msgproc.log(f"\tartist_id:[{occ.artist_id}] mb_id:[{occ.mb_id}]")


def check_supports():
    check_supports_highest()
    check_supports_internet_radios()


def check_supports_highest():
    # see if there is support for highest in getAlbumLists2
    supported : bool = False
    try:
        res : Response[AlbumList] = connector_provider.get().getAlbumList(ltype = ListType.HIGHEST, size = 1)
        if res and res.isOk():
            # supported!
            supported = True
    except Exception as ex:
        msgproc.log(f"check_supports_highest highest not supported [{type(ex)}] [{ex}]")
    msgproc.log(f"highest type in getAlbumList supported: [{'yes' if supported else 'no'}]")
    if not supported: config.album_list_by_highest_supported = False


def check_supports_internet_radios():
    # see if there is support for highest in getAlbumLists2
    supported : bool = False
    try:
        res : Response[InternetRadioStations] = connector_provider.get().getInternetRadioStations()
        if res and res.isOk():
            # supported!
            supported = True
    except Exception as ex:
        msgproc.log(f"check_supports_highest highest not supported [{type(ex)}] [{ex}]")
    msgproc.log(f"Internet Radio stations supported: [{'yes' if supported else 'no'}]")
    if not supported: config.internet_radio_stations_supported = False


def initial_caching():
    load_by_newest()
    load_by_artists()
    load_genres()


def load_genres():
    genres_response : Response[Genres] = request_cache.get_genres()
    if not genres_response.isOk(): return
    genre_list = genres_response.getObj().getGenres()
    for current_genre in genre_list if genre_list and len(genre_list) > 0 else list():
        genre : str = current_genre.getName()
        if genre: load_single_genre(genre)


def load_single_genre(genre : str):
    msgproc.log(f"Processing genre [{genre}]")
    if cache_manager_provider.get().is_element_cached(ElementType.GENRE, genre):
        # msgproc.log(f"Genre [{genre}] already has art, skipping")
        return
    msgproc.log(f"Genre {genre} has not art yet, looking for an album")
    # pick an album for the genre
    album_list_res : Response[AlbumList] = connector_provider.get().getAlbumList(
        ltype = ListType.BY_GENRE,
        size = constants.subsonic_max_return_size,
        genre = genre)
    if album_list_res.isOk() and album_list_res.getObj() and len(album_list_res.getObj().getAlbums()) > 0:
        album_list : AlbumList = album_list_res.getObj()
        album : Album = secrets.choice(album_list.getAlbums())
        if not album: return
        genre_list : list[str] = album.getGenres()
        cache_manager_provider.get().on_album_for_genre_list(album, genre_list)


def load_by_newest():
    album_list : list[Album] = None
    offset : int = 0
    total_albums : int = 0
    while not album_list or len(album_list) == constants.subsonic_max_return_size:
        album_list = subsonic_util.get_albums(
            query_type = TagType.RECENTLY_ADDED_ALBUMS.getQueryType(),
            size = constants.subsonic_max_return_size,
            offset = offset)
        total_albums += len(album_list)
        msgproc.log(f"loaded {total_albums} albums ...")
        album : Album
        for album in album_list:
            # for every album
            cache_manager_provider.get().on_album(album)
        offset += len(album_list)


def load_by_artist_initial(current_artists_initial : ArtistsInitial):
    artist_list_items : list[ArtistListItem] = current_artists_initial.getArtistListItems()
    if len(artist_list_items) == 0: return
    current : ArtistListItem
    for current in artist_list_items:
        artist_id : str = current.getId()
        if cache_manager_provider.get().is_album_artist(artist_id):
            cache_manager_provider.get().cache_element_multi_value(
                ElementType.ARTIST_BY_INITIAL,
                current_artists_initial.getName(),
                artist_id)


def load_by_artists():
    # create art cache for artists by initial
    artists_response : Response[Artists] = connector_provider.get().getArtists()
    if not artists_response.isOk(): return
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
        load_by_artist_initial(current_artists_initial)
