"""Test helpers shared by unit and integration tests (synthetic data only)."""

import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from sqlalchemy import Connection, text

JWT_SECRET = "test-secret-not-real-0123456789-abcdefghij"
NOW = "2026-10-01T09:30:00+00:00"


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def make_token(role: str = "kyc-analyst", secret: str = JWT_SECRET, ttl: int = 600) -> str:
    claims = {"sub": "tester", "role": role, "exp": int(time.time()) + ttl}
    return jwt.encode(claims, secret, algorithm="HS256")


def auth_header(role: str = "kyc-analyst") -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(role)}"}


def ensure_template(conn: Connection, product: str, version: int) -> None:
    """Insert a checklist template row if the seed migration has not already."""
    found = conn.execute(
        text("SELECT 1 FROM checklist_templates WHERE product = :p AND version = :v"),
        {"p": product, "v": version},
    ).first()
    if found is None:
        conn.execute(
            text(
                "INSERT INTO checklist_templates (product, version, created_at) VALUES (:p, :v, :t)"
            ),
            {"p": product, "v": version, "t": NOW},
        )


def insert_case(
    conn: Connection,
    state: str = "INITIATED",
    product: str = "Savings",
    checklist_version: int = 1,
) -> str:
    """Insert a synthetic case row and return its case_id."""
    ensure_template(conn, product, checklist_version)
    case_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO cases (case_id, name, contact, product, state, checklist_version,"
            " created_at, updated_at) VALUES (:id, 'Test Person One', '9999999921', :p, :s, :v,"
            " :t, :t)"
        ),
        {"id": case_id, "p": product, "s": state, "v": checklist_version, "t": NOW},
    )
    return case_id


class FakeClock:
    """Mutable UTC clock for deterministic tests (starts at the real current time)."""

    def __init__(self) -> None:
        self._now = datetime.now(UTC).replace(microsecond=0)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        self._now += timedelta(seconds=seconds)
