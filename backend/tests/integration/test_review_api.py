"""AC-08 / AC-07 / NFR-02 / NFR-08: review queue, evidence, override, reclassify, account."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import bearer, staff_headers
from helpers import FakeClock
from pipeline_helpers import rows, state_of
from review_helpers import (
    case_in,
    case_in_review,
    officer,
    override,
    reclassify,
)

QUEUE = "/api/v1/review-queue"
CODES_APPROVE = ["FALSE_POSITIVE_CLEARED", "RISK_ACCEPTED", "DOCS_CONFIRMED"]
CODES_REJECT = ["CONFIRMED_WATCHLIST_MATCH", "DOCS_INSUFFICIENT", "RISK_TOO_HIGH", "POLICY_OTHER"]


def code(response: Any) -> str:
    return str(response.json()["error"]["code"])


@pytest.mark.ac("AC-08")
def test_ac08_1_queue_lists_manual_review_cases_oldest_first(
    client: TestClient, clock: FakeClock
) -> None:
    """AC-08.1: oldest first with reason code, product and age_minutes."""
    first = case_in_review(client, "AML")
    clock.advance(600)
    second = case_in_review(client, "MEDIUM")
    clock.advance(1200)
    body = client.get(QUEUE, headers=officer(client)).json()
    assert [i["case_id"] for i in body["items"]] == [first["case_id"], second["case_id"]]
    assert body["total"] == 2
    assert body["items"][0]["reason_code"] == "AML_HIT" and body["items"][0]["product"] == "Savings"
    assert body["items"][1]["reason_code"] == "RISK_MEDIUM"
    assert body["items"][0]["age_minutes"] == 30 and body["items"][1]["age_minutes"] == 20


@pytest.mark.ac("AC-08")
def test_ac08_1_queue_excludes_other_states_and_resolved_cases(client: TestClient) -> None:
    """AC-08.1: only MANUAL_REVIEW cases; a resolved case leaves the queue."""
    case_in(client, "CLEAN")
    lead = case_in_review(client, "HIGH")
    assert client.get(QUEUE, headers=officer(client)).json()["total"] == 1
    assert override(client, lead, "REJECT", "RISK_TOO_HIGH").status_code == 200
    assert client.get(QUEUE, headers=officer(client)).json() == {"items": [], "total": 0}


@pytest.mark.ac("AC-08")
def test_ac08_1_queue_filters_by_product_and_reason(client: TestClient) -> None:
    """AC-08.1: optional product and reason_code filters; invalid values are 422."""
    case_in_review(client, "AML")
    case_in_review(client, "MEDIUM")
    head = officer(client)
    by_product = client.get(QUEUE, params={"product": "Current"}, headers=head).json()
    assert [i["reason_code"] for i in by_product["items"]] == ["RISK_MEDIUM"]
    by_reason = client.get(QUEUE, params={"reason_code": "AML_HIT"}, headers=head).json()
    assert [i["product"] for i in by_reason["items"]] == ["Savings"]
    assert client.get(QUEUE, params={"product": "Loans"}, headers=head).status_code == 422
    assert client.get(QUEUE, params={"reason_code": "NOPE"}, headers=head).status_code == 422


@pytest.mark.ac("AC-08")
@pytest.mark.nfr("NFR-03")
def test_ac08_1_queue_payload_has_no_pii(client: TestClient) -> None:
    """NFR-03: the queue exposes ids, product, reason and age only."""
    case_in_review(client, "AML")
    item = client.get(QUEUE, headers=officer(client)).json()["items"][0]
    assert set(item) == {"case_id", "product", "reason_code", "age_minutes", "entered_review_at"}


@pytest.mark.ac("AC-08")
def test_ac08_evidence_shows_hits_risk_documents_decision_and_history(
    client: TestClient,
) -> None:
    """E4-S3 / DD-7: evidence assembles hits, breakdown, documents, decision and history."""
    lead = case_in_review(client, "AML")
    response = client.get(f"/api/v1/cases/{lead['case_id']}/evidence", headers=officer(client))
    body = response.json()
    assert response.status_code == 200
    assert body["state"] == "MANUAL_REVIEW" and body["review_reason_code"] == "AML_HIT"
    assert body["screening"]["hits"][0]["reason_code"] == "AML_HIT"
    assert (
        body["risk_assessment"]["band"] == "LOW" and len(body["risk_assessment"]["breakdown"]) == 4
    )
    assert len(body["documents"]) == 3 and body["decision"]["outcome"] == "MANUAL_REVIEW"
    assert body["override"] is None and body["account_number_masked"] is None
    assert [h["to_state"] for h in body["history"]] == [
        "INITIATED", "DOCS_SUBMITTED", "SCREENED", "CLASSIFIED", "MANUAL_REVIEW",
    ]  # fmt: skip


@pytest.mark.ac("AC-08")
def test_ac08_evidence_after_override_includes_override_and_masked_account(
    client: TestClient,
) -> None:
    """Evidence of a resolved case carries the override row and the masked account."""
    lead = case_in_review(client, "MEDIUM")
    override(client, lead, "APPROVE", "RISK_ACCEPTED", comment="checked")
    body = client.get(f"/api/v1/cases/{lead['case_id']}/evidence", headers=officer(client)).json()
    assert body["state"] == "APPROVED" and body["override"]["decision"] == "APPROVE"
    assert body["override"]["previous_state"] == "MANUAL_REVIEW"
    assert body["account_number_masked"].startswith("CUR") and "*" in body["account_number_masked"]
    assert body["review_reason_code"] == "RISK_MEDIUM"  # the routing reason stays on record


@pytest.mark.ac("AC-08")
def test_ac08_evidence_for_unknown_case_is_404_and_for_clean_case_has_no_review_code(
    client: TestClient,
) -> None:
    """Unknown case -> 404; an auto-approved case has a decision but no review reason."""
    head = officer(client)
    assert client.get("/api/v1/cases/nope/evidence", headers=head).status_code == 404
    lead = case_in(client, "CLEAN")
    body = client.get(f"/api/v1/cases/{lead['case_id']}/evidence", headers=head).json()
    assert body["decision"]["reason_code"] == "AUTO_APPROVED" and body["review_reason_code"] is None


@pytest.mark.ac("AC-08")
@pytest.mark.parametrize(
    ("decision", "reason", "state"),
    [(d, r, s) for d, rs, s in (("APPROVE", CODES_APPROVE, "APPROVED"),
                                ("REJECT", CODES_REJECT, "REJECTED")) for r in rs],
)  # fmt: skip
def test_ac08_2_override_with_every_valid_reason_changes_state(
    client: TestClient, decision: str, reason: str, state: str
) -> None:
    """AC-08.2: every controlled reason code works for its own direction."""
    lead = case_in_review(client, "AML")
    response = override(client, lead, decision, reason, comment="reviewed")
    body = response.json()
    assert response.status_code == 200 and body["state"] == state
    assert body["override"]["reason_code"] == reason and body["override"]["comment"] == "reviewed"
    assert state_of(client, lead) == state


@pytest.mark.ac("AC-08")
def test_ac08_2_missing_reason_is_422_and_changes_nothing(
    client: TestClient, engine: Engine
) -> None:
    """AC-08.2: no reason_code -> 422 VALIDATION_ERROR, state and tables untouched."""
    lead = case_in_review(client, "AML")
    response = override(client, lead, "APPROVE", None)
    assert response.status_code == 422 and code(response) == "VALIDATION_ERROR"
    assert state_of(client, lead) == "MANUAL_REVIEW"
    assert rows(engine, "SELECT COUNT(*) FROM overrides")[0][0] == 0


@pytest.mark.ac("AC-08")
@pytest.mark.parametrize(
    ("decision", "reason"),
    [("APPROVE", "NOT_A_CODE"), ("APPROVE", "RISK_TOO_HIGH"), ("REJECT", "RISK_ACCEPTED")],
)
def test_ac08_2_unknown_or_wrong_direction_reason_is_422(
    client: TestClient, engine: Engine, decision: str, reason: str
) -> None:
    """AC-08.2 / DD-3: unknown or wrong-direction reason -> 422 UNKNOWN_REASON_CODE."""
    lead = case_in_review(client, "AML")
    response = override(client, lead, decision, reason)
    body = response.json()["error"]
    assert response.status_code == 422 and body["code"] == "UNKNOWN_REASON_CODE"
    assert body["details"]["allowed"] == (CODES_APPROVE if decision == "APPROVE" else CODES_REJECT)
    assert state_of(client, lead) == "MANUAL_REVIEW"
    assert rows(engine, "SELECT COUNT(*) FROM overrides")[0][0] == 0


@pytest.mark.ac("AC-08")
def test_ac08_2_unknown_decision_and_long_comment_are_422(client: TestClient) -> None:
    """AC-08.2: decision must be APPROVE or REJECT; comment at most 500 characters."""
    lead = case_in_review(client, "AML")
    assert override(client, lead, "MAYBE", "RISK_ACCEPTED").status_code == 422
    too_long = override(client, lead, "APPROVE", "RISK_ACCEPTED", comment="x" * 501)
    assert too_long.status_code == 422
    assert override(client, lead, "APPROVE", "RISK_ACCEPTED", comment="x" * 500).status_code == 200


@pytest.mark.ac("AC-08")
@pytest.mark.parametrize("user", ["analyst1", "admin1", "prospect1"])
def test_ac08_3_other_roles_get_403_on_override_and_queue(
    client: TestClient, engine: Engine, user: str
) -> None:
    """AC-08.3: analyst, admin and prospect cannot override or read the queue."""
    lead = case_in_review(client, "AML")
    assert override(client, lead, user=user).status_code == 403
    assert client.get(QUEUE, headers=staff_headers(client, user)).status_code == 403
    assert rows(engine, "SELECT COUNT(*) FROM overrides")[0][0] == 0
    assert state_of(client, lead) == "MANUAL_REVIEW"


@pytest.mark.ac("AC-08")
def test_ac08_3_case_owner_token_cannot_override(client: TestClient) -> None:
    """AC-08.3: the owning prospect token is a prospect: 403."""
    lead = case_in_review(client, "AML")
    response = client.post(
        f"/api/v1/cases/{lead['case_id']}/override",
        json={"decision": "APPROVE", "reason_code": "RISK_ACCEPTED"},
        headers=bearer(lead["access_token"]),
    )
    assert response.status_code == 403


@pytest.mark.ac("AC-08")
def test_ac08_3_override_requires_a_token(client: TestClient) -> None:
    """NFR-04: no token -> 401."""
    lead = case_in_review(client, "AML")
    body = {"decision": "APPROVE", "reason_code": "RISK_ACCEPTED"}
    assert client.post(f"/api/v1/cases/{lead['case_id']}/override", json=body).status_code == 401
    assert client.get(QUEUE).status_code == 401


@pytest.mark.ac("AC-08")
def test_ac08_3_override_on_a_case_not_in_manual_review_is_409(client: TestClient) -> None:
    """AC-08.3: APPROVED, REJECTED and in-flight cases return 409 INVALID_STATE."""
    approved = case_in(client, "CLEAN")
    response = override(client, approved)
    assert response.status_code == 409 and code(response) == "INVALID_STATE"
    rejected = case_in_review(client, "AML")
    override(client, rejected, "REJECT", "POLICY_OTHER")
    assert override(client, rejected, "APPROVE", "RISK_ACCEPTED").status_code == 409


@pytest.mark.ac("AC-08")
def test_ac08_3_override_unknown_case_is_404(client: TestClient) -> None:
    """Unknown case id -> 404 NOT_FOUND."""
    response = client.post(
        "/api/v1/cases/nope/override",
        json={"decision": "APPROVE", "reason_code": "RISK_ACCEPTED"},
        headers=officer(client),
    )
    assert response.status_code == 404 and code(response) == "NOT_FOUND"


@pytest.mark.ac("AC-08")
@pytest.mark.nfr("NFR-02")
def test_ac08_4_override_appends_a_row_and_an_audit_entry(
    client: TestClient, engine: Engine
) -> None:
    """AC-08.4: Override row with actor, previous_state, decision, reason, rule_version."""
    lead = case_in_review(client, "AML")
    override(client, lead, "REJECT", "CONFIRMED_WATCHLIST_MATCH", comment="match")
    row = rows(
        engine,
        "SELECT actor, previous_state, decision, reason_code, comment, rule_version"
        " FROM overrides WHERE case_id=:c",
        c=lead["case_id"],
    )[0]
    assert tuple(row) == (
        "officer1", "MANUAL_REVIEW", "REJECT", "CONFIRMED_WATCHLIST_MATCH", "match", 1,
    )  # fmt: skip
    audit = rows(
        engine,
        "SELECT actor, role, payload, correlation_id FROM audit_log"
        " WHERE case_id=:c AND event='OVERRIDE_APPLIED'",
        c=lead["case_id"],
    )
    assert len(audit) == 1 and audit[0][0] == "officer1" and audit[0][1] == "compliance-officer"
    payload = json.loads(audit[0][2])
    assert payload["previous_state"] == "MANUAL_REVIEW" and payload["decision"] == "REJECT"
    assert payload["reason_code"] == "CONFIRMED_WATCHLIST_MATCH" and payload["rule_version"] == 1
    assert "match" not in audit[0][2] and audit[0][3] != "none"


@pytest.mark.ac("AC-08")
@pytest.mark.nfr("NFR-06")
def test_ac08_4_audit_entry_carries_the_request_correlation_id(
    client: TestClient, engine: Engine
) -> None:
    """NFR-06: the OVERRIDE_APPLIED audit row stores the inbound X-Correlation-ID."""
    lead = case_in_review(client, "AML")
    response = client.post(
        f"/api/v1/cases/{lead['case_id']}/override",
        json={"decision": "APPROVE", "reason_code": "FALSE_POSITIVE_CLEARED"},
        headers={**officer(client), "X-Correlation-ID": "corr-override-1"},
    )
    assert response.headers["X-Correlation-ID"] == "corr-override-1"
    found = rows(
        engine,
        "SELECT correlation_id FROM audit_log WHERE case_id=:c AND event='OVERRIDE_APPLIED'",
        c=lead["case_id"],
    )
    assert found[0][0] == "corr-override-1"


@pytest.mark.ac("AC-08")
@pytest.mark.nfr("NFR-02")
def test_ac08_4_override_rows_cannot_be_updated_or_deleted(
    client: TestClient, engine: Engine
) -> None:
    """AC-08.4 / NFR-02: triggers reject UPDATE and DELETE on overrides."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    lead = case_in_review(client, "AML")
    override(client, lead)
    for sql in ("UPDATE overrides SET actor='x'", "DELETE FROM overrides"):
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(text(sql))


