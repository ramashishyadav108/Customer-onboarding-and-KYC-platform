"""AC-01 / NFR-03 / E1-S3: idempotency and PII-safe logging."""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import (
    VALID_LEAD,
    VALID_PROFILE,
    count_rows,
    create_lead,
    lead_headers,
)


@pytest.mark.ac("AC-01")
def test_ac01_6_same_idempotency_key_returns_same_case_with_200(
    client: TestClient, engine: Engine
) -> None:
    """AC-01.6: the same Idempotency-Key returns the same case_id (200) and one case row."""
    headers = {"Idempotency-Key": "lead-key-1"}
    first = client.post("/api/v1/leads", json=VALID_LEAD, headers=headers)
    second = client.post("/api/v1/leads", json=VALID_LEAD, headers=headers)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["case_id"] == second.json()["case_id"]
    assert second.json()["access_token"]
    assert count_rows(engine, "cases") == 1 and count_rows(engine, "state_history") == 1
    assert count_rows(engine, "audit_log") == 1


@pytest.mark.ac("AC-01")
def test_ac01_6_replay_with_a_different_payload_is_422(client: TestClient, engine: Engine) -> None:
    """api-contracts: a replayed key with a different payload is 422 on Idempotency-Key."""
    headers = {"Idempotency-Key": "lead-key-2"}
    client.post("/api/v1/leads", json=VALID_LEAD, headers=headers)
    response = client.post("/api/v1/leads", json={**VALID_LEAD, "product": "NRE"}, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"][0]["field"] == "Idempotency-Key"
    assert count_rows(engine, "cases") == 1


@pytest.mark.ac("AC-01")
def test_ac01_6_without_a_key_each_post_creates_a_case(client: TestClient, engine: Engine) -> None:
    """AC-01.6: no key, no deduplication."""
    a, b = create_lead(client), create_lead(client)
    assert a["case_id"] != b["case_id"] and count_rows(engine, "cases") == 2


@pytest.mark.ac("AC-01")
def test_ac01_6_replayed_token_is_bound_to_the_same_case(client: TestClient) -> None:
    """DD-6: the token returned on replay still opens exactly that case."""
    headers = {"Idempotency-Key": "lead-key-3"}
    client.post("/api/v1/leads", json=VALID_LEAD, headers=headers)
    replay = client.post("/api/v1/leads", json=VALID_LEAD, headers=headers).json()
    assert (
        client.get(f"/api/v1/cases/{replay['case_id']}", headers=lead_headers(replay)).status_code
        == 200
    )


@pytest.mark.nfr("NFR-03")
def test_nfr03_lead_and_profile_requests_log_no_pii(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """NFR-03: name, contact and profile values never appear in any log line."""
    lead = create_lead(
        client, name="Zorblax Quentin Test", contact="test.secret.person@example.com"
    )
    client.put(
        f"/api/v1/cases/{lead['case_id']}/profile", json=VALID_PROFILE, headers=lead_headers(lead)
    )
    client.post("/api/v1/leads", json={"name": "Zorblax Quentin Test", "contact": "bad"})
    out = capsys.readouterr().out
    assert out.strip()
    for secret in ("Zorblax", "test.secret.person", "3000000", "SELF_EMPLOYED", "1990-04-12"):
        assert secret not in out
    assert re.search(r"lead created case_id=", out)


@pytest.mark.nfr("NFR-06")
def test_nfr06_case_scoped_request_logs_case_id(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """NFR-06: GET /cases/{id} request lines carry the case_id."""
    lead = create_lead(client)
    capsys.readouterr()
    client.get(f"/api/v1/cases/{lead['case_id']}", headers=lead_headers(lead))
    assert lead["case_id"] in capsys.readouterr().out
