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

class TagType(Enum):
    
    NEWEST = 0, "n", "Newest Albums", "newest"
    RECENTLY_PLAYED = 10, "rp", "Recently Played", "recent"
    HIGHEST_RATED = 20, "hr", "Highest Rated", "highest"
    FAVOURITES = 30, "fav", "Favourites", "starred"
    MOST_PLAYED = 40, "mp", "Most Played", "frequent"
    RANDOM = 50, "r", "Random Albums", "random"
    GENRES = 60, "g", "Genres", None
    ARTISTS_ALL = 70, "a_all", "Artists", None
    ARTISTS_INDEXED = 80, "a_ndx", "Artists (By Initial)", None
    PLAYLISTS = 90, "pl", "Playlists", None
    RANDOM_SONGS = 100, "rs", "Random Songs", None,
    INTERNET_RADIOS = 110, "ir", "Internet Radios", None

    def __init__(self, 
            num : int, 
            tag_name : str, 
            tag_title : str, 
            query_type : str):
        self.num : int = num
        self.tag_name : str = tag_name
        self.tag_title : str = tag_title
        self.query_type : str = query_type

    def getTagName(self) -> str:
        return self.tag_name

    def getTagTitle(self) -> str:
        return self.tag_title

    def getQueryType(self) -> str:
        return self.query_type
