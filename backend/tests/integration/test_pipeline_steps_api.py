"""E3-S1 / E3-S3 / E4-S1: screen, classify and decide endpoints (AC-05, AC-06, AC-07)."""

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from api_helpers import create_lead, lead_headers, staff_headers
from pipeline_helpers import (
    PROFILE_C,
    PROFILE_D,
    get_case,
    history,
    rows,
    state_of,
    step,
    submitted_case,
)

WATCHLIST_ONE = "10000000-0000-4000-8000-000000000001"


@pytest.mark.ac("AC-05")
def test_ac05_1_screening_a_submitted_case_stores_a_result_and_moves_to_screened(
    client: TestClient, engine: Engine
) -> None:
    lead = submitted_case(client)
    response = step(client, lead, "screen")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "SCREENED"
    result = body["result"]
    assert set(result) == {
        "id", "case_id", "hits", "requires_manual_review", "watchlist_version", "screened_at",
    }  # fmt: skip
    assert result["case_id"] == lead["case_id"] and result["hits"] == []
    assert result["requires_manual_review"] is False and result["watchlist_version"] == 10
    assert history(engine, lead["case_id"]) == ["INITIATED", "DOCS_SUBMITTED", "SCREENED"]


@pytest.mark.ac("AC-05")
def test_ac05_3_watchlist_hit_is_recorded_and_the_case_still_moves_to_screened(
    client: TestClient, engine: Engine
) -> None:
    """Case B: name 'Test Person One' hits entry 1; no SCREENED -> MANUAL_REVIEW edge."""
    lead = submitted_case(client, name="Test Person One")
    body = step(client, lead, "screen").json()
    assert body["state"] == "SCREENED"
    assert body["result"]["requires_manual_review"] is True
    assert body["result"]["hits"] == [
        {"entry_id": WATCHLIST_ONE, "list_type": "AML", "reason_code": "AML_HIT"}
    ]
    assert state_of(client, lead) == "SCREENED"


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize(
    ("name", "list_type", "reason"),
    [
        ("TEST  person-ONE", "AML", "AML_HIT"),
        ("Person One Test", "AML", "AML_HIT"),
        ("T P One", "AML", "AML_HIT"),
        ("Mock Minister Epsilon", "PEP", "PEP_HIT"),
        ("senator zeta", "PEP", "PEP_HIT"),
    ],
)
def test_ac05_2_variants_hit_through_the_endpoint(
    client: TestClient, name: str, list_type: str, reason: str
) -> None:
    lead = submitted_case(client, name=name)
    (hit,) = step(client, lead, "screen").json()["result"]["hits"]
    assert (hit["list_type"], hit["reason_code"]) == (list_type, reason)


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize("name", ["Test Person Two", "Test Person", "Completely Different"])
def test_ac05_2_non_matching_names_are_clean(client: TestClient, name: str) -> None:
    lead = submitted_case(client, name=name)
    result = step(client, lead, "screen").json()["result"]
    assert result["hits"] == [] and result["requires_manual_review"] is False


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize("user", ["analyst1", "admin1"])
def test_ac05_screen_is_allowed_for_analyst_and_admin(client: TestClient, user: str) -> None:
    lead = submitted_case(client)
    assert step(client, lead, "screen", user).status_code == 200


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("name", ["screen", "classify", "decide", "advance"])
def test_nfr04_pipeline_steps_reject_officer_prospect_and_anonymous(
    client: TestClient, name: str
) -> None:
    lead = submitted_case(client)
    url = f"/api/v1/cases/{lead['case_id']}/{name}"
    assert step(client, lead, name, "officer1").status_code == 403
    assert client.post(url, headers=lead_headers(lead)).status_code == 403
    assert client.post(url).status_code == 401
    assert state_of(client, lead) == "DOCS_SUBMITTED"


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize("name", ["screen", "classify", "decide", "advance"])
def test_ac05_steps_on_an_unknown_case_are_404(client: TestClient, name: str) -> None:
    response = client.post(
        f"/api/v1/cases/00000000-0000-4000-8000-00000000dead/{name}",
        headers=staff_headers(client),
    )
    assert response.status_code == 404


