"""NFR-04 role matrix for every staff and admin route, plus /health (NFR-07)."""

import pytest
from fastapi.testclient import TestClient

from api_helpers import staff_headers
from review_helpers import case_in_review

ROLES = ("prospect1", "analyst1", "officer1", "admin1")
STAFF = {"analyst1", "officer1", "admin1"}
STEPPERS = {"analyst1", "admin1"}
OFFICER = {"officer1"}
ANALYST = {"analyst1"}
ADMIN = {"admin1"}

# (method, path with {c} for the case id, json body, roles that pass the role check)
ROUTES: list[tuple[str, str, dict[str, str] | None, set[str]]] = [
    ("GET", "/api/v1/cases", None, STAFF),
    ("GET", "/api/v1/cases/{c}/evidence", None, STAFF),
    ("GET", "/api/v1/cases/{c}/account", None, STAFF),
    ("GET", "/api/v1/review-queue", None, OFFICER),
    ("POST", "/api/v1/cases/{c}/override", {}, OFFICER),
    ("POST", "/api/v1/cases/{c}/reclassify", {}, OFFICER),
    ("POST", "/api/v1/cases/{c}/screen", None, STEPPERS),
    ("POST", "/api/v1/cases/{c}/classify", None, STEPPERS),
    ("POST", "/api/v1/cases/{c}/decide", None, STEPPERS),
    ("POST", "/api/v1/cases/{c}/advance", None, STEPPERS),
    ("GET", "/api/v1/admin/rule-sets", None, ADMIN),
    ("GET", "/api/v1/admin/rule-sets/1", None, ADMIN),
    ("POST", "/api/v1/admin/rule-sets", None, ADMIN),
    ("PUT", "/api/v1/admin/rule-sets/99", {}, ADMIN),
    ("POST", "/api/v1/admin/rule-sets/99/publish", None, ADMIN),
    ("GET", "/api/v1/admin/watchlist", None, ADMIN),
    ("POST", "/api/v1/admin/watchlist", {}, ADMIN),
    ("POST", "/api/v1/admin/watchlist/x/deactivate", None, ADMIN),
    ("GET", "/api/v1/admin/reports/tat", None, ADMIN),
    ("GET", "/api/v1/admin/reports/funnel", None, ADMIN),
    ("GET", "/api/v1/admin/reports/backlog", None, ADMIN),
    ("GET", "/api/v1/admin/reports/time-per-stage", None, ADMIN),
    ("GET", "/api/v1/admin/reports/rejection-reasons", None, ADMIN),
    ("GET", "/api/v1/admin/reports/auto-approval", None, ADMIN),
    ("GET", "/api/v1/admin/reports/dropped-leads", None, ADMIN),
    ("GET", "/api/v1/admin/users", None, ADMIN),
    ("POST", "/api/v1/admin/users", {}, ADMIN),
    ("PUT", "/api/v1/admin/users/x/role", {}, ADMIN),
    ("POST", "/api/v1/admin/users/x/deactivate", None, ADMIN),
    ("POST", "/api/v1/admin/users/x/reactivate", None, ADMIN),
    ("GET", "/api/v1/admin/checklists", None, ADMIN),
    ("POST", "/api/v1/admin/checklists/Savings", {}, ADMIN),
    ("GET", "/api/v1/cases/{c}/queries", None, STAFF),
    ("POST", "/api/v1/cases/{c}/queries", {}, ANALYST),
    ("POST", "/api/v1/cases/{c}/queries/x/close", None, ANALYST),
    ("POST", "/api/v1/cases/{c}/queries/x/responses", {"message": "x"}, set()),
]


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("route", ROUTES, ids=lambda r: f"{r[0]} {r[1]}")
def test_nfr04_role_matrix_for_all_four_roles_and_no_token(
    client: TestClient, route: tuple[str, str, dict[str, str] | None, set[str]]
) -> None:
    """Every route: 401 without a token, 403 for roles outside the matrix, passed otherwise."""
    method, template, body, allowed = route
    url = template.replace("{c}", case_in_review(client)["case_id"])
    anonymous = client.request(method, url, json=body)
    assert anonymous.status_code == 401, url
    for user in ROLES:
        response = client.request(method, url, json=body, headers=staff_headers(client, user))
        if user in allowed:
            assert response.status_code not in (401, 403), (url, user, response.status_code)
        else:
            assert response.status_code == 403, (url, user, response.status_code)
            assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.nfr("NFR-07")
def test_nfr07_health_is_public_and_ok(client: TestClient) -> None:
    """NFR-07: GET /health answers without a token."""
    response = client.get("/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
