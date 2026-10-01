"""E2-S1 / AC-02, AC-03: POST/GET /cases/{id}/documents with immediate classification."""

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from api_helpers import bearer, create_lead, lead_headers, staff_headers
from pipeline_helpers import (
    PDF_BYTES,
    rows,
    upload,
    upload_ok,
)


@pytest.mark.ac("AC-02")
def test_ac02_1_upload_returns_201_with_classification_feedback(client: TestClient) -> None:
    """E2-S1 AC1: 201 with document_id, version 1, class, status and confidence."""
    lead = create_lead(client)
    body = upload_ok(client, lead, "ID_PROOF", "pan_valid.pdf")
    assert body["checklist_item"] == "ID_PROOF" and body["version"] == 1
    assert (body["doc_class"], body["status"], body["reason_code"]) == ("PAN", "VERIFIED", None)
    assert body["confidence_bp"] == 9500 and body["rule_version"] == 1
    assert set(body) == {
        "document_id", "checklist_item", "version", "doc_class", "status",
        "reason_code", "confidence_bp", "rule_version",
    }  # fmt: skip


@pytest.mark.ac("AC-03")
@pytest.mark.parametrize(
    ("item", "filename", "doc_class"),
    [
        ("ID_PROOF", "pan_valid.pdf", "PAN"),
        ("ID_PROOF", "aadhaar_valid.jpg", "AADHAAR"),
        ("ID_PROOF", "passport_valid.png", "PASSPORT"),
        ("ADDRESS_PROOF", "utility-bill_valid.pdf", "UTILITY_BILL"),
        ("PHOTOGRAPH", "photograph_1.jpg", "PHOTOGRAPH"),
    ],
)
def test_ac03_1_upload_classifies_fixture_names(
    client: TestClient, item: str, filename: str, doc_class: str
) -> None:
    """AC-03.1/03.2 through the endpoint."""
    body = upload_ok(client, create_lead(client), item, filename)
    assert (body["doc_class"], body["status"]) == (doc_class, "VERIFIED")


@pytest.mark.ac("AC-03")
@pytest.mark.parametrize(
    ("product", "item", "filename", "doc_class"),
    [
        ("Current", "BUSINESS_PROOF", "gst-certificate_1.pdf", "GST_CERTIFICATE"),
        ("NRE", "OVERSEAS_ADDRESS_PROOF", "visa_1.pdf", "VISA"),
    ],
)
def test_ac03_2_current_and_nre_items_classify(
    client: TestClient, product: str, item: str, filename: str, doc_class: str
) -> None:
    body = upload_ok(client, create_lead(client, product=product), item, filename)
    assert (body["doc_class"], body["status"]) == (doc_class, "VERIFIED")


@pytest.mark.ac("AC-03")
def test_ac03_3_unrecognised_name_is_flagged(client: TestClient) -> None:
    body = upload_ok(client, create_lead(client), "ID_PROOF", "random_scan.pdf")
    assert (body["doc_class"], body["status"], body["reason_code"]) == (
        "UNRECOGNISED", "FLAGGED", "DOC_UNRECOGNISED",
    )  # fmt: skip
    assert body["confidence_bp"] == 0


@pytest.mark.ac("AC-03")
def test_ac03_4_class_not_accepted_by_item_is_flagged_mismatch(client: TestClient) -> None:
    """utility-bill uploaded as ID_PROOF -> FLAGGED DOC_CLASS_MISMATCH."""
    body = upload_ok(client, create_lead(client), "ID_PROOF", "utility-bill_1.pdf")
    assert (body["doc_class"], body["status"], body["reason_code"]) == (
        "UTILITY_BILL", "FLAGGED", "DOC_CLASS_MISMATCH",
    )  # fmt: skip


@pytest.mark.ac("AC-03")
def test_ac03_nre_id_proof_accepts_only_passport(client: TestClient) -> None:
    """NRE ID_PROOF accepts PASSPORT only, so a PAN is a mismatch."""
    lead = create_lead(client, product="NRE")
    assert upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")["reason_code"] == "DOC_CLASS_MISMATCH"
    assert upload_ok(client, lead, "ID_PROOF", "passport_1.pdf")["status"] == "VERIFIED"


