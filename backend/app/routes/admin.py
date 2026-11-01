from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import require_admin
from app.models.admin import AdminCRUD

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminIn(BaseModel):
    services: list[dict[str, Any]] | None = None
    budget_min: str | None = None
    budget_max: str | None = None
    budget_step: str | None = None


class AdminCreate(BaseModel):
    services: list[dict[str, Any]] = Field(default_factory=list)
    budget_min: str = "200000"
    budget_max: str = "6000000"
    budget_step: str = "50000"


@router.get("")
def get_admin() -> dict[str, Any]:
    row = AdminCRUD.get_current()
    if row is None:
        row = AdminCRUD.ensure_default()
    return row


@router.get("/{settings_id}")
def get_admin_by_id(settings_id: int) -> dict[str, Any]:
    row = AdminCRUD.get(settings_id)
    if row is None:
        raise HTTPException(status_code=404, detail="настройки не найдены")
    return row


@router.post("")
def create_admin(data: AdminCreate, _admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    return AdminCRUD.create(data.model_dump())


@router.patch("/{settings_id}")
def update_admin(
    settings_id: int,
    data: AdminIn,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    row = AdminCRUD.update(settings_id, data.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=404, detail="настройки не найдены")
    return row


@router.delete("/{settings_id}")
def delete_admin(settings_id: int, _admin: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    if not AdminCRUD.delete(settings_id):
        raise HTTPException(status_code=404, detail="настройки не найдены")
    return {"ok": True}
