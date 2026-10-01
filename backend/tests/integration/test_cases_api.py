"""E1-S3 / api-contracts 2.2: GET /cases (staff list, filters, pagination) and masking."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api_helpers import create_lead, lead_headers, staff_headers
from helpers import FakeClock


def list_cases(client: TestClient, query: str = "", user: str = "analyst1") -> dict[str, object]:
    response = client.get(f"/api/v1/cases{query}", headers=staff_headers(client, user))
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


@pytest.mark.ac("AC-01")
def test_ac01_case_list_shape_and_no_pii(client: TestClient) -> None:
    """api-contracts: items carry case_id, product, state, age_minutes, created_at only."""
    create_lead(client, name="Zorblax Quentin", contact="zorblax@example.com")
    body = list_cases(client)
    assert set(body) == {"items", "page", "page_size", "total"}
    (item,) = body["items"]  # type: ignore[misc]
    assert set(item) == {"case_id", "product", "state", "age_minutes", "created_at"}
    assert (body["page"], body["page_size"], body["total"]) == (1, 25, 1)


@pytest.mark.ac("AC-01")
def test_ac01_case_list_response_never_contains_names_or_contacts(client: TestClient) -> None:
    """NFR-03: no name or contact in the list response."""
    create_lead(client, name="Zorblax Quentin", contact="zorblax@example.com")
    response = client.get("/api/v1/cases", headers=staff_headers(client))
    assert "Zorblax" not in response.text and "example.com" not in response.text


@pytest.mark.ac("AC-01")
def test_ac01_case_list_age_minutes_uses_the_clock(client: TestClient, clock: FakeClock) -> None:
    """api-contracts: age_minutes is whole minutes since creation (integer)."""
    create_lead(client)
    clock.advance(2 * 3600 + 59)
    (item,) = list_cases(client)["items"]  # type: ignore[misc]
    assert item["age_minutes"] == 120 and type(item["age_minutes"]) is int


@pytest.mark.ac("AC-01")
def test_ac01_case_list_default_order_is_oldest_first_and_sortable(
    client: TestClient, clock: FakeClock
) -> None:
    """api-contracts: sort age_desc (default) = oldest first; age_asc = newest first."""
    ids = []
    for _ in range(3):
        ids.append(create_lead(client)["case_id"])
        clock.advance(60)
    default = [i["case_id"] for i in list_cases(client)["items"]]  # type: ignore[attr-defined]
    newest = [i["case_id"] for i in list_cases(client, "?sort=age_asc")["items"]]  # type: ignore[attr-defined]
    assert default == ids and newest == ids[::-1]


@pytest.mark.ac("AC-01")
def test_ac01_case_list_filters_by_state_and_product(client: TestClient, engine: Engine) -> None:
    """api-contracts: state and product filters combine."""
    create_lead(client, product="Savings")
    current = create_lead(client, product="Current")
    create_lead(client, product="NRE")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET state='DOCS_SUBMITTED' WHERE case_id=:c"),
            {"c": current["case_id"]},
        )
    by_state = list_cases(client, "?state=DOCS_SUBMITTED")
    assert [i["case_id"] for i in by_state["items"]] == [current["case_id"]]  # type: ignore[attr-defined]
    assert list_cases(client, "?product=NRE")["total"] == 1
    assert list_cases(client, "?state=INITIATED&product=Current")["total"] == 0
    assert list_cases(client, "?state=INITIATED")["total"] == 2


@pytest.mark.ac("AC-01")
def test_ac01_case_list_pagination(client: TestClient, clock: FakeClock) -> None:
    """api-contracts: page and page_size slice the ordered list; total is the full count."""
    ids = []
    for _ in range(5):
        ids.append(create_lead(client)["case_id"])
        clock.advance(1)
    first = list_cases(client, "?page=1&page_size=2")
    third = list_cases(client, "?page=3&page_size=2")
    assert [i["case_id"] for i in first["items"]] == ids[:2]  # type: ignore[attr-defined]
    assert [i["case_id"] for i in third["items"]] == ids[4:]  # type: ignore[attr-defined]
    assert first["total"] == 5 and third["page"] == 3


@pytest.mark.ac("AC-01")
@pytest.mark.parametrize(
    "query",
    [
        "?page_size=101",
        "?page_size=0",
        "?page=0",
        "?state=BOGUS",
        "?product=Gold",
        "?sort=sideways",
    ],
)
def test_ac01_case_list_invalid_filters_are_422(client: TestClient, query: str) -> None:
    """api-contracts: invalid filters or paging are 422 VALIDATION_ERROR."""
    response = client.get(f"/api/v1/cases{query}", headers=staff_headers(client))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.ac("AC-01")
def test_ac01_case_list_is_not_available_to_prospects(client: TestClient) -> None:
    """NFR-04: a prospect token cannot list cases."""
    lead = create_lead(client)
    assert client.get("/api/v1/cases", headers=lead_headers(lead)).status_code == 403


@pytest.mark.ac("AC-01")
def test_ac01_case_detail_contains_the_contract_fields(client: TestClient) -> None:
    """api-contracts CaseDetail: every documented field is present."""
    lead = create_lead(client)
    body = client.get(f"/api/v1/cases/{lead['case_id']}", headers=lead_headers(lead)).json()
    assert set(body) == {
        "case_id", "name", "contact_masked", "product", "state", "checklist_version",
        "checklist_items", "missing_items", "action_required", "profile", "profile_complete",
        "account_number_masked", "created_at", "updated_at",
    }  # fmt: skip
    assert body["account_number_masked"] is None
    assert set(body["checklist_items"][0]) == {
        "item_code", "mandatory", "accepted_classes", "status", "document_id", "doc_version",
        "doc_class", "reason_code",
    }  # fmt: skip
