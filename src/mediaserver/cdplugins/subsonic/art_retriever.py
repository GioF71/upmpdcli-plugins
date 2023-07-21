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

from subsonic_connector.response import Response
from subsonic_connector.album_list import AlbumList
from subsonic_connector.list_type import ListType
from subsonic_connector.genres import Genres
from subsonic_connector.genre import Genre
from subsonic_connector.artists import Artists
from subsonic_connector.artists_initial import ArtistsInitial
from subsonic_connector.artist_list_item import ArtistListItem
from subsonic_connector.playlists import Playlists
from subsonic_connector.playlist import Playlist
from subsonic_connector.artist_cover import ArtistCover
from subsonic_connector.starred import Starred
from subsonic_connector.artist import Artist
from subsonic_connector.song import Song

from tag_type import TagType
from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey

import connector_provider

import secrets

def __get_cover_art_from_album_list(response : Response[AlbumList], random : bool = False) -> str:
    if not response.isOk() or len(response.getObj().getAlbums()) == 0: return None
    return secrets.choice(response.getObj().getAlbums()).getCoverArt() if random else response.getObj().getAlbums()[0].getCoverArt()

def group_albums_art_retriever() -> str:
    # try favourite
    art : str = favourite_albums_art_retriever(random_range = 500, random = True)
    # else random
    if not art: art = random_albums_art_retriever()
    return art

def group_artists_art_retriever() -> str:
    # try favourite
    art : str = favourite_artist_art_retriever()
    # else random
    if not art: art = random_artist_art_retriever()
    return art

def group_songs_art_retriever() -> str:
    # try favourite
    art : str = get_favourite_song_id(random = True)
    # else random
    if not art: art = random_albums_art_retriever()
    return art

def newest_albums_art_retriever() -> str:
    response : Response[AlbumList] = connector_provider.get().getNewestAlbumList(size = 1)
    return __get_cover_art_from_album_list(response = response)

def random_albums_art_retriever() -> str:
    response : Response[AlbumList] = connector_provider.get().getRandomAlbumList(size = 1)
    return __get_cover_art_from_album_list(response = response)

def recently_played_albums_art_retriever() -> str:
    response : Response[AlbumList] = connector_provider.get().getAlbumList(ltype = ListType.RECENT, size = 1)
    return __get_cover_art_from_album_list(response = response)

def highest_rated_albums_art_retriever() -> str:
    response : Response[AlbumList] = connector_provider.get().getAlbumList(ltype = ListType.HIGHEST, size = 1)
    return __get_cover_art_from_album_list(response = response)

def favourite_albums_art_retriever(random_range : int = 1, random : bool = False) -> str:
    response : Response[AlbumList] = connector_provider.get().getAlbumList(ltype = ListType.STARRED, size = random_range)
    return __get_cover_art_from_album_list(response = response, random = random)

def most_played_albums_art_retriever() -> str:
    response : Response[AlbumList] = connector_provider.get().getAlbumList(ltype = ListType.FREQUENT, size = 1)
    return __get_cover_art_from_album_list(response = response)

def genres_art_retriever() -> str:
    response : Response[Genres] = connector_provider.get().getGenres()
    if not response.isOk(): return None
    genre_list : list[Genre] = response.getObj().getGenres()
    select_genre : Genre = secrets.choice(genre_list)
    if not select_genre: return None
    return __genre_art_retriever(select_genre.getName())

def __genre_art_retriever(genre_name : str) -> str:
    response : Response[AlbumList] = connector_provider.get().getAlbumList(
        ltype = ListType.BY_GENRE, 
        genre = genre_name, 
        size = 1)
    return __get_cover_art_from_album_list(response = response)

def __get_random_artist_cover_by_initial(artists_initial : ArtistsInitial) -> str:
    artist_list_item_list : list[ArtistListItem] = artists_initial.getArtistListItems()
    select_artist_list_item : ArtistListItem = secrets.choice(artist_list_item_list)
    if not select_artist_list_item: return None
    artist_id : str = select_artist_list_item.getId()
    return get_artist_cover(artist_id)

def _get_random_artist_cover() -> str:
    response : Response[Artists] = connector_provider.get().getArtists()
    if not response.isOk(): return None
    artist_initial_list : list[ArtistsInitial] = response.getObj().getArtistListInitials()
    select_initial : ArtistsInitial = secrets.choice(artist_initial_list)
    if not select_initial: return None
    return __get_random_artist_cover_by_initial(select_initial)

def get_artist_cover(artist_id : str) -> str:
    artist_cover : ArtistCover = connector_provider.get().getCoverByArtistId(artist_id)
    if not artist_cover: return None
    return artist_cover.getCoverArt()

def random_artist_art_retriever() -> str:
    return _get_random_artist_cover()

def favourite_artist_art_retriever() -> str:
    response : Response[Starred] = connector_provider.get().getStarred()
    if not response.isOk(): return None
    artist_list : list[Artist] = response.getObj().getArtists()
    select_artist : Artist = artist_list[0] if artist_list and len(artist_list) > 0 else None
    if not select_artist: return None
    return get_artist_cover(select_artist.getId())

def favourite_song_retriever() -> str:
    return get_favourite_song_id(random = True)

def get_favourite_song_id(random : bool = False) -> str:
    response : Response[Starred] = connector_provider.get().getStarred()
    if not response.isOk(): return None
    song_list : list[Song] = response.getObj().getSongs()
    if not song_list or len(song_list) == 0: return None
    select_song : Song = secrets.choice(song_list) if random else song_list[0]
    return select_song.getId()

def playlists_art_retriever() -> str:
    response : Response[Playlists] = connector_provider.get().getPlaylists()
    if not response.isOk(): return None
    playlist_list : list[Playlist] = response.getObj().getPlaylists()
    select : Playlist = secrets.choice(playlist_list)
    if not select: return None
    return select.getCoverArt()

def _get_artist_initial(initial_list : list[ArtistsInitial], initial_name : str) -> ArtistsInitial:
    current : ArtistsInitial
    for current in initial_list:
        if current.getName() == initial_name: return current

def artist_art_retriever(item_identifier : ItemIdentifier) -> str:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    return get_artist_cover(artist_id)

def artist_initial_art_retriever(item_identifier : ItemIdentifier) -> str:
    initial_name : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    response : Response[Artists] = connector_provider.get().getArtists()
    if not response.isOk(): return None
    artist_initial_list : list[ArtistsInitial] = response.getObj().getArtistListInitials()
    select : ArtistsInitial = _get_artist_initial(artist_initial_list, initial_name)
    if not select: return None
    return __get_random_artist_cover_by_initial(select)

tag_art_retriever : dict[str, any] = {
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
    TagType.ARTISTS_ALL.getTagName(): random_artist_art_retriever,
    TagType.ARTISTS_INDEXED.getTagName(): random_artist_art_retriever,
    TagType.FAVOURITE_ARTISTS.getTagName(): favourite_artist_art_retriever,
    TagType.PLAYLISTS.getTagName(): playlists_art_retriever,
    TagType.FAVOURITE_SONGS.getTagName(): favourite_song_retriever,
    TagType.FAVOURITE_SONGS_LIST.getTagName(): favourite_song_retriever
}
