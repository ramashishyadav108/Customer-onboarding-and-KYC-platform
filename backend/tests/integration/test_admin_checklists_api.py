"""AC-12 / NFR-05: admin checklist versions are appended, never edited."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import create_lead, lead_headers, staff_headers
from pipeline_helpers import rows
from review_helpers import admin

BASE = "/api/v1/admin/checklists"
COUNT_TEMPLATES = "SELECT COUNT(*) FROM checklist_templates WHERE product='Savings'"


def savings_items(**changes: Any) -> list[dict[str, Any]]:
    items = [
        {"item_code": "ID_PROOF", "mandatory": True, "accepted_classes": ["PAN", "AADHAAR"]},
        {"item_code": "ADDRESS_PROOF", "mandatory": True, "accepted_classes": ["UTILITY_BILL"]},
        {"item_code": "PHOTOGRAPH", "mandatory": True, "accepted_classes": ["PHOTOGRAPH"]},
    ]
    return [{**i, **changes.get(i["item_code"], {})} for i in items]


def publish(client: TestClient, product: str = "Savings", items: Any = None) -> Any:
    body = {"items": savings_items() if items is None else items}
    return client.post(f"{BASE}/{product}", json=body, headers=admin(client))


@pytest.mark.ac("AC-12.1")
def test_ac12_1_list_returns_latest_version_per_product(client: TestClient) -> None:
    response = client.get(BASE, headers=admin(client))
    assert response.status_code == 200
    by_product = {c["product"]: c for c in response.json()["items"]}
    assert set(by_product) == {"Savings", "Current", "NRE"}
    savings = by_product["Savings"]
    assert savings["version"] == 1 and savings["created_at"]
    assert {i["item_code"] for i in savings["items"]} == {"ID_PROOF", "ADDRESS_PROOF", "PHOTOGRAPH"}


@pytest.mark.ac("AC-12.2")
@pytest.mark.ac("AC-12.4")
def test_ac12_2_new_version_is_appended_and_old_cases_keep_theirs(
    client: TestClient, engine: Engine
) -> None:
    old_case = create_lead(client)
    response = publish(client)
    assert response.status_code == 201, response.text
    assert response.json()["version"] == 2
    versions = rows(engine, "SELECT version FROM checklist_templates WHERE product='Savings'")
    assert sorted(v[0] for v in versions) == [1, 2]
    v1 = rows(engine, "SELECT COUNT(*) FROM checklist_items WHERE product='Savings' AND version=1")
    assert v1[0][0] == 3
    new_case = create_lead(client, contact="9999999922")
    got_old = client.get(f"/api/v1/cases/{old_case['case_id']}", headers=lead_headers(old_case))
    got_new = client.get(f"/api/v1/cases/{new_case['case_id']}", headers=lead_headers(new_case))
    assert got_old.json()["checklist_version"] == 1
    assert got_new.json()["checklist_version"] == 2
    served = client.get("/api/v1/products/Savings/checklist", headers=staff_headers(client))
    assert served.json()["version"] == 2
    latest = {c["product"]: c for c in client.get(BASE, headers=admin(client)).json()["items"]}
    assert latest["Savings"]["version"] == 2


@pytest.mark.ac("AC-12.3")
@pytest.mark.parametrize(
    "items",
    [
        [],
        savings_items()[:2],
        savings_items(PHOTOGRAPH={"mandatory": False}),
        savings_items() + [savings_items()[0]],
        savings_items(ID_PROOF={"accepted_classes": []}),
        savings_items(ID_PROOF={"accepted_classes": ["UNRECOGNISED"]}),
        savings_items(ID_PROOF={"accepted_classes": ["DRIVING_LICENCE"]}),
        savings_items() + [{"item_code": "NOPE", "mandatory": False, "accepted_classes": ["PAN"]}],
    ],
    ids=["empty", "missing-baseline", "optional-photo", "duplicate", "no-classes",
         "unrecognised-class", "unknown-class", "unknown-item"],
)  # fmt: skip
def test_ac12_3_invalid_checklists_are_422_and_append_nothing(
    client: TestClient, engine: Engine, items: Any
) -> None:
    response = publish(client, items=items)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert rows(engine, COUNT_TEMPLATES)[0][0] == 1


@pytest.mark.ac("AC-12.3")
def test_ac12_3_unknown_product_is_404(client: TestClient) -> None:
    assert publish(client, "Loan").status_code == 404


@pytest.mark.ac("AC-12.5")
def test_ac12_5_publishing_is_audited(client: TestClient, engine: Engine) -> None:
    publish(client)
    sql = "SELECT payload FROM audit_log WHERE event='CHECKLIST_VERSION_CREATED'"
    events = rows(engine, sql)
    assert len(events) == 1 and '"Savings"' in events[0][0] and "2" in events[0][0]


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-12.6")
@pytest.mark.parametrize("user", ["prospect1", "analyst1", "officer1"])
def test_ac12_6_only_admin_may_manage_checklists(client: TestClient, user: str) -> None:
    assert client.get(BASE).status_code == 401
    headers = staff_headers(client, user)
    body = {"items": savings_items()}
    assert client.get(BASE, headers=headers).status_code == 403
    assert client.post(f"{BASE}/Savings", json=body, headers=headers).status_code == 403
