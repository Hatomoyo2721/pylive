from http.client import HTTPResponse
from queue import Queue
from random import randint
from threading import Thread
from typing import IO, Callable, Iterable, Union
from urllib import error as urllib_error
from urllib import request as urllib_request


class MISSING_TYPE:
    def __getattribute__(self, __n: str):
        return self.__class__

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self):
        return False


class ThreadRunner:
    @staticmethod
    def run_in_thread(callable: Callable, *args, **kwargs):
        def call_func(queue: Queue):
            ret = callable(*args, **kwargs)
            queue.put(ret)

        q_ = Queue()
        thread = Thread(
            target=call_func, args=(q_,), name=f"run-in-thread:{id(q_):#x}", daemon=True
        )
        thread.start()

        thread.join()
        return q_.get_nowait()


class URLRequest:
    @staticmethod
    def request(
        url,
        method="GET",
        data=None,
        headers=dict(),
        want_compression=False,
        *args,
        **kwargs,
    ) -> HTTPResponse:
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
            url=url, data=data, headers=headers, method=method
        )
        try:
            return urllib_request.urlopen(request_data, *args, **kwargs)
        except urllib_error.HTTPError:
            return __class__.proxy_request(url, *args, **kwargs)

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
