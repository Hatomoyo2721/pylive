import json
import subprocess
from array import array
from queue import Queue
from threading import Event, Lock, Thread
from time import sleep

from src.utils import extractor
from src.utils.general import MISSING_TYPE, ThreadRunner, URLRequest
from src.utils.opusreader import OggStream

MISSING = MISSING_TYPE()


class QueueAudioHandler:
    __slots__ = (
        "filler",
        "queue",
        "skip",
        "lock",
        "event",
        "now_playing",
        "header",
        "buffer",
        "ffmpeg",
        "ffmpeg_stdout",
        "ffmpeg_stdin",
        "audio_thread",
        "thr_queue",
    )

    def __init__(self):
        # self.filler = extractor.fetch_playlist(
        #     "https://www.youtube.com/playlist?list=PLtXKbXocjFKmpCFHNS0SNF3GouqOuX6SF"
        # )
        self.queue = ["https://www.youtube.com/watch?v=2b1IexhKPz4"]
        self.skip = False
        self.lock = Lock()
        self.event = Event()
        self.now_playing: dict = None  # type: ignore

        self.header = b""
        self.buffer = b""

        self.ffmpeg = MISSING
        self.ffmpeg = self._spawn_process()
        self.ffmpeg_stdout = self.ffmpeg.stdout
        self.ffmpeg_stdin = self.ffmpeg.stdin

        self.audio_thread = Thread(
            target=self.serve_audio, name="audio_vroom_vroom", daemon=True
        )
        self.thr_queue = Thread(target=self.queue_handle, name="queue", daemon=True)
        self.thr_queue.start()
        self.audio_thread.start()

    @staticmethod
    def get_related_tracks(data):
        if data["extractor"] != "youtube":
            data = extractor.create(f"ytsearch1:{data['title']}", process=False)
            if not data:
                return

        related_video = json.loads(
            URLRequest.request(
                f'https://yt.funami.tech/api/v1/videos/{data["id"]}?fields=recommendedVideos'
            ).read()
        )
        return extractor.create(
            f"https://www.youtube.com/watch?v={related_video['recommendedVideos'][0]['videoId']}",
            process=False,
        )

    @staticmethod
    def __add(queue, url):
        ret = extractor.create(url, process=False)
        if not ret:
            return

        queue.append(ret)

    def add(self, url):
        ThreadRunner.run_in_thread(self.__add, self.queue, url)

    def pop(self):
        if self.queue:
            return self.queue.pop()

        return self.get_related_tracks(self.now_playing)

    @staticmethod
    def _spawn_process():
        return subprocess.Popen(
            [
                # "ffmpeg", "-re", "-i", "sample.webm",
                "ffmpeg",
                "-re",
                "-i",
                "-",
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
        for page in pages_iter:
            partial = array("b")
            partial.frombytes(b"OggS" + page.header + page.segtable)
            for data, _ in page.iter_packets():
                partial.frombytes(data)

            # print(f"{page.flag=}, {page.pagenum=} len={len(partial)}")
            data = partial.tobytes()
            if page.flag == 2 or page.pagenum == 1:
                self.header += data
                continue

            self.buffer = data
            self.event.set()
            self.event.clear()

    def stdin_writer(self, q: Queue, sig: Event):
        while True:
            audio_np = q.get()
            s = subprocess.Popen(
                [
                    # "ffmpeg", "-re", "-i", "sample.webm",
                    "ffmpeg",
                    "-reconnect",
                    "1",
                    "-reconnect_streamed",
                    "1",
                    "-reconnect_delay_max",
                    "5",
                    "-i",
                    audio_np["url"],
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
                data = s.stdout.read(8192)  # type: ignore
                if not data or self.skip:
                    break
                self.ffmpeg_stdin.write(data)  # type: ignore

            sig.set()
            self.skip = False
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
            self.now_playing: dict = self.pop()  # type: ignore

            if isinstance(self.now_playing, str):
                self.now_playing = extractor.create(self.now_playing)  # type: ignore
            elif not self.now_playing.get("process", False):  # type: ignore
                self.now_playing = extractor.create(self.now_playing["webpage_url"])  # type: ignore  # noqa: E501

            if not self.now_playing:
                continue

            queue.put(self.now_playing)
            print(f"Playing {self.now_playing['title']}")
            signal.wait()
            print("wait for signal")

    def wait_for_header(self):
        while True:
            if self.header:
                return self.header
            sleep(0.5)
