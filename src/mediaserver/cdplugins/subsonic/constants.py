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


class PluginConstant(Enum):

    PLUGIN_RELEASE = "0.9.2"
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
    COVER_ART = "coverArt"
    ALBUM_VERSION = "version"
    ALBUM_RECORD_LABELS = "recordLabels"
    IS_COMPILATION = "isCompilation"
    ROLES = "roles"
    MOODS = "moods"
    SONG_ALBUM_ARTISTS = "albumArtists"
    SONG_ARTISTS = "artists"
    ALBUM_PLAYED = "played"
    ALBUM_DISPLAY_ARTIST = "displayArtist"
    SONG_DISPLAY_ARTIST = "displayArtist"
    SONG_DISPLAY_ALBUM_ARTIST = "displayAlbumArtist"
    PLAYLIST_ENTRY_DISPLAY_ARTIST = "displayArtist"
    ITEM_SIZE = "size"
    ARTIST_SORT_NAME = "sortName"
    ALBUM_SONG_COUNT = "songCount"
    ALBUM_CREATED = "created"
    ALBUM_USER_RATING = "userRating"
    ALBUM_IS_COMPILATION = "isCompilation"
    ALBUM_PLAY_COUNT = "playCount"
    ALBUM_SORT_NAME = "sortName"
    ALBUM_GENRES = "genres"
    SONG_COMMENT = "comment"
    SONG_CREATED = "created"
    SONG_IS_DIR = "isDir"
    SONG_PLAY_COUNT = "playCount"
    SONG_PLAYED = "played"
    SONG_YEAR = "year"
    SONG_TYPE = "type"
    SONG_DISPLAY_COMPOSER = "displayComposer"
    SONG_SORT_NAME = "sortName"


class DictKey(Enum):

    ID = "id"
    NAME = "name"
    ROLE = "role"
    SUB_ROLE = "subRole"
    ARTIST = "artist"
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    DISC = "disc"
    TITLE = "title"


class AlbumEntryType(Enum):
    ALBUM_VIEW = 1,
    ALBUM_CONTAINER = 2


class Defaults(Enum):

    SUBSONIC_API_MAX_RETURN_SIZE = 500  # API Hard Limit
    CACHED_REQUEST_TIMEOUT_SEC = 30
    FALLBACK_TRANSCODE_CODEC = "ogg"


# we should remove the Defaults enumerated and converge to this new enumerated
class _ConfigParamData:

    def __init__(self, key: str, default_value: any, description: str):
        self.__key: str = key
        self.__default_value: any = default_value
        self.__description: str = description

    @property
    def key(self) -> str:
        return self.__key

    @property
    def default_value(self) -> any:
        return self.__default_value

    @property
    def description(self) -> str:
        return self.__description


