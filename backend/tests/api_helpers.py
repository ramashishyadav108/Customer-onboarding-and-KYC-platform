"""HTTP-level helpers for integration tests (synthetic data only)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

DEMO_PASSWORDS = {
    "prospect1": "demo-prospect1-pass",
    "analyst1": "demo-analyst1-pass",
    "officer1": "demo-officer1-pass",
    "admin1": "demo-admin1-pass",
}
VALID_LEAD = {"name": "Test Person Alpha", "contact": "9999999921", "product": "Savings"}
VALID_PROFILE = {
    "date_of_birth": "1990-04-12",
    "annual_income": 3000000,
    "occupation_category": "SELF_EMPLOYED",
    "country_code": "IN",
    "state_code": "MH",
}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def staff_headers(client: TestClient, username: str = "analyst1") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": DEMO_PASSWORDS[username]}
    )
    assert response.status_code == 200, response.text
    return bearer(response.json()["access_token"])


def create_lead(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post("/api/v1/leads", json={**VALID_LEAD, **overrides})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def lead_headers(lead: dict[str, Any]) -> dict[str, str]:
    return bearer(lead["access_token"])


def count_rows(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