@pytest.mark.ac("AC-03")
def test_ac03_6_every_classification_is_an_appended_row(client: TestClient, engine: Engine) -> None:
    """AC-03.6: each upload appends a classification row with rule_version and timestamp."""
    lead = create_lead(client)
    upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    upload_ok(client, lead, "ID_PROOF", "pan_2.pdf")
    found = rows(
        engine, "SELECT doc_class, status, rule_version, classified_at FROM classification_results"
    )
    assert len(found) == 2 and all(r[2] == 1 and r[3].endswith("Z") for r in found)


@pytest.mark.ac("AC-02")
def test_ac02_4_unsupported_type_is_415_and_nothing_is_stored(
    client: TestClient, engine: Engine, upload_dir: Path
) -> None:
    lead = create_lead(client)
    response = upload(client, lead, "ID_PROOF", "pan_1.txt", b"x", "text/plain")
    assert response.status_code == 415
    assert response.json()["error"] == {
        "code": "UNSUPPORTED_MEDIA_TYPE",
        "message": "Unsupported file type",
        "details": {"allowed": ["pdf", "jpg", "png"]},
    }
    assert rows(engine, "SELECT COUNT(*) FROM documents")[0][0] == 0
    assert not upload_dir.exists() or list(upload_dir.rglob("*.*")) == []


@pytest.mark.ac("AC-02")
def test_ac02_4_oversize_file_is_413_and_nothing_is_stored(
    client: TestClient, engine: Engine, upload_dir: Path
) -> None:
    lead = create_lead(client)
    response = upload(client, lead, "ID_PROOF", "pan_1.pdf", b"x" * (5 * 1024 * 1024 + 1))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert response.json()["error"]["details"] == {"max_bytes": 5242880}
    assert rows(engine, "SELECT COUNT(*) FROM documents")[0][0] == 0
    assert not upload_dir.exists() or list(upload_dir.rglob("*.*")) == []


@pytest.mark.ac("AC-02")
def test_ac02_4_a_file_of_exactly_five_mebibytes_is_accepted(client: TestClient) -> None:
    body = PDF_BYTES + b"x" * (5 * 1024 * 1024 - len(PDF_BYTES))
    response = upload(client, create_lead(client), "ID_PROOF", "pan_1.pdf", body)
    assert response.status_code == 201 and response.json()["status"] == "VERIFIED"


@pytest.mark.ac("AC-02")
def test_ac02_4_extension_and_content_type_must_agree(client: TestClient) -> None:
    response = upload(client, create_lead(client), "ID_PROOF", "pan_1.pdf", b"x", "image/png")
    assert response.status_code == 415


@pytest.mark.ac("AC-02")
def test_ac02_4_empty_file_is_422(client: TestClient) -> None:
    response = upload(client, create_lead(client), "ID_PROOF", "pan_1.pdf", b"")
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.ac("AC-02")
def test_ac02_4_unknown_checklist_item_is_422(client: TestClient) -> None:
    """E2-S1 AC3: BUSINESS_PROOF is not on the Savings checklist."""
    response = upload(client, create_lead(client), "BUSINESS_PROOF", "gst-certificate_1.pdf")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_CHECKLIST_ITEM"
    assert response.json()["error"]["details"] == {"checklist_item": "BUSINESS_PROOF"}


@pytest.mark.ac("AC-02")
def test_ac02_4_a_code_outside_the_enum_is_also_unknown_checklist_item(client: TestClient) -> None:
    response = upload(client, create_lead(client), "NOT_A_CODE", "pan_1.pdf")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_CHECKLIST_ITEM"


