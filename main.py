import subprocess
from array import array
from queue import Queue
from threading import Event, Lock, Thread
from time import sleep
from typing import Callable

from flask import Flask, jsonify, request
from flask.wrappers import Response

import extractor
from opusreader import OggStream


class _MISSING:
    def __getattribute__(self, __name: str):
        return self

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _MISSING()


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
        "ffmpeg",
        "ffmpeg_stdout",
        "ffmpeg_stdin",
        "audio_thread",
        "thr_queue",
    )

    def __init__(self):
        self.filler = extractor.fetch_playlist(
            "https://www.youtube.com/playlist?list=PLtXKbXocjFKmpCFHNS0SNF3GouqOuX6SF"
        )
        self.queue = []
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
    def run_in_thread(callable: Callable, *args, **kwargs):
        def call_func(queue: Queue):
            ret = callable(*args, **kwargs)
            queue.put(ret)

        q = Queue()
        thread = Thread(
            target=call_func, args=(q,), name=f"run-in-thread:{id(q):#x}", daemon=True
        )
        thread.start()

        thread.join()
        return q.get_nowait()

    def add(self, url):
        ret = self.run_in_thread(extractor.create, url, process=False)
        if not ret:
            return

        self.queue.append(ret)

    def pop(self):
        if self.queue:
            return self.queue.pop()

        return self.filler.pop()

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
        pages_iter = OggStream(self.ffmpeg_stdout).iter_pages()
        for page in pages_iter:
            partial = array("b")
            partial.frombytes(b"OggS" + page.header + page.segtable)
            for data, _ in page.iter_packets():
                partial.frombytes(data)

            print(f"{page.flag=}, {page.pagenum=} len={len(partial)}")
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
                    "-re",
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
                    "-loglevel",
                    "error",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stdin=None,
                stderr=None,
            )

            while True:
                data = s.stdout.read(8192)
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
            self.now_playing: dict = self.pop()

            if isinstance(self.now_playing, str):
                self.now_playing = extractor.create(self.now_playing)  # type: ignore
            elif not self.now_playing.get("process", False):
                self.now_playing = extractor.create(self.now_playing)  # type: ignore

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


audio = QueueAudioHandler()
app = Flask(__name__)


def gen(audio: QueueAudioHandler):
    yield audio.wait_for_header()

    while audio.audio_thread.is_alive():
        yield audio.buffer
        audio.event.wait()
    return


@app.route("/add")
def add():
    url = request.args.get("url")
    if not url:
        return Response("url params can't be null")

    audio.add(url)
    return Response("done")


@app.route("/queue")
def get_queue():
    index = int(request.args.get("index") or request.args.get("page", 0)) + 1
    end_offset = max(index * 5, len(audio.queue))
    start_offset = max(end_offset - 5, 0)
    return jsonify(audio.queue[start_offset:end_offset])


@app.route("/np")
@app.route("/nowplaying")
def np():
    return jsonify(audio.now_playing)


@app.route("/skip")
def skip():
    audio.skip = True
    return Response("done")


@app.route("/stream")
def get():
    return Response(gen(audio), content_type="audio/ogg")


app.run()
