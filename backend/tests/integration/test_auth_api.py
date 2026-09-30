"""NFR-04 / E1-S2: login, JWT expiry, role boundaries and prospect case binding."""

import jwt
import pytest
from fastapi.testclient import TestClient

from api_helpers import DEMO_PASSWORDS, bearer, create_lead, lead_headers, staff_headers
from helpers import JWT_SECRET, FakeClock, auth_header, make_token
from onboardx.config.settings import Settings
from onboardx.main import create_app

STAFF = ["analyst1", "officer1", "admin1"]
ROLE_OF = {
    "prospect1": "prospect",
    "analyst1": "kyc-analyst",
    "officer1": "compliance-officer",
    "admin1": "admin",
}


def login(client: TestClient, username: str, password: str) -> object:
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("username", sorted(ROLE_OF))
def test_nfr04_login_returns_bearer_token_and_role(client: TestClient, username: str) -> None:
    """E1-S2 AC1: valid login returns 200, access_token, token_type bearer and role."""
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": DEMO_PASSWORDS[username]}
    )
    body = response.json()
    assert response.status_code == 200
    assert body["token_type"] == "bearer" and body["role"] == ROLE_OF[username]
    assert body["expires_in"] == 1800 and body["case_id"] is None
    claims = jwt.decode(body["access_token"], JWT_SECRET, algorithms=["HS256"])
    assert claims["role"] == ROLE_OF[username]
    assert jwt.get_unverified_header(body["access_token"])["alg"] == "HS256"


@pytest.mark.nfr("NFR-04")
def test_nfr04_wrong_password_and_unknown_user_are_indistinguishable(client: TestClient) -> None:
    """E1-S2 AC1: 401 with the same body for wrong password and unknown user."""
    wrong = client.post("/api/v1/auth/login", json={"username": "analyst1", "password": "nope"})
    unknown = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "UNAUTHENTICATED"
    text = wrong.text.lower()
    assert "password" not in text and "username" not in text


@pytest.mark.nfr("NFR-04")
def test_nfr04_responses_never_contain_password_material(client: TestClient) -> None:
    """E1-S2 AC2: neither hashes nor passwords appear in login responses."""
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin1", "password": DEMO_PASSWORDS["admin1"]}
    )
    assert "pbkdf2" not in response.text and DEMO_PASSWORDS["admin1"] not in response.text


@pytest.mark.nfr("NFR-04")
def test_nfr04_login_validation_error_is_422_envelope(client: TestClient) -> None:
    """NFR-04: a missing password is a 422 VALIDATION_ERROR with a field list."""
    response = client.post("/api/v1/auth/login", json={"username": "admin1"})
    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"][0]["field"] == "password"


@pytest.mark.nfr("NFR-04")
def test_nfr04_protected_endpoint_without_token_is_401(client: TestClient) -> None:
    """E1-S2 AC3: no token -> 401 with the error envelope."""
    response = client.get("/api/v1/cases")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize(
    "header",
    [
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Basic abc"},
        {"Authorization": f"Bearer {make_token(secret='x' * 40)}"},
        {"Authorization": f"Bearer {make_token(role='superuser')}"},
        {"Authorization": f"Bearer {make_token(ttl=-10)}"},
    ],
    ids=["garbage", "wrong-scheme", "bad-signature", "unknown-role", "expired"],
)
def test_nfr04_invalid_tokens_are_401(client: TestClient, header: dict[str, str]) -> None:
    """E1-S2 AC3/AC4: malformed, forged, unknown-role and expired tokens are 401."""
    assert client.get("/api/v1/cases", headers=header).status_code == 401


@pytest.mark.nfr("NFR-04")
def test_nfr04_unauthorised_role_is_403_with_required_roles(client: TestClient) -> None:
    """E1-S2 AC3: a valid token of an unauthorised role is 403 FORBIDDEN."""
    response = client.get("/api/v1/cases", headers=auth_header("prospect"))
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "FORBIDDEN"
    assert error["details"]["required_roles"] == ["admin", "compliance-officer", "kyc-analyst"]


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize(
    ("username", "status"),
    [("prospect1", 403), ("analyst1", 200), ("officer1", 200), ("admin1", 200)],
)
def test_nfr04_role_matrix_for_case_list(client: TestClient, username: str, status: int) -> None:
    """NFR-04: GET /cases is staff only."""
    headers = staff_headers(client, username)
    assert client.get("/api/v1/cases", headers=headers).status_code == status


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize(
    ("username", "status"),
    [("prospect1", 403), ("analyst1", 403), ("officer1", 403), ("admin1", 200)],
)
def test_nfr04_role_matrix_for_admin_rule_sets(
    client: TestClient, username: str, status: int
) -> None:
    """NFR-04: rule-set administration is admin only."""
    headers = staff_headers(client, username)
    assert client.get("/api/v1/admin/rule-sets", headers=headers).status_code == status


