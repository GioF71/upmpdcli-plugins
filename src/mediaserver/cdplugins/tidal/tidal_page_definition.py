# Copyright (C) 2025 Giovanni Fulco
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


class TidalPageDefinition(Enum):

    RISING = "rising", "pages/rising", "Tidal Rising"
    NEW_MUSIC = "newmusic", "pages/explore_new_music", "New Music"
    HOME = "home", "pages/home", "Home"
    GENRES = "genres", "pages/genre_page", "Genres"
    LOCAL_GENRES = "local_genres", "pages/genre_page_local", "Local Genres"
    MOODS = "moods", "pages/moods", "Moods"
    FOR_YOU = "foryou", "pages/for_you", "For You"
    HI_RES = "hires", "pages/hires", "Hi-Res"
    EXPLORE = "explore", "pages/explore", "Explore"

    def __init__(
            self,
            _: any,
            page_path: str,
            page_title: str):
        self.__page_path: str = page_path
        self.__page_title: str = page_title

    @property
    def page_path(self) -> str:
        return self.__page_path

    @property
    def page_title(self) -> str:
        return self.__page_title
