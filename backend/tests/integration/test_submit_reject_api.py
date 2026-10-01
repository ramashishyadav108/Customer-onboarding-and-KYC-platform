"""E2-S2 / E2-S4: submit gating (AC-02) and document rejection / re-upload (AC-09)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import create_lead, lead_headers, staff_headers
from pipeline_helpers import (
    PROFILE_A,
    get_case,
    history,
    notifications,
    put_profile,
    ready_case,
    reject,
    rows,
    state_of,
    submit,
    upload_all,
    upload_ok,
)


@pytest.mark.ac("AC-02")
def test_ac02_6_submit_with_everything_present_moves_to_docs_submitted(
    client: TestClient, engine: Engine
) -> None:
    """E2-S2 AC1: 200 DOCS_SUBMITTED, missing_items empty, one history row."""
    lead = ready_case(client)
    response = submit(client, lead)
    assert response.status_code == 200
    assert response.json() == {
        "case_id": lead["case_id"],
        "state": "DOCS_SUBMITTED",
        "missing_items": [],
    }
    assert state_of(client, lead) == "DOCS_SUBMITTED"
    assert history(engine, lead["case_id"]) == ["INITIATED", "DOCS_SUBMITTED"]


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize("product", ["Savings", "Current", "NRE"])
def test_ac02_6_each_product_submits_with_its_own_mandatory_items(
    client: TestClient, product: str
) -> None:
    lead = ready_case(client, product=product)
    assert submit(client, lead).status_code == 200


@pytest.mark.ac("AC-02")
def test_ac02_7_missing_mandatory_items_are_listed_and_state_stays_initiated(
    client: TestClient, engine: Engine
) -> None:
    """E2-S2 AC2: 422 MISSING_DOCUMENTS naming each absent item."""
    lead = create_lead(client)
    put_profile(client, lead, PROFILE_A)
    upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    response = submit(client, lead)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "MISSING_DOCUMENTS"
    assert error["details"] == {"missing_items": ["ADDRESS_PROOF", "PHOTOGRAPH"]}
    assert state_of(client, lead) == "INITIATED"
    assert history(engine, lead["case_id"]) == ["INITIATED"]


@pytest.mark.ac("AC-02")
def test_ac02_7_current_product_requires_the_business_proof(client: TestClient) -> None:
    lead = ready_case(client, product="Current")
    other = create_lead(client, product="Current")
    put_profile(client, other, PROFILE_A)
    upload_all(client, other, "Current", {})
    assert submit(client, lead).status_code == 200
    partial = create_lead(client, product="Current")
    put_profile(client, partial, PROFILE_A)
    for item, name in [("ID_PROOF", "pan_1.pdf"), ("ADDRESS_PROOF", "utility-bill_1.pdf")]:
        upload_ok(client, partial, item, name)
    upload_ok(client, partial, "PHOTOGRAPH", "photograph_1.jpg")
    response = submit(client, partial)
    assert response.json()["error"]["details"]["missing_items"] == ["BUSINESS_PROOF"]


@pytest.mark.ac("AC-02")
def test_ac02_7_nothing_uploaded_lists_every_mandatory_item(client: TestClient) -> None:
    lead = create_lead(client, product="NRE")
    put_profile(client, lead, PROFILE_A)
    response = submit(client, lead)
    assert response.json()["error"]["details"]["missing_items"] == [
        "ID_PROOF",
        "ADDRESS_PROOF",
        "PHOTOGRAPH",
        "OVERSEAS_ADDRESS_PROOF",
    ]


@pytest.mark.ac("AC-02")
def test_ac02_8_incomplete_profile_is_422_missing_profile(
    client: TestClient, engine: Engine
) -> None:
    """E2-S2 AC3: documents complete but no profile -> MISSING_PROFILE."""
    lead = create_lead(client)
    upload_all(client, lead, "Savings")
    response = submit(client, lead)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "MISSING_PROFILE"
    assert set(error["details"]["missing_fields"]) >= {"date_of_birth", "annual_income"}
    assert state_of(client, lead) == "INITIATED"
    assert history(engine, lead["case_id"]) == ["INITIATED"]


@pytest.mark.ac("AC-02")
def test_ac02_7_8_documents_are_checked_before_the_profile(client: TestClient) -> None:
    """Both gaps: the contract lists MISSING_DOCUMENTS first."""
    lead = create_lead(client)
    assert submit(client, lead).json()["error"]["code"] == "MISSING_DOCUMENTS"


@pytest.mark.ac("AC-02")
def test_ac02_9_duplicate_submit_is_idempotent_without_a_second_history_row(
    client: TestClient, engine: Engine
) -> None:
    """E2-S2 AC4: second submit returns 200 and adds no history row."""
    lead = ready_case(client)
    assert submit(client, lead).status_code == 200
    again = submit(client, lead)
    assert again.status_code == 200 and again.json()["state"] == "DOCS_SUBMITTED"
    assert history(engine, lead["case_id"]) == ["INITIATED", "DOCS_SUBMITTED"]
    assert (
        rows(engine, "SELECT COUNT(*) FROM audit_log WHERE event='DOCUMENTS_SUBMITTED'")[0][0] == 1
    )


@pytest.mark.ac("AC-02")
@pytest.mark.parametrize(
    "step_names", [["screen"], ["screen", "classify"], ["screen", "classify", "decide"]]
)
def test_ac02_9_submit_in_any_later_state_is_409_invalid_state(
    client: TestClient, step_names: list[str]
) -> None:
    from pipeline_helpers import step

    lead = ready_case(client)
    submit(client, lead)
    for name in step_names:
        assert step(client, lead, name).status_code == 200
    response = submit(client, lead)
    assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_STATE"


@pytest.mark.ac("AC-02")
def test_ac02_6_submit_appends_a_documents_submitted_audit_entry_with_ids(
    client: TestClient, engine: Engine
) -> None:
    """E2-S2 AC5: DOCUMENTS_SUBMITTED audit lists the document ids, no file names."""
    lead = ready_case(client)
    submit(client, lead)
    (row,) = rows(
        engine, "SELECT payload, actor, role FROM audit_log WHERE event='DOCUMENTS_SUBMITTED'"
    )
    import json

    payload = json.loads(row[0])
    assert len(payload["document_ids"]) == 3 and row[2] == "prospect"
    assert "pan_valid" not in row[0]


@pytest.mark.ac("AC-02")
def test_ac02_6_get_case_has_empty_missing_items_after_submit(client: TestClient) -> None:
    lead = ready_case(client)
    submit(client, lead)
    detail = get_case(client, lead)
    assert detail["missing_items"] == [] and detail["action_required"] == []
    assert all(i["status"] == "VERIFIED" for i in detail["checklist_items"])


@pytest.mark.nfr("NFR-04")
def test_nfr04_only_the_owner_can_submit(client: TestClient) -> None:
    lead = ready_case(client)
    other = create_lead(client, name="Test Person Other")
    url = f"/api/v1/cases/{lead['case_id']}/submit"
    assert client.post(url, headers=lead_headers(other)).status_code == 403
    assert client.post(url).status_code == 401
    for user in ("analyst1", "officer1", "admin1"):
        assert client.post(url, headers=staff_headers(client, user)).status_code == 403


@pytest.mark.ac("AC-02")
def test_ac02_case_detail_reflects_uploaded_documents_per_item(client: TestClient) -> None:
    """Case detail checklist_items statuses come from real documents."""
    lead = create_lead(client)
    upload_ok(client, lead, "ID_PROOF", "utility-bill_1.pdf")
    upload_ok(client, lead, "PHOTOGRAPH", "photograph_1.jpg")
    detail = get_case(client, lead)
    items = {i["item_code"]: i for i in detail["checklist_items"]}
    assert items["ID_PROOF"]["status"] == "FLAGGED" and items["ID_PROOF"]["doc_version"] == 1
    assert items["ID_PROOF"]["reason_code"] == "DOC_CLASS_MISMATCH"
    assert items["ID_PROOF"]["doc_class"] == "UTILITY_BILL" and items["ID_PROOF"]["document_id"]
    assert items["PHOTOGRAPH"]["status"] == "VERIFIED"
    assert (
        items["ADDRESS_PROOF"]["status"] == "MISSING"
        and items["ADDRESS_PROOF"]["document_id"] is None
    )
    assert detail["missing_items"] == ["ADDRESS_PROOF"]
    actions = {a["item_code"]: a for a in detail["action_required"]}
    assert actions["ID_PROOF"] == {
        "item_code": "ID_PROOF", "status": "FLAGGED", "reason_code": "DOC_CLASS_MISMATCH",
    }  # fmt: skip
    assert (
        actions["ADDRESS_PROOF"]["status"] == "MISSING"
        and actions["ADDRESS_PROOF"]["reason_code"] is None
    )


@pytest.mark.ac("AC-09")
def test_ac09_3a_analyst_can_reject_a_document_with_a_reason(
    client: TestClient, engine: Engine
) -> None:
    """E2-S4 AC1: 200 REJECTED, rejection row and DOCUMENT_REJECTED audit appended."""
    lead = create_lead(client)
    doc = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    response = reject(client, lead, doc["document_id"], "DOC_EXPIRED", comment="expired in 2020")
    assert response.status_code == 200
    assert response.json() == {
        "document_id": doc["document_id"],
        "status": "REJECTED",
        "reason_code": "DOC_EXPIRED",
    }
    (row,) = rows(engine, "SELECT reason_code, comment, actor FROM document_rejections")
    assert tuple(row) == ("DOC_EXPIRED", "expired in 2020", "analyst1")
    audit = rows(engine, "SELECT payload, role FROM audit_log WHERE event='DOCUMENT_REJECTED'")
    assert len(audit) == 1 and audit[0][1] == "kyc-analyst" and "expired in 2020" not in audit[0][0]


@pytest.mark.ac("AC-09")
@pytest.mark.parametrize(
    "reason", ["DOC_ILLEGIBLE", "DOC_EXPIRED", "DOC_NAME_MISMATCH", "DOC_WRONG_TYPE", "DOC_OTHER"]
)
def test_ac09_3a_every_reason_code_in_the_controlled_list_is_accepted(
    client: TestClient, reason: str
) -> None:
    lead = create_lead(client)
    doc = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    assert reject(client, lead, doc["document_id"], reason).json()["reason_code"] == reason


@pytest.mark.ac("AC-09")
@pytest.mark.parametrize("user", ["officer1", "admin1"])
def test_ac09_3a_other_staff_roles_cannot_reject(client: TestClient, user: str) -> None:
    lead = create_lead(client)
    doc = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    assert reject(client, lead, doc["document_id"], user=user).status_code == 403


@pytest.mark.ac("AC-09")
def test_ac09_3a_prospect_and_anonymous_cannot_reject(client: TestClient) -> None:
    lead = create_lead(client)
    doc = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    url = f"/api/v1/cases/{lead['case_id']}/documents/{doc['document_id']}/reject"
    assert (
        client.post(url, json={"reason_code": "DOC_OTHER"}, headers=lead_headers(lead)).status_code
        == 403
    )
    assert client.post(url, json={"reason_code": "DOC_OTHER"}).status_code == 401


@pytest.mark.ac("AC-09")
def test_ac09_3a_unknown_reason_code_is_422_unknown_reason_code(client: TestClient) -> None:
    lead = create_lead(client)
    doc = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    response = reject(client, lead, doc["document_id"], "BECAUSE")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "UNKNOWN_REASON_CODE" and "DOC_ILLEGIBLE" in error["details"]["allowed"]


@pytest.mark.ac("AC-09")
def test_ac09_3a_missing_reason_or_overlong_comment_is_a_validation_error(
    client: TestClient,
) -> None:
    lead = create_lead(client)
    doc = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    url = f"/api/v1/cases/{lead['case_id']}/documents/{doc['document_id']}/reject"
    headers = staff_headers(client)
    assert client.post(url, json={}, headers=headers).status_code == 422
    too_long = client.post(
        url, json={"reason_code": "DOC_OTHER", "comment": "x" * 501}, headers=headers
    )
    assert too_long.status_code == 422 and too_long.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.ac("AC-09")
def test_ac09_3a_unknown_document_and_document_of_another_case_are_404(client: TestClient) -> None:
    lead = create_lead(client)
    other = create_lead(client, name="Test Person Other")
    doc = upload_ok(client, other, "ID_PROOF", "pan_1.pdf")
    assert reject(client, lead, "00000000-0000-4000-8000-000000000abc").status_code == 404
    assert reject(client, lead, doc["document_id"]).status_code == 404


@pytest.mark.ac("AC-09")
def test_ac09_3c_reject_on_a_terminal_case_is_409_case_locked(
    client: TestClient, engine: Engine
) -> None:
    from sqlalchemy import text

    lead = create_lead(client)
    doc = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET state='APPROVED' WHERE case_id=:c"), {"c": lead["case_id"]}
        )
    response = reject(client, lead, doc["document_id"])
    assert response.status_code == 409 and response.json()["error"]["code"] == "CASE_LOCKED"


@pytest.mark.ac("AC-09")
def test_ac09_3a_repeat_reject_is_idempotent_and_adds_no_second_row(
    client: TestClient, engine: Engine
) -> None:
    lead = create_lead(client)
    doc = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    first = reject(client, lead, doc["document_id"], "DOC_EXPIRED")
    second = reject(client, lead, doc["document_id"], "DOC_OTHER")
    assert first.status_code == second.status_code == 200
    assert second.json()["reason_code"] == "DOC_EXPIRED"
    assert rows(engine, "SELECT COUNT(*) FROM document_rejections")[0][0] == 1


@pytest.mark.ac("AC-09")
def test_ac09_3b_a_superseded_version_cannot_be_rejected(client: TestClient) -> None:
    lead = create_lead(client)
    old = upload_ok(client, lead, "ID_PROOF", "junk.pdf")
    upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    response = reject(client, lead, old["document_id"])
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.ac("AC-09")
def test_ac09_3e_rejected_item_shows_in_action_required_with_reason_code(
    client: TestClient,
) -> None:
    """AC-09.3e: REJECTED items are listed with the analyst's reason code."""
    lead = ready_case(client)
    doc = next(i for i in get_case(client, lead)["checklist_items"] if i["item_code"] == "ID_PROOF")
    reject(client, lead, doc["document_id"], "DOC_NAME_MISMATCH")
    detail = get_case(client, lead)
    item = next(i for i in detail["checklist_items"] if i["item_code"] == "ID_PROOF")
    assert (item["status"], item["reason_code"]) == ("REJECTED", "DOC_NAME_MISMATCH")
    assert detail["action_required"] == [
        {"item_code": "ID_PROOF", "status": "REJECTED", "reason_code": "DOC_NAME_MISMATCH"}
    ]


