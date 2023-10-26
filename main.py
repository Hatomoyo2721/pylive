from time import sleep
from flask import Flask, Response, jsonify, render_template, request

from src.audio import QueueAudioHandler
from src.utils.general import URLRequest, run_in_thread
import json

WEBHOOK_URL = None
app = Flask(__name__, static_url_path="/static")
# prev_add = None

# audio streaming
audio = QueueAudioHandler()


def send_webhook(func):
    def webhook(response: Response, webhook_url=None, func_name=""):
        if not webhook_url:
            return

        res = URLRequest.request(
            webhook_url,
            method="POST",
            data={
                "content": f"`/{func_name}`\n```{json.dumps(response.json, indent=2)}\n```",
                "username": "debug radio",
            },
            headers={
                "Content-Type": "application/json",
            },
        )

        if res.getcode() != 204:
            print("Failed to send webhook")
            print(res.read().decode("utf-8"))

    def wrapper(*args, **kwargs):
        ret = func(*args, **kwargs)
        run_in_thread(
            webhook,
            wait_for_result=False,
            response=ret[0],
            func_name=func.__name__,
            webhook_url=WEBHOOK_URL,
        )
        return ret

    wrapper.__name__ = func.__name__
    return wrapper


def check_empty(arg) -> bool:
    if arg is None:
        return True

    return any(arg) and (len(arg) != 0)


def make_response(
    data=None,
    msg: str = "success",
    is_error: bool = False,
    status_code: int = 200,
    other_data=None,
) -> tuple[Response, int]:
    build_resp = {
        "msg": msg,
        "error": is_error,
        "data": data if check_empty(data) else None,
    }

    if other_data:
        build_resp.update({"other_data": other_data})

    return jsonify(build_resp), status_code


def make_error(*args, **kwargs):
    return make_response(*args, is_error=True, **kwargs)


def gen(audio: QueueAudioHandler):
    yield audio.wait_for_header()
    while audio.audio_thread.is_alive():
        yield audio.buffer
        audio.event.wait()
    return


@app.route("/add")
@send_webhook
def add():
    # global prev_add
    # if prev_add == request.remote_addr:
    #     return make_error(msg="Calm down you just use this.", status_code=429)

    url = request.args.get("url")
    if not url:
        return make_error(msg="missing `url` argument")

    try:
        audio.add(url)
    except Exception as err:
        return make_error(msg=f"{err.__class__.__name__}: {str(err)}")

    # prev_add = request.remote_addr
    return make_response()


@app.route("/queue")
@send_webhook
def get_queue():
    index = int(request.args.get("index") or request.args.get("page", 0)) + 1
    use_autoqueue = request.args.get("use_autoqueue", "0") == "1"

    end_offset = max(index * 5, len(audio.queue))
    start_offset = max(end_offset - 5, 0)

    data = {
        "queue": audio.queue[start_offset:end_offset],
    }

    if use_autoqueue and audio.auto_queue:
        data.update({"auto_queue": audio.auto_queue})

    return make_response(data=data)


@app.route("/np")
@app.route("/nowplaying")
@send_webhook
def get_nowplaying():
    data: dict = {"now_playing": audio.now_playing}

    if audio.queue:
        data.update({"next_up": audio.queue[0]})

    return make_response(data=data)


@app.route("/skip")
@send_webhook
def skip():
    audio._skip = True
    return make_response()


@app.route("/stream")
def get_stream():
    if not audio.ffmpeg:
        return make_response(msg="No stream avaliable.", is_error=True, status_code=404)

    return Response(gen(audio), content_type="audio/ogg", status=200)


@app.route("/")
def index():
    return render_template("stream.html", np=audio.now_playing, queue=audio.queue)


@app.route("/info_event")
def get_info_event():
    def gen():
        while audio.audio_thread.is_alive():
            while not isinstance(audio.now_playing, dict):
                sleep(1)

            prv_np = audio.now_playing

            yield f"data: {json.dumps(audio.now_playing)}\n\n"
            audio.next_signal.wait()

            # wait till now_playing is changed
            while prv_np == audio.now_playing:
                sleep(1)

        return

    return Response(gen(), content_type="text/event-stream")


if __name__ == "__main__":
    app.run("0.0.0.0", port=5000, threaded=True)
