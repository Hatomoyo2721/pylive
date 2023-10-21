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
    "playlistend": 10,
    "playlistrandom": True,
}


def check_length(item: dict) -> bool:
    """Check if length > 15min"""
    return item.get("duration", 0.0) > 900.0


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

            if check_length(data):
                return

            need_reencode = False
            if data.get("asr", 0) != 48000:
                need_reencode = True

            if data.get("acodec", "none") != "opus":
                need_reencode = True

            ret = {
                "title": data.get("title", "NA"),
                "id": data.get("id", "NA"),
                "webpage_url": data.get("webpage_url")
                or data.get("original_url")
                or data.get("url", "NA"),
                "duration": data.get("duration", 0.0),
                "format_duration": data.get("duration_string", "0:00"),
                "channel": data.get("uploader", "NA"),
                "channel_url": data.get("uploader_url")
                or data.get("channel_url", "NA"),
                "process": False,
                "extractor": data.get("extractor", "None"),
                "need_reencode": need_reencode,
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

                if check_length(item):
                    continue

                playlist.append(item["url"])
            except TypeError:
                print(f"{item['url']} is private")

            count += 1

    return playlist
