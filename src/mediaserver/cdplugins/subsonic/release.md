# Subsonic Plugin Release Notes

## Release 0.7.6

- Add artist metadata using upnp:artist
- Artist is appended using a dash as the separator, instead of putting it inside square brackets
- Try to use upnp:genre for album genres
- Remove upmpd:albumgenres in favor of standard and already available upnp:genre
- Add new table kv_cache_v1 for simple key-value caches

## Release 0.7.5

- Add support for album version
- Avoid to add disc/tracks in album containers by default
- Populate fields in upmpd vendor tags:
  - albumtitle
  - albumartist
  - albumyear
  - albumoriginalreleasedate
  - albumduration
  - albumiscompilation
  - albumreleasetypes
  - albumversion
  - albumgenres
  - albumrecordlabels
  - albumexplicitstatus
  - albumquality
  - albumdisctrackcounters
  - albummusicbrainzid
  - albumid

## Release 0.7.4

- Remove unnecessary check for null album on handler_element_album

## Release 0.7.3

- Review image caching, get mimetype and extension from server in order to store and serve the file properly

## Release 0.7.2

- Advance subsonic-connector to 0.3.9, fixed url encoding (covers now show in Moode Audio)
- Add All Artists (unsorted), marked others as Slow
- Disable request cache for Favorite Albums
- Reload and save coverArt for tracks when opening and album
- Introduced image caching, requires webdocument root, disabled by default
- Reduce paging for additional artists to 10
- Fixed bug that would cause to not show explicit status when dump explicit status is disabled
- Handle album that do not return an artistId, but return a list of "artists"
- Create artist entries using Artist object when possible
- Initial use of coverArt from Artist data structure
- Add logging for initialization process
- Treat codecs (suffixex) case-insensitively
- General code cleanup and optimizations

## Release 0.7.1

- Use new method available in upcoming upmpdcli 1.9.2 for retrieving the plugin path
- Changes to adapt to upcoming upmpdcli 1.9.2 (webserver document root)
- Added quality badge to album (also search results)
- Initial support for additional metadata
- General code cleanup and optimizations

## Release 0.7.0

- Albums by release type include only albums for the selected artist_id (others go to Appearances)
- Only dump explicit status if configured to do so
- Default to not show artist id even for album container

## Release 0.6.9

- Reduced request cache timeout default to 30 seconds
- Honor config.disable_navigable_album everytime we would want to create a navigable album entry
- Added two more items to album subdivision folder name prefixes
- Release number and plugin name to a new enum class in constants
- Add song selection entry for additional artist in album
- Add new method for reading config param as int from enum
- Improved configuration support
- Granular configurability for showing album mb id in album entries
- Granular configurability for showing year in album entries
- Configurability for dumping genres for album
- Granular configurability for showing album id in album entries
- Granular configurability for showing artist in album entries
- Granular configurability for showing quality badge in album entries
- Improved quality badge detection
- Allow configuration for showing disc/track count in album as search results
- More concise naming
- Better configurability of entry title for album view and album container
- Better parameter naming (maybe remove this entry when releasing)
- Optionally allow search album results to be presented as containers
- Respect show only placeholder config parameter for additional artists in album
- Readable sampling rate for lossy quality badges
- Add album count for artist with albums of a single release type
- Add album count for artist with same name
- Reviewed albums from Genre creating navigable entries
- Add cover art to next button for genre albums
- Search results show album mbid considering "show only placeholder" parameter
- Add support for showing genres in album lists
- Add optional support for showing genres in album view
- Add counters to "All Releases" and to "Appearances" album lists
- Use subsequent artist for selecting an album art for the "Next" button
- Show WARN when an album without genre is met
- Add m4a and mp3 as lossy format suffix
- General code cleanup and optimizations

## Release 0.6.8

- Introduced TODO.md file to keep track of new things to do
- Add counters to albums by release type entries
- Add support for Appearances
- Fix date support, fallback to year when original release date is missing
- Sort artist albums by date
- Show album mbid in search results
- Add album in lists after the title instead of before it
- Show artist id and mbid in additional artists view
- Show number of discs in album lists
- Show number of tracks in album lists

## Release 0.6.7

- Add support for Explicit status (ITUNESADVISORY tag for Lightweight Music Server)
- Support partial original release date
- Let user configure parameter to allow Artist in entry title for album lists
- Allow [mb] placeholder instead of full mbid
- Add additional artists entry when there are too many additional artists (limit configurable)
- Simply add artist name along with id where artists with same name as one with mbid exist
- Improved linting

