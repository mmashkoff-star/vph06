from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import hash_password, public_admin, require_admin
from app.models.admin_user import AdminUserCRUD, clean_email

router = APIRouter(prefix="/admins", tags=["admins"])

LOGIN_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,64}$")


class AdminUserCreate(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class AdminUserUpdate(BaseModel):
    login: str | None = Field(default=None, min_length=3, max_length=64)
    email: str | None = Field(default=None, min_length=5, max_length=254)
    password: str | None = Field(default=None, min_length=8, max_length=128)


def _clean_login(raw: str) -> str:
    login = raw.strip()
    if not LOGIN_RE.fullmatch(login):
        raise HTTPException(status_code=422, detail="логин: 3–64 символа, латиница, цифры, ._@-")
    return login


@router.get("")
def list_admins(_admin: dict[str, Any] = Depends(require_admin)) -> list[dict[str, Any]]:
    return [public_admin(row) for row in AdminUserCRUD.list()]


@router.get("/{admin_id}")
def get_admin_user(admin_id: int, _admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    row = AdminUserCRUD.get(admin_id)
    if row is None:
        raise HTTPException(status_code=404, detail="админ не найден")
    return public_admin(row)


@router.post("")
def create_admin_user(
    data: AdminUserCreate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    login = _clean_login(data.login)
    try:
        email = clean_email(data.email)
        row = AdminUserCRUD.create(login, email, hash_password(data.password))
    except ValueError as exc:
        status = 422 if "e-mail" in str(exc) and "занят" not in str(exc) else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return public_admin(row)


@router.patch("/{admin_id}")
def update_admin_user(
    admin_id: int,
    data: AdminUserUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if data.login is not None:
        payload["login"] = _clean_login(data.login)
    if data.email is not None:
        try:
            payload["email"] = clean_email(data.email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if data.password is not None:
        payload["password_hash"] = hash_password(data.password)
    try:
        row = AdminUserCRUD.update(admin_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="админ не найден")
    return public_admin(row)


@router.delete("/{admin_id}")
def delete_admin_user(
    admin_id: int,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, bool]:
    if admin["id"] == admin_id and AdminUserCRUD.count() <= 1:
        raise HTTPException(status_code=400, detail="нельзя удалить последнего админа")
    if not AdminUserCRUD.delete(admin_id):
        raise HTTPException(status_code=404, detail="админ не найден")
    return {"ok": True}
