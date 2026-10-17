# Team board — Claude (boss) + Antigravity (worker)

## Active Locks (files currently being edited)
<!-- none -->

## [CLAUDE] Queue

## [ANTIGRAVITY] Queue

## Review (waiting for Claude)

## Done
- **#1 ASR research + stack recommendation** — [CLAUDE] — `docs/asr-research.md`
  - Recommendation: Omnilingual-ASR-Khm (self-hosted, code-switch trained) + Google Chirp 3 streaming as cloud baseline; pick by CER/latency on our own eval set.
- **#2 Project scaffold** — [ANTIGRAVITY] — `backend/**`, `frontend/**`
  - Model: claude-opus-5-5-high (fallback gemini-3.8-flash-high) via `.agy/run.sh` (uses `--mode accept-edits`)
  - conversation_id: 899327e9-978d-478f-9459-ae56cf2ee809
  - Claude review: diff stayed inside allowed folders; 18/18 pytest pass on Python 3.14; live smoke test OK (`/health`, static page, `.js` MIME, WebSocket partial→final→done). No changes needed.

## QA & Bug Reports
- (minor) `app.py`: `_send_error` and the caption pump can call `send_json` concurrently on one socket. Fine for the stub; add a send lock when real engines land.
- (minor) Worklet downsampling is a box filter — replace with a proper low-pass before plugging in a real ASR engine.
- (minor) `test_frontend_served_at_root` couples backend tests to `frontend/index.html`.
- (info) Starlette deprecation warning: TestClient wants `httpx2` instead of `httpx`.
- (process) agy headless mode auto-denies commands and file writes but still reports `SUCCESS` — always check `denied_actions` + `git status`.
