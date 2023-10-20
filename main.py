from flask import Flask, Response, jsonify, request

from src.audio import QueueAudioHandler
from src.image import GelbooruRandomImage
from src.utils.general import IOReading

app = Flask(__name__)


# audio streaming
audio = QueueAudioHandler()


def check_empty(arg) -> bool:
    if arg is None:
        return True

    return any(arg) and (len(arg) != 0)


def make_response(
    data=None, msg: str = "success", is_error: bool = False, status_code: int = 200
) -> tuple[Response, int]:
    build_resp = {
        "msg": msg,
        "error": is_error,
        "data": data if check_empty(data) else None,
    }
    return jsonify(build_resp), status_code


def make_error(*args, **kwargs):
    return make_response(*args, is_error=True, **kwargs)


def gen(audio: QueueAudioHandler):
    yield audio.wait_for_header()
    while audio.audio_thread.is_alive():  # type: ignore
        yield audio.buffer
        audio.event.wait()
    return


@app.route("/add")
def add():
    url = request.args.get("url")
    if not url:
        return Response("url params can't be null")

    try:
        audio.add(url)
    except Exception as err:
        return make_error(msg=f"{err.__class__.__name__}: {str(err)}")

    return make_response()


@app.route("/queue")
def get_queue():
    index = int(request.args.get("index") or request.args.get("page", 0)) + 1
    end_offset = max(index * 5, len(audio.queue))
    start_offset = max(end_offset - 5, 0)
    return make_response(data=audio.queue[start_offset:end_offset])


@app.route("/np")
@app.route("/nowplaying")
def np():
    return make_response(data=audio.now_playing)


@app.route("/skip")
def skip():
    audio._skip = True
    return make_response()


@app.route("/stream")
def get():
    if not audio.ffmpeg:
        return make_response(msg="No stream avaliable.", is_error=True, status_code=404)

    return Response(gen(audio), content_type="audio/ogg")  # type: ignore


# image randomize
gelbooru = GelbooruRandomImage()


@app.route("/random")
def random_image():
    image = gelbooru.random_post(tags=request.args.get("tags"))
    return Response(
        IOReading.iter_contents(image, 8192),
        headers=image.headers.items(),  # type: ignore
    )


if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, threaded=True)
