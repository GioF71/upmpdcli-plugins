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


import json
import codec


class ValueHolder:

    def __init__(self, value: str):
        self.__value: str = value
    
    @property
    def value(self) -> str:
        return self.__value
    

def encode_value_holder(value: str) -> str:
    value_holder: ValueHolder = ValueHolder(value=value)
    d: dict[str, str] = {"value": value_holder.value}
    return codec.base64_encode(json.dumps(d))

def decode_value_holder(encoded: str) -> str:
    decoded: str = codec.base64_decode(encoded)
    d: dict[str, str] = json.loads(decoded)
    value_holder: ValueHolder = ValueHolder(value=d["value"])
    return value_holder.value