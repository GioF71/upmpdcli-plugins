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

class ElementType(Enum):
    TAG = 0, "tag"
    CATEGORY = 1, "cat",
    ALBUM = 2, "lbm",
    PLAYLIST = 3, "pl"
    MIX = 4, "mix"
    PAGELINK = 5, "pglnk"
    ARTIST = 6, "rtst"
    ARTIST_ALBUM_ALBUMS = 7, "rtstlbms"
    ARTIST_ALBUM_EP_SINGLES = 8, "rtstepsngls"
    ARTIST_ALBUM_OTHERS = 9, "rtstthrs"
    SIMILAR_ARTISTS = 10, "smlrrtsts"
    PLAYLIST_CONTAINER = 11, "plc"
    PLAYLIST_NAVIGABLE = 12, "pln"
    PLAYLIST_NAVIGABLE_ITEM = 13, "plni"
    MIX_CONTAINER = 14, "mixc"
    MIX_NAVIGABLE = 15, "mixn",
    MIX_NAVIGABLE_ITEM = 16, "mixi"
    ALBUM_CONTAINER = 17, "lbmc"
    ARTIST_TOP_TRACKS_NAVIGABLE = 18, "rtstttrks"
    NAVIGABLE_TRACK = 19, "trkn"
    ARTIST_RADIO_NAVIGABLE = 20, "rtstrd"
    ARTIST_TOP_TRACKS_LIST = 21, "rtstttrkslst"
    ARTIST_RADIO_LIST = 22, "rtstrdlst",
    RECENTLY_PLAYED_TRACKS_NAVIGABLE = 23, "rcntlptrks",
    RECENTLY_PLAYED_TRACKS_LIST = 24, "rcntlptrkslst",
    MOST_PLAYED_TRACKS_NAVIGABLE = 25, "mptrks",
    MOST_PLAYED_TRACKS_LIST = 26, "mptrkslst",
    FAVORITE_TRACKS_NAVIGABLE = 27, "fvrttrksn",
    FAVORITE_TRACKS_LIST = 28, "fvrttrksl",
    PAGE = 29, "pg",
    RECENTLY_PLAYED_ALBUMS = 30, "rcntpllbms",
    MOST_PLAYED_ALBUMS = 31, "mplbms",
    TRACK = 101, "trk"
    TRACK_CONTAINER = 102, "trkc"

    def __init__(self, 
            num : int, 
            element_name : str):
        self.num : int = num
        self.element_name : str = element_name

    def getName(self):
        return self.element_name

# duplicate check
name_checker_set : set[str] = set()
id_checker_set : set[int] = set()
for v in ElementType:
    if v.getName() in name_checker_set:
        raise Exception(f"Duplicated name [{v.getName()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.getName())
    id_checker_set.add(v.value[0])