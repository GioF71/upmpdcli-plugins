class ReplayGain:

    def __init__(
            self,
            album_gain: float = None,
            track_gain: float = None):
        self.__album_gain: float = album_gain
        self.__track_gain: float = track_gain
    
    @property
    def album_gain(self) -> float | None:
        return self.__album_gain

    @property
    def track_gain(self) -> float | None:
        return self.__track_gain