@pytest.mark.ac("AC-08")
def test_ac08_4_state_history_records_the_override_transition(
    client: TestClient, engine: Engine
) -> None:
    """The MANUAL_REVIEW -> APPROVED/REJECTED history row carries the reason code and actor."""
    lead = case_in_review(client, "AML")
    override(client, lead, "REJECT", "DOCS_INSUFFICIENT")
    last = rows(
        engine,
        "SELECT from_state, to_state, actor, reason_code FROM state_history"
        " WHERE case_id=:c ORDER BY seq DESC LIMIT 1",
        c=lead["case_id"],
    )[0]
    assert tuple(last) == ("MANUAL_REVIEW", "REJECTED", "officer1", "DOCS_INSUFFICIENT")


@pytest.mark.ac("AC-08")
@pytest.mark.ac("AC-07")
def test_ac08_5_approve_creates_the_stub_account_reject_does_not(
    client: TestClient, engine: Engine
) -> None:
    """AC-08.5 / AC-07.11: APPROVE returns the account number; REJECT creates none."""
    approved = case_in_review(client, "AML")
    body = override(client, approved, "APPROVE", "FALSE_POSITIVE_CLEARED").json()
    assert body["account_number"].startswith("SAV") and len(body["account_number"]) == 15
    rejected = case_in_review(client, "MEDIUM")
    assert override(client, rejected, "REJECT", "RISK_TOO_HIGH").json()["account_number"] is None
    accounts = rows(engine, "SELECT case_id FROM accounts")
    assert [r[0] for r in accounts] == [approved["case_id"]]
    audits = rows(engine, "SELECT COUNT(*) FROM audit_log WHERE event='ACCOUNT_CREATED'")
    assert audits[0][0] == 1


