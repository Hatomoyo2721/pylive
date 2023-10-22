from http.client import HTTPResponse
import json
from queue import Queue
from random import randint
from threading import Thread
from typing import IO, Callable, Iterable, Union
from urllib import request as urllib_request


class NonRaisingHTTPErrorProcessor(urllib_request.HTTPErrorProcessor):
    http_response = https_response = lambda self, request, response: response


class MISSING_TYPE:
    def __getattribute__(self, __n: str):
        return self.__class__

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self):
        return False


def run_in_thread(callable: Callable, *args, wait_for_result: bool = True, **kwargs):
    def call_func(queue: Queue):
        ret = callable(*args, **kwargs)
        queue.put(ret)

    q_ = Queue()
    thread = Thread(
        target=call_func, args=(q_,), name=f"run-in-thread:{id(q_):#x}", daemon=True
    )
    thread.start()

    if not wait_for_result:
        return

    thread.join()
    return q_.get_nowait()


class URLRequest:
    @staticmethod
    def request(
        url,
        method="GET",
        data=None,
        headers=None,
        want_compression=False,
        use_proxy=True,
        *args,
        **kwargs,
    ) -> HTTPResponse:
        if not headers:
            headers = dict()

        headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11",  # noqa: E501
                "Connection": "keep-alive",
            }
        )

        if want_compression:
            headers["Accept-Encoding"] = "gzip, deflate, br"
        else:
            headers["Accept-Encoding"] = "identity"

        request_data = urllib_request.Request(
            url=url,
            data=bytes(json.dumps(data), encoding="utf-8") if data else None,
            headers=headers,
            method=method,
        )
        opener = urllib_request.build_opener(NonRaisingHTTPErrorProcessor())
        # try:
        ret: HTTPResponse = opener.open(request_data, *args, **kwargs)
        if ret.getcode() >= 400:
            if use_proxy:
                return __class__.proxy_request(url, *args, **kwargs)
        return ret
        # except urllib_error.HTTPError:
        #     if use_proxy:
        #         return __class__.proxy_request(url, *args, **kwargs)

    @staticmethod
    def proxy_request(url, *args, **kwargs):
        if "proxysite" in url:
            return __class__.request(
                "https://catbox.moe/error.html",
                method="GET",
                *args,
                **kwargs,
            )

        return __class__.request(
            f"https://eu{randint(1,15)}.proxysite.com/includes/process.php?action=update",
            method="POST",
            data={"d": url, "allowCookies": "on"},
            *args,
            **kwargs,
        )


class IOReading:
    @staticmethod
    def iter_contents(
        data: Union[IO, HTTPResponse, None], chunk_size=1024
    ) -> Iterable[bytes]:
        if not data:
            return

        for chunk in iter(lambda: data.read(chunk_size), b""):
            yield chunk
