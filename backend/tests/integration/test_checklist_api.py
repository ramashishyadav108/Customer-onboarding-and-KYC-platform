"""AC-02 / NFR-05 / E1-S5: checklist per product, read-only, versioned and pinned to cases."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api_helpers import bearer, create_lead, lead_headers, staff_headers
from helpers import make_token

ID = ["PAN", "AADHAAR", "PASSPORT"]
ADDR = ["AADHAAR", "PASSPORT", "UTILITY_BILL"]
EXPECTED = {
    "Savings": {
        "ID_PROOF": ID,
        "ADDRESS_PROOF": ADDR,
        "PHOTOGRAPH": ["PHOTOGRAPH"],
    },
    "Current": {
        "ID_PROOF": ID,
        "ADDRESS_PROOF": ADDR,
        "PHOTOGRAPH": ["PHOTOGRAPH"],
        "BUSINESS_PROOF": ["GST_CERTIFICATE"],
    },
    "NRE": {
        "ID_PROOF": ["PASSPORT"],
        "ADDRESS_PROOF": ADDR,
        "PHOTOGRAPH": ["PHOTOGRAPH"],
        "OVERSEAS_ADDRESS_PROOF": ["VISA"],
    },
}


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", sorted(EXPECTED))
def test_ac02_1_checklist_items_and_accepted_classes_per_product(
    client: TestClient, product: str
) -> None:
    """AC-02.1/02.2: exact items, all mandatory, accepted classes, version 1."""
    response = client.get(f"/api/v1/products/{product}/checklist", headers=staff_headers(client))
    body = response.json()
    assert response.status_code == 200
    assert body["product"] == product and body["version"] == 1
    assert {i["item_code"]: i["accepted_classes"] for i in body["items"]} == EXPECTED[product]
    assert all(i["mandatory"] is True for i in body["items"])


@pytest.mark.ac("AC-02")
def test_ac02_2_item_order_is_stable(client: TestClient) -> None:
    """AC-02.2: items come back in the canonical item order."""
    body = client.get("/api/v1/products/NRE/checklist", headers=staff_headers(client)).json()
    assert [i["item_code"] for i in body["items"]] == [
        "ID_PROOF", "ADDRESS_PROOF", "PHOTOGRAPH", "OVERSEAS_ADDRESS_PROOF",
    ]  # fmt: skip


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", ["Gold", "savings", "SAVINGS", "Fixed"])
def test_ac02_2_unknown_product_is_404(client: TestClient, product: str) -> None:
    """AC-02.2 / E1-S5 AC4: an unknown product returns 404 NOT_FOUND."""
    response = client.get(f"/api/v1/products/{product}/checklist", headers=staff_headers(client))
    assert response.status_code == 404
    assert response.json()["error"]["details"] == {"resource": "product"}


@pytest.mark.ac("AC-02")
def test_ac02_2_checklist_requires_authentication(client: TestClient) -> None:
    """E1-S5 AC4: any authenticated user, but not anonymous callers."""
    assert client.get("/api/v1/products/Savings/checklist").status_code == 401


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("role", ["prospect", "kyc-analyst", "compliance-officer", "admin"])
def test_ac02_2_any_authenticated_role_can_read_a_checklist(client: TestClient, role: str) -> None:
    """E1-S5 AC4: all four roles may read the checklist (staff via a real login, NFR-04)."""
    users = {"kyc-analyst": "analyst1", "compliance-officer": "officer1", "admin": "admin1"}
    headers = bearer(make_token(role)) if role == "prospect" else staff_headers(client, users[role])
    assert client.get("/api/v1/products/Current/checklist", headers=headers).status_code == 200


@pytest.mark.ac("AC-02")
def test_ac02_checklist_endpoint_is_read_only(client: TestClient) -> None:
    """E1-S5: checklists are exposed read-only; write verbs are not routed."""
    headers = staff_headers(client, "admin1")
    for method in ("post", "put", "delete", "patch"):
        response = getattr(client, method)("/api/v1/products/Savings/checklist", headers=headers)
        assert response.status_code == 405


NEW_V2 = [
    ("Savings", 2, "ID_PROOF", ["PAN", "PASSPORT"]),
    ("Savings", 2, "ADDRESS_PROOF", ["PASSPORT"]),
    ("Savings", 2, "PHOTOGRAPH", ["PHOTOGRAPH"]),
]


def seed_savings_v2(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO checklist_templates VALUES ('Savings', 2, '2026-11-01T00:00:00Z')")
        )
        for product, version, code, classes in NEW_V2:
            conn.execute(
                text("INSERT INTO checklist_items VALUES (:p, :v, :c, 1, :a)"),
                {"p": product, "v": version, "c": code, "a": str(classes).replace("'", '"')},
            )


@pytest.mark.ac("AC-02")
@pytest.mark.nfr("NFR-05")
def test_ac02_3_case_keeps_its_checklist_version_after_a_newer_one_is_seeded(
    client: TestClient, engine: Engine
) -> None:
    """AC-02.3 / E1-S5 AC5: a case created under v1 still reports v1 after v2 is seeded."""
    old = create_lead(client)
    seed_savings_v2(engine)
    new = create_lead(client)
    old_case = client.get(f"/api/v1/cases/{old['case_id']}", headers=lead_headers(old)).json()
    new_case = client.get(f"/api/v1/cases/{new['case_id']}", headers=lead_headers(new)).json()
    assert old_case["checklist_version"] == 1
    assert old_case["checklist_items"][0]["accepted_classes"] == ["PAN", "AADHAAR", "PASSPORT"]
    assert new_case["checklist_version"] == 2
    assert new_case["checklist_items"][0]["accepted_classes"] == ["PAN", "PASSPORT"]


@pytest.mark.ac("AC-02")
@pytest.mark.nfr("NFR-05")
def test_ac02_3_product_endpoint_returns_the_latest_version_and_v1_is_untouched(
    client: TestClient, engine: Engine
) -> None:
    """E1-S5 AC5: v2 is additive; v1 rows are byte-for-byte unchanged."""
    with engine.connect() as conn:
        before = conn.execute(
            text("SELECT * FROM checklist_items WHERE product='Savings' AND version=1 ORDER BY 3")
        ).all()
    seed_savings_v2(engine)
    body = client.get("/api/v1/products/Savings/checklist", headers=staff_headers(client)).json()
    assert body["version"] == 2
    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT * FROM checklist_items WHERE product='Savings' AND version=1 ORDER BY 3")
        ).all()
    assert before == after


@pytest.mark.nfr("NFR-05")
def test_nfr05_case_cannot_reference_a_missing_checklist_version(engine: Engine) -> None:
    """Data model: cases.checklist_version is a composite FK to an existing template."""
    from sqlalchemy.exc import IntegrityError

    with engine.connect() as conn, pytest.raises(IntegrityError):
        conn.execute(
            text("INSERT INTO cases VALUES ('c', 'n', 'c', 'Savings', 'INITIATED', 7, 't', 't')")
        )
