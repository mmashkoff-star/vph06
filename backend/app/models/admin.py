from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from psycopg.types.json import Json

from app.core.db import get_conn

DEFAULT_WORK_TYPES = {
    "Диагностика и ТО": ["Плановое ТО", "Диагностика", "Замена расходников", "Подготовка к сезону"],
    "Детейлинг и керамика": ["Детейлинг", "Полировка ЛКП", "Керамическое покрытие", "Мойка премиум"],
    "Антигравий PPF": ["Оклейка PPF", "Зоны риска", "Полный кузов", "Замена плёнки"],
    "Кузов и цвет": ["Кузовной ремонт", "Локальная покраска", "Подбор эмали", "Удаление сколов"],
    "Салон и кожа": ["Реставрация кожи", "Алькантара", "Дерево и хром", "Химчистка салона"],
    "Сезонное сопровождение": ["Подготовка к сезону", "Хранение", "Выезд мастера", "Персональный слот"],
}

DEFAULT_SERVICES = [
    {
        "key": "diagnostics",
        "title": "Диагностика и ТО",
        "description": "Дилерский регламент для Porsche, Bentley, Mercedes-Maybach, Rolls-Royce",
        "work_types": DEFAULT_WORK_TYPES["Диагностика и ТО"],
        "budget_min": "80000",
        "budget_max": "450000",
        "budget_step": "10000",
    },
    {
        "key": "detailing",
        "title": "Детейлинг и керамика",
        "description": "Полировка, покрытие кузова, уход за ЛКП без компромиссов",
        "work_types": DEFAULT_WORK_TYPES["Детейлинг и керамика"],
        "budget_min": "120000",
        "budget_max": "900000",
        "budget_step": "20000",
    },
    {
        "key": "ppf",
        "title": "Антигравий PPF",
        "description": "Оклейка полиуретаном зон риска или всего кузова",
        "work_types": DEFAULT_WORK_TYPES["Антигравий PPF"],
        "budget_min": "250000",
        "budget_max": "2800000",
        "budget_step": "50000",
    },
    {
        "key": "body",
        "title": "Кузов и цвет",
        "description": "Локальный ремонт, подбор эмали, сохранение заводской фактуры",
        "work_types": DEFAULT_WORK_TYPES["Кузов и цвет"],
        "budget_min": "180000",
        "budget_max": "3500000",
        "budget_step": "50000",
    },
    {
        "key": "interior",
        "title": "Салон и кожа",
        "description": "Реставрация кожи, алькантары, дерева и хрома",
        "work_types": DEFAULT_WORK_TYPES["Салон и кожа"],
        "budget_min": "100000",
        "budget_max": "1500000",
        "budget_step": "25000",
    },
    {
        "key": "concierge",
        "title": "Сезонное сопровождение",
        "description": "Хранение, выдача, выезд мастера и персональный слот",
        "work_types": DEFAULT_WORK_TYPES["Сезонное сопровождение"],
        "budget_min": "200000",
        "budget_max": "6000000",
        "budget_step": "50000",
    },
]


def _as_money(value: Any, fallback: str) -> str:
    raw = str(value if value not in (None, "") else fallback).replace(" ", "").replace("\u00a0", "")
    digits = re.sub(r"[^\d]", "", raw)
    return digits or fallback


def _as_work_types(value: Any, title: str) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        items = [str(part).strip() for part in value]
    else:
        items = list(DEFAULT_WORK_TYPES.get(title, []))
    return [item for item in items if item]


def _as_key(value: Any, title: str, index: int) -> str:
    raw = str(value or "").strip().lower()
    key = re.sub(r"[^a-z0-9-]+", "-", raw).strip("-")
    if key:
        return key
    return f"svc-{index + 1}"


def normalize_service(item: Any, index: int, fallback: dict[str, str]) -> dict[str, Any]:
    data = item if isinstance(item, dict) else {"title": str(item or "")}
    title = str(data.get("title") or data.get("key") or "").strip()
    catalog = next((row for row in DEFAULT_SERVICES if row["title"] == title or row["key"] == data.get("key")), None)
    base = catalog or {}
    return {
        "key": _as_key(data.get("key") or base.get("key"), title, index),
        "title": title,
        "description": str(data.get("description") or base.get("description") or "").strip(),
        "work_types": _as_work_types(data.get("work_types"), title) or list(base.get("work_types") or []),
        "budget_min": _as_money(data.get("budget_min"), base.get("budget_min") or fallback["budget_min"]),
        "budget_max": _as_money(data.get("budget_max"), base.get("budget_max") or fallback["budget_max"]),
        "budget_step": _as_money(data.get("budget_step"), base.get("budget_step") or fallback["budget_step"]),
    }


