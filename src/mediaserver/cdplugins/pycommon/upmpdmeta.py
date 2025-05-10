#################################
# Copyright (C) 2025 Giovanni Fulco
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the
#   Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
########################################################
# Command communication module and utilities. See commands in cmdtalk.h
#
# All data is binary. This is important for Python3
# All parameter names are converted to and processed as str/unicode

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
    ALBUM_ORIGINAL_RELEASE_DATE = "albumoriginalreleasedate"
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
