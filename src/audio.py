import sys
import json
import subprocess
from array import array
from queue import Queue
from random import randint
from threading import Event, Lock, Thread
from time import sleep
from typing import Any, Generator, Union

from src.utils import extractor
from src.utils.general import MISSING_TYPE, URLRequest, run_in_thread
from src.utils.opusreader import OggStream

MISSING = MISSING_TYPE()


def get_or_set_savefile(data=None):
    patf = sys.path[0] + "/.saveurl"
    try:
        with open(patf, "w" if data else "r") as f:
            if not data:
                return f.read()
            f.write(data)
        return data
    except FileNotFoundError:
        return "https://music.youtube.com/watch?v=cUuQ5L6Obu4"


class SendEvent:
    NEXT_TRACK = "next"
    QUEUE_ADD = "queueadd"
    NOW_PLAYING = "nowplaying"

    def __init__(self) -> None:
        self.event_queue = Queue()
        self.event_data = ""
        self.event_signal = Event()

        self._event = Thread(
            target=self.manage_event, name="send_event_manager", daemon=True
        )
        self._event.start()

    def watch(self) -> Generator[str, None, None]:
        if "nowplaying" in self.event_data:
            yield self.event_data

        while True:
            self.event_signal.wait()
            yield self.event_data

    def manage_event(self):
        while True:
            self.event_signal.clear()
            data: tuple[str, dict[str, Any]] = self.event_queue.get()
            self.event_data = f"event: {data[0]}\ndata: {json.dumps(data[1])}\n\n"
            self.event_signal.set()

    def add_event(self, event_type: str, data: dict):
        self.event_queue.put((event_type, data))


class QueueAudioHandler:
    __slots__ = (
        "queue",
        "auto_queue",
        "_skip",
        "lock",
        "event",
        "now_playing",
        "header",
        "buffer",
        "next_signal",
        "ffmpeg",
        "ffmpeg_stdout",
        "ffmpeg_stdin",
        "_audio_position",
        "audio_thread",
        "thr_queue",
        "event_queue",
    )

    def __init__(self):
        # self.queue = ["https://music.youtube.com/watch?v=cUuQ5L6Obu4"]
        self.queue: list[Union[str, dict[str, str | bool | float]]] = [
            get_or_set_savefile()
        ]
        self.auto_queue: list[Union[str, dict[str, str | bool | float]]] = []

        self._skip = False
        self.lock = Lock()
        self.event = Event()
        self.now_playing: dict = {}

        self.header = b""
        self.buffer = b""

        self.next_signal = Event()

        self.event_queue = SendEvent()

        self.ffmpeg = MISSING
        self.ffmpeg = self._spawn_main_process()
        self.ffmpeg_stdout = self.ffmpeg.stdout
        self.ffmpeg_stdin = self.ffmpeg.stdin

        self._audio_position: int = 0
        self.audio_thread = Thread(
            target=self.oggstream_reader, name="audio_vroom_vroom", daemon=True
        )
        self.thr_queue = Thread(target=self.queue_handler, name="queue", daemon=True)
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
        if "youtube" not in data["extractor"]:
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
                "videoId": self.now_playing.get("id", "NA"),
                "racyCheckOk": True,
                "contentCheckOk": True,
            },
            headers={
                "Origin": "https://www.youtube.com",
                "Referer": "https://www.youtube.com/",
                "Content-Type": "application/json; charset=utf-8",
            },
        )

        if not data:
            print("data not found")
            return []

        data_json = json.loads(data.read())

        related: list[dict] = []
        try:
            related = data_json["contents"]["twoColumnWatchNextResults"][
                "secondaryResults"
            ]["secondaryResults"]["results"]
        except Exception as err:
            print("empty response")
            print(err.__class__.__name__, str(err))
            # import pprint
            # pprint.pprint(data_json, indent=2)
            return ["https://music.youtube.com/watch?v=cUuQ5L6Obu4"]

        for item in related:
            res = item.get("compactRadioRenderer", False)

            if not res:
                continue

            playlist = extractor.fetch_playlist(res["shareUrl"])
            # remove the first entry; it usually is the same as the now-play one.
            return playlist[1:]

        playlist = []
        for count, item in enumerate(related):
            if count > 1:  # take 2 items only
                break

            res = item.get("compactVideoRenderer", False)
            if not res:
                continue
            playlist.append(f"https://www.youtube.com/watch?v={res['videoId']}")

        return playlist

    def populate_autoqueue(self):
        if not self.auto_queue and not self.queue:
            self.auto_queue = self.experiment_get_related_tracks()

    def add(self, url):
        ret = extractor.create(url, process=False)
        self.queue.append(ret)
        self.event_queue.add_event(SendEvent.QUEUE_ADD, ret)

    # def add(self, url):
    #     # run_in_thread(self.__add, url)

    def pop(self):
        if self.queue:
            self.auto_queue.clear()
            return self.queue.pop(0)

        if not self.auto_queue:
            self.populate_autoqueue()
        return self.auto_queue.pop(0)

    @staticmethod
    def _spawn_main_process():
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

    def oggstream_reader(self):
        pages_iter = OggStream(self.ffmpeg_stdout).iter_pages()  # type: ignore
        try:
            page = next(pages_iter)
            if page.flag == 2:
                self.header += b"OggS" + page.header + page.segtable + page.data

            page = next(pages_iter)
            self.header += b"OggS" + page.header + page.segtable + page.data

            for page in pages_iter:
                partial = array("b")
                partial.frombytes(b"OggS" + page.header + page.segtable)
                for data, _ in page.iter_packets():
                    partial.frombytes(data)

                self.buffer = partial.tobytes()
                self.audio_position += 1
                self.event.set()
                self.event.clear()
        except ValueError:
            return

    def ffmpeg_stdin_writer(self, q: Queue, sig: Event):
        while True:
            audio_np = q.get()
            self.audio_position = 0

            self.event_queue.add_event(SendEvent.NOW_PLAYING, audio_np)
            get_or_set_savefile(audio_np["webpage_url"])

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

    def queue_handler(self):
        queue = Queue()
        stdin_writer_thread = Thread(
            target=self.ffmpeg_stdin_writer,
            args=(queue, self.next_signal),
            name="ffmpeg_stdin_writer",
            daemon=True,
        )
        stdin_writer_thread.start()
        print("start stdin writer")

        while True:
            self.next_signal.clear()
            next_track = self.pop()  # type: ignore

            try:
                if isinstance(next_track, str):
                    next_track = extractor.create(next_track)  # type: ignore
                elif not next_track.get("process", False):  # type: ignore
                    next_track = extractor.create(next_track["webpage_url"])  # type: ignore  # noqa: E501

                if not next_track:
                    continue
            except Exception:
                continue

            self.now_playing = next_track
            queue.put(self.now_playing)
            print(f"Playing {self.now_playing['title']}")
            print("wait for signal")
            self.next_signal.wait()

    def wait_for_header(self):
        while True:
            if self.header:
                return self.header
            sleep(0.5)

    def __skip(self):
        track = self.pop()
        self.queue.append(track)
        self._skip = True

    def skip(self):
        run_in_thread(self.__skip, wait_for_result=False)
