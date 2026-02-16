# Copyright (C) 2026 Giovanni Fulco
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


import constants


class ReleaseDate:

    def __init__(self, obj_dict: dict[str, int]):
        self.__dict: dict[str, int] = {}
        k: constants.DictKey
        for k in [constants.DictKey.YEAR, constants.DictKey.MONTH, constants.DictKey.DAY]:
            if k.value in obj_dict:
                self.__dict[k.value] = obj_dict[k.value]

    def __or_none(self, dict_key: constants.DictKey) -> str | None:
        return self.__dict[dict_key.value] if dict_key.value in self.__dict else None

    def __or_none_as_int(self, dict_key: constants.DictKey) -> str | None:
        or_none: str | None = self.__or_none(dict_key=dict_key)
        if or_none is None:
            return None
        try:
            return int(or_none)
        except Exception:
            # maybe log something?
            return None

    @property
    def year(self) -> int:
        return self.__or_none_as_int(dict_key=constants.DictKey.YEAR)

    @property
    def month(self) -> int:
        return self.__or_none_as_int(dict_key=constants.DictKey.MONTH)

    @property
    def day(self) -> int:
        return self.__or_none_as_int(dict_key=constants.DictKey.DAY)
