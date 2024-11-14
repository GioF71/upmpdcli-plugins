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

from tidalapi.album import Album as TidalAlbum

from datetime import datetime
from persistence import AlbumMetadata
import tidal_util
import persistence
import copy
import typing
import cmdtalkplugin

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


def __albumToAlbumMetadata(album: TidalAlbum) -> AlbumMetadata:
    result: AlbumMetadata = AlbumMetadata()
    result.album_id = album.id
    result.album_name = album.name
    result.artist_id = album.artist.id if album.artist else None
    result.artist_name = album.artist.name if album.artist else None
    result.explicit = 1 if album.explicit else 0
    result.release_date = album.release_date
    result.available_release_date = album.available_release_date
    result.image_url = tidal_util.get_image_url(album)
    album_audio_modes: list[str] = album.audio_modes
    result.audio_modes = ",".join(album_audio_modes) if album_audio_modes else None
    result.audio_quality = album.audio_quality
    album_media_metadata_tags: list[str] = album.media_metadata_tags
    result.media_metadata_tags = ",".join(album_media_metadata_tags) if album_media_metadata_tags else None
    return result


class AlbumAdapter:

    id: str = None
    name: str = None
    artist_id: str = None
    artist_name: str = None
    explicit: bool = False
    release_date: datetime = None
    available_release_date: datetime = None
    image_url: str = None
    audio_modes: list[str] = None
    audio_quality: str = None
    media_metadata_tags: list[str] = None

    @property
    def year(self) -> int:
        return self.available_release_date.year if self.available_release_date else None


def tidal_album_to_adapter(tidal_album: TidalAlbum) -> AlbumAdapter:
    persistence.store_album_metadata(__albumToAlbumMetadata(tidal_album))
    album_adapter: AlbumAdapter = AlbumAdapter()
    album_adapter.id = tidal_album.id
    album_adapter.name = tidal_album.name
    album_adapter.artist_id = tidal_album.artist.id if tidal_album.artist else None
    album_adapter.artist_name = tidal_album.artist.name if tidal_album.artist else None
    album_adapter.explicit = tidal_album.explicit
    album_adapter.release_date = tidal_album.release_date
    album_adapter.available_release_date = tidal_album.available_release_date
    album_adapter.image_url = tidal_util.get_image_url(tidal_album)
    album_adapter.audio_modes = copy.deepcopy(tidal_album.audio_modes)
    album_adapter.audio_quality = tidal_album.audio_quality
    album_adapter.media_metadata_tags = copy.deepcopy(tidal_album.media_metadata_tags)
    return album_adapter


def __album_metadata_to_adapter(album_metadata: AlbumMetadata) -> AlbumAdapter:
    album_adapter: AlbumAdapter = AlbumAdapter()
    album_adapter.id = album_metadata.album_id
    album_adapter.name = album_metadata.album_name
    album_adapter.artist_id = album_metadata.artist_id
    album_adapter.artist_name = album_metadata.artist_name
    album_adapter.explicit = True if album_metadata.explicit == 1 else False
    album_adapter.release_date = album_metadata.release_date
    album_adapter.available_release_date = album_metadata.available_release_date
    album_adapter.image_url = album_metadata.image_url
    album_adapter.audio_modes = (album_metadata.audio_modes.split(",")
                                 if album_metadata.audio_modes
                                 else None)
    album_adapter.audio_quality = album_metadata.audio_quality
    album_adapter.media_metadata_tags = (album_metadata.media_metadata_tags.split(",")
                                         if album_metadata.media_metadata_tags
                                         else None)
    return album_adapter


def album_adapter_by_album_id(
        album_id: str,
        tidal_album_loader: typing.Callable[[str], TidalAlbum]) -> AlbumAdapter:
    album_metadata: AlbumMetadata = persistence.get_album_metadata(album_id=album_id)
    # msgproc.log(f"album_adapter_by_album_id [{album_id}] cache hit: [{'yes' if album_metadata else 'no'}]")
    if album_metadata:
        return __album_metadata_to_adapter(album_metadata)
    # load the album if no metadata is available
    tidal_album: TidalAlbum = tidal_album_loader(album_id)
    # convert to adapter (performs caching)
    return tidal_album_to_adapter(tidal_album) if tidal_album else None
