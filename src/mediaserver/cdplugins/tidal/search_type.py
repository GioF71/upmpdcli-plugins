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

from element_type import ElementType
import tidalapi

from enum import Enum

class SearchType(Enum):
    
    ALBUM = 0, "album", "albums", tidalapi.album.Album
    ARTIST = 1, "artist", "artists", tidalapi.artist.Artist
    TRACK = 2, "track", "tracks", tidalapi.media.Track

    def __init__(self, 
            num : int, 
            element_name : str,
            dict_entry : str,
            model : type):
        self.num : int = num
        self.element_name : str = element_name
        self.dict_entry : str = dict_entry
        self.model : type = model

    def get_name(self):
        return self.element_name

    def get_dict_entry(self) -> str:
        return self.dict_entry

    def get_model(self) -> type:
        return self.model
    
# duplicate check
name_checker_set : set[str] = set()
id_checker_set : set[int] = set()
for v in SearchType:
    if v.get_name() in name_checker_set:
        raise Exception(f"Duplicated name [{v.get_name()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.get_name())
    id_checker_set.add(v.value[0])