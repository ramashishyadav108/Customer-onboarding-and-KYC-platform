"""AC-14.8 to AC-14.9 / NFR-04: staff accounts requested at sign-up need admin approval."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import bearer, staff_headers
from pipeline_helpers import rows
from review_helpers import admin

PASSWORD = "synthetic-pass-123"
USERS = "/api/v1/admin/users"


def request_staff(
    client: TestClient, username: str = "officer.two", role: str = "compliance-officer"
) -> Any:
    body = {"username": username, "password": PASSWORD, "role": role}
    return client.post("/api/v1/auth/signup", json=body)


def login(client: TestClient, username: str, password: str = PASSWORD) -> Any:
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def uid(client: TestClient, username: str) -> str:
    items = client.get(USERS, headers=admin(client)).json()["items"]
    return str(next(u["user_id"] for u in items if u["username"] == username))


def status_of(client: TestClient, username: str) -> str:
    items = client.get(USERS, headers=admin(client)).json()["items"]
    return str(next(u["status"] for u in items if u["username"] == username))


@pytest.mark.ac("AC-14.8")
def test_ac14_8_a_pending_account_cannot_sign_in_but_the_reason_is_clear(
    client: TestClient,
) -> None:
    request_staff(client)
    pending = login(client, "officer.two")
    assert pending.status_code == 403
    assert pending.json()["error"]["code"] == "ACCOUNT_PENDING"
    wrong = login(client, "officer.two", "wrong-password-xyz")
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.ac("AC-14.9")
def test_ac14_9_the_admin_list_shows_a_status_for_every_account(client: TestClient) -> None:
    request_staff(client)
    assert status_of(client, "officer.two") == "PENDING"
    assert status_of(client, "admin1") == "ACTIVE"
    client.post(f"{USERS}/{uid(client, 'analyst1')}/deactivate", headers=admin(client))
    assert status_of(client, "analyst1") == "DEACTIVATED"


@pytest.mark.ac("AC-14.9")
def test_ac14_9_approval_activates_the_account_with_the_requested_role(
    client: TestClient, engine: Engine
) -> None:
    request_staff(client)
    done = client.post(f"{USERS}/{uid(client, 'officer.two')}/approve", headers=admin(client))
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "ACTIVE" and done.json()["role"] == "compliance-officer"
    session = login(client, "officer.two")
    assert session.status_code == 200 and session.json()["role"] == "compliance-officer"
    queue = client.get("/api/v1/review-queue", headers=bearer(session.json()["access_token"]))
    assert queue.status_code == 200
    audit = rows(engine, "SELECT payload FROM audit_log WHERE event = 'USER_APPROVED'")
    assert len(audit) == 1 and PASSWORD not in audit[0][0] and "pbkdf2" not in audit[0][0]


@pytest.mark.ac("AC-14.9")
def test_ac14_9_the_admin_can_change_the_role_while_approving(client: TestClient) -> None:
    request_staff(client, "wants.admin", "admin")
    done = client.post(
        f"{USERS}/{uid(client, 'wants.admin')}/approve",
        json={"role": "kyc-analyst"},
        headers=admin(client),
    )
    assert done.status_code == 200 and done.json()["role"] == "kyc-analyst"
    assert login(client, "wants.admin").json()["role"] == "kyc-analyst"
    forbidden = client.get(
        USERS, headers=bearer(login(client, "wants.admin").json()["access_token"])
    )
    assert forbidden.status_code == 403


@pytest.mark.ac("AC-14.9")
def test_ac14_9_rejection_closes_the_request_and_the_account_stays_inactive(
    client: TestClient, engine: Engine
) -> None:
    request_staff(client)
    done = client.post(f"{USERS}/{uid(client, 'officer.two')}/reject", headers=admin(client))
    assert done.status_code == 200 and done.json()["status"] == "DEACTIVATED"
    refused = login(client, "officer.two")
    assert refused.status_code == 401
    assert rows(engine, "SELECT COUNT(*) FROM audit_log WHERE event = 'USER_REJECTED'")[0][0] == 1


@pytest.mark.ac("AC-14.9")
def test_ac14_9_approve_and_reject_only_apply_to_pending_accounts(client: TestClient) -> None:
    target = uid(client, "analyst1")
    for action in ("approve", "reject"):
        response = client.post(f"{USERS}/{target}/{action}", headers=admin(client))
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "NOT_PENDING"
    assert client.post(f"{USERS}/nope/approve", headers=admin(client)).status_code == 404
    request_staff(client)
    pending = uid(client, "officer.two")
    assert (
        client.post(
            f"{USERS}/{pending}/approve", json={"role": "prospect"}, headers=admin(client)
        ).status_code
        == 422
    )


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-14.9")
@pytest.mark.parametrize("user", ["prospect1", "analyst1", "officer1"])
def test_ac14_9_only_admins_can_approve_or_reject(client: TestClient, user: str) -> None:
    request_staff(client)
    pending = uid(client, "officer.two")
    headers = staff_headers(client, user)
    assert client.post(f"{USERS}/{pending}/approve", headers=headers).status_code == 403
    assert client.post(f"{USERS}/{pending}/reject", headers=headers).status_code == 403
    assert client.post(f"{USERS}/{pending}/approve").status_code == 401
    assert status_of(client, "officer.two") == "PENDING"


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-14.9")
def test_ac14_9_a_pending_admin_request_gives_no_admin_power(client: TestClient) -> None:
    request_staff(client, "wants.admin", "admin")
    assert login(client, "wants.admin").status_code == 403
    users = client.get(USERS, headers=admin(client)).json()["items"]
    assert sum(1 for u in users if u["role"] == "admin" and u["status"] == "ACTIVE") == 1
