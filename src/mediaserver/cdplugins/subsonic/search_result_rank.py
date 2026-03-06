# Copyright (C) 2026 Giovanni Fulco
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
from typing import Callable, List, TypeVar

from artist_metadata import ArtistMetadata
from search_util import simplify


class _SearchResultRank:
    def __init__(self, rank_value: int):
        self.__rank_value: int = rank_value

    @property
    def rank_value(self) -> int:
        return self.__rank_value


class SearchResultRank(Enum):
    MATCH_EXACT = _SearchResultRank(rank_value=1)
    MATCH_CASE_SENSITIVE = _SearchResultRank(rank_value=2)
    MATCH_CASE_INSENSITIVE = _SearchResultRank(rank_value=3)
    STARTS_WITH_EXACT = _SearchResultRank(rank_value=4)
    STARTS_WITH_CASE_SENSITIVE = _SearchResultRank(rank_value=5)
    STARTS_WITH_CASE_INSENSITIVE = _SearchResultRank(rank_value=6)
    ENDS_WITH_EXACT = _SearchResultRank(rank_value=7)
    ENDS_WITH_CASE_SENSITIVE = _SearchResultRank(rank_value=8)
    ENDS_WITH_CASE_INSENSITIVE = _SearchResultRank(rank_value=9)
    CONTAINS_EXACT = _SearchResultRank(rank_value=10)
    CONTAINS_CASE_SENSITIVE = _SearchResultRank(rank_value=11)
    CONTAINS_CASE_INSENSITIVE = _SearchResultRank(rank_value=12)

    @property
    def rank_value(self) -> int:
        return self.value.rank_value

    def is_match(self, sv: str, sv_s: str, sv_l: str, n: str, n_s: str, n_l: str) -> bool:
        """
        sv: search_value, sv_s: simplified, sv_l: lower
        n: name, n_s: name_simplified, n_l: name_lower
        """
        match self:
            case SearchResultRank.MATCH_EXACT:
                return n == sv
            case SearchResultRank.MATCH_CASE_SENSITIVE:
                return n_s == sv_s
            case SearchResultRank.MATCH_CASE_INSENSITIVE:
                return n_l == sv_l
            case SearchResultRank.STARTS_WITH_EXACT:
                return n.startswith(sv)
            case SearchResultRank.STARTS_WITH_CASE_SENSITIVE:
                return n_s.startswith(sv_s)
            case SearchResultRank.STARTS_WITH_CASE_INSENSITIVE:
                return n_l.startswith(sv_l)
            case SearchResultRank.ENDS_WITH_EXACT:
                return n.endswith(sv)
            case SearchResultRank.ENDS_WITH_CASE_SENSITIVE:
                return n_s.endswith(sv_s)
            case SearchResultRank.ENDS_WITH_CASE_INSENSITIVE:
                return n_l.endswith(sv_l)
            case SearchResultRank.CONTAINS_EXACT:
                return sv in n
            case SearchResultRank.CONTAINS_CASE_SENSITIVE:
                return sv_s in n_s
            case SearchResultRank.CONTAINS_CASE_INSENSITIVE:
                return sv_l in n_l
            case _:
                return False


def sort_artist_list_by_rank(
        search_value: str,
        artist_list: list[ArtistMetadata]) -> list[ArtistMetadata]:
    def get_names(a: ArtistMetadata) -> list[str]:
        return [a.artist_name, a.artist_sort_name] if a.artist_sort_name else [a.artist_name]
    return sort_obj_by_rank(
        search_value=search_value,
        obj_list=artist_list,
        key=get_names)


T = TypeVar("T")


def sort_obj_by_rank(
        search_value: str,
        obj_list: List[T],
        key: Callable[[T], List[str]]) -> List[T]:
    if not obj_list or len(obj_list) == 0:
        return []
    # Pre-calculate search variants once
    sv_s = simplify(search_value)
    sv_l = sv_s.lower()
    ranked_list: list[tuple[T, int]] = []
    for curr in obj_list:
        found_rank = None
        # Pre-process all names for THIS object once
        names_data = []
        for name in key(curr):
            n_s = simplify(name)
            names_data.append((name, n_s, n_s.lower()))
        # Now check those pre-processed names against each rank
        for rank_member in SearchResultRank:
            for n, n_s, n_l in names_data:
                if rank_member.is_match(search_value, sv_s, sv_l, n, n_s, n_l):
                    found_rank = rank_member.rank_value
                    break
            if found_rank:
                break
        if found_rank:
            ranked_list.append((curr, found_rank))
    if ranked_list:
        ranked_list.sort(key=lambda x: x[1])
        return [item[0] for item in ranked_list]
    return obj_list
