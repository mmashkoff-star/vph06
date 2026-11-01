"""Драйвер PostgreSQL. Хост postgres доступен только из сети data."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


def _password() -> str:
    raw = os.environ.get("POSTGRES_PASSWORD", "")
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        return raw[1:-1]
    return raw


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "deluxe"),
        password=_password(),
        dbname=os.environ.get("POSTGRES_DB", "deluxe_auto"),
        row_factory=dict_row,
        connect_timeout=5,
    )


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    from app.models.admin import AdminSettings
    from app.models.admin_user import AdminUser
    from app.models.behavior import Behavior
    from app.models.behavior_metric import BehaviorMetric
    from app.models.lead import Lead

    statements = [
        Lead.__doc__,
        Behavior.__doc__,
        BehaviorMetric.__doc__,
        AdminSettings.__doc__,
        AdminUser.__doc__,
    ]
    with get_conn() as conn:
        with conn.cursor() as cur:
            for sql in statements:
                if not sql:
                    raise RuntimeError("у модели нет SQL в docstring")
                cur.execute(sql)
        from app.models.admin import AdminCRUD
        from app.models.admin_user import AdminUserCRUD

        AdminCRUD.ensure_default(conn)
    AdminUserCRUD.ensure_schema()
