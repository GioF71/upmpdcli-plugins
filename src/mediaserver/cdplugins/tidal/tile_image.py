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

import datetime


class TileImage:

    def __init__(self):
        pass

    @property
    def tile_type(self) -> str:
        return self._tile_type

    @tile_type.setter
    def tile_type(self, value: str):
        self._tile_type: str = value

    @property
    def tile_id(self) -> str:
        return self._tile_id

    @tile_id.setter
    def tile_id(self, value: str):
        self._tile_id: str = value

    @property
    def tile_image(self) -> str:
        return self._tile_image

    @tile_image.setter
    def tile_image(self, value: str):
        self._tile_image: str = value

    @property
    def update_time(self) -> datetime.datetime:
        return self._update_time

    @update_time.setter
    def update_time(self, value: datetime.datetime):
        self._update_time: datetime.datetime = value
