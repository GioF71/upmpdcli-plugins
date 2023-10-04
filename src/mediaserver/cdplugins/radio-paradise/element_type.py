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
    TAG = 0, "tag"
    RADIO_ENTRY = 1, "ntr",
    ENTRY_BY_CODEC = 2, "ntrbc",
    ENTRY_BY_TITLE = 3, "ntrbt"

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
for v in ElementType:
    if v.getName() in name_checker_set:
        raise Exception(f"Duplicated name [{v.getName()}]")
    if v.value[0] in id_checker_set:
        raise Exception(f"Duplicated id [{v.value[0]}]")
    name_checker_set.add(v.getName())
    id_checker_set.add(v.value[0])