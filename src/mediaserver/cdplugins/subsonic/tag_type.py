from enum import Enum

class TagType(Enum):
    
    NEWEST = 0, "newest", "Newest Albums", "newest"
    RANDOM = 10, "random", "Random Albums", "random"
    GENRES = 20, "genres", "Genres", None
    ARTISTS_ALL = 30, "artists_all", "Artists", None
    ARTISTS_INDEXED = 40, "artists_ndx", "Artists (By Initial)", None

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
