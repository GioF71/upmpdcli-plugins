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

    PLUGIN_RELEASE = "0.8.22"
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
    CONTRIBUTORS = "contributors"
    ORIGINAL_RELEASE_DATE = "originalReleaseDate"
    RELEASE_DATE = "releaseDate"
    EXPLICIT_STATUS = "explicitStatus"
    DISC_TITLES = "discTitles"
    DISC_TITLES_DISC = "disc"
    DISC_TITLES_TITLE = "title"
    COVER_ART = "coverArt"
    VERSION = "version"
    ALBUM_RECORD_LABELS = "recordLabels"
    IS_COMPILATION = "isCompilation"
    ROLES = "roles"
    MOODS = "moods"
    SONG_ALBUM_ARTISTS = "albumartists"
    SONG_ARTISTS = "artists"
    LAST_PLAYED = "played"
    ALBUM_DISPLAY_ARTIST = "displayArtist"
    SONG_DISPLAY_ARTIST = "displayArtist"
    SONG_DISPLAY_ALBUM_ARTIST = "displayAlbumArtist"
    PLAYLIST_ENTRY_DISPLAY_ARTIST = "displayArtist"


class DictKey(Enum):

    ID = "id"
    NAME = "name"
    ROLE = "role"
    ARTIST = "artist"


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

    ALLOW_APPEND_ARTIST_IN_ALBUM_CONTAINER = _ConfigParamData("allowappendartistinalbumcontainer", True)
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
    SONG_SEARCH_LIMIT = _ConfigParamData("songsearchlimit", 100)
    ITEMS_PER_PAGE = _ConfigParamData("itemsperpage", 20)
    ADDITIONAL_ARTISTS_MAX = _ConfigParamData("maxadditionalartists", 10)
    MAX_ARTISTS_PER_PAGE = _ConfigParamData("maxartistsperpage", 20)
    MAX_ADDITIONAL_ALBUM_ARTISTS_PER_PAGE = _ConfigParamData("maxadditionalalbumartistsperpage", 10)
    DUMP_STREAMING_PROPERTIES = _ConfigParamData("dumpstreamingproperties", False)
    APPEND_CODEC_TO_ALBUM = _ConfigParamData("appendcodecstoalbum", True)
    APPEND_ROLES_TO_ARTIST = _ConfigParamData("appendrolestoartist", True)
    TRANSCODE_CODEC = _ConfigParamData("transcodecodec", "")
    TRANSCODE_MAX_BITRATE = _ConfigParamData("transcodemaxbitrate", "")
    DISABLE_NAVIGABLE_ALBUM = _ConfigParamData("disablenavigablealbum", False)
    DUMP_EXPLICIT_STATUS = _ConfigParamData("dumpexplicitstatus", False)
    ENABLE_IMAGE_CACHING = _ConfigParamData("enableimagecaching", False)
    SHOW_META_ALBUM_PATH = _ConfigParamData("showmetaalbumpath", False)

    ENABLE_CACHED_IMAGE_AGE_LIMIT = _ConfigParamData("enablecachedimageagelimit", False)
    CACHED_IMAGE_MAX_AGE_DAYS = _ConfigParamData("cachedimagemaxagedays", 60)

    SKIP_USER_AGENT = _ConfigParamData("skipuseragent", False)
    USER_AGENT = _ConfigParamData("useragent", "upmpdcli")

    MAX_TRACKS_FOR_NO_DISC_SPLIT = _ConfigParamData("maxtracksfornodiscsplit", 60)

    VERBOSE_LOGGING = _ConfigParamData("verboselogging", False)

    CACHED_ARTIST_LIST_CACHE_TIMEOUT_SEC = _ConfigParamData("cachedartistlistcachetimeoutsec", 300)
    SEARCH_SIZE_ALBUM_LIBRARY_MAINTENANCE = _ConfigParamData("searchsizealbumlibrarymaintenance", 1000)
    ENABLE_MAINTENANCE_FEATURES = _ConfigParamData("enablemaintenancefeatures", False)
    MAINTENANCE_MAX_ALBUM_LOAD_SIZE = _ConfigParamData("maintenancemaxalbumloadsize", 3000)

    GENRE_VIEW_SEARCH_ALBUMS_FOR_COVER_ART = _ConfigParamData("genreviewsearchalbumsforcoverart", False)
    ALLOW_ARTIST_COVER_ART = _ConfigParamData("allowartistcoverart", True)

    ALLOW_FAVORITES_FOR_FRONT_PAGE_TAGS = _ConfigParamData("allowfavoritesforfrontpagetags", False)
    ALLOW_SHUFFLE_RANDOM_ALBUM_FOR_FRONT_PAGE_TAGS = _ConfigParamData("allowshufflerandomalbumsforfrontpagetags", True)

    DEFEAT_COVER_ART_URL = _ConfigParamData("defeatcoverarturl", False)
    LOG_WITH_TIMESTAMP = _ConfigParamData("logwithtimestamp", True)

    # 250 seems a good compromise, still quite fast
    # 500 is still the absolute max
    MAX_RANDOM_SONG_LIST_SIZE = _ConfigParamData("maxrandomsonglistsize", 250)

    @property
    def key(self) -> str:
        return self.value.key

    @property
    def default_value(self) -> any:
        return self.value.default_value


