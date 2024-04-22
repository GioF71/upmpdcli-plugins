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


from tidalapi import Quality as TidalQuality


class StreamingInfo:

    def __init__(self):
        self._url : str = None
        self._mimetype : str = None
        self._codec : any = None
        self._sample_rate : int = None
        self._bit_depth : int = None
        self._audio_quality : TidalQuality = None
        self._audio_mode : str = None

    @property
    def url(self) -> str:
        return self._url

    @url.setter
    def url(self, value : str):
        self._url : str = value

    @property
    def mimetype(self) -> str:
        return self._mimetype

    @mimetype.setter
    def mimetype(self, value : str):
        self._mimetype : str = value

    @property
    def codecs(self) -> any:
        return self._codec

    @codecs.setter
    def codecs(self, value : any):
        self._codec = value

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @sample_rate.setter
    def sample_rate(self, value : int):
        self._sample_rate = value

    @property
    def bit_depth(self) -> int:
        return self._bit_depth

    @bit_depth.setter
    def bit_depth(self, value : int):
        self._bit_depth = value

    @property
    def audio_quality(self) -> TidalQuality:
        return self._audio_quality

    @audio_quality.setter
    def audio_quality(self, value : TidalQuality):
        self._audio_quality = value

    @property
    def audio_mode(self) -> str:
        return self._audio_mode

    @audio_mode.setter
    def audio_mode(self, value : str):
        self._audio_mode = value
