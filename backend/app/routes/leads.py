from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.lead_insight import enrich_lead, summarize_leads
from app.models.behavior import BehaviorCRUD
from app.models.lead import LeadCRUD

router = APIRouter(prefix="/leads", tags=["leads"])


class LeadIn(BaseModel):
    last_name: str = ""
    first_name: str = ""
    patronymic: str = ""
    phone: str = ""
    email: str = ""
    make: str = ""
    model: str = ""
    year: str = ""
    vehicle_details: str = ""
    service: str = ""
    work_type: str = ""
    work_area: str = ""
    visit_format: str = ""
    booked_by: str = ""
    needed_by: str = ""
    budget: str = ""
    preferred_contact: str = ""
    convenient_time: str = ""
    comments: str = ""


class BehaviorIn(BaseModel):
    time_on_page_ms: int = 0
    return_count: int = 0
    buttons_clicked: list[Any] = Field(default_factory=list)
    cursor_hovers: list[Any] = Field(default_factory=list)
    user_agent: str = ""
    language: str = ""
    timezone: str = ""
    screen_width: int | None = None
    screen_height: int | None = None
    referrer: str = ""
    page_url: str = ""
    tech: dict[str, Any] = Field(default_factory=dict)


class LeadPackage(LeadIn):
    behavior: BehaviorIn | None = None


@router.post("")
def create_lead(
    package: LeadPackage,
    x_real_ip: str | None = Header(default=None, alias="X-Real-IP"),
) -> dict[str, Any]:
    lead = LeadCRUD.create(package.model_dump(exclude={"behavior"}))
    behavior = None
    if package.behavior is not None:
        payload = package.behavior.model_dump()
        tech = dict(payload.get("tech") or {})
        if x_real_ip:
            tech.setdefault("ip", x_real_ip)
        payload["tech"] = tech
        behavior = BehaviorCRUD.create(payload, lead_id=lead["id"])
    return {"lead": lead, "behavior": behavior}


@router.get("")
def list_leads(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return [enrich_lead(row) for row in LeadCRUD.list(limit=limit, offset=offset)]


@router.get("/queue")
def leads_queue(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    rows = [enrich_lead(row) for row in LeadCRUD.list(limit=limit, offset=offset)]
    rows.sort(key=lambda row: (-int(row["insight"]["score"]), int(row["id"])))
    return {"summary": summarize_leads(rows), "leads": rows}


@router.get("/{lead_id}")
def get_lead(lead_id: int) -> dict[str, Any]:
    lead = LeadCRUD.get(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="заявка не найдена")
    return {"lead": enrich_lead(lead), "behavior": BehaviorCRUD.get(lead_id)}


@router.patch("/{lead_id}")
def update_lead(lead_id: int, data: LeadIn) -> dict[str, Any]:
    row = LeadCRUD.update(lead_id, data.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=404, detail="заявка не найдена")
    return row


@router.delete("/{lead_id}")
def delete_lead(lead_id: int) -> dict[str, bool]:
    if not LeadCRUD.delete(lead_id):
        raise HTTPException(status_code=404, detail="заявка не найдена")
    return {"ok": True}
