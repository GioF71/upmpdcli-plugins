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

from enum import Enum


class CodecDelimiterStyle(Enum):

    SQUARE = 0, "[", "]"
    ROUND = 1, "(", ")"

    def __init__(self, num: int, left: str, right: str):
        self.__num: int = num
        self.__left: str = left
        self.__right: str = right

    def get_num(self) -> int: return self.__num
    def get_left(self) -> str: return self.__left
    def get_right(self) -> str: return self.__right
