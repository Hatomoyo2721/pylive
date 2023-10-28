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

    this.ctxCanvas = ctxCanvas;
    this.ctxAudio = ctxAudio;
    this.timeDomain = new Uint8Array(this.analyser.fftSize);
    this.drawRequest = 0;
    this.isEnable = false;
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
    self,
    ctx,
    x0 = 0,
    y0 = 0,
    width = ctx.canvas.width - x0,
    height = ctx.canvas.height - y0
  ) {
    var bufferLength = self.analyser.frequencyBinCount;
    var dataArray = new Float32Array(bufferLength);
    self.analyser.getFloatFrequencyData(dataArray);

    var barWidth = (width / bufferLength) * 4;
	var barHeight;
	let posX = 0;
	for (let i = 0; i < bufferLength; i++) {
		barHeight = (dataArray[i] + ((i <= 3) ? 30 : ( (i <= 14) ? 45 : 50))) * 8;
		ctx.fillStyle = "green";

		ctx.fillRect(posX, height - barHeight/2, barWidth, barHeight/2);
		posX += barWidth + 1;
	}
  }

  drawOsc(
    self,
    ctx,
    x0 = 0,
    y0 = 0,
    width = ctx.canvas.width - x0,
    height = ctx.canvas.height - y0
  ) {
    self.analyser.getByteTimeDomainData(self.timeDomain);
    const step = width / self.timeDomain.length;

    ctx.beginPath();
    // drawing loop (skipping every second record)
    for (let i = 0; i < self.timeDomain.length; i += 8) {
      const percent = self.timeDomain[i] / 256;
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
    var _map = {
      oscilloscope: this.drawOsc,
      bars: this.drawBars,
    }

    _map[this.type](this, ctx, x0, y0, width, height)
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

