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
codec_mp3: str = "mp3"

mimetype_flac: str = "audio/flac"
mimetype_aac: str = "audio/aac"
mimetype_mp3: str = "audio/mp3"

radio_station_list: list[RadioStationEntry] = list()


def __add(codec: str, url: str, title: str, mimetype: str):
    id: int = len(radio_station_list) + 1
    e: RadioStationEntry = RadioStationEntry(
        id=id, url=url, codec=codec, title=title, mimetype=mimetype
    )
    radio_station_list.append(e)


__add(
    url="https://motherearth.streamserver24.com/listen/motherearth/motherearth",
    title="Mother Earth Radio",
    codec=codec_flac,
    mimetype=mimetype_flac,
)
__add(
    url="https://motherearth.streamserver24.com/listen/motherearth/motherearth.aac",
    title="Mother Earth Radio",
    codec=codec_aac,
    mimetype=mimetype_aac,
)
__add(
    url="https://motherearth.streamserver24.com/listen/motherearth/motherearth.mp3",
    title="Mother Earth Radio",
    codec=codec_mp3,
    mimetype=mimetype_mp3,
)
__add(
    url="https://motherearth.streamserver24.com/listen/motherearth_klassik/motherearth.klassik",
    title="Mother Earth Klassik",
    codec=codec_flac,
    mimetype=mimetype_flac,
)
__add(
    url="https://motherearth.streamserver24.com/listen/motherearth_klassik/motherearth.klassik.aac",
    title="Mother Earth Klassik",
    codec=codec_aac,
    mimetype=mimetype_aac,
)
__add(
    url="https://motherearth.streamserver24.com/listen/motherearth_klassik/motherearth.klassik.mp3",
    title="Mother Earth Klassik",
    codec=codec_mp3,
    mimetype=mimetype_mp3,
)
__add(
    url="https://motherearth.streamserver24.com/listen/motherearth_instrumental/motherearth.instrumental",
    title="Mother Earth Instrumental",
    codec=codec_flac,
    mimetype=mimetype_flac,
)
__add(
    url="https://motherearth.streamserver24.com/listen/motherearth_instrumental/motherearth.instrumental.aac",
    title="Mother Earth Instrumental",
    codec=codec_aac,
    mimetype=mimetype_aac,
)
__add(
    url="https://motherearth.streamserver24.com/listen/motherearth_instrumental/motherearth.instrumental.mp3",
    title="Mother Earth Instrumental",
    codec=codec_mp3,
    mimetype=mimetype_mp3,
)
