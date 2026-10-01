"""Helpers for manual-review, admin and report tests (synthetic data only, data-models 5)."""

from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from api_helpers import staff_headers
from pipeline_helpers import PROFILE_C, PROFILE_D, step, submitted_case

SCENARIOS: dict[str, dict[str, Any]] = {
    "CLEAN": {"name": "Test Person Alpha"},
    "AML": {"name": "Test Person One"},
    "MEDIUM": {"name": "Test Person Gamma", "product": "Current", "profile": PROFILE_C},
    "HIGH": {"name": "Test Person Delta", "product": "NRE", "profile": PROFILE_D},
}
ROLES = ("prospect1", "analyst1", "officer1", "admin1")


def officer(client: TestClient) -> dict[str, str]:
    return staff_headers(client, "officer1")


def admin(client: TestClient) -> dict[str, str]:
    return staff_headers(client, "admin1")


def advance(client: TestClient, lead: dict[str, Any]) -> Response:
    return step(client, lead, "advance")


def case_in(client: TestClient, kind: str) -> dict[str, Any]:
    """Drive a scenario case through the pipeline (auto-advance is off in the default app)."""
    lead = submitted_case(client, **SCENARIOS[kind])
    response = advance(client, lead)
    assert response.status_code == 200, response.text
    return lead


def case_in_review(client: TestClient, kind: str = "AML") -> dict[str, Any]:
    lead = case_in(client, kind)
    assert response_state(client, lead) == "MANUAL_REVIEW"
    return lead


def response_state(client: TestClient, lead: dict[str, Any]) -> str:
    response = client.get(f"/api/v1/cases/{lead['case_id']}", headers=officer(client))
    return str(response.json()["state"])


def override(
    client: TestClient,
    lead: dict[str, Any],
    decision: str = "APPROVE",
    reason: str | None = "RISK_ACCEPTED",
    user: str = "officer1",
    **extra: Any,
) -> Response:
    body: dict[str, Any] = {"decision": decision, **extra}
    if reason is not None:
        body["reason_code"] = reason
    return client.post(
        f"/api/v1/cases/{lead['case_id']}/override", json=body, headers=staff_headers(client, user)
    )


def reclassify(
    client: TestClient,
    lead: dict[str, Any],
    band: str = "HIGH",
    reason: str | None = "SCORING_ERROR",
    user: str = "officer1",
    **extra: Any,
) -> Response:
    body: dict[str, Any] = {"band": band, **extra}
    if reason is not None:
        body["reason_code"] = reason
    return client.post(
        f"/api/v1/cases/{lead['case_id']}/reclassify",
        json=body,
        headers=staff_headers(client, user),
    )
