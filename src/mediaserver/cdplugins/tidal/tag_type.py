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


class _TagTypeData:

    def __init__(self, name: str, title: str, prefer_non_static_icon: bool = False):
        self.__name: str = name
        self.__title: str = title
        self.__prefer_non_static_icon: bool = prefer_non_static_icon

    @property
    def name(self) -> str:
        return self.__name

    @property
    def title(self) -> str:
        return self.__title

    @property
    def prefer_non_static_icon(self) -> bool:
        return self.__prefer_non_static_icon


class TagType(Enum):
    PAGE_SELECTION = _TagTypeData("pgslctn", "Page Selection")
    CATEGORIES = _TagTypeData("ctgrs", "Categories")
    HOME = _TagTypeData("home", "Home")
    EXPLORE = _TagTypeData("xplr", "Explore")
    EXPLORE_NEW_MUSIC = _TagTypeData("new", "New Music")
    EXPLORE_TIDAL_RISING = _TagTypeData("rising", "Tidal Rising")
    FOR_YOU = _TagTypeData("foru", "For You")
    HIRES_PAGE = _TagTypeData("hires", "Hi-Res")
    GENRES_PAGE = _TagTypeData("genres", "Genres")
    LOCAL_GENRES_PAGE = _TagTypeData("local_genres", "Local Genres")
    MOODS_PAGE = _TagTypeData("moods", "Moods")
    ALL_PLAYLISTS = _TagTypeData("allplsts", "Playlists", prefer_non_static_icon=True)
    MY_PLAYLISTS = _TagTypeData("myplsts", "My Playlists", prefer_non_static_icon=True)
    FAVORITE_ARTISTS = _TagTypeData("fvrtsts", "My Artists", prefer_non_static_icon=True)
    FAVORITE_ALBUMS = _TagTypeData("fvlbms", "My Albums", prefer_non_static_icon=True)
    FAVORITE_TRACKS = _TagTypeData("fvrttrks", "My Tracks", prefer_non_static_icon=True)
    BOOKMARKS = _TagTypeData("lstnq", "Bookmarks", prefer_non_static_icon=True)
    PLAYBACK_STATISTICS = _TagTypeData("plbkstts", "Playback Statistics", prefer_non_static_icon=True)

    @property
    def name(self) -> str:
        return self.value.name

    @property
    def title(self) -> str:
        return self.value.title

    @property
    def prefer_non_static_icon(self) -> bool:
        return self.value.prefer_non_static_icon


def get_tidal_tag_type_by_name(tag_name: str) -> TagType:
    for _, member in TagType.__members__.items():
        if tag_name == member.name:
            return member
    raise Exception(f"get_tidal_tag_type_by_name with {tag_name} NOT found")
