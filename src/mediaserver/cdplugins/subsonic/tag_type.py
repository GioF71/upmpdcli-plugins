from enum import Enum

class TagType(Enum):
    
    NEWEST = 0, "n", "Newest Albums", "newest"
    RECENTLY_PLAYED = 10, "rp", "Recently Played", "recent"
    RANDOM = 20, "r", "Random Albums", "random"
    GENRES = 30, "g", "Genres", None
    ARTISTS_ALL = 40, "a_all", "Artists", None
    ARTISTS_INDEXED = 50, "a_ndx", "Artists (By Initial)", None
    PLAYLISTS = 60, "pl", "Playlists", None

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