@pytest.mark.ac("AC-08")
def test_ac08_override_creates_a_notification_for_the_new_state(client: TestClient) -> None:
    """AC-09.1: the override transition notifies the prospect exactly once."""
    from pipeline_helpers import notifications

    lead = case_in_review(client, "AML")
    override(client, lead, "APPROVE", "RISK_ACCEPTED")
    events = [n["event"] for n in notifications(client, lead)]
    assert events.count("APPROVED") == 1 and events[0] == "APPROVED"


@pytest.mark.ac("AC-08")
@pytest.mark.nfr("NFR-08")
def test_ac08_6_reclassify_appends_assessment_and_audit(client: TestClient, engine: Engine) -> None:
    """AC-08.6 / NFR-08: new OFFICER_RECLASSIFY assessment plus RISK_RECLASSIFIED audit."""
    lead = case_in_review(client, "AML")
    response = reclassify(client, lead, "HIGH", "NEW_INFORMATION", comment="found more")
    body = response.json()
    assert response.status_code == 200 and body["band"] == "HIGH"
    assert (
        body["source"] == "OFFICER_RECLASSIFY" and body["score"] == 16 and body["rule_version"] == 1
    )
    assert len(body["breakdown"]) == 4
    bands = rows(
        engine, "SELECT band, source FROM risk_assessments WHERE case_id=:c ORDER BY seq",
        c=lead["case_id"],
    )  # fmt: skip
    assert [tuple(b) for b in bands] == [("LOW", "RULE_ENGINE"), ("HIGH", "OFFICER_RECLASSIFY")]
    audit = rows(
        engine,
        "SELECT actor, role, payload FROM audit_log WHERE case_id=:c AND event='RISK_RECLASSIFIED'",
        c=lead["case_id"],
    )
    payload = json.loads(audit[0][2])
    assert audit[0][0] == "officer1" and audit[0][1] == "compliance-officer"
    assert payload["previous_band"] == "LOW" and payload["new_band"] == "HIGH"
    assert payload["reason_code"] == "NEW_INFORMATION" and "found more" not in audit[0][2]
    assert state_of(client, lead) == "MANUAL_REVIEW"


