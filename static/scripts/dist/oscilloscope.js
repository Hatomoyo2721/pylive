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
    this.maxFPS = options.maxFPS || 24;
    this.type = options.type || "bars";
    this.thickness = options.stroke || 1;

    this.ctxCanvas = ctxCanvas;
    this.ctxAudio = ctxAudio;
    this.isEnable = false;

    // mapping function
    this.mapDrawfn = {
      bars: this.drawBars,
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
      barHeight = (dataArray[i] + (i <= 3 ? 30 : i <= 14 ? 45 : 50)) * 4;
      ctx.fillStyle = "green";

      // ctx.fillRect(posX, height - barHeight / 2, barWidth, barHeight / 2);
      ctx.beginPath();
      ctx.moveTo(posX, height);
      ctx.lineTo(posX, height - barHeight);
      ctx.lineTo(posX + barWidth, height - barHeight);
      ctx.lineTo(posX + barWidth, height);
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
    // drawing loop (skipping every second record)
    for (let i = 0; i < bufferLength; i += 8) {
      const percent = dataArray[i] / 256;
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
    if (["bars", "oscilloscope"].indexOf(type) === -1) {
      return;
    }
    this.type = type;
  }

  changeFPS(fps) {
    this.maxFPS = fps;
  }

  changeSize(width, height) {
    this.ctxCanvas.canvas.width = width;
    this.ctxCanvas.canvas.height = height;
  }

  changeThickness(v) {
    this.thickness = v;
  }

  changeSensitivity(v) {
    if (v >= 0 && v <= 1) {
      this.analyser.smoothingTimeConstant = v;
    }
  }

  toggle() {
    if (this.isEnable) {
      this.stop();
    } else {
      this.animate();
    }
  }
}
