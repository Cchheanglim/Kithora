"""Database models and session factory (SQLite by default, Postgres via DATABASE_URL)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import settings


def utcnow() -> datetime:
    # Naive UTC: SQLite drops tzinfo on read, so storing naive keeps comparisons consistent.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    def to_public(self) -> dict:
        return {"id": self.id, "email": self.email, "created_at": self.created_at.isoformat()}


class LoginSession(Base):
    """Website login. Only the SHA-256 of the cookie value is stored."""

    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime]


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(100))
    key_prefix: Mapped[str] = mapped_column(String(32))
    key_hash_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    scopes: Mapped[str] = mapped_column(String(200))  # space-separated
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)

    def to_public(self) -> dict:
        """Everything except the hash: the dashboard never needs it."""
        return {
            "id": self.id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scopes": self.scopes.split(),
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "status": "revoked" if self.revoked_at else "active",
        }


class UsageRecord(Base):
    """Operational metadata only: never audio or transcript text."""

    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    api_key_id: Mapped[str | None] = mapped_column(String(32), index=True)  # None = website playground
    endpoint: Mapped[str] = mapped_column(String(64))
    engine_id: Mapped[str] = mapped_column(String(64))
    is_mock: Mapped[bool]
    status_code: Mapped[int]
    audio_bytes: Mapped[int]
    latency_ms: Mapped[int]
    code_switched_detected: Mapped[bool]

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "api_key_id": self.api_key_id,
            "endpoint": self.endpoint,
            "engine_id": self.engine_id,
            "is_mock": self.is_mock,
            "status_code": self.status_code,
            "audio_bytes": self.audio_bytes,
            "latency_ms": self.latency_ms,
            "code_switched_detected": self.code_switched_detected,
        }


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    # shortcut: create_all instead of Alembic migrations; switch to Alembic before the schema changes with real data in it (Phase 2).
    Base.metadata.create_all(engine)


def get_db():
    with SessionLocal() as db:
        yield db


__all__ = ["ApiKey", "LoginSession", "User", "UsageRecord", "Session", "SessionLocal", "get_db", "init_db", "utcnow"]
