from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.db import get_conn

COLUMNS = (
    "session_id",
    "application_id",
    "time_on_page",
    "buttons_clicked",
    "cursor_positions",
    "return_frequency",
)

MAX_BUTTONS = 8_192
MAX_CURSOR = 200_000


@dataclass
class BehaviorMetric:
    """
    CREATE TABLE IF NOT EXISTS behavior_metrics (
        id                SERIAL PRIMARY KEY,
        session_id        TEXT NOT NULL UNIQUE,
        application_id    INTEGER NOT NULL DEFAULT 0,
        time_on_page      INTEGER NOT NULL DEFAULT 0,
        buttons_clicked   TEXT NOT NULL DEFAULT '',
        cursor_positions  TEXT NOT NULL DEFAULT '',
        return_frequency  INTEGER NOT NULL DEFAULT 0,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """

    id: int | None = None
    session_id: str = ""
    application_id: int = 0
    time_on_page: int = 0
    buttons_clicked: str = ""
    cursor_positions: str = ""
    return_frequency: int = 0
    created_at: Any = None
    updated_at: Any = None


class BehaviorMetricCRUD:
    @staticmethod
    def _clip(value: Any, limit: int) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        return text[-limit:]

    @staticmethod
    def _payload(data: dict[str, Any]) -> dict[str, Any]:
        session_id = str(data.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("нужен session_id")
        return {
            "session_id": session_id[:128],
            "application_id": int(data.get("application_id") or 0),
            "time_on_page": max(0, int(data.get("time_on_page") or 0)),
            "buttons_clicked": BehaviorMetricCRUD._clip(data.get("buttons_clicked"), MAX_BUTTONS),
            "cursor_positions": BehaviorMetricCRUD._clip(data.get("cursor_positions"), MAX_CURSOR),
            "return_frequency": int(data.get("return_frequency") or 0),
        }

    @staticmethod
    def upsert(data: dict[str, Any]) -> dict[str, Any]:
        payload = BehaviorMetricCRUD._payload(data)
        names = ", ".join(COLUMNS)
        placeholders = ", ".join(f"%({key})s" for key in COLUMNS)
        assignments = ", ".join(
            f"{key} = EXCLUDED.{key}" for key in COLUMNS if key != "session_id"
        )
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO behavior_metrics ({names})
                VALUES ({placeholders})
                ON CONFLICT (session_id) DO UPDATE SET
                    {assignments},
                    updated_at = NOW()
                RETURNING *
                """,
                payload,
            )
            row = cur.fetchone()
        return dict(row)

    @staticmethod
    def list(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM behavior_metrics
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]