@pytest.mark.ac("AC-05")
def test_ac05_6_screening_an_initiated_case_is_409_invalid_state(client: TestClient) -> None:
    lead = create_lead(client)
    response = step(client, lead, "screen")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"
    assert response.json()["error"]["details"]["from_state"] == "INITIATED"


@pytest.mark.ac("AC-05")
@pytest.mark.parametrize("later", [["classify"], ["classify", "decide"]])
def test_ac05_6_screening_after_classification_is_409(client: TestClient, later: list[str]) -> None:
    lead = submitted_case(client)
    step(client, lead, "screen")
    for name in later:
        step(client, lead, name)
    assert step(client, lead, "screen").status_code == 409


@pytest.mark.ac("AC-05")
def test_ac05_6_repeat_screen_on_screened_with_same_watchlist_returns_the_existing_result(
    client: TestClient, engine: Engine
) -> None:
    lead = submitted_case(client)
    first = step(client, lead, "screen").json()["result"]
    second = step(client, lead, "screen").json()["result"]
    assert first == second
    assert rows(engine, "SELECT COUNT(*) FROM screening_results")[0][0] == 1
    assert history(engine, lead["case_id"]).count("SCREENED") == 1


@pytest.mark.ac("AC-05")
def test_ac05_7_rescreening_after_a_watchlist_change_appends_a_new_row_without_a_transition(
    client: TestClient, engine: Engine
) -> None:
    """AC-05.7/05.9: a deactivation changes the version; re-screen appends, never updates."""
    lead = submitted_case(client, name="Test Person One")
    first = step(client, lead, "screen").json()["result"]
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO watchlist_deactivations (id, entry_id, deactivated_by, created_at)"
                " VALUES ('d1', :e, 'admin1', '2026-10-01T00:00:00Z')"
            ),
            {"e": WATCHLIST_ONE},
        )
    second = step(client, lead, "screen").json()["result"]
    assert first["hits"] != [] and second["hits"] == []
    assert second["watchlist_version"] == first["watchlist_version"] + 1
    assert second["id"] != first["id"]
    assert rows(engine, "SELECT COUNT(*) FROM screening_results")[0][0] == 2
    assert history(engine, lead["case_id"]).count("SCREENED") == 1
    assert state_of(client, lead) == "SCREENED"


@pytest.mark.ac("AC-05")
def test_ac05_9_a_deactivated_entry_no_longer_hits_new_cases(
    client: TestClient, engine: Engine
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO watchlist_deactivations (id, entry_id, deactivated_by, created_at)"
                " VALUES ('d1', :e, 'admin1', '2026-10-01T00:00:00Z')"
            ),
            {"e": WATCHLIST_ONE},
        )
    lead = submitted_case(client, name="Test Person One")
    assert step(client, lead, "screen").json()["result"]["hits"] == []


@pytest.mark.ac("AC-05")
def test_ac05_7_an_added_entry_is_honoured_by_later_screening(
    client: TestClient, engine: Engine
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO watchlist_entries (entry_id, name, aliases, list_type, name_tokens,"
                " alias_tokens, added_by, created_at) VALUES ('new-1', 'Zorblax Quentin', '[]',"
                " 'PEP', 'quentin zorblax', '[]', 'admin1', '2026-10-01T00:00:00Z')"
            )
        )
    lead = submitted_case(client, name="quentin ZORBLAX")
    (hit,) = step(client, lead, "screen").json()["result"]["hits"]
    assert hit == {"entry_id": "new-1", "list_type": "PEP", "reason_code": "PEP_HIT"}


@pytest.mark.nfr("NFR-02")
def test_nfr02_screening_results_are_append_only(client: TestClient, engine: Engine) -> None:
    lead = submitted_case(client)
    step(client, lead, "screen")
    for statement in ("UPDATE screening_results SET hits='[]'", "DELETE FROM screening_results"):
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(text(statement))


