"""AC-16 / NFR-02 / NFR-03 / NFR-04: staff and the owner can open the uploaded file itself."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import bearer, create_lead, staff_headers
from pipeline_helpers import PDF_BYTES, rows, upload_ok

SECRET_NAME = "pan_ABCDE1234F_private.pdf"


def file_url(lead: dict[str, Any], document_id: str) -> str:
    return f"/api/v1/cases/{lead['case_id']}/documents/{document_id}/file"


def uploaded(client: TestClient, lead: dict[str, Any], name: str = "pan_valid.pdf") -> str:
    return str(upload_ok(client, lead, "ID_PROOF", name)["document_id"])


@pytest.mark.ac("AC-16.1")
def test_ac16_1_the_owner_gets_back_the_exact_bytes_with_safe_headers(client: TestClient) -> None:
    lead = create_lead(client)
    document_id = uploaded(client, lead, SECRET_NAME)
    response = client.get(file_url(lead, document_id), headers=bearer(lead["access_token"]))
    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("inline;") and "ID_PROOF" in disposition
    assert "ABCDE1234F" not in disposition and SECRET_NAME not in disposition


@pytest.mark.ac("AC-16.1")
@pytest.mark.parametrize("role_user", ["analyst1", "officer1", "admin1"])
def test_ac16_1_every_staff_role_can_open_a_customers_document(
    client: TestClient, role_user: str
) -> None:
    lead = create_lead(client)
    document_id = uploaded(client, lead)
    response = client.get(file_url(lead, document_id), headers=staff_headers(client, role_user))
    assert response.status_code == 200 and response.content == PDF_BYTES


@pytest.mark.ac("AC-16.2")
def test_ac16_2_images_keep_their_content_type(client: TestClient) -> None:
    lead = create_lead(client)
    document_id = str(upload_ok(client, lead, "PHOTOGRAPH", "photograph_valid.jpg")["document_id"])
    response = client.get(file_url(lead, document_id), headers=staff_headers(client))
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    assert "PHOTOGRAPH" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.jpg"')


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-16.3")
def test_ac16_3_other_prospects_and_anonymous_callers_are_refused(client: TestClient) -> None:
    lead = create_lead(client)
    other = create_lead(client, contact="9999999922")
    document_id = uploaded(client, lead)
    url = file_url(lead, document_id)
    assert client.get(url).status_code == 401
    assert client.get(url, headers=bearer(other["access_token"])).status_code == 403
    assert client.get(url, headers=staff_headers(client, "prospect1")).status_code == 403


@pytest.mark.ac("AC-16.4")
def test_ac16_4_unknown_documents_and_documents_of_another_case_are_404(client: TestClient) -> None:
    lead = create_lead(client)
    other = create_lead(client, contact="9999999922")
    mine = uploaded(client, lead)
    headers = staff_headers(client)
    assert client.get(file_url(lead, "no-such-document"), headers=headers).status_code == 404
    assert client.get(file_url(other, mine), headers=headers).status_code == 404
    ghost = {"case_id": "00000000-0000-4000-8000-0000000000ff"}
    assert client.get(file_url(ghost, mine), headers=headers).status_code == 404


@pytest.mark.ac("AC-16.5")
def test_ac16_5_earlier_versions_stay_viewable_by_staff(client: TestClient) -> None:
    lead = create_lead(client)
    first = uploaded(client, lead, "pan_valid.pdf")
    second = uploaded(client, lead, "pan_v2.pdf")
    headers = staff_headers(client)
    assert client.get(file_url(lead, first), headers=headers).status_code == 200
    assert client.get(file_url(lead, second), headers=headers).status_code == 200


@pytest.mark.nfr("NFR-03")
@pytest.mark.ac("AC-16.6")
def test_ac16_6_every_view_is_audited_by_id_only_and_logs_hold_no_file_name(
    client: TestClient, engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = create_lead(client)
    document_id = uploaded(client, lead, SECRET_NAME)
    capsys.readouterr()
    client.get(file_url(lead, document_id), headers=staff_headers(client, "analyst1"))
    client.get(file_url(lead, document_id), headers=bearer(lead["access_token"]))
    sql = "SELECT actor, role, payload FROM audit_log WHERE event = 'DOCUMENT_VIEWED' ORDER BY seq"
    events = rows(engine, sql)
    assert [e[1] for e in events] == ["kyc-analyst", "prospect"]
    for _, _, payload in events:
        assert document_id in payload and SECRET_NAME not in payload and "ABCDE1234F" not in payload
    captured = capsys.readouterr()
    assert "ABCDE1234F" not in captured.out + captured.err


@pytest.mark.nfr("NFR-02")
@pytest.mark.ac("AC-16.6")
def test_ac16_6_viewing_never_changes_the_document_records(
    client: TestClient, engine: Engine
) -> None:
    lead = create_lead(client)
    document_id = uploaded(client, lead)
    before = rows(engine, "SELECT COUNT(*), MAX(seq) FROM documents")
    client.get(file_url(lead, document_id), headers=staff_headers(client))
    assert rows(engine, "SELECT COUNT(*), MAX(seq) FROM documents") == before


@pytest.mark.ac("AC-16.5")
def test_ac16_5_evidence_lists_replaced_versions_flagged_so_staff_can_open_them(
    client: TestClient,
) -> None:
    lead = create_lead(client)
    first = uploaded(client, lead, "pan_valid.pdf")
    second = uploaded(client, lead, "pan_v2.pdf")
    evidence = client.get(
        f"/api/v1/cases/{lead['case_id']}/evidence", headers=staff_headers(client)
    )
    assert evidence.status_code == 200
    by_id = {d["document_id"]: d for d in evidence.json()["documents"]}
    assert by_id[first]["superseded"] is True and by_id[second]["superseded"] is False
