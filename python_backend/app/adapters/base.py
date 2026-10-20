"""
Speech-engine adapters. Routes only talk to `SpeechEngineAdapter`, so engines can be swapped
without touching the API.
"""

from __future__ import annotations

import asyncio
import base64
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..config import settings


@dataclass(frozen=True)
class AudioInputPayload:
    audio_bytes: bytes
    mime_type: str
    vocabulary: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EngineTranscriptionOutput:
    raw_transcript: str
    engine_id: str
    is_mock_engine: bool
    latency_ms: int
    warnings: list[str] = field(default_factory=list)


class SpeechEngineAdapter(ABC):
    engine_id: str
    display_name: str
    is_mock: bool

    @abstractmethod
    def is_configured(self) -> bool:
        """True when credentials or local weights are available."""

    @abstractmethod
    async def transcribe_audio(self, payload: AudioInputPayload) -> EngineTranscriptionOutput:
        """Transcribe without translating: Khmer stays Khmer script, English stays Latin."""


class DeterministicMockSpeechAdapter(SpeechEngineAdapter):
    """Test adapter. Never listens to the audio; always says so in `warnings`."""

    engine_id = "mock-deterministic"
    display_name = "Mock adapter (tests only, does not listen to audio)"
    is_mock = True

    def is_configured(self) -> bool:
        return True

    async def transcribe_audio(self, payload: AudioInputPayload) -> EngineTranscriptionOutput:
        return EngineTranscriptionOutput(
            raw_transcript="ខ្ញុំនឹង send it to you tomorrow មុនម៉ោងប្រាំ។",
            engine_id=self.engine_id,
            is_mock_engine=True,
            latency_ms=0,
            warnings=["MOCK_ENGINE: fixed sample text. The audio was not analysed."],
        )


class GeminiTranscribeSpeechAdapter(SpeechEngineAdapter):
    """Google `gemini-3.5-transcribe` via the Interactions API, verbatim mode."""

    engine_id = "gemini-3.5-transcribe"
    display_name = "Gemini 3.5 Transcribe (Google, verbatim)"
    is_mock = False

    PRIVACY_WARNING = (
        "Audio was sent to Google's Gemini API. On Gemini's free tier, Google may use it to improve its products."
    )

    def is_configured(self) -> bool:
        return bool(settings.gemini_api_key.strip())

    async def transcribe_audio(self, payload: AudioInputPayload) -> EngineTranscriptionOutput:
        if not self.is_configured():
            raise RuntimeError("GEMINI_API_KEY is not set on the server.")
        start = time.perf_counter()
        # The SDK call is blocking; run it in a thread so other requests keep flowing.
        text = await asyncio.to_thread(self._transcribe_sync, payload)
        return EngineTranscriptionOutput(
            raw_transcript=text.strip(),
            engine_id=self.engine_id,
            is_mock_engine=False,
            latency_ms=int((time.perf_counter() - start) * 1000),
            warnings=[self.PRIVACY_WARNING],
        )

    def _transcribe_sync(self, payload: AudioInputPayload) -> str:
        from google import genai
        from google.genai import types

        transcription_config: dict = {"mode": "verbatim"}
        codes = [c.strip() for c in settings.gemini_language_codes.split(",") if c.strip()]
        if codes:
            transcription_config["language_codes"] = codes
        if payload.vocabulary:
            transcription_config["custom_vocabulary"] = payload.vocabulary

        # The HTTP timeout matters: the route's asyncio timeout stops waiting, but cannot stop this
        # thread. Without a timeout here, a hung request would hold a worker thread forever.
        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(settings.kethra_engine_timeout_seconds * 1000)),
        )
        interaction = client.interactions.create(
            model=self.engine_id,
            input=[{
                "type": "audio",
                "mime_type": payload.mime_type,
                "data": base64.b64encode(payload.audio_bytes).decode("ascii"),
            }],
            generation_config={"transcription_config": transcription_config},
        )
        return getattr(interaction, "output_text", "") or ""


ADAPTERS: dict[str, SpeechEngineAdapter] = {
    a.engine_id: a for a in (GeminiTranscribeSpeechAdapter(), DeterministicMockSpeechAdapter())
}
