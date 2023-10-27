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

from radio_station_entry import RadioStationEntry

codec_flac: str = "flac"
codec_aac: str = "aac"

mimetype_flac: str = "audio/flac"
mimetype_aac: str = "audio/aac"

title_main_mix : str = "Radio Paradise Main Mix"
title_mellow_mix : str = "Radio Paradise Mellow Mix"
title_rock_mix : str = "Radio Paradise Rock Mix"
title_global_mix : str = "Radio Paradise Global Mix"

radio_station_list: list[RadioStationEntry] = list()

def __add(codec : str, url : str, title : str, mimetype : str, bitrate : int = None):
    id : int = len(radio_station_list) + 1
    e : RadioStationEntry = RadioStationEntry(
        id = id, 
        codec = codec,
        url = url,
        title = title,
        mimetype = mimetype,
        bitrate = bitrate)
    radio_station_list.append(e)

__add(
    url="http://stream.radioparadise.com/flacm",
    title=title_main_mix,
    codec=codec_flac,
    mimetype=mimetype_flac)

__add(
    url="http://stream.radioparadise.com/aac-320",
    title=title_main_mix,
    codec=codec_aac,
    mimetype=mimetype_aac,
    bitrate=320)

__add(
    url="http://stream.radioparadise.com/aac-128",
    title=title_main_mix,
    codec=codec_aac,
    mimetype=mimetype_aac,
    bitrate=128)

__add(
    url="http://stream.radioparadise.com/mellow-flacm",
    title=title_mellow_mix,
    codec=codec_flac,
    mimetype=mimetype_flac)

__add(
    url="http://stream.radioparadise.com/mellow-320",
    title=title_mellow_mix,
    codec=codec_aac,
    mimetype=mimetype_aac,
    bitrate=320)

__add(
    url="http://stream.radioparadise.com/mellow-128",
    title=title_mellow_mix,
    codec=codec_aac,
    mimetype=mimetype_aac,
    bitrate=128)

__add(
    url="http://stream.radioparadise.com/rock-flacm",
    title=title_rock_mix,
    codec=codec_flac,
    mimetype=mimetype_flac)

__add(
    url="http://stream.radioparadise.com/rock-320",
    title=title_rock_mix,
    codec=codec_aac,
    mimetype=mimetype_aac,
    bitrate=320)

__add(
    url="http://stream.radioparadise.com/rock-128",
    title=title_rock_mix,
    codec=codec_aac,
    mimetype=mimetype_aac,
    bitrate=128)

__add(
    url="http://stream.radioparadise.com/global-flacm",
    title=title_global_mix,
    codec=codec_flac,
    mimetype=mimetype_flac)

__add(
    url="http://stream.radioparadise.com/global-320",
    title=title_global_mix,
    codec=codec_aac,
    mimetype=mimetype_aac,
    bitrate=320)

__add(
    url="http://stream.radioparadise.com/global-128",
    title=title_global_mix,
    codec=codec_aac,
    mimetype=mimetype_aac,
    bitrate=128)
