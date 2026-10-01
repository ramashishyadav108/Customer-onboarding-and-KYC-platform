"""AC-05 / AC-06 / NFR-02 / NFR-05 / NFR-08: admin watchlist API and audited admin changes."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from pipeline_helpers import rows, submitted_case
from review_helpers import admin

BASE = "/api/v1/admin/watchlist"
NAME = "Zephyr Quillfeather"


def add(client: TestClient, **body: Any) -> Any:
    payload = {"name": NAME, "aliases": ["Z Quill"], "list_type": "AML", **body}
    return client.post(BASE, json=payload, headers=admin(client))


def screen_state(client: TestClient, name: str) -> str:
    """Screen a fresh case with this name and return its first decision reason."""
    from pipeline_helpers import step

    lead = submitted_case(client, name=name)
    step(client, lead, "screen")
    step(client, lead, "classify")
    decided = step(client, lead, "decide").json()
    return str(decided["decision"]["reason_code"])


@pytest.mark.ac("AC-05")
def test_ac05_list_returns_the_seeded_entries_with_the_version(client: TestClient) -> None:
    """E3-S4: GET lists the ten seeded entries, all active, with watchlist_version 10."""
    body = client.get(BASE, headers=admin(client)).json()
    assert body["watchlist_version"] == 10 and len(body["items"]) == 10
    first = body["items"][0]
    assert first["name"] == "Test Person One" and first["aliases"] == ["T P One"]
    assert first["active"] is True and first["deactivated_at"] is None
    assert {i["list_type"] for i in body["items"]} == {"AML", "PEP"}


@pytest.mark.ac("AC-05")
def test_ac05_4_add_returns_201_and_bumps_the_version(client: TestClient) -> None:
    """E3-S4 AC4: POST adds an entry (name, aliases, list_type) and the version rises."""
    response = add(client)
    body = response.json()
    assert response.status_code == 201 and body["name"] == NAME and body["active"] is True
    assert body["aliases"] == ["Z Quill"] and body["list_type"] == "AML"
    assert body["deactivated_at"] is None and body["entry_id"] and body["added_at"].endswith("Z")
    listing = client.get(BASE, headers=admin(client)).json()
    assert (
        listing["watchlist_version"] == 11 and listing["items"][-1]["entry_id"] == body["entry_id"]
    )


@pytest.mark.ac("AC-05")
def test_ac05_4_screening_uses_entries_active_at_screening_time(client: TestClient) -> None:
    """E3-S4 AC4: a new entry hits, and after deactivation later screenings do not."""
    assert screen_state(client, NAME) == "AUTO_APPROVED"
    entry = add(client).json()
    assert screen_state(client, NAME) == "AML_HIT"
    assert screen_state(client, "Z Quill") == "AML_HIT"  # the alias matches too
    deactivated = client.post(f"{BASE}/{entry['entry_id']}/deactivate", headers=admin(client))
    assert deactivated.status_code == 200 and deactivated.json()["active"] is False
    assert screen_state(client, NAME) == "AUTO_APPROVED"


@pytest.mark.ac("AC-05")
def test_ac05_pep_entry_routes_to_pep_hit(client: TestClient) -> None:
    """A PEP entry produces PEP_HIT."""
    add(client, name="Quixotic Minister", aliases=[], list_type="PEP")
    assert screen_state(client, "Quixotic Minister") == "PEP_HIT"


@pytest.mark.ac("AC-05")
@pytest.mark.nfr("NFR-02")
def test_ac05_deactivation_is_append_only_and_version_is_monotonic(
    client: TestClient, engine: Engine
) -> None:
    """NFR-02: deactivate appends a row; entries are never updated; the version never drops."""
    head = admin(client)
    entry = add(client).json()
    versions = [client.get(BASE, headers=head).json()["watchlist_version"]]
    client.post(f"{BASE}/{entry['entry_id']}/deactivate", headers=head)
    versions.append(client.get(BASE, headers=head).json()["watchlist_version"])
    add(client, name="Another Fictional Person")
    versions.append(client.get(BASE, headers=head).json()["watchlist_version"])
    assert versions == [11, 12, 13]
    assert rows(engine, "SELECT COUNT(*) FROM watchlist_entries")[0][0] == 12
    assert rows(engine, "SELECT COUNT(*) FROM watchlist_deactivations")[0][0] == 1


@pytest.mark.ac("AC-05")
def test_ac05_list_filters_by_active(client: TestClient) -> None:
    """GET ?active=true|false filters on the derived flag; invalid value is 422."""
    head = admin(client)
    entry = add(client).json()
    client.post(f"{BASE}/{entry['entry_id']}/deactivate", headers=head)
    active = client.get(BASE, params={"active": "true"}, headers=head).json()["items"]
    inactive = client.get(BASE, params={"active": "false"}, headers=head).json()["items"]
    assert len(active) == 10 and [i["entry_id"] for i in inactive] == [entry["entry_id"]]
    assert inactive[0]["deactivated_at"] is not None
    assert client.get(BASE, params={"active": "maybe"}, headers=head).status_code == 422


@pytest.mark.ac("AC-05")
def test_ac05_deactivate_twice_is_409_and_unknown_is_404(client: TestClient) -> None:
    """api-contracts 2.7: ALREADY_DEACTIVATED 409, unknown entry 404."""
    head = admin(client)
    entry = add(client).json()
    url = f"{BASE}/{entry['entry_id']}/deactivate"
    assert client.post(url, headers=head).status_code == 200
    again = client.post(url, headers=head)
    assert again.status_code == 409 and again.json()["error"]["code"] == "ALREADY_DEACTIVATED"
    assert client.post(f"{BASE}/nope/deactivate", headers=head).status_code == 404


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize(
    "body",
    [
        {"aliases": [], "list_type": "AML"},
        {"name": "", "aliases": [], "list_type": "AML"},
        {"name": "x" * 101, "aliases": [], "list_type": "AML"},
        {"name": "Valid Name", "aliases": [], "list_type": "SANCTIONS"},
        {"name": "Valid Name", "aliases": []},
        {"name": "Valid Name", "aliases": [f"alias {i}" for i in range(11)], "list_type": "AML"},
        {"name": "!!!", "aliases": [], "list_type": "AML"},
        {"name": "Valid Name", "aliases": ["  "], "list_type": "PEP"},
    ],
)
def test_ac05_add_validation_errors_are_422_and_write_nothing(
    client: TestClient, engine: Engine, body: dict[str, Any]
) -> None:
    """E3-S4: bad name, alias list or list_type -> 422 and no row."""
    response = client.post(BASE, json=body, headers=admin(client))
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert rows(engine, "SELECT COUNT(*) FROM watchlist_entries")[0][0] == 10


@pytest.mark.ac("AC-05")
@pytest.mark.nfr("NFR-02")
def test_ac05_there_is_no_edit_or_delete_route(client: TestClient) -> None:
    """api-contracts 2.7: no PUT, PATCH or DELETE on the watchlist."""
    head = admin(client)
    entry = add(client).json()
    url = f"{BASE}/{entry['entry_id']}"
    for method in ("put", "patch", "delete"):
        assert getattr(client, method)(url, headers=head).status_code in (404, 405)
    assert client.delete(BASE, headers=head).status_code == 405


@pytest.mark.ac("AC-05")
@pytest.mark.nfr("NFR-08")
def test_ac05_admin_changes_are_audited_without_the_name(
    client: TestClient, engine: Engine
) -> None:
    """E3-S4 AC5 / AC-05.10: audit rows hold actor, event, entry_id and list_type only."""
    head = admin(client)
    entry = add(client).json()
    client.post(f"{BASE}/{entry['entry_id']}/deactivate", headers=head)
    audit = rows(
        engine,
        "SELECT event, actor, role, payload, case_id FROM audit_log"
        " WHERE event LIKE 'WATCHLIST_%' ORDER BY seq",
    )
    assert [a[0] for a in audit] == ["WATCHLIST_ENTRY_ADDED", "WATCHLIST_ENTRY_DEACTIVATED"]
    for row in audit:
        assert row[1] == "admin1" and row[2] == "admin" and row[4] is None
        assert json.loads(row[3]) == {"entry_id": entry["entry_id"], "list_type": "AML"}
        assert NAME not in row[3] and "Quill" not in row[3]


@pytest.mark.ac("AC-05")
@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("user", ["prospect1", "analyst1", "officer1"])
def test_nfr04_non_admin_roles_cannot_use_the_watchlist_api(client: TestClient, user: str) -> None:
    """E3-S4: every watchlist route is 403 for non-admin roles (and 401 without a token)."""
    from api_helpers import staff_headers

    head = staff_headers(client, user)
    body = {"name": "Valid Name", "aliases": [], "list_type": "AML"}
    assert client.get(BASE, headers=head).status_code == 403
    assert client.post(BASE, json=body, headers=head).status_code == 403
    assert client.post(f"{BASE}/x/deactivate", headers=head).status_code == 403
    assert client.get(BASE).status_code == 401 and client.post(BASE, json=body).status_code == 401


@pytest.mark.ac("AC-05")
def test_ac05_watchlist_tables_reject_update_and_delete(client: TestClient, engine: Engine) -> None:
    """NFR-02: triggers protect entries and deactivations at database level."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    entry = add(client).json()
    client.post(f"{BASE}/{entry['entry_id']}/deactivate", headers=admin(client))
    for table in ("watchlist_entries", "watchlist_deactivations"):
        for sql in (f"UPDATE {table} SET entry_id='x'", f"DELETE FROM {table}"):
            with pytest.raises(IntegrityError), engine.begin() as conn:
                conn.execute(text(sql))


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-08")
def test_ac06_rule_set_admin_changes_are_audited_with_actor_and_event(
    client: TestClient, engine: Engine
) -> None:
    """E3-S4 AC5: draft create, edit and publish each append an audit row with the actor."""
    head = admin(client)
    base = "/api/v1/admin/rule-sets"
    client.post(base, headers=head)
    client.put(f"{base}/2", json={"thresholds": {"low_max": 20, "medium_max": 50}}, headers=head)
    client.post(f"{base}/2/publish", headers=head)
    audit = rows(
        engine,
        "SELECT event, actor, role, payload FROM audit_log"
        " WHERE event LIKE 'RULESET_%' ORDER BY seq",
    )
    assert [a[0] for a in audit] == [
        "RULESET_DRAFT_CREATED", "RULESET_DRAFT_UPDATED", "RULESET_PUBLISHED",
    ]  # fmt: skip
    assert all(a[1] == "admin1" and a[2] == "admin" and json.loads(a[3]) == {"version": 2}
               for a in audit)  # fmt: skip


@pytest.mark.ac("AC-06")
@pytest.mark.nfr("NFR-08")
def test_ac06_published_rule_set_is_immutable_through_api_and_database(
    client: TestClient, engine: Engine
) -> None:
    """E3-S4 AC2 / E5-S5 AC1: PUT is 409 RULESET_IMMUTABLE and raw SQL is refused."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    head = admin(client)
    before = client.get("/api/v1/admin/rule-sets/1", headers=head).json()
    response = client.put(
        "/api/v1/admin/rule-sets/1",
        json={"thresholds": {"low_max": 1, "medium_max": 2}},
        headers=head,
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "RULESET_IMMUTABLE"
    assert client.get("/api/v1/admin/rule-sets/1", headers=head).json() == before
    for sql in ("UPDATE risk_rule_sets SET low_max=1 WHERE version=1",
                "DELETE FROM risk_rule_sets WHERE version=1"):  # fmt: skip
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(text(sql))
