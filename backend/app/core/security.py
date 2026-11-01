from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="JWT",
    description="Вставьте access_token из POST /api/auth/login. Слово Bearer писать не нужно.",
)

from app.models.admin_user import AdminUserCRUD

PBKDF2_ROUNDS = 200_000
TOKEN_TTL_SEC = 60 * 60 * 12


def _secret() -> str:
    raw = os.environ.get("JWT_SECRET", "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        raw = raw[1:-1]
    if not raw:
        raise HTTPException(status_code=500, detail="не задан JWT_SECRET")
    return raw


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS)
    return f"pbkdf2${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if kind != "pbkdf2":
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS).hex()
    return hmac.compare_digest(check, digest)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def create_access_token(admin_id: int, login: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    now = int(time.time())
    payload = {"sub": str(admin_id), "login": login, "iat": now, "exp": now + TOKEN_TTL_SEC}
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing = f"{header}.{body}".encode("utf-8")
    sig = hmac.new(_secret().encode("utf-8"), signing, hashlib.sha256).digest()
    return f"{header}.{body}.{_b64url(sig)}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        header_b64, body_b64, sig_b64 = token.split(".")
        signing = f"{header_b64}.{body_b64}".encode("utf-8")
        expected = hmac.new(_secret().encode("utf-8"), signing, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
            return None
        payload = json.loads(_b64url_decode(body_b64))
        if int(payload.get("exp") or 0) < int(time.time()):
            return None
        return payload
    except (ValueError, json.JSONDecodeError, TypeError):
        return None


def public_admin(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "login": row["login"],
        "email": row.get("email") or "",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="нужен JWT-токен")
    token = creds.credentials.strip()
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="токен недействителен")
    try:
        admin_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="токен недействителен") from None
    row = AdminUserCRUD.get(admin_id)
    if row is None:
        raise HTTPException(status_code=401, detail="админ не найден")
    return public_admin(row)
