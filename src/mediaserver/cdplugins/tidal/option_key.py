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

from enum import Enum


class _OptionKeyData:

    def __init__(self, name: str, default_value: any = None):
        self.__name: str = name
        self.__default_value: any = default_value

    @property
    def name(self) -> str:
        return self.__name

    @property
    def default_value(self) -> any:
        return self.__default_value


class OptionKey(Enum):
    SKIP_TRACK_NUMBER = _OptionKeyData("skip-track-number", False)
    FORCED_TRACK_NUMBER = _OptionKeyData("forced-track-number", None)
    SKIP_TRACK_ARTIST = _OptionKeyData("skip-track-artist", False)
    OVERRIDDEN_ART_URI = _OptionKeyData("overriden-art-uri", None)
    OVERRIDDEN_TRACK_NAME = _OptionKeyData("overridden-track-name", None)
    ENTRY_AS_CONTAINER = _OptionKeyData("entry-as-container", False)
    ADD_EXPLICIT = _OptionKeyData("add-explicit", True)
    ADD_ALBUM_YEAR = _OptionKeyData("add-album-year", True)
    SKIP_ART = _OptionKeyData("skip-art", False)
    ADD_ARTIST_TO_ALBUM_ENTRY = _OptionKeyData("add-artist-to-album-entry", False)
    # integer to prepend e.g. pass 3 -> [03] album_title instead of album_title
    PREPEND_ENTRY_NUMBER_IN_ENTRY_NAME = _OptionKeyData("prepend-entry-number-in-entry-name", None)
    OMIT_ARTIST_TO_ALBUM_ENTRY_UNLESS_DIFFERENT = _OptionKeyData("omit-rsts-nls-dffrnt", False)
    ALBUM_OMITTABLE_ARTIST_ID = _OptionKeyData("lbm-omit-rtst", None)
    TRACK_OMITTABLE_ARTIST_NAME = _OptionKeyData("trk-omit-rtst", None)
    INITIAL_TRACK_NUMBER = _OptionKeyData("ntl-trkn", 1)
    TRACK_AS_NAVIGABLE = _OptionKeyData("nvgbl-trk", False)
    TRACK_CONTAINER_SET_CLASS = _OptionKeyData("trkc-sclzz", False)

    @property
    def name(self) -> str:
        return self.value.name

    @property
    def default_value(self) -> any:
        return self.value.default_value
