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

class ItemIdentifierKey(Enum):
    
    THING_NAME = 0, 'n'
    THING_VALUE = 1, 'v'
    PAGE_NUMBER = 3, 'p'
    ALBUM_ID = 4, 'a'
    OFFSET = 5, 'o'
    TAG_TYPE = 6, 't',
    CATEGORY_TITLE = 10, 'catt'
    PAGE_LIST = 11, 'pglst'
    PAGE_LINK_API_PATH = 12, "pglnkppth"
    CATEGORY_KEY = 13, "catk"
    MAX_ITEMS = 14, "mxtms"
            
    def __init__(self, 
            num : int, 
            key_name : str):
        self.num : int = num
        self.key_name : str = key_name
    
    def getName(self) -> str:
        return self.key_name
    
# duplicate check
name_checker_set : set[str] = set()
id_checker_set : set[int] = set()
for v in ItemIdentifierKey:
    if v.getName() in name_checker_set:
        raise Exception(f"Duplicated name [{v.getName()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.getName())
    id_checker_set.add(v.value[0])