from upmplgmodels import Artist, Album, Track, Playlist, SearchResult, \
     Category, Genre, Model


class OwnGenre(Genre):
    prefix = "Unknown"

class DynamicModel(Model):

    def set(self, name, value):
        setattr(self, name, value)