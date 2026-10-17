"""Fake ASR engine so the capture -> WebSocket -> caption loop works end to end.

The engine ignores what the audio *contains* and only counts how much audio
has arrived. Every ``ms_per_word`` of audio it reveals one more word of the
current fake phrase as a partial caption; when the phrase is complete it
emits a final caption, waits ``gap_ms`` of audio, then starts the next phrase
(cycling through the list). Output is fully deterministic for a given
amount of audio, which keeps the tests simple.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from kithora.asr.base import SAMPLE_RATE, SAMPLE_WIDTH_BYTES, AsrEngine, CaptionEvent
from kithora.asr.lang import detect_lang

DEFAULT_PHRASES: tuple[str, ...] = (
    "សួស្តី everyone, ថ្ងៃនេះ we will talk about AI",
    "Machine learning គឺជា subset មួយនៃ artificial intelligence",
    "សូមអរគុណ សម្រាប់ការស្តាប់",
    "Let's start the meeting now",
    "យើងនឹង deploy model នេះ នៅ next week",
)


class DummyEngine(AsrEngine):
    """Emits growing partial captions then a final one, driven by audio length."""

    name = "dummy"

    def __init__(
        self,
        phrases: Sequence[str] | None = None,
        ms_per_word: int = 250,
        gap_ms: int = 500,
    ) -> None:
        source = tuple(phrases) if phrases is not None else DEFAULT_PHRASES
        word_lists = tuple(tuple(p.split()) for p in source)
        if not word_lists or any(not words for words in word_lists):
            raise ValueError("phrases must be a non-empty sequence of non-blank strings")
        if ms_per_word <= 0:
            raise ValueError("ms_per_word must be > 0")
        if gap_ms < 0:
            raise ValueError("gap_ms must be >= 0")

        self._phrases = word_lists
        self._ms_per_word = ms_per_word
        self._gap_ms = gap_ms

        self._queue: asyncio.Queue[CaptionEvent | None] | None = None
        self._started = False
        self._finished = False
        self._bytes_received = 0

        self._segment_id = 0
        self._phrase_index = 0
        self._words_shown = 0
        self._segment_start_ms = 0
        self._next_word_ms = ms_per_word

    # -- AsrEngine API -----------------------------------------------------

    async def start(self) -> None:
        if self._started:
            raise RuntimeError("DummyEngine.start() called twice")
        self._queue = asyncio.Queue()
        self._started = True

    async def feed_audio(self, pcm: bytes) -> None:
        if not self._started:
            raise RuntimeError("start() must be called before feed_audio()")
        if self._finished:
            raise RuntimeError("feed_audio() called after finish()")
        self._bytes_received += len(pcm)
        now_ms = self._audio_ms()
        while now_ms >= self._next_word_ms:
            self._reveal_next_word(self._next_word_ms)

    async def finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        if self._queue is None:  # never started
            return
        if self._words_shown > 0:
            # Audio ended mid-phrase: finalise whatever has been revealed.
            self._emit(is_final=True, end_ms=self._audio_ms())
        self._queue.put_nowait(None)

    async def events(self) -> AsyncIterator[CaptionEvent]:
        if self._queue is None:
            raise RuntimeError("start() must be called before events()")
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event

    # -- internals ---------------------------------------------------------

    def _audio_ms(self) -> int:
        samples = self._bytes_received // SAMPLE_WIDTH_BYTES
        return samples * 1000 // SAMPLE_RATE

    def _reveal_next_word(self, boundary_ms: int) -> None:
        words = self._phrases[self._phrase_index]
        self._words_shown += 1
        is_final = self._words_shown >= len(words)
        self._emit(is_final=is_final, end_ms=boundary_ms)
        if is_final:
            self._advance_segment(boundary_ms)
        else:
            self._next_word_ms = boundary_ms + self._ms_per_word

    def _emit(self, *, is_final: bool, end_ms: int) -> None:
        assert self._queue is not None
        words = self._phrases[self._phrase_index]
        text = " ".join(words[: self._words_shown])
        self._queue.put_nowait(
            CaptionEvent(
                segment_id=self._segment_id,
                text=text,
                is_final=is_final,
                lang=detect_lang(text),
                start_ms=self._segment_start_ms,
                end_ms=max(end_ms, self._segment_start_ms),
            )
        )

    def _advance_segment(self, end_ms: int) -> None:
        self._segment_id += 1
        self._phrase_index = (self._phrase_index + 1) % len(self._phrases)
        self._words_shown = 0
        self._segment_start_ms = end_ms + self._gap_ms
        self._next_word_ms = self._segment_start_ms + self._ms_per_word
