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
import uuid

class Codec:

    def __init__(self):
        self.__by_name : dict[str, str] = {}
        self.__by_id : dict[str, str] = {}

    def encode(self, name : str) -> str:
        by_id : str = self.__by_name[name] if name in self.__by_name else None
        if not by_id:
            new_id : str = uuid.uuid4().hex
            self.__by_id[new_id] = name
            self.__by_name[name] = new_id
            by_id = new_id
        return by_id
    
    def decode(self, id : str) -> str:
        if id in self.__by_id: return self.__by_id[id]
        raise Exception("Id not found")

