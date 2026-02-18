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

from subsonic_connector.album import Album
from subsonic_connector.album_list import AlbumList
from subsonic_connector.response import Response
import request_cache
import connector_provider
import config
import constants
from msgproc_provider import msgproc
import random


class TagToEntryContext:

    def __init__(self):
        self.__first_load: bool = True
        self.__random_album_list: list[Album] = []

    @property
    def random_album_list(self) -> list[Album]:
        verbose: bool = config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING)
        if verbose:
            msgproc.log("TagToEntryContext::random_album_list enter ...")
        if not self.__random_album_list or len(self.__random_album_list) == 0:
            # load some random albums
            if verbose:
                msgproc.log("TagToEntryContext::random_album_list (loading) ...")
            res: Response[AlbumList] = None
            if self.__first_load:
                if verbose:
                    msgproc.log("TagToEntryContext::random_album_list loading from request cache ...")
                # res = connector_provider.get().getRandomAlbumList(size=config.get_items_per_page())
                res = request_cache.get_random_album_list(size=config.get_items_per_page())
                self.__first_load = False
            else:
                # don't use cache
                if verbose:
                    msgproc.log("TagToEntryContext::random_album_list loading random albums ...")
                res = connector_provider.get().getRandomAlbumList(size=config.get_items_per_page())
            if res and res.isOk():
                # store.
                res_list: list[Album] = res.getObj().getAlbums()
                self.__random_album_list = list(res_list) if res_list else []
                if (len(self.__random_album_list) > 0 and
                        config.get_config_param_as_bool(constants.ConfigParam.ALLOW_SHUFFLE_RANDOM_ALBUM_FOR_FRONT_PAGE_TAGS)):
                    random.shuffle(self.__random_album_list)
            else:
                # storing an empty list
                self.__random_album_list = []
        if verbose:
            msgproc.log(f"TagToEntryContext::random_album_list return a list with [{len(self.__random_album_list)}] items")
        return self.__random_album_list
