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
    
    ALBUMS = 100, "glbms", "Albums", None
    NEWEST = 110, "n", "Newest Albums", "newest"
    RECENTLY_PLAYED = 120, "rp", "Recently Played Albums", "recent"
    HIGHEST_RATED = 130, "hr", "Highest Rated Albums", "highest"
    FAVOURITES = 140, "fav", "Favourite Albums", "starred"
    MOST_PLAYED = 150, "mp", "Most Played Albums", "frequent"
    RANDOM = 160, "r", "Random Albums", "random"
    ARTISTS = 200, "grtsts", "Artists", None
    ARTISTS_ALL = 210, "a_all", "Artists (All)", None
    ARTISTS_INDEXED = 220, "a_ndx", "Artists (By Initial)", None
    FAVOURITE_ARTISTS = 230, "fav_rtsts", "Favourite Artists", "starred"
    SONGS = 300, "gsngs", "Songs", None,
    RANDOM_SONGS = 310, "rs", "Random Songs", None,
    RANDOM_SONGS_LIST = 320, "rsl", "Random Songs (List)", None
    FAVOURITE_SONGS = 330, "fs", "Favourite Songs", None,
    FAVOURITE_SONGS_LIST = 340, "fsl", "Favourite Songs (List)", None,
    GENRES = 400, "g", "Genres", None
    PLAYLISTS = 500, "pl", "Playlists", None
    INTERNET_RADIOS = 600, "ir", "Internet Radios", None

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

def get_tag_type_by_name(tag_name : str) -> TagType:
    for _, member in TagType.__members__.items():
        if tag_name == member.getTagName():
            return member
    raise Exception(f"get_tag_type_by_name with {tag_name} NOT found")

# duplicate check
name_checker_set : set[str] = set()
id_checker_set : set[int] = set()
for v in TagType:
    if v.getTagName() in name_checker_set:
        raise Exception(f"Duplicated name [{v.getTagName()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.getTagName())
    id_checker_set.add(v.value[0])