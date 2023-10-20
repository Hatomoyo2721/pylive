from typing import Union

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

globopts = {
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
    "playlist_items": "1-10",
    "extract_flat": True,
    "compat_opts": ["no-youtube-unavailable-videos"],
    "playlistend": 10
}


def create(url, process=True) -> Union[dict, None]:
    """
    Return data as follow:
        - duration[float]
        - [tuple]:
            - title[str]
            - id[str]
            - original_url[str]
    """

    ytdlopts = globopts.copy()
    ytdlopts.update(
        {
            "format": "bestaudio[ext=webm]/bestaudio/best",
            "restrictfilenames": True,
        }
    )

    with YoutubeDL(ytdlopts) as ytdl:
        try:
            data = ytdl.extract_info(url=url, download=False, process=process)
            if not data:
                return

            ret = {
                "title": data.get("title", "NA"),
                "id": data.get("id", "NA"),
                "webpage_url": data.get("webpage_url")
                or data.get("original_url")
                or data.get("url", "NA"),
                "duration": data.get("duration", 0.0),
                "channel": data.get("uploader", "NA"),
                "channel_url": data.get("uploader_url")
                or data.get("channel_url", "NA"),
                "process": False,
                "headers": data.get("http_headers", {}),
                "extractor": data.get("extractor", "None"),
            }

            if process:
                ret.update({"url": data.get("url")})
                ret["process"] = True
            return ret
        except DownloadError:
            print("403 link forbidden but i dont fucking care")
            return


def fetch_playlist(url_playlist) -> list:
    item: dict
    max_entries = globopts.get("playlistend", 25)
    count = 0

    print(url_playlist)

    playlist = []
    with YoutubeDL(globopts) as ytdl:
        data = ytdl.extract_info(url=url_playlist, download=False, process=False)

        if not data:
            return playlist

        for item in data.get("entries", []):
            try:
                if count >= max_entries:
                    return playlist

                if not item:
                    return playlist

                if item.get("duration", 0.0) <= 900.0:
                    playlist.append(item["url"])
            except TypeError:
                print(f"{item['url']} is private")

            count += 1

    return playlist
