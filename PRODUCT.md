# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **API users (primary):** developers who sign up on the website, log in, and create an API key so their own apps (web, mobile, desktop) can turn Khmer-English speech into text. They come to the site to get a key, test it in the playground, read the docs, and check their usage.
- **Owner/operator:** the project's developer, who watches accounts, API keys and usage through the backend and its database. There is no admin screen on the website yet; whether to add one is undecided.

## Product Purpose

Kethra (tagline: "Every Word, Clearly Heard.") is a speech-to-text API with a developer website, built for people who switch between Khmer and English in the same sentence. A visitor should be able to sign up, get an API key, and get back a real transcript that keeps both languages as spoken.

It is a learning project: the goal is to build a serious, working API product and understand every part of it. There are no business or pricing plans.

## Positioning

General speech tools pick one language and translate or garble the rest. Kethra transcribes mixed speech verbatim: Khmer stays in Khmer script, English stays in Latin script, and the language switches are kept. It never translates.

## Operating Context

- Website pages: landing, register/login, dashboard (usage, integration status), API keys (create, show once, revoke, per-key usage), playground (live microphone captions and file upload), docs, account settings.
- Developers call `POST /v1/transcriptions` and `WS /v1/listen` from their own servers with `Authorization: Bearer <api key>`. Browser and mobile clients get a 5-minute, single-use session token from their server instead of holding a key.
- The speech engine is Google's Gemini 3.5 Transcribe on the free tier, so audio is sent to Google, and Google may use it to improve its products.

## Capabilities and Constraints

- Built: FastAPI backend (SQLite by default) and a React + Vite + Tailwind site, with email/password accounts, hashed API keys with permissions, rate limits, and usage records that store metadata only, never audio or transcripts.
- Built: the whole website switches between English and Khmer (`src/i18n.tsx`; choice saved in the browser).
- Built: an accuracy evaluation tool (`python_backend/evaluation/`) that scores an engine against human reference transcripts. It has not been run on real clips yet.
- Live captions arrive as 4-second clips with about 5 seconds of delay. There are no word-by-word partial results, and words can be cut at clip edges.
- Not built: email verification, password reset, projects, SDKs, an admin view.
- No pricing or plans. Do not show pricing.
- Terminology: "API key" (permanent, server-side), "session token" (short-lived, for live captions), "playground" (in-browser testing).

## Brand Commitments

- Product name **Kethra**. The repository is named Kithora.
- Tagline: "Every Word, Clearly Heard."
- Honesty is part of the brand. Never imply accuracy that hasn't been measured. Always label mock-engine output. Always disclose when audio goes to Google.

## Evidence on Hand

- Verified: a computer-voice English clip was transcribed correctly through REST and live WebSocket (2026-10-19).
- None yet: measured Khmer or Khmer-English accuracy, real users, testimonials, customers, benchmarks, logos, press. Future work must not fabricate any of these.

## Product Principles

1. **Keep what was said.** Transcripts preserve both languages and never translate. Normalization only fixes spacing and Unicode, and the raw output is always available.
2. **Honest by default.** Show real numbers or honest empty states. Label mocks, state limits, disclose third-party processing.
3. **Secure without friction.** Keys are shown once and never sit in public clients; the safe path is the easy path.
4. **Khmer speakers are first-class.** Khmer text and Khmer readers get the same care as English, including a full Khmer version of the site.
5. **Simple enough to understand.** As a learning project, prefer clear, explainable choices over clever ones.

## Accessibility & Inclusion

- Khmer script and English must both be fully legible wherever they appear, including mixed in one line.
- The site must work fully in either English or Khmer.