@pytest.mark.ac("AC-09")
def test_ac09_3d_replacement_upload_clears_the_action_required_entry(client: TestClient) -> None:
    """AC-09.3d / E2-S4 AC4: a VERIFIED replacement for a REJECTED document clears it."""
    lead = ready_case(client)
    doc = next(i for i in get_case(client, lead)["checklist_items"] if i["item_code"] == "ID_PROOF")
    reject(client, lead, doc["document_id"])
    assert upload_ok(client, lead, "ID_PROOF", "aadhaar_2.jpg")["status"] == "VERIFIED"
    detail = get_case(client, lead)
    assert detail["action_required"] == [] and detail["missing_items"] == []
    item = next(i for i in detail["checklist_items"] if i["item_code"] == "ID_PROOF")
    assert (item["doc_version"], item["doc_class"]) == (2, "AADHAAR")


@pytest.mark.ac("AC-09")
def test_ac09_3d_a_flagged_replacement_keeps_the_flag(client: TestClient) -> None:
    lead = create_lead(client)
    upload_ok(client, lead, "ID_PROOF", "junk.pdf")
    upload_ok(client, lead, "ID_PROOF", "also-junk.pdf")
    item = next(
        i for i in get_case(client, lead)["checklist_items"] if i["item_code"] == "ID_PROOF"
    )
    assert (item["status"], item["doc_version"]) == ("FLAGGED", 2)


