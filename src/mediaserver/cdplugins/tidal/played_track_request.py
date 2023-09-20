class PlayedTrackRequest:

    def __init__(self):
        self._track_id : str = None
        self._album_id : str = None
        self._album_track_count : int = None
        self._track_name : str = None
        self._track_duration : int = None
        self._track_num : int = None
        self._volume_num : int = None
        self._album_num_volumes : int = None
        self._album_name : str = None
        self._audio_quality : str = None
        self._album_artist_name : str = None
        self._image_url : str = None
        self._explicit : int = None
        self._artist_name : str = None
        self._album_duration : int = None

    @property
    def track_id(self) -> str:
        return self._track_id

    @track_id.setter
    def track_id(self, value : str):
        self._track_id : str = value

    @property
    def album_id(self) -> str:
        return self._album_id

    @album_id.setter
    def album_id(self, value : str):
        self._album_id : str = value

    @property
    def album_track_count(self) -> int:
        return self._album_track_count

    @album_track_count.setter
    def album_track_count(self, value : str):
        self._album_track_count : int = value
    
    @property
    def track_name(self) -> str:
        return self._track_name

    @track_name.setter
    def track_name(self, value : str):
        self._track_name : str = value

    @property
    def track_duration(self) -> int:
        return self._track_duration

    @track_duration.setter
    def track_duration(self, value : int):
        self._track_duration : int = value

    @property
    def track_num(self) -> int:
        return self._track_num

    @track_num.setter
    def track_num(self, value : int):
        self._track_num : int = value

    @property
    def volume_num(self) -> int:
        return self._volume_num

    @volume_num.setter
    def volume_num(self, value : int):
        self._volume_num : int = value

    @property
    def album_num_volumes(self) -> int:
        return self._album_num_volumes

    @album_num_volumes.setter
    def album_num_volumes(self, value : int):
        self._album_num_volumes : int = value

    @property
    def album_name(self) -> str:
        return self._album_name

    @album_name.setter
    def album_name(self, value : str):
        self._album_name : str = value

    @property
    def audio_quality(self) -> str:
        return self._audio_quality

    @audio_quality.setter
    def audio_quality(self, value : str):
        self._audio_quality : str = value

    @property
    def album_artist_name(self) -> str:
        return self._album_artist_name

    @album_artist_name.setter
    def album_artist_name(self, value : str):
        self._album_artist_name : str = value

    @property
    def image_url(self) -> str:
        return self._image_url

    @image_url.setter
    def image_url(self, value : str):
        self._image_url : str = value

    @property
    def explicit(self) -> int:
        return self._explicit

    @explicit.setter
    def explicit(self, value : int):
        self._explicit : int = value

    @property
    def artist_name(self) -> str:
        return self._artist_name

    @artist_name.setter
    def artist_name(self, value : str):
        self._artist_name : str = value

    @property
    def album_duration(self) -> int:
        return self._album_duration

    @album_duration.setter
    def album_duration(self, value : int):
        self._album_duration : int = value

