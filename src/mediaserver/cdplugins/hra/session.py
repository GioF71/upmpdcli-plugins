# defined to emulate the session object from the tidal module, which is
# defined in the tidalapi part (we want to keep the qobuz api/ dir as
# much alone as possible.
from __future__ import print_function

import sys
import json
from upmplgmodels import Artist, Album, Track, Playlist, SearchResult, \
     Category, Genre, Model
from ownModel import DynamicModel
from upmplgutils import *
from highresaudio.api import raw
import urllib
import datetime
import traceback

class Session(object):
    def __init__(self):
        self.api = None
        self.user = None

    def login(self, username, password):
        self.api = raw.RawApi()
        data = self.api.user_login(username=username, password=password)

        if data:
            self.user = User(**data)

            return True
        else:
            return False

    def get_media_url(self, trackid, format_id=5):
        # Format id: 5 for MP3 320, 6 for FLAC Lossless, 7 for FLAC
        # Hi-Res 24 bit =< 96kHz, 27 for FLAC Hi-Res 24 bit >96 kHz &
        # =< 192 kHz
        dat = self.api.track_getFileUrl(track_id = trackid, userData=self.user.get_raw())

        url = dat["data"]["results"]["tracks"]
        uplog("get_media_url got: %s" % url)
        return url['url'] if url and 'url' in url else None

    def get_album_tracks(self, albid):
        data = self.api.album_get(album_id=albid, userData=self.user.get_raw())
        album = _parse_album(data["data"]["results"])

        # album = {}
        return [_parse_track(t, album) for t in data["data"]["results"]['tracks']]

    def get_playlist_tracks(self, plid):
        data = self.api.playlist_get(playlist_id = plid, extra = 'tracks')
        #uplog("PLAYLIST: %s" % json.dumps(data, indent=4))
        return [_parse_track(t) for t in data['tracks']['items']]

    def get_artist_albums(self, artid):
        data = self.api.artist_get(artist_id=artid, extra='albums')
        if 'albums' in data:
            albums = [_parse_album(alb) for alb in data['albums']['items']]
            return [alb for alb in albums if alb.available]
        return []

    def get_artist_similar(self, artid):
        data = self.api.artist_getSimilarArtists(artist_id=artid)
        if 'artists' in data and 'items' in data['artists']:
            return [_parse_artist(art) for art in data['artists']['items']]
        return []

    def get_featured_albums(self, genre_id='None', type='new-releases'):
        #uplog("get_featured_albums, genre_id %s type %s " % (genre_id, type))
        if genre_id != 'None':
            data = self.api.album_getFeatured(type=type,
                                              genre_id=genre_id, limit=100)
        else:
            data = self.api.album_getFeatured(type=type, limit=100)
            
        try:
            albums = [_parse_album(alb) for alb in data['albums']['items']]
            if albums:
                return [alb for alb in albums if alb.available]
        except:
            pass
        return []

    def get_editor_items(self, content_type):
        if content_type is None:
            content_type = "playlist"

        if content_type == 'moods':
            data = self.api.editor_getPlaylistsMoods(userData=self.user.get_raw())
            return [_parse_menu_item(g) for g in data['data']['results']]
        elif content_type == 'genre':
            data = self.api.editor_getPlaylistsGenres(userData=self.user.get_raw())
            return [_parse_menu_item(g) for g in data['data']['results']]
        elif content_type == 'themes':
            data = self.api.editor_getPlaylistsThemes(userData=self.user.get_raw())
            return [_parse_menu_item(g) for g in data['data']['results']]
        elif content_type == 'playlists':
            data = self.api.editor_getPlaylists(userData=self.user.get_raw())
            return [_parse_menu_item(g) for g in data['data']['results']]


    def get_editor_detail_playlist(self, playlist_id):
        uplog(playlist_id)
        data = self.api.editor_getDetailPlaylist(id=playlist_id, userData=self.user.get_raw())
        return [_parse_track(t, None) for t in data["data"]["results"][0]['tracks']]


    def get_editor_playlists_by_mood(self, mood_id):
        data = self.api.editor_getPlaylistsByMood(userData=self.user.get_raw(), mood_id=mood_id)
        return [_parse_menu_image_item(item) for item in data['data']['results']]


    def get_editor_playlists_by_genre(self, genre_id):
        data = self.api.editor_getPlaylistsByGenre(userData=self.user.get_raw(), genre_id=genre_id)
        return [_parse_menu_image_item(item) for item in data['data']['results']]

    def get_editor_playlists_by_theme(self, theme_id):
        data = self.api.editor_getPlaylistsByTheme(userData=self.user.get_raw(), theme_id=theme_id)
        return [_parse_menu_image_item(item) for item in data['data']['results']]



    def get_featured_playlists(self, genre_id='None'):
        if genre_id != 'None':
            data = self.api.playlist_getFeatured(type='editor-picks',
                                                 genre_id=genre_id, limit=100)
        else:
            data = self.api.playlist_getFeatured(type='editor-picks',
                                                 limit=100)
        if data and 'playlists' in data:
            return [_parse_playlist(pl) for pl in data['playlists']['items']]
        return []

    # content_type: albums/artists/playlists.  type : The type of
    # recommandations to fetch: best-sellers, most-streamed,
    # new-releases, press-awards, editor-picks, most-featured
    # In practise, and despite the existence of the
    # catalog_getFeaturedTypes call which returns the above list, I
    # could not find a way to pass the type parameter to
    # catalog_getFeatured (setting type triggers an
    # error). album_getFeatured() and playlist_getFeatured() do accept type.
    def get_featured_items(self, content_type, type=''):
        #uplog("FEATURED TYPES: %s" % self.api.catalog_getFeaturedTypes())
        limit = '400'
        data = self.api.catalog_getFeatured(limit=limit)
        #uplog("Featured: %s" % json.dumps(data,indent=4)))
        if content_type == 'artists':
            if 'artists' in data:
                return [_parse_artist(i) for i in data['artists']['items']]
        elif content_type == 'playlists':
            if 'playlists' in data:
                return [_parse_playlist(pl) for pl in data['playlists']['items']]
        elif content_type == 'albums':
            if 'albums' in data:
                return [_parse_album(alb) for alb in data['albums']['items']]
        return []

    def get_category_list(self, genre_id=None):
        data = self.api.category_list(genre_id=genre_id)
        return [_parse_album(g) for g in data['data']['results']]

    def get_genres(self, parent=None):
        data = self.api.genre_list()
        # return [Genre(id=None, name='All Genres')] + \
        return [_parse_genre(g) for g in data['data']['results']]


    def filter_search(self, list, by):
        results = []
        for i in list:
            val = list[i]
            if val["type"].lower() == by.lower():
                val["id"] = i
                results.append(val)
        return results

    def _search1(self, query,  tp):
        uplog("_search1: query [%s] tp [%s]" % (query, tp))

        limit = 200
        slice = 200
        if tp == 'artists':
            limit = 20
            slice = 20
        elif tp == 'albums' or tp == 'playlists':
            limit = 50
            slice = 50
        offset = 0
        all = []
        while offset < limit:
            uplog("_search1: call catalog_search, offset %d" % offset)
            #data = self.api.catalog_search(query=query, type=tp,
            #                               offset=offset, limit=slice)
            data = self.api.quick_search(search=query)

            uplog(data)

            uplog(self.filter_search(data["data"], "artist"))

            ncnt = 0
            ndata = []

            try:
                if tp == 'artists':

                    uplog(data["data"])

                    artists = self.filter_search(data["data"], "artist")
                    ncnt = len(artists) #['artists']['items'])
                    ndata = [_parse_artist(i) for i in artists]

                elif tp == 'albums':
                    albums = self.filter_search(data["data"], "album")
                    ncnt = len(albums)
                    ndata = [_parse_album(i) for i in albums]
                    ndata = [alb for alb in ndata if alb.available]

                #elif tp == 'playlists':
                #    ncnt = len(data['playlists']['items'])
                #    ndata = [_parse_playlist(i) for i in \
                #             data['playlists']['items']]
                elif tp == 'tracks':
                    ncnt = len(data['tracks']['items'])
                    ndata = [_parse_track(i) for i in data['tracks']['items']]
            except Exception as err:
                uplog("_search1: exception while parsing result: %s" % err)
                var = traceback.format_exc()
                uplog(var)

                break
            all.extend(ndata)
            #uplog("Got %d more (slice %d)" % (ncnt, slice))
            if ncnt < slice:
                break
            offset += slice

        if tp == 'artists':
            return SearchResult(artists=all)
        elif tp == 'albums':
            return SearchResult(albums=all)
        elif tp == 'playlists':
            return SearchResult(playlists=all)
        elif tp == 'tracks':
            return SearchResult(tracks=all)

    def search(self, query, tp):
        if tp:
            return self._search1(query, tp)
        else:
            cplt = SearchResult()

            res = self._search1(query, 'artists')
            cplt.artists = res.artists

            res = self._search1(query, 'albums')
            cplt.albums = res.albums

            res = self._search1(query, 'tracks')
            cplt.tracks = res.tracks

            res = self._search1(query, 'playlists')
            cplt.playlists = res.playlists

            return cplt

