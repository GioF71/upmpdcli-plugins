import os
from re import split
from enum import Enum
from functools import cmp_to_key

from subsonic_connector.song import Song

__split_characters : list[str] = [' ', '-', '_']

def split_string(string, delimiters):
  pattern = r'|'.join(delimiters)
  return split(pattern, string)

class Starter(Enum):
    
    CD = 0
    DISC = 1
    DISCO = 2

def __is_int(value : str) -> bool:
    try:
        # converting to integer
        int(value)
        return True
    except ValueError:
        return False


def ignorable(last_path : str) -> bool:
    # first case: start with a starter, then there is a number without a splitter
    for name, member in Starter.__members__.items():
        if last_path.upper().startswith(name):
            # is there a number after that?
            potential_discnumber : str = last_path[len(name)]
            if __is_int(potential_discnumber): return True

    # second case: start with a starter, then there is a number after a splitter
    for name, member in Starter.__members__.items():
        if last_path.upper().startswith(name):
            splitted : list = split_string(last_path, __split_characters)
            if splitted is not None and len(splitted) == 2:
                last : str = splitted[1]
                if __is_int(last): return True

    return False

class __Decorated_Song:

    def __init__(self, song : Song):
        self._song = song
        self._disc : int = song.getDiscNumber() if song.getDiscNumber() else 0
        self._track : int = song.getTrack() if song.getTrack() else 0
        path : str = os.path.dirname(song.getPath())
        last_path = os.path.basename(os.path.normpath(path))
        last_path_ignorable : bool = ignorable(last_path)
        if last_path_ignorable:
            self._path = os.path.split(path)[0]
        else:
            self._path = path

    def getSong(self) -> Song: return self._song
    def getPath(self) -> str: return self._path

def __compare_decorated_song(left : __Decorated_Song, right : __Decorated_Song) -> int:
    cmp : int
    cmp = -1 if left._path < right._path else 0 if left._path == right._path else 1
    if cmp == 0:
        cmp = -1 if left._disc < right._disc else 0 if left._disc == right._disc else 1
    if cmp == 0: 
        cmp = -1 if left._track < right._track else 0 if left._track == right._track else 1
    return cmp

def sort_song_list(song_list : list[Song]) -> list[Song]:
    dec_list : list[__Decorated_Song] = []
    for song in song_list:
        dec : __Decorated_Song = __Decorated_Song(song)
        dec_list.append(dec)
    dec_list.sort(key = cmp_to_key(__compare_decorated_song))
    result : list[song] = []
    current : __Decorated_Song
    for current in dec_list:
        result.append(current.getSong())
    return result
    
