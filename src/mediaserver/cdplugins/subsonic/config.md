# Configuration Parameters

## Read this first

The following is a non-exaustive list of the configuration options for the subsonic plugin.  
All the variable names must be prepended with `subsonic` when you add them to your upmpdcli.conf file.  
For boolean values (distinguishable because the default is True or False), you will have to use 1 or 0.

## List of variables

VARIABLE|DESCRIPTION|DEFAULT_VALUE
:---|:---|:---
allowgenreinalbumcontainer|Show genre in album container|False
allowgenreinalbumview|Show genre in album view|False
showemptyfavorites|Show the Favorites entry, even when there are none|False
showemptyplaylists|Show the Playlists entry, even when there are none|False
searchresultalbumascontainer|Show search results for albums as containers (breaks some control points, but not upplay)|False
allowappenddisccountinalbumcontainer|Append disc count to album container|False
allowappenddisccountinalbumview|Append disc count to album view|False
allowappenddisccountinalbumsearchresult|Append disc count to album search result|False
allowappendtrackcountinalbumcontainer|Append track number to album container|False
allowappendtrackcountinalbumview|Append track number to album view|False
allowappendtrackcountinalbumsearchresult|Append track number to album search result|False
allowappendartistinalbumcontainer|Append artist to album container|True
allowappendartistinalbumview|Append artist to album view|False
allowappendartistinsearchresult|Append artist to album search result|False
artistalbumnewestfirst|Show albums from the artist from newest to oldest (True) or the opposite (False)|True
allowqbadgeinalbumcontainer|Append quality badge to album container|True
allowqbadgeinalbumview|Append quality badge to album view|False
allowqbadgeinalbumsearchresult|Append quality badge to album search result|False
allowversioninalbumcontainer|Append version to album container|True
allowversioninalbumview|Append version to album view|True
allowversioninalbumsearchresult|Append version to album search result|True
showalbumidinalbumcontainer|Show album id in album container|False
showalbumidinalbumview|Show album id in album search result|False
showalbumidinalbumsearchresult|Show album id in album search result|False
appendyeartoalbumcontainer|Show year in album container|True
appendyeartoalbumview|Show year in album view|False
appendyeartoalbumsearchresult|Show year in album search result|False
showalbummbidinalbumcontainer|Show album musicbrainz id in album container|False
showalbummbidinalbumview|Show album musicbrainz id in album view|False
showalbummbidinalbumsearchres|Show album musicbrainz id in album search result|False
showalbummbidasplaceholder|Show `mbid` as a placeholder for musicbrainz id, effective only if showing mb id for album is enabled|True
showartistmbid|Show `mbid` as a placeholder for musicbrainz id, effective only if showing mb id for artist is enabled|False
showartistmbidasplaceholder|Show `mbid` as a placeholder for musicbrainz id, effective only if showing mb id for artist is enabled|True
dumpactiononmbalbumcache|Show actions on album cache in logs|False
dumpalbumgenre|Show album genre in logs|False
setclasstoalbumfornavigablealbum|Force the navigable album to have the album class|False
dumpalbumsortabledate|Show what is used for sorting by date in logs|False
showpathsinalbum|Show album path in logs|False
showartistid|Show artist id in artist|False
artistsearchlimit|Max artists to show when searching|50
albumsearchlimit|Max albums to show when searching|50
songsearchlimit|Max songs to show when searching|100
itemsperpage|Items per page|20
maxadditionalartists|Max additional artists shown without creating a dedicated entry|10
maxartistsperpage|Artists per page|20
maxadditionalalbumartistsperpage|Max number of additional artists per page|10
dumpstreamingproperties|Dump streaming properties to log|False
appendcodecstoalbum|Show codec in album|True
appendrolestoartist|Append roles to artist|False
transcodecodec|Transcode codec to use|
transcodemaxbitrate|Max bitrate to be used when transcoding|
disablenavigablealbum|Disable navigability for albums|False
dumpexplicitstatus|Dump explicit status to logs|False
enableimagecaching|Enables the server to cache images locally|False
showmetaalbumpath|Add album paths to upmpd metadata|False
enablecachedimageagelimit|Enables check on age for cached images|False
cachedimagemaxagedays|If cache files are older than the specified max age, they are deleted on startup|60
skipuseragent|Skip specification of a custom user agent|False
useragent|User agent for api calls|upmpdcli
maxtracksfornodiscsplit|Maximum number of tracks, under this value the album will not be split to discs unless there are disc subtitles|60
verboselogging|General verbose logging|False
cachedartistlistcachetimeoutsec|Timeout for cached artist list|300
searchsizealbumlibrarymaintenance|Maximum number of albums to search in maintenance features|1000
enablemaintenancefeatures|Enable maintenance features|False
maintenancemaxalbumloadsize|Max number of albums to load for a single page in order to avoid timeouts|3000
genreviewsearchalbumsforcoverart|Search albums for cover art for genres view (it might be slow)|False
allowartistcoverart|Allow to use coverArt from subsonic api for artist art. Usually it's safe to enable. Can be slow on navidrome when spotify is integrated because of throttling|True
allowfavoritesforfrontpagetags|Allow to use favorites when searching images to apply to the initial view entries|False
allowshufflerandomalbumsforfrontpagetags|Allow to shuffle random albums when selecting image for initial view entries|True
defeatcoverarturl|Allows to entirely defeat loading of cover art|False
logwithtimestamp|Adds a timestamp to log entries|True
maxrandomsonglistsize|Max number of random songs to display|250
setalbumartistrolealbumartist|Enable set the role 'albumartist' in album|False
allowsongdidlalbumartist|Allow to add DIDL fragment for album artist in song|False
skipintermediateurl|Avoid to create URLs that will be redirected to the trackuri method|False
skiprandomid|Generate a random id on each identifier entry, might be useful with Linn Kazoo|True