def _parse_artist(json_obj):
    artist = Artist(id=json_obj['id'], name=json_obj['title'].encode())
    return artist

def _parse_genre(data):
    return Genre(id=urllib.quote_plus(data['prefix']), name=data['title'])

def _parse_menu_item(data):
    return DynamicModel(id=data['id'], name=data['title'])

def _parse_menu_image_item(data):
    return DynamicModel(id=data['id'], name=data['title'], image=data["playlistCover"])


def _parse_album(json_obj, artist=None, artists=None):
    #if artist is None and 'artist' in json_obj:
    #    artist = _parse_artist(json_obj['artist'])
    #if artists is None:
    #    artists = _parse_artists(json_obj['artists'])
    # available = json_obj['streamable'] if 'streamable' in json_obj else false
    #if not available:
    #    uplog("Album not streamable: %s " % json_obj['title'])

    uplog(json_obj)
    uplog("-_"*30)

    kwargs = {
        'id': json_obj['id'].encode("utf-8"),
        'name': json_obj['title'].encode("utf-8"),
        'num_tracks': json_obj.get('trackCount'),
        'duration': json_obj.get('duration'),
        'artist': json_obj['artist'].encode("utf-8"),
        #'available': available,
        #'artists': artists,
    }

    if 'cover' in json_obj:

        if "preview" in json_obj["cover"] and isinstance(json_obj["cover"], dict):
            kwargs['image'] = json_obj['cover']["preview"]["file_url"]
        else:
            kwargs['image'] = json_obj['cover']


    ##if 'releaseDate' in json_obj:
    ##    try:
    ##        kwargs['release_date'] = datetime.datetime(*map(int, json_obj['releaseDate'].split('-')))
    ##    except ##ValueError:
    ##        pass
    a = Album(**kwargs)
    return a


