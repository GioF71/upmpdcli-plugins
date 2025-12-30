# Copyright (C) 2025 Giovanni Fulco
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


def __number_to_base(n: int, b: int) -> list[int]:
    if n == 0:
        return [0]
    digits = []
    while n:
        digits.append(int(n % b))
        n //= b
    return digits[::-1]


def number_to_base_decoded(n: int, base_chars: str) -> str:
    result: str = ""
    cnv: list[int] = __number_to_base(n=n, b=len(base_chars))
    curr: int
    for curr in cnv:
        result += base_chars[curr]
    return result