@pytest.mark.ac("AC-02")
def test_ac02_4_missing_form_fields_are_validation_errors(client: TestClient) -> None:
    lead = create_lead(client)
    url = f"/api/v1/cases/{lead['case_id']}/documents"
    no_item = client.post(
        url, files={"file": ("a.pdf", b"x", "application/pdf")}, headers=lead_headers(lead)
    )
    no_file = client.post(url, data={"checklist_item": "ID_PROOF"}, headers=lead_headers(lead))
    assert no_item.status_code == no_file.status_code == 422
    assert no_item.json()["error"]["code"] == no_file.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.ac("AC-02")
def test_ac02_5_stored_document_records_sha256_size_and_safe_name(
    client: TestClient, engine: Engine, upload_dir: Path
) -> None:
    """AC-02.5: checksum, size, sanitised name; file lands under the upload directory."""
    lead = create_lead(client)
    content = b"%PDF-1.4 synthetic content 123"
    response = upload(client, lead, "ID_PROOF", "pan_valid.pdf", content)
    (row,) = rows(
        engine,
        "SELECT sha256, size_bytes, display_name, storage_path, content_type, uploaded_by, version"
        " FROM documents",
    )
    assert row[0] == hashlib.sha256(content).hexdigest() and row[1] == len(content)
    assert row[2] == "pan_valid.pdf" and row[4] == "application/pdf"
    assert row[5] == f"prospect:{lead['case_id']}" and row[6] == 1
    assert row[3] == f"{lead['case_id']}/{response.json()['document_id']}.pdf"
    assert (upload_dir / row[3]).read_bytes() == content


@pytest.mark.ac("AC-02")
def test_ac02_5_traversal_filename_is_stored_safely_inside_the_upload_dir(
    client: TestClient, engine: Engine, upload_dir: Path, tmp_path: Path
) -> None:
    """E2-S1 AC5: ../../etc/passwd.pdf becomes passwd.pdf and nothing escapes."""
    lead = create_lead(client)
    response = upload(client, lead, "ID_PROOF", "../../etc/passwd.pdf")
    assert response.status_code == 201
    (row,) = rows(engine, "SELECT display_name, storage_path FROM documents")
    assert row[0] == "passwd.pdf" and ".." not in row[1]
    written = [p for p in tmp_path.rglob("*") if p.is_file() and p.suffix == ".pdf"]
    assert written and all(upload_dir.resolve() in p.resolve().parents for p in written)
    assert not (tmp_path / "etc").exists()


@pytest.mark.ac("AC-02")
def test_ac02_5_backslash_traversal_name_is_sanitised(client: TestClient, engine: Engine) -> None:
    upload(client, create_lead(client), "ID_PROOF", "..\\..\\boot\\pan_1.pdf")
    assert rows(engine, "SELECT display_name FROM documents")[0][0] == "pan_1.pdf"


@pytest.mark.ac("AC-02")
def test_ac02_5_response_never_contains_the_file_name_or_path(client: TestClient) -> None:
    """NFR-03: the stored file name is not returned by upload or list."""
    lead = create_lead(client)
    upload_body = upload(client, lead, "ID_PROOF", "pan_secretname.pdf").text
    listing = client.get(
        f"/api/v1/cases/{lead['case_id']}/documents", headers=lead_headers(lead)
    ).text
    assert "secretname" not in upload_body and "secretname" not in listing
    assert "storage_path" not in listing and "display_name" not in listing


@pytest.mark.ac("AC-02")
def test_ac02_upload_only_to_own_case_403(client: TestClient) -> None:
    """E2-S1 AC6: a prospect token bound to another case is refused."""
    mine = create_lead(client)
    other = create_lead(client, name="Test Person Other")
    response = client.post(
        f"/api/v1/cases/{mine['case_id']}/documents",
        data={"checklist_item": "ID_PROOF"},
        files={"file": ("pan_1.pdf", b"x", "application/pdf")},
        headers=bearer(other["access_token"]),
    )
    assert response.status_code == 403


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("user", ["analyst1", "officer1", "admin1"])
def test_nfr04_staff_cannot_upload(client: TestClient, user: str) -> None:
    """E2-S1 AC6 / contract: a kyc-analyst (and every staff role) cannot upload."""
    lead = create_lead(client)
    response = client.post(
        f"/api/v1/cases/{lead['case_id']}/documents",
        data={"checklist_item": "ID_PROOF"},
        files={"file": ("pan_1.pdf", b"x", "application/pdf")},
        headers=staff_headers(client, user),
    )
    assert response.status_code == 403 and response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.nfr("NFR-04")
