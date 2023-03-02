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
    "playlistend": 4,
    # 'cookiefile': '/home/foxeiz/.config/yt-dlp/cookies-youtube-com.txt'
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

    playlist = []
    with YoutubeDL(globopts) as ytdl:
        data = ytdl.extract_info(url=url_playlist, download=False, process=False)

        if not data:
            return playlist

        for item in data.get("entries", []):
            try:
                if not item:
                    return playlist

                if item.get("duration", 0.0) <= 900.0:
                    playlist.append(item["url"])
            except TypeError:
                print(f"{item['url']} is private")

    return playlist
