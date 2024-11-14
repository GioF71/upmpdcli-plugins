# Copyright (C) 2024 Giovanni Fulco
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

from context_key import ContextKey


class Context:

    def __init__(self):
        self._dict: dict[str, any] = dict()

    def __not_null(self, key: ContextKey):
        if not key: raise Exception("Provided key is None")

    def __raise_missing_key(self, key_str: str):
        raise Exception(f"Missing key [{key_str}]")

    def __not_in(self, key: ContextKey):
        self.__not_null(key)
        if key in self._dict: raise Exception(f"Duplicate key [{key.name}]")

    def contains(self, key: ContextKey) -> bool:
        self.__not_null(key)
        return key.name in self._dict

    def add(self, key: ContextKey, value: any, allow_update: bool = False):
        if allow_update:
            self.__not_null(key)
        else:
            self.__not_in(key)
        self._dict[key.name] = value

    def update(self, key: ContextKey, value: any):
        self.add(key=key, value=value, allow_update=True)

    def increment(self, key: ContextKey):
        v: any = self.get(key=key)
        if not isinstance(v, int): raise Exception(f"Item at key [{key.name}] is not a int")
        self.update(key=key, value=int(v) + 1)

    def get(self, key: ContextKey, allow_empty: bool = True):
        self.__not_null(key)
        if not allow_empty and key.name not in self._dict:
            self.__raise_missing_key(key.name)
        return self._dict[key.name] if key.name in self._dict else key.default_value

    def remove(self, key: ContextKey, allow_empty: bool = True):
        if key.name in self.__dict:
            del self._dict[key.name]
        else:
            if not allow_empty:
                raise Exception(f"Missing key [{key.name}]")

    def __get_dict(self, dict_key: ContextKey, allow_empty: bool = True) -> dict[str, any]:
        select_dict: dict[str, any] = self.get(key=dict_key)
        if not select_dict:
            if not allow_empty: raise Exception(f"Key [{dict_key.name}] not found")
            select_dict = dict()
            self.add(key=dict_key, value=select_dict)
        else:
            # is it a dictionary?
            if not isinstance(select_dict, dict):
                raise Exception(f"Element by key [{dict_key.name}] is not a dictionary")
        return select_dict

    def dict_add(
            self,
            dict_key: ContextKey,
            entry_key: str,
            entry_value: any,
            allow_empty: bool = True,
            allow_update: bool = False):
        # check if key exists
        select_dict: dict[str, any] = self.__get_dict(dict_key=dict_key, allow_empty=allow_empty)
        if entry_key in select_dict and not allow_update: raise Exception(f"Duplicate key [{entry_key}]")
        select_dict[entry_key] = entry_value

    def dict_update(
            self,
            dict_key: ContextKey,
            entry_key: str,
            entry_value: any,
            allow_empty: bool = True):
        self.dict_add(
            dict_key=dict_key,
            entry_key=entry_key,
            entry_value=entry_value,
            allow_empty=allow_empty,
            allow_update=True)

    def dict_remove(
            self,
            dict_key: ContextKey,
            entry_key: str,
            allow_empty: bool = True,
            allow_missing: bool = True):
        select_dict: dict[str, any] = self.__get_dict(dict_key=dict_key, allow_empty=allow_empty)
        if entry_key in select_dict:
            del select_dict[entry_key]
        else:
            if not allow_missing: raise Exception(f"Key [{entry_key}] not found")

    def dict_get(
            self,
            dict_key: ContextKey,
            entry_key: str,
            allow_empty: bool = True,
            allow_missing: bool = True,
            default_value: any = None) -> bool:
        select_dict: dict[str, any] = self.__get_dict(dict_key=dict_key, allow_empty=allow_empty)
        if entry_key not in select_dict:
            if not allow_missing: raise Exception(f"Key [{entry_key}] not found")
            return default_value
        else:
            return select_dict[entry_key]

    def dict_contains(
            self,
            dict_key: ContextKey,
            entry_key: str,
            allow_empty: bool = True) -> bool:
        select_dict: dict[str, any] = self.__get_dict(dict_key=dict_key, allow_empty=allow_empty)
        return entry_key in select_dict
