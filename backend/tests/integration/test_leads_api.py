"""AC-01 / NFR-03 / E1-S3: lead registration, case read, profile and idempotency."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api_helpers import (
    VALID_LEAD,
    VALID_PROFILE,
    count_rows,
    create_lead,
    lead_headers,
    staff_headers,
)
from onboardx.domain.enums import CaseState
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.audit_service import AuditService


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize("product", ["Savings", "Current", "NRE"])
def test_ac01_1_valid_lead_returns_201_uuid_and_initiated(client: TestClient, product: str) -> None:
    """AC-01.1: 201, UUID case_id and state INITIATED for each product."""
    response = client.post("/api/v1/leads", json={**VALID_LEAD, "product": product})
    body = response.json()
    assert response.status_code == 201
    assert uuid.UUID(body["case_id"]).version == 4
    assert body["state"] == "INITIATED" and body["product"] == product
    assert body["token_type"] == "bearer" and body["expires_in"] == 1800 and body["access_token"]


@pytest.mark.ac("AC-01")
def test_ac01_1_email_contact_is_accepted(client: TestClient) -> None:
    """AC-01.1: a valid email is an acceptable contact."""
    response = client.post(
        "/api/v1/leads", json={**VALID_LEAD, "contact": "test.person@example.com"}
    )
    assert response.status_code == 201


@pytest.mark.ac("AC-01")
def test_ac01_1_lead_is_public_no_token_needed(client: TestClient) -> None:
    """DD-6: POST /leads needs no Authorization header."""
    assert client.post("/api/v1/leads", json=VALID_LEAD).status_code == 201


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize(
    ("payload", "fields"),
    [
        ({"contact": "9999999921", "product": "Savings"}, {"name"}),
        ({"name": "Test Person", "product": "Savings"}, {"contact"}),
        ({"name": "Test Person", "contact": "12345", "product": "Savings"}, {"contact"}),
        ({"name": "Test Person", "contact": "no-at-sign", "product": "Savings"}, {"contact"}),
        ({"name": "Test Person", "contact": "9999999921", "product": "Gold"}, {"product"}),
        ({"name": "Test Person", "contact": "9999999921"}, {"product"}),
        ({"name": "", "contact": "9999999921", "product": "Savings"}, {"name"}),
        ({"name": "   ", "contact": "9999999921", "product": "Savings"}, {"name"}),
        ({"name": "x" * 101, "contact": "9999999921", "product": "Savings"}, {"name"}),
        ({"name": "T", "contact": "bad", "product": "Gold"}, {"contact", "product"}),
        ({}, {"name", "contact", "product"}),
    ],
)
def test_ac01_2_invalid_lead_is_422_with_field_errors_and_no_case(
    client: TestClient, engine: Engine, payload: dict[str, str], fields: set[str]
) -> None:
    """AC-01.2: 422 with a field-level error list; no case row is created."""
    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert {f["field"] for f in error["details"]["fields"]} == fields
    assert count_rows(engine, "cases") == 0


@pytest.mark.ac("AC-01")
def test_ac01_2_validation_errors_do_not_echo_pii(client: TestClient) -> None:
    """NFR-03: 422 bodies never echo the submitted contact or name back."""
    response = client.post(
        "/api/v1/leads", json={"name": "Secret Name Zed", "contact": "12345678", "product": "NRE"}
    )
    assert "12345678" not in response.text and "Secret Name Zed" not in response.text


@pytest.mark.ac("AC-01")
def test_ac01_3_lead_appends_audit_and_initial_history_in_one_transaction(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    """AC-01.3: audit LEAD_CREATED and an INITIATED history row exist together, UTC-stamped."""
    lead = create_lead(client)
    with uow_factory() as uow:
        audit = uow.audit.list_for_case(lead["case_id"])
        history = uow.state_history.list_for_case(lead["case_id"])
    assert [a.event for a in audit] == ["LEAD_CREATED"]
    assert audit[0].actor == f"prospect:{lead['case_id']}" and audit[0].created_at.endswith("Z")
    assert len(history) == 1
    assert history[0].from_state is None and history[0].to_state is CaseState.INITIATED
    assert history[0].created_at == audit[0].created_at


@pytest.mark.ac("AC-01")
def test_ac01_3_failure_while_auditing_rolls_back_the_case(
    app: FastAPI, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-01.3: if the audit append fails nothing is stored (same transaction)."""

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("forced failure")

    monkeypatch.setattr(AuditService, "record", boom)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/leads", json=VALID_LEAD)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert count_rows(engine, "cases") == 0
    assert count_rows(engine, "state_history") == 0