def test_nfr04_upload_without_a_token_is_401(client: TestClient) -> None:
    lead = create_lead(client)
    response = client.post(
        f"/api/v1/cases/{lead['case_id']}/documents",
        data={"checklist_item": "ID_PROOF"},
        files={"file": ("pan_1.pdf", b"x", "application/pdf")},
    )
    assert response.status_code == 401


@pytest.mark.ac("AC-02")
def test_ac02_upload_to_a_case_that_does_not_exist_is_404(client: TestClient) -> None:
    lead = create_lead(client)
    forged = {**lead, "case_id": "00000000-0000-4000-8000-00000000dead"}
    assert upload(client, forged, "ID_PROOF", "pan_1.pdf").status_code == 403
    response = client.get(
        "/api/v1/cases/00000000-0000-4000-8000-00000000dead/documents",
        headers=staff_headers(client),
    )
    assert response.status_code == 404


@pytest.mark.ac("AC-02")
def test_ac02_4_listing_returns_current_version_per_item_with_classification(
    client: TestClient,
) -> None:
    """E2-S1 AC4: GET lists the current version with status, doc_class and reason code."""
    lead = create_lead(client)
    upload_ok(client, lead, "ID_PROOF", "utility-bill_1.pdf")
    upload_ok(client, lead, "PHOTOGRAPH", "photograph_1.jpg")
    response = client.get(f"/api/v1/cases/{lead['case_id']}/documents", headers=lead_headers(lead))
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == lead["case_id"]
    by_item = {d["checklist_item"]: d for d in body["documents"]}
    assert by_item["ID_PROOF"]["status"] == "FLAGGED"
    assert by_item["ID_PROOF"]["reason_code"] == "DOC_CLASS_MISMATCH"
    assert by_item["PHOTOGRAPH"]["doc_class"] == "PHOTOGRAPH"
    assert set(by_item["PHOTOGRAPH"]) == {
        "document_id", "checklist_item", "version", "doc_class", "status", "reason_code",
        "confidence_bp", "rule_version", "superseded", "size_bytes", "sha256", "uploaded_at",
    }  # fmt: skip


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("user", ["analyst1", "officer1", "admin1"])
def test_ac02_staff_can_list_documents_of_any_case(client: TestClient, user: str) -> None:
    lead = create_lead(client)
    upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    response = client.get(
        f"/api/v1/cases/{lead['case_id']}/documents", headers=staff_headers(client, user)
    )
    assert response.status_code == 200 and len(response.json()["documents"]) == 1


@pytest.mark.ac("AC-02")
def test_ac02_another_prospect_cannot_list_documents(client: TestClient) -> None:
    lead = create_lead(client)
    other = create_lead(client, name="Test Person Other")
    response = client.get(f"/api/v1/cases/{lead['case_id']}/documents", headers=lead_headers(other))
    assert response.status_code == 403


@pytest.mark.ac("AC-09")
def test_ac09_3b_reupload_creates_version_n_plus_1_and_keeps_the_earlier(
    client: TestClient, engine: Engine
) -> None:
    """AC-09.3b: version 2 is current, version 1 kept and listed as superseded for staff."""
    lead = create_lead(client)
    first = upload_ok(client, lead, "ID_PROOF", "junk.pdf")
    second = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    assert (first["version"], second["version"]) == (1, 2)
    assert first["document_id"] != second["document_id"]
    url = f"/api/v1/cases/{lead['case_id']}/documents"
    current = client.get(url, headers=lead_headers(lead)).json()["documents"]
    assert [(d["version"], d["superseded"]) for d in current] == [(2, False)]
    staff = client.get(url + "?include_superseded=true", headers=staff_headers(client))
    assert [(d["version"], d["superseded"]) for d in staff.json()["documents"]] == [
        (1, True),
        (2, False),
    ]
    assert rows(engine, "SELECT COUNT(*) FROM documents")[0][0] == 2


