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
