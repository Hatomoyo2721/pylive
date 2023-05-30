import socket
import subprocess
from array import array
from queue import Queue
from threading import Event, Lock, Thread
from time import sleep
from typing import IO, Callable, Optional

from .utils.general import MISSING_TYPE
from .utils.opusreader import OggStream

MISSING = MISSING_TYPE()


class HTTPAudioServer(Thread):
    __slots__ = (
        "socks",
        "call_after",
        "lock",
        "event",
        "queue",
        "now_playing",
        "skip",
        "header",
        "buffer",
        "ffmpeg",
        "ffmpeg_stdout",
        "ffmpeg_stdin",
        "thr_queue",
    )

    def __init__(self, io_stream: IO[bytes], call_after: Optional[Callable] = None):
        super().__init__()

        self.socks = io_stream
        self.call_after = call_after

        self.lock = Lock()
        self.event = Event()

        self.queue = ()
        self.now_playing = "stream"
        self.skip = False

        self.header = b""
        self.buffer = b""

        self.ffmpeg = MISSING  # type: ignore
        self.ffmpeg_stdout = MISSING
        self.ffmpeg_stdin = MISSING

        self.audio_thread = MISSING
        self.start()

    @staticmethod
    def _spawn_process(q: IO, d: Queue):
        s = subprocess.Popen(
            [
                "ffmpeg",
                "-strict",
                "-2",
                "-re",
                "-i",
                "-",
                "-threads",
                "2",
                "-c:a",
                "copy",
                "-vn",
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
        d.put(s)
        while True:
            if s.poll():
                break
            if q.closed:
                break

            try:
                data = q.read(1024)
            except (OSError, socket.timeout) as err:
                print(err.__class__.__name__, str(err))
                break

            if not data:
                print("no data, exiting")
                break

            s.stdin.write(data)  # type: ignore

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
                self.event.set()
                self.event.clear()
        except ValueError:
            return

    def run(self):
        queue = Queue()
        self.audio_thread = Thread(
            target=self.serve_audio,
            name="audio_vroom_vroom",
            daemon=True,
        )
        print("start stdin writer")
        with self.socks:
            stdin_writer_thread = Thread(
                target=self._spawn_process,
                args=(self.socks, queue),
                name="ffmpeg_stdin_writer",
                daemon=True,
            )

            stdin_writer_thread.start()
            self.ffmpeg: subprocess.Popen = queue.get()
            self.ffmpeg_stdin = self.ffmpeg.stdin
            self.ffmpeg_stdout = self.ffmpeg.stdout

            self.audio_thread.start()
            stdin_writer_thread.join()

            self.socks.close()
            self.ffmpeg.kill()
            self.audio_thread.join()

            self.audio_thread = self.ffmpeg = MISSING  # type: ignore
            self.ffmpeg_stdout = self.ffmpeg_stdin = MISSING
            self.header = b""
            self.buffer = b""

            if self.call_after:
                self.call_after()

    def wait_for_header(self):
        while True:
            if self.header:
                return self.header

            if not self.ffmpeg:
                return None

            sleep(0.5)

    def add(self, url):
        return
