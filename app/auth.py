"""Single-owner browser authentication for the private dashboard."""

import base64
import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware


COOKIE_NAME = "mage_session"
SESSION_SECONDS = 12 * 60 * 60
router = APIRouter()
_failed_logins: dict[str, tuple[int, float]] = {}


def _auth_config() -> dict[str, str]:
    path = os.getenv("DASHBOARD_AUTH_FILE", "")
    if not path:
        raise RuntimeError("DASHBOARD_AUTH_FILE is not configured")
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
        if not all(isinstance(config[key], str) and config[key] for key in ("salt", "password_hash", "session_key")):
            raise ValueError("Invalid dashboard auth configuration")
        return config
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("Dashboard authentication is unavailable") from exc


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _key(config: dict[str, str]) -> bytes:
    return _decode(config["session_key"])


def _password_matches(password: str, config: dict[str, str]) -> bool:
    candidate = hashlib.scrypt(password.encode("utf-8"), salt=_decode(config["salt"]), n=2**14, r=8, p=1)
    return hmac.compare_digest(candidate, _decode(config["password_hash"]))


def _new_session(config: dict[str, str]) -> str:
    payload = f"{int(time.time())}.{secrets.token_urlsafe(24)}"
    signature = hmac.new(_key(config), payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{_encode(signature)}"


def _valid_session(token: str | None, config: dict[str, str]) -> bool:
    if not token or len(token) > 256:
        return False
    try:
        issued, nonce, signature = token.split(".")
        timestamp = int(issued)
        if not nonce or not (0 <= time.time() - timestamp <= SESSION_SECONDS):
            return False
        expected = hmac.new(_key(config), f"{issued}.{nonce}".encode(), hashlib.sha256).digest()
        return hmac.compare_digest(expected, _decode(signature))
    except (ValueError, UnicodeError, binascii.Error):
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/health", "/login", "/auth/login"}:
            return await call_next(request)
        try:
            config = _auth_config()
        except RuntimeError:
            return JSONResponse({"detail": "Dashboard authentication is unavailable"}, status_code=503)
        if not _valid_session(request.cookies.get(COOKIE_NAME), config):
            if request.method == "GET" and request.url.path == "/":
                return RedirectResponse("/login", status_code=303)
            return JSONResponse({"detail": "Sign in required"}, status_code=401)
        return await call_next(request)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


@router.get("/login")
def login_page() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parent / "static" / "login.html")


@router.post("/auth/login")
def login(body: LoginRequest, request: Request):
    address = request.client.host if request.client else "unknown"
    count, until = _failed_logins.get(address, (0, 0.0))
    if until > time.monotonic():
        raise HTTPException(429, "Too many attempts; try again in 15 minutes")
    try:
        config = _auth_config()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not _password_matches(body.password, config):
        count += 1
        _failed_logins[address] = (count, time.monotonic() + 900 if count >= 5 else 0.0)
        raise HTTPException(401, "Incorrect password")
    _failed_logins.pop(address, None)
    response = JSONResponse({"ok": True})
    response.set_cookie(
        COOKIE_NAME, _new_session(config), max_age=SESSION_SECONDS,
        httponly=True, samesite="strict", secure=request.url.scheme == "https", path="/",
    )
    return response


@router.post("/auth/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response
