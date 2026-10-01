"""AC-11 / NFR-04: admin user and role management, enforced in the controller layer."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import bearer, staff_headers
from onboardx.controllers.dependencies.services import Services
from onboardx.domain.errors import LastAdminError
from pipeline_helpers import rows
from review_helpers import admin

BASE = "/api/v1/admin/users"
PASSWORD = "synthetic-pass-123"


def create(client: TestClient, username: str = "analyst.two", role: str = "kyc-analyst") -> Any:
    body = {"username": username, "password": PASSWORD, "role": role}
    return client.post(BASE, json=body, headers=admin(client))


def login(client: TestClient, username: str, password: str = PASSWORD) -> Any:
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def user_id(client: TestClient, username: str) -> str:
    listing = client.get(BASE, headers=admin(client)).json()["items"]
    return str(next(u["user_id"] for u in listing if u["username"] == username))


@pytest.mark.ac("AC-11.1")
def test_ac11_1_list_shows_users_without_secrets(client: TestClient) -> None:
    response = client.get(BASE, headers=admin(client))
    assert response.status_code == 200
    items = response.json()["items"]
    assert {u["username"] for u in items} >= {"prospect1", "analyst1", "officer1", "admin1"}
    for user in items:
        assert set(user) == {"user_id", "username", "role", "active", "created_at", "status"}
    assert "pbkdf2" not in response.text


@pytest.mark.ac("AC-11.2")
def test_ac11_2_create_user_stores_only_a_hash_and_can_log_in(
    client: TestClient, engine: Engine
) -> None:
    response = create(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["username"] == "analyst.two" and body["role"] == "kyc-analyst" and body["active"]
    assert PASSWORD not in response.text and "password" not in body
    stored = rows(engine, "SELECT password_hash FROM users WHERE username = 'analyst.two'")
    assert stored[0][0].startswith("pbkdf2_sha256$") and PASSWORD not in stored[0][0]
    assert login(client, "analyst.two").json()["role"] == "kyc-analyst"


@pytest.mark.ac("AC-11.2")
@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"username": "ab", "password": PASSWORD, "role": "admin"}, "username"),
        ({"username": "Bad Name", "password": PASSWORD, "role": "admin"}, "username"),
        ({"username": "ok.user", "password": "short", "role": "admin"}, "password"),
        ({"username": "ok.user", "password": PASSWORD, "role": "prospect"}, "role"),
        ({"username": "ok.user", "password": PASSWORD, "role": "root"}, "role"),
    ],
)
def test_ac11_2_invalid_input_is_422_naming_the_field(
    client: TestClient, body: dict[str, str], field: str
) -> None:
    response = client.post(BASE, json=body, headers=admin(client))
    assert response.status_code == 422
    assert field in {f["field"] for f in response.json()["error"]["details"]["fields"]}


@pytest.mark.ac("AC-11.2")
def test_ac11_2_duplicate_username_is_409(client: TestClient) -> None:
    assert create(client).status_code == 201
    duplicate = create(client)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "USERNAME_TAKEN"


@pytest.mark.ac("AC-11.3")
def test_ac11_3_role_change_validates_and_404s(client: TestClient) -> None:
    create(client)
    uid = user_id(client, "analyst.two")
    url = f"{BASE}/{uid}/role"
    ok = client.put(url, json={"role": "compliance-officer"}, headers=admin(client))
    assert ok.status_code == 200 and ok.json()["role"] == "compliance-officer"
    assert client.put(url, json={"role": "prospect"}, headers=admin(client)).status_code == 422
    missing = client.put(f"{BASE}/nope/role", json={"role": "admin"}, headers=admin(client))
    assert missing.status_code == 404


@pytest.mark.ac("AC-11.4")
def test_ac11_4_deactivated_user_cannot_log_in_and_old_token_dies(client: TestClient) -> None:
    create(client)
    old = bearer(login(client, "analyst.two").json()["access_token"])
    assert client.get("/api/v1/cases", headers=old).status_code == 200
    uid = user_id(client, "analyst.two")
    off = client.post(f"{BASE}/{uid}/deactivate", headers=admin(client))
    assert off.status_code == 200 and off.json()["active"] is False
    assert client.get("/api/v1/cases", headers=old).status_code == 401
    refused = login(client, "analyst.two")
    assert refused.status_code == 401
    assert refused.json() == login(client, "analyst.two", "wrong-password-xyz").json()
    on = client.post(f"{BASE}/{uid}/reactivate", headers=admin(client))
    assert on.json()["active"] is True
    assert login(client, "analyst.two").status_code == 200


@pytest.mark.ac("AC-11.5")
def test_ac11_5_role_change_applies_to_an_already_issued_token(client: TestClient) -> None:
    create(client, "admin.two", "admin")
    token = bearer(login(client, "admin.two").json()["access_token"])
    assert client.get(BASE, headers=token).status_code == 200
    uid = user_id(client, "admin.two")
    client.put(f"{BASE}/{uid}/role", json={"role": "kyc-analyst"}, headers=admin(client))
    assert client.get(BASE, headers=token).status_code == 403
    assert client.get("/api/v1/cases", headers=token).status_code == 200


@pytest.mark.ac("AC-11.6")
def test_ac11_6_an_admin_cannot_modify_their_own_account(client: TestClient) -> None:
    me = user_id(client, "admin1")
    for call in (
        client.post(f"{BASE}/{me}/deactivate", headers=admin(client)),
        client.put(f"{BASE}/{me}/role", json={"role": "kyc-analyst"}, headers=admin(client)),
    ):
        assert call.status_code == 409
        assert call.json()["error"]["code"] == "SELF_MODIFICATION"


@pytest.mark.ac("AC-11.6")
def test_ac11_6_the_last_active_admin_cannot_be_deactivated_or_demoted(
    client: TestClient, services: Services
) -> None:
    """Service-level invariant: unreachable through the API for an active caller, so tested here."""
    target = user_id(client, "admin1")
    with pytest.raises(LastAdminError):
        services.user_admin.deactivate(user_id=target, actor="someone.else")
    with pytest.raises(LastAdminError):
        services.user_admin.change_role(user_id=target, role="kyc-analyst", actor="someone.else")
    create(client, "admin.two", "admin")
    done = services.user_admin.deactivate(user_id=target, actor="someone.else")
    assert done.active is False


@pytest.mark.ac("AC-11.7")
@pytest.mark.nfr("NFR-03")
def test_ac11_7_user_changes_are_audited_without_secrets(
    client: TestClient, engine: Engine
) -> None:
    create(client)
    uid = user_id(client, "analyst.two")
    client.put(f"{BASE}/{uid}/role", json={"role": "admin"}, headers=admin(client))
    client.post(f"{BASE}/{uid}/deactivate", headers=admin(client))
    client.post(f"{BASE}/{uid}/reactivate", headers=admin(client))
    sql = "SELECT event, payload FROM audit_log WHERE event LIKE 'USER_%' ORDER BY seq"
    events = rows(engine, sql)
    assert [e[0] for e in events] == [
        "USER_CREATED", "USER_ROLE_CHANGED", "USER_DEACTIVATED", "USER_REACTIVATED"
    ]  # fmt: skip
    for _, payload in events:
        assert PASSWORD not in payload and "pbkdf2" not in payload and uid in payload


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-11.8")
@pytest.mark.parametrize("user", ["prospect1", "analyst1", "officer1"])
def test_ac11_8_non_admin_roles_are_forbidden_and_anonymous_is_401(
    client: TestClient, user: str
) -> None:
    assert client.get(BASE).status_code == 401
    headers = staff_headers(client, user)
    assert client.get(BASE, headers=headers).status_code == 403
    assert client.post(BASE, json={}, headers=headers).status_code == 403
    assert client.put(f"{BASE}/x/role", json={}, headers=headers).status_code == 403
    assert client.post(f"{BASE}/x/deactivate", headers=headers).status_code == 403
