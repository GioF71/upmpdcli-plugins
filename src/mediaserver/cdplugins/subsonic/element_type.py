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


class ElementType(Enum):
    TAG = 0, "tag"
    ALBUM = 1, "lbm"
    GENRE = 3, "gnr"
    GENRE_ARTIST_LIST = 4, "gnr_rtsts"
    GENRE_ALBUM_LIST = 5, "gnr_lbus"
    ARTIST = 6, "rtst"
    GENRE_ARTIST = 7, "gnr_rtst"
    ARTIST_BY_INITIAL = 8, "rtstntl"
    TRACK = 9, "trk",
    PLAYLIST = 10, "pl"
    INTERNET_RADIO = 11, "i_rd",
    SONG_ENTRY_NAVIGABLE = 12, "sngntr_n",
    SONG_ENTRY_THE_SONG = 13, "sngntr_s",
    NEXT_RANDOM_SONGS = 14, "nxt_rndm_sngs",
    NAVIGABLE_ALBUM = 15, "sprs_lbm",
    ARTIST_TOP_SONGS = 16, "rtsttp",
    ARTIST_TOP_SONGS_LIST = 17, "rtsttp_sl",
    ARTIST_SIMILAR = 18, "rtst_smlr",
    ARTIST_ALBUMS = 19, "rtst_lbms",
    RADIO = 20, "rd",
    RADIO_SONG_LIST = 21, "rd_sl",
    GENRE_ARTIST_ALBUMS = 22, "gnr_rtst_lbms"
    # artist which appear as artistId for albums
    ALBUM_ARTIST = 23, "lbmrtst"
    ALBUM_FOCUS = 24, "lbmfcs"
    ARTIST_FOCUS = 25, "rstsfcs"
    ADDITIONAL_ALBUM_ARTISTS = 26, "ddtlnlbmrtsts"

    def __init__(
            self,
            num: int,
            element_name: str):
        self.num: int = num
        self.element_name: str = element_name

    def getName(self):
        return self.element_name


def get_element_type_by_name(element_name: str) -> ElementType:
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
