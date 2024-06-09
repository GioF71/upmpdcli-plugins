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

from subsonic_connector.response import Response
from subsonic_connector.album_list import AlbumList
from subsonic_connector.list_type import ListType
from subsonic_connector.genres import Genres
from subsonic_connector.genre import Genre
from subsonic_connector.playlists import Playlists
from subsonic_connector.playlist import Playlist
from subsonic_connector.artist_cover import ArtistCover
from subsonic_connector.starred import Starred
from subsonic_connector.artist import Artist
from subsonic_connector.album import Album
from subsonic_connector.song import Song

from tag_type import TagType
from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey
from retrieved_art import RetrievedArt

import connector_provider
import request_cache

import config

import secrets

from typing import Callable

import cmdtalkplugin

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


def __get_cover_art_from_res_album_list(response : Response[AlbumList], random : bool = False) -> RetrievedArt:
    if not response.isOk() or len(response.getObj().getAlbums()) == 0: return None
    album_list: list[Album] = response.getObj().getAlbums()
    return __get_cover_art_from_album_list(album_list=album_list, random=random)


def __get_cover_art_from_album_list(album_list: list[Album], random: bool = False) -> RetrievedArt:
    if not album_list or len(album_list) == 0: return None
    album : Album = (secrets.choice(album_list)
        if random
        else album_list[0])
    return RetrievedArt(cover_art = album.getCoverArt())


def group_albums_art_retriever() -> RetrievedArt:
    # try in favorites (pick random)
    art : str = favourite_albums_art_retriever()
    # else random album
    if not art: art = random_albums_art_retriever()
    return art


def group_artists_art_retriever() -> RetrievedArt:
    # try in favorites (pick random)
    art : RetrievedArt = favourite_artist_art_retriever()
    # else random album
    if not art: art = random_albums_art_retriever()
    return art


def group_songs_art_retriever() -> RetrievedArt:
    # try in favorites (pick random)
    art = __art_for_favourite_song(random = True)
    # else random
    if not art: art = random_albums_art_retriever()
    return art


def newest_albums_art_retriever() -> RetrievedArt:
    response : Response[AlbumList] = connector_provider.get().getNewestAlbumList(size = 1)
    return __get_cover_art_from_res_album_list(response=response)


def random_albums_art_retriever() -> RetrievedArt:
    response : Response[AlbumList] = request_cache.get_random_album_list()
    return __get_cover_art_from_res_album_list(response = response)


def recently_played_albums_art_retriever() -> RetrievedArt:
    response : Response[AlbumList] = connector_provider.get().getAlbumList(ltype = ListType.RECENT, size = 1)
    return __get_cover_art_from_res_album_list(response = response)


def highest_rated_albums_art_retriever() -> RetrievedArt:
    response : Response[AlbumList] = connector_provider.get().getAlbumList(ltype = ListType.HIGHEST, size = 1)
    return __get_cover_art_from_res_album_list(response = response)


def most_played_albums_art_retriever() -> RetrievedArt:
    response : Response[AlbumList] = connector_provider.get().getAlbumList(ltype = ListType.FREQUENT, size = 1)
    return __get_cover_art_from_res_album_list(response = response)


def genres_art_retriever() -> RetrievedArt:
    response : Response[Genres] = request_cache.get_genres()
    if not response.isOk(): return None
    genre_list : list[Genre] = response.getObj().getGenres()
    select_genre : Genre = secrets.choice(genre_list)
    if not select_genre: return None
    return __genre_art_retriever(select_genre.getName())


def __genre_art_retriever(genre_name : str) -> RetrievedArt:
    response : Response[AlbumList] = connector_provider.get().getAlbumList(
        ltype = ListType.BY_GENRE,
        genre = genre_name,
        size = 1)
    return __get_cover_art_from_res_album_list(response = response)


def get_artist_art(artist_id : str) -> RetrievedArt:
    artist_cover : ArtistCover = connector_provider.get().getCoverByArtistId(artist_id)
    if not artist_cover: return None
    return (RetrievedArt(art_url = artist_cover.getArtistArtUrl())
        if artist_cover.getArtistArtUrl() and config.allow_artist_art
        else RetrievedArt(cover_art = artist_cover.getAlbumId()))


