"""Health, recorded-audio transcription, and real-time streaming over WebSocket."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from starlette.datastructures import UploadFile

from ..adapters.base import ADAPTERS, AudioInputPayload, SpeechEngineAdapter
from ..audio import sniff_audio_mime
from ..config import settings
from ..db import Session, SessionLocal, UsageRecord, get_db
from ..security import (
    Caller,
    KethraError,
    authenticate,
    check_rate_limit,
    close_stream,
    consume_stream_token,
    issue_stream_token,
    new_id,
    open_stream,
    verify_api_key,
)
from ..services.normalizer import normalize_khmer_english_transcript

router = APIRouter(prefix="/v1", tags=["speech"])
log = logging.getLogger("kethra")

SUPPORTED_FORMATS = "WAV, MP3, WebM, OGG, M4A/MP4, FLAC"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_engine(engine_id: str | None) -> SpeechEngineAdapter:
    adapter = ADAPTERS.get(engine_id or settings.kethra_default_engine)
    if adapter is None:
        raise KethraError(400, "unsupported_engine", f"Unknown engine_id. Available: {list(ADAPTERS)}")
    if not adapter.is_configured():
        raise KethraError(503, "engine_not_configured", f"{adapter.engine_id} is not configured on this server.")
    return adapter


def parse_vocabulary(hint: object) -> list[str]:
    """Comma-separated words the engine should expect, e.g. 'GitHub, deploy'."""
    if not isinstance(hint, str):
        return []
    return [t.strip()[:50] for t in hint.split(",") if t.strip()][:100]


def record_usage(db: Session, caller: Caller, endpoint: str, engine_id: str, is_mock: bool,
                 status: int, audio_bytes: int, latency_ms: int, code_switched: bool = False) -> None:
    db.add(UsageRecord(
        user_id=caller.user_id, api_key_id=caller.api_key_id, endpoint=endpoint, engine_id=engine_id,
        is_mock=is_mock, status_code=status, audio_bytes=audio_bytes, latency_ms=latency_ms,
        code_switched_detected=code_switched,
    ))
    db.commit()


async def transcribe(adapter: SpeechEngineAdapter, audio: bytes, vocabulary: list[str]):
    mime = sniff_audio_mime(audio)
    if mime is None:
        raise KethraError(415, "unsupported_media_type", f"Not a recognised audio file. Supported: {SUPPORTED_FORMATS}.")
    try:
        output = await asyncio.wait_for(adapter.transcribe_audio(AudioInputPayload(audio, mime, vocabulary)),
                                        timeout=settings.kethra_engine_timeout_seconds)
    except TimeoutError:
        raise KethraError(504, "speech_engine_timeout", "The speech engine took too long. Try again.", retryable=True)
    except Exception:
        # Log server-side only; provider errors can contain request details.
        log.exception("speech engine %s failed", adapter.engine_id)
        raise KethraError(502, "speech_engine_error", "The speech engine failed. Try again.", retryable=True)
    return mime, output, normalize_khmer_english_transcript(output.raw_transcript)


@router.get("/health", tags=["meta"])
def health():
    return {
        "status": "healthy",
        "service": "kethra-api",
        "default_engine": settings.kethra_default_engine,
        "engines": [
            {"engine_id": a.engine_id, "display_name": a.display_name, "is_mock": a.is_mock,
             "configured": a.is_configured()}
            for a in ADAPTERS.values()
        ],
    }


@router.post(
    "/transcriptions",
    openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object",
        "required": ["file"],
        "properties": {
            "file": {"type": "string", "format": "binary", "description": f"Audio file ({SUPPORTED_FORMATS})."},
            "engine_id": {"type": "string", "description": "Optional. Defaults to the server's engine."},
            "prompt_hint": {"type": "string", "description": "Optional comma-separated vocabulary, e.g. 'GitHub, deploy'."},
        },
    }}}}},
)
async def create_transcription(request: Request, db: Session = Depends(get_db)):
    """Transcribe one recorded audio file. Auth: `Authorization: Bearer <api key>` (scope transcriptions:write)."""
    # Auth and size checks happen before the body is parsed.
    caller = authenticate(db, request, "transcriptions:write")
    check_rate_limit(f"speech:{caller.user_id}")
    max_bytes = settings.kethra_max_upload_bytes
    if int(request.headers.get("content-length") or 0) > max_bytes + 64 * 1024:
        raise KethraError(413, "payload_too_large", f"Audio exceeds {max_bytes // (1024 * 1024)} MB.")

    engine_id, size, started = "unknown", 0, time.perf_counter()
    try:
        form = await request.form(max_files=1, max_fields=5)
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise KethraError(400, "missing_audio", 'Multipart field "file" is required.')
        audio = await upload.read(max_bytes + 1)
        size = len(audio)
        if size > max_bytes:
            raise KethraError(413, "payload_too_large", f"Audio exceeds {max_bytes // (1024 * 1024)} MB.")
        if size == 0:
            raise KethraError(400, "empty_audio", "The uploaded file is empty.")
        adapter = resolve_engine(form.get("engine_id") or None)
        engine_id = adapter.engine_id
        mime, output, norm = await transcribe(adapter, audio, parse_vocabulary(form.get("prompt_hint")))
    except KethraError as e:
        record_usage(db, caller, "/v1/transcriptions", engine_id, engine_id == "mock-deterministic", e.status,
                     size, int((time.perf_counter() - started) * 1000))
        raise

    record_usage(db, caller, "/v1/transcriptions", output.engine_id, output.is_mock_engine, 200, size,
                 output.latency_ms, norm.is_code_switched)
    # Audio bytes are dropped when this function returns; nothing is written to disk by Kethra.
    return {
        "id": f"tr_{secrets.token_hex(8)}",
        "object": "transcription",
        "created_at": now_iso(),
        "status": "completed",
        "engine_id": output.engine_id,
        "is_mock_engine": output.is_mock_engine,
        "audio_metadata": {"filename": upload.filename or "audio", "mime_type": mime, "size_bytes": size},
        "raw_transcript": output.raw_transcript,
        "normalized_transcript": norm.normalized_text,
        "normalization": norm.to_dict(),
        "processing_latency_ms": output.latency_ms,
        "retention_policy": "zero-retention",
        "warnings": output.warnings,
    }


@router.post("/auth/session-token", status_code=201)
def session_token(request: Request, db: Session = Depends(get_db)):
    """Swap an API key (on your server) for a 5-minute, single-use token a browser or phone can use on /v1/listen."""
    caller = authenticate(db, request, "stream:listen")
    check_rate_limit(f"speech:{caller.user_id}")
    return issue_stream_token(caller)


def _error_event(session_id: str, e: KethraError) -> dict:
    return {"type": "error", "session_id": session_id, "timestamp": now_iso(),
            "error": {"code": e.code, "message": e.message, "retryable": e.retryable}}


@router.websocket("/listen")
async def listen(ws: WebSocket):
    """Protocol is documented in the README (session.init, audio.chunk, session.complete)."""
    await ws.accept()
    with SessionLocal() as db:
        try:
            token = ws.query_params.get("token")
            auth = ws.headers.get("authorization", "")
            if token:
                caller, session_id = consume_stream_token(db, token)
            elif auth.lower().startswith("bearer "):  # server-to-server clients
                key = verify_api_key(db, auth[7:].strip(), "stream:listen")
                caller, session_id = Caller(key.user_id, key.id), new_id("sess")
            else:
                raise KethraError(401, "unauthorized_stream", "Connect with ?token=<session token> from POST /v1/auth/session-token.")
            adapter = resolve_engine(ws.query_params.get("engine_id"))
            open_stream(caller.user_id)
        except KethraError as e:
            await ws.send_json(_error_event("unauthenticated", e))
            await ws.close(1008)
            return
        try:
            await _run_stream(ws, db, caller, session_id, adapter)
        except WebSocketDisconnect:
            pass
        finally:
            close_stream(caller.user_id)


async def _run_stream(ws: WebSocket, db: Session, caller: Caller, session_id: str, adapter: SpeechEngineAdapter):
    vocabulary: list[str] = []
    sequence = 0
    deadline = time.monotonic() + settings.kethra_ws_session_timeout_seconds
    max_b64 = settings.kethra_max_ws_chunk_bytes * 4 // 3 + 4
    await ws.send_json({"type": "session.started", "session_id": session_id, "engine_id": adapter.engine_id,
                        "is_mock_engine": adapter.is_mock, "timestamp": now_iso()})

    while True:
        remaining = deadline - time.monotonic()
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=max(0.0, min(remaining, settings.kethra_ws_idle_timeout_seconds)))
        except TimeoutError:
            reason = "session_timeout" if remaining <= settings.kethra_ws_idle_timeout_seconds else "idle_timeout"
            await ws.send_json(_error_event(session_id, KethraError(408, reason, "Session closed: time limit reached.")))
            await ws.close(1000)
            return

        try:
            if len(raw) > max_b64 + 1024:
                raise KethraError(413, "payload_too_large", "Audio chunk is too large.")
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                raise KethraError(400, "invalid_message", "Messages must be JSON.")
            kind = msg.get("type") if isinstance(msg, dict) else None

            if kind == "session.init":
                if msg.get("engine_id"):
                    adapter = resolve_engine(msg["engine_id"])
                vocabulary = parse_vocabulary(msg.get("prompt_hint"))
            elif kind == "audio.chunk":
                try:
                    audio = base64.b64decode(msg.get("audio_base64") or "", validate=True)
                except (binascii.Error, TypeError):
                    raise KethraError(400, "invalid_audio", "audio_base64 is not valid base64.")
                if not audio:
                    raise KethraError(400, "empty_audio", "Audio chunk is empty.")
                check_rate_limit(f"speech:{caller.user_id}")
                sequence += 1
                try:
                    _, output, norm = await transcribe(adapter, audio, vocabulary)
                except KethraError as e:
                    record_usage(db, caller, "/v1/listen", adapter.engine_id, adapter.is_mock, e.status, len(audio), 0)
                    raise
                record_usage(db, caller, "/v1/listen", output.engine_id, output.is_mock_engine, 200, len(audio),
                             output.latency_ms, norm.is_code_switched)
                is_final = msg.get("is_final", True) is not False
                await ws.send_json({
                    "type": "transcript.final" if is_final else "transcript.partial",
                    "session_id": session_id, "sequence": sequence, "is_final": is_final,
                    "text": norm.normalized_text, "raw_text": output.raw_transcript,
                    "engine_id": output.engine_id, "is_mock_engine": output.is_mock_engine,
                    "latency_ms": output.latency_ms, "normalization": norm.to_dict(),
                    "warnings": output.warnings, "timestamp": now_iso(),
                })
            elif kind == "session.complete":
                await ws.send_json({"type": "session.completed", "session_id": session_id, "timestamp": now_iso()})
                await ws.close(1000)
                return
            else:
                raise KethraError(400, "unknown_message_type", "type must be session.init, audio.chunk or session.complete.")
        except KethraError as e:
            await ws.send_json(_error_event(session_id, e))
