import Oscilloscope from "./dist/oscilloscope.js";

var ctxAudio = new window.AudioContext();

var audioElement = document.getElementById("main-player");
var source = ctxAudio.createMediaElementSource(audioElement);
var options = {
  stroke: 1, // size of the wave
  fftSize: 4096, // size ranging from 32 to any number that that is a power of 2
};
var canvas = document.getElementById("visualizer");
var ctxCanvas = canvas.getContext("2d");

window.visualizer = new Oscilloscope(source, ctxCanvas, ctxAudio, options);
