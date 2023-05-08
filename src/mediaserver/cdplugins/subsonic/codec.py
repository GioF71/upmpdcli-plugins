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

import base64

class Codec:

    def encode(self, name : str) -> str:
        message_bytes : bytes = name.encode('ascii')
        base64_bytes : bytes = base64.b64encode(message_bytes)
        id : str = base64_bytes.decode('ascii')
        return id

    def decode(self, id : str) -> str:
        base64_bytes : bytes = id.encode('ascii')
        message_bytes : bytes = base64.b64decode(base64_bytes)
        name : str = message_bytes.decode('ascii')
        return name
