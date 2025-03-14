#!/usr/bin/env python3
#
# A lot of code copied from the Kodi Tidal addon which is:
# Copyright (C) 2014 Thomas Amland
#
# Additional code and modifications:
# Copyright (C) 2016 J.F.Dockes
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

from __future__ import print_function
import sys
import os
import json
import re
import cmdtalkplugin
from upmplgutils import *
from xbmcplug import *

# Using kodi routing module
from routing import Plugin

plugin = Plugin("")

from session import Session

qobidprefix = "0$qobuz$"

# We maybe should retrieve this from the "index" call (cf notes/qobuz/featured/index/json)
_playlist_tags = (
    ("hi-res", "Hi-Res"),
    ("new", "New"),
    ("focus", "Themes"),
    ("danslecasque", "Artist's choices"),
    ("label", "Labels"),
    ("mood", "Moods"),
    ("artist", "Artists"),
    ("events", "Events"),
    ("auditoriums", "Hi-Fi Audio Partners"),
    ("popular", "Popular"),
)

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()
# Pipe message handler
msgproc = cmdtalkplugin.Processor(dispatcher)

# Initial formatid (mp3). Will be reset on login. This is because we may need a session when
# get_appid is called (when the plugin is used with the credentials service). It seems that a local
# session inside getappid would suffice, TBD check).
session = Session(5)

_g_loginok = False


def maybelogin(a={}):
    global session
    global formatid
    global httphp
    global pathprefix
    global _g_loginok
    global renum_tracks
    global explicit_item_numbers
    global prepend_artist_to_album

    # Do this always
    setidprefix(qobidprefix)

    if _g_loginok:
        return True

    if "UPMPD_HTTPHOSTPORT" not in os.environ:
        raise Exception("No UPMPD_HTTPHOSTPORT in environment")
    httphp = os.environ["UPMPD_HTTPHOSTPORT"]
    if "UPMPD_PATHPREFIX" not in os.environ:
        raise Exception("No UPMPD_PATHPREFIX in environment")
    pathprefix = os.environ["UPMPD_PATHPREFIX"]
    if "UPMPD_CONFIG" not in os.environ:
        raise Exception("No UPMPD_CONFIG in environment")

    # Format id: 5 for MP3 320, 6 for FLAC Lossless, 7 for FLAC
    # Hi-Res 24 bit =< 96kHz, 27 for FLAC Hi-Res 24 bit >96 kHz &
    # =< 192 kHz
    formatid = getOptionValue("qobuzformatid", 6)
    # Decide if we fetch the actual track audio details when listing containers. This is expensive
    # and normally not needed.
    needaudiodetails = getOptionValue("qobuzaudiodetails", False)
    showalbumrateandbits = getOptionValue("qobuzalbrateandbits", False)

    # renum_tracks will instruct the trackentries method to generate track numbers by
    # counting the displayed elements, so the tracks should be always presented in the correct order
    # in the case of playlists and, most importantly, multi-disc albums
    # This is afaik to the benefit of kodi mostly
    renum_tracks = getOptionValue("qobuzrenumtracks", True)

    # explicit_item_numbers will cause the lists to be prepended with a number in
    # square brackets
    # It is disabled by default
    # This is afaik to the benefit of kodi mostly which always tries
    # to sort the lists by name
    explicit_item_numbers = getOptionValue("qobuzexplicititemnumbers", False)

    # prepend_artist_to_album will cause the album list to include the
    # artist before the album title so the contents of the list are more
    # accessible on kodi, which does not display the name of the parent directory
    # This is afaik to the benefit of kodi mostly, for better usability
    prepend_artist_to_album = getOptionValue("qobuzprependartisttoalbum", False)

    appid = getOptionValue("qobuzappid")
    cfvalue = getOptionValue("qobuzcfvalue")
    if "user" in a:
        username = a["user"]
        password = a["password"]
    else:
        username, password = getserviceuserpass("qobuz")

    # Set default values for track listings
    if formatid == 5:
        setMimeAndSamplerate("audio/mpeg", "44100")
    if formatid == 6:
        setMimeAndSamplerate("application/flac", "44100")
    elif formatid == 7:
        setMimeAndSamplerate("application/flac", "96000", bits="24")
    elif formatid == 27:
        setMimeAndSamplerate("application/flac", "192000", bits="24")
    else:
        setMimeAndSamplerate("audio/mpeg", "44100")

    session = Session(
        formatid, fetch_resource_info=needaudiodetails, show_album_maxaudio=showalbumrateandbits
    )

    # Don't raise an error here because it happens if we are started as an ohcredentials helper with
    # no login data stored: we are going to get the stuff through the ohcreds service further on.
    if not username or not password:
        _g_loginok = False
        return False

    _g_loginok = session.login(username, password, appid, cfvalue)


# The following two (getappid and login) are not used by the media server, they're for use by the
# OpenHome Credentials service
@dispatcher.record("getappid")
def getappid(a):
    appid = getOptionValue("qobuzappid")
    if appid:
        return {"appid": appid}
    appid = session.get_appid()
    return {"appid": appid}


