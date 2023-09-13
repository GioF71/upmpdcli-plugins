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

from enum import Enum

class OptionKey(Enum):
    SKIP_TRACK_NUMBER = 0, "skip-track-number", False
    FORCED_TRACK_NUMBER = 1, "forced-track-number", None
    SKIP_TRACK_ARTIST = 3, "skip-track-artist", False
    OVERRIDDEN_ART_URI = 4, "overriden-art-uri", None
    OVERRIDDEN_TRACK_NAME = 5, "overridden-track-name", None
    ENTRY_AS_CONTAINER = 6, "entry-as-container", False
    ADD_EXPLICIT = 7, "add-explicit", True
    ADD_ALBUM_YEAR = 8, "add-album-year", True
    SKIP_ART = 9, "skip-art", False
    ADD_ARTIST_TO_ALBUM_ENTRY = 10, "add-artist-to-album-entry", False
    
    def __init__(self, 
            num : int, 
            element_name : str,
            default_value : any):
        self.num : int = num
        self.element_name : str = element_name
        self.default_value : any = default_value

    def get_name(self) -> str:
        return self.element_name
    
    def get_default_value(self) -> any:
        return self.default_value

# duplicate check
name_checker_set : set[str] = set()
id_checker_set : set[int] = set()
for v in OptionKey:
    if v.get_name() in name_checker_set:
        raise Exception(f"Duplicated name [{v.get_name()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.get_name())
    id_checker_set.add(v.value[0])