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

function voteSkip() {
  var xhttp = new XMLHttpRequest();
  xhttp.onload = function () {
    data = JSON.parse(xhttp.responseText);
    if (data.msg == "success") {
      console.log("Vote skip success");
    }
  }
  xhttp.open("GET", "/skip", true);
  xhttp.send();
}

function increaseDuration() {
  duration += 1;
  duration_div.innerText = secondsToTime(duration);
}

function changeSongEvent(e) {
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

function addQueueEvent(e) {
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

  if (!source) {
    var source = new EventSource("/watch_event");
  }
  source.addEventListener("nowplaying", changeSongEvent);
  source.addEventListener("queueadd", addQueueEvent);

  return function () {
    is_paused = true;
    clearInterval(counter);
    source.close();
    source = null;
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

function addQueue(url) {
  var xhttp = new XMLHttpRequest();
  xhttp.onload = function () {
    data = JSON.parse(xhttp.responseText);
    if (data.msg == "success") {
      console.log("Add queue success");
    }
  }
  xhttp.open("GET", `/add?url=${url}`, true);
  xhttp.send();
}

document.getElementById("add-btn").addEventListener("click", function () {
  var input = document.getElementById("add-queue-box");
  if (this.style.transform != "") {
    this.style.transform = "";
    input.style.height = "";
    input.style.visibility = "";
    if (input.value != "") {
      addQueue(input.value);
      input.value = "";
    }
    return;
  }
  this.style.transform = "rotate(45deg)";
  input.style.height = "25px";
  input.style.visibility = "visible";
});