@pytest.mark.nfr("NFR-04")
def test_nfr04_token_expires_after_the_ttl(
    app: object, client: TestClient, clock: FakeClock
) -> None:
    """E1-S2 AC4: a token presented after its TTL is 401; before it, 200."""
    headers = staff_headers(client)
    assert client.get("/api/v1/cases", headers=headers).status_code == 200
    clock.advance(1799)
    assert client.get("/api/v1/cases", headers=headers).status_code == 200
    clock.advance(2)
    assert client.get("/api/v1/cases", headers=headers).status_code == 401


@pytest.mark.nfr("NFR-04")
def test_nfr04_token_ttl_is_configurable(db_url: str, clock: FakeClock) -> None:
    """E1-S2 AC4: TOKEN_TTL_SECONDS controls expires_in and expiry."""
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, database_url=db_url, jwt_secret=JWT_SECRET, token_ttl_seconds=30
    )
    with TestClient(create_app(settings, clock=clock)) as client:
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin1", "password": DEMO_PASSWORDS["admin1"]}
        )
        assert response.json()["expires_in"] == 30
        headers = bearer(response.json()["access_token"])
        clock.advance(31)
        assert client.get("/api/v1/cases", headers=headers).status_code == 401


@pytest.mark.nfr("NFR-04")
def test_nfr04_prospect_token_is_bound_to_one_case(client: TestClient) -> None:
    """E1-S2 AC5: a prospect reads its own case (200) and gets 403 for any other case."""
    mine = create_lead(client, name="Test Person One")
    other = create_lead(client, name="Test Person Two")
    assert (
        client.get(f"/api/v1/cases/{mine['case_id']}", headers=lead_headers(mine)).status_code
        == 200
    )
    response = client.get(f"/api/v1/cases/{other['case_id']}", headers=lead_headers(mine))
    assert response.status_code == 403 and response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.nfr("NFR-04")
def test_nfr04_prospect_cannot_probe_unknown_cases(client: TestClient) -> None:
    """NFR-04: a prospect gets 403 (not 404) for an unknown case id, so ids cannot be probed."""
    mine = create_lead(client)
    response = client.get(
        "/api/v1/cases/00000000-0000-4000-8000-00000000dead", headers=lead_headers(mine)
    )
    assert response.status_code == 403


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("username", STAFF)
def test_nfr04_staff_roles_can_read_any_case(client: TestClient, username: str) -> None:
    """E1-S2 AC5: staff roles read any case."""
    lead = create_lead(client)
    response = client.get(
        f"/api/v1/cases/{lead['case_id']}", headers=staff_headers(client, username)
    )
    assert response.status_code == 200


@pytest.mark.nfr("NFR-04")
def test_nfr04_seeded_prospect_without_a_case_cannot_read_cases(client: TestClient) -> None:
    """NFR-04: prospect1 is bound to no case and therefore reads none."""
    lead = create_lead(client)
    headers = staff_headers(client, "prospect1")
    assert client.get(f"/api/v1/cases/{lead['case_id']}", headers=headers).status_code == 403


@pytest.mark.nfr("NFR-04")
def test_nfr04_staff_cannot_update_a_profile(client: TestClient) -> None:
    """NFR-04: PUT profile is owner-only; staff get 403."""
    lead = create_lead(client)
    response = client.put(
        f"/api/v1/cases/{lead['case_id']}/profile", json={}, headers=staff_headers(client)
    )
    assert response.status_code == 403


@pytest.mark.nfr("NFR-04")
def test_nfr04_unknown_route_uses_the_error_envelope(client: TestClient) -> None:
    """NFR-04: unknown paths return the stable NOT_FOUND envelope."""
    response = client.get("/api/v1/nothing-here")
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"
