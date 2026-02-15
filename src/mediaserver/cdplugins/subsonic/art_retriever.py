# Copyright (C) 2023,2024,2025,2026 Giovanni Fulco
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

from persistence_tuple import ArtistAlbumCoverArt
from tag_type import TagType
from retrieved_art import RetrievedArt

from tag_to_entry_context import TagToEntryContext

import connector_provider
import request_cache
import subsonic_util
import cache_actions
import persistence
import config
import constants

import secrets

from typing import Callable
from msgproc_provider import msgproc


def _get_cover_art_from_res_album_list(response: Response[AlbumList], random: bool = False) -> RetrievedArt:
    if not response.isOk() or len(response.getObj().getAlbums()) == 0:
        return None
    album_list: list[Album] = response.getObj().getAlbums()
    return __get_cover_art_from_album_list(album_list=album_list, random=random)


def __get_cover_art_from_album_list(album_list: list[Album], random: bool = False) -> RetrievedArt:
    album_list = _filter_album_without_cover_art(album_list=album_list)
    if not album_list or len(album_list) == 0:
        return None
    album: Album = (secrets.choice(album_list)
                    if random
                    else album_list[0])
    album_url: str = subsonic_util.build_cover_art_url(item_id=album.getCoverArt()) if album else None
    return RetrievedArt(art_url=album_url) if album_url else None


def _filter_album_without_cover_art(album_list: list[Album]) -> list[Album]:
    return (list(filter(lambda x: x.getCoverArt() is not None and len(x.getCoverArt()) > 0, album_list))
            if album_list
            else [])


def consume_random_album_for_cover_art(tag_to_entry_context: TagToEntryContext = None) -> Album:
    if tag_to_entry_context is None:
        msgproc.log("consume_random_album_for_cover_art cannot return an album because a context is not available")
        return None
    random_album_list: list[Album] = tag_to_entry_context.random_album_list
    msgproc.log(f"Albums available in tagToEntryContext [{len(random_album_list)}] ...")
    select_album: Album = None
    while not select_album and len(random_album_list) > 0:
        select: Album = random_album_list.pop(0)
        # does the album have a cover art?
        if select.getCoverArt() is not None:
            msgproc.log(f"consume_random_album_for_cover_art consumed album [{select.getId()}] [{select.getTitle()}] "
                        f"by [{subsonic_util.get_album_display_artist(album=select)}]")
            return select
        else:
            msgproc.log(f"Skipping album [{select.getId()}] [{select.getTitle()}] "
                        f"from [{subsonic_util.get_album_display_artist(album=select)}] (no cover art)")
    msgproc.log("consume_random_album_for_cover_art cannot not return an album")
    return None


def group_albums_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    msgproc.log(f"group_albums_art_retriever tag_to_entry_context is set: [{tag_to_entry_context is not None}]")
    # try in favorites (pick random), if allowed
    art: RetrievedArt = (favourite_albums_art_retriever()
                         if config.get_config_param_as_bool(constants.ConfigParam.ALLOW_FAVORITES_FOR_FRONT_PAGE_TAGS)
                         else None)
    # else random album from context, if available
    random_album: Album = consume_random_album_for_cover_art(tag_to_entry_context=tag_to_entry_context)
    # set RetrievedArt if album is found
    art = (RetrievedArt(art_url=subsonic_util.build_cover_art_url(item_id=random_album.getCoverArt()))
           if random_album
           else None)
    # else random
    if not art:
        art = random_albums_art_retriever()
    return art


def group_artists_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    # try in favorites (pick random)
    art: RetrievedArt = (favourite_artist_art_retriever()
                         if config.get_config_param_as_bool(constants.ConfigParam.ALLOW_FAVORITES_FOR_FRONT_PAGE_TAGS)
                         else None)
    # else random album from context, if available
    random_album: Album = consume_random_album_for_cover_art(tag_to_entry_context=tag_to_entry_context)
    # set RetrievedArt if album is found
    art = (RetrievedArt(art_url=subsonic_util.build_cover_art_url(item_id=random_album.getCoverArt()))
           if random_album
           else None)
    if not art:
        art = random_albums_art_retriever()
    return art


