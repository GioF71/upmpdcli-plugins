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


from enum import Enum

class _ArtistRoleData:

    def __init__(
            self,
            key: str,
            display_value: str):
        self.__key: str = key
        self.__display_value: str = display_value
    
    @property
    def key(self) -> str:
        return self.__key

    @property
    def display_value(self) -> str:
        return self.__display_value
    

class ArtistRole(Enum):

    ALBUM_ARTIST = _ArtistRoleData(
        key="albumartist",
        display_value="Album Artist")
    
    @property
    def key(self) -> str:
        return self.value.key

    @property
    def display_value(self) -> str:
        return self.value.display_value
        

def get_artist_role_display_value(key: str) -> str:
    curr: ArtistRole
    for curr in ArtistRole:
        if curr.key == key:
            if curr.display_value is None or len(curr.display_value) == 0:
                break
            return curr.display_value
    return key.capitalize()
