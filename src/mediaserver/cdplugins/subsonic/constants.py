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

from enum import Enum


class PluginConstant(Enum):

    PLUGIN_RELEASE = "0.8.0"
    PLUGIN_NAME = "subsonic"


class ItemKey(Enum):

    BIT_DEPTH = "bitDepth"
    SAMPLING_RATE = "samplingRate"
    CHANNEL_COUNT = "channelCount"
    MUSICBRAINZ_ID = "musicBrainzId"
    MEDIA_TYPE = "mediaType"
    RELEASE_TYPES = "releaseTypes"
    ALBUM_ARTISTS = "albumArtists"
    ARTISTS = "artists"
    ORIGINAL_RELEASE_DATE = "originalReleaseDate"
    EXPLICIT_STATUS = "explicitStatus"
    DISC_TITLES = "discTitles"
    DISC_TITLES_DISC = "disc"
    DISC_TITLES_TITLE = "title"
    COVER_ART = "coverArt"
    VERSION = "version"
    ALBUM_RECORD_LABELS = "recordLabels"
    IS_COMPILATION = "isCompilation"


class AlbumEntryType(Enum):
    ALBUM_VIEW = 1,
    ALBUM_CONTAINER = 2


class Defaults(Enum):

    SUBSONIC_API_MAX_RETURN_SIZE = 500  # API Hard Limit
    CACHED_REQUEST_TIMEOUT_SEC = 30
    FALLBACK_TRANSCODE_CODEC = "ogg"


# we should remove the Defaults enumerated and converge to this new enumerated
class _ConfigParamData:

    def __init__(self, key: str, default_value: any):
        self.__key: str = key
        self.__default_value: any = default_value

    @property
    def key(self) -> str:
        return self.__key

    @property
    def default_value(self) -> any:
        return self.__default_value


