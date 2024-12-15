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
from subsonic_connector.playlists import Playlists
from subsonic_connector.playlist import Playlist
from subsonic_connector.starred import Starred
from subsonic_connector.artist import Artist
from subsonic_connector.album import Album
from subsonic_connector.song import Song

from tag_type import TagType
from retrieved_art import RetrievedArt

import connector_provider
import request_cache

import secrets

from typing import Callable

import cmdtalkplugin
import datetime

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


def __get_cover_art_from_res_album_list(response: Response[AlbumList], random: bool = False) -> RetrievedArt:
    if not response.isOk() or len(response.getObj().getAlbums()) == 0:
        return None
    album_list: list[Album] = response.getObj().getAlbums()
    return __get_cover_art_from_album_list(album_list=album_list, random=random)


def __get_cover_art_from_album_list(album_list: list[Album], random: bool = False) -> RetrievedArt:
    if not album_list or len(album_list) == 0:
        return None
    album: Album = (secrets.choice(album_list)
                    if random
                    else album_list[0])
    album_url: str = connector_provider.get().buildCoverArtUrl(item_id=album.getId()) if album else None
    return RetrievedArt(art_url=album_url) if album_url else None


def group_albums_art_retriever() -> RetrievedArt:
    # try in favorites (pick random)
    art: str = favourite_albums_art_retriever()
    # else random album
    if not art:
        art = random_albums_art_retriever()
    return art


def group_artists_art_retriever() -> RetrievedArt:
    # try in favorites (pick random)
    art: RetrievedArt = favourite_artist_art_retriever()
    # else random album
    if not art:
        art = random_albums_art_retriever()
    return art


def group_songs_art_retriever() -> RetrievedArt:
    # try in favorites (pick random)
    art = __art_for_favourite_song(random=True)
    # else random
    if not art:
        art = random_albums_art_retriever()
    return art


def newest_albums_art_retriever() -> RetrievedArt:
    response: Response[AlbumList] = connector_provider.get().getAlbumList(
        ltype=ListType.BY_YEAR,
        size=1,
        fromYear=datetime.datetime.now().year,
        toYear=0)
    return __get_cover_art_from_res_album_list(response=response)


def recently_added_albums_art_retriever() -> RetrievedArt:
    response: Response[AlbumList] = connector_provider.get().getNewestAlbumList(size=1)
    return __get_cover_art_from_res_album_list(response=response)


def random_albums_art_retriever() -> RetrievedArt:
    response: Response[AlbumList] = request_cache.get_random_album_list()
    return __get_cover_art_from_res_album_list(response=response)


def recently_played_albums_art_retriever() -> RetrievedArt:
    response: Response[AlbumList] = connector_provider.get().getAlbumList(ltype=ListType.RECENT, size=1)
    return __get_cover_art_from_res_album_list(response=response)


def highest_rated_albums_art_retriever() -> RetrievedArt:
    response: Response[AlbumList] = connector_provider.get().getAlbumList(ltype=ListType.HIGHEST, size=1)
    return __get_cover_art_from_res_album_list(response=response)


def most_played_albums_art_retriever() -> RetrievedArt:
    response: Response[AlbumList] = connector_provider.get().getAlbumList(ltype=ListType.FREQUENT, size=1)
    return __get_cover_art_from_res_album_list(response=response)


def get_artist_art_url_using_albums(artist_id: str) -> str:
    # get an album cover for the artist entry
    artist_res: Response[Artist] = (connector_provider.get().getArtist(artist_id=artist_id)
                                    if artist_id
                                    else None)
    artist: Artist = artist_res.getObj() if artist_res and artist_res.isOk() else None
    msgproc.log(f"artist_entry_for_album loaded artist for id [{artist_id}] -> "
                f"[{'yes' if artist else 'no'}]")
    album_list: list[Album] = artist.getAlbumList() if artist else list()
    msgproc.log(f"artist_entry_for_album album_list len is [{len(album_list)}]")
    select_album: Album = secrets.choice(album_list) if len(album_list) > 0 else None
    # load album
    msgproc.log(f"artist_entry_for_album selected album: [{select_album.getId() if select_album else None}]")
    load_album_res: Response[Album] = (connector_provider.get().getAlbum(albumId=select_album.getId())
                                       if select_album
                                       else None)
    loaded_album: Album = load_album_res.getObj() if load_album_res and load_album_res.isOk() else None
    select_cover: str = loaded_album.getCoverArt() if loaded_album else None
    return connector_provider.get().buildCoverArtUrl(select_cover) if select_cover else None


def favourite_albums_art_retriever() -> RetrievedArt:
    fav: RetrievedArt = __favourite_albums_art_retriever()
    return fav if fav else random_albums_art_retriever()


def __favourite_albums_art_retriever() -> RetrievedArt:
    response: Response[Starred] = request_cache.get_starred()
    if not response.isOk():
        return None
    album_list: list[Album] = response.getObj().getAlbums()
    return __get_cover_art_from_album_list(album_list=album_list, random=True)