@pytest.mark.ac("AC-05")
def test_ac05_screening_audit_and_history_carry_hit_count_and_reason_but_no_name(
    client: TestClient, engine: Engine
) -> None:
    """AC-05.10: audit holds counts and ids, never the applicant name."""
    lead = submitted_case(client, name="Test Person One")
    step(client, lead, "screen")
    (audit,) = rows(engine, "SELECT payload FROM audit_log WHERE event='CASE_SCREENED'")
    payload = json.loads(audit[0])
    assert payload["hit_count"] == 1 and payload["watchlist_version"] == 10
    assert "Test Person" not in audit[0]
    (reason,) = rows(
        engine,
        "SELECT reason_code FROM state_history WHERE to_state='SCREENED' AND case_id=:c",
        c=lead["case_id"],
    )
    assert reason[0] == "AML_HIT"


@pytest.mark.ac("AC-06")
def test_ac06_10_classify_a_screened_case_returns_score_band_and_rule_version(
    client: TestClient, engine: Engine
) -> None:
    """Case A: age 36, 3,000,000, SELF_EMPLOYED, IN/MH -> 16 LOW."""
    lead = submitted_case(client)
    step(client, lead, "screen")
    response = step(client, lead, "classify")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "CLASSIFIED" and body["case_id"] == lead["case_id"]
    assessment = body["assessment"]
    assert (assessment["score"], assessment["band"], assessment["rule_version"]) == (16, "LOW", 1)
    assert assessment["source"] == "RULE_ENGINE"
    assert {
        f["factor"]: (f["points"], f["weight"], f["contribution"]) for f in assessment["breakdown"]
    } == {
        "age": (0, 20, 0),
        "income_band": (30, 25, 750),
        "occupation_category": (30, 30, 900),
        "geography": (0, 25, 0),
    }
    assert history(engine, lead["case_id"])[-1] == "CLASSIFIED"


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize(
    ("profile", "product", "score", "band"),
    [(PROFILE_C, "Current", 45, "MEDIUM"), (PROFILE_D, "NRE", 72, "HIGH")],
)
def test_ac06_7_worked_examples_c_and_d(
    client: TestClient, profile: dict[str, Any], product: str, score: int, band: str
) -> None:
    lead = submitted_case(client, product=product, profile=profile)
    step(client, lead, "screen")
    assessment = step(client, lead, "classify").json()["assessment"]
    assert (assessment["score"], assessment["band"]) == (score, band)
    assert all(type(f["points"]) is int for f in assessment["breakdown"])
    assert type(assessment["score"]) is int


@pytest.mark.ac("AC-06")
def test_ac06_9_assessment_breakdown_hides_raw_income_and_occupation(
    client: TestClient,
) -> None:
    """Contract: value_label is a band label, never raw income or occupation text."""
    lead = submitted_case(client)
    step(client, lead, "screen")
    response = step(client, lead, "classify")
    assert "3000000" not in response.text and "SELF_EMPLOYED" not in response.text
    labels = {f["factor"]: f["value_label"] for f in response.json()["assessment"]["breakdown"]}
    assert labels["income_band"] == "B3" and labels["age"] == "25-60"


@pytest.mark.ac("AC-06")
@pytest.mark.parametrize("state", ["INITIATED", "DOCS_SUBMITTED"])
def test_ac06_10_classify_before_screening_is_409(client: TestClient, state: str) -> None:
    lead = create_lead(client) if state == "INITIATED" else submitted_case(client)
    response = step(client, lead, "classify")
    assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_STATE"


@pytest.mark.ac("AC-06")
def test_ac06_10_classify_twice_is_409_and_appends_nothing(
    client: TestClient, engine: Engine
) -> None:
    lead = submitted_case(client)
    step(client, lead, "screen")
    step(client, lead, "classify")
    assert step(client, lead, "classify").status_code == 409
    assert rows(engine, "SELECT COUNT(*) FROM risk_assessments")[0][0] == 1