@pytest.mark.ac("AC-01")
def test_ac01_4_get_case_returns_state_product_checklist_and_masked_contact(
    client: TestClient,
) -> None:
    """AC-01.4: state, product, checklist version and items; contact masked to last 2 chars."""
    lead = create_lead(client, contact="9999999921")
    response = client.get(f"/api/v1/cases/{lead['case_id']}", headers=lead_headers(lead))
    body = response.json()
    assert response.status_code == 200
    assert body["state"] == "INITIATED" and body["product"] == "Savings"
    assert body["checklist_version"] == 1
    assert [i["item_code"] for i in body["checklist_items"]] == [
        "ID_PROOF", "ADDRESS_PROOF", "PHOTOGRAPH",
    ]  # fmt: skip
    assert body["contact_masked"] == "********21" and "9999999921" not in response.text
    assert body["missing_items"] == ["ID_PROOF", "ADDRESS_PROOF", "PHOTOGRAPH"]
    assert body["profile"] is None and body["profile_complete"] is False
    assert {a["status"] for a in body["action_required"]} == {"MISSING"}


@pytest.mark.ac("AC-01")
def test_ac01_4_staff_view_hides_the_profile(client: TestClient) -> None:
    """DD-5: staff never receive raw income or occupation; the owner does."""
    lead = create_lead(client)
    path = f"/api/v1/cases/{lead['case_id']}"
    client.put(f"{path}/profile", json=VALID_PROFILE, headers=lead_headers(lead))
    staff = client.get(path, headers=staff_headers(client)).json()
    owner = client.get(path, headers=lead_headers(lead)).json()
    assert staff["profile"] is None and staff["profile_complete"] is True
    assert owner["profile"]["annual_income"] == 3000000


@pytest.mark.ac("AC-01")
def test_ac01_4_unknown_case_is_404_for_staff(client: TestClient) -> None:
    """AC-01.4: unknown case -> 404 NOT_FOUND for staff."""
    response = client.get(f"/api/v1/cases/{uuid.uuid4()}", headers=staff_headers(client))
    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "NOT_FOUND", "message": "case not found", "details": {"resource": "case"},
    }  # fmt: skip


@pytest.mark.ac("AC-01")
def test_ac01_5_profile_is_stored_while_initiated(client: TestClient, engine: Engine) -> None:
    """AC-01.5: PUT profile stores the four fields (+ state_code) and returns the case."""
    lead = create_lead(client)
    response = client.put(
        f"/api/v1/cases/{lead['case_id']}/profile", json=VALID_PROFILE, headers=lead_headers(lead)
    )
    assert response.status_code == 200
    assert response.json()["profile"] == VALID_PROFILE and response.json()["profile_complete"]
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM case_profiles")).one()._mapping
    assert (row["annual_income"], row["state_code"], row["country_code"]) == (3000000, "MH", "IN")


