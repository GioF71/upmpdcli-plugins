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


class TagType(Enum):
    PAGE_SELECTION = 10, "pgslctn", "Page Selection"
    CATEGORIES = 100, "ctgrs", "Categories"
    HOME = 112, "home", "Home"
    EXPLORE = 113, "xplr", "Explore"
    EXPLORE_NEW_MUSIC = 114, "new", "New Music"
    EXPLORE_TIDAL_RISING = 116, "rising", "Tidal Rising"
    FOR_YOU = 115, "foru", "For You"
    HIRES_PAGE = 120, "hires", "Hi-Res"
    GENRES_PAGE = 129, "genres", "Genres"
    LOCAL_GENRES_PAGE = 140, "local_genres", "Local Genres"
    MOODS_PAGE = 130, "moods", "Moods"
    ALL_PLAYLISTS = 200, "allplsts", "Playlists"
    MY_PLAYLISTS = 300, "myplsts", "My Playlists"
    FAVORITE_ARTISTS = 400, "fvrtsts", "My Artists"
    FAVORITE_ALBUMS = 500, "fvlbms", "My Albums"
    FAVORITE_TRACKS = 600, "fvrttrks", "My Tracks"
    BOOKMARKS = 700, "lstnq", "Bookmarks"
    PLAYBACK_STATISTICS = 800, "plbkstts", "Playback Statistics"

    def __init__(
            self,
            num: int,
            tag_name: str,
            tag_title: str):
        self.num: int = num
        self.tag_name: str = tag_name
        self.tag_title: str = tag_title

    def getTagName(self) -> str:
        return self.tag_name

    def getTagTitle(self) -> str:
        return self.tag_title


def get_tidal_tag_type_by_name(tag_name: str) -> TagType:
    # msgproc.log(f"get_tidal_tag_type_by_name with {tag_name}")
    for _, member in TagType.__members__.items():
        if tag_name == member.getTagName():
            return member
    raise Exception(f"get_tidal_tag_type_by_name with {tag_name} NOT found")


# duplicate check
name_checker_set: set[str] = set()
id_checker_set: set[int] = set()
for v in TagType:
    if v.getTagName() in name_checker_set:
        raise Exception(f"Duplicated name [{v.getTagName()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.getTagName())
    id_checker_set.add(v.value[0])
