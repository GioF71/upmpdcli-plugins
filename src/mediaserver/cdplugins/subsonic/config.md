# Configuration Parameters

## Read this first

The following is a non-exaustive list of the configuration options for the subsonic plugin. All the variable names must be prepended with `subsonic` when you add them to your upmpdcli.conf file.  
For boolean values (distinguishable because the default is True or False), you will have to use 1 or 0.

## List of variables

VARIABLE|DESCRIPTION
:---|:---
allowgenreinalbumview|Show genre in album view, defaults to False
allowgenreinalbumcontainer|Show genre in album container, defaults to False
showemptyfavorites|Show the Favorites entry, even when there are none, defaults to False
showemptyplaylists|Show the Playlists entry, even when there are none, defaults to False
searchresultalbumascontainer|Show search results for albums as containers, defaults to False (breaks some control points, but not upplay)
allowappenddisccountinalbumcontainer|Append disc count to album container, defaults to False
allowappenddisccountinalbumview|Append disc count to album view, defaults to False
allowappenddisccountinalbumsearchresult|Append disc count to album search result, defaults to False
allowappendtrackcountinalbumcontainer|Append track number to album container, defaults to False
allowappendtrackcountinalbumview|Append track number to album view, defaults to False
allowappendtrackcountinalbumsearchresult|Append track number to album search result, defaults to False
allowappendartistinalbumcontainer|Append artist to album container, defaults to False
allowappendartistinalbumview|Append artist to album view, defaults to False
allowappendartistinsearchresult|Append artist to album search result, defaults to False
artistalbumnewestfirst|Show albums from the artist from newest to oldest (True) or the opposite (False), defaults to True
allowqbadgeinalbumcontainer|Append quality badge to album container, defaults to True
allowqbadgeinalbumview|Append quality badge to album view, defaults to True
allowqbadgeinalbumsearchresult|Append quality badge to album search result, defaults to True
allowversioninalbumcontainer|Append version to album container, defaults to True
allowversioninalbumview|Append version to album view, defaults to True
allowversioninalbumsearchresult|Append version to album search result, defaults to True
showalbumidinalbumcontainer|Show album id in album container, defaults to False
showalbumidinalbumview|Show album id in album view, defaults to False
showalbumidinalbumsearchresult|Show album id in album search result, defaults to False
showalbummbidasplaceholder|Show `mbid` as a placeholder for musicbrainz id, effective only if showing mb id for album is enabled, defaults to True
showartistmbidasplaceholder|Show `mbid` as a placeholder for musicbrainz id, effective only if showing mb id for artist is enabled, defaults to True
dumpactiononmbalbumcache|Show actions on album cache in logs, defaults to False
dumpalbumgenre|Show album genre in logs, defaults to False
appendyeartoalbumcontainer|Show year in album container, defaults to True
appendyeartoalbumview|Show year in album view, defaults to True
appendyeartoalbumsearchresult|Show year in album search result, defaults to True
setclasstoalbumfornavigablealbum|Force the navigable album to have the album class, defaults to False
dumpalbumsortabledate|Show what is used for sorting by date in logs, defaults to False
showalbummbidinalbumcontainer|Show album musicbrainz id in album container, defaults to False
showalbummbidinalbumview|Show album musicbrainz id in album view, defaults to False
showalbummbidinalbumsearchres|Show album musicbrainz id in album search result, defaults to False
showpathsinalbum|Show album path in logs, defaults to False
showartistmbid|Show musicbrainz id in artist, defaults to False
showartistid|Show artist id in artist, defaults to False
albumsearchlimit|Max albums to show when searching
artistsearchlimit|Max artists to show when searching
songsearchlimit|Max songs to show when searching
itemsperpage|Items per page, defaults to 20
maxadditionalartists|Max additional artists shown without creating a dedicated entry, defaults to 10
maxartistsperpage|Artists per page, defaults to 20
maxadditionalalbumartistsperpage|Max number of additional artists per page, defaults to 10
dumpstreamingproperties|Dump streaming properties to log, defaults to False
APPEND_CODEC_TO_ALBUM|Show codec inb album, defaults to True
appendrolestoartist|Append roles to artist, defaults to True
transcodecodec|Transcode codec to use, defaults to none (empty)
disablenavigablealbum|Disable navigability for albums, defaults to False
dumpexplicitstatus|Dump explicit status to logs, defaults to False
enableimagecaching|Enables the serve to cache images locally
showmetaalbumpath|Add album paths to upmpd metadata, defaults to False
enablecachedimageagelimit|Enables check on age for cached images, defaults to False
cachedimagemaxagedays|If cache files are older than the specified max age, they are deleted on startup
skipuseragent|Avoid to specify a user agent, defaults to False
useragent|User agent for api calls, defaults to `upmpdcli`
maxtracksfornodiscsplit|Maximum number of tracks, under this value the album will not be splitted in discs unless there are disc subtitles, defaults to 60
verboselogging|General verbose logging, defaults to False
cachedartistlistcachetimeoutsec|Timeout fo cached artist list, defaults to 300
searchsizealbumlibrarymaintenance|Maximum number of albums to search in maintenance features, defaults to 1000
enablemaintenancefeatures|Enable maintenance features, defaults to False
maintenancemaxalbumloadsize|Max number of albums to load for a single page in order to avoid timeouts, defaults to 3000
genreviewsearchalbumsforcoverart|Search albums for cover art for genres view, defaults to False (it might be slow)
allowartistcoverart|Allow to use coverArt from subsonic api for artist art. Usually it's safe to enable. Can be slow on navidrome when spotify is integrated because of them applying some throttling.
allowfavoritesforfrontpagetags|Allow to use favorites when searching images to apply to the initial view entries
allowshufflerandomalbumsforfrontpagetags|Allow to shuffle random albums when selecting image for initial view entries
