"""AC-14 / NFR-04: prospect sign-up, sign-in and account-linked cases; staff is not self-service."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import VALID_LEAD, bearer, create_lead, staff_headers
from helpers import make_token
from pipeline_helpers import rows
from review_helpers import admin

SIGNUP = "/api/v1/auth/signup"
PASSWORD = "synthetic-pass-123"


def signup(client: TestClient, username: str = "meera.nair", **extra: Any) -> Any:
    return client.post(SIGNUP, json={"username": username, "password": PASSWORD, **extra})


def login(client: TestClient, username: str, password: str = PASSWORD) -> Any:
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def register_lead(client: TestClient, token: str, **overrides: Any) -> Any:
    return client.post("/api/v1/leads", json={**VALID_LEAD, **overrides}, headers=bearer(token))


@pytest.mark.ac("AC-14.1")
def test_ac14_1_signup_creates_a_prospect_with_no_case_and_stores_only_a_hash(
    client: TestClient, engine: Engine
) -> None:
    response = signup(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "prospect" and body["case_id"] is None
    assert body["token_type"] == "bearer" and body["access_token"] and body["expires_in"] > 0
    stored = rows(
        engine, "SELECT password_hash, role, active, case_id FROM users WHERE username='meera.nair'"
    )
    assert stored[0][0].startswith("pbkdf2_sha256$") and PASSWORD not in stored[0][0]
    assert tuple(stored[0])[1:] == ("prospect", 1, None)
    assert PASSWORD not in response.text


@pytest.mark.ac("AC-14.1")
@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"username": "ab", "password": PASSWORD}, "username"),
        ({"username": "Bad Name", "password": PASSWORD}, "username"),
        ({"username": "ok.user", "password": "short"}, "password"),
        ({"username": "ok.user", "password": "x" * 129}, "password"),
    ],
)
def test_ac14_1_invalid_signup_is_422_naming_the_field(
    client: TestClient, body: dict[str, str], field: str
) -> None:
    response = client.post(SIGNUP, json=body)
    assert response.status_code == 422
    assert field in {f["field"] for f in response.json()["error"]["details"]["fields"]}


@pytest.mark.ac("AC-14.1")
@pytest.mark.parametrize("name", ["meera.nair", "admin1", "officer1"])
def test_ac14_1_taken_usernames_are_409_including_seeded_staff(
    client: TestClient, name: str
) -> None:
    if name == "meera.nair":
        assert signup(client, name).status_code == 201
    second = signup(client, name)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "USERNAME_TAKEN"


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-14.2")
@pytest.mark.parametrize("role", ["kyc-analyst", "compliance-officer", "admin"])
def test_ac14_2_a_requested_staff_role_is_pending_with_no_token_and_no_access(
    client: TestClient, engine: Engine, role: str
) -> None:
    response = signup(client, role=role)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PENDING_APPROVAL" and body["role"] == role
    assert body["access_token"] is None
    stored = rows(engine, "SELECT role, active, pending FROM users WHERE username='meera.nair'")
    assert tuple(stored[0]) == (role, 0, 1)


@pytest.mark.ac("AC-14.2")
def test_ac14_2_prospect_is_the_default_role_and_can_be_explicit(client: TestClient) -> None:
    default = signup(client).json()
    assert default["status"] == "ACTIVE" and default["role"] == "prospect"
    explicit = signup(client, "second.user", role="prospect").json()
    assert explicit["status"] == "ACTIVE" and explicit["access_token"]


@pytest.mark.ac("AC-14.2")
@pytest.mark.parametrize("role", ["root", "", "ADMIN", 5])
def test_ac14_2_an_unknown_role_is_422(client: TestClient, role: object) -> None:
    response = client.post(SIGNUP, json={"username": "ok.user", "password": PASSWORD, "role": role})
    assert response.status_code == 422
    assert "role" in {f["field"] for f in response.json()["error"]["details"]["fields"]}


@pytest.mark.ac("AC-14.3")
def test_ac14_3_a_signed_in_prospect_registers_a_lead_linked_to_the_account(
    client: TestClient, engine: Engine
) -> None:
    token = signup(client).json()["access_token"]
    response = register_lead(client, token)
    assert response.status_code == 201, response.text
    lead = response.json()
    linked = rows(engine, "SELECT case_id FROM users WHERE username='meera.nair'")
    assert linked[0][0] == lead["case_id"]
    own = client.get(f"/api/v1/cases/{lead['case_id']}", headers=bearer(lead["access_token"]))
    assert own.status_code == 200


@pytest.mark.ac("AC-14.3")
def test_ac14_3_a_second_lead_from_the_same_account_is_409(client: TestClient) -> None:
    token = signup(client).json()["access_token"]
    first = register_lead(client, token)
    second = register_lead(client, token, contact="9999999922")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CASE_EXISTS"
    again = register_lead(client, first.json()["access_token"], contact="9999999923")
    assert again.status_code == 409


@pytest.mark.ac("AC-14.3")
def test_ac14_3_anonymous_lead_registration_still_works(client: TestClient, engine: Engine) -> None:
    lead = create_lead(client)
    assert lead["access_token"]
    assert rows(engine, "SELECT COUNT(*) FROM users WHERE case_id IS NOT NULL")[0][0] == 0


@pytest.mark.ac("AC-14.3")
def test_ac14_3_staff_and_anonymous_case_tokens_register_leads_without_linking(
    client: TestClient, engine: Engine
) -> None:
    anonymous = create_lead(client)
    assert register_lead(client, anonymous["access_token"], contact="9999999922").status_code == 201
    staff = register_lead(
        client, staff_headers(client)["Authorization"].split()[1], contact="9999999923"
    )
    assert staff.status_code == 201
    assert rows(engine, "SELECT COUNT(*) FROM users WHERE case_id IS NOT NULL")[0][0] == 0


@pytest.mark.ac("AC-14.4")
def test_ac14_4_login_returns_the_linked_case_and_a_token_bound_to_it(client: TestClient) -> None:
    token = signup(client).json()["access_token"]
    before = login(client, "meera.nair").json()
    assert before["role"] == "prospect" and before["case_id"] is None
    lead = register_lead(client, token).json()
    after = login(client, "meera.nair").json()
    assert after["case_id"] == lead["case_id"]
    other = create_lead(client, contact="9999999922")
    mine = bearer(after["access_token"])
    assert client.get(f"/api/v1/cases/{lead['case_id']}", headers=mine).status_code == 200
    assert client.get(f"/api/v1/cases/{other['case_id']}", headers=mine).status_code == 403


@pytest.mark.ac("AC-14.4")
def test_ac14_4_a_prospect_without_a_case_cannot_read_any_case(client: TestClient) -> None:
    token = signup(client).json()["access_token"]
    other = create_lead(client)
    assert client.get(f"/api/v1/cases/{other['case_id']}", headers=bearer(token)).status_code == 403


@pytest.mark.ac("AC-14.5")
def test_ac14_5_deactivating_a_prospect_account_kills_login_and_its_token(
    client: TestClient,
) -> None:
    token = signup(client).json()["access_token"]
    lead = register_lead(client, token).json()
    mine = bearer(lead["access_token"])
    assert client.get(f"/api/v1/cases/{lead['case_id']}", headers=mine).status_code == 200
    users = client.get("/api/v1/admin/users", headers=admin(client)).json()["items"]
    uid = next(u["user_id"] for u in users if u["username"] == "meera.nair")
    assert (
        client.post(f"/api/v1/admin/users/{uid}/deactivate", headers=admin(client)).status_code
        == 200
    )
    assert client.get(f"/api/v1/cases/{lead['case_id']}", headers=mine).status_code == 401
    assert login(client, "meera.nair").status_code == 401


@pytest.mark.ac("AC-14.5")
def test_ac14_5_anonymous_case_tokens_are_not_affected_by_the_user_store(
    client: TestClient,
) -> None:
    lead = create_lead(client)
    response = client.get(f"/api/v1/cases/{lead['case_id']}", headers=bearer(lead["access_token"]))
    assert response.status_code == 200


@pytest.mark.nfr("NFR-03")
@pytest.mark.ac("AC-14.6")
def test_ac14_6_signup_is_audited_without_secrets(client: TestClient, engine: Engine) -> None:
    signup(client)
    events = rows(engine, "SELECT event, role, payload FROM audit_log WHERE event='USER_SIGNED_UP'")
    assert len(events) == 1 and events[0][1] == "prospect"
    assert PASSWORD not in events[0][2] and "pbkdf2" not in events[0][2]
    assert "meera.nair" not in events[0][2]


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-14.5")
def test_ac14_5_a_forged_prospect_account_token_for_an_unknown_user_is_401(
    client: TestClient,
) -> None:
    forged = bearer(make_token("prospect"))
    assert client.get("/api/v1/cases/x", headers=forged).status_code == 401
    assert client.post("/api/v1/leads", json=VALID_LEAD, headers=forged).status_code == 401
