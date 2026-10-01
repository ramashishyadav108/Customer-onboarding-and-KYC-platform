"""Helpers for document, submission and pipeline tests (synthetic data only, data-models 5)."""

from typing import Any

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine, text

from api_helpers import VALID_PROFILE, bearer, create_lead, lead_headers, staff_headers

CONTENT_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png"}
PDF_BYTES = b"%PDF-1.4 synthetic fixture"
JPEG_BYTES = bytes.fromhex("ffd8ff") + b" synthetic fixture"
PNG_BYTES = bytes.fromhex("89504e470d0a1a0a") + b" synthetic fixture"
FIXTURE_BYTES = {"pdf": PDF_BYTES, "jpg": JPEG_BYTES, "png": PNG_BYTES}

GOOD_FILES: dict[str, dict[str, str]] = {
    "Savings": {
        "ID_PROOF": "pan_valid.pdf",
        "ADDRESS_PROOF": "utility-bill_valid.pdf",
        "PHOTOGRAPH": "photograph_valid.jpg",
    },
    "Current": {
        "ID_PROOF": "pan_valid.pdf",
        "ADDRESS_PROOF": "utility-bill_valid.pdf",
        "PHOTOGRAPH": "photograph_valid.jpg",
        "BUSINESS_PROOF": "gst-certificate_valid.pdf",
    },
    "NRE": {
        "ID_PROOF": "passport_valid.png",
        "ADDRESS_PROOF": "aadhaar_valid.jpg",
        "PHOTOGRAPH": "photograph_valid.jpg",
        "OVERSEAS_ADDRESS_PROOF": "visa_valid.pdf",
    },
}

PROFILE_A = dict(VALID_PROFILE)  # score 16 LOW
PROFILE_C = {
    "date_of_birth": "1960-03-01",
    "annual_income": 12000000,
    "occupation_category": "BUSINESS_OWNER",
    "country_code": "GB",
}  # score 45 MEDIUM
PROFILE_D = {
    "date_of_birth": "1960-03-01",
    "annual_income": 12000000,
    "occupation_category": "CASH_INTENSIVE",
    "country_code": "KP",
}  # score 72 HIGH


def content_type_for(filename: str) -> str:
    return CONTENT_TYPES[filename.rsplit(".", 1)[-1].lower()]


def bytes_for(filename: str) -> bytes:
    """Synthetic content whose magic bytes match the extension (AC-02.4a)."""
    return FIXTURE_BYTES[filename.rsplit(".", 1)[-1].lower()]


def upload(
    client: TestClient,
    lead: dict[str, Any],
    item: str,
    filename: str,
    content: bytes | None = None,
    content_type: str | None = None,
) -> Response:
    body = bytes_for(filename) if content is None else content
    files = {"file": (filename, body, content_type or content_type_for(filename))}
    return client.post(
        f"/api/v1/cases/{lead['case_id']}/documents",
        data={"checklist_item": item},
        files=files,
        headers=lead_headers(lead),
    )


def upload_ok(client: TestClient, lead: dict[str, Any], item: str, filename: str) -> dict[str, Any]:
    response = upload(client, lead, item, filename)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def put_profile(client: TestClient, lead: dict[str, Any], profile: dict[str, Any]) -> None:
    response = client.put(
        f"/api/v1/cases/{lead['case_id']}/profile", json=profile, headers=lead_headers(lead)
    )
    assert response.status_code == 200, response.text


def upload_all(
    client: TestClient, lead: dict[str, Any], product: str, overrides: dict[str, str] | None = None
) -> None:
    files = {**GOOD_FILES[product], **(overrides or {})}
    for item, filename in files.items():
        upload_ok(client, lead, item, filename)


def ready_case(
    client: TestClient,
    *,
    name: str = "Test Person Alpha",
    product: str = "Savings",
    profile: dict[str, Any] | None = None,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """A lead with profile and every mandatory document uploaded, not yet submitted."""
    lead = create_lead(client, name=name, product=product)
    put_profile(client, lead, profile or PROFILE_A)
    upload_all(client, lead, product, overrides)
    return lead


def submit(client: TestClient, lead: dict[str, Any]) -> Response:
    return client.post(f"/api/v1/cases/{lead['case_id']}/submit", headers=lead_headers(lead))


def submitted_case(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    lead = ready_case(client, **kwargs)
    response = submit(client, lead)
    assert response.status_code == 200, response.text
    return lead


def step(client: TestClient, lead: dict[str, Any], name: str, user: str = "analyst1") -> Response:
    return client.post(
        f"/api/v1/cases/{lead['case_id']}/{name}", headers=staff_headers(client, user)
    )


def get_case(client: TestClient, lead: dict[str, Any]) -> dict[str, Any]:
    response = client.get(f"/api/v1/cases/{lead['case_id']}", headers=lead_headers(lead))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def state_of(client: TestClient, lead: dict[str, Any]) -> str:
    return str(get_case(client, lead)["state"])


def reject(
    client: TestClient,
    lead: dict[str, Any],
    document_id: str,
    reason: str = "DOC_ILLEGIBLE",
    user: str = "analyst1",
    **extra: Any,
) -> Response:
    return client.post(
        f"/api/v1/cases/{lead['case_id']}/documents/{document_id}/reject",
        json={"reason_code": reason, **extra},
        headers=staff_headers(client, user),
    )


def notifications(client: TestClient, lead: dict[str, Any]) -> list[dict[str, Any]]:
    response = client.get(
        f"/api/v1/cases/{lead['case_id']}/notifications", headers=lead_headers(lead)
    )
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["notifications"]
    return items


def history(engine: Engine, case_id: str) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT to_state FROM state_history WHERE case_id=:c ORDER BY seq"),
            {"c": case_id},
        )
        return [str(r[0]) for r in rows]


def rows(engine: Engine, sql: str, **params: Any) -> list[Any]:
    with engine.connect() as conn:
        return list(conn.execute(text(sql), params))


def other_prospect_headers(client: TestClient) -> dict[str, str]:
    other = create_lead(client, name="Test Person Other")
    return bearer(other["access_token"])
