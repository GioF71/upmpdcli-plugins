from subsonic_connector.connector import Connector
from subsonic_connector.response import Response
from subsonic_connector.album_list import AlbumList
from subsonic_connector.list_type import ListType
from subsonic_connector.genres import Genres
from subsonic_connector.genre import Genre
from subsonic_connector.artists import Artists
from subsonic_connector.artists_initial import ArtistsInitial
from subsonic_connector.artist_list_item import ArtistListItem
from subsonic_connector.artist import Artist
from subsonic_connector.album import Album
from subsonic_connector.playlists import Playlists
from subsonic_connector.playlist import Playlist
from subsonic_connector.artist_cover import ArtistCover

from tag_type import TagType
from element_type import ElementType
from item_identifier import ItemIdentifier
from item_identifier_key import ItemIdentifierKey

from config import subsonic_max_return_size

import secrets

def _get_cover_art_from_first_album(response : Response[AlbumList]) -> str:
    if not response.isOk() or len(response.getObj().getAlbums()) == 0: return None
    return response.getObj().getAlbums()[0].getCoverArt()

def newest_albums_art_retriever(connector : Connector) -> str:
    response : Response[AlbumList] = connector.getNewestAlbumList(size = 1)
    return _get_cover_art_from_first_album(response)

def random_albums_art_retriever(connector : Connector) -> str:
    response : Response[AlbumList] = connector.getRandomAlbumList(size = 1)
    return _get_cover_art_from_first_album(response)

def recently_played_albums_art_retriever(connector : Connector) -> str:
    response : Response[AlbumList] = connector.getAlbumList(ltype = ListType.RECENT, size = 1)
    return _get_cover_art_from_first_album(response)

def highest_rated_albums_art_retriever(connector : Connector) -> str:
    response : Response[AlbumList] = connector.getAlbumList(ltype = ListType.HIGHEST, size = 1)
    return _get_cover_art_from_first_album(response)

def favourite_albums_art_retriever(connector : Connector) -> str:
    response : Response[AlbumList] = connector.getAlbumList(ltype = ListType.STARRED, size = 1)
    return _get_cover_art_from_first_album(response)

def most_played_albums_art_retriever(connector : Connector) -> str:
    response : Response[AlbumList] = connector.getAlbumList(ltype = ListType.FREQUENT, size = 1)
    return _get_cover_art_from_first_album(response)

def genres_art_retriever(connector : Connector) -> str:
    response : Response[Genres] = connector.getGenres()
    if not response.isOk(): return None
    genre_list : list[Genre] = response.getObj().getGenres()
    select_genre : Genre = secrets.choice(genre_list)
    if not select_genre: return None
    return _genre_art_retriever(connector, select_genre.getName())

def _genre_art_retriever(connector : Connector, genre_name : str) -> str:
    response : Response[AlbumList] = connector.getAlbumList(
        ltype = ListType.BY_GENRE, 
        genre = genre_name, 
        size = 1)
    return _get_cover_art_from_first_album(response)

def _get_random_artist_cover_by_initial(connector : Connector, artists_initial : ArtistsInitial) -> str:
    artist_list_item_list : list[ArtistListItem] = artists_initial.getArtistListItems()
    select_artist_list_item : ArtistListItem = secrets.choice(artist_list_item_list)
    if not select_artist_list_item: return None
    artist_id : str = select_artist_list_item.getId()
    return _get_artist_cover(connector, artist_id)

def _get_random_artist_cover(connector : Connector) -> str:
    response : Response[Artists] = connector.getArtists()
    if not response.isOk(): return None
    artist_initial_list : list[ArtistsInitial] = response.getObj().getArtistListInitials()
    select_initial : ArtistsInitial = secrets.choice(artist_initial_list)
    if not select_initial: return None
    return _get_random_artist_cover_by_initial(connector, select_initial)

def _get_artist_cover(connector : Connector, artist_id : str) -> str:
    artist_cover : ArtistCover = connector.getCoverByArtistId(artist_id)
    if not artist_cover: return None
    return artist_cover.getCoverArt()

