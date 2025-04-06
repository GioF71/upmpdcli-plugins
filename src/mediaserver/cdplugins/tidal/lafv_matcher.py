# Copyright (C) 2023,2024,2025 Giovanni Fulco
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
# from msgproc_provider import msgproc


class LavfMatchMode(Enum):
    EQ = 1  # exact only
    GE = 2  # exact or better


class LavfConstant(Enum):
    PREFIX = "Lavf/"
    INITIAL_SPLITTER = "/"
    VERSION_SPLITTER = "."


def match(to_match: str, pattern: str, match_mode: LavfMatchMode = LavfMatchMode.EQ) -> bool:
    # msgproc.log(f"Matching on to_match: [{to_match}] pattern: [{pattern}] mode: [{match_mode}]")
    # sanity checks.
    if (not to_match or
            not pattern or
            not to_match.startswith(LavfConstant.PREFIX.value) or
            not pattern.startswith(LavfConstant.PREFIX.value)):
        # msgproc.log(f"Invalid to_match [{to_match}] or pattern [{pattern}]")
        return False
    # can do the split?
    to_match_splitted: list[str] = to_match.split(LavfConstant.INITIAL_SPLITTER.value)
    pattern_splitted: list[str] = pattern.split(LavfConstant.INITIAL_SPLITTER.value)
    if not to_match_splitted or len(to_match_splitted) != 2:
        return False
    if not pattern_splitted or len(pattern_splitted) != 2:
        # msgproc.log(f"Cannot split, len is [{len(pattern_splitted) if pattern_splitted else 0}]")
        return False
    # split complete, check versions.
    to_match_version: str = to_match_splitted[1]
    pattern_version: str = pattern_splitted[1]
    # msgproc.log(f"to_match_version [{to_match_version}] pattern_version [{pattern_version}]")
    same: bool = to_match_version == pattern_version
    if same:
        return True
    if not same and match_mode == LavfMatchMode.EQ:
        return False
    # compare the versions.
    to_match_v_array: list[str] = to_match_version.split(LavfConstant.VERSION_SPLITTER.value)
    pattern_v_array: list[str] = pattern_version.split(LavfConstant.VERSION_SPLITTER.value)
    for i in range(0, min(len(to_match_v_array), len(pattern_v_array))):
        t: int = _to_int(to_match_v_array[i])
        p: int = _to_int(pattern_v_array[i])
        if t is not None and p is not None:
            if t > p:
                return True
            elif t < p:
                return False
        else:
            return False
    # if we are here, they are the same version if the length is the same
    if len(to_match_v_array) >= len(pattern_v_array):
        return True
    return False


def _to_int(v: str) -> int:
    try:
        return int(v)
    except Exception:
        return None