@dispatcher.record("login")
def login(a):
    maybelogin(a)
    appid, token = session.get_appid_and_token()
    if token is None:
        # login failed. cmdtalk does not like None values
        token = ""
    return {"appid": appid, "token": token}


@dispatcher.record("trackuri")
def trackuri(a):
    msgproc.log(f"trackuri: [{a}]")
    maybelogin()

    trackid = trackid_from_urlpath(pathprefix, a)
    media_url = session.get_media_url(trackid)

    return {"media_url": media_url}


def track_list(tracks):
    xbmcplugin.entries += trackentries(
        httphp, pathprefix, xbmcplugin.objid, tracks, generate_track_nums=renum_tracks
    )


@dispatcher.record("browse")
def browse(a):
    global xbmcplugin
    msgproc.log("browse: [%s]" % a)
    if "objid" not in a:
        raise Exception("No objid in args")
    objid = a["objid"]
    bflg = a["flag"] if "flag" in a else "children"

    if re.match(r"0\$qobuz\$", objid) is None:
        raise Exception("bad objid [%s]" % objid)

    xbmcplugin = XbmcPlugin(qobidprefix, objid, routeplugin=plugin)

    maybelogin()

    idpath = objid.replace(qobidprefix, "", 1)
    if bflg == "meta":
        m = re.match(r".*\$(.+)$", idpath)
        if m:
            trackid = m.group(1)
            track = session.get_track(trackid)
            track_list(
                [
                    track,
                ]
            )
    else:
        plugin.run([idpath])
    # msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries": encoded}


@plugin.route("/")
def root():
    xbmcplugin.add_directory("Discover Catalog", whats_new)
    xbmcplugin.add_directory("Discover Genres", root_genres)
    xbmcplugin.add_directory("Favourites", my_music)


@plugin.route("/root_genres")
def root_genres():
    items = session.get_genres()
    xbmcplugin.view(
        items,
        xbmcplugin.urls_from_id(genre_view, items),
        initial_item_num=1 if explicit_item_numbers else None,
    )


@plugin.route("/genre/<genre_id>")
def genre_view(genre_id):
    endpoint_list = [
        ("New Releases", plugin.url_for(featured_albums, genre_id=genre_id, type="new-releases")),
        (
            "Ideal Discography",
            plugin.url_for(featured_albums, genre_id=genre_id, type="ideal-discography"),
        ),
        ("Qobuzissime", plugin.url_for(featured_albums, genre_id=genre_id, type="qobuzissims")),
        ("Editor Picks", plugin.url_for(featured_albums, genre_id=genre_id, type="editor-picks")),
        ("Press Awards", plugin.url_for(featured_albums, genre_id=genre_id, type="press-awards")),
        ("Qobuz Playlists", plugin.url_for(featured_playlists, genre_id=genre_id, tags="None")),
    ]

    item_num = 1
    for endpoint in endpoint_list:
        xbmcplugin.add_directory(
            endpoint[0], endpoint[1], item_num=item_num if explicit_item_numbers else None
        )
        item_num += 1


@plugin.route("/featured/<genre_id>/<type>")
def featured_albums(genre_id, type):
    items = session.get_featured_albums(genre_id=genre_id, type=type)
    update_album_names(items)
    xbmcplugin.view(
        items,
        xbmcplugin.urls_from_id(album_view, items),
        initial_item_num=1 if explicit_item_numbers else None,
    )


# This used to be /featured/<genre_id>/playlist, but this path can be
# matched by the one for genre_view_type, and the wrong function may
# be called, depending on the rules ordering (meaning we had the
# problem on an rpi, but not ubuntu...)
@plugin.route("/featured_playlists/<genre_id>/<tags>")
def featured_playlists(genre_id, tags):
    items = session.get_featured_playlists(genre_id=genre_id, tags=tags)
    xbmcplugin.view(
        items,
        xbmcplugin.urls_from_id(playlist_view, items),
        initial_item_num=1 if explicit_item_numbers else None,
    )


@plugin.route("/featured_artists")
def featured_artists():
    items = session.get_featured_artists()
    xbmcplugin.view(
        items,
        xbmcplugin.urls_from_id(artist_view, items),
        initial_item_num=1 if explicit_item_numbers else None,
    )


@plugin.route("/whats_new")
def whats_new():
    xbmcplugin.add_directory(
        "Playlists", plugin.url_for(featured_playlists, genre_id=None, tags=None)
    )
    xbmcplugin.add_directory(
        "Albums (ideal discography)",
        plugin.url_for(featured_albums, genre_id=None, type="ideal-discography"),
    )
    xbmcplugin.add_directory(
        "Albums (Qobuzissime)", plugin.url_for(featured_albums, genre_id=None, type="qobuzissims")
    )
    xbmcplugin.add_directory(
        "Albums (new)", plugin.url_for(featured_albums, genre_id=None, type="new-releases-full")
    )
    xbmcplugin.add_directory("Artists", plugin.url_for(featured_artists))

    for tag, label in _playlist_tags:
        xbmcplugin.add_directory(
            f"Playlists ({label})", plugin.url_for(featured_playlists, genre_id=None, tags=tag)
        )