def random_artist_art_retriever(connector : Connector) -> str:
    return _get_random_artist_cover(connector)

def playlists_art_retriever(connector : Connector) -> str:
    response : Response[Playlists] = connector.getPlaylists()
    if not response.isOk(): return None
    playlist_list : list[Playlist] = response.getObj().getPlaylists()
    select : Playlist = secrets.choice(playlist_list)
    if not select: return None
    return select.getCoverArt()

def _get_artist_initial(initial_list : list[ArtistsInitial], initial_name : str) -> ArtistsInitial:
    current : ArtistsInitial
    for current in initial_list:
        if current.getName() == initial_name: return current

def artist_art_retriever(connector : Connector, item_identifier : ItemIdentifier) -> str:
    artist_id : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    return _get_artist_cover(connector, artist_id)

def artist_initial_art_retriever(connector : Connector, item_identifier : ItemIdentifier) -> str:
    initial_name : str = item_identifier.get(ItemIdentifierKey.THING_VALUE)
    response : Response[Artists] = connector.getArtists()
    if not response.isOk(): return None
    artist_initial_list : list[ArtistsInitial] = response.getObj().getArtistListInitials()
    select : ArtistsInitial = _get_artist_initial(artist_initial_list, initial_name)
    if not select: return None
    return _get_random_artist_cover_by_initial(connector, select)

def art_by_artist_initial_dict_creator(connector : Connector) -> dict[str, str]:
    result : dict[str, str] = {}
    art_by_artist : dict[str, str] = art_by_artist_dict_creator(connector)
    response : Response[Artists] = connector.getArtists()
    if not response.isOk(): raise Exception(f"Failed to load call getArtists")
    ai_list : list[ArtistsInitial] = response.getObj().getArtistListInitials()
    ai : ArtistsInitial
    for ai in ai_list:
        ali_list : list[ArtistListItem] = ai.getArtistListItems()
        select : ArtistListItem = secrets.choice(ali_list)
        if select: result[ai.getName()] = art_by_artist[select.getId()]
    return result

def art_by_artist_dict_creator(connector : Connector) -> dict[str, str]:
    art_by_artist_id : dict[str, str] = {}
    album_list : list[Album] = None
    offset : int = 0
    while not album_list or len(album_list) == subsonic_max_return_size:
        album_list_response : Response[AlbumList] = connector.getAlbumList(
            ltype = ListType.NEWEST,
            size = subsonic_max_return_size,
            offset = offset)
        if not album_list_response.isOk(): raise Exception(f"Failed to load newest albums with offset {offset}")
        album_list : list[Album] = album_list_response.getObj().getAlbums()
        album : Album
        for album in album_list:
            artist_id : str = album.getArtistId()
            if not artist_id in art_by_artist_id:
                art_by_artist_id[artist_id] = album.getId()
        offset += len(album_list)
    return art_by_artist_id

tag_art_retriever : dict[str, any] = {
    TagType.NEWEST.getTagName(): newest_albums_art_retriever,
    TagType.RECENTLY_PLAYED.getTagName(): recently_played_albums_art_retriever,
    TagType.HIGHEST_RATED.getTagName(): highest_rated_albums_art_retriever,
    TagType.FAVOURITES.getTagName(): favourite_albums_art_retriever,
    TagType.MOST_PLAYED.getTagName(): most_played_albums_art_retriever,
    TagType.RANDOM.getTagName(): random_albums_art_retriever,
    TagType.GENRES.getTagName(): genres_art_retriever,
    TagType.ARTISTS_ALL.getTagName(): random_artist_art_retriever,
    TagType.ARTISTS_INDEXED.getTagName(): random_artist_art_retriever,
    TagType.PLAYLISTS.getTagName(): playlists_art_retriever
}

element_art_retriever : dict[str, any] = {
    ElementType.ARTIST_INITIAL.getName(): artist_initial_art_retriever,
    ElementType.ARTIST.getName(): artist_art_retriever
}