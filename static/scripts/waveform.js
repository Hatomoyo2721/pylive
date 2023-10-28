import Oscilloscope from "./dist/oscilloscope.js";

window.ctxAudio = new window.AudioContext();
var audioElement = document.getElementById("main-player");
var source = window.ctxAudio.createMediaElementSource(audioElement);
var options = {
  stroke: 1, // size of the wave
  type: "oscilloscope",
  fftSize: 2048, // size ranging from 32 to any number that that is a power of 2
};
var canvas = document.getElementById("visualizer");
var ctxCanvas = canvas.getContext("2d");

window.visualizer = new Oscilloscope(
  source,
  ctxCanvas,
  window.ctxAudio,
  options
);