@pytest.mark.ac("AC-01")
def test_ac01_5_profile_can_be_replaced_while_initiated(client: TestClient) -> None:
    """AC-01.5: a second PUT while INITIATED overwrites the first."""
    lead = create_lead(client)
    path = f"/api/v1/cases/{lead['case_id']}/profile"
    client.put(path, json=VALID_PROFILE, headers=lead_headers(lead))
    changed = {**VALID_PROFILE, "annual_income": 100, "state_code": "PB"}
    response = client.put(path, json=changed, headers=lead_headers(lead))
    assert response.json()["profile"]["annual_income"] == 100
    assert response.json()["profile"]["state_code"] == "PB"


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize("income", [3000000.5, 3000000.0, "3000000", True, None, -5])
def test_ac01_5_non_integer_or_negative_income_is_422(client: TestClient, income: object) -> None:
    """AC-01.5: non-integer income (float, string, bool, null) or negative is rejected."""
    lead = create_lead(client)
    response = client.put(
        f"/api/v1/cases/{lead['case_id']}/profile",
        json={**VALID_PROFILE, "annual_income": income},
        headers=lead_headers(lead),
    )
    assert response.status_code == 422
    assert "annual_income" in {f["field"] for f in response.json()["error"]["details"]["fields"]}


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"state_code": None}, "state_code"),
        ({"country_code": "GB", "state_code": "PB"}, "state_code"),
        ({"state_code": "pb"}, "state_code"),
        ({"date_of_birth": "2999-01-01"}, "date_of_birth"),
        ({"date_of_birth": "1990-13-45"}, "date_of_birth"),
        ({"date_of_birth": "12/04/1990"}, "date_of_birth"),
        ({"occupation_category": "ASTRONAUT"}, "occupation_category"),
        ({"country_code": "india"}, "country_code"),
    ],
)
def test_ac01_5_invalid_profile_fields_are_422(
    client: TestClient, override: dict[str, object], field: str
) -> None:
    """AC-01.5 / DD-14: state_code required for IN, omitted otherwise; bad dates etc. are 422."""
    lead = create_lead(client)
    response = client.put(
        f"/api/v1/cases/{lead['case_id']}/profile",
        json={**VALID_PROFILE, **override},
        headers=lead_headers(lead),
    )
    assert response.status_code == 422
    assert field in {f["field"] for f in response.json()["error"]["details"]["fields"]}


@pytest.mark.ac("AC-01")
def test_ac01_5_non_indian_profile_without_state_code_is_valid(client: TestClient) -> None:
    """DD-14: a GB profile omits state_code."""
    lead = create_lead(client)
    body = {**VALID_PROFILE, "country_code": "GB"}
    del body["state_code"]
    response = client.put(
        f"/api/v1/cases/{lead['case_id']}/profile", json=body, headers=lead_headers(lead)
    )
    assert response.status_code == 200 and response.json()["profile"]["state_code"] is None


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize(
    "state", [CaseState.DOCS_SUBMITTED, CaseState.SCREENED, CaseState.MANUAL_REVIEW]
)
def test_ac01_5_profile_update_after_docs_submitted_is_409_profile_locked(
    client: TestClient, engine: Engine, state: CaseState
) -> None:
    """AC-01.5: 409 PROFILE_LOCKED once the case is DOCS_SUBMITTED or later."""
    lead = create_lead(client)
    with engine.begin() as conn:
        conn.execute(text("UPDATE cases SET state=:s"), {"s": str(state)})
    response = client.put(
        f"/api/v1/cases/{lead['case_id']}/profile", json=VALID_PROFILE, headers=lead_headers(lead)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROFILE_LOCKED"
    assert response.json()["error"]["details"]["state"] == str(state)


@pytest.mark.ac("AC-01")
@pytest.mark.nfr("NFR-08")
@pytest.mark.parametrize("state", [CaseState.APPROVED, CaseState.REJECTED])
def test_nfr08_profile_update_on_a_closed_case_is_409_case_locked(
    client: TestClient, engine: Engine, state: CaseState
) -> None:
    """NFR-08: writes to an APPROVED or REJECTED case return 409 CASE_LOCKED."""
    lead = create_lead(client)
    with engine.begin() as conn:
        conn.execute(text("UPDATE cases SET state=:s"), {"s": str(state)})
    response = client.put(
        f"/api/v1/cases/{lead['case_id']}/profile", json=VALID_PROFILE, headers=lead_headers(lead)
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "CASE_LOCKED"


@pytest.mark.ac("AC-01")
def test_ac01_5_profile_update_is_audited_without_values(
    client: TestClient, uow_factory: UnitOfWorkFactory
) -> None:
    """Audit catalogue: PROFILE_UPDATED lists field names only (NFR-03)."""
    lead = create_lead(client)
    client.put(
        f"/api/v1/cases/{lead['case_id']}/profile", json=VALID_PROFILE, headers=lead_headers(lead)
    )
    with uow_factory() as uow:
        (entry,) = uow.audit.list_by_event("PROFILE_UPDATED")
    assert "annual_income" in entry.payload["fields"]
    assert "3000000" not in str(entry.payload) and "SELF_EMPLOYED" not in str(entry.payload)
