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


import os
import shutil
from enum import Enum
from pathlib import Path
from typing import NamedTuple

import cmdtalkplugin
import upmplgutils

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)


def publish_icon(plugin_name: str):
    doc_root: str | None = upmplgutils.getUpnpWebDocRoot(plugin_name)
    # sanitization: we just rely on getUpnpWebDocRoot for now
    doc_root_enabled: bool = doc_root is not None
    msgproc.log(f"Publishing icon requested for [{plugin_name}], webDocumentRoot is enabled [{doc_root_enabled}]")
    if doc_root is not None:
        pkg_datadir: str = upmplgutils.getOptionValue("pkgdatadir")
        cdplugins_path: str = os.path.join(pkg_datadir, "cdplugins")
        plugin_path: str = os.path.join(cdplugins_path, plugin_name)
        msgproc.log(f"plugin_icon [{plugin_name}] plugin path [{plugin_path}]")
        # check if file exists
        icon_file: __IconFile | None
        icon_file = __find_icon_file(
            cdplugins_path=cdplugins_path,
            plugin_path=plugin_path,
            plugin_name=plugin_name)
        msgproc.log(f"Icon file [{icon_file}] available for plugin [{plugin_name}]")
        if icon_file is not None:
            # now copy the file
            # dest_file_name: str = os.path.join(doc_root, "cdplugins")
            src_file: str = os.path.join(icon_file.file_path, f"{icon_file.file_name}.{icon_file.file_extension.value}")
            dst_file: str = os.path.join(doc_root, f"{plugin_name}-icon.{icon_file.file_extension.value}")
            msgproc.log(f"Copying icon file [{src_file}] for [{plugin_name}] to [{dst_file}] ...")
            shutil.copy2(src_file, dst_file)
            msgproc.log(f"Copied icon file [{src_file}] for [{plugin_name}] to [{dst_file}].")


class SupportedExtension(Enum):

    JPG = "jpg"
    PNG = "png"


class __IconFile(NamedTuple):
    file_path: str
    file_name: str
    file_extension: SupportedExtension


def __find_icon_file(cdplugins_path: str, plugin_path: str, plugin_name: str) -> __IconFile | None:
    curr: SupportedExtension
    for curr in SupportedExtension:
        # build logo file name
        file_name_noext: str = f"{plugin_name}-icon"
        file_name: str =  f"{file_name_noext}.{curr.value}"
        f_name: str = os.path.join(plugin_path, file_name)
        msgproc.log(f"Searching for [{f_name}]")
        # file exists?
        f_path: Path = Path(f_name)
        f_exists: bool = f_path.is_file()
        if f_exists:
            return __IconFile(
                file_path=plugin_path,
                file_name=file_name_noext,
                file_extension=curr)
    # still nothing? use fallback if available
    for curr in SupportedExtension:
        # build icon file name
        file_name: str = f"plugin.{curr.value}"
        f_name: str = os.path.join(cdplugins_path, file_name)
        msgproc.log(f"Searching for [{f_name}]")
        # file exists?
        f_path: Path = Path(f_name)
        f_exists: bool = f_path.is_file()
        if f_exists:
            return __IconFile(
                file_path=cdplugins_path,
                file_name="plugin",
                file_extension=curr)
    return None