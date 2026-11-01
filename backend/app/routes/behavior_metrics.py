from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.models.behavior_metric import BehaviorMetricCRUD

router = APIRouter(prefix="/behavior-metrics", tags=["behavior-metrics"])


class BehaviorMetricIn(BaseModel):
    application_id: int = 0
    time_on_page: int = 0
    buttons_clicked: str = ""
    cursor_positions: str = ""
    return_frequency: int = 0
    session_id: str | None = Field(default=None, max_length=128)


def _save(data: BehaviorMetricIn) -> dict[str, Any]:
    payload = data.model_dump()
    payload["session_id"] = (data.session_id or "").strip() or secrets.token_hex(16)
    row = BehaviorMetricCRUD.upsert(payload)
    return {
        "id": row["id"],
        "application_id": row["application_id"],
        "time_on_page": row["time_on_page"],
        "return_frequency": row["return_frequency"],
    }


@router.post("")
@router.post("/")
def create_behavior_metric(data: BehaviorMetricIn) -> dict[str, Any]:
    return _save(data)


@router.get("")
@router.get("/")
def list_behavior_metrics(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return BehaviorMetricCRUD.list(limit=limit, offset=offset)