## Release 0.6.6

- Some more constants are now enumerated
- Try to select albums as main artist for "Albums by release type" view if possible
- Log genres from album
- More appropriate caching for album by artist id
- Try to select albums as main artist for artist entry if possible
- Add metadata for album view in upplay
- Avoid to raise unnecessary exception for missing tracks
- Separate parameters for search limits
- Avoid to display a lot of additional artists (slow loading)
- Handle missing album more gracefully
- In artist view, show artists with same name (case-insensitively) if artist has MusicBrainz id
- In artist view, show "All Releases" only when there are more than one release types
- Configurability for mb album id caching (dumpactiononmbalbumcache)
- Case insensitive album release types
- Removed some code duplication
- Avoid some string duplication
- Handle deletion event of previously cached album_id by artist_id
- Release types default to just "album" if empty/missing

## Release 0.6.5

- Updates for lms changes about coverArt
- Some constants are now enumerated
- Support for splitting releases by type
- Improve album art for songs, prefer album

## Release 0.6.4

- Simplified class RetrievedArt
- Cache artist mb id
- Improve selection of artist art using albums
- reduce dependency on RetrievedArt
- Tag art retriever dict made private
- Initial work for album classification
- Caching for album mb id so it's more available
- Remove all remaining dependencies from old caching
- Allow to dump paths for album, useful for tagging purposes
- Advance subsonic-connector to 0.3.5
- Add optional album mbid in album view
- Initial MusicBrainz support
- Add optional artist mbid in artist entries
- Configurability for showing artist/album id around
- Add artist id in artist entries and additional artists
- Some randomization for tiles images from favorites
- Get rid of views for Album Artists (required caching)
- Artists by Genre use existing entry creator
- Get rid of precaching
- Presentation of artists by genre is much faster now
- Use random album cover for "Genres" tile
- Additional artists (work in progress)
- Improved linting

## Release 0.6.3

- Don't present Artist again from items in Artist Albums view
- Don't force expensive album/track loading for artist albums view
- Reduce default logging
- Use subsequent album as album art for "Next" in some album lists
- Bug: Changed album badge would not be saved to db

## Release 0.6.2

- Implemented Newest Albums using byYear type
- Renamed old "Newest Albums" to "Recently Added Albums"
- TagType naming review (not a feature)

## Release 0.6.1

- Fixed missing art for Favorite Albums

## Release 0.6.0

- Introduced persistency (local sqlite3 database)
- Quality badges are now persisted
- Introduced request caching for enhanced speed
- Artist views reviewed and enriched
- View "Artists (All)" removed, could lead to timeouts
- Artist views are now always paginated
- Artist views are split in "All Artists" and "Album Artists"
- Avoid to display an empty "Favorites" entry by default
- Avoid to display an empty "Playlists" entry by default
- General code cleanup and optimizations
- Collecting release notes (this file)

## Release 0.5.0

- Add quality badge on Album view (currently only supported by lightweight music server)
- Quality badge is available in Album lists when already calculated
- Cleanup of code for the trackuri method

## Release 0.4.0

- Support for bitDepth and samplingRate
- Add quality badges (server must support bitDepth and samplingRate)
- Improved performance

## Release 0.3.6

- Advance subsonic-connector to 0.3.2

## Release 0.3.5

- Changes for Kodi support (optional item numbering)

## Release 0.3.4

- Add support for originalReleaseDate
- Artists are paginated
- Add Album list from Artist

## Release 0.3.3

- Reduced logging in trackuri, could lead to failing gapless

## Release 0.3.2

- Add artist in album lists
- Progressive track numbers in Radio and Top Tracks (list mode)
- Speed up Radio entry creation (was awfully slow)
- Corrected parameter type to subsoniclegacyauth
- Handle misconfigured legacyauth
- Support for server-side scrobbling

## Release 0.3.1

- disabled nocache again as it caused issues with lms

## Release 0.3.0

- Don't present Radios if not implemented by server
- Don't present Highest Rated if not implemented by server
- Handle when getTopSongs is not implemented by server
- Recreating mime_type from suffix when needed
- Support for transcoding
- Logging for intermediate url
- Compatibility for missing artistId from album

## Release 0.2.7

- handle empty playlist
- Gonic compatibility: getSimilarSongs
- Fix playlist could not be opened

## Release 0.2.6

- Back to using intermediate url (scrobbler now supports it)
