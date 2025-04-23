# Tidal Plugin Release notes

## 0.8.6

- Cached images are not pruned by default
- Safety checks before executing image pruning
- Misc code corrections, cleanup and refactoring
- Hi-Res matching process improved

## 0.8.5

- Log whether user agent whitelist is enabled or not
- Remove global tidal session
- Avoid to downgrade quality information to db just because we played to a non-whitelisted player in standard resolution
- Report missing user-agent (no match is executed in this case, and we fallback to lower quality if agent whitelist is enabled)
- Misc code corrections, cleanup and refactoring

## 0.8.4

- Don't assume that images are jpg files, use mimetypes instead
- Select newest file when there are more than one cached file for the same item (might happen if file type changes)
- Avoid to accumulate cached images indefinitely: by default, on startup, files older than 60 days are removed
- Avoid use of "/".join(...) using os.path.join(...)

## 0.8.3

- Improve badge assignment
- Reduce unnecessary logging
- Use of enums instead of constants in variables
- Whitelisted new WiiM firmware `Lavf/58.76.100` and up (so now WiiM devices should be hi-res capable)
- Misc code corrections, cleanup and refactoring

## 0.8.2

- Tidal Plugin: HiRes lossless whitelisted for mpd and gmrender-resurrect
- Tidal Plugin: use user-agent to lower quality when player cannot do hires lossless
- Tidal Plugin: make use of user-agent, thanks to [this commit](https://framagit.org/medoc92/upmpdcli/-/commit/2c742f13eb81c4fd1bf3270fa24877e04aadbaed) by J.F. Dockes

## 0.8.1

- Changes to adapt to upcoming upmpdcli 1.9.3 (webserver document root)
- Fix tidal plugin executable files using #!/usr/bin/env python3

## 0.8.0

- Cleanup config parameters enum in constants
- Do not add action buttons by default (bookmark, favorite, statistics)
- Handle invalid type from manifest.get_url, unlikely to happen anyway
- Add metadata for new upplay album view also from search album
- Add Local Genres page
- Featured page is now Home
- Hi-Res as TidalPageDefinition
- For You as TidalPageDefinition
- Moods as TidalPageDefinition
- Genres as TidalPageDefinition
- Removed page "Home", because it was the same as "Featured"
- Add enumerated for Tidal Page definitions
- Add metadata for new upplay album view
- Set correct object class for album entry
- Bump to [tidalapi version 0.8.3](https://github.com/tamland/python-tidal/releases/tag/v0.8.3)
- Add "Tidal Rising" to Page Selection
- Add "All Tracks" in Playlist and Mix view for easy playback/queueing
- Corrected support for hls mode
- Misc code corrections, cleanup and refactoring

## 0.7.11

- Bump to [tidalapi version 0.8.2](https://github.com/tamland/python-tidal/releases/tag/v0.8.2)
- Handle missing track in trackuri

## 0.7.10

- Restore "Add to Bookmark" functionality for Albums
- Improve reliability of image caching
- Misc code corrections, cleanup and refactoring

## 0.7.9 (2024-11-13)

- Bump to [tidalapi version 0.8.1](https://github.com/tamland/python-tidal/releases/tag/v0.8.1)
- Remove old get_credentials_pkce.py
- Misc code corrections, cleanup and refactoring

## 0.7.8 (2024-11-05)

- Pagination on PageLinks
- Better handling of missing Tracks
- Better handling of missing Albums
- Present playlist items (tracks) in track container
- Better handling of PageLinks in Categories
- Add image caching for Playlists and Mixes
- Fix call to track_to_track_container with wrong named argument
- When a missing album is encountered, we now remove it from playback statistics and metadata cache if the entry is clicked
- Misc code corrections, cleanup and refactoring

## 0.7.7 (2024-11-01)

- Track from a track container would not work
- Some track lists were not presented as not navigable

## 0.7.6 (2024-10-29)

- Corrected support for tidalimagecaching
- Corrected support for boolean configuration values
- Better logging
- Some improvements in linting (long way to go!)

## 0.7.5 (2024-10-22)

- Allow to remove from Favorites an album that does not exist anymore
- Allow to remove from Bookmarks an album that does not exist anymore
- Present MISSING_ALBUM entry when album does not exist anymore
- Removed references to MQA and Sony 360
- Bump to [tidalapi version 0.8.0](https://github.com/tamland/python-tidal/releases/tag/v0.8.0)
- Handle albums that don't exist anymore (e.g. from Favorites) more gracefully
- Fixed obscure bug preventing to display an album list
- Oauth2 authentication method now supports HI_RES_LOSSLESS
- Add "explore_new_music" page (shown as "New Music")
- Improved compatibility with renderers when using lossless quality or lower

## 0.7.4 (2024-08-06)

- Created tag for Page Selection for faster loading
- Restrict pages to inspect just to select a tile image
- Configuration for tile image expiration time
- Add Tile: Featured

## 0.7.3 (2024-08-01)

- Add Tile: Genres
- Add Tile: For You
- Paging in Page view
- Improved management of page items
- Add Tile: Home
- Add Tile: Moods
- Add Tile: HiRes
- Tracks from a Category are now navigable
- Add support for overriding the country code
- Misc code corrections, cleanup and refactoring

## 0.7.2 (2024-07-22)

- Some view (mostly from statistics) were still using deprecated image_url from db
- Non-stereo Albums from playback statistics are not skipped
- Add artists from individual tracks in Album view
- Fixed silly bug which would prevent to show additional album artists in most cases
- Misc code corrections, cleanup and refactoring

## 0.7.1 (2024-07-12)

- Fixed album image caching for Recently Played Albums

## 0.7.0 (2024-07-04)

- Cover image for Next button in Bookmarks
- Cover image for Next button in Navigable Artist Radio
- Cover image for Next button in List of Artist Radio
- Cover image for Next button in List of Artist Top Tracks
- Cover image for Next button in Navigable Artist Top Tracks
- Cover image for Next button in List of Favorite Tracks
- Cover image for Next button in Navigable Favorite Tracks
- Cover image for Next button in Similar Artists
- Cover image for Next button in Albums from Playlist
- Cover image for Next button in Artists from Playlist
- Cover image for Next button in Favorite Artists (all flavors)
- Bug: only first page of all playlists was correctly presented
- Cover image for Next button in Navigable Tracks from a Mix
- Cover image for Next button in Artist Albums (all types)
- Cover image for Next button in Favorite Albums (all flavors)
- Cover image for Next button in List of Recently Played Tracks
- Cover image for Next button in List of Most Played Tracks
- Cover image for Next button in Navigable Recently Played Tracks
- Cover image for Next button in Navigable Most Played Tracks
- Most Played Albums uses metadata cache (faster)
- Cover image for Next button in Most Played Albums
- Better management of non stereo albums
- Recently Played Albums uses metadata cache (faster)
- Misc code cleanup and refactoring
- Cover image for Next button in Recently Played Albums
- Moved some methods related to credential files to tidal_util
- Removed unnecessay check of static pkce credentials with credential file  

## 0.6.0 (2024-06-13)

- Use album art caching more extensively
- Limit search limit to 15 items by default, configurable (tidalsearchlimit)
- Favorite Tracks (List) is paginated
- Recently/Most Played Tracks (List) are paginated
- Most Played Tracks is paginated
- Similar Artists is paginated
- Artist Radio (List) is paginated
- Artist Radio (Navigable) is paginated
- Artist Top tracks (list mode) is paginated
- Avoid unknown file type as seen in Linn Kazoo

## 0.5.1 (2024-06-01)

- timestamp was not saved in metadata cache table
- collecting release notes (this file)

## 0.5.0 (2024-05-23)

- New Feature: Bookmarks (renamed from Listen Queue)
- Quality badges introduced
- Updated get_credentials.py program
- Fixed bug in single track view
- Various fixes and performance optimizations
- Introduced optional image caching, for Artists and Albums (tidalenableimagecaching)

## 0.4.1 (Hotfix) (2024-05-17)

- fixed scope of variable in get_category_image_url
- On top of the hotfix, a small change which can handle artist as the items in a Category

## 0.4.0 (2024-05-04)

- Paginated artists/albums from mix/playlist
- Replaced deprecated calls
- Access playlist items in while cycle
- Albums and Artists list from playist/mixes are now complete
- Avoid to extract tracks which have not been played
- Avoid entries without images
- Implemented Album Listen Queue on local db
- Add tracks entry from Album view
- Enable add/remove tracks to/from favorites
- Corrected remove from stats, just reset counters

## 0.3.0 (2024-04-22)

- support PKCE authentication
- major review of the plugin

## 0.2.1.1 (Hotfix) (2024-02-12)

- Failing to drop table result in a warning instead of an error
- There are no consequences as the column is nullable
- We will not reuse the same field names

## 0.2.1 (2024-01-23)

- some calls were not receiving the session argument

## 0.2.0 (2024-01-02)

- Implement login mechanims similar to what's implemented in the qobuz plugin

## 0.0.13 (2023-12-30)

- Numbering for albums lists (kodi compatibility)

## 0.0.12 (2023-10-28)

- mixes: entries for limited tracks (for speed)

## 0.0.11 (2023-10-27)

- Add sorting for favorite albums
- Refresh_token and expiry_time not strictly required
- Playlists: entries for limited tracks (for speed)

## 0.0.10 (2023-10-14)

- Album view pagination by 25 items
- Navigable playlist paginated down to 25 items (100 could be too slow)
- Caching expiration time up to 1 day

## 0.0.9 (2023-10-12)

- Paging for Artist top tracks
- Method tidal_search uses arguments
- Recently played albums and tracks limit up to 100
- Allow removal of Album from Statistics
- Allow removal of Track from Statistics

## 0.0.8 (2023-10-10)

- Authentication challenge
- Displayed last unnamed category as "Other"
- More graceful handling of dead links
- Safer (atomic) playcount update
- Removed unnecessarily alarming logs
- Removed harmless reference to subsonic

## 0.0.7 (2023-09-29)

- Improved statistics
- Improved search compatibility
- Support Favorites add/remove for Album and Artist
- Tiles are now displayed for decades
- Tile Images for artist Albums
- Tile Images for Similar Artists
- Tile Images for Artist Radio
- Tile Images for Top Tracks
- Handle PageLink failures (see [notes](#007-additional-notes))
- Set upnp class for album (but not for album container)

### 0.0.7 Additional Notes

Some links sometime refer to non-existing resources. These missing 'things' can happen on Tidal itself, but now this will not prevent an entire view from loading.

## 0.0.6 (2023-09-23)

- Safer query for most played
- Better PageLink handling
- Tile images for all genres
- Handle missing tracks in playlist
- Handle missing image in playlist

## 0.0.5 (2023-09-20)

This has been the first release note, so it briefly reports a summary of the features of the plugin.

### Features

- All tidal categories are available under the tile "Categories".
- Tiles on the first level have an image when possibile. Of course playlist, mixes, albums, artists and tracks have always had their tile image
- Views for favourite Artists, Albums and Tracks are available
- Views for Playlist and User Playlist are available
- Playback statistics are available, relying on data collected by the plugin itself locally
- The "Playback statistics" will show recent/most played albums/tracks, collected considering the playback history from the server itself.
- Scrobbling (sort of...)
- We currently don't have a way to "tell" Tidal we played a track (a.k.a. scrobbling) so we can only rely on locally collected data.
- A track is considered "played" when the server provides the stream url to the player. This can happen even before the player actually starts playing the song if this in a playback queue. For a renderer based on mpd/upmpdcli (renderer mode) the track is url is requested ~20 sec before the previous tracks should end.

### Scrobbling limitations

Also, we cannot require something like 50% playback time or minimum playback time before considering a track as "played" because the server has no control on the actual player. So these statistic are a mere approximation of the reality. I believe it is better than nothing, but I am open to hear comments, suggestions and critics.
