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

import base64
import constants
import config
from msgproc_provider import msgproc
import persistence
from cache_type import CacheType
import sqlite3


__encoding: str = "utf-8"


def encode(data: str) -> str:
    if config.get_config_param_as_bool(constants.ConfigParam.MINIMIZE_IDENTIFIER_LENGTH):
        encoded_name: str = base64_encode(data)
        connection: sqlite3.Connection = persistence.get_working_connection(provided=None)
        kv_list: list[persistence.KeyValueItem] = persistence.get_kv_items_by_value(
            partition=CacheType.ITEM_IDENTIFIER_CODEC.cache_name,
            value=encoded_name,
            connection=connection)
        if len(kv_list) > 1:
            raise Exception(f"Duplicate entries for [{encoded_name}]")
        kv_item: persistence.KeyValueItem = kv_list[0] if len(kv_list) == 1 else None
        if kv_item:
            return kv_item.key
        else:
            persistence.lock_immediate(connection=connection)
            id_count: int = persistence.get_kv_partition_count(
                partition=CacheType.ITEM_IDENTIFIER_CODEC.cache_name,
                connection=connection)
            new_id: str = str(id_count + 1)
            persistence.save_kv_item(key_value_item=persistence.KeyValueItem(
                partition=CacheType.ITEM_IDENTIFIER_CODEC.cache_name,
                key=new_id,
                value=encoded_name),
                connection=connection,
                do_commit=True)
            return str(new_id)
    else:
        return base64_encode(data)


def decode(id: str) -> str:
    if config.get_config_param_as_bool(constants.ConfigParam.MINIMIZE_IDENTIFIER_LENGTH):
        # must be in dict, otherwise we get an exception
        encoded_kv: persistence.KeyValueItem = persistence.get_kv_item(
            partition=CacheType.ITEM_IDENTIFIER_CODEC.cache_name,
            key=id)
        if encoded_kv is None:
            raise Exception(f"codec.decode id [{id}] not found, please browse from the root of the plugin")
        # decode encoded value
        return base64_decode(encoded_kv.value)
    else:
        return base64_decode(id)


def base64_encode(v: str) -> str:
    message_bytes: bytes = v.encode(__encoding)
    base64_bytes: bytes = base64.b64encode(message_bytes)
    id: str = base64_bytes.decode(__encoding)
    return id


def base64_decode(encoded: str) -> str:
    missing_padding: int = len(encoded) % 4
    data: str = encoded
    if missing_padding != 0:
        # add missing padding characters
        data += '=' * (4 - missing_padding)
        if config.get_config_param_as_bool(constants.ConfigParam.VERBOSE_LOGGING):
            msgproc.log(f"codec.base64_decode sanitized [{data}] "
                        f"(added [{4 - missing_padding}] padding characters)")
    base64_bytes: bytes = data.encode(__encoding)
    message_bytes: bytes = base64.b64decode(base64_bytes)
    name: str = message_bytes.decode(__encoding)
    return name