def favourite_albums_art_retriever() -> RetrievedArt:
    fav: RetrievedArt = __favourite_albums_art_retriever()
    if fav is None: return random_albums_art_retriever()


def __favourite_albums_art_retriever() -> RetrievedArt:
    response : Response[Starred] = request_cache.get_starred()
    if not response.isOk(): return None
    album_list : list[Album] = response.getObj().getAlbums()
    return __get_cover_art_from_album_list(album_list=album_list, random=False)


def favourite_artist_art_retriever() -> RetrievedArt:
    fav: RetrievedArt = __favourite_artist_art_retriever()
    if fav is None: return random_albums_art_retriever()


def __favourite_artist_art_retriever() -> RetrievedArt:
    response : Response[Starred] = request_cache.get_starred()
    if not response.isOk(): return None
    artist_list : list[Artist] = response.getObj().getArtists()
    select_artist : Artist = artist_list[0] if artist_list and len(artist_list) > 0 else None
    if not select_artist: return None
    return get_artist_art(select_artist.getId())


def favourite_song_retriever() -> RetrievedArt:
    fav: RetrievedArt = __favourite_song_retriever()
    if fav is None: return random_albums_art_retriever()


def __favourite_song_retriever() -> RetrievedArt:
    return __art_for_favourite_song(random=True)


def __art_for_favourite_song(random: bool = False) -> RetrievedArt:
    response : Response[Starred] = request_cache.get_starred()
    if not response.isOk(): return None
    song_list : list[Song] = response.getObj().getSongs()
    if not song_list or len(song_list) == 0: return None
    select_song : Song = secrets.choice(song_list) if random else song_list[0]
    return RetrievedArt(cover_art = select_song.getId())


def playlists_art_retriever() -> RetrievedArt:
    response : Response[Playlists] = connector_provider.get().getPlaylists()
    if not response.isOk(): return None
    playlist_list : list[Playlist] = response.getObj().getPlaylists()
    if not playlist_list or len(playlist_list) == 0: return None
    select : Playlist = secrets.choice(playlist_list)
    if not select: return None
    return RetrievedArt(cover_art = select.getCoverArt())


def artist_art_retriever(item_identifier : ItemIdentifier) -> RetrievedArt:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    return get_artist_art(artist_id)


tag_art_retriever : dict[str, Callable[[], RetrievedArt]] = {
    TagType.ALBUMS.getTagName(): group_albums_art_retriever,
    TagType.ARTISTS.getTagName(): group_artists_art_retriever,
    TagType.SONGS.getTagName(): group_songs_art_retriever,
    TagType.NEWEST.getTagName(): newest_albums_art_retriever,
    TagType.RECENTLY_PLAYED.getTagName(): recently_played_albums_art_retriever,
    TagType.HIGHEST_RATED.getTagName(): highest_rated_albums_art_retriever,
    TagType.FAVOURITES.getTagName(): favourite_albums_art_retriever,
    TagType.MOST_PLAYED.getTagName(): most_played_albums_art_retriever,
    TagType.RANDOM.getTagName(): random_albums_art_retriever,
    TagType.RANDOM_SONGS.getTagName(): random_albums_art_retriever,
    TagType.RANDOM_SONGS_LIST.getTagName(): random_albums_art_retriever,
    TagType.GENRES.getTagName(): genres_art_retriever,
    TagType.ALL_ARTISTS.getTagName(): random_albums_art_retriever,
    TagType.ALBUM_ARTISTS.getTagName(): random_albums_art_retriever,
    TagType.ALBUM_ARTISTS_INDEXED.getTagName(): random_albums_art_retriever,
    TagType.ALL_ARTISTS_INDEXED.getTagName(): random_albums_art_retriever,
    TagType.FAVOURITE_ARTISTS.getTagName(): favourite_artist_art_retriever,
    TagType.PLAYLISTS.getTagName(): playlists_art_retriever,
    TagType.FAVOURITE_SONGS.getTagName(): favourite_song_retriever,
    TagType.FAVOURITE_SONGS_LIST.getTagName(): favourite_song_retriever
}
