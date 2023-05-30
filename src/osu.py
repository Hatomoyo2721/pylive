import random
import re
import subprocess
from array import array
from pathlib import Path
from queue import Queue
from threading import Event, Lock, Thread
from time import sleep
from typing import Callable, Generator, List

from src.utils.general import MISSING_TYPE
from src.utils.opusreader import OggStream

MISSING = MISSING_TYPE()


class OsuMapParser(object):
    # Part of this are taken from https://github.com/The-CJ/oppadc.py/blob/master/oppadc/osumap.py#L21-L237

    __slots__ = (
        "file_path",
        "raw_str",
        "found",
        "format_version",
        "audio_path",
        "mode",
        "title",
        "title_unicode",
        "artist",
        "artist_unicode",
        "mapset_id",
        "source",
        "tags",
        "background",
        "video",
    )

    def __init__(self, file_path: str = None, raw_str: str = None):  # type: ignore
        # internal
        self.file_path: str = file_path
        self.raw_str: str = raw_str
        self.found: bool = False

        # general
        self.format_version: int = 1
        self.audio_path: str = ""
        self.mode: int = 0

        # metadata
        self.title: str = ""
        self.title_unicode: str = ""
        self.artist: str = ""
        self.artist_unicode: str = ""
        self.mapset_id: int = 0
        self.source: str = ""
        self.tags: str = ""

        # events
        self.background: str = ""
        self.video: str = ""

        self.parse()

    @staticmethod
    def __legacy_id_extract(beatmap_path: str):
        print(f"Using legacy extractor for {beatmap_path}")
        regex = r"([0-9]+)\W(.*)"
        if search := re.search(regex, Path(beatmap_path).name):
            id, _ = search.groups()
            return int(id)
        return -1  # i give up, this sh*t don't have an id

    # parse utils
    def lineGenerator(self) -> Generator[str, None, None]:
        if not self.raw_str and not self.file_path:
            raise AttributeError("missing raw content or path to file")

        elif self.raw_str:
            for line in self.raw_str.splitlines():
                yield line

        elif self.file_path:
            FileObject = open(self.file_path, mode="r", encoding="UTF-8")
            self.found = True
            for line in FileObject:
                yield line

        else:
            raise StopIteration()

    def parseProp(self, line) -> tuple:
        """
        get prop from line, also strip white spaces from value
        """
        pair: list = line.split(":", 1)
        if len(pair) == 1:
            raise SyntaxError(
                f"property must me pair of ':'-separated values, can't get property from line: {line}"
            )

        return (pair[0], pair[1].strip())

    def parse(self) -> None:
        Source: Generator[str, None, None] = self.lineGenerator()

        section: str = ""

        for line in Source:
            # ignore all types of commants
            if not line:
                continue
            if line[0] in [" ", "_"]:
                continue
            if line[0:2] == "//":
                continue

            line = line.strip()
            if not line:
                continue

            # change current section
            if line.startswith("["):
                section = line[1:-1]
                continue

            try:
                if not section:
                    format_str: str = "file format v"
                    findatpos: int = line.find(format_str)
                    if findatpos > 0:
                        self.format_version = int(line[findatpos + len(format_str) :])

                elif section == "General":
                    self.parseGeneral(line)
                elif section == "Metadata":
                    self.parseMetadata(line)
                elif section == "Events":
                    next_line = self.parseEvents(line)
                    if not next_line:
                        return

            except (ValueError, SyntaxError) as e:
                raise e

    def parseGeneral(self, line: str) -> None:
        prop: tuple = self.parseProp(line)

        if prop[0] == "Mode":
            self.mode = int(prop[1])
        elif prop[0] == "AudioFilename":
            self.audio_path = str(prop[1])

    def parseMetadata(self, line: str) -> None:
        prop: tuple = self.parseProp(line)

        if prop[0] == "Title":
            self.title = prop[1]
        elif prop[0] == "TitleUnicode":
            self.title_unicode = prop[1]
        elif prop[0] == "Artist":
            self.artist = prop[1]
        elif prop[0] == "ArtistUnicode":
            self.artist_unicode = prop[1]
        elif prop[0] == "BeatmapSetID":
            self.mapset_id = (
                int(prop[1])
                if int(prop[1]) != -1
                else self.__legacy_id_extract(self.file_path)
            )
        elif prop[0] == "Source":
            self.source = prop[1]
        elif prop[0] == "Tags":
            self.tags = prop[1]

    def parseEvents(self, line: str) -> bool:
        """Although the name is "parseEvents", it's actually just to get the beatmap's background filename"""
        pair: list = line.split(",")
        if len(pair) == 1:
            raise SyntaxError(
                f"property must me pair of ','-separated values, can't get property from line: {line}"
            )

        if pair[0] == "Video":
            self.video = pair[2].strip('"')
            return True
        elif pair[0] == "0" and pair[1] == "0":
            self.background = pair[2].strip('"')
            return False
        else:
            return True