def update_album_names(items):
    for item in items if items and len(items) > 0 else []:
        update_album_name(item)


def update_album_name(item):
    if prepend_artist_to_album:
        artist = item.artist.name if item.artist else None
        if artist and len(artist) > 0:
            item.name = f"{artist} - {item.name}"


@plugin.route("/my_music")
def my_music():
    xbmcplugin.add_directory("Albums", favourite_albums)
    xbmcplugin.add_directory("Tracks", favourite_tracks)
    xbmcplugin.add_directory("Artists", favourite_artists)
    xbmcplugin.add_directory("Playlists", favourite_playlists)
    pass


@plugin.route("/album/<album_id>")
def album_view(album_id):
    track_list(session.get_album_tracks(album_id))


@plugin.route("/playlist/<playlist_id>")
def playlist_view(playlist_id):
    track_list(session.get_playlist_tracks(playlist_id))


@plugin.route("/artist/<artist_id>")
def artist_view(artist_id):
    xbmcplugin.add_directory("Similar Artists", plugin.url_for(similar_artists, artist_id))
    albums = session.get_artist_albums(artist_id)
    xbmcplugin.view(
        albums,
        xbmcplugin.urls_from_id(album_view, albums),
        initial_item_num=1 if explicit_item_numbers else None,
    )


@plugin.route("/artist/<artist_id>/similar")
def similar_artists(artist_id):
    artists = session.get_artist_similar(artist_id)
    xbmcplugin.view(
        artists,
        xbmcplugin.urls_from_id(artist_view, artists),
        initial_item_num=1 if explicit_item_numbers else None,
    )


@plugin.route("/favourite_tracks")
def favourite_tracks():
    track_list(session.user.favorites.tracks())


@plugin.route("/favourite_artists")
def favourite_artists():
    try:
        items = session.user.favorites.artists()
    except Exception as err:
        msgproc.log("session.user.favorite.artists failed: %s" % err)
        return
    if items:
        msgproc.log("First artist name %s" % items[0].name)
        xbmcplugin.view(
            items,
            xbmcplugin.urls_from_id(artist_view, items),
            initial_item_num=1 if explicit_item_numbers else None,
        )


@plugin.route("/favourite_albums")
def favourite_albums():
    items = session.user.favorites.albums()
    update_album_names(items)
    xbmcplugin.view(
        items,
        xbmcplugin.urls_from_id(album_view, items),
        initial_item_num=1 if explicit_item_numbers else None,
    )


@plugin.route("/favourite_playlists")
def favourite_playlists():
    items = session.user.favorites.playlists()
    xbmcplugin.view(
        items,
        xbmcplugin.urls_from_id(playlist_view, items),
        initial_item_num=1 if explicit_item_numbers else None,
    )


@dispatcher.record("search")
def search(a):
    global xbmcplugin
    msgproc.log("search: [%s]" % a)
    objid = a["objid"]
    field = a["field"] if "field" in a else None
    value = a["value"]
    objkind = a["objkind"] if "objkind" in a and a["objkind"] else None

    if re.match(r"0\$qobuz\$", objid) is None:
        raise Exception("bad objid [%s]" % objid)

    xbmcplugin = XbmcPlugin(qobidprefix, objid, routeplugin=plugin)

    maybelogin()

    if field and field not in ["artist", "album", "playlist", "track", "title"]:
        msgproc.log("Unknown field '%s'" % field)
        field = "title"
    elif field == "track":
        field = "title"

    if objkind and objkind not in ["artist", "album", "playlist", "track"]:
        msgproc.log("Unknown objkind '%s'" % objkind)
        objkind = "track"

    # type must be 'tracks', 'albums', 'artists' or 'playlists'
    qkind = objkind + "s" if objkind else None
    searchresults = session.search(field, value, qkind)

    if objkind is None or objkind == "artist":
        xbmcplugin.view(
            searchresults.artists,
            xbmcplugin.urls_from_id(artist_view, searchresults.artists),
            end=False,
        )
    if objkind is None or objkind == "album":
        xbmcplugin.view(
            searchresults.albums,
            xbmcplugin.urls_from_id(album_view, searchresults.albums),
            end=False,
        )
        # Kazoo and bubble only search for object.container.album, not
        # playlists. So if we want these to be findable, need to send
        # them with the albums
        if objkind == "album":
            searchresults = session.search(field, value, "playlists")
            objkind = "playlist"
            # Fallthrough to view playlists
    if objkind is None or objkind == "playlist":
        xbmcplugin.view(
            searchresults.playlists,
            xbmcplugin.urls_from_id(playlist_view, searchresults.playlists),
            end=False,
        )
    if objkind is None or objkind == "track":
        track_list(searchresults.tracks)

    # msgproc.log("%s" % xbmcplugin.entries)
    encoded = json.dumps(xbmcplugin.entries)
    return {"entries": encoded}


msgproc.log("Qobuz running")
maybelogin()
msgproc.mainloop()
