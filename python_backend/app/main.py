"""Kethra API entry point. Run: `uvicorn app.main:app --reload` from python_backend/."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import account, keys, speech
from .config import REPO_ROOT
from .db import init_db
from .security import KethraError

log = logging.getLogger("kethra")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Kethra API", version="0.2.0", lifespan=lifespan,
              description="Khmer-English code-switching speech recognition.")


def _error(status: int, code: str, message: str, retryable: bool = False) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "retryable": retryable}}, status_code=status)


@app.exception_handler(KethraError)
async def kethra_error(_request: Request, e: KethraError):
    return _error(e.status, e.code, e.message, e.retryable)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, e: RequestValidationError):
    first = e.errors()[0] if e.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:])
    return _error(400, "invalid_request", f"{field}: {first.get('msg', 'invalid value')}".strip(": "))


@app.exception_handler(Exception)
async def unexpected_error(_request: Request, e: Exception):
    log.exception("unhandled error")
    return _error(500, "internal_error", "Something went wrong on our side.", retryable=True)


for module in (account, keys, speech):
    app.include_router(module.router)

# Serve the built website (npm run build) from the same origin in production.
_dist = REPO_ROOT / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