@pytest.mark.ac("AC-09")
def test_ac09_3b_prospect_cannot_request_superseded_versions(client: TestClient) -> None:
    lead = create_lead(client)
    response = client.get(
        f"/api/v1/cases/{lead['case_id']}/documents?include_superseded=true",
        headers=lead_headers(lead),
    )
    assert response.status_code == 403


@pytest.mark.ac("AC-09")
def test_ac09_3c_reupload_leaves_state_and_history_unchanged(
    client: TestClient, engine: Engine
) -> None:
    """AC-09.3c: no state change and no state-history row from uploads."""
    lead = create_lead(client)
    before = rows(engine, "SELECT COUNT(*) FROM state_history")[0][0]
    upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    upload_ok(client, lead, "ID_PROOF", "pan_2.pdf")
    assert rows(engine, "SELECT COUNT(*) FROM state_history")[0][0] == before
    detail = client.get(f"/api/v1/cases/{lead['case_id']}", headers=lead_headers(lead)).json()
    assert detail["state"] == "INITIATED"


@pytest.mark.ac("AC-09")
@pytest.mark.parametrize("state", ["APPROVED", "REJECTED"])
def test_ac09_3c_upload_on_a_terminal_case_is_409_case_locked(
    client: TestClient, engine: Engine, state: str
) -> None:
    lead = create_lead(client)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET state=:s WHERE case_id=:c"), {"s": state, "c": lead["case_id"]}
        )
    response = upload(client, lead, "ID_PROOF", "pan_1.pdf")
    assert response.status_code == 409 and response.json()["error"]["code"] == "CASE_LOCKED"
    assert rows(engine, "SELECT COUNT(*) FROM documents")[0][0] == 0


@pytest.mark.ac("AC-09")
@pytest.mark.parametrize("state", ["DOCS_SUBMITTED", "MANUAL_REVIEW"])
def test_ac09_3b_upload_is_allowed_while_submitted_or_in_manual_review(
    client: TestClient, engine: Engine, state: str
) -> None:
    lead = create_lead(client)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET state=:s WHERE case_id=:c"), {"s": state, "c": lead["case_id"]}
        )
    assert upload(client, lead, "ID_PROOF", "pan_1.pdf").status_code == 201


@pytest.mark.ac("AC-09")
@pytest.mark.parametrize("state", ["SCREENED", "CLASSIFIED"])
def test_ac09_dd8_upload_is_frozen_in_the_transient_pipeline_states(
    client: TestClient, engine: Engine, state: str
) -> None:
    """DD-8: SCREENED and CLASSIFIED are frozen for uploads (409 INVALID_STATE)."""
    lead = create_lead(client)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET state=:s WHERE case_id=:c"), {"s": state, "c": lead["case_id"]}
        )
    response = upload(client, lead, "ID_PROOF", "pan_1.pdf")
    assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_STATE"


@pytest.mark.nfr("NFR-02")
def test_nfr02_documents_and_classifications_reject_update_and_delete(
    client: TestClient, engine: Engine
) -> None:
    """NFR-02: triggers make the document tables append-only."""
    lead = create_lead(client)
    upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    for table in ("documents", "classification_results"):
        for statement in (f"UPDATE {table} SET seq = seq", f"DELETE FROM {table}"):
            with pytest.raises(IntegrityError), engine.begin() as conn:
                conn.execute(text(statement))


@pytest.mark.nfr("NFR-03")
def test_nfr03_document_uploads_never_log_file_names_or_content(
    client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    lead = create_lead(client)
    capsys.readouterr()
    upload(client, lead, "ID_PROOF", "pan_ABCDE1234F_secret.pdf", PDF_BYTES + b"TOPSECRETBYTES")
    logged = capsys.readouterr().out
    assert "ABCDE1234F" not in logged and "secret" not in logged and "TOPSECRET" not in logged
    assert "document uploaded" in logged and lead["case_id"] in logged
