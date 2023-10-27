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

    if (options.fftSize) {
      this.analyser.fftSize = options.fftSize;
    }
    this.ctxCanvas = ctxCanvas;
    this.timeDomain = new Uint8Array(this.analyser.fftSize);
    this.drawRequest = 0;
    this.maxFPS = 24;
    this.isEnable = false;
  }

  // begin default signal animation
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

  // draw signal
  draw(
    ctx,
    x0 = 0,
    y0 = 0,
    width = ctx.canvas.width - x0,
    height = ctx.canvas.height - y0
  ) {
    this.analyser.getByteTimeDomainData(this.timeDomain);
    const step = width / this.timeDomain.length;

    ctx.beginPath();
    // drawing loop (skipping every second record)
    for (let i = 0; i < this.timeDomain.length; i += 8) {
      const percent = this.timeDomain[i] / 256;
      const x = x0 + i * step;
      const y = y0 + height * percent;
      ctx.lineTo(x, y);
    }

    ctx.stroke();
  }

  changefps(fps) {
    this.maxFPS = fps;
  }

  toggle() {
    if (this.isEnable) {
      this.stop();
    } else {
      this.animate();
    }
  }
}
