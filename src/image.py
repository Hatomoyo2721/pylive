import json
from http.client import HTTPResponse
from random import randint
from typing import Optional, Union
from urllib import error as urllib_error

from src.utils.general import URLRequest


class GelbooruRandomImage:
    def __init__(self):
        pass

    def _request(
        self, url, method="GET", data=None, headers=None
    ) -> Optional[HTTPResponse]:
        try:
            return URLRequest.request(
                method=method,
                url=url,
                data=data,
                headers=headers,
                timeout=10,
            )

        except urllib_error.HTTPError:
            return self.proxy_request(url)

        except Exception as err:
            print(f"{err.__class__.__name__} raise {err}")
            return

    def proxy_request(self, url):
        if "proxysite" in url:
            return

        return URLRequest.request(
            f"https://eu{randint(1,15)}.proxysite.com/includes/process.php?action=update",
            method="POST",
            data={"d": url, "allowCookies": "on"},
        )

    @staticmethod
    def simple_encode(data):
        return bytes(data, "utf-8")

    def random_post(self, tags: Optional[str]) -> Optional[HTTPResponse]:
        data: HTTPResponse
        data_json: dict
        posts: Union[dict, list]

        if not tags:
            tags = "suzuran_(arknights)+-rating:explicit"

        url = f"https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&tags={tags}&limit=1"  # noqa: E501
        data = URLRequest.request(
            url,
            headers={
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        data_read = data.read()
        data_json = json.loads(data_read)

        data = URLRequest.request(
            f'{url}&pid={randint(1, data_json["@attributes"]["count"])}'
        )

        if not data or data.status >= 400:
            return

        data_json = json.loads(data.read())
        if posts := data_json.get("post"):  # type: ignore
            posts = posts[0]
            if url := posts.get("sample_url"):  # type: ignore
                return URLRequest.request(url, want_compression=True)

            if url := posts.get("file_url"):  # type: ignore
                return URLRequest.request(url, want_compression=True)

        return