@pytest.mark.ac("AC-08")
@pytest.mark.parametrize("reason", ["NEW_INFORMATION", "SCORING_ERROR", "MANUAL_ASSESSMENT"])
def test_ac08_6_every_reclassify_reason_code_is_accepted(client: TestClient, reason: str) -> None:
    """DD-4: the three proposed reclassify reason codes."""
    lead = case_in_review(client, "MEDIUM")
    assert reclassify(client, lead, "LOW", reason).status_code == 200


@pytest.mark.ac("AC-08")
def test_ac08_6_reclassify_without_or_with_bad_reason_is_422_and_band_stays(
    client: TestClient, engine: Engine
) -> None:
    """AC-08.6: missing reason -> 422 and the original band stays in force."""
    lead = case_in_review(client, "MEDIUM")
    missing = reclassify(client, lead, "HIGH", None)
    assert missing.status_code == 422 and code(missing) == "VALIDATION_ERROR"
    unknown = reclassify(client, lead, "HIGH", "RISK_ACCEPTED")
    assert unknown.status_code == 422 and code(unknown) == "UNKNOWN_REASON_CODE"
    bad_band = reclassify(client, lead, "EXTREME", "SCORING_ERROR")
    assert bad_band.status_code == 422
    assert rows(engine, "SELECT COUNT(*) FROM risk_assessments WHERE case_id=:c",
                c=lead["case_id"])[0][0] == 1  # fmt: skip
    assert rows(engine, "SELECT COUNT(*) FROM audit_log WHERE event='RISK_RECLASSIFIED'")[0][0] == 0