class ConfigParam(Enum):

    ALLOW_GENRE_IN_ALBUM_CONTAINER = _ConfigParamData(
        "allowgenreinalbumcontainer",
        default_value=False,
        description="Show genre in album container")
    ALLOW_GENRE_IN_ALBUM_VIEW = _ConfigParamData(
        "allowgenreinalbumview",
        default_value=False,
        description="Show genre in album view")

    SHOW_EMPTY_FAVORITES = _ConfigParamData(
        "showemptyfavorites",
        default_value=False,
        description="Show the Favorites entry, even when there are none")
    SHOW_EMPTY_PLAYLISTS = _ConfigParamData(
        "showemptyplaylists",
        default_value=False,
        description="Show the Playlists entry, even when there are none")

    SEARCH_RESULT_ALBUM_AS_CONTAINER = _ConfigParamData(
        "searchresultalbumascontainer",
        default_value=False,
        description="Show search results for albums as containers (breaks some control points, but not upplay)")

    ALLOW_APPEND_ARTIST_IN_ALBUM_CONTAINER = _ConfigParamData(
        "allowappendartistinalbumcontainer",
        default_value=True,
        description="Append artist to album container")
    ALLOW_APPEND_ARTIST_IN_ALBUM_VIEW = _ConfigParamData(
        "allowappendartistinalbumview",
        default_value=False,
        description="Append artist to album view")
    ALLOW_APPEND_ARTIST_IN_SEARCH_RES = _ConfigParamData(
        "allowappendartistinsearchresult",
        default_value=False,
        description="Append artist to album search result")

    ARTIST_ALBUM_NEWEST_FIRST = _ConfigParamData(
        "artistalbumnewestfirst",
        default_value=True,
        description="Show albums from the artist from newest to oldest (True) or the opposite (False)")

    ALLOW_QUALITY_BADGE_IN_ALBUM_CONTAINER = _ConfigParamData(
        "allowqbadgeinalbumcontainer",
        default_value=True,
        description="Append quality badge to album container")
    ALLOW_QUALITY_BADGE_IN_ALBUM_VIEW = _ConfigParamData(
        "allowqbadgeinalbumview",
        default_value=False,
        description="Append quality badge to album view")
    ALLOW_QUALITY_BADGE_IN_ALBUM_SEARCH_RES = _ConfigParamData(
        "allowqbadgeinalbumsearchresult",
        default_value=False,
        description="Append quality badge to album search result")

    ALLOW_ALBUM_VERSION_IN_ALBUM_CONTAINER = _ConfigParamData(
        "allowversioninalbumcontainer",
        default_value=True,
        description="Append version to album container")
    ALLOW_ALBUM_VERSION_IN_ALBUM_VIEW = _ConfigParamData(
        "allowversioninalbumview",
        default_value=True,
        description="Append version to album view")
    ALLOW_ALBUM_VERSION_IN_ALBUM_SEARCH_RES = _ConfigParamData(
        "allowversioninalbumsearchresult",
        default_value=True,
        description="Append version to album search result")

    APPEND_ALBUM_ID_IN_ALBUM_CONTAINER = _ConfigParamData(
        "showalbumidinalbumcontainer",
        default_value=False,
        description="Show album id in album container")
    APPEND_ALBUM_ID_IN_ALBUM_VIEW = _ConfigParamData(
        "showalbumidinalbumview",
        default_value=False,
        description="Show album id in album search result")
    APPEND_ALBUM_ID_IN_ALBUM_SEARCH_RES = _ConfigParamData(
        "showalbumidinalbumsearchresult",
        default_value=False,
        description="Show album id in album search result")

    APPEND_YEAR_TO_ALBUM_CONTAINER = _ConfigParamData(
        "appendyeartoalbumcontainer",
        default_value=True,
        description="Show year in album container")
    APPEND_YEAR_TO_ALBUM_VIEW = _ConfigParamData(
        "appendyeartoalbumview",
        default_value=False,
        description="Show year in album view")
    APPEND_YEAR_TO_ALBUM_SEARCH_RES = _ConfigParamData(
        "appendyeartoalbumsearchresult",
        default_value=False,
        description="Show year in album search result")

    PREPEND_NUMBER_IN_ALBUM_LIST = _ConfigParamData(
        "prependnumberinalbumlist",
        default_value=False,
        description="Add number in album lists, mostly to defeat client sorting")

    SHOW_ALBUM_MBID_IN_ALBUM_CONTAINER = _ConfigParamData(
        "showalbummbidinalbumcontainer",
        default_value=False,
        description="Show album musicbrainz id in album container")
    SHOW_ALBUM_MBID_IN_ALBUM_VIEW = _ConfigParamData(
        "showalbummbidinalbumview",
        default_value=False,
        description="Show album musicbrainz id in album view")
    SHOW_ALBUM_MBID_IN_ALBUM_SEARCH_RES = _ConfigParamData(
        "showalbummbidinalbumsearchres",
        default_value=False,
        description="Show album musicbrainz id in album search result")
    # only determines if mb id is shown or we just show "mb" in order to say that there is an album mb id
    SHOW_ALBUM_MB_ID_AS_PLACEHOLDER = _ConfigParamData(
        "showalbummbidasplaceholder",
        default_value=True,
        description="Show `mbid` as a placeholder for musicbrainz id, effective only if showing mb id for album is enabled")

    SHOW_ARTIST_MB_ID = _ConfigParamData(
        "showartistmbid",
        default_value=False,
        description="Show `mbid` as a placeholder for musicbrainz id, effective only if showing mb id for artist is enabled")
    # only determines if mb id is shown or we just show "mb" in order to say that there is an artist mb id
    SHOW_ARTIST_MB_ID_AS_PLACEHOLDER = _ConfigParamData(
        "showartistmbidasplaceholder",
        default_value=True,
        description="Show `mbid` as a placeholder for musicbrainz id, effective only if showing mb id for artist is enabled")

    WHITELIST_CODECS = _ConfigParamData(
        "whitelistcodecs",
        default_value="alac,wav,flac,dsf",
        description=("List of codecs in a whitelist "
                     "because they are considered lossless, comma separated"))

    ALLOW_BLACKLIST_CODEC_IN_SONG = _ConfigParamData(
        "allowblacklistedcodecinsong",
        default_value=True,
        description="Show codecs that do not belong to whitelist in song lists")

    SERVER_SIDE_SCROBBLING = _ConfigParamData(
        "serversidescrobbling",
        default_value=False,
        description="Scrobble to the subsonic server when trackuri is invoked")

    DUMP_ACTION_ON_MB_ALBUM_CACHE = _ConfigParamData(
        "dumpactiononmbalbumcache",
        default_value=False,
        description="Show actions on album cache in logs")
    DUMP_ALBUM_GENRE = _ConfigParamData(
        "dumpalbumgenre",
        default_value=False,
        description="Show album genre in logs")

    SET_CLASS_TO_ALBUM_FOR_NAVIGABLE_ALBUM = _ConfigParamData(
        "setclasstoalbumfornavigablealbum",
        default_value=False,
        description="Force the navigable album to have the album class")
    DUMP_ALBUM_SORTABLE_DATE = _ConfigParamData(
        "dumpalbumsortabledate",
        default_value=False,
        description="Show what is used for sorting by date in logs")
    SHOW_PATHS_IN_ALBUM = _ConfigParamData(
        "showpathsinalbum",
        default_value=False,
        description="Show album path in logs")
    SHOW_ARTIST_ID = _ConfigParamData(
        "showartistid",
        default_value=False,
        description="Show artist id in artist")

    ARTIST_SEARCH_LIMIT = _ConfigParamData(
        "artistsearchlimit",
        default_value=50,
        description="Max artists to show when searching")
    ALBUM_SEARCH_LIMIT = _ConfigParamData(
        "albumsearchlimit",
        default_value=50,
        description="Max albums to show when searching")
    SONG_SEARCH_LIMIT = _ConfigParamData(
        "songsearchlimit",
        default_value=100,
        description="Max songs to show when searching")

    ITEMS_PER_PAGE = _ConfigParamData(
        "itemsperpage",
        default_value=20,
        description="Items per page")
    MAX_ADDITIONAL_ARTISTS = _ConfigParamData(
        "maxadditionalartists",
        default_value=25,
        description="Max additional artists shown without creating a dedicated entry")
    MAX_ARTISTS_PER_PAGE = _ConfigParamData(
        "maxartistsperpage",
        default_value=20,
        description="Artists per page")
    MAX_ADDITIONAL_ALBUM_ARTISTS_PER_PAGE = _ConfigParamData(
        "maxadditionalalbumartistsperpage",
        default_value=10,
        description="Max number of additional artists per page")
    DUMP_STREAMING_PROPERTIES = _ConfigParamData(
        "dumpstreamingproperties",
        default_value=False,
        description="Dump streaming properties to log")
    APPEND_CODEC_TO_ALBUM = _ConfigParamData(
        "appendcodecstoalbum",
        default_value=True,
        description="Show codec in album")
    APPEND_ROLES_TO_ARTIST = _ConfigParamData(
        "appendrolestoartist",
        default_value=False,
        description="Append roles to artist")
    TRANSCODE_CODEC = _ConfigParamData(
        "transcodecodec",
        default_value="",
        description="Transcode codec to use")
    TRANSCODE_MAX_BITRATE = _ConfigParamData(
        "transcodemaxbitrate",
        default_value="",
        description="Max bitrate to be used when transcoding")
    DISABLE_NAVIGABLE_ALBUM = _ConfigParamData(
        "disablenavigablealbum",
        default_value=False,
        description="Disable navigability for albums")
    DUMP_EXPLICIT_STATUS = _ConfigParamData(
        "dumpexplicitstatus",
        default_value=False,
        description="Dump explicit status to logs")
    ENABLE_IMAGE_CACHING = _ConfigParamData(
        "enableimagecaching",
        default_value=False,
        description="Enables the server to cache images locally")
    SHOW_META_ALBUM_PATH = _ConfigParamData(
        "showmetaalbumpath",
        default_value=False,
        description="Add album paths to upmpd metadata")

    ENABLE_CACHED_IMAGE_AGE_LIMIT = _ConfigParamData(
        "enablecachedimageagelimit",
        default_value=False,
        description="Enables check on age for cached images")
    CACHED_IMAGE_MAX_AGE_DAYS = _ConfigParamData(
        "cachedimagemaxagedays",
        default_value=60,
        description="If cache files are older than the specified max age, they are deleted on startup")

    SKIP_USER_AGENT = _ConfigParamData(
        "skipuseragent",
        default_value=False,
        description="Skip specification of a custom user agent")
    USER_AGENT = _ConfigParamData(
        "useragent",
        default_value="upmpdcli",
        description="User agent for api calls")

    MAX_TRACKS_FOR_NO_DISC_SPLIT = _ConfigParamData(
        "maxtracksfornodiscsplit",
        default_value=60,
        description=("Maximum number of tracks, under this value the album will not "
                     "be split to discs unless there are disc subtitles"))

    VERBOSE_LOGGING = _ConfigParamData(
        "verboselogging",
        default_value=False,
        description="General verbose logging")

    CACHED_ARTIST_LIST_CACHE_TIMEOUT_SEC = _ConfigParamData(
        "cachedartistlistcachetimeoutsec",
        default_value=300,
        description="Timeout for cached artist list")
    SEARCH_SIZE_ALBUM_LIBRARY_MAINTENANCE = _ConfigParamData(
        "searchsizealbumlibrarymaintenance",
        default_value=1000,
        description="Maximum number of albums to search in maintenance features")
    ENABLE_MAINTENANCE_FEATURES = _ConfigParamData(
        "enablemaintenancefeatures",
        default_value=False,
        description="Enable maintenance features")
    MAINTENANCE_MAX_ALBUM_LOAD_SIZE = _ConfigParamData(
        "maintenancemaxalbumloadsize",
        default_value=3000,
        description="Max number of albums to load for a single page in order to avoid timeouts")

    GENRE_VIEW_SEARCH_ALBUMS_FOR_COVER_ART = _ConfigParamData(
        "genreviewsearchalbumsforcoverart",
        default_value=False,
        description="Search albums for cover art for genres view (it might be slow)")
    ALLOW_ARTIST_COVER_ART = _ConfigParamData(
        "allowartistcoverart",
        default_value=True,
        description=("Allow to use coverArt from subsonic api for artist art. "
                     "Usually it's safe to enable. Can be slow on navidrome when spotify "
                     "is integrated because of throttling"))
    ALLOW_FAVORITES_FOR_FRONT_PAGE_TAGS = _ConfigParamData(
        "allowfavoritesforfrontpagetags",
        default_value=False,
        description="Allow to use favorites when searching images to apply to the initial view entries")
    ALLOW_SHUFFLE_RANDOM_ALBUM_FOR_FRONT_PAGE_TAGS = _ConfigParamData(
        "allowshufflerandomalbumsforfrontpagetags",
        default_value=True,
        description="Allow to shuffle random albums when selecting image for initial view entries")

    DEFEAT_COVER_ART_URL = _ConfigParamData(
        "defeatcoverarturl",
        default_value=False,
        description="Allows to entirely defeat loading of cover art")
    LOG_WITH_TIMESTAMP = _ConfigParamData(
        "logwithtimestamp",
        default_value=True,
        description="Adds a timestamp to log entries")

    # 250 seems a good compromise, still quite fast
    # 500 is still the absolute max
    MAX_RANDOM_SONG_LIST_SIZE = _ConfigParamData(
        "maxrandomsonglistsize",
        default_value=250,
        description="Max number of random songs to display")

    SET_ALBUM_ARTIST_ROLE_ALBUMARTIST = _ConfigParamData(
        "setalbumartistrolealbumartist",
        default_value=False,
        description="Enable set the role 'albumartist' in album")

    ALLOW_SONG_DIDL_ALBUMARTIST = _ConfigParamData(
        "allowsongdidlalbumartist",
        default_value=False,
        description="Allow to add DIDL fragment for album artist in song")

    LOG_INTERMEDIATE_URL = _ConfigParamData(
        key="logintermediateurl",
        default_value=False,
        description="Display the intermediate track urls")

    ENABLE_TRACK_INTERMEDIATE_URL = _ConfigParamData(
        key="enabletrackintermediateurl",
        default_value=True,
        description="Create intermediate track URLs that will be processed by the trackuri method")

    ENABLE_COVER_ART_INTERMEDIATE_URL = _ConfigParamData(
        key="enablecoverartintermediateurl",
        default_value=True,
        description="Create intermediate cover art URLs that will be processed by the trackuri method")

    ENABLE_RANDOM_ID = _ConfigParamData(
        key="enablerandomid",
        default_value=False,
        description=("Generate a random id on each identifier entry, "
                     "might be useful with Linn Kazoo as this will "
                     "defeat its excessive caching"))

    PRELOAD_MAX_DELTA_SEC = _ConfigParamData(
        key="preloadmaxdeltasec",
        default_value=3600,
        description=("Preload data only if oldest update is before current time minus this delta"))

    PRELOAD_VERBOSE_LOGGING = _ConfigParamData(
        key="preloadverboselogging",
        default_value=False,
        description=("Verbose logging while preloading"))

    PRELOAD_ARTISTS = _ConfigParamData(
        key="preloadartists",
        default_value=True,
        description=("Preload artists at plugin startup time"))

    PRELOAD_ALBUMS = _ConfigParamData(
        key="preloadalbums",
        default_value=True,
        description=("Preload albums at plugin startup time, requires preloadartists"))

    PRELOAD_SONGS = _ConfigParamData(
        key="preloadsongs",
        default_value=True,
        description=("Preload songs at plugin startup time, requires preloadalbums"))

    BROWSE_WITHOUT_CACHE = _ConfigParamData(
        key="browsewithoutcache",
        default_value=False,
        description=("Set value of no_cache when browsing the library"))

    SEARCH_WITHOUT_CACHE = _ConfigParamData(
        key="searchwithoutcache",
        default_value=True,
        description=("Set value of no_cache when browsing search results"))

    TRACE_PERSISTENCE_OPERATIONS = _ConfigParamData(
        key="tracepersistenceoperations",
        default_value=False,
        description=("Trace persistence operations"))

    MINIMIZE_IDENTIFIER_LENGTH = _ConfigParamData(
        key="minimizeidentifierlength",
        default_value=True,
        description=("Set value to true/1 in order to minimize the length of identifiers, "
                     "this might solve issues with some Denon AVR, "
                     "but will create lots of database entries. "
                     "If disabled, the identifier strings might be a lot longer but "
                     "no dedicated entries will be created on the database"))

    PURGE_IDENTIFIER_CACHE = _ConfigParamData(
        key="purgeidentifiercache",
        default_value=True,
        description=("Purge the identifier cache records created by id caching"))

    EXECUTE_VACUUM = _ConfigParamData(
        key="executevacuum",
        default_value=True,
        description=("Execute VACUUM on startup (reduce db size)"))

    CACHED_REQUEST_TIMEOUT_SEC = _ConfigParamData(
        key="cachedrequesttimeoutsec",
        default_value=Defaults.CACHED_REQUEST_TIMEOUT_SEC.value,
        description=("Timeout for cached requests in seconds"))

    @property
    def key(self) -> str:
        return self.value.key

    @property
    def default_value(self) -> any:
        return self.value.default_value

    @property
    def description(self) -> str:
        return self.value.description


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


class MaxLength(Enum):
    ALBUM_PATH = 65535
