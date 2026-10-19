import base64
import io
import wave

import pytest

from app.config import settings


def wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 1600)
    return buf.getvalue()


def make_key(client, scopes=None) -> str:
    r = client.post("/v1/keys", json={"name": "test key", **({"scopes": scopes} if scopes else {})})
    assert r.status_code == 201
    return r.json()["plaintext_key_once"]


def upload(client, key=None, data=None, **fields):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    audio = wav_bytes() if data is None else data
    return client.post("/v1/transcriptions", headers=headers, files={"file": ("a.wav", audio, "audio/wav")}, data=fields)


# --- accounts ---------------------------------------------------------------------------------

def test_register_login_logout(client, user):
    assert client.get("/v1/auth/me").json()["user"]["email"] == user["email"]
    assert client.post("/v1/auth/logout").status_code == 204
    assert client.get("/v1/auth/me").status_code == 401
    assert client.post("/v1/auth/login", json={**user, "password": "wrong password"}).status_code == 401
    assert client.post("/v1/auth/login", json=user).status_code == 200
    assert client.get("/v1/auth/me").status_code == 200


def test_register_validation(client, user):
    assert client.post("/v1/auth/register", json=user).json()["error"]["code"] == "email_taken"
    assert client.post("/v1/auth/register", json={"email": "nope", "password": "longenough"}).status_code == 400
    assert client.post("/v1/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 400


def test_password_is_hashed(client, user):
    from app.db import SessionLocal, User

    with SessionLocal() as db:
        stored = db.query(User).filter_by(email=user["email"]).one().password_hash
    assert user["password"] not in stored and stored.startswith("scrypt$")


def test_login_is_rate_limited(client, user):
    wrong = {**user, "password": "wrong password"}
    codes = [client.post("/v1/auth/login", json=wrong).status_code for _ in range(11)]
    assert codes[-1] == 429


def test_change_password_and_delete_account(client, user):
    new = "a brand new password"
    bad = client.post("/v1/account/password", json={"current_password": "nope", "new_password": new})
    assert bad.status_code == 401
    ok = client.post("/v1/account/password", json={"current_password": user["password"], "new_password": new})
    assert ok.status_code == 200
    key = make_key(client)
    assert client.post("/v1/account/delete", json={"password": new}).status_code == 204
    assert client.get("/v1/auth/me").status_code == 401
    assert upload(client, key).status_code == 401  # keys die with the account


# --- API keys ---------------------------------------------------------------------------------

def test_keys_require_login(client):
    assert client.get("/v1/keys").status_code == 401
    assert client.post("/v1/keys", json={"name": "x key"}).status_code == 401


def test_key_lifecycle(client, user):
    key = make_key(client)
    listed = client.get("/v1/keys").json()["data"]
    assert len(listed) == 1 and "key_hash_sha256" not in listed[0] and key not in str(listed)
    assert upload(client, key).status_code == 200
    assert client.get("/v1/keys").json()["data"][0]["request_count"] == 1
    assert client.post(f"/v1/keys/{listed[0]['id']}/revoke").status_code == 200
    assert upload(client, key).json()["error"]["message"] == "API key has been revoked."


def test_cannot_revoke_someone_elses_key(client, user):
    key_id = client.post("/v1/keys", json={"name": "mine"}).json()["record"]["id"]
    client.post("/v1/auth/logout")
    client.post("/v1/auth/register", json={"email": "thief@example.com", "password": "another password"})
    assert client.post(f"/v1/keys/{key_id}/revoke").status_code == 404


def test_scopes_are_enforced(client, user):
    key = make_key(client, scopes=["usage:read"])
    client.cookies.clear()
    assert upload(client, key).status_code == 403
    assert client.get("/v1/usage", headers={"Authorization": f"Bearer {key}"}).status_code == 200


# --- transcription ----------------------------------------------------------------------------

def test_transcription_requires_auth(client):
    assert upload(client).status_code == 401
    assert upload(client, "kth_live_fake").status_code == 401


def test_transcription_with_mock_engine(client, user):
    body = upload(client, make_key(client)).json()
    assert body["is_mock_engine"] is True and body["warnings"]
    assert body["normalization"]["is_code_switched"] is True
    assert body["audio_metadata"]["mime_type"] == "audio/wav"


def test_playground_uses_login_cookie(client, user):
    assert upload(client).status_code == 200


@pytest.mark.parametrize("data,code", [(b"", 400), (b"this is not audio at all", 415)])
def test_bad_audio_rejected(client, user, data, code):
    assert upload(client, data=data).status_code == code


def test_oversized_upload_rejected(client, user, monkeypatch):
    monkeypatch.setattr(settings, "kethra_max_upload_bytes", 1000)
    assert upload(client).status_code == 413


def test_unconfigured_engine_is_an_error_not_a_fake_transcript(client, user):
    r = upload(client, engine_id="gemini-3.5-transcribe")
    assert r.status_code == 503 and r.json()["error"]["code"] == "engine_not_configured"


def test_engine_failure_returns_502_without_leaking(client, user, monkeypatch):
    from app.adapters.base import ADAPTERS

    async def boom(_payload):
        raise RuntimeError("provider exploded with secret details")

    monkeypatch.setattr(ADAPTERS["mock-deterministic"], "transcribe_audio", boom)
    r = upload(client)
    assert r.status_code == 502 and "secret" not in r.text


def test_slow_engine_times_out(client, user, monkeypatch):
    import asyncio

    from app.adapters.base import ADAPTERS

    async def slow(_payload):
        await asyncio.sleep(5)

    monkeypatch.setattr(ADAPTERS["mock-deterministic"], "transcribe_audio", slow)
    monkeypatch.setattr(settings, "kethra_engine_timeout_seconds", 0.1)
    r = upload(client)
    assert r.status_code == 504 and r.json()["error"]["retryable"] is True


def test_rate_limit(client, user, monkeypatch):
    monkeypatch.setattr(settings, "kethra_rate_limit_per_minute", 2)
    assert [upload(client).status_code for _ in range(3)] == [200, 200, 429]


def test_usage_is_per_user(client, user):
    upload(client)
    upload(client, data=b"junk")
    usage = client.get("/v1/usage").json()
    assert usage["total_requests"] == 2 and usage["error_count"] == 1
    client.post("/v1/auth/logout")
    client.post("/v1/auth/register", json={"email": "fresh@example.com", "password": "another password"})
    assert client.get("/v1/usage").json()["total_requests"] == 0


# --- streaming --------------------------------------------------------------------------------

def test_stream_session_flow(client, user):
    token = client.post("/v1/auth/session-token").json()["token"]
    with client.websocket_connect(f"/v1/listen?token={token}") as ws:
        assert ws.receive_json()["type"] == "session.started"
        ws.send_json({"type": "audio.chunk", "audio_base64": base64.b64encode(wav_bytes()).decode()})
        event = ws.receive_json()
        assert event["type"] == "transcript.final" and event["is_mock_engine"] is True
        ws.send_json({"type": "audio.chunk", "audio_base64": "!!!"})
        assert ws.receive_json()["error"]["code"] == "invalid_audio"
        ws.send_json({"type": "session.complete"})
        assert ws.receive_json()["type"] == "session.completed"


def test_stream_token_is_single_use(client, user):
    token = client.post("/v1/auth/session-token").json()["token"]
    with client.websocket_connect(f"/v1/listen?token={token}") as ws:
        ws.receive_json()
    with client.websocket_connect(f"/v1/listen?token={token}") as ws:
        assert ws.receive_json()["error"]["code"] == "unauthorized_stream"


def test_stream_rejects_raw_api_key_in_url(client, user):
    key = make_key(client)
    with client.websocket_connect(f"/v1/listen?token={key}") as ws:
        assert ws.receive_json()["type"] == "error"
