# Copyright (C) 2025 Giovanni Fulco
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


class UpMpdMeta(Enum):
    ALBUM_QUALITY = "albumquality"
    ALBUM_VERSION = "albumversion"
    ALBUM_EXPLICIT_STATUS = "albumexplicitstatus"
    ALBUM_ID = "albumid"
    ALBUM_MUSICBRAINZ_ID = "albummusicbrainzid"
    ALBUM_RECORD_LABELS = "albumrecordlabels"
    ALBUM_DURATION = "albumduration"
    ALBUM_DISC_AND_TRACK_COUNTERS = "albumdisctrackcounters"
    ALBUM_ARTIST = "albumartist"
    # ALBUM_ARTISTS = "albumartists"
    ALBUM_TITLE = "albumtitle"
    ALBUM_YEAR = "albumyear"
    ALBUM_MEDIA_TYPE = "albummediatype"
    MOOD = "mood"
    ALBUM_ORIGINAL_RELEASE_DATE = "albumoriginalreleasedate"
    ALBUM_AVAILABLE_RELEASE_DATE = "albumavailablereleasedate"
    IS_COMPILATION = "albumiscompilation"
    RELEASE_TYPES = "albumreleasetypes"
    ARTIST_ID = "artistid"
    ARTIST_MUSICBRAINZ_ID = "artistmusicbrainzid"
    ARTIST_ALBUM_COUNT = "artistalbumcount"
    ARTIST_MEDIA_TYPE = "artistmediatype"
    ARTIST_ROLE = "artistrole"
    ALBUM_PATH = "albumpath"
    TRACK_DURATION = "trackduration"
    TRACK_NUMBER = "tracknumber"
    DISC_NUMBER = "discnumber"
    COPYRIGHT = "copyright"
    UNIVERSAL_PRODUCT_NUMBER = "universalproductnumber"


def get_duration_display_from_sec(duration_sec: int) -> str:
    if duration_sec < 0:
        # duration is invalid
        return "<invalid duration>"
    # hours, minutes, seconds
    remaining_sec: int = duration_sec
    seconds: int = duration_sec % 60
    remaining_sec -= seconds
    minutes: int = int(int(remaining_sec / 60) % 60)
    remaining_sec -= (minutes * 60)
    hours: int = int(remaining_sec / 3600)
    result: str = ""
    # format it!
    if hours > 0:
        result += f"{hours}h"
    if minutes > 0:
        if len(result) > 0:
            result += " "
        result += f"{minutes:02d}m"
    # add seconds in any case
    if len(result) > 0:
        result += " "
    result += f"{seconds:02d}s"
    return result