def group_songs_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    # try in favorites (pick random)
    art: RetrievedArt = (_art_for_favourite_song(random=True)
                         if config.get_config_param_as_bool(constants.ConfigParam.ALLOW_FAVORITES_FOR_FRONT_PAGE_TAGS)
                         else None)
    # else random album from context, if available
    random_album: Album = consume_random_album_for_cover_art(tag_to_entry_context=tag_to_entry_context)
    # set RetrievedArt if album is found
    art = (RetrievedArt(art_url=subsonic_util.build_cover_art_url(item_id=random_album.getCoverArt()))
           if random_album
           else None)
    # else random
    if not art:
        art = random_albums_art_retriever()
    return art


def newest_albums_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    response: Response[AlbumList] = request_cache.get_first_newest_album_list()
    return _get_cover_art_from_res_album_list(response=response, random=False)


def recently_added_albums_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    response: Response[AlbumList] = connector_provider.get().getNewestAlbumList(size=1)
    return _get_cover_art_from_res_album_list(response=response)


def random_albums_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    random_album_from_context: Album = consume_random_album_for_cover_art(tag_to_entry_context=tag_to_entry_context)
    if random_album_from_context:
        return RetrievedArt(art_url=subsonic_util.build_cover_art_url(item_id=random_album_from_context.getCoverArt()))
    response: Response[AlbumList] = request_cache.get_random_album_list(size=config.get_items_per_page())
    return _get_cover_art_from_res_album_list(response=response, random=True)


def recently_played_albums_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    response: Response[AlbumList] = connector_provider.get().getAlbumList(ltype=ListType.RECENT, size=1)
    return _get_cover_art_from_res_album_list(response=response)


def highest_rated_albums_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    response: Response[AlbumList] = connector_provider.get().getAlbumList(ltype=ListType.HIGHEST, size=1)
    return _get_cover_art_from_res_album_list(response=response)


def most_played_albums_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    response: Response[AlbumList] = connector_provider.get().getAlbumList(ltype=ListType.FREQUENT, size=1)
    return _get_cover_art_from_res_album_list(response=response)


def get_album_cover_art_uri_by_artist(artist: Artist, force_save: bool = False) -> str:
    # best option, the artist has its coverArt
    artist_cover_art: str = subsonic_util.get_artist_cover_art(artist=artist)
    if artist_cover_art:
        return subsonic_util.build_cover_art_url(item_id=artist_cover_art, force_save=force_save)
    # maybe look at the albums if available
    album_list: list[Album] = artist.getAlbumList()
    if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
        msgproc.log(f"get_album_cover_art_uri_by_artist [{artist.getId()}] [{artist.getName()}] "
                    f"album_list len is [{len(album_list)}]")
    if not album_list:
        album_list = []
    non_appearances: list[Album] = subsonic_util.get_artist_albums_as_appears_on(
        artist_id=artist.getId(),
        album_list=album_list,
        opposite=True)
    appearances: list[Album] = subsonic_util.get_artist_albums_as_appears_on(
        artist_id=artist.getId(),
        album_list=album_list,
        opposite=False)
    if len(non_appearances) > 0:
        subsonic_util.sort_albums_by_date(album_list=non_appearances)
        # take first with a coverArt
        first_cover_art: str = __get_first_cover_art_from_album_list(album_list=non_appearances)
        if first_cover_art:
            return subsonic_util.build_cover_art_url(item_id=first_cover_art)
    # fallback into appearances
    if len(appearances) > 0:
        subsonic_util.sort_albums_by_date(album_list=appearances)
        # take first with a coverArt
        first_cover_art: str = __get_first_cover_art_from_album_list(album_list=appearances)
        if first_cover_art:
            return subsonic_util.build_cover_art_url(item_id=first_cover_art)
    # otherwise we fallback to other options
    return get_album_cover_art_url_by_artist_id(artist_id=artist.getId())


