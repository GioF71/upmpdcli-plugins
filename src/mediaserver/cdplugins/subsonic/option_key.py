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

from album_util import MultiCodecAlbum

class OptionKey(Enum):
    SKIP_TRACK_NUMBER = 0, "skip-track-number", False
    PREPEND_ARTIST_IN_ALBUM_TITLE = 1, "prepend-artist-in-album-title", True
    FORCE_TRACK_NUMBER = 2, "force-track-number", None
    ALBUM_ART_URI = 3, "album-art-uri", None
    MULTI_CODEC_ALBUM = 4, "multi-codec-album", MultiCodecAlbum.NO
    SKIP_ART = 5, "skip-art", False
    OFFSET = 6, "offset", 0
    PAGINATED = 7, "paginated", False,
    # integer to prepend e.g. pass 3 -> [03] album_title instead of album_title
    PREPEND_ENTRY_NUMBER_IN_ALBUM_TITLE = 8, "prepend-entry-number-in-album-title", None

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