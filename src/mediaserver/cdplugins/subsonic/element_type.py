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

    def __init__(self, 
            num : int, 
            element_name : str):
        self.num : int = num
        self.element_name : str = element_name

    def getName(self):
        return self.element_name
