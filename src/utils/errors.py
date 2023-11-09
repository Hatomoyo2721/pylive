class VideoIsLiveException(Exception):
    pass


class VideoIsPrivateException(Exception):
    pass


class VideoIsUnavailableException(Exception):
    pass


class VideoIsOverLengthException(Exception):
    pass


class PlaylistNotFoundException(Exception):
    pass
