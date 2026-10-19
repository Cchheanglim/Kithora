# Kithora

Kethra is a real-time Khmer-English code-switching captioning application that converts mixed-language speech into readable text while preserving the speaker's original words.

Users sign up on the website, create API keys, and call the speech API from their own apps. The website's playground uses the same API.

## Layout

| Path | What it is |
|---|---|
| `python_backend/app/main.py` | FastAPI app: error format, routers, serves the built website from `dist/` |
| `python_backend/app/api/account.py` | Register, login/logout, change password, delete account |
| `python_backend/app/api/keys.py` | Create / list / revoke API keys, usage stats |
| `python_backend/app/api/speech.py` | `POST /v1/transcriptions`, `POST /v1/auth/session-token`, `WS /v1/listen`, `GET /v1/health` |
| `python_backend/app/security.py` | Password hashing (scrypt), login sessions, key hashing, stream tokens, rate limits |
| `python_backend/app/adapters/base.py` | Speech engines: Gemini 3.5 Transcribe and a labelled mock. Add new engines here |
| `python_backend/app/services/normalizer.py` | Fixes Unicode/spacing between Khmer and English. Never changes words |
| `python_backend/app/db.py` | SQLAlchemy models: users, login sessions, API keys, usage records |
| `src/` | React website: landing, login/register, dashboard, keys, playground, docs, settings |

## Run it locally

You need Python 3.12+ and Node 20+.

```bash
# 1. Config
cp .env.example .env          # then put your GEMINI_API_KEY in .env (free: https://aistudio.google.com/apikey)

# 2. API (terminal 1)
cd python_backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt    # macOS/Linux: .venv/bin/pip
.venv/Scripts/uvicorn app.main:app --reload --port 8000

# 3. Website (terminal 2, repo root)
npm install
npm run dev                    # http://localhost:3000
```

Without a `GEMINI_API_KEY`, set `KETHRA_DEFAULT_ENGINE=mock-deterministic` to click through the site. The mock returns a fixed sentence and is labelled as mock everywhere.

Interactive API reference: http://localhost:8000/docs. Health check: `curl http://localhost:8000/v1/health`.

**Production:** `npm run build`, then run only uvicorn; it serves `dist/` and the API from one origin. Put it behind HTTPS and set `KETHRA_COOKIE_SECURE=true`.

## Tests

```bash
cd python_backend
.venv/Scripts/python -m pytest       # backend: accounts, keys, scopes, uploads, rate limits, WebSocket (mock engine, no API cost)
cd .. && npm run lint                # frontend type check
```

## Status and known limits

- **Accuracy is not measured yet.** Google lists Khmer (`km-KH`) for Gemini 3.5 Transcribe, but nobody has tested Khmer-English code-switching on it here. Next step: record ~20 consented mixed-language clips and score them.
- Live captions send a complete 4-second clip at a time, so there are no word-by-word partial results and words can be split at clip boundaries. Gemini's real streaming model (`gemini-3.5-transcribe-live`) is the upgrade path.
- Rate limits, live-session tokens and stream counts live in server memory: fine for one server process, needs Redis for more.
- Database tables are created automatically; there are no Alembic migrations yet. Add them before changing tables that hold real data.
- Not built yet: email verification, password reset, projects (keys belong directly to a user), SDKs.
