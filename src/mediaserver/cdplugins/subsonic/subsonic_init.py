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

from tag_type import TagType
from element_type import ElementType

import config
import subsonic_util

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

def subsonic_init():
    msgproc.log(f"Subsonic Initializing ...")
    init_success : bool = False
    try:
        initial_caching()
        check_supports()
        init_success = True
    except Exception as e:
        msgproc.log(f"Subsonic Initialization failed [{e}]")
    msgproc.log(f"Subsonic Initialization success: [{init_success}]")

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
    genres_response : Response[Genres] = connector_provider.get().getGenres()
    if not genres_response.isOk(): return
    genre_list = genres_response.getObj().getGenres()
    for current_genre in genre_list:
        genre : str = current_genre.getName()
        if genre: load_single_genre(genre)

def load_single_genre(genre : str):
    msgproc.log(f"Processing genre [{genre}]")
    if cache_manager_provider.get().is_element_cached(ElementType.GENRE, genre):
        #msgproc.log(f"Genre [{genre}] already has art, skipping")
        return
    msgproc.log(f"Genre {genre} has not art yet, looking for an album")
    # pick an album for the genre
    album_list_res : Response[AlbumList] = connector_provider.get().getAlbumList(
        ltype = ListType.BY_GENRE, 
        size = config.subsonic_max_return_size, 
        genre = genre)
    if album_list_res.isOk() and album_list_res.getObj() and len(album_list_res.getObj().getAlbums()) > 0:
        album_list : AlbumList = album_list_res.getObj()
        album : Album = secrets.choice(album_list.getAlbums())
        if album:
            msgproc.log(f"Caching genre [{genre}] with album_id [{album.getId()}]")
            cache_manager_provider.get().cache_element_value(ElementType.GENRE, genre, album.getId())

def load_by_newest():
    sz : int = None
    album_list : list[Album] = None
    offset : int = 0
    total_albums : int = 0
    first_processed : bool = False
    while not album_list or len(album_list) == config.subsonic_max_return_size:
        album_list = subsonic_util.get_albums(TagType.NEWEST.getQueryType(), size = config.subsonic_max_return_size, offset = offset)
        total_albums += len(album_list)
        msgproc.log(f"loaded {total_albums} albums ...")
        album : Album
        for album in album_list:
            if not first_processed:
                # action to do once
                cache_manager_provider.get().cache_element_value(ElementType.TAG, TagType.GENRES.getTagName(), album.getId())
                cache_manager_provider.get().cache_element_value(ElementType.TAG, TagType.ARTISTS_ALL.getTagName(), album.getId())
                cache_manager_provider.get().cache_element_value(ElementType.TAG, TagType.ARTISTS_INDEXED.getTagName(), album.getId())
                first_processed = True
            # for every album
            genre : str = album.getGenre()
            if not cache_manager_provider.get().is_element_cached(ElementType.GENRE, genre):
                cache_manager_provider.get().cache_element_value(ElementType.GENRE, genre, album.getId())
            artist_id : str = album.getArtistId()
            if not cache_manager_provider.get().is_element_cached(ElementType.ARTIST, artist_id):
                cache_manager_provider.get().cache_element_value(ElementType.ARTIST, artist_id, album.getId())
        offset += len(album_list)

def load_by_artist_initial(current_artists_initial : ArtistsInitial):
    artist_list_items : list[ArtistListItem] = current_artists_initial.getArtistListItems()
    if len(artist_list_items) == 0: return
    current : ArtistListItem
    for current in artist_list_items:
        artist_id : str = current.getId()
        if cache_manager_provider.get().is_element_cached(ElementType.ARTIST, artist_id):
            artist_album_id : str = cache_manager_provider.get().get_cached_element(ElementType.ARTIST, artist_id)
            cache_manager_provider.get().cache_element_value(ElementType.ARTIST_INITIAL, current_artists_initial.getName(), artist_album_id)
            return

def load_by_artists():
    #create art cache for artists by initial
    artists_response : Response[Artists] = connector_provider.get().getArtists()
    if not artists_response.isOk(): return
    artists_initial : list[ArtistsInitial] = artists_response.getObj().getArtistListInitials()
    current_artists_initial : ArtistsInitial
    for current_artists_initial in artists_initial:
        load_by_artist_initial(current_artists_initial)

