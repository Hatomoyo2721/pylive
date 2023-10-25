const audio_player = document.getElementById("main-player");
const play_btn = document.getElementById("play");
const pause_btn = document.getElementById("pause");

const title_div = document.getElementById("title");
const artist_div = document.getElementById("artist");
const duration_div = document.getElementById("duration");

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

function watchEvent() {
  is_paused = false;
  var counter = setInterval(() => {
    increaseDuration();
  }, 1000);

  var source = new EventSource("/info_event");
  source.onmessage = function (e) {
    var data = JSON.parse(e.data);
    title_div.innerText = data.title;
    title_div.href = data.webpage_url;

    artist_div.innerText = data.channel;
    artist_div.href = data.channel_url;
  };

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

  stopFn = watchEvent();
});

pause_btn.addEventListener("click", function () {
  play_btn.classList.remove("hidden");
  pause_btn.classList.add("hidden");

  audio_player.src = "";
  stopFn();
});