def get_album_cover_art_by_artist_id(artist_id: str, skip_artist_metadata_cache: bool = False) -> str:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    if verbose:
        msgproc.log(f"get_album_cover_art_by_artist_id for [{artist_id}] "
                    f"skip_artist_metadata_cache [{skip_artist_metadata_cache}]")
    artist_metadata: persistence.ArtistMetadata = (persistence.get_artist_metadata(artist_id=artist_id)
                                                   if not skip_artist_metadata_cache
                                                   else None)
    if artist_metadata and artist_metadata.artist_cover_art:
        # found in cache.
        if verbose:
            msgproc.log(f"get_album_cover_art_by_artist_id metadata cache hit for [{artist_id}] -> "
                        f"[{'yes' if artist_metadata else 'no'}]")
        return artist_metadata.artist_cover_art
    # second option is album cover art by artist id table
    album_cover_art_list: list[ArtistAlbumCoverArt] = persistence.get_cover_art_list_by_artist_id(artist_id=artist_id)
    # filter by cover art set
    album_cover_art_list_with_cover: list[ArtistAlbumCoverArt] = list(filter(
        lambda x: x.cover_art,
        album_cover_art_list))
    if len(album_cover_art_list_with_cover) > 0:
        if verbose:
            msgproc.log(f"get_album_cover_art_by_artist_id for [{artist_id}] "
                        f"skip_artist_metadata_cache [{skip_artist_metadata_cache}] "
                        f"found [{len(album_cover_art_list)}] "
                        "using get_cover_art_list_by_artist_id")
        return secrets.choice(album_cover_art_list_with_cover).cover_art
    album_cover_art_list_without_cover: list[ArtistAlbumCoverArt] = list(filter(
            lambda x: x.cover_art is None,
            album_cover_art_list))
    if len(album_cover_art_list_without_cover) > 0:
        # at least we have album id, let's see if we have cover art
        # choose one randomly
        sel_album_without: ArtistAlbumCoverArt = secrets.choice(album_cover_art_list_without_cover)
        return sel_album_without.cover_art
    # if there is precaching, we are finished here.
    if config.get_config_param_as_bool(constants.ConfigParam.PRELOAD_SONGS):
        return None
    # load artist
    if verbose:
        msgproc.log(f"get_album_cover_art_by_artist_id loading artist by id [{artist_id}] ...")
    artist: Artist = subsonic_util.try_get_artist(artist_id=artist_id)
    artist_cover_art: str = subsonic_util.get_artist_cover_art(artist=artist) if artist else None
    if artist_cover_art:
        # use this!
        if verbose:
            msgproc.log(f"get_album_cover_art_by_artist_id using artist coverArt for artist_id [{artist_id}]")
        return artist_cover_art
    album_list: list[Album] = artist.getAlbumList() if artist else []
    select_album_list: list[Album] = album_list
    # try to avoid "appearances" first
    as_main_artist_album_list: list[Album] = subsonic_util.get_artist_albums_as_appears_on(
        artist_id=artist_id,
        album_list=album_list,
        opposite=True)
    if verbose:
        msgproc.log(f"get_album_cover_art_by_artist_id select_album_list for [{artist_id}] "
                    f"[{artist.getName() if artist else None}] "
                    f"full length [{len(album_list) if album_list else 0}] "
                    f"as main artist only [{len(as_main_artist_album_list)}]")
    if len(as_main_artist_album_list) > 0:
        select_album_list = as_main_artist_album_list
    subsonic_util.sort_albums_by_date(select_album_list)
    select_album: Album = __get_first_album_with_cover_art_from_album_list(select_album_list)
    if verbose:
        msgproc.log(f"get_album_cover_art_by_artist_id for artist_id [{artist_id}] "
                    f"select_album [{select_album.getId() if select_album else 'None'}]")
    if select_album:
        cache_actions.on_album(album=select_album)
    return select_album.getCoverArt() if select_album else None


def get_album_cover_art_url_by_artist_id(artist_id: str, skip_artist_metadata_cache: bool = False) -> str:
    cover_art: str = get_album_cover_art_by_artist_id(
        artist_id=artist_id,
        skip_artist_metadata_cache=skip_artist_metadata_cache)
    return subsonic_util.build_cover_art_url(item_id=cover_art) if cover_art else None


