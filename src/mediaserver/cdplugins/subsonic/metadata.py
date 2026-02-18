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

from column_name import ColumnName
from typing import Any
from typing import Optional
from typing import Protocol


# We still use a small Protocol just so the linter knows the Enum
# members have a .column_name.value attribute.
class MetadataMember(Protocol):
    @property
    def column_name(self) -> ColumnName: ...


class Metadata:
    def __init__(self):
        self.__data: dict[Any, Any] = {}

    def _set(self, key: Any, value: Any) -> None:
        """Internal helper to update the data dictionary."""
        if value is None:
            return
        if isinstance(value, str) and len(value) == 0:
            return
        self.__data[key] = value

    def _get(self, key: Any) -> Optional[Any]:
        """Internal helper to retrieve values from the data dictionary."""
        return self.__data.get(key)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.__data})"
