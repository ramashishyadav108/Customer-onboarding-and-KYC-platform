"""NFR-03 / NFR-06: review, admin and report flows log JSON with ids and never PII."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api_helpers import create_lead
from pipeline_helpers import PROFILE_A, put_profile, step, upload_all
from review_helpers import admin, officer

NAME = "Zorblax Quentinsen"
EMAIL = "zorblax.quentinsen@example.com"
COMMENT = "Confidential remark about Zorblax and 9999999921"


def lines(output: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def watch_listed_case(client: TestClient) -> dict[str, Any]:
    """A case that hits the watchlist under a name we then add as an entry."""
    lead = create_lead(client, name=NAME, contact=EMAIL)
    put_profile(client, lead, PROFILE_A)
    upload_all(client, lead, "Savings")
    client.post(f"/api/v1/cases/{lead['case_id']}/submit", headers=_owner(lead))
    return lead


def _owner(lead: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {lead['access_token']}"}


@pytest.mark.nfr("NFR-03")
@pytest.mark.nfr("NFR-06")
def test_nfr03_review_admin_and_report_flows_log_no_pii_and_carry_ids(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """Watchlist add, screen, override with a comment, reclassify, reports: no PII in logs;
    the override log line has case_id and the request correlation id."""
    capsys.readouterr()
    head = admin(client)
    client.post(
        "/api/v1/admin/watchlist",
        json={"name": NAME, "aliases": [], "list_type": "AML"},
        headers=head,
    )
    lead = watch_listed_case(client)
    cid = lead["case_id"]
    step(client, lead, "advance")
    boss = officer(client)
    client.get(f"/api/v1/cases/{cid}/evidence", headers=boss)
    client.get("/api/v1/review-queue", headers=boss)
    client.post(
        f"/api/v1/cases/{cid}/reclassify",
        json={"band": "MEDIUM", "reason_code": "SCORING_ERROR", "comment": COMMENT},
        headers=boss,
    )
    client.post(
        f"/api/v1/cases/{cid}/override",
        json={"decision": "REJECT", "reason_code": "CONFIRMED_WATCHLIST_MATCH", "comment": COMMENT},
        headers={**boss, "X-Correlation-ID": "corr-review-77"},
    )
    for path in ("tat", "funnel", "backlog", "rejection-reasons", "auto-approval"):
        client.get(f"/api/v1/admin/reports/{path}", headers=head)
    out = capsys.readouterr().out
    for secret in (
        NAME,
        "Zorblax",
        "Quentinsen",
        EMAIL,
        "example.com",
        "Confidential",
        "9999999921",
    ):
        assert secret not in out, secret
    records = lines(out)
    assert all({"timestamp", "level", "correlation_id", "message"} <= set(r) for r in records)
    applied = [r for r in records if r["message"] == "override applied"]
    assert len(applied) == 1
    assert applied[0]["case_id"] == cid and applied[0]["correlation_id"] == "corr-review-77"
    assert applied[0]["decision"] == "REJECT"
