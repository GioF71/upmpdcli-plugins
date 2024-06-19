# Subsonic Plugin Release notes

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