def _parse_playlist(json_obj, artist=None, artists=None):
    kwargs = {
        'id': json_obj['id'],
        'name': json_obj['name'],
        'num_tracks': json_obj.get('tracks_count'),
        'duration': json_obj.get('duration'),
    }
    return Playlist(**kwargs)

def _parse_track(json_obj, albumarg = None):

    artist = Artist(name=json_obj["artist"].encode("utf-8"))
    #if 'performer' in json_obj:
    #    artist = _parse_artist(json_obj['performer'])
    #elif 'artist' in json_obj:
    #    artist = json_obj["artist"] #_parse_artist(json_obj['artist'])
    #elif albumarg and albumarg.artist:
    #    artist = albumarg.artist

    album = None
    ##if 'album' in json_obj:
        ##album = _parse_album(json_obj['album'].encode(), artist)
    ##else:
    album = albumarg

    #available = json_obj['streamable'] if 'streamable' in json_obj else false
    #if not available:
    #uplog("Track no not streamable: %s " % json_obj['title'])

    #artists = _parse_artists(json_obj['artists'])


    kwargs = {
        'id': json_obj['playlistAdd'],
        'name': json_obj['title'].encode("utf-8"),
        'duration': json_obj['playtime'],
        #'disc_num': json_obj['media_number'],
        'artist': artist,
        'available': True
        #'artists': artists,
    }

    if "trackNumber" in kwargs:
        kwargs["track_num"] = json_obj["trackNumber"]
    else:
        kwargs["track_num"] = 0

    if album:
        kwargs['album'] = album

    track = Track(**kwargs)

    return track


class Favorites(object):

    def __init__(self, session):
        self.session = session

    def artists(self):
        offset = 0
        artists = []
        slice = 45
        while True:
            r = self.session.api.favorite_getUserFavorites(
                user_id = self.session.user.id,
                type = 'artists', offset=offset, limit=slice)
            #uplog("%s" % r)
            arts = [_parse_artist(item) for item in r['artists']['items']]
            artists += arts
            uplog("Favourite artists: got %d at offs %d"% (len(arts), offset))
            offset += len(arts)
            if len(arts) != slice:
                break

        return artists

    def albums(self):
        offset = 0
        albums = []
        slice = 45
        while True:
            r = self.session.api.favorite_getUserFavorites(
                user_id = self.session.user.id,
                type = 'albums', offset = offset, limit=slice)
            #uplog("%s" % r)
            albs = [_parse_album(item) for item in r['albums']['items']]
            albums += albs
            uplog("Favourite albums: got %d at offset %d"% (len(albs), offset))
            offset += len(albs)
            if len(albs) != slice:
                break

        return [alb for alb in albums if alb.available]

    def playlists(self):
        r = self.session.api.playlist_getUserPlaylists()
        return [_parse_playlist(item) for item in r['playlists']['items']]

    def tracks(self):
        offset = 0
        result = []
        slice = 45
        while True:
            r = self.session.api.favorite_getUserFavorites(
                user_id = self.session.user.id,
                type = 'tracks', offset=offset, limit=slice)
            #uplog("%s" % r)
            res = [_parse_track(item) for item in r['tracks']['items']]
            result += res
            uplog("Favourite tracks: got %d at offs %d"% (len(res), offset))
            offset += len(res)
            if len(res) != slice:
                break

        return [trk for trk in result if trk.available]


class User(object):


    def __init__(self, **kwargs):
        self.raw = kwargs
        self.session = kwargs["session_id"]
        self.id = kwargs["user_id"]
        self.fistname = kwargs["firstname"]
        self.lastname = kwargs["lastname"]
        self.has_subscription = kwargs["has_subscription"]
        self.filter = kwargs["filter"]
        self.hasfilter = kwargs["hasfilter"]
        self.favorites = Favorites(self.session)

    def get_raw(self):
        return json.dumps(self.raw)

    def playlists(self):
        return self.session.get_user_playlists(self.id)