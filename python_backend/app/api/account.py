"""Registration, login/logout, and account settings for the website."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete

from ..config import settings
from ..db import ApiKey, LoginSession, Session, UsageRecord, get_db
from ..security import (
    LOGIN_SESSION_DAYS,
    SESSION_COOKIE,
    KethraError,
    authenticate_user,
    check_rate_limit,
    end_login_session,
    hash_password,
    register_user,
    require_user,
    start_login_session,
    validate_credentials,
    verify_password,
)

router = APIRouter(prefix="/v1", tags=["account"])


class Credentials(BaseModel):
    email: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PasswordConfirm(BaseModel):
    password: str


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, max_age=LOGIN_SESSION_DAYS * 86400,
        httponly=True, samesite="lax", secure=settings.kethra_cookie_secure, path="/",
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/auth/register", status_code=201)
def register(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    check_rate_limit(f"register:{_client_ip(request)}", per_minute=5)
    user = register_user(db, body.email, body.password)
    _set_cookie(response, start_login_session(db, user))
    return {"user": user.to_public()}


@router.post("/auth/login")
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    check_rate_limit(f"login-ip:{_client_ip(request)}", per_minute=10)
    check_rate_limit(f"login-email:{body.email.strip().lower()}", per_minute=10)
    user = authenticate_user(db, body.email, body.password)
    _set_cookie(response, start_login_session(db, user))
    return {"user": user.to_public()}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    end_login_session(db, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/auth/me")
def me(request: Request, db: Session = Depends(get_db)):
    return {"user": require_user(db, request).to_public()}


@router.post("/account/password")
def change_password(body: PasswordChange, request: Request, response: Response, db: Session = Depends(get_db)):
    user = require_user(db, request)
    check_rate_limit(f"password:{user.id}", per_minute=5)
    if not verify_password(body.current_password, user.password_hash):
        raise KethraError(401, "invalid_login", "Current password is incorrect.")
    validate_credentials(user.email, body.new_password)
    user.password_hash = hash_password(body.new_password)
    # Log out every other device.
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    db.commit()
    _set_cookie(response, start_login_session(db, user))
    return {"ok": True}


@router.post("/account/delete", status_code=204)
def delete_account(body: PasswordConfirm, request: Request, response: Response, db: Session = Depends(get_db)):
    user = require_user(db, request)
    check_rate_limit(f"password:{user.id}", per_minute=5)
    if not verify_password(body.password, user.password_hash):
        raise KethraError(401, "invalid_login", "Password is incorrect.")
    for model in (ApiKey, LoginSession, UsageRecord):
        db.execute(delete(model).where(model.user_id == user.id))
    db.delete(user)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
