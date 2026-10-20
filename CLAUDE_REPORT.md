# Kethra / Kithora: Project Status & Handoff Report for Claude Code

**Date:** October 20, 2026  
**Repository:** `Kithora` (Product name: **Kethra**)  
**Branch:** `Work-Branch`  
**Working Directory:** `D:\Very, Urgenly, Important\Github Projects\Kithora`

---

## 1. Executive Summary & User Goal

### Core Product Purpose
Kethra is a speech-to-text API engine designed for **Khmer-English code-switching** (speakers mixing Khmer and English in the same sentence). The founding commitment is **verbatim transcription**:
- Khmer remains in Khmer script.
- English remains in Latin script.
- **Never translate** and **never transliterate** what was spoken.

### Primary User Goal (New Requirement)
The user wants to use Kethra as the **core transcription engine for editor software**, specifically targeting **both**:
1. **Subtitle / Video / Audio Editor**:
   - Requires word-level or segment-level timestamps (`start_time`, `end_time`).
   - Requires export/output formats suitable for video editors (e.g., SRT, WebVTT, JSON cues).
2. **Live Dictation / Text Editor**:
   - Real-time speech-to-text as the user speaks into a microphone.
   - Streaming text delivery with low latency over WebSockets.

---

## 2. Architecture & Codebase Overview

### Backend (`python_backend/`)
- **Framework:** FastAPI, Uvicorn, Python 3.12+ (tested up to 3.14).
- **Database:** SQLite with SQLAlchemy (`app/db.py`) storing users, hashed API keys, session tokens, and metadata-only usage metrics (zero-retention: audio and transcripts are never stored on disk).
- **Security:** Scrypt password hashing, bearer API keys with scopes (`transcriptions:write`, `stream:listen`), and single-use 5-minute session tokens for web/mobile streaming clients (`app/security.py`).
- **Engine Adapter Layer (`app/adapters/base.py`):**
  - Abstract base class: `SpeechEngineAdapter`.
  - Current adapters:
    1. `GeminiTranscribeSpeechAdapter` (`gemini-3.5-transcribe` via Google `genai.Client`).
    2. `DeterministicMockSpeechAdapter` (`mock-deterministic`, test adapter returning a fixed bilingual sentence).
- **Text Normalizer (`app/services/normalizer.py`):**
  - Unicode NFC normalization.
  - Spacing rules at Khmer/Latin script boundaries without altering words.
  - Identification of code-switch points and span segmentation.
- **WebSocket Streaming (`app/api/speech.py`):**
  - `/v1/listen` endpoint using `session.init`, `audio.chunk`, `session.complete` messages.
- **Accuracy Evaluation & Scoring (`app/services/scoring.py`, `evaluation/`):**
  - Newly built evaluation pipeline specifically for Khmer-English code-switching.

### Frontend (`src/`)
- React 18 + Vite + Tailwind CSS.
- Multi-page UI: Landing, Playground (live mic captioning & file upload), API Keys, Dashboard, Docs, Settings.
- Full bilingual English/Khmer i18n switcher (`src/i18n.tsx`) stored in `localStorage`.
- **Note:** The user confirmed satisfaction with the current UI/UX state.

---

## 3. Work Completed in This Session

### A. Khmer-English Accuracy Evaluation Harness
Khmer has no word boundary spaces, rendering standard Word Error Rate (WER) ineffective. We designed and implemented an academic-grade evaluation tool:
1. **`python_backend/app/services/scoring.py`**:
   - **Mixed Error Rate (MER):** Khmer is segmented into **Khmer Character Clusters (KCC)** (base consonant + coeng subscripts + dependent vowels + diacritics); English is segmented into words; numbers into digit sequences.
   - **Cross-Script Substitutions:** Detects when Khmer tokens are substituted with English words (or vice versa), directly tracking unwanted translation/transliteration.
   - **Foreign Script Penalty:** Flags and penalizes unexpected foreign scripts (e.g., Thai, Chinese).
   - **Orthographic Invariance:** Normalizes interchangeable Khmer glyph variants (such as subscript TA `្ត` vs subscript DA `្ដ`).
   - Also computes separate English WER, Khmer Cluster Error Rate, and Character Error Rate (CER).
2. **`python_backend/evaluation/run.py`**:
   - CLI runner that iterates through audio files and matching `.txt` reference files.
   - Supports automated retries, rate-limiting delays (to protect free tiers), and HTTP timeout handling.
   - Generates structured JSON and human-readable Markdown reports under `evaluation/results/`.
   - `--rescore` mode to recalculate scores against corrected ground-truth references without making new API calls.
3. **`python_backend/evaluation/README.md`**:
   - Guide for collecting consented native voice clips, formatting references, and interpreting metrics.
4. **Git updates**:
   - Added `python_backend/evaluation/clips/` and `python_backend/evaluation/results/` to `.gitignore` to prevent committing audio recordings or personal data.
5. **Backend Tests:**
   - Added unit tests in `tests/test_scoring.py`.
   - **All 38 backend tests currently pass** via pytest (`.venv/Scripts/python -m pytest`).

---

## 4. Key Findings from Real-Engine Testing

Using 6 neural TTS synthetic clips (Edge-TTS: Aria for EN, Sreymom and Piseth for KM), we performed live evaluations against `gemini-3.5-transcribe`:

