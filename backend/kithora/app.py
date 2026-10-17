"""FastAPI application: caption WebSocket, health check and static frontend.

Run from ``backend/``::

    uvicorn kithora.app:app --reload

WebSocket protocol (``/ws/captions``):

* client -> server, binary frame: raw PCM, 16 kHz mono signed 16-bit LE.
* client -> server, text frame ``{"type": "stop"}``: end of audio.
* server -> client, JSON text frames:
    - ``{"type": "caption", "segment_id", "text", "is_final", "lang", "start_ms", "end_ms"}``
    - ``{"type": "error", "message": "..."}`` (bad control message; stream continues)
    - ``{"type": "done"}`` after ``stop``, once all captions are flushed; then the
      server closes the socket.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from kithora import __version__
from kithora.asr import AsrEngine, create_engine, resolve_engine_name

logger = logging.getLogger("kithora")

# The Windows registry sometimes maps .js to text/plain, which makes browsers
# refuse module scripts and AudioWorklet modules. Force correct types.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app(engine_name: str | None = None, frontend_dir: Path | None = FRONTEND_DIR) -> FastAPI:
    """Build the app. ``engine_name`` defaults to ``$KITHORA_ENGINE`` or ``"dummy"``.

    The engine name is validated here so a typo fails at startup rather than on
    the first WebSocket connection.
    """
    resolved_engine = resolve_engine_name(engine_name)

    app = FastAPI(title="Kithora", version=__version__)
    app.state.engine_name = resolved_engine

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws/captions")
    async def captions(websocket: WebSocket) -> None:
        await _handle_caption_socket(websocket, resolved_engine)

    # Mounted last so the routes above take precedence over static files.
    if frontend_dir is not None and frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    else:
        logger.warning("Frontend directory %s not found; serving API only", frontend_dir)

    return app


async def _handle_caption_socket(websocket: WebSocket, engine_name: str) -> None:
    await websocket.accept()
    engine = create_engine(engine_name)
    sender: asyncio.Task[None] | None = None
    try:
        await engine.start()
        sender = asyncio.create_task(_pump_events(websocket, engine))
        client_gone = await _receive_audio(websocket, engine)
        await engine.finish()
        if client_gone:
            return
        await sender  # drains remaining captions
        await websocket.send_json({"type": "done"})
        await websocket.close()
    except WebSocketDisconnect:
        pass
    finally:
        await engine.finish()  # idempotent
        if sender is not None:
            if not sender.done():
                sender.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await sender


async def _pump_events(websocket: WebSocket, engine: AsrEngine) -> None:
    async for event in engine.events():
        await websocket.send_json({"type": "caption", **event.to_dict()})


async def _receive_audio(websocket: WebSocket, engine: AsrEngine) -> bool:
    """Feed incoming audio to ``engine``.

    Returns ``True`` if the client disconnected, ``False`` if it sent ``stop``.
    """
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return True

        data = message.get("bytes")
        if data is not None:
            if data:
                await engine.feed_audio(data)
            continue

        text = message.get("text")
        if text is None:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            await _send_error(websocket, "invalid JSON control message")
            continue
        if isinstance(payload, dict) and payload.get("type") == "stop":
            return False
        await _send_error(websocket, 'unknown control message; expected {"type": "stop"}')


async def _send_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_json({"type": "error", "message": message})


app = create_app()