class _TranscodingInfoData:

    def __init__(self, codec: str, default_bitrate: int, default_bitdepth: int = None):
        self.__codec: str = codec
        self.__default_bitrate: int = default_bitrate
        self.__default_bitdepth: int = default_bitdepth

    @property
    def codec(self) -> str:
        return self.__codec

    @property
    def default_bitrate(self) -> int:
        return self.__default_bitrate

    @property
    def default_bitdepth(self) -> int:
        return self.__default_bitdepth


class TranscodingInfo(Enum):

    OPUS = _TranscodingInfoData(codec="opus", default_bitrate=512, default_bitdepth=0)
    OGG = _TranscodingInfoData(codec="ogg", default_bitrate=500, default_bitdepth=0)
    MP3 = _TranscodingInfoData(codec="mp3", default_bitrate=320, default_bitdepth=0)
    FLAC = _TranscodingInfoData(codec="flac", default_bitrate=None, default_bitdepth=16)

    @property
    def codec(self) -> str:
        return self.value.codec

    @property
    def default_bitrate(self) -> int:
        return self.value.default_bitrate

    @property
    def default_bitdepth(self) -> int:
        return self.value.default_bitdepth


def get_transcoding_information_by_coded(codec: str) -> TranscodingInfo | None:
    current: TranscodingInfo
    for current in TranscodingInfo:
        if current.codec.lower() == codec.lower():
            # found!
            return current
    return None


def get_default_bitrate_by_codec(codec: str) -> int | None:
    info: TranscodingInfo = get_transcoding_information_by_coded(codec=codec)
    return info.default_bitrate if info else None


def get_default_bitdepth_by_codec(codec: str) -> int | None:
    info: TranscodingInfo = get_transcoding_information_by_coded(codec=codec)
    return info.default_bitdepth if info else None


class ThingName(Enum):
    ALBUM = "album"
    ARTIST = "artist"
    ALBUM_ARTIST = "albumartist"
    PERFORMER = "performer"
    CONDUCTOR = "conductor"
    COMPOSER = "composer"


class RoleName(Enum):
    ALBUM_ARTIST = ThingName.ALBUM_ARTIST.value
    ARTIST = ThingName.ARTIST.value
    PERFORMER = ThingName.PERFORMER.value
    CONDUCTOR = ThingName.CONDUCTOR.value
    COMPOSER = ThingName.COMPOSER.value


class MediaType(Enum):
    ARTIST = ThingName.ARTIST.value
    ALBUM = ThingName.ALBUM.value


class NameTranslatorData:

    def __init__(self, name_key: str, display_name: str):
        self.__name_key: str = name_key
        self.__display_name: str = display_name

    @property
    def name_key(self) -> str:
        return self.__name_key

    @property
    def display_name(self) -> str:
        return self.__display_name


class NameTranslator(Enum):

    ARTIST = NameTranslatorData(ThingName.ARTIST.value, "Artist")
    ALBUM_ARTIST = NameTranslatorData(ThingName.ALBUM_ARTIST.value, "Album Artist")
    PERFORMER = NameTranslatorData(ThingName.PERFORMER.value, "Performer")
    CONDUCTOR = NameTranslatorData(ThingName.CONDUCTOR.value, "Conductor")
    COMPOSER = NameTranslatorData(ThingName.COMPOSER.value, "Composer")

    @property
    def name_key(self) -> str:
        return self.value.name_key

    @property
    def display_name(self) -> str:
        return self.value.display_name


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


class MetadataMaxLength(Enum):

    ALBUM_PATH = 128


class Separator(Enum):

    DISC_NUMBER_SEPARATOR = ","
    GENRE_FOR_ARTIST_SEPARATOR = ","


class _SupportedImageTypeData:

    def __init__(self, extension_list: list[str], content_type_list: list[str]):
        self.__extension_list: list[str] = extension_list
        self.__content_type_list: list[str] = content_type_list

    @property
    def extension_list(self) -> list[str]:
        return self.__extension_list

    @property
    def content_type_list(self) -> list[str]:
        return self.__content_type_list


class SupportedImageType(Enum):

    JPG = _SupportedImageTypeData(extension_list=["jpg", "jpeg", "jpe"], content_type_list=["image/jpeg"])
    PNG = _SupportedImageTypeData(extension_list=["png"], content_type_list=["image/png"])

    @property
    def extension_list(self) -> list[str]:
        return self.value.extension_list

    @property
    def content_type_list(self) -> list[str]:
        return self.value.content_type_list


default_debug_badge_mngmt: int = 0
default_debug_artist_albums: int = 0
