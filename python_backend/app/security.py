"""Passwords, website login sessions, API keys, short-lived stream tokens, and rate limits."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import settings
from .db import ApiKey, LoginSession, User, utcnow

ALL_SCOPES = ("transcriptions:write", "stream:listen", "usage:read")
SESSION_COOKIE = "kethra_session"
LOGIN_SESSION_DAYS = 14
STREAM_TOKEN_TTL_SECONDS = 300
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class KethraError(Exception):
    """Rendered as {"error": {"code", "message", "retryable"}} by the app's exception handler."""

    def __init__(self, status: int, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.status, self.code, self.message, self.retryable = status, code, message, retryable


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


# --- Passwords (stdlib scrypt) --------------------------------------------------------------

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    _, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)


_DUMMY_HASH = hash_password(secrets.token_hex(8))


def validate_credentials(email: str, password: str) -> str:
    email = email.strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise KethraError(400, "invalid_email", "Enter a valid email address.")
    if not 8 <= len(password) <= 128:
        raise KethraError(400, "invalid_password", "Password must be 8 to 128 characters.")
    return email


def register_user(db: Session, email: str, password: str) -> User:
    email = validate_credentials(email, password)
    if db.scalar(select(User).where(User.email == email)):
        raise KethraError(409, "email_taken", "An account with this email already exists.")
    user = User(id=new_id("usr"), email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    # Hash even when the user doesn't exist so response time doesn't reveal registered emails.
    if not verify_password(password, user.password_hash if user else _DUMMY_HASH) or user is None:
        raise KethraError(401, "invalid_login", "Email or password is incorrect.")
    return user


def start_login_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.execute(delete(LoginSession).where(LoginSession.expires_at < utcnow()))
    db.add(LoginSession(token_hash=sha256(token), user_id=user.id,
                        expires_at=utcnow() + timedelta(days=LOGIN_SESSION_DAYS)))
    db.commit()
    return token


def end_login_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == sha256(token)))
        db.commit()


def user_from_cookie(db: Session, request: Request) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = db.get(LoginSession, sha256(token))
    if session is None or session.expires_at < utcnow():
        return None
    return db.get(User, session.user_id)


def require_user(db: Session, request: Request) -> User:
    user = user_from_cookie(db, request)
    if user is None:
        raise KethraError(401, "not_logged_in", "Log in to continue.")
    return user


# --- API keys ----------------------------------------------------------------------------------


def create_api_key(db: Session, user: User, name: str, scopes: list[str]) -> tuple[ApiKey, str]:
    plaintext = f"kth_live_{secrets.token_hex(20)}"
    record = ApiKey(
        id=new_id("key"),
        user_id=user.id,
        name=name,
        key_prefix=f"{plaintext[:13]}...{plaintext[-4:]}",
        # SHA-256 is enough here: keys are 160-bit random, so there is nothing to brute-force.
        key_hash_sha256=sha256(plaintext),
        scopes=" ".join(scopes),
    )
    db.add(record)
    db.commit()
    return record, plaintext


def verify_api_key(db: Session, plaintext: str, scope: str) -> ApiKey:
    record = db.scalar(select(ApiKey).where(ApiKey.key_hash_sha256 == sha256(plaintext)))
    if record is None:
        raise KethraError(401, "unauthorized", "Invalid API key.")
    if record.revoked_at:
        raise KethraError(401, "unauthorized", "API key has been revoked.")
    if scope not in record.scopes.split():
        raise KethraError(403, "insufficient_scope", f"API key lacks required scope: {scope}")
    record.last_used_at = utcnow()
    db.commit()
    return record


@dataclass
class Caller:
    """Who is making a request: a user, via an API key or via the website login cookie."""

    user_id: str
    api_key_id: str | None


def authenticate(db: Session, request: Request, scope: str) -> Caller:
    """`Authorization: Bearer <api key>` for apps; the login cookie for the website playground."""
    auth = request.headers.get("authorization", "")
    if auth:
        if not auth.lower().startswith("bearer "):
            raise KethraError(401, "unauthorized", "Use Authorization: Bearer <api key>.")
        key = verify_api_key(db, auth[7:].strip(), scope)
        return Caller(key.user_id, key.id)
    user = user_from_cookie(db, request)
    if user is None:
        raise KethraError(401, "unauthorized", "Missing Authorization: Bearer <api key>.")
    return Caller(user.id, None)


# --- Short-lived, single-use stream tokens -----------------------------------------------------
# shortcut: in-process dicts; tokens, rate limits and stream counts reset on restart and do not
# work across several server processes. Move to Redis when running more than one process.


@dataclass
class _StreamToken:
    session_id: str
    caller: Caller
    expires_at: float


_stream_tokens: dict[str, _StreamToken] = {}


def issue_stream_token(caller: Caller) -> dict:
    now = time.time()
    for t in [t for t, v in _stream_tokens.items() if v.expires_at < now]:
        del _stream_tokens[t]
    token = f"kth_sess_{secrets.token_hex(16)}"
    entry = _StreamToken(new_id("sess"), caller, now + STREAM_TOKEN_TTL_SECONDS)
    _stream_tokens[token] = entry
    return {
        "token": token,
        "session_id": entry.session_id,
        "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry.expires_at)),
        "single_use": True,
        "ws_endpoint": "/v1/listen",
    }


def consume_stream_token(db: Session, token: str) -> tuple[Caller, str]:
    """Returns (caller, session id). The token is deleted on first use."""
    entry = _stream_tokens.pop(token, None)
    if entry is None or entry.expires_at < time.time():
        raise KethraError(401, "unauthorized_stream", "Session token is invalid, expired, or already used.")
    key_id = entry.caller.api_key_id
    if key_id and (db.get(ApiKey, key_id) is None or db.get(ApiKey, key_id).revoked_at):
        raise KethraError(401, "unauthorized_stream", "The API key behind this session token was revoked.")
    if db.get(User, entry.caller.user_id) is None:
        raise KethraError(401, "unauthorized_stream", "Account no longer exists.")
    return entry.caller, entry.session_id


_requests: dict[str, deque[float]] = defaultdict(deque)
_open_streams: dict[str, int] = defaultdict(int)


def check_rate_limit(bucket: str, per_minute: int | None = None) -> None:
    """Sliding one-minute window. Speech calls cost money; login attempts invite brute force."""
    limit = per_minute or settings.kethra_rate_limit_per_minute
    now = time.time()
    window = _requests[bucket]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= limit:
        raise KethraError(429, "rate_limited", "Too many requests. Try again in a minute.", retryable=True)
    window.append(now)


def open_stream(user_id: str) -> None:
    if _open_streams[user_id] >= settings.kethra_max_streams_per_user:
        raise KethraError(429, "too_many_streams", "You already have the maximum number of open streams.")
    _open_streams[user_id] += 1


def close_stream(user_id: str) -> None:
    _open_streams[user_id] = max(0, _open_streams[user_id] - 1)
