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

import cmdtalkplugin
import upmplgutils
import constants

from tidalapi import Quality as TidalQuality
from tidalapi.artist import Artist as TidalArtist
from tidalapi.album import Album as TidalAlbum
from tidalapi.playlist import Playlist as TidalPlaylist
from tidalapi.playlist import UserPlaylist as TidalUserPlaylist
from tidalapi.mix import Mix as TidalMix

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

log_unavailable_images_sizes : bool = upmplgutils.getOptionValue(f"{constants.plugin_name}log_unavailable_images_sizes", "0") == "1"
log_unavailable_image : bool = upmplgutils.getOptionValue(f"{constants.plugin_name}log_unavailable_image", "0") == "1"

default_image_sz_by_type : dict[str, int] = dict()
default_image_sz_by_type[TidalArtist.__name__] = [750, 480, 320, 160]
default_image_sz_by_type[TidalAlbum.__name__] = [1280, 640, 320, 160, 80]
default_image_sz_by_type[TidalPlaylist.__name__] = [1080, 750, 640, 480, 320, 160]
default_image_sz_by_type[TidalMix.__name__] = [1500, 640, 320]
default_image_sz_by_type[TidalUserPlaylist.__name__] = default_image_sz_by_type[TidalPlaylist.__name__]

def get_image_dimension_list(obj : any) -> list[int]:
    key = type(obj).__name__
    return default_image_sz_by_type[key] if key in default_image_sz_by_type else list()

def get_name_or_title(obj : any) -> str:
    if hasattr(obj, "name"):
        return obj.name
    if hasattr(obj, "title"):
        return obj.title
    return None

def get_image_url(obj : any) -> str:
    dimension_list : list[int] = get_image_dimension_list(obj)
    if not dimension_list or len(dimension_list) == 0:
        msgproc.log(f"Type [{type(obj).__name__}] does not have an image sizes list!")
        return None
    current : int
    for current in dimension_list if dimension_list else list():
        try:
            return obj.image(dimensions = current)
        except ValueError:
            if log_unavailable_images_sizes:
                msgproc.log(f"Cannot find image for type [{type(obj).__name__}] id [{obj.id}] Name [{get_name_or_title(obj)}] with size [{current}]")
        except AttributeError as ae_exc:
            msgproc.log(f"Cannot find image for type [{type(obj).__name__}] id [{obj.id}] Name [{get_name_or_title(obj)}] Exception [{ae_exc}]")
    if log_unavailable_image:
        msgproc.log(f"Cannot find image for type [{type(obj).__name__}] id [{obj.id}] Name [{get_name_or_title(obj)}] (any size)")
    return None

def is_mp3(q : TidalQuality) -> bool:
    return q == TidalQuality.low_320k or q == TidalQuality.low_96k

def get_mime_type(track_quality : TidalQuality) -> str:
    if is_mp3(track_quality):
        return "audio/mp3"
    else:
        return "audio/flac"

def is_multidisc_album(album : TidalAlbum) -> bool:
    return album.num_volumes and album.num_volumes > 1

