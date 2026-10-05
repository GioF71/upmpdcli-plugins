# Copyright (C) 2023,2024,2025,2026 Giovanni Fulco
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

import copy
import random
import string
from typing import Any

import config
import constants
from item_identifier_key import ItemIdentifierKey


class ItemIdentifierException(Exception):
    """Raised when a ItemIdentifier error occurs."""


class ItemIdentifier:

    def randomword(self, length) -> str:
        letters: str = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(length))

    @classmethod
    def from_dict(cls, id_dict: dict[str, Any]):
        thing_name: str = ItemIdentifier.__check_mandatory(id_dict, ItemIdentifierKey.THING_NAME)
        thing_value: Any = ItemIdentifier.__check_mandatory(id_dict, ItemIdentifierKey.THING_VALUE)
        id: ItemIdentifier = cls(thing_name, thing_value)
        for k, v in id_dict.items():
            if not id.__has_name(k):
                id.__set(k, v)
        return id

    def __check_mandatory(id_dict: dict[str, Any], id_key: ItemIdentifierKey) -> Any:
        if id_key.identifier_name not in id_dict:
            raise ItemIdentifierException(f"Mandatory [{id_key.identifier_name}] missing")
        return id_dict[id_key.identifier_name]

    def __init__(self, name: str, value: Any):
        self.__dict: dict[str, Any] = {}
        if not name:
            raise ItemIdentifierException("name cannot be empty")
        if not value:
            raise ItemIdentifierException("value cannot be empty")
        self.set(ItemIdentifierKey.THING_NAME, name)
        self.set(ItemIdentifierKey.THING_VALUE, value)
        if config.get_config_param_as_bool(constants.ConfigParam.ENABLE_RANDOM_ID):
            random_value: str = self.randomword(6)
            self.set(ItemIdentifierKey.RANDOM_VALUE, random_value)

    def getDictionary(self):
        return copy.deepcopy(self.__dict)

    def has(self, key: ItemIdentifierKey):
        return self.__has_name(key.identifier_name)

    def __has_name(self, name: str):
        return name in self.__dict

    def get(self, key: ItemIdentifierKey, defaultValue: Any = None):
        return self.__get(key.identifier_name, defaultValue)

    def __get(self, key_name: str, defaultValue: Any = None):
        return self.__dict.get(key_name, defaultValue)

    def set(self, key: ItemIdentifierKey, value):
        if not self.__valid_key(key):
            raise ItemIdentifierException(f"Key {key.identifier_name if key else None} already set")
        self.__set(key.identifier_name, value)

    def __set(self, key_name: str, value):
        if not self.__valid_key_name(key_name):
            raise ItemIdentifierException(f"Key {key_name} already set")
        self.__dict[key_name] = value

    def __valid_key(self, key: ItemIdentifierKey) -> bool:
        return key and self.__valid_key_name(key.identifier_name)

    def __valid_key_name(self, key_name: str) -> bool:
        return key_name and key_name not in self.__dict
