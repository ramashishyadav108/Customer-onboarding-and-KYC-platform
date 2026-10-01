"""AC-14.8 to AC-14.9 / NFR-04: staff accounts requested at sign-up need admin approval."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import bearer, staff_headers
from helpers import JWT_SECRET, FakeClock
from onboardx.config.settings import ConfigurationError, Settings, load_settings
from onboardx.main import create_app
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


# --- AC-14.11: ADMIN_SIGNUP=open lets an admin sign-up skip approval (staff roles do not) ---


@pytest.fixture
def open_admin_client(db_url: str, upload_dir: Path, clock: FakeClock) -> Iterator[TestClient]:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url=db_url,
        jwt_secret=JWT_SECRET,
        upload_dir=upload_dir,
        admin_signup="open",
    )
    with TestClient(create_app(settings, clock=clock)) as client:
        yield client


@pytest.mark.ac("AC-14.11")
def test_ac14_11_approval_is_the_default_for_admin_sign_up(client: TestClient) -> None:
    options = client.get("/api/v1/auth/signup-options")
    assert options.status_code == 200
    assert options.json() == {"admin_requires_approval": True, "staff_requires_approval": True}
    assert request_staff(client, "wants.admin", "admin").json()["status"] == "PENDING_APPROVAL"


@pytest.mark.ac("AC-14.11")
def test_ac14_11_open_admin_sign_up_creates_an_active_admin_with_a_token(
    open_admin_client: TestClient, engine: Engine
) -> None:
    options = open_admin_client.get("/api/v1/auth/signup-options").json()
    assert options == {"admin_requires_approval": False, "staff_requires_approval": True}
    response = request_staff(open_admin_client, "new.admin", "admin")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ACTIVE" and body["role"] == "admin" and body["access_token"]
    stored = rows(engine, "SELECT role, active, pending FROM users WHERE username='new.admin'")
    assert tuple(stored[0]) == ("admin", 1, 0)
    token = bearer(body["access_token"])
    assert open_admin_client.get(USERS, headers=token).status_code == 200
    audit = rows(engine, "SELECT role, payload FROM audit_log WHERE event='USER_SIGNED_UP'")
    assert audit[0][0] == "admin" and PASSWORD not in audit[0][1] and "pbkdf2" not in audit[0][1]


@pytest.mark.ac("AC-14.11")
def test_ac14_11_open_admin_sign_up_can_log_in_afterwards(open_admin_client: TestClient) -> None:
    request_staff(open_admin_client, "new.admin", "admin")
    session = login(open_admin_client, "new.admin")
    assert session.status_code == 200 and session.json()["role"] == "admin"


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-14.11")
@pytest.mark.parametrize("role", ["kyc-analyst", "compliance-officer"])
def test_ac14_11_analyst_and_officer_still_need_approval_when_admin_sign_up_is_open(
    open_admin_client: TestClient, role: str
) -> None:
    body = request_staff(open_admin_client, "staff.request", role).json()
    assert body["status"] == "PENDING_APPROVAL" and body["access_token"] is None
    assert login(open_admin_client, "staff.request").status_code == 403


@pytest.mark.ac("AC-14.11")
def test_ac14_11_an_unknown_admin_signup_value_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_SIGNUP", "anyone")
    with pytest.raises(ConfigurationError, match="ADMIN_SIGNUP"):
        load_settings()
