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

from item_identifier import ItemIdentifier
from html import escape

import codec

import json


def __escape_objid(value : str) -> str:
    return escape(value, quote = True)


def create_objid(objid, id : str) -> str:
    return objid + "/" + __escape_objid(id)


def create_id_from_identifier(identifier : ItemIdentifier) -> str:
    return codec.encode(json.dumps(identifier.getDictionary()))