class NotOsuSongFolder(Exception):
    pass


class BrokenOsuFile(Exception):
    pass


class BeatmapMetadata(OsuMapParser):
    def __init__(self, beatmap_path: Path) -> None:
        self.beatmap_path = beatmap_path.resolve()

        osu_list = tuple(self.beatmap_path.glob("*.osu"))
        error_counter = 0
        if not osu_list:
            raise NotOsuSongFolder(str(self.beatmap_path))

        for self.osufile_path in osu_list:
            try:
                super().__init__(file_path=str(self.osufile_path))
                break
            except:
                if error_counter <= 5:
                    error_counter += 1
                    continue
                raise BrokenOsuFile(str(self.osufile_path))

        self.audio_path: Path = self.GetAudioFile()
        if not self.audio_path.exists():
            raise NotOsuSongFolder("No song found in this beatmap")

    def GetAudioFile(self) -> Path:
        if self.audio_path:
            return self.beatmap_path.joinpath(self.audio_path)

        regex = r"(?<=AudioFilename: )(.*)"

        with self.osufile_path.open(encoding="utf-8") as file:
            while True:
                if search := re.search(regex, file.readline()):
                    return self.beatmap_path.joinpath(search.group())
                break

        try:
            return next(self.beatmap_path.glob("*.mp3"))
        except StopIteration:
            return self.beatmap_path.joinpath("audio.mp3")

    def ToJson(self):
        return {
            "title": self.title,
            "title_unicode": self.title_unicode,
            "artist": self.artist,
            "artist_unicode": self.artist_unicode,
            "mapset_id": self.mapset_id,
            "source": self.source,
            "tags": self.tags,
            "video": self.video,
            "background": self.background,
            "song_filename": self.audio_path.name,
            "has_video": 1 if self.video else 0,
        }


class QueueAudioHandler:
    __slots__ = (
        "queue",
        "queue_indexing",
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
        self.queue: tuple = tuple(Path("/win/d/osu!/Songs/").iterdir())
        self.queue_indexing: List[int] = list(range(len(self.queue)))
        random.shuffle(self.queue_indexing)

        self.skip = False
        self.lock = Lock()
        self.event = Event()
        self.now_playing: BeatmapMetadata = MISSING  # type: ignore

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

    def add(self, _):
        raise NotImplementedError

    def pop(self):
        try:
            index = self.queue_indexing.pop()
            return BeatmapMetadata(self.queue[index])
        except IndexError:
            self.queue_indexing = list(range(len(self.queue)))
            random.shuffle(self.queue_indexing)
            return self.pop()
        except (NotOsuSongFolder, BrokenOsuFile) as err:
            print(err)
            return self.pop()

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
            audio_np: Path = q.get()
            s = subprocess.Popen(
                [
                    "ffmpeg",
                    "-strict",
                    "-2",
                    "-re",
                    "-i",
                    str(audio_np.resolve()),
                    "-threads",
                    "2",
                    "-b:a",
                    "152k",
                    "-ar",
                    "48000",
                    "-c:a",
                    "libopus",
                    "-vn",
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
                data = s.stdout.read(8192)  # type: ignore
                if not data or self.skip:
                    break
                self.ffmpeg_stdin.write(data)  # type: ignore

            sig.set()
            self.skip = False
            self.header = b""
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
            self.now_playing = self.pop()

            if not self.now_playing:
                continue

            queue.put(self.now_playing.audio_path)
            print(f"Playing {self.now_playing.title}")
            signal.wait()
            print("wait for signal")

    def wait_for_header(self):
        while True:
            if self.header:
                return self.header
            sleep(0.5)
