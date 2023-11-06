export default class Oscilloscope {
  constructor(source, ctxCanvas, ctxAudio, options = {}) {
    if (!(source instanceof window.AudioNode)) {
      throw new Error("Oscilloscope source must be an AudioNode");
    }

    if (source instanceof window.AnalyserNode) {
      this.analyser = source;
    } else {
      this.analyser = source.context.createAnalyser();
      source.connect(this.analyser);
    }

    source.connect(ctxAudio.destination);

    this.analyser.fftSize = options.fftSize || 1024;
    this.analyser.smoothingTimeConstant = options.sensitivity || 0.6;
    this.analyser.minDecibels = options.minDecibels || -100;
    this.analyser.maxDecibels = options.minDecibels || -30;
    this.color = options.color || "black";
    this.maxFPS = options.maxFPS || 48;
    this.multiplier = options.multiplier || 1;
    this.type = options.type || "bars";
    this.thickness = options.stroke || 1;
    this.XOffset = options.XOffset || 0;
    this.YOffset = options.YOffset || 0;

    this.ctxCanvas = ctxCanvas;
    this.ctxAudio = ctxAudio;
    this.isEnable = false;

    // mapping function
    this.mapDrawfn = {
      bars: this.testdrawBars,
      oscilloscope: this.drawOsc,
    };
  }

  animate(x0, y0, width, height) {
    if (this.isEnable) {
      throw new Error("Oscilloscope animation is already running");
    }
    this.isEnable = true;

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    const drawLoop = () => {
      sleep(1000 / this.maxFPS).then(() => {
        if (!this.isEnable) {
          return;
        }
        this.ctxCanvas.clearRect(
          0,
          0,
          this.ctxCanvas.canvas.width,
          this.ctxCanvas.canvas.height
        );
        this.draw(this.ctxCanvas, x0, y0, width, height);
        window.requestAnimationFrame(drawLoop);
      });
    };
    drawLoop();
  }

  // stop default signal animation
  stop() {
    if (this.isEnable) {
      this.isEnable = false;
      // window.cancelAnimationFrame(this.drawRequest);
      this.ctxCanvas.clearRect(
        0,
        0,
        this.ctxCanvas.canvas.width,
        this.ctxCanvas.canvas.height
      );
    }
  }

  drawBars(
    ctx,
    x0 = 0,
    y0 = 0,
    width = ctx.canvas.width - x0,
    height = ctx.canvas.height - y0
  ) {
    var bufferLength = this.analyser.frequencyBinCount;
    var dataArray = new Float32Array(bufferLength);
    this.analyser.getFloatFrequencyData(dataArray);

    var barWidth = (width / bufferLength) * this.thickness;
    var barHeight;
    let posX = 0;
    for (let i = 0; i < bufferLength; i++) {
      barHeight =
        (dataArray[i] + (i <= 3 ? 30 : i <= 14 ? 45 : 50)) *
        6 *
        this.multiplier;
      ctx.fillStyle = this.color;

      ctx.fillRect(posX, height - barHeight, barWidth, barHeight);
      ctx.fill();
      posX += barWidth + 1;
    }
  }

  testdrawBars(
    ctx,
    x0 = 0,
    y0 = 0,
    width = ctx.canvas.width - x0,
    height = ctx.canvas.height - y0
  ) {
    var bufferLength = this.analyser.frequencyBinCount;
    var dataArray = new Uint8Array(this.analyser.fftSize);
    this.analyser.getByteFrequencyData(dataArray);

    var barWidth = (width / bufferLength) * this.thickness;
    let posX = 0;
    var barHeight;
    for (let i = 0; i < bufferLength; i++) {
      ctx.fillStyle = this.color;
      barHeight =
        (dataArray[i] / height) *
        (i <= 6 ? 8 : i <= 14 ? 12 : 16) *
        this.multiplier;

      ctx.fillRect(posX, height - barHeight + this.YOffset, barWidth, barHeight);
      ctx.fill();
      posX += barWidth + 1;
    }
  }

  drawOsc(
    ctx,
    x0 = 0,
    y0 = 0,
    width = ctx.canvas.width - x0,
    height = ctx.canvas.height - y0
  ) {
    var bufferLength = this.analyser.frequencyBinCount;
    var dataArray = new Uint8Array(this.analyser.fftSize);
    this.analyser.getByteTimeDomainData(dataArray);
    const step = width / bufferLength;

    ctx.beginPath();
    ctx.lineWidth = this.thickness;
    ctx.strokeStyle = this.color;
    // drawing loop (skipping every second record)
    for (let i = 0; i < bufferLength; i += 4) {
      // i += n, n higher == less detail
      const percent = dataArray[i] / (256 / this.multiplier);
      const x = x0 + i * step;
      const y = y0 + height * percent;
      ctx.lineTo(x, y);
    }

    ctx.stroke();
  }

  // draw signal
  draw(
    ctx,
    x0 = 0,
    y0 = 0,
    width = ctx.canvas.width - x0,
    height = ctx.canvas.height - y0
  ) {
    this.mapDrawfn[this.type].call(this, ctx, x0, y0, width, height);
  }

  changeType(type) {
    type = type.toLowerCase()
    if (["bars", "oscilloscope"].indexOf(type) === -1) {
      return;
    }
    var prevType = this.type;
    this.type = type;
    this.stop();
    this.animate();
    if (prevType == "oscilloscope") {
      this.ctxCanvas.beginPath();
      this.ctxCanvas.stroke();
    }
  }

  changeFPS(fps) {
    this.maxFPS = fps;
  }

  changeSize(width, height) {
    this.ctxCanvas.canvas.width = width;
    this.ctxCanvas.canvas.height = height;
  }

  changeThickness(v) {
    if (v == "") v = 1;
    this.thickness = v;
  }

  changeColor(v) {
    if (v == "") v = "black";
    this.color = v;
  }

  changeSensitivity(v) {
    if (v == "") v = 0.6;
    if (v >= 0 && v <= 1) {
      this.analyser.smoothingTimeConstant = v;
    }
  }

  changeMultiply(v) {
    if (v == "") v = 1;
    this.multiplier = v;
  }

  changeminDecibels(v) {
    if (v == "") v = -100;
    this.analyser.minDecibels = v;
  }

  changemaxDecibels(v) {
    if (v == "") v = -30;
    this.analyser.maxDecibels = v;
  }

  toggle() {
    if (this.isEnable) {
      this.stop();
    } else {
      this.animate();
    }
  }
}
