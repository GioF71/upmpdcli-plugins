# Tidal Plugin Release notes

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
- Introduced optional image caching, for Artists and Albums (tidalimagecaching)

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

Also, we cannot require something like 50% playback time or minimum playback time before considering a track as "played" because the server has no control on the actual player. So these statistic are a mere approximation of the reality. I believe it is better than nothing, but I am will to hear comments, suggestions and critics.
