/*
 * AudioWorklet processor: mono downmix -> downsample to 16 kHz -> Int16 LE chunks.
 *
 * Posts an ArrayBuffer (transferred) to the main thread every `chunkMs`
 * milliseconds of 16 kHz audio (default 100 ms = 1600 samples = 3200 bytes).
 *
 * Messages from the main thread:
 *   {type: "flush"} -> post any partially filled chunk, then {type: "flushed"}
 *   {type: "stop"}  -> post any partial chunk and stop processing
 *
 * Downsampling uses a box filter (average of the input samples that fall into
 * each output sample). That is a crude anti-alias filter, but adequate for
 * speech and keeps the worklet tiny. If the device rate is below the target,
 * samples are repeated (zero-order hold).
 */

const DEFAULT_TARGET_RATE = 16000;
const DEFAULT_CHUNK_MS = 100;

class PcmDownsamplerProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    this.targetRate = opts.targetSampleRate || DEFAULT_TARGET_RATE;
    const chunkMs = opts.chunkMs || DEFAULT_CHUNK_MS;
    this.chunkSamples = Math.max(1, Math.round((this.targetRate * chunkMs) / 1000));

    // `sampleRate` is a global in AudioWorkletGlobalScope (the context rate).
    this.ratio = sampleRate / this.targetRate; // input samples per output sample
    this.phase = 0;
    this.acc = 0;
    this.accCount = 0;
    this.active = true;
    this.newChunk();

    this.port.onmessage = (event) => {
      const type = event.data && event.data.type;
      if (type === "flush") {
        this.flush();
        this.port.postMessage({ type: "flushed" });
      } else if (type === "stop") {
        this.flush();
        this.active = false;
      }
    };
  }

  newChunk() {
    this.chunk = new ArrayBuffer(this.chunkSamples * 2);
    this.view = new DataView(this.chunk);
    this.chunkIndex = 0;
  }

  pushSample(value) {
    const s = value > 1 ? 1 : value < -1 ? -1 : value;
    // DataView guarantees little-endian regardless of platform.
    this.view.setInt16(this.chunkIndex * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    this.chunkIndex += 1;
    if (this.chunkIndex >= this.chunkSamples) {
      const full = this.chunk;
      this.newChunk();
      this.port.postMessage(full, [full]);
    }
  }

  flush() {
    if (this.chunkIndex === 0) return;
    const part = this.chunk.slice(0, this.chunkIndex * 2);
    this.newChunk();
    this.port.postMessage(part, [part]);
  }

  process(inputs) {
    if (!this.active) return false;
    const input = inputs[0];
    if (!input || input.length === 0) return true;

    const channels = input.length;
    const frames = input[0].length;
    for (let i = 0; i < frames; i++) {
      let sample = 0;
      for (let c = 0; c < channels; c++) sample += input[c][i];
      sample /= channels;

      this.acc += sample;
      this.accCount += 1;
      this.phase += 1;
      if (this.phase >= this.ratio) {
        const avg = this.acc / this.accCount;
        while (this.phase >= this.ratio) {
          this.pushSample(avg);
          this.phase -= this.ratio;
        }
        this.acc = 0;
        this.accCount = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-downsampler", PcmDownsamplerProcessor);
