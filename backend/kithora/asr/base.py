"""Engine-agnostic speech recognition interface.

Every ASR backend (dummy, local model, cloud API, ...) implements
:class:`AsrEngine` so the WebSocket layer never needs to know which engine
is in use.

Audio contract: ``feed_audio`` receives raw PCM, 16 kHz, mono, signed 16-bit
little-endian (see the constants below). Chunks may be any length; engines
must not assume chunk boundaries line up with samples or words.
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

SAMPLE_RATE = 16_000
"""Expected input sample rate in Hz."""

SAMPLE_WIDTH_BYTES = 2
"""Bytes per sample (signed 16-bit little-endian)."""

CHANNELS = 1
"""Expected number of channels (mono)."""

Lang = Literal["km", "en", "mixed"]
VALID_LANGS: frozenset[str] = frozenset({"km", "en", "mixed"})


@dataclass(frozen=True, slots=True)
class CaptionEvent:
    """A partial or final caption for one speech segment.

    Partials for a segment share its ``segment_id`` and each one replaces the
    previous; the final event for that ``segment_id`` is the last one sent.
    """

    segment_id: int
    text: str
    is_final: bool
    lang: Lang
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.lang not in VALID_LANGS:
            raise ValueError(f"lang must be one of {sorted(VALID_LANGS)}, got {self.lang!r}")
        if self.end_ms < self.start_ms:
            raise ValueError(f"end_ms ({self.end_ms}) must be >= start_ms ({self.start_ms})")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict of this event."""
        return dataclasses.asdict(self)


class AsrEngine(ABC):
    """Abstract streaming speech recogniser.

    Lifecycle (one engine instance per audio stream / WebSocket connection)::

        await engine.start()
        # concurrently: async for event in engine.events(): ...
        await engine.feed_audio(chunk)   # repeated
        await engine.finish()

    ``events()`` must yield caption events as they become available and stop
    iterating once ``finish()`` has been called and every pending event has
    been delivered. It supports a single consumer.
    """

    name: str = "base"

    @abstractmethod
    async def start(self) -> None:
        """Prepare the engine for a new audio stream."""

    @abstractmethod
    async def feed_audio(self, pcm: bytes) -> None:
        """Feed a chunk of 16 kHz mono s16le PCM audio."""

    @abstractmethod
    async def finish(self) -> None:
        """Signal end of audio; flush remaining results. Must be idempotent."""

    @abstractmethod
    def events(self) -> AsyncIterator[CaptionEvent]:
        """Async iterator of caption events; ends after ``finish()`` drains."""

    def __aiter__(self) -> AsyncIterator[CaptionEvent]:
        return self.events()