1. **Language Code Parameter Sensitivity:**
   - **`GEMINI_LANGUAGE_CODES=km-KH,en-US`:**
     - Pure Khmer audio was translated into English (`"I will go to the market tomorrow to buy vegetables."`).
     - Occasional foreign script hallucination (Thai `นี้` and Chinese `我们`).
   - **`GEMINI_LANGUAGE_CODES=km-KH`:**
     - Successfully stopped translating pure Khmer into English!
     - However, English loan phrases were sometimes transliterated phonetically into Khmer script (e.g. "send the report" -> `សិនដឺរេផត`).
   - **Auto-detection (`GEMINI_LANGUAGE_CODES=""`):**
     - Prone to hanging/timeouts with the current Gemini API.
2. **Timeout Fix Applied:**
   - In `app/adapters/base.py`, added `http_options=types.HttpOptions(timeout=int(settings.kethra_engine_timeout_seconds * 1000))` to the Gemini client initialization so blocked network calls fail fast and do not leak worker threads.
3. **Gemini SDK Timestamp Support Discovered:**
   - In `google.genai.types.AudioTranscriptionConfig`, Google supports:
     - `word_timestamp: bool`
     - `diarization: bool`
     - `mode: "VERBATIM" | "SMART"`
   - *Crucial note for editors:* Setting `word_timestamp=True` allows obtaining word-level timings directly from Gemini when in `VERBATIM` mode!

---

## 5. Self-Hosting / Offline Engine Options (No Google API)

The user asked whether we can run entirely without Google/Gemini:
- **Available Open-Source Whisper Khmer Models:**
  - `seanghay/whisper-small-khmer-v2` (Fine-tuned on Google FLEURS, OpenSLR SLR42).
  - `Vira21/Whisper-Small-Khmer` (Reported ~37.6% WER on standard Khmer test sets).
  - `sengtha/whisper-base-khmer` (ONNX/browser/offline focus).
- **Trade-offs for Khmer-English Code Switching:**
  - Existing open-source models are fine-tuned almost exclusively on *monolingual* Khmer data. They often struggle when speakers switch rapidly between Khmer and English mid-sentence.
  - Running Whisper locally requires PyTorch or `faster-whisper`. On a CPU without CUDA, inference latency will be several seconds per clip.
  - **Recommendation:** Add a `WhisperSpeechAdapter` to `app/adapters/base.py` to allow side-by-side benchmarking against Gemini using `evaluation/run.py`.

---

## 6. Actionable Roadmap for Claude Code

To fulfill the user's goal of building an engine for **editor software** (subtitles with timestamps + live dictation), follow these prioritized tasks:

### Task 1: Add Timestamps & Subtitle Export (Video/Audio Editor Support)
- [ ] Update `EngineTranscriptionOutput` in `app/adapters/base.py` to include structured segments/words with timestamps:
  ```python
  @dataclass(frozen=True)
  class WordTiming:
      word: str
      start_ms: int
      end_ms: int

  @dataclass(frozen=True)
  class TranscriptSegment:
      text: str
      start_ms: int
      end_ms: int
      words: list[WordTiming] = field(default_factory=list)
  ```
- [ ] In `GeminiTranscribeSpeechAdapter._transcribe_sync`, enable `word_timestamp=True` in `AudioTranscriptionConfig` and parse word/segment timestamps from Gemini's response.
- [ ] Add subtitle format serializers in a new service (`app/services/subtitles.py`):
  - Export to **SRT** (`.srt`).
  - Export to **WebVTT** (`.vtt`).
  - Export to **Timestamped JSON** (for timeline editors).
- [ ] Update `POST /v1/transcriptions` to accept query parameter `?format=json|srt|vtt` and include the `segments` in the JSON response.

### Task 2: Real-Time Streaming Dictation (Text Editor Support)
- [ ] Review `app/api/speech.py` `/v1/listen` WebSocket.
- [ ] Support progressive partial transcripts (`transcript.partial`) vs final segment commitments (`transcript.final`).
- [ ] Create a small client helper or SDK snippet (Python / JS) demonstrating how an external editor connects, streams microphone PCM/WebM chunks, and renders text directly into a text cursor.

### Task 3: Local / Offline Engine Adapter (Optional / Next Milestone)
- [ ] Create `WhisperLocalSpeechAdapter` in `app/adapters/base.py` using `faster-whisper` or HuggingFace `transformers`.
- [ ] Test with `seanghay/whisper-small-khmer-v2` or `openai/whisper-small` for offline transcription without sending audio to Google.
- [ ] Run `python -m evaluation.run --engine whisper-local` to compare against Gemini.

---

## 7. Quick Commands for Development

```bash
# Run backend unit tests
cd python_backend
.venv/Scripts/python -m pytest

# Run evaluation with mock engine (dry run)
.venv/Scripts/python -m evaluation.run --engine mock-deterministic

# Run evaluation with real Gemini engine (requires GEMINI_API_KEY in .env)
.venv/Scripts/python -m evaluation.run --clips path/to/clips --out evaluation/results/ --yes

# Start backend server
.venv/Scripts/uvicorn app.main:app --reload --port 8000

# Start frontend dev server (repo root)
npm run dev
```
