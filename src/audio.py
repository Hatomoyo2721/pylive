import json
import subprocess
from array import array
from queue import Queue
from threading import Event, Lock, Thread
from time import sleep
from random import randint
from typing import Union

from src.utils import extractor
from src.utils.general import MISSING_TYPE, URLRequest, run_in_thread
from src.utils.opusreader import OggStream

MISSING = MISSING_TYPE()


class QueueAudioHandler:
    __slots__ = (
        "filler",
        "queue",
        "auto_queue",
        "_skip",
        "lock",
        "event",
        "now_playing",
        "header",
        "buffer",
        "ffmpeg",
        "ffmpeg_stdout",
        "ffmpeg_stdin",
        "_audio_position",
        "audio_thread",
        "thr_queue",
    )

    def __init__(self):
        # self.filler = extractor.fetch_playlist(
        #     "https://www.youtube.com/playlist?list=PLtXKbXocjFKmpCFHNS0SNF3GouqOuX6SF"
        # )
        # self.queue = ["https://music.youtube.com/watch?v=KBuILboH6xY"]
        self.queue = ["https://www.youtube.com/watch?v=QkAZ58VEXzM"]
        self.auto_queue = []
        self._skip = False
        self.lock = Lock()
        self.event = Event()
        self.now_playing: Union[dict, str] = {}

        self.header = b""
        self.buffer = b""

        self.ffmpeg = MISSING
        self.ffmpeg = self._spawn_process()
        self.ffmpeg_stdout = self.ffmpeg.stdout
        self.ffmpeg_stdin = self.ffmpeg.stdin

        self._audio_position: int = 0
        self.audio_thread = Thread(
            target=self.serve_audio, name="audio_vroom_vroom", daemon=True
        )
        self.thr_queue = Thread(target=self.queue_handle, name="queue", daemon=True)
        self.thr_queue.start()
        self.audio_thread.start()

    @property
    def audio_duration(self):
        if not isinstance(self.now_playing, dict):
            return 0

        return self.now_playing.get("duration", 0)

    @property
    def audio_position(self):
        return self._audio_position

    @audio_position.setter
    def audio_position(self, value):
        with self.lock:
            self._audio_position = value

    @staticmethod
    def get_related_tracks(data):
        if data["extractor"] != "youtube":
            data = extractor.create(f"ytsearch1:{data['title']}", process=False)
            if not data:
                return

        related_video: dict = json.loads(
            URLRequest.request(
                f'https://vid.puffyan.us/api/v1/videos/{data["id"]}?fields=recommendedVideos'
            ).read()
        )

        if related_video.get("recommendedVideos", False):
            related_video = related_video["recommendedVideos"]

        return extractor.create(
            f"https://www.youtube.com/watch?v={related_video[randint(0, len(related_video) - 1)]['videoId']}",
            process=False,
        )

    def experiment_get_related_tracks(self) -> list:
        data = URLRequest.request(
            "https://www.youtube.com/youtubei/v1/next?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8",
            method="POST",
            data={
                "context": {
                    "client": {
                        "hl": "en",
                        "gl": "US",
                        "clientName": "WEB",
                        "clientVersion": "2.20220809.02.00",
                        "originalUrl": "https://www.youtube.com",
                        "platform": "DESKTOP",
                    },
                },
                "videoId": self.now_playing.get("id", "NA"),  # type: ignore
                "racyCheckOk": True,
                "contentCheckOk": True,
            },
            headers={
                "Origin": "https://www.youtube.com",
                "Referer": "https://www.youtube.com/",
            },
        )

        if not data:
            return []

        data_json = json.loads(data.read())

        related = data_json["contents"]["twoColumnWatchNextResults"][
            "secondaryResults"
        ]["secondaryResults"]["results"]

        for item in related:
            res = item.get("compactRadioRenderer", False)

            if not res:
                continue

            playlist = extractor.fetch_playlist(res["shareUrl"])
            return playlist

        playlist = []
        for item in related:
            res = item.get("compactVideoRenderer", False)

            if not res:
                continue

            playlist.append(
                extractor.create(f"https://www.youtube.com/watch?v={res['videoId']}")
            )
        return playlist

    @staticmethod
    def __add(queue, url):
        ret = extractor.create(url, process=False)
        if not ret:
            return

        queue.append(ret)

    def add(self, url):
        run_in_thread(self.__add, self.queue, url)

    def pop(self):
        if self.queue:
            self.auto_queue.clear()
            return self.queue.pop()

        if not self.auto_queue:
            self.auto_queue = self.experiment_get_related_tracks()

        return self.auto_queue.pop()

    @staticmethod
    def _spawn_process():
        return subprocess.Popen(
            [
                "ffmpeg",
                "-re",
                "-i",
                "-",
                "-threads",
                "2",
                "-c:a",
                "copy",
                "-f",
                "opus",
                "-loglevel",
                "error",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=None,
        )

    def serve_audio(self):
        pages_iter = OggStream(self.ffmpeg_stdout).iter_pages()  # type: ignore
        try:
            for page in pages_iter:
                partial = array("b")
                partial.frombytes(b"OggS" + page.header + page.segtable)
                for data, _ in page.iter_packets():
                    partial.frombytes(data)

                data = partial.tobytes()
                if page.flag == 2 or page.pagenum == 1:
                    self.header += data
                    continue

                self.buffer = data
                print(f"in serve_audio {self.audio_position=}, {self.audio_duration=}")
                self.audio_position += 1
                self.event.set()
                self.event.clear()
        except ValueError:
            return

    def stdin_writer(self, q: Queue, sig: Event):
        while True:
            audio_np = q.get()
            self.audio_position = 0
            s = subprocess.Popen(
                [
                    "ffmpeg",
                    "-reconnect",
                    "1",
                    "-reconnect_streamed",
                    "1",
                    "-reconnect_delay_max",
                    "5",
                    "-i",
                    audio_np["url"],
                    "-threads",
                    "2",
                    "-b:a",
                    "152k",
                    "-ar",
                    "48000",
                    "-c:a",
                    "copy",
                    "-f",
                    "opus",
                    "-vn",
                    "-loglevel",
                    "error",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stdin=None,
                stderr=None,
            )

            while True:
                if s.poll():
                    break

                data = s.stdout.read(8192)  # type: ignore
                if not data or self._skip:
                    break
                self.ffmpeg_stdin.write(data)  # type: ignore

            sig.set()
            self._skip = False
            # self.header = b""
            # self.buffer = b""
            print("signal is set")

    def queue_handle(self):
        queue = Queue()
        signal = Event()
        stdin_writer_thread = Thread(
            target=self.stdin_writer,
            args=(queue, signal),
            name="ffmpeg_stdin_writer",
            daemon=True,
        )
        stdin_writer_thread.start()
        print("start stdin writer")

        while True:
            signal.clear()
            self.now_playing = self.pop()  # type: ignore

            if isinstance(self.now_playing, str):
                self.now_playing = extractor.create(self.now_playing)  # type: ignore
            elif not self.now_playing.get("process", False):  # type: ignore
                self.now_playing = extractor.create(self.now_playing["webpage_url"])  # type: ignore  # noqa: E501

            if not self.now_playing:
                continue

            queue.put(self.now_playing)
            print(f"Playing {self.now_playing['title']}")
            print("wait for signal")
            signal.wait()

    def wait_for_header(self):
        while True:
            if self.header:
                return self.header
            sleep(0.5)

    def skip(self):
        track = run_in_thread(self.pop)
        self.queue.append(track)
        self._skip = True
