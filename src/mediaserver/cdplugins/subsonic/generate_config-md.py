#!/usr/bin/env python3

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


import constants
from pathlib import Path


header: list[str] = [
    "# Configuration Parameters",
    "",
    "## Read this first",
    "",
    "The following is a non-exaustive list of the configuration options for the subsonic plugin.  ",
    "All the variable names must be prepended with `subsonic` when you add them to your upmpdcli.conf file.  ",
    "For boolean values (distinguishable because the default is True or False), you will have to use 1 or 0.",
    "",
    "## List of variables",
    "",
    "VARIABLE|DESCRIPTION|DEFAULT_VALUE",
    ":---|:---|:---"
    ]


def generate():
    cnt: int = 0
    print("Generating ...")
    script_dir = Path(__file__).parent.absolute()
    file_path = script_dir / "config.md"
    with open(file_path, "w", encoding="utf-8") as f:
        curr: str
        for curr in header:
            f.write(f"{curr}\n")
    with open(file_path, "a", encoding="utf-8") as f:
        config_param: constants.ConfigParam
        for config_param in constants.ConfigParam:
            f.write(f"{config_param.key}|{config_param.description}|{config_param.default_value}\n")
            cnt += 1
    print(f"Generation complete [{cnt} entries])")


if __name__ == "__main__":
    generate()