class ConfigParam(Enum):

    ALLOW_GENRE_IN_ALBUM_VIEW = _ConfigParamData("allowgenreinalbumview", False)
    ALLOW_GENRE_IN_ALBUM_CONTAINER = _ConfigParamData("allowgenreinalbumcontainer", False)

    SHOW_EMPTY_FAVORITES = _ConfigParamData("showemptyfavorites", False)
    SHOW_EMPTY_PLAYLISTS = _ConfigParamData("showemptyplaylists", False)

    SEARCH_RESULT_ALBUM_AS_CONTAINER = _ConfigParamData("searchresultalbumascontainer", False)

    ALLOW_APPEND_DISC_CNT_IN_ALBUM_CONTAINER = _ConfigParamData("allowappenddisccountinalbumcontainer", False)
    ALLOW_APPEND_DISC_CNT_IN_ALBUM_VIEW = _ConfigParamData("allowappenddisccountinalbumview", False)
    ALLOW_APPEND_DISC_CNT_IN_ALBUM_SEARCH_RESULT = _ConfigParamData("allowappenddisccountinalbumsearchresult", False)

    ALLOW_APPEND_TRACK_CNT_IN_ALBUM_CONTAINER = _ConfigParamData("allowappendtrackcountinalbumcontainer", False)
    ALLOW_APPEND_TRACK_CNT_IN_ALBUM_VIEW = _ConfigParamData("allowappendtrackcountinalbumview", False)
    ALLOW_APPEND_TRACK_CNT_IN_ALBUM_SEARCH_RESULT = _ConfigParamData("allowappendtrackcountinalbumsearchresult", False)

    ALLOW_APPEND_ARTIST_IN_ALBUM_CONTAINER = _ConfigParamData("allowprependartistinalbumcontainer", True)
    ALLOW_APPEND_ARTIST_IN_ALBUM_VIEW = _ConfigParamData("allowappendartistinalbumview", True)
    ALLOW_APPEND_ARTIST_IN_SEARCH_RES = _ConfigParamData("allowappendartistinsearchresult", False)

    ARTIST_ALBUM_NEWEST_FIRST = _ConfigParamData("artistalbumnewestfirst", True)

    ALLOW_QUALITY_BADGE_IN_ALBUM_CONTAINER = _ConfigParamData("allowqbadgeinalbumcontainer", True)
    ALLOW_QUALITY_BADGE_IN_ALBUM_VIEW = _ConfigParamData("allowqbadgeinalbumview", True)
    ALLOW_QUALITY_BADGE_IN_ALBUM_SEARCH_RES = _ConfigParamData("allowqbadgeinalbumsearchresult", True)

    ALLOW_ALBUM_VERSION_IN_ALBUM_CONTAINER = _ConfigParamData("allowversioninalbumcontainer", True)
    ALLOW_ALBUM_VERSION_IN_ALBUM_VIEW = _ConfigParamData("allowversioninalbumview", True)
    ALLOW_ALBUM_VERSION_IN_ALBUM_SEARCH_RES = _ConfigParamData("allowversioninalbumsearchresult", True)

    APPEND_ALBUM_ID_IN_ALBUM_CONTAINER = _ConfigParamData("showalbumidinalbumcontainer", False)
    APPEND_ALBUM_ID_IN_ALBUM_VIEW = _ConfigParamData("showalbumidinalbumview", False)
    APPEND_ALBUM_ID_IN_ALBUM_SEARCH_RES = _ConfigParamData("showalbumidinalbumsearchresult", False)

    SHOW_ALBUM_MB_ID_AS_PLACEHOLDER = _ConfigParamData("showalbummbidasplaceholder", True)
    SHOW_ARTIST_MB_ID_AS_PLACEHOLDER = _ConfigParamData("showartistmbidasplaceholder", True)

    DUMP_ACTION_ON_MB_ALBUM_CACHE = _ConfigParamData("dumpactiononmbalbumcache", False)
    DUMP_ALBUM_GENRE = _ConfigParamData("dumpalbumgenre", False)
    APPEND_YEAR_TO_ALBUM_CONTAINER = _ConfigParamData("appendyeartoalbumcontainer", True)
    APPEND_YEAR_TO_ALBUM_VIEW = _ConfigParamData("appendyeartoalbumview", False)
    APPEND_YEAR_TO_ALBUM_SEARCH_RES = _ConfigParamData("appendyeartoalbumsearchresult", False)
    SET_CLASS_TO_ALBUM_FOR_NAVIGABLE_ALBUM = _ConfigParamData("setclasstoalbumfornavigablealbum", False)
    DUMP_ALBUM_SORTABLE_DATE = _ConfigParamData("dumpalbumsortabledate", False)
    SHOW_ALBUM_MBID_IN_ALBUM_CONTAINER = _ConfigParamData("showalbummbidinalbumcontainer", False)
    SHOW_ALBUM_MBID_IN_ALBUM_VIEW = _ConfigParamData("showalbummbidinalbumview", False)
    SHOW_ALBUM_MBID_IN_ALBUM_SEARCH_RES = _ConfigParamData("showalbummbidinalbumsearchres", False)
    SHOW_PATHS_IN_ALBUM = _ConfigParamData("showpathsinalbum", False)
    SHOW_ARTIST_MB_ID = _ConfigParamData("showartistmbid", False)
    SHOW_ARTIST_ID = _ConfigParamData("showartistid", False)
    ALBUM_SEARCH_LIMIT = _ConfigParamData("albumsearchlimit", 50)
    ARTIST_SEARCH_LIMIT = _ConfigParamData("artistsearchlimit", 50)
    SONG_SEARCH_LIMIT = _ConfigParamData("albumsearchlimit", 100)
    ITEMS_PER_PAGE = _ConfigParamData("itemsperpage", 20)
    ADDITIONAL_ARTISTS_MAX = _ConfigParamData("maxadditionalartists", 10)
    MAX_ARTISTS_PER_PAGE = _ConfigParamData("maxartistsperpage", 20)
    MAX_ADDITIONAL_ALBUM_ARTISTS_PER_PAGE = _ConfigParamData("maxadditionalalbumartistsperpage", 10)
    DUMP_STREAMING_PROPERTIES = _ConfigParamData("dumpstreamingproperties", 0)
    APPEND_CODEC_TO_ALBUM = _ConfigParamData("appendcodecstoalbum", True)
    TRANSCODE_CODEC = _ConfigParamData("transcodecodec", "")
    DISABLE_NAVIGABLE_ALBUM = _ConfigParamData("disablenavigablealbum", False)
    DUMP_EXPLICIT_STATUS = _ConfigParamData("dumpexplicitstatus", False)
    ENABLE_IMAGE_CACHING = _ConfigParamData("enableimagecaching", False)
    SHOW_META_ALBUM_PATH = _ConfigParamData("showmetaalbumpath", False)

    ENABLE_CACHED_IMAGE_AGE_LIMIT = _ConfigParamData("enabledumpstreamdata", True)
    CACHED_IMAGES_MAX_AGE_DAYS = _ConfigParamData("cachedimagesmaxagedays", 180)

    SKIP_USER_AGENT = _ConfigParamData("skipuseragent", 0)
    USER_AGENT = _ConfigParamData("useragent", "upmpdcli")

    @property
    def key(self) -> str:
        return self.value.key

    @property
    def default_value(self) -> any:
        return self.value.default_value


class _ExplicitStatusData:

    def __init__(self, tag_value: str, display_value: str, display_value_long: str):
        self.__tag_value: str = tag_value
        self.__display_value: str = display_value
        self.__display_value_long: str = display_value_long

    @property
    def tag_value(self) -> str:
        return self.__tag_value

    @property
    def display_value(self) -> str:
        return self.__display_value

    @property
    def display_value_long(self) -> str:
        return self.__display_value_long


class ExplicitDiplayMode:

    SHORT = 1
    LONG = 2


class ExplicitStatus(Enum):

    EXPLICIT = _ExplicitStatusData("explicit", "E", "Explicit")
    CLEAN = _ExplicitStatusData("clean", "C", "Clean")


class UpnpMeta(Enum):
    GENRE = "genre"
    ARTIST = "artist"


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
    ALBUM_PATH = "albumpath"


class MetadataMaxLength(Enum):
    ALBUM_PATH = 128


default_debug_badge_mngmt: int = 0
default_debug_artist_albums: int = 0