def __get_first_album_with_cover_art_from_album_list(album_list: list[Album]) -> str:
    album: Album
    for album in album_list if album_list else []:
        if album.getCoverArt():
            if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
                msgproc.log(f"__get_first_album_with_cover_art_from_album_list using album [{album.getId()}] "
                            f"coverArt [{album.getCoverArt()}]")
            return album
    # none found
    return None


def __get_first_cover_art_from_album_list(album_list: list[Album]) -> str:
    album: Album = __get_first_album_with_cover_art_from_album_list(album_list=album_list)
    return album.getCoverArt() if album else None


def favourite_albums_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    fav: RetrievedArt = __favourite_albums_art_retriever()
    return fav if fav else random_albums_art_retriever()


def __favourite_albums_art_retriever() -> RetrievedArt:
    response: Response[Starred] = request_cache.get_starred()
    if not response.isOk():
        return None
    album_list: list[Album] = response.getObj().getAlbums()
    return __get_cover_art_from_album_list(album_list=album_list, random=True)


def favourite_artist_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    fav: RetrievedArt = _favourite_artist_art_retriever()
    msgproc.log(f"favourite_artist_art_retriever fav found: [{'yes' if fav else 'no'}]")
    return fav if fav is not None else random_albums_art_retriever()


def _favourite_artist_art_retriever() -> RetrievedArt:
    verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
    response: Response[Starred] = request_cache.get_starred()
    if not response.isOk():
        msgproc.log("_favourite_artist_art_retriever no starred artists")
        return None
    artist_list: list[Artist] = response.getObj().getArtists()
    with_id: list[Artist] = list(filter(lambda a: a.getId() is not None, artist_list if artist_list else []))
    select_artist: Artist = secrets.choice(with_id) if with_id and len(with_id) > 0 else None
    msgproc.log(f"_favourite_artist_art_retriever select_artist is set: {'yes' if select_artist else 'no'}")
    msgproc.log("_favourite_artist_art_retriever selected artist "
                f"[{select_artist.getId() if select_artist else None}] "
                f"[{select_artist.getName() if select_artist else None}]")
    if not select_artist:
        return None
    artist_cover_art: str = subsonic_util.get_artist_cover_art(artist=select_artist)
    art_url: str = None
    if verbose:
        msgproc.log("_favourite_artist_art_retriever got cover art from artist "
                    f"[{select_artist.getId()}] [{select_artist.getName()}]: "
                    f"[{'yes' if artist_cover_art else 'no'}] "
                    f"-> CoverArt: [{artist_cover_art}]")
    if artist_cover_art:
        msgproc.log(f"_favourite_artist_art_retriever [{select_artist.getId()}] [{select_artist.getName()}] "
                    f"using artist information (best option)")
        art_url = subsonic_util.build_cover_art_url(item_id=artist_cover_art)
        return RetrievedArt(art_url=art_url)
    # look in cache first
    select_artist_metadata: persistence.ArtistMetadata = persistence.get_artist_metadata(artist_id=select_artist.getId())
    if select_artist_metadata and select_artist_metadata.artist_cover_art:
        msgproc.log(f"_favourite_artist_art_retriever [{select_artist.getId()}] [{select_artist.getName()}] "
                    f"using artist metadata (second best option)")
        art_url = subsonic_util.build_cover_art_url(item_id=select_artist_metadata.artist_cover_art)
        return RetrievedArt(art_url=art_url)
    # last chance, load artist, get albums, then select one
    msgproc.log(f"_favourite_artist_art_retriever [{select_artist.getId()}] [{select_artist.getName()}] "
                f"loading artist, worst option")
    art_url = get_album_cover_art_url_by_artist_id(artist_id=select_artist.getId())
    return RetrievedArt(art_url=art_url)


def favourite_song_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    fav: RetrievedArt = _favourite_song_retriever()
    return fav if fav else random_albums_art_retriever()


