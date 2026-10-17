# Kithora backend

FastAPI + WebSocket server for real-time Khmer–English code-switching captions.
Right now it only ships a `DummyEngine` that emits fake captions, so the full
mic → WebSocket → caption loop can be developed and tested without a real ASR model.

## Layout

```
backend/
  kithora/
    app.py            FastAPI app: /ws/captions, /health, static frontend at /
    asr/
      base.py         AsrEngine (abstract) + CaptionEvent
      dummy.py        DummyEngine (fake mixed Khmer/English captions)
      factory.py      create_engine(), selected by KITHORA_ENGINE
      lang.py         script-based km / en / mixed tagger
  tests/
    test_dummy_ws.py
  requirements.txt
  pytest.ini
```

## Setup

All commands are run from the `backend/` directory.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

```bash
uvicorn kithora.app:app --reload --port 8000
```

Then open <http://localhost:8000/> and press **Start**. The frontend (`../frontend`)
is served at `/`. Microphone access only works on `http://localhost` or over HTTPS.

- `GET /health` → `{"status": "ok"}`
- `WS /ws/captions` → see the protocol below

### Choosing an engine

The engine is picked by the `KITHORA_ENGINE` environment variable (default `dummy`).
An unknown name makes the app fail at startup.

```powershell
$env:KITHORA_ENGINE = "dummy"; uvicorn kithora.app:app
```

New engines subclass `AsrEngine` in `kithora/asr/` and are registered in
`kithora/asr/factory.py`.

## WebSocket protocol (`/ws/captions`)

Client → server:

- **binary frames**: raw PCM, 16 kHz, mono, signed 16-bit little-endian (the frontend sends ~100 ms chunks).
- **text frame** `{"type": "stop"}`: end of audio.

Server → client (JSON text frames):

```json
{"type": "caption", "segment_id": 0, "text": "សួស្តី everyone", "is_final": false, "lang": "mixed", "start_ms": 0, "end_ms": 500}
{"type": "error", "message": "invalid JSON control message"}
{"type": "done"}
```

Partials for a `segment_id` replace each other; the event with `is_final: true` is the
last one for that segment. After `stop` the server flushes the remaining captions,
sends `{"type": "done"}`, and closes the socket.

## Tests

```bash
pytest
```

(or `python -m pytest`, with the venv active, from `backend/`).