@pytest.mark.ac("AC-08")
@pytest.mark.nfr("NFR-08")
def test_ac08_6_reclassify_is_only_allowed_in_manual_review(client: TestClient) -> None:
    """DD-10 / NFR-08: APPROVED -> CASE_LOCKED; an in-flight case -> INVALID_STATE."""
    approved = case_in(client, "CLEAN")
    locked = reclassify(client, approved)
    assert locked.status_code == 409 and code(locked) == "CASE_LOCKED"
    from pipeline_helpers import step, submitted_case

    lead = submitted_case(client)
    step(client, lead, "screen")
    step(client, lead, "classify")
    early = reclassify(client, lead)
    assert early.status_code == 409 and code(early) == "INVALID_STATE"


@pytest.mark.ac("AC-08")
@pytest.mark.parametrize("user", ["analyst1", "admin1", "prospect1"])
def test_ac08_6_reclassify_other_roles_get_403(client: TestClient, user: str) -> None:
    """E4-S3: only the compliance officer may reclassify."""
    lead = case_in_review(client, "MEDIUM")
    assert reclassify(client, lead, user=user).status_code == 403


@pytest.mark.ac("AC-08")
def test_ac08_6_reclassify_unknown_case_is_404(client: TestClient) -> None:
    """Unknown case -> 404."""
    response = client.post(
        "/api/v1/cases/nope/reclassify",
        json={"band": "LOW", "reason_code": "SCORING_ERROR"},
        headers=officer(client),
    )
    assert response.status_code == 404


