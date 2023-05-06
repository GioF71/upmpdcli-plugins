from enum import Enum

class ItemIdentifierKey(Enum):
    
    THING_NAME = 0, 'thing_name'
    THING_VALUE = 1, 'thing_value'
    GENRE = 2, 'genre'
    PAGE_NUMBER = 3, 'page_number'
    ALBUM_ID = 4, 'album_id'
    OFFSET = 5, 'offset'
    TAG_TYPE = 6, 'tag_type',
    ALBUM_TRACKS = 7, 'album_tracks',
    ALBUM_VERSION_PATH = 8, 'album_path',
    SONG_DATA = 9, 'song_data',
    ENTRY_ID = 11, 'entry_id'
    
    def __init__(self, 
            num : int, 
            key_name : str):
        self.num : int = num
        self.key_name : str = key_name
    
    def getName(self) -> str:
        return self.key_name
    