def favourite_artist_art_retriever() -> RetrievedArt:
    fav: RetrievedArt = __favourite_artist_art_retriever()
    msgproc.log(f"favourite_artist_art_retriever fav found: [{'yes' if fav else 'no'}]")
    return fav if fav is not None else random_albums_art_retriever()


def __favourite_artist_art_retriever() -> RetrievedArt:
    response: Response[Starred] = request_cache.get_starred()
    if not response.isOk():
        msgproc.log("__favourite_artist_art_retriever no starred artists")
        return None
    artist_list: list[Artist] = response.getObj().getArtists()
    select_artist: Artist = secrets.choice(artist_list) if artist_list and len(artist_list) > 0 else None
    msgproc.log("__favourite_artist_art_retriever selected artist "
                f"[{select_artist.getId() if select_artist else None}]")
    if not select_artist:
        return None
    art_url: str = get_artist_art_url_using_albums(artist_id=select_artist.getId())
    return RetrievedArt(art_url=art_url)


def favourite_song_retriever() -> RetrievedArt:
    fav: RetrievedArt = __favourite_song_retriever()
    return fav if fav else random_albums_art_retriever()


def __favourite_song_retriever() -> RetrievedArt:
    return __art_for_favourite_song(random=True)


def __art_for_favourite_song(random: bool = False) -> RetrievedArt:
    response: Response[Starred] = request_cache.get_starred()
    if not response.isOk():
        return None
    song_list: list[Song] = response.getObj().getSongs()
    if not song_list or len(song_list) == 0:
        return None
    select_song: Song = secrets.choice(song_list) if random else song_list[0]
    art_url: str = (connector_provider.get().buildCoverArtUrl(item_id=select_song.getId())
                    if select_song
                    else None)
    return RetrievedArt(art_url=art_url)


def playlists_art_retriever() -> RetrievedArt:
    response: Response[Playlists] = connector_provider.get().getPlaylists()
    if not response.isOk():
        msgproc.log("playlists_art_retriever - cannot get playlists")
        return None
    playlist_list: list[Playlist] = response.getObj().getPlaylists()
    if not playlist_list or len(playlist_list) == 0:
        msgproc.log("playlists_art_retriever - no playlists")
        return None
    select: Playlist = secrets.choice(playlist_list)
    if not select:
        msgproc.log("playlists_art_retriever - no playlist selected")
        return None
    art_url: str = (connector_provider.get().buildCoverArtUrl(select.getCoverArt())
                    if select and select.getCoverArt()
                    else None)
    return RetrievedArt(art_url=art_url)


def execute_art_retriever(tag: TagType) -> RetrievedArt:
    tagname: str = tag.getTagName()
    if tagname in __tag_art_retriever_dict:
        try:
            return __tag_art_retriever_dict[tagname]()
        except Exception as ex:
            msgproc.log(f"Cannot retrieve art for tag [{tagname}] [{type(ex)}] [{ex}]")


__tag_art_retriever_dict: dict[str, Callable[[], RetrievedArt]] = {
    TagType.ALBUMS.getTagName(): group_albums_art_retriever,
    TagType.ARTISTS.getTagName(): group_artists_art_retriever,
    TagType.SONGS.getTagName(): group_songs_art_retriever,
    TagType.RECENTLY_ADDED_ALBUMS.getTagName(): recently_added_albums_art_retriever,
    TagType.NEWEST_ALBUMS.getTagName(): newest_albums_art_retriever,
    TagType.RECENTLY_PLAYED_ALBUMS.getTagName(): recently_played_albums_art_retriever,
    TagType.HIGHEST_RATED_ALBUMS.getTagName(): highest_rated_albums_art_retriever,
    TagType.FAVOURITE_ALBUMS.getTagName(): favourite_albums_art_retriever,
    TagType.MOST_PLAYED_ALBUMS.getTagName(): most_played_albums_art_retriever,
    TagType.RANDOM.getTagName(): random_albums_art_retriever,
    TagType.RANDOM_SONGS.getTagName(): random_albums_art_retriever,
    TagType.RANDOM_SONGS_LIST.getTagName(): random_albums_art_retriever,
    TagType.GENRES.getTagName(): random_albums_art_retriever,
    TagType.ALL_ARTISTS.getTagName(): random_albums_art_retriever,
    TagType.ALL_ARTISTS_INDEXED.getTagName(): random_albums_art_retriever,
    TagType.FAVOURITE_ARTISTS.getTagName(): favourite_artist_art_retriever,
    TagType.PLAYLISTS.getTagName(): playlists_art_retriever,
    TagType.FAVOURITE_SONGS.getTagName(): favourite_song_retriever,
    TagType.FAVOURITE_SONGS_LIST.getTagName(): favourite_song_retriever
}