@pytest.mark.ac("AC-08")
def test_ac08_6_reclassify_never_changes_the_decision_or_state(
    client: TestClient, engine: Engine
) -> None:
    """DD-10: reclassification never auto-approves; evidence shows the latest band."""
    lead = case_in_review(client, "HIGH")
    reclassify(client, lead, "LOW", "MANUAL_ASSESSMENT")
    assert state_of(client, lead) == "MANUAL_REVIEW"
    body = client.get(f"/api/v1/cases/{lead['case_id']}/evidence", headers=officer(client)).json()
    assert body["risk_assessment"]["band"] == "LOW"
    assert body["risk_assessment"]["source"] == "OFFICER_RECLASSIFY"
    assert body["decision"]["reason_code"] == "RISK_HIGH"
    assert rows(engine, "SELECT COUNT(*) FROM accounts")[0][0] == 0


@pytest.mark.ac("AC-07")
def test_ac07_account_endpoint_staff_see_number_owner_sees_masked(client: TestClient) -> None:
    """E4-S2: GET account on an APPROVED case; owner masked, staff full; derived number."""
    from onboardx.domain.account_numbers import derive_account_number
    from onboardx.domain.enums import Product

    lead = case_in(client, "CLEAN")
    cid = lead["case_id"]
    staff = client.get(f"/api/v1/cases/{cid}/account", headers=officer(client)).json()
    assert staff["account_number"] == derive_account_number(cid, Product.SAVINGS)
    owner = client.get(f"/api/v1/cases/{cid}/account", headers=bearer(lead["access_token"]))
    assert (
        owner.json()["account_number"]
        == staff["account_number"][:3] + "*" * 8 + staff["account_number"][-4:]
    )
    assert client.get(f"/api/v1/cases/{cid}/account", headers=officer(client)).json() == staff


@pytest.mark.ac("AC-07")
def test_ac07_account_endpoint_404_until_approved_and_403_for_other_prospect(
    client: TestClient,
) -> None:
    """E4-S2: no account before approval (404); another prospect gets 403; no token 401."""
    from api_helpers import create_lead

    lead = case_in_review(client, "AML")
    url = f"/api/v1/cases/{lead['case_id']}/account"
    assert client.get(url, headers=officer(client)).status_code == 404
    other = create_lead(client)
    assert client.get(url, headers=bearer(other["access_token"])).status_code == 403
    assert client.get(url).status_code == 401
    assert client.get("/api/v1/cases/nope/account", headers=officer(client)).status_code == 404
