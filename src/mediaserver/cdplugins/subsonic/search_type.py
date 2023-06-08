from element_type import ElementType

from enum import Enum

class SearchType(Enum):
    ALBUM = 0, "album"
    ARTIST = 1, "artist"
    TRACK = 2, "track"

    def __init__(self, 
            num : int, 
            element_name : str):
        self.num : int = num
        self.element_name : str = element_name

    def getName(self):
        return self.element_name

# duplicate check
name_checker_set : set[str] = set()
id_checker_set : set[int] = set()
for v in SearchType:
    if v.getName() in name_checker_set:
        raise Exception(f"Duplicated name [{v.getName()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.getName())
    id_checker_set.add(v.value[0])