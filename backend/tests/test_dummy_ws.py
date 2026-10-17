"""Tests for DummyEngine and the /ws/captions WebSocket roundtrip."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from kithora.app import create_app
from kithora.asr import ENGINE_ENV_VAR, CaptionEvent, create_engine, resolve_engine_name
from kithora.asr.base import SAMPLE_RATE, SAMPLE_WIDTH_BYTES
from kithora.asr.dummy import DEFAULT_PHRASES, DummyEngine
from kithora.asr.lang import detect_lang

CAPTION_KEYS = {"type", "segment_id", "text", "is_final", "lang", "start_ms", "end_ms"}


def silence(ms: int) -> bytes:
    """``ms`` milliseconds of 16 kHz mono s16le silence."""
    return b"\x00" * (SAMPLE_RATE * ms // 1000 * SAMPLE_WIDTH_BYTES)


async def _collect(engine: DummyEngine, chunks: list[bytes]) -> list[CaptionEvent]:
    await engine.start()
    collected: list[CaptionEvent] = []

    async def consume() -> None:
        async for event in engine.events():
            collected.append(event)

    consumer = asyncio.create_task(consume())
    for chunk in chunks:
        await engine.feed_audio(chunk)
    await engine.finish()
    await asyncio.wait_for(consumer, timeout=5)
    return collected


def run_engine(engine: DummyEngine, chunks: list[bytes]) -> list[CaptionEvent]:
    return asyncio.run(_collect(engine, chunks))


# -- CaptionEvent / lang ---------------------------------------------------


def test_caption_event_to_dict_is_json_serialisable() -> None:
    event = CaptionEvent(segment_id=3, text="សួស្តី AI", is_final=True, lang="mixed", start_ms=0, end_ms=500)
    data = event.to_dict()
    assert data == {
        "segment_id": 3,
        "text": "សួស្តី AI",
        "is_final": True,
        "lang": "mixed",
        "start_ms": 0,
        "end_ms": 500,
    }
    assert json.loads(json.dumps(data, ensure_ascii=False)) == data


def test_caption_event_rejects_bad_lang() -> None:
    with pytest.raises(ValueError):
        CaptionEvent(segment_id=0, text="x", is_final=False, lang="fr", start_ms=0, end_ms=0)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("សូមអរគុណ សម្រាប់ការស្តាប់", "km"),
        ("Let's start the meeting now", "en"),
        ("សួស្តី everyone", "mixed"),
        ("123 ...", "en"),
    ],
)
def test_detect_lang(text: str, expected: str) -> None:
    assert detect_lang(text) == expected


# -- DummyEngine -----------------------------------------------------------


def test_dummy_emits_growing_partials_then_final() -> None:
    phrase = DEFAULT_PHRASES[0]
    words = phrase.split()
    engine = DummyEngine(ms_per_word=250, gap_ms=500)

    # Exactly enough audio for the first phrase, in 100 ms chunks.
    total_ms = 250 * len(words)
    events = run_engine(engine, [silence(100)] * (total_ms // 100))

    assert len(events) == len(words)
    assert all(e.segment_id == 0 for e in events)
    assert [e.is_final for e in events] == [False] * (len(words) - 1) + [True]
    for i, event in enumerate(events, start=1):
        assert event.text == " ".join(words[:i])
        assert event.lang in {"km", "en", "mixed"}
        assert event.start_ms == 0
    assert [e.end_ms for e in events] == sorted(e.end_ms for e in events)
    assert events[-1].text == phrase
    assert events[-1].lang == "mixed"


def test_dummy_cycles_through_phrases() -> None:
    engine = DummyEngine(phrases=["hello world", "សួស្តី world"], ms_per_word=100, gap_ms=0)
    events = run_engine(engine, [silence(1000)])

    finals = [e for e in events if e.is_final]
    assert [e.segment_id for e in finals] == [0, 1, 2, 3, 4]
    assert [e.text for e in finals] == ["hello world", "សួស្តី world"] * 2 + ["hello world"]
    assert [e.lang for e in finals] == ["en", "mixed"] * 2 + ["en"]
    # Every segment gets exactly one final, after its partials.
    for seg_id in range(5):
        seg = [e for e in events if e.segment_id == seg_id]
        assert [e.is_final for e in seg] == [False, True]


def test_dummy_finish_finalises_pending_partial() -> None:
    engine = DummyEngine(ms_per_word=250)
    events = run_engine(engine, [silence(300)])

    assert len(events) == 2
    partial, final = events
    assert not partial.is_final and final.is_final
    assert partial.segment_id == final.segment_id == 0
    assert final.text == partial.text == DEFAULT_PHRASES[0].split()[0]
    assert final.end_ms == 300


def test_dummy_handles_odd_sized_chunks() -> None:
    audio = silence(1000)
    even = run_engine(DummyEngine(), [audio])
    odd = run_engine(DummyEngine(), [audio[i : i + 333] for i in range(0, len(audio), 333)])
    assert odd == even


def test_dummy_requires_start() -> None:
    engine = DummyEngine()
    with pytest.raises(RuntimeError):
        asyncio.run(engine.feed_audio(silence(100)))


# -- factory ---------------------------------------------------------------


def test_factory_defaults_to_dummy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENGINE_ENV_VAR, raising=False)
    assert resolve_engine_name() == "dummy"
    assert isinstance(create_engine(), DummyEngine)


def test_factory_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENGINE_ENV_VAR, "  DUMMY ")
    assert isinstance(create_engine(), DummyEngine)


def test_factory_rejects_unknown_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENGINE_ENV_VAR, "no-such-engine")
    with pytest.raises(ValueError):
        create_engine()
    with pytest.raises(ValueError):
        create_app()


# -- HTTP / WebSocket ------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv(ENGINE_ENV_VAR, raising=False)
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_served_at_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Kithora" in response.text


def _receive_until_done(ws, limit: int = 1000) -> list[dict]:
    messages = []
    for _ in range(limit):
        message = ws.receive_json()
        messages.append(message)
        if message["type"] == "done":
            return messages
    raise AssertionError("server never sent {'type': 'done'}")


def test_websocket_roundtrip(client: TestClient) -> None:
    with client.websocket_connect("/ws/captions") as ws:
        for _ in range(30):  # 3 s of audio in 100 ms chunks
            ws.send_bytes(silence(100))
        ws.send_text(json.dumps({"type": "stop"}))
        messages = _receive_until_done(ws)

    assert messages[-1] == {"type": "done"}
    captions = messages[:-1]
    assert captions, "expected caption events"
    for msg in captions:
        assert msg["type"] == "caption"
        assert set(msg) == CAPTION_KEYS
        assert msg["lang"] in {"km", "en", "mixed"}

    partials = [m for m in captions if not m["is_final"]]
    finals = [m for m in captions if m["is_final"]]
    assert partials and finals
    assert finals[0]["segment_id"] == 0
    assert finals[0]["text"] == DEFAULT_PHRASES[0]
    # Audio stopped mid-way through the second phrase -> it is finalised too.
    assert finals[-1]["segment_id"] == 1
    assert captions[-1]["is_final"]


def test_websocket_rejects_bad_control_message(client: TestClient) -> None:
    with client.websocket_connect("/ws/captions") as ws:
        ws.send_text("not json")
        error = ws.receive_json()
        assert error["type"] == "error"
        ws.send_text(json.dumps({"type": "pause"}))
        assert ws.receive_json()["type"] == "error"
        ws.send_text(json.dumps({"type": "stop"}))
        assert _receive_until_done(ws) == [{"type": "done"}]
