from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from psycopg.errors import UniqueViolation

from app.core.db import get_conn

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean_email(raw: str) -> str:
    email = str(raw or "").strip().lower()
    if not EMAIL_RE.fullmatch(email) or len(email) > 254:
        raise ValueError("укажите корректный e-mail")
    return email


@dataclass
class AdminUser:
    """
    CREATE TABLE IF NOT EXISTS admins (
        id             SERIAL PRIMARY KEY,
        login          TEXT NOT NULL UNIQUE,
        email          TEXT NOT NULL UNIQUE,
        password_hash  TEXT NOT NULL,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """

    id: int | None = None
    login: str = ""
    email: str = ""
    password_hash: str = ""
    created_at: Any = None
    updated_at: Any = None


def _unique_error(exc: UniqueViolation) -> ValueError:
    text = str(exc).lower()
    if "email" in text:
        return ValueError("e-mail уже занят")
    return ValueError("логин уже занят")


class AdminUserCRUD:
    @staticmethod
    def ensure_schema() -> None:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("ALTER TABLE admins ADD COLUMN IF NOT EXISTS email TEXT")
            cur.execute(
                """
                UPDATE admins
                SET email = lower(login) || '@deluxe-auto.local'
                WHERE email IS NULL OR btrim(email) = ''
                """
            )
            cur.execute("ALTER TABLE admins ALTER COLUMN email SET NOT NULL")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS admins_email_key ON admins (email)")

    @staticmethod
    def create(login: str, email: str, password_hash: str) -> dict[str, Any]:
        with get_conn() as conn, conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO admins (login, email, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING *
                    """,
                    (login, email, password_hash),
                )
            except UniqueViolation as exc:
                raise _unique_error(exc) from exc
            row = cur.fetchone()
        return dict(row)

    @staticmethod
    def get(admin_id: int) -> dict[str, Any] | None:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM admins WHERE id = %s", (admin_id,))
            row = cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_by_login(login: str) -> dict[str, Any] | None:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM admins WHERE login = %s", (login,))
            row = cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    def list(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM admins ORDER BY id ASC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def count() -> int:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM admins")
            row = cur.fetchone()
        return int(row["n"] if row else 0)

    @staticmethod
    def update(admin_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        current = AdminUserCRUD.get(admin_id)
        if current is None:
            return None
        login = str(data.get("login") or current["login"]).strip()
        email = str(data.get("email") or current.get("email") or "").strip().lower()
        password_hash = data.get("password_hash") or current["password_hash"]
        with get_conn() as conn, conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    UPDATE admins
                    SET login = %s,
                        email = %s,
                        password_hash = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (login, email, password_hash, admin_id),
                )
            except UniqueViolation as exc:
                raise _unique_error(exc) from exc
            row = cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    def delete(admin_id: int) -> bool:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM admins WHERE id = %s RETURNING id", (admin_id,))
            row = cur.fetchone()
        return row is not None