@pytest.mark.ac("AC-06")
def test_ac06_10_missing_profile_field_is_422_and_the_state_is_unchanged(
    client: TestClient, engine: Engine
) -> None:
    """A case pushed to SCREENED without a profile row fails with MISSING_PROFILE_FIELD."""
    lead = create_lead(client)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET state='SCREENED' WHERE case_id=:c"), {"c": lead["case_id"]}
        )
    response = step(client, lead, "classify")
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "MISSING_PROFILE_FIELD",
        "message": "A profile field needed by the rules is missing",
        "details": {"field": "date_of_birth"},
    }
    assert rows(engine, "SELECT state FROM cases")[0][0] == "SCREENED"
    assert rows(engine, "SELECT COUNT(*) FROM risk_assessments")[0][0] == 0


@pytest.mark.ac("AC-06")
def test_ac06_9_each_assessment_records_the_rule_version_and_later_publishing_changes_nothing(
    client: TestClient, engine: Engine
) -> None:
    lead = submitted_case(client)
    step(client, lead, "screen")
    step(client, lead, "classify")
    admin = staff_headers(client, "admin1")
    draft = client.post("/api/v1/admin/rule-sets", headers=admin).json()
    assert (
        client.post(
            f"/api/v1/admin/rule-sets/{draft['version']}/publish", headers=admin
        ).status_code
        == 200
    )
    (row,) = rows(engine, "SELECT rule_version, score, band FROM risk_assessments")
    assert tuple(row) == (1, 16, "LOW")
    later = submitted_case(client)
    step(client, later, "screen")
    assert step(client, later, "classify").json()["assessment"]["rule_version"] == draft["version"]


@pytest.mark.nfr("NFR-02")
@pytest.mark.ac("AC-07.9")
def test_nfr02_risk_assessments_decisions_accounts_notifications_are_append_only(
    client: TestClient, engine: Engine
) -> None:
    lead = submitted_case(client)
    for name in ("screen", "classify", "decide"):
        step(client, lead, name)
    for table in ("risk_assessments", "decisions", "accounts", "notifications"):
        for statement in (f"UPDATE {table} SET seq = seq", f"DELETE FROM {table}"):
            with pytest.raises(IntegrityError), engine.begin() as conn:
                conn.execute(text(statement))


@pytest.mark.ac("AC-07")
def test_ac07_1_decide_approves_a_clean_low_case_and_creates_the_account(
    client: TestClient, engine: Engine
) -> None:
    lead = submitted_case(client)
    step(client, lead, "screen")
    step(client, lead, "classify")
    response = step(client, lead, "decide")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "APPROVED"
    decision = body["decision"]
    assert (decision["type"], decision["outcome"], decision["reason_code"]) == (
        "AUTO",
        "APPROVED",
        "AUTO_APPROVED",
    )
    assert decision["rule_version"] == 1 and decision["actor"] == "analyst1"
    assert body["account_number"].startswith("SAV") and len(body["account_number"]) == 15
    (account,) = rows(engine, "SELECT account_number, product FROM accounts")
    assert account[0] == body["account_number"] and account[1] == "Savings"


@pytest.mark.ac("AC-07")
def test_ac07_6_account_number_is_the_derived_one_and_masked_in_the_case_detail(
    client: TestClient,
) -> None:
    from onboardx.domain.account_numbers import derive_account_number
    from onboardx.domain.enums import Product

    lead = submitted_case(client)
    for name in ("screen", "classify"):
        step(client, lead, name)
    number = step(client, lead, "decide").json()["account_number"]
    assert number == derive_account_number(lead["case_id"], Product.SAVINGS)
    masked = get_case(client, lead)["account_number_masked"]
    assert masked == f"SAV{'*' * 8}{number[-4:]}"
    assert number not in json.dumps(get_case(client, lead))


