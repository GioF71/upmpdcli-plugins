# Copyright (C) 2023,2024,2025 Giovanni Fulco
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
    FAV_ARTIST_ADD = 32, "fvrtstadd",
    FAV_ARTIST_DEL = 33, "fvrtstdel",
    FAV_ALBUM_ADD = 34, "fvrtlbmadd",
    FAV_ALBUM_DEL = 35, "fvrtlbmdel",
    REMOVE_ALBUM_FROM_STATS = 36, "rmvlbmstts",
    REMOVE_TRACK_FROM_STATS = 37, "rmvtrkstts",
    FAVORITE_ALBUMS_BY_ARTIST_ASC = 39, "fvlbmbrtsta",
    FAVORITE_ALBUMS_BY_ARTIST_DESC = 40, "fvlbmbrtstd",
    FAVORITE_ALBUMS_BY_TITLE_ASC = 41, "fvlbmttla",
    FAVORITE_ALBUMS_BY_TITLE_DESC = 42, "fvlbmttld",
    FAVORITE_ALBUMS_BY_RELEASE_DATE_ASC = 43, "fvlbmrdta",
    FAVORITE_ALBUMS_BY_RELEASE_DATE_DESC = 44, "fvlbmrdtd",
    FAVORITE_ALBUMS_BY_USER_DATE_ADDED_ASC = 45, "fvlbmudaa",
    FAVORITE_ALBUMS_BY_USER_DATE_ADDED_DESC = 46, "fvlbmudad",
    FAVORITE_ARTISTS_BY_NAME_ASC = 47, "fvrtstna",
    FAVORITE_ARTISTS_BY_NAME_DESC = 48, "fvrtstnd",
    FAVORITE_ARTISTS_BY_USER_DATE_ADDED_ASC = 49, "fvrtstudaa",
    FAVORITE_ARTISTS_BY_USER_DATE_ADDED_DESC = 50, "fvrtstudad",
    ARTIST_FOCUS = 51, "rtstrl"
    ALBUMS_IN_MIX_OR_PLAYLIST = 52, "lbmnmxplst"
    ARTISTS_IN_MIX_OR_PLAYLIST = 53, "rtstnmxplst"
    BOOKMARK_ALBUM_ACTION = 54, "lbmlqctn"
    BOOKMARK_ALBUMS = 55, "lbllstnq"
    ALBUM_TRACKS = 56, "lbmtrks"
    TRACK_FAVORITE_ACTION = 57, "trkfvtct"
    BOOKMARK_ARTISTS = 58, "rtstlstnq"
    BOOKMARK_ARTIST_ACTION = 59, "rtstlqctn"
    BOOKMARK_TRACKS = 60, "snglstnq"
    BOOKMARK_TRACK_ACTION = 61, "snglstnqctn"
    MISSING_ALBUM = 62, "msnglbm"
    MISSING_TRACK = 63, "msngtrk"
    MISSING_ARTIST = 65, "msngrtst"
    ALL_TRACKS_IN_PLAYLIST_OR_MIX = 64, "lltrksmxplst"
    TRACK = 101, "trk"
    TRACK_CONTAINER = 102, "trkc"
    SEARCH = 103, "srch"

    def __init__(
            self,
            num: int,
            element_name: str):
        self.num: int = num
        self.element_name: str = element_name

    def getName(self):
        return self.element_name


def get_element_type_by_name(element_name: str) -> ElementType:
    # msgproc.log(f"get_tidal_tag_type_by_name with {tag_name}")
    for _, member in ElementType.__members__.items():
        if element_name == member.getName():
            return member
    raise Exception(f"get_element_type_by_name with {element_name} NOT found")


# duplicate check
name_checker_set: set[str] = set()
id_checker_set: set[int] = set()
for v in ElementType:
    if v.getName() in name_checker_set:
        raise Exception(f"Duplicated name [{v.getName()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.getName())
    id_checker_set.add(v.value[0])
