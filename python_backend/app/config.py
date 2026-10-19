"""Settings read from environment variables or the repo-root `.env` file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    gemini_api_key: str = ""
    # Comma-separated BCP-47 codes sent to Gemini; empty string = automatic detection.
    gemini_language_codes: str = "km-KH,en-US"
    kethra_default_engine: str = "gemini-3.5-transcribe"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'kethra.db').as_posix()}"
    # Set true in production (HTTPS) so the login cookie is never sent over plain HTTP.
    kethra_cookie_secure: bool = False
    kethra_max_upload_bytes: int = 25 * 1024 * 1024
    kethra_max_ws_chunk_bytes: int = 5 * 1024 * 1024
    kethra_ws_session_timeout_seconds: int = 600
    kethra_ws_idle_timeout_seconds: int = 60
    kethra_max_streams_per_user: int = 2
    kethra_rate_limit_per_minute: int = 30
    kethra_engine_timeout_seconds: float = 30


settings = Settings()
