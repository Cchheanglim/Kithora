"""API key management (website login required) and usage reporting."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from ..db import ApiKey, Session, UsageRecord, get_db, utcnow
from ..security import ALL_SCOPES, KethraError, authenticate, create_api_key, require_user

router = APIRouter(prefix="/v1", tags=["keys & usage"])

MAX_ACTIVE_KEYS = 20


class NewKey(BaseModel):
    name: str
    scopes: list[str] | None = None


@router.get("/keys")
def list_keys(request: Request, db: Session = Depends(get_db)):
    user = require_user(db, request)
    keys = db.scalars(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())).all()
    counts = dict(db.execute(
        select(UsageRecord.api_key_id, func.count()).where(UsageRecord.user_id == user.id).group_by(UsageRecord.api_key_id)
    ).all())
    return {"object": "list", "data": [{**k.to_public(), "request_count": counts.get(k.id, 0)} for k in keys]}


@router.post("/keys", status_code=201)
def new_key(body: NewKey, request: Request, db: Session = Depends(get_db)):
    user = require_user(db, request)
    name = body.name.strip()
    if not 2 <= len(name) <= 100:
        raise KethraError(400, "invalid_request", "Key name must be 2 to 100 characters.")
    scopes = list(ALL_SCOPES) if body.scopes is None else body.scopes
    if not scopes or any(s not in ALL_SCOPES for s in scopes):
        raise KethraError(400, "invalid_request", f"Scopes must be a non-empty subset of {list(ALL_SCOPES)}.")
    active = db.scalar(select(func.count()).where(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None)))
    if active >= MAX_ACTIVE_KEYS:
        raise KethraError(400, "too_many_keys", f"Revoke a key first; the limit is {MAX_ACTIVE_KEYS} active keys.")
    record, plaintext = create_api_key(db, user, name, scopes)
    return {
        "object": "api_key",
        "record": {**record.to_public(), "request_count": 0},
        "plaintext_key_once": plaintext,
    }


@router.post("/keys/{key_id}/revoke")
def revoke_key(key_id: str, request: Request, db: Session = Depends(get_db)):
    user = require_user(db, request)
    record = db.get(ApiKey, key_id)
    if record is None or record.user_id != user.id:
        raise KethraError(404, "not_found", "API key not found.")
    record.revoked_at = record.revoked_at or utcnow()
    db.commit()
    return {"object": "api_key", "record": record.to_public()}


@router.get("/usage")
def usage(request: Request, db: Session = Depends(get_db)):
    caller = authenticate(db, request, "usage:read")
    mine = UsageRecord.user_id == caller.user_id
    total, audio_bytes, errors, code_switched, avg_latency = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(UsageRecord.audio_bytes), 0),
            func.count().filter(UsageRecord.status_code >= 400),
            func.count().filter(UsageRecord.code_switched_detected),
            func.avg(UsageRecord.latency_ms).filter(UsageRecord.status_code < 400),
        ).where(mine)
    ).one()
    logs = db.scalars(select(UsageRecord).where(mine).order_by(UsageRecord.id.desc()).limit(100)).all()
    return {
        "total_requests": total,
        "total_audio_bytes": audio_bytes,
        "error_count": errors,
        "code_switched_utterances": code_switched,
        "average_latency_ms": round(avg_latency) if avg_latency is not None else None,
        "logs": [r.to_public() for r in logs],
    }