@pytest.mark.ac("AC-02")
def test_ac02_7_a_rejected_mandatory_document_blocks_submission_until_replaced(
    client: TestClient,
) -> None:
    """DD-9: REJECTED blocks submit; a replacement unblocks it."""
    lead = ready_case(client)
    doc = next(
        i for i in get_case(client, lead)["checklist_items"] if i["item_code"] == "PHOTOGRAPH"
    )
    reject(client, lead, doc["document_id"], "DOC_ILLEGIBLE")
    blocked = submit(client, lead)
    assert blocked.status_code == 422
    assert blocked.json()["error"]["details"] == {"missing_items": ["PHOTOGRAPH"]}
    upload_ok(client, lead, "PHOTOGRAPH", "photograph_2.jpg")
    assert submit(client, lead).status_code == 200


@pytest.mark.ac("AC-09")
def test_ac09_3c_rejection_does_not_change_state_or_history(
    client: TestClient, engine: Engine
) -> None:
    lead = ready_case(client)
    doc = next(i for i in get_case(client, lead)["checklist_items"] if i["item_code"] == "ID_PROOF")
    before = history(engine, lead["case_id"])
    reject(client, lead, doc["document_id"])
    assert history(engine, lead["case_id"]) == before
    assert state_of(client, lead) == "INITIATED"


@pytest.mark.ac("AC-09")
def test_ac09_2_rejection_records_a_doc_rejected_notification_with_item_and_reason(
    client: TestClient,
) -> None:
    """AC-09.2 / E4-S4 AC2: DOC_REJECTED carries item_code and reason_code."""
    lead = create_lead(client)
    doc = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    reject(client, lead, doc["document_id"], "DOC_WRONG_TYPE")
    (rejected,) = [n for n in notifications(client, lead) if n["event"] == "DOC_REJECTED"]
    assert rejected["details"] == {"item_code": "ID_PROOF", "reason_code": "DOC_WRONG_TYPE"}
    assert "ID_PROOF" in rejected["text"] and "DOC_WRONG_TYPE" in rejected["text"]


@pytest.mark.ac("AC-09")
def test_ac09_2_each_rejection_adds_its_own_notification(client: TestClient) -> None:
    lead = create_lead(client)
    first = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    second = upload_ok(client, lead, "PHOTOGRAPH", "photograph_1.jpg")
    reject(client, lead, first["document_id"])
    reject(client, lead, second["document_id"])
    assert [n["event"] for n in notifications(client, lead)].count("DOC_REJECTED") == 2