def normalize_settings(data: dict[str, Any] | None) -> dict[str, Any]:
    raw = data or {}
    fallback = {
        "budget_min": _as_money(raw.get("budget_min"), "200000"),
        "budget_max": _as_money(raw.get("budget_max"), "6000000"),
        "budget_step": _as_money(raw.get("budget_step"), "50000"),
    }
    source = raw.get("services")
    if not isinstance(source, list) or not source:
        services = [normalize_service(item, index, fallback) for index, item in enumerate(DEFAULT_SERVICES)]
    else:
        services = [normalize_service(item, index, fallback) for index, item in enumerate(source)]
    return {
        "services": services,
        "budget_min": fallback["budget_min"],
        "budget_max": fallback["budget_max"],
        "budget_step": fallback["budget_step"],
    }


@dataclass
class AdminSettings:
    """
    CREATE TABLE IF NOT EXISTS admin_settings (
        id           SERIAL PRIMARY KEY,
        services     JSONB NOT NULL DEFAULT '[]'::jsonb,
        budget_min   TEXT NOT NULL DEFAULT '50000',
        budget_max   TEXT NOT NULL DEFAULT '5000000',
        budget_step  TEXT NOT NULL DEFAULT '50000',
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """

    id: int | None = None
    services: list | None = None
    budget_min: str = "200000"
    budget_max: str = "6000000"
    budget_step: str = "50000"
    updated_at: Any = None


class AdminCRUD:
    @staticmethod
    def _payload(data: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_settings(data)
        return {
            "services": Json(normalized["services"]),
            "budget_min": normalized["budget_min"],
            "budget_max": normalized["budget_max"],
            "budget_step": normalized["budget_step"],
        }

    @staticmethod
    def _row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        normalized = normalize_settings(row)
        return {**row, **normalized}

    @staticmethod
    def ensure_default(conn: Any | None = None) -> dict[str, Any]:
        def _run(cur: Any) -> dict[str, Any]:
            cur.execute("SELECT * FROM admin_settings ORDER BY id ASC LIMIT 1")
            row = cur.fetchone()
            if row:
                return AdminCRUD._row(dict(row))
            payload = AdminCRUD._payload({})
            cur.execute(
                """
                INSERT INTO admin_settings (services, budget_min, budget_max, budget_step)
                VALUES (%(services)s, %(budget_min)s, %(budget_max)s, %(budget_step)s)
                RETURNING *
                """,
                payload,
            )
            return AdminCRUD._row(dict(cur.fetchone()))

        if conn is not None:
            with conn.cursor() as cur:
                return _run(cur)
        with get_conn() as owned, owned.cursor() as cur:
            return _run(cur)

    @staticmethod
    def create(data: dict[str, Any]) -> dict[str, Any]:
        payload = AdminCRUD._payload(data)
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO admin_settings (services, budget_min, budget_max, budget_step)
                VALUES (%(services)s, %(budget_min)s, %(budget_max)s, %(budget_step)s)
                RETURNING *
                """,
                payload,
            )
            row = cur.fetchone()
        return AdminCRUD._row(dict(row))

    @staticmethod
    def get(settings_id: int) -> dict[str, Any] | None:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM admin_settings WHERE id = %s", (settings_id,))
            row = cur.fetchone()
        return AdminCRUD._row(dict(row)) if row else None

    @staticmethod
    def get_current() -> dict[str, Any] | None:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM admin_settings ORDER BY id ASC LIMIT 1")
            row = cur.fetchone()
        return AdminCRUD._row(dict(row)) if row else None

    @staticmethod
    def list(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM admin_settings ORDER BY id ASC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
        return [AdminCRUD._row(dict(row)) for row in rows]

    @staticmethod
    def update(settings_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        current = AdminCRUD.get(settings_id)
        if current is None:
            return None
        merged = {
            "services": data["services"] if "services" in data else current["services"],
            "budget_min": data.get("budget_min", current["budget_min"]),
            "budget_max": data.get("budget_max", current["budget_max"]),
            "budget_step": data.get("budget_step", current["budget_step"]),
        }
        payload = AdminCRUD._payload(merged)
        payload["id"] = settings_id
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE admin_settings
                SET services = %(services)s,
                    budget_min = %(budget_min)s,
                    budget_max = %(budget_max)s,
                    budget_step = %(budget_step)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                RETURNING *
                """,
                payload,
            )
            row = cur.fetchone()
        return AdminCRUD._row(dict(row)) if row else None

    @staticmethod
    def delete(settings_id: int) -> bool:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM admin_settings WHERE id = %s RETURNING id", (settings_id,))
            row = cur.fetchone()
        return row is not None
