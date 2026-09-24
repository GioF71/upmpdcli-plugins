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


from enum import Enum
from radio_station_entry import RadioStationEntry


def get_base_url() -> str:
    return "stream.motherearthradio.de"


def get_base_listen_url() ->  str: 
    return f"https://{get_base_url()}/listen"


class Codec(Enum):
    FLAC = "flac"
    AAC = "aac"
    MP3 = "mp3"


class MimeType(Enum):
    FLAC = "audio/flac"
    AAC = "audio/aac"
    MP3 = "audio/mpeg"


class RadioTitle(Enum):
    MAIN = "Mother Earth Main"
    JAZZ = "Mother Earth Jazz"
    KLASSIK = "Mother Earth Klassik"
    INSTRUMENTAL = "Mother Earth Instrumental"


class RadioStation(Enum):

    MAIN_FLAC_MONO = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth/motherearth.mono",
        title=RadioTitle.MAIN.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=192000,
        channel_count=1)
    MAIN_FLAC_192_24 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth/motherearth",
        title=RadioTitle.MAIN.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=192000)
    MAIN_FLAC_96_24 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth/motherearth.flac-lo",
        title=RadioTitle.MAIN.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=96000)
    MAIN_AAC_24_96 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth/motherearth.aac",
        title=RadioTitle.MAIN.value,
        codec=Codec.AAC.value,
        mimetype=MimeType.AAC.value,
        bit_depth=24,
        sampling_rate=96000,
        channel_count=2)
    MAIN_AAC_16_48 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth/motherearth.aac-lo",
        title=RadioTitle.MAIN.value,
        codec=Codec.AAC.value,
        mimetype=MimeType.AAC.value,
        bit_depth=24,
        sampling_rate=48000,
        channel_count=2)
    MAIN_MP3_16_44 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth/motherearth.mp3",
        title=RadioTitle.MAIN.value,
        codec=Codec.MP3.value,
        mimetype=MimeType.MP3.value,
        bit_depth=16,
        sampling_rate=44100,
        channel_count=2)

    JAZZ_FLAC_MONO = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_jazz/motherearth.jazz.mono",
        title=RadioTitle.JAZZ.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=192000,
        channel_count=1)
    JAZZ_FLAC_192_24 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_jazz/motherearth.jazz",
        title=RadioTitle.JAZZ.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=192000)
    JAZZ_FLAC_96_24 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_jazz/motherearth.jazz.flac-lo",
        title=RadioTitle.JAZZ.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=96000)
    JAZZ_AAC_24_96 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_jazz/motherearth.jazz.mp4",
        title=RadioTitle.JAZZ.value,
        codec=Codec.AAC.value,
        mimetype=MimeType.AAC.value,
        bit_depth=24,
        sampling_rate=96000,
        channel_count=2)
    JAZZ_AAC_16_48 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_jazz/motherearth.jazz.aac-lo",
        title=RadioTitle.JAZZ.value,
        codec=Codec.AAC.value,
        mimetype=MimeType.AAC.value,
        bit_depth=24,
        sampling_rate=48000,
        channel_count=2)
    JAZZ_MP3_16_44 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_jazz/motherearth.jazz.mp3",
        title=RadioTitle.JAZZ.value,
        codec=Codec.MP3.value,
        mimetype=MimeType.MP3.value,
        bit_depth=16,
        sampling_rate=44100,
        channel_count=2)

    CLASSIC_FLAC_MONO = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_klassik/motherearth.klassik.mono",
        title=RadioTitle.KLASSIK.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=192000,
        channel_count=1)
    CLASSIC_FLAC_192_24 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_klassik/motherearth.klassik",
        title=RadioTitle.KLASSIK.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=192000)
    CLASSIC_FLAC_96_24 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_klassik/motherearth.klassik.flac-lo",
        title=RadioTitle.KLASSIK.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=96000)
    CLASSIC_AAC_24_96 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_klassik/motherearth.klassik.aac",
        title=RadioTitle.KLASSIK.value,
        codec=Codec.AAC.value,
        mimetype=MimeType.AAC.value,
        bit_depth=24,
        sampling_rate=96000,
        channel_count=2)
    CLASSIC_AAC_16_48 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_klassik/motherearth.klassik.aac-lo",
        title=RadioTitle.KLASSIK.value,
        codec=Codec.AAC.value,
        mimetype=MimeType.AAC.value,
        bit_depth=24,
        sampling_rate=48000,
        channel_count=2)
    CLASSIC_MP3_16_44 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_klassik/motherearth.klassik.mp3",
        title=RadioTitle.KLASSIK.value,
        codec=Codec.MP3.value,
        mimetype=MimeType.MP3.value,
        bit_depth=16,
        sampling_rate=44100,
        channel_count=2)


    INSTRUMENTAL_FLAC_MONO = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_instrumental/motherearth.instrumental.mono",
        title=RadioTitle.INSTRUMENTAL.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=192000,
        channel_count=1)
    INSTRUMENTAL_FLAC_192_24 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_instrumental/motherearth.instrumental",
        title=RadioTitle.INSTRUMENTAL.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=192000)
    INSTRUMENTAL_FLAC_96_24 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_instrumental/motherearth.instrumental.flac-lo",
        title=RadioTitle.INSTRUMENTAL.value,
        codec=Codec.FLAC.value,
        mimetype=MimeType.FLAC.value,
        bit_depth=24,
        sampling_rate=96000)
    INSTRUMENTAL_AAC_24_96 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_instrumental/motherearth.instrumental.aac",
        title=RadioTitle.INSTRUMENTAL.value,
        codec=Codec.AAC.value,
        mimetype=MimeType.AAC.value,
        bit_depth=24,
        sampling_rate=96000,
        channel_count=2)
    INSTRUMENTAL_AAC_16_48 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_instrumental/motherearth.instrumental.aac-lo",
        title=RadioTitle.INSTRUMENTAL.value,
        codec=Codec.AAC.value,
        mimetype=MimeType.AAC.value,
        bit_depth=24,
        sampling_rate=48000,
        channel_count=2)
    INSTRUMENTAL_MP3_16_44 = RadioStationEntry(
        url=f"{get_base_listen_url()}/motherearth_instrumental/motherearth.instrumental.mp3",
        title=RadioTitle.INSTRUMENTAL.value,
        codec=Codec.MP3.value,
        mimetype=MimeType.MP3.value,
        bit_depth=16,
        sampling_rate=44100,
        channel_count=2)


def get_by_name(station_name: str) -> RadioStationEntry:
    curr: RadioStationEntry
    for curr in RadioStation:
        if curr.name == station_name:
            return curr
    return None


radio_station_list: list[RadioStationEntry] = list([x.value for x in RadioStation])

