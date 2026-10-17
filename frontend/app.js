// Kithora frontend: mic -> AudioWorklet (16 kHz Int16) -> WebSocket -> live captions.

const TARGET_SAMPLE_RATE = 16000;
const CHUNK_MS = 100;
const MAX_SEGMENTS = 200;
const FLUSH_TIMEOUT_MS = 500;
const DONE_TIMEOUT_MS = 5000;
const LANG_LABELS = { km: "KM", en: "EN", mixed: "MIX" };

const toggleBtn = document.getElementById("toggle");
const statusEl = document.getElementById("status");
const statusText = statusEl.querySelector(".status__text");
const captionsEl = document.getElementById("captions");
const errorEl = document.getElementById("error");

// phase: "idle" | "starting" | "live" | "stopping"
const state = {
  phase: "idle",
  ws: null,
  stream: null,
  audioContext: null,
  source: null,
  worklet: null,
  sink: null,
  flushResolve: null,
  doneTimer: null,
};

/** segment_id -> { el, badge, text } */
const segments = new Map();

// ---------------------------------------------------------------- UI helpers

function setStatus(kind, text) {
  statusEl.dataset.state = kind;
  statusText.textContent = text;
}

function showError(message) {
  errorEl.textContent = message || "";
  errorEl.hidden = !message;
}

function updateButton() {
  const live = state.phase === "live" || state.phase === "stopping";
  toggleBtn.textContent = live ? "Stop" : "Start";
  toggleBtn.classList.toggle("btn--stop", live);
  toggleBtn.disabled = state.phase === "starting" || state.phase === "stopping";
}

function describeError(err) {
  if (err && err.name === "NotAllowedError") return "Microphone permission was denied.";
  if (err && err.name === "NotFoundError") return "No microphone was found.";
  return (err && err.message) || String(err);
}

function formatMs(ms) {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = String(total % 60).padStart(2, "0");
  return `${m}:${s}`;
}

// ---------------------------------------------------------------- captions

function renderCaption(event) {
  const lang = Object.prototype.hasOwnProperty.call(LANG_LABELS, event.lang) ? event.lang : "mixed";
  const nearBottom =
    captionsEl.scrollHeight - captionsEl.scrollTop - captionsEl.clientHeight < 48;

  let seg = segments.get(event.segment_id);
  if (!seg) {
    const el = document.createElement("p");
    el.className = "segment";
    const badge = document.createElement("span");
    const text = document.createElement("span");
    text.className = "segment__text";
    el.append(badge, text);
    captionsEl.append(el);
    seg = { el, badge, text };
    segments.set(event.segment_id, seg);
    pruneSegments();
  }

  seg.text.textContent = event.text;
  seg.badge.textContent = LANG_LABELS[lang];
  seg.badge.className = `badge badge--${lang}`;
  seg.el.classList.toggle("segment--partial", !event.is_final);
  seg.el.classList.toggle("segment--final", Boolean(event.is_final));
  // A precise lang attribute helps the browser pick Khmer glyphs/shaping.
  if (lang === "mixed") seg.el.removeAttribute("lang");
  else seg.el.lang = lang;
  seg.el.title = `${formatMs(event.start_ms)} – ${formatMs(event.end_ms)}`;

  if (nearBottom) captionsEl.scrollTop = captionsEl.scrollHeight;
}

function pruneSegments() {
  while (segments.size > MAX_SEGMENTS) {
    const [oldestId, oldest] = segments.entries().next().value;
    oldest.el.remove();
    segments.delete(oldestId);
  }
}

// ---------------------------------------------------------------- WebSocket

function socketUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/captions`;
}

function openSocket() {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(socketUrl());
    ws.binaryType = "arraybuffer";
    const cleanup = () => {
      ws.removeEventListener("open", onOpen);
      ws.removeEventListener("error", onFail);
      ws.removeEventListener("close", onFail);
    };
    const onOpen = () => {
      cleanup();
      resolve(ws);
    };
    const onFail = () => {
      cleanup();
      reject(new Error("Could not connect to the caption server."));
    };
    ws.addEventListener("open", onOpen);
    ws.addEventListener("error", onFail);
    ws.addEventListener("close", onFail);
  });
}

function closeSocket() {
  const ws = state.ws;
  state.ws = null;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    ws.close(1000);
  }
}

function onSocketMessage(event) {
  if (typeof event.data !== "string") return;
  let msg;
  try {
    msg = JSON.parse(event.data);
  } catch {
    return;
  }
  switch (msg.type) {
    case "caption":
      renderCaption(msg);
      break;
    case "error":
      showError(`Server: ${msg.message}`);
      break;
    case "done":
      finishStopped();
      break;
    default:
      break;
  }
}

function onSocketClose(event) {
  if (event.target !== state.ws) return; // a socket we already let go of
  state.ws = null;
  if (state.phase === "stopping") {
    finishStopped();
  } else if (state.phase === "live" || state.phase === "starting") {
    teardownAudio();
    state.phase = "idle";
    setStatus("error", "Disconnected");
    showError("Connection to the caption server was lost.");
    updateButton();
  }
}

// ---------------------------------------------------------------- audio

async function startAudio(ws) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  state.stream = stream;

  // Use the device's native rate; the worklet downsamples to 16 kHz.
  const ctx = new AudioContext();
  state.audioContext = ctx;
  await ctx.audioWorklet.addModule("pcm-worklet.js");

  const source = ctx.createMediaStreamSource(stream);
  const worklet = new AudioWorkletNode(ctx, "pcm-downsampler", {
    numberOfInputs: 1,
    numberOfOutputs: 1,
    channelCount: 1,
    channelCountMode: "explicit",
    processorOptions: { targetSampleRate: TARGET_SAMPLE_RATE, chunkMs: CHUNK_MS },
  });
  // Route through a muted gain to the destination so the graph keeps pulling
  // audio through the worklet in every browser, without audible playback.
  const sink = ctx.createGain();
  sink.gain.value = 0;

  worklet.port.onmessage = (event) => {
    const data = event.data;
    if (data instanceof ArrayBuffer) {
      if (ws.readyState === WebSocket.OPEN) ws.send(data);
    } else if (data && data.type === "flushed" && state.flushResolve) {
      state.flushResolve();
    }
  };

  source.connect(worklet);
  worklet.connect(sink);
  sink.connect(ctx.destination);
  Object.assign(state, { source, worklet, sink });

  if (ctx.state === "suspended") await ctx.resume();
}

function flushWorklet() {
  const node = state.worklet;
  if (!node) return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer);
      state.flushResolve = null;
      resolve();
    };
    const timer = setTimeout(done, FLUSH_TIMEOUT_MS);
    state.flushResolve = done;
    node.port.postMessage({ type: "flush" });
  });
}

function teardownAudio() {
  const { stream, audioContext, source, worklet, sink } = state;
  if (worklet) {
    worklet.port.onmessage = null;
    worklet.port.postMessage({ type: "stop" });
  }
  for (const node of [source, worklet, sink]) {
    if (node) {
      try {
        node.disconnect();
      } catch {
        /* already disconnected */
      }
    }
  }
  if (stream) stream.getTracks().forEach((track) => track.stop());
  if (audioContext && audioContext.state !== "closed") audioContext.close().catch(() => {});
  Object.assign(state, { stream: null, audioContext: null, source: null, worklet: null, sink: null });
}

// ---------------------------------------------------------------- start / stop

async function start() {
  if (state.phase !== "idle") return;
  showError("");
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showError("Microphone access needs a secure page (https:// or http://localhost).");
    return;
  }

  state.phase = "starting";
  updateButton();
  setStatus("connecting", "Connecting…");
  try {
    const ws = await openSocket();
    state.ws = ws;
    ws.addEventListener("message", onSocketMessage);
    ws.addEventListener("close", onSocketClose);
    await startAudio(ws);
    if (state.phase !== "starting") {
      teardownAudio(); // socket dropped while the mic was starting
      return;
    }
    state.phase = "live";
    setStatus("live", "Live — listening");
  } catch (err) {
    teardownAudio();
    closeSocket();
    state.phase = "idle";
    setStatus("error", "Error");
    showError(describeError(err));
  }
  updateButton();
}

async function stop() {
  if (state.phase !== "live") return;
  state.phase = "stopping";
  updateButton();
  setStatus("stopping", "Finishing…");

  await flushWorklet(); // send the last partial chunk of audio
  teardownAudio();

  const ws = state.ws;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "stop" }));
    // Server flushes remaining captions, sends {"type":"done"}, then closes.
    state.doneTimer = setTimeout(finishStopped, DONE_TIMEOUT_MS);
  } else {
    finishStopped();
  }
}

function finishStopped() {
  clearTimeout(state.doneTimer);
  state.doneTimer = null;
  closeSocket();
  teardownAudio();
  state.phase = "idle";
  setStatus("idle", "Stopped");
  updateButton();
}

toggleBtn.addEventListener("click", () => {
  if (state.phase === "idle") start();
  else if (state.phase === "live") stop();
});

window.addEventListener("pagehide", () => {
  teardownAudio();
  closeSocket();
});

updateButton();
