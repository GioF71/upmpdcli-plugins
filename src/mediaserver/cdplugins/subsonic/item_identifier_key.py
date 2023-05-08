from enum import Enum

class ItemIdentifierKey(Enum):
    
    THING_NAME = 0, 'n'
    THING_VALUE = 1, 'v'
    GENRE_NAME = 2, 'g'
    PAGE_NUMBER = 3, 'p'
    ALBUM_ID = 4, 'a'
    OFFSET = 5, 'o'
    TAG_TYPE = 6, 't',
    ALBUM_VERSION_PATH_BASE64 = 7, 'ap',
    
    def __init__(self, 
            num : int, 
            key_name : str):
        self.num : int = num
        self.key_name : str = key_name
    
    def getName(self) -> str:
        return self.key_name
    
