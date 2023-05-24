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
    
    TAG   = 0, "tag"
    ALBUM = 1, "album"
    GENRE = 3, "genre"
    GENRE_ARTIST_LIST = 4, "genre_artists"
    GENRE_ALBUM_LIST = 5, "genre_albums"
    ARTIST = 6, "artist"
    GENRE_ARTIST = 7, "genre_artist"
    ARTIST_INITIAL = 8, "artist_initial"
    TRACK = 9, "track",
    PLAYLIST = 10, "playlist"
    INTERNET_RADIO = 11, "internet_radio",
    RANDOM_SONG = 12, "random_song",
    RANDOM_SONG_THE_SONG = 13, "random_song_the_song",
    NEXT_RANDOM_SONGS = 14, "next_random_songs",
    SPARSE_ALBUM = 15, "sparse_album",
    ARTIST_TOP_SONGS = 16, "artist_top_songs",
    ARTIST_SIMILAR = 17, "artist_similar",
    ARTIST_ALBUMS = 18, "artist_albums"

    def __init__(self, 
            num : int, 
            element_name : str):
        self.num : int = num
        self.element_name : str = element_name

    def getName(self):
        return self.element_name