def _favourite_song_retriever() -> RetrievedArt:
    return _art_for_favourite_song(random=True)


def _art_for_favourite_song(random: bool = False) -> RetrievedArt:
    response: Response[Starred] = request_cache.get_starred()
    if not response.isOk():
        return None
    song_list: list[Song] = response.getObj().getSongs()
    if not song_list or len(song_list) == 0:
        return None
    select_song: Song = secrets.choice(song_list) if random else song_list[0]
    art_url: str = (subsonic_util.build_cover_art_url(item_id=select_song.getCoverArt())
                    if select_song
                    else None)
    return RetrievedArt(art_url=art_url)


def playlists_art_retriever(tag_to_entry_context: TagToEntryContext = None) -> RetrievedArt:
    response: Response[Playlists] = request_cache.get_playlists()
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
    art_url: str = (subsonic_util.build_cover_art_url(item_id=select.getCoverArt())
                    if select and select.getCoverArt()
                    else None)
    return RetrievedArt(art_url=art_url)


def execute_art_retriever(
        tag: TagType,
        context: TagToEntryContext = None) -> RetrievedArt:
    tagname: str = tag.tag_name
    if tagname in __tag_art_retriever_dict:
        try:
            return __tag_art_retriever_dict[tagname](context)
        except Exception as ex:
            msgproc.log(f"Cannot retrieve art for tag [{tagname}] [{type(ex)}] [{ex}]")


__tag_art_retriever_dict: dict[str, Callable[[], RetrievedArt]] = {
    TagType.ALBUMS.tag_name: group_albums_art_retriever,
    TagType.ARTIST_ROLES.tag_name: group_artists_art_retriever,
    TagType.ARTISTS.tag_name: group_artists_art_retriever,
    TagType.SONGS.tag_name: group_songs_art_retriever,
    TagType.RECENTLY_ADDED_ALBUMS.tag_name: recently_added_albums_art_retriever,
    TagType.ALPHABETICAL_BY_NAME_ALBUMS.tag_name: random_albums_art_retriever,
    TagType.ALPHABETICAL_BY_ARTIST_ALBUMS.tag_name: random_albums_art_retriever,
    TagType.NEWEST_ALBUMS.tag_name: newest_albums_art_retriever,
    TagType.OLDEST_ALBUMS.tag_name: random_albums_art_retriever,
    TagType.RECENTLY_PLAYED_ALBUMS.tag_name: recently_played_albums_art_retriever,
    TagType.HIGHEST_RATED_ALBUMS.tag_name: highest_rated_albums_art_retriever,
    TagType.FAVORITE_ALBUMS.tag_name: favourite_albums_art_retriever,
    TagType.MOST_PLAYED_ALBUMS.tag_name: most_played_albums_art_retriever,
    TagType.RANDOM.tag_name: random_albums_art_retriever,
    TagType.ALBUM_BROWSER.tag_name: random_albums_art_retriever,
    TagType.ALBUMS_WITHOUT_MUSICBRAINZ.tag_name: random_albums_art_retriever,
    TagType.ALBUMS_WITHOUT_COVER.tag_name: random_albums_art_retriever,
    TagType.ALBUMS_WITHOUT_GENRE.tag_name: random_albums_art_retriever,
    TagType.RANDOM_SONGS.tag_name: random_albums_art_retriever,
    TagType.RANDOM_SONGS_LIST.tag_name: random_albums_art_retriever,
    TagType.GENRES.tag_name: random_albums_art_retriever,
    TagType.ALL_ARTISTS.tag_name: random_albums_art_retriever,
    TagType.ALL_ARTISTS_UNSORTED.tag_name: random_albums_art_retriever,
    TagType.ALL_ARTISTS_INDEXED.tag_name: random_albums_art_retriever,
    TagType.FAVORITE_ARTISTS.tag_name: favourite_artist_art_retriever,
    TagType.PLAYLISTS.tag_name: playlists_art_retriever,
    TagType.FAVORITE_SONGS.tag_name: favourite_song_retriever,
    TagType.FAVORITE_SONGS_LIST.tag_name: favourite_song_retriever
}