@pytest.mark.ac("AC-07")
@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"name": "Test Person One"}, "AML_HIT"),
        ({"name": "Mock Minister Epsilon"}, "PEP_HIT"),
        ({"product": "Current", "profile": PROFILE_C}, "RISK_MEDIUM"),
        ({"product": "NRE", "profile": PROFILE_D}, "RISK_HIGH"),
        ({"overrides": {"ID_PROOF": "junk.pdf"}}, "DOC_UNRECOGNISED"),
        ({"overrides": {"ID_PROOF": "utility-bill_1.pdf"}}, "DOC_UNRECOGNISED"),
    ],
)
def test_ac07_2_every_non_approval_routes_to_manual_review_with_its_code_and_no_account(
    client: TestClient, engine: Engine, kwargs: dict[str, Any], reason: str
) -> None:
    lead = submitted_case(client, **kwargs)
    for name in ("screen", "classify"):
        step(client, lead, name)
    body = step(client, lead, "decide").json()
    assert body["state"] == "MANUAL_REVIEW" and body["account_number"] is None
    assert (body["decision"]["outcome"], body["decision"]["reason_code"]) == (
        "MANUAL_REVIEW",
        reason,
    )
    assert rows(engine, "SELECT COUNT(*) FROM accounts")[0][0] == 0
    (row,) = rows(
        engine,
        "SELECT reason_code FROM state_history WHERE to_state='MANUAL_REVIEW' AND case_id=:c",
        c=lead["case_id"],
    )
    assert row[0] == reason


@pytest.mark.ac("AC-07")
def test_ac07_2_a_rejected_document_sends_the_case_to_manual_review(client: TestClient) -> None:
    from pipeline_helpers import reject

    lead = submitted_case(client)
    item = next(
        i for i in get_case(client, lead)["checklist_items"] if i["item_code"] == "PHOTOGRAPH"
    )
    assert reject(client, lead, item["document_id"]).status_code == 200
    for name in ("screen", "classify"):
        step(client, lead, name)
    assert step(client, lead, "decide").json()["decision"]["reason_code"] == "DOC_UNRECOGNISED"


@pytest.mark.ac("AC-07")
def test_ac07_4_decide_is_idempotent_and_returns_the_original_decision(
    client: TestClient, engine: Engine
) -> None:
    lead = submitted_case(client)
    for name in ("screen", "classify"):
        step(client, lead, name)
    first = step(client, lead, "decide").json()
    second = step(client, lead, "decide").json()
    assert first == second
    assert rows(engine, "SELECT COUNT(*) FROM decisions")[0][0] == 1
    assert rows(engine, "SELECT COUNT(*) FROM accounts")[0][0] == 1
    assert history(engine, lead["case_id"]).count("APPROVED") == 1


@pytest.mark.ac("AC-07")
@pytest.mark.parametrize("name", ["INITIATED", "DOCS_SUBMITTED", "SCREENED"])
def test_ac07_decide_before_classification_is_409(client: TestClient, name: str) -> None:
    lead = create_lead(client)
    if name != "INITIATED":
        lead = submitted_case(client)
    if name == "SCREENED":
        step(client, lead, "screen")
    response = step(client, lead, "decide")
    assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_STATE"


@pytest.mark.ac("AC-07")
def test_ac07_3_an_approved_case_cannot_be_modified(client: TestClient, engine: Engine) -> None:
    """AC-07.3 / NFR-08: the DB refuses any update of an APPROVED case."""
    lead = submitted_case(client)
    for name in ("screen", "classify", "decide"):
        step(client, lead, name)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET state='REJECTED' WHERE case_id=:c"), {"c": lead["case_id"]}
        )
    from pipeline_helpers import upload

    locked = upload(client, lead, "ID_PROOF", "pan_2.pdf")
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "CASE_LOCKED"


@pytest.mark.ac("AC-07")
def test_ac07_decision_audit_and_account_audit_do_not_expose_the_number(
    client: TestClient, engine: Engine
) -> None:
    """AC-07.10: ACCOUNT_CREATED audit holds only the masked number."""
    lead = submitted_case(client)
    for name in ("screen", "classify"):
        step(client, lead, name)
    number = step(client, lead, "decide").json()["account_number"]
    (account_audit,) = rows(engine, "SELECT payload FROM audit_log WHERE event='ACCOUNT_CREATED'")
    assert number not in account_audit[0] and number[-4:] in account_audit[0]
    decided = rows(engine, "SELECT payload FROM audit_log WHERE event='DECISION_RECORDED'")
    assert len(decided) == 1 and json.loads(decided[0][0])["reason_code"] == "AUTO_APPROVED"
