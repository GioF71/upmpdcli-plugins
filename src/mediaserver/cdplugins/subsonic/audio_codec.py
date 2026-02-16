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


from enum import Enum


class _AudioCodecData:

    def __init__(
            self,
            codec_name: str,
            lossless: bool,
            suffixes: list[str] = None):
        self.__codec_name: str = codec_name
        self.__lossless: bool = lossless
        self.__suffixes: list[str] = (list(map(lambda x: x.lower(), suffixes))
                                      if len(suffixes if suffixes else []) > 0 else codec_name.lower())

    @property
    def codec_name(self) -> str:
        return self.__codec_name

    @property
    def lossless(self) -> str:
        return self.__lossless

    @property
    def suffixes(self) -> list[str]:
        return self.__suffixes


class AudioCodec(Enum):

    FLAC = _AudioCodecData(
        codec_name="flac",
        lossless=True,
        suffixes=["flac", "flc", "fla"])
    ALAC = _AudioCodecData(
        codec_name="alac",
        lossless=True)
    DSF = _AudioCodecData(
        codec_name="dsf",
        lossless=True)
    DFF = _AudioCodecData(
        codec_name="dff",
        lossless=True)
    WAV = _AudioCodecData(
        codec_name="wav",
        lossless=True)
    AIFF = _AudioCodecData(
        codec_name="aiff",
        lossless=True,
        suffixes=["aiff", "aif"])
    M4A = _AudioCodecData(
        codec_name="m4a",
        lossless=False)
    MP3 = _AudioCodecData(
        codec_name="mp3",
        lossless=False)
    MP2 = _AudioCodecData(
        codec_name="mp2",
        lossless=False)
    OGG = _AudioCodecData(
        codec_name="ogg",
        lossless=False)
    OPUS = _AudioCodecData(
        codec_name="opus",
        lossless=False)

    @property
    def codec_name(self) -> str:
        return self.value.codec_name

    @property
    def lossless(self) -> str:
        return self.value.lossless

    @property
    def suffixes(self) -> list[str]:
        return self.value.suffixes[:]


class LosslessStatus(Enum):

    LOSSLESS = "lossless"
    LOSSY = "lossy"
    MIXED = "mixed"


def get_lossless_status_by_value(v: str) -> LosslessStatus:
    if not v:
        raise Exception("Provide a valid lossless_status_value")
    curr: LosslessStatus
    for curr in LosslessStatus:
        if curr.value == v:
            return curr
    raise Exception(f"get_lossless_status_by_value no match for [{v}]")


def is_lossless(suffix: str):
    if not suffix:
        raise Exception("is_lossless requires a valid suffix")
    lower_suffix: str = suffix.lower()
    audio_codec: AudioCodec
    for audio_codec in AudioCodec:
        if not audio_codec.lossless:
            continue
        if lower_suffix in audio_codec.suffixes:
            return True
    return False


def is_lossy(suffix: str):
    return not is_lossless(suffix)


def get_lossless_status(suffix: str) -> LosslessStatus:
    v: bool = is_lossless(suffix)
    return LosslessStatus.LOSSLESS if (v is True) else LosslessStatus.LOSSY
