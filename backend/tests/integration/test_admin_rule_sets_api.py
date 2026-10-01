"""AC-06 / NFR-01 / NFR-08: admin rule-set endpoints (draft copy, edit, publish, immutability)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api_helpers import staff_headers
from ruleset_fixture import V1_DICT

BASE = "/api/v1/admin/rule-sets"
WEIGHTS = {"age": 20, "income_band": 25, "occupation_category": 30, "geography": 25}


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    return staff_headers(client, "admin1")


@pytest.mark.ac("AC-06")
def test_ac06_6_get_seeded_v1_matches_the_contract(
    client: TestClient, admin: dict[str, str]
) -> None:
    """AC-06.6: GET v1 returns the published spec values and integers only."""
    response = client.get(f"{BASE}/1", headers=admin)
    assert response.status_code == 200
    assert response.json() == V1_DICT


@pytest.mark.ac("AC-06")
def test_ac06_list_rule_sets_returns_summaries(client: TestClient, admin: dict[str, str]) -> None:
    """api-contracts 2.6: list returns version, status, author, created_at, published_at."""
    body = client.get(BASE, headers=admin).json()
    assert body == {
        "items": [
            {
                "version": 1, "status": "PUBLISHED", "author": "system",
                "created_at": "2026-10-01T00:00:00Z", "published_at": "2026-10-01T00:00:00Z",
            }
        ]
    }  # fmt: skip


@pytest.mark.ac("AC-06")
def test_ac06_unknown_version_is_404(client: TestClient, admin: dict[str, str]) -> None:
    """api-contracts: unknown rule-set version -> 404 NOT_FOUND."""
    assert client.get(f"{BASE}/42", headers=admin).status_code == 404
    assert client.post(f"{BASE}/42/publish", headers=admin).status_code == 404


@pytest.mark.ac("AC-06")
def test_ac06_4_post_creates_a_draft_copy_as_version_2(
    client: TestClient, admin: dict[str, str]
) -> None:
    """AC-06.4: POST creates DRAFT v2 (copy of v1); a second POST is 409 DRAFT_EXISTS."""
    response = client.post(BASE, headers=admin)
    body = response.json()
    assert response.status_code == 201
    assert body["version"] == 2 and body["status"] == "DRAFT" and body["published_at"] is None
    assert body["weights"] == V1_DICT["weights"] and body["author"] == "admin1"
    again = client.post(BASE, headers=admin)
    assert again.status_code == 409 and again.json()["error"]["code"] == "DRAFT_EXISTS"


@pytest.mark.ac("AC-06")
def test_ac06_draft_can_be_edited_then_published(client: TestClient, admin: dict[str, str]) -> None:
    """AC-06.3: edit the draft, publish it; published_at is set and v1 is untouched."""
    client.post(BASE, headers=admin)
    edited = client.put(
        f"{BASE}/2",
        json={"thresholds": {"low_max": 25, "medium_max": 55}, "border_states": ["JK", "PB"]},
        headers=admin,
    )
    assert edited.status_code == 200
    assert edited.json()["thresholds"] == {"low_max": 25, "medium_max": 55}
    published = client.post(f"{BASE}/2/publish", headers=admin)
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED" and published.json()["published_at"]
    assert client.get(f"{BASE}/1", headers=admin).json() == V1_DICT


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-08")
def test_nfr08_published_rule_set_cannot_be_edited_or_republished(
    client: TestClient, admin: dict[str, str]
) -> None:
    """AC-06.3 / NFR-08: PUT or POST publish on a PUBLISHED version is 409 RULESET_IMMUTABLE."""
    put = client.put(f"{BASE}/1", json={"weights": WEIGHTS}, headers=admin)
    publish = client.post(f"{BASE}/1/publish", headers=admin)
    for response in (put, publish):
        assert response.status_code == 409
        assert response.json()["error"] == {
            "code": "RULESET_IMMUTABLE",
            "message": "Published rule set is immutable",
            "details": {"version": 1},
        }
    assert client.get(f"{BASE}/1", headers=admin).json() == V1_DICT


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-01")
@pytest.mark.parametrize(
    "body",
    [
        {"weights": {**WEIGHTS, "age": 0.25}},
        {"weights": {**WEIGHTS, "age": "20"}},
        {"weights": {**WEIGHTS, "age": 20.0}},
        {"thresholds": {"low_max": 29.5, "medium_max": 59}},
        {"points": {**V1_DICT["points"], "geography": {"DOMESTIC": 0.5}}},
        {"points": {**V1_DICT["points"], "age": [{"label": "x", "min_years": 0,
                                                   "max_years": None, "points": 1.5}]}},
    ],
)  # fmt: skip
def test_ac06_2_fractional_values_in_a_draft_are_422(
    client: TestClient, admin: dict[str, str], body: dict[str, Any]
) -> None:
    """AC-06.2 / NFR-01: floats (even 20.0) anywhere in weights, points or thresholds are 422."""
    client.post(BASE, headers=admin)
    response = client.put(f"{BASE}/2", json=body, headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get(f"{BASE}/2", headers=admin).json()["weights"] == V1_DICT["weights"]


@pytest.mark.ac("AC-06")
def test_ac06_5_publish_invalid_draft_is_422_ruleset_invalid(
    client: TestClient, admin: dict[str, str]
) -> None:
    """AC-06.5: weights not summing to 100 and thresholds not ascending -> RULESET_INVALID."""
    client.post(BASE, headers=admin)
    client.put(
        f"{BASE}/2",
        json={"weights": {**WEIGHTS, "age": 30}, "thresholds": {"low_max": 60, "medium_max": 59}},
        headers=admin,
    )
    response = client.post(f"{BASE}/2/publish", headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RULESET_INVALID"
    assert response.json()["error"]["details"] == {"reasons": ["WEIGHTS_SUM", "THRESHOLDS_ORDER"]}
    assert client.get(f"{BASE}/2", headers=admin).json()["status"] == "DRAFT"


@pytest.mark.ac("AC-06")
def test_ac06_4_next_draft_after_publish_is_version_3(
    client: TestClient, admin: dict[str, str]
) -> None:
    """AC-06.4: version = max + 1 even after a publish."""
    client.post(BASE, headers=admin)
    client.post(f"{BASE}/2/publish", headers=admin)
    assert client.post(BASE, headers=admin).json()["version"] == 3
    assert [i["version"] for i in client.get(BASE, headers=admin).json()["items"]] == [1, 2, 3]


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("user", ["prospect1", "analyst1", "officer1"])
def test_nfr04_non_admin_roles_cannot_touch_rule_sets(client: TestClient, user: str) -> None:
    """NFR-04: every rule-set endpoint is 403 for non-admin roles."""
    headers = staff_headers(client, user)
    calls = [
        client.get(BASE, headers=headers),
        client.get(f"{BASE}/1", headers=headers),
        client.post(BASE, headers=headers),
        client.put(f"{BASE}/1", json={}, headers=headers),
        client.post(f"{BASE}/1/publish", headers=headers),
    ]
    assert [c.status_code for c in calls] == [403] * 5


@pytest.mark.ac("AC-06")
def test_ac06_no_float_appears_in_any_rule_set_response(
    client: TestClient, admin: dict[str, str]
) -> None:
    """NFR-01: the JSON of every rule-set response contains integers only."""
    client.post(BASE, headers=admin)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        else:
            assert type(value) is not float

    for path in (BASE, f"{BASE}/1", f"{BASE}/2"):
        walk(client.get(path, headers=admin).json())
