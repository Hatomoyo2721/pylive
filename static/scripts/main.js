const audio_player = document.getElementById("main-player");
const play_btn = document.getElementById("play");
const pause_btn = document.getElementById("pause");

const title_div = document.getElementById("title");
const artist_div = document.getElementById("artist");
const duration_div = document.getElementById("duration");

const queue_list = document.getElementById("queue-list");
const queue_empty = document.getElementsByClassName("queue-empty")[0];

var duration = 0;
var is_paused = true;

var stopFn = function () {};

function secondsToTime(secs) {
  secs = Math.round(secs);
  var hours = Math.floor(secs / (60 * 60));

  var divisor_for_minutes = secs % (60 * 60);
  var minutes = Math.floor(divisor_for_minutes / 60);

  var divisor_for_seconds = divisor_for_minutes % 60;
  var seconds = Math.ceil(divisor_for_seconds);

  if (hours == 0) {
    return minutes + ":" + (seconds < 10 ? "0" : "") + seconds;
  } else {
    return (
      hours +
      ":" +
      (minutes < 10 ? "0" : "") +
      minutes +
      ":" +
      (seconds < 10 ? "0" : "") +
      seconds
    );
  }
}

function increaseDuration() {
  duration += 1;
  duration_div.innerText = secondsToTime(duration);
}

function changeSong(e) {
  if (queue_list.children.length > 1) {
    queue_list.removeChild(queue_list.children[1]);
    if (queue_list.children.length == 1) {
      queue_empty.classList.remove("hidden");
    }
  }
  data = JSON.parse(e.data);
  title_div.innerText = data.title;
  title_div.href = data.webpage_url;

  artist_div.innerText = data.channel;
  artist_div.href = data.channel_url;
}

function addQueue(e) {
  data = JSON.parse(e.data);
  queue_empty.classList.add("hidden");

  var _d = document.createElement("div");
  _d.innerHTML = `<a href="${data.webpage_url}" class="text" id="title">${data.title}</a>
    <a href="${data.channel_url}" class="text" id="artist">${data.channel}</a>`;
  queue_list.appendChild(_d);
}

function watchEvent() {
  is_paused = false;
  var counter = setInterval(() => {
    increaseDuration();
  }, 1000);

  // var _map = {
  //   nowplaying: changeSong,
  // };

  var source = new EventSource("/watch_event");
  // source.onmessage = function (e) {
  //   var data = JSON.parse(e.data);
  //   window.console.log(e);
  //   window.console.log(data);
  //   _map[e.event](data.data);
  // };
  source.addEventListener("nowplaying", changeSong);
  source.addEventListener("queueadd", addQueue);

  return function () {
    is_paused = true;
    clearInterval(counter);
    source.close();
  };
}

play_btn.addEventListener("click", function () {
  play_btn.classList.add("hidden");
  pause_btn.classList.remove("hidden");

  audio_player.src = "/stream";
  audio_player.play();
  window.ctxAudio.resume();

  stopFn = watchEvent();
});

pause_btn.addEventListener("click", function () {
  play_btn.classList.remove("hidden");
  pause_btn.classList.add("hidden");

  audio_player.src = "";
  stopFn();
});
