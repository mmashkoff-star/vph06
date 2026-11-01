from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import (
    create_access_token,
    hash_password,
    public_admin,
    require_admin,
    verify_password,
)
from app.models.admin_user import AdminUserCRUD, clean_email

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,64}$")


class AuthIn(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class RegisterIn(AuthIn):
    email: str = Field(min_length=5, max_length=254)


def _clean_login(raw: str) -> str:
    login = raw.strip()
    if not LOGIN_RE.fullmatch(login):
        raise HTTPException(status_code=422, detail="логин: 3–64 символа, латиница, цифры, ._@-")
    return login


def _token_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "access_token": create_access_token(row["id"], row["login"]),
        "token_type": "bearer",
        "admin": public_admin(row),
    }


@router.get("/status")
def auth_status() -> dict[str, bool]:
    return {"has_admin": AdminUserCRUD.count() > 0}


@router.post("/register")
def register(data: RegisterIn) -> dict[str, Any]:
    if AdminUserCRUD.count() > 0:
        raise HTTPException(status_code=403, detail="регистрация закрыта: админ уже есть")
    login = _clean_login(data.login)
    try:
        email = clean_email(data.email)
        row = AdminUserCRUD.create(login, email, hash_password(data.password))
    except ValueError as exc:
        status = 422 if "e-mail" in str(exc) and "занят" not in str(exc) else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return _token_payload(row)


@router.post("/login")
def login(data: AuthIn) -> dict[str, Any]:
    login = _clean_login(data.login)
    row = AdminUserCRUD.get_by_login(login)
    if row is None or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="неверный логин или пароль")
    return _token_payload(row)


@router.get("/me")
def me(admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    return admin


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/password")
def change_password(
    data: PasswordChange,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    row = AdminUserCRUD.get(admin["id"])
    if row is None:
        raise HTTPException(status_code=401, detail="админ не найден")
    if not verify_password(data.current_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="текущий пароль неверный")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail="новый пароль совпадает с текущим")
    updated = AdminUserCRUD.update(admin["id"], {"password_hash": hash_password(data.new_password)})
    return public_admin(updated or row)
