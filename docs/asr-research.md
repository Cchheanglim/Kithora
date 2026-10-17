# ASR research: real-time Khmer-English code-switching

_Task #1 — researched 2026-10-17. Vendor and model facts change fast; re-check before committing money or GPU time._

## The problem in one line

Speakers mix Khmer and English **inside a single sentence** ("ថ្ងៃនេះ we will deploy the model"), and Kithora must caption that live, keeping each word in the language and script it was spoken in — Khmer in Khmer script, English in Latin, no translation.

That rules out anything that picks one language per utterance and transliterates or drops the other.

## Key findings

| Option | Khmer quality | Code-switching | Streaming | Cost / hosting |
|---|---|---|---|---|
| **Google Chirp 3** (Speech-to-Text V2) | `km-KH` supported in `StreamingRecognize`, but **Preview** | `language_codes` accepts multiple locales or `"auto"`; mixing *within* a sentence is not documented | Yes, native | ~$0.016/min, 60 free min/month; regions `us`/`eu` |
| **Azure Speech** | `km-KH` supported | Continuous LID handles up to 10 languages but **does not switch within a sentence** | Yes, native | Pay per hour; cloud only for LID |
| **ElevenLabs Scribe** | Batch Scribe lists Khmer | Unknown | Scribe v2 Realtime is ~150 ms, but Khmer is **not confirmed** in its realtime list | Paid API |
| **Deepgram Nova** | ~100% WER on FLEURS Khmer — unusable | — | — | — |
| **Vanilla Whisper** (large-v3) | >100% WER on Khmer out of the box | Poor | Not native | Free, self-host |
| **Fine-tuned Whisper** (e.g. `seanghay/whisper-small-khmer-v2`, `ksoky/whisper-large-khmer-asr`) | WER ~30–60% (WER is misleading for Khmer; CER ~20%+) | Not trained on code-switch | Via `whisper_streaming` / faster-whisper, ~3 s latency | Free, needs GPU for large |
| **Omnilingual-ASR-Khm** (`Darayut/Omnilingual-ASR-Khm`, Meta Omnilingual 300M + CTC) | FLEURS 12.0% CER / 25.7% WER; SLR42 14.8% CER | **Fine-tuned on Khmer-English code-switching data** | CTC is streaming-friendly (chunked decode) but no streaming code shipped | MIT, 300M params — runs on modest GPU / maybe CPU |

Notes:
- **Use CER, not WER, for Khmer.** Khmer is written without spaces between words, so WER depends on whichever word segmenter you use.
- No public Khmer-English code-switching **benchmark** turned up. We will need our own small evaluation set (see the plan below).

## Recommendation

**Run two engines behind the `AsrEngine` interface and pick between them with our own test set.**

1. **Primary self-hosted engine: `Omnilingual-ASR-Khm`.**
   It is the only candidate trained on Khmer-English code-switching. It is small (300M), MIT-licensed, and its CTC output fits chunked streaming. The risk is that it is a single-author community model with no streaming implementation, so we write the chunking and partial/final logic ourselves.

2. **Cloud baseline: Google Chirp 3 streaming** with `language_codes=["km-KH","en-US"]`.
   It is the fastest way to get real captions on screen, streams natively, and is cheap at ~$0.016/min. The risks are that `km-KH` is still Preview and mid-sentence switching is unproven, so we measure it rather than assume it works.

3. **Fallback/experiment: fine-tuned Whisper via faster-whisper + whisper_streaming.** It is mature tooling, but latency is ~3 s and it has no code-switch training. Keep it only if both engines above fail.

Skip Deepgram (does not handle Khmer) and Azure (cannot switch within a sentence). Revisit ElevenLabs if it confirms Khmer support in realtime.

### Proposed stack
- **Backend:** Python + FastAPI WebSocket (already scaffolded). `KITHORA_ENGINE=dummy|google|omnilingual`.
- **Per-segment language tag** (`km`/`en`/`mixed`): compute it from the output script (Khmer Unicode block U+1780–U+17FF vs Latin). This is more reliable than trusting the engine's language ID.
- **Post-processing:** Khmer word segmentation (e.g. `khmer-nltk`) only for display line-breaking, never altering the words.

## Next steps
1. Record a **30-minute in-house eval set** of natural Khmer-English code-switched speech with reference transcripts.
2. Implement a `GoogleChirpEngine` → measure CER and latency.
3. Implement an `OmnilingualEngine` with chunked CTC decoding → measure CER and latency on the same set.
4. Choose the default engine from those numbers.

## Sources
- [Google Chirp 3 docs](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3) · [Speech-to-Text pricing](https://cloud.google.com/speech-to-text/pricing/)
- [Azure language identification](https://learn.microsoft.com/en-my/Azure/ai-services/speech-service/language-identification)
- [ElevenLabs Khmer STT](https://elevenlabs.io/speech-to-text/khmer) · [Scribe v2 Realtime](https://elevenlabs.io/realtime-speech-to-text)
- [Fine-tuning Whisper across 81 languages (2026)](https://aclanthology.org/2026.scil-main.37.pdf)
- [seanghay/whisper-small-khmer-v2](https://huggingface.co/seanghay/whisper-small-khmer-v2) · [ksoky/whisper-large-khmer-asr](https://huggingface.co/ksoky/whisper-large-khmer-asr)
- [Darayut/Omnilingual-ASR-Khm](https://huggingface.co/Darayut/Omnilingual-ASR-Khm) · [Meta Omnilingual ASR](https://ai.meta.com/blog/omnilingual-asr-advancing-automatic-speech-recognition/)
- [ufal/whisper_streaming](https://github.com/ufal/whisper_streaming) · [Turning Whisper into a real-time system](https://arxiv.org/html/2307.14743)
