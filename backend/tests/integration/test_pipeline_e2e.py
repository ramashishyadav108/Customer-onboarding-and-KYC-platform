"""E4-S1 / AC-07.5 end-to-end: submit and advance drive cases A-D (data-models section 5)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import create_lead, lead_headers, staff_headers
from onboardx.controllers.dependencies.services import Services
from onboardx.domain.errors import NotFoundError
from pipeline_helpers import (
    PROFILE_C,
    PROFILE_D,
    get_case,
    history,
    ready_case,
    rows,
    state_of,
    step,
    submit,
    submitted_case,
)

SCENARIOS: list[tuple[str, dict[str, Any], str, str, int, str]] = [
    ("A", {"name": "Test Person Alpha"}, "APPROVED", "AUTO_APPROVED", 16, "LOW"),
    ("B", {"name": "Test Person One"}, "MANUAL_REVIEW", "AML_HIT", 16, "LOW"),
    (
        "C",
        {"name": "Test Person Gamma", "product": "Current", "profile": PROFILE_C},
        "MANUAL_REVIEW",
        "RISK_MEDIUM",
        45,
        "MEDIUM",
    ),
    (
        "D",
        {"name": "Test Person Delta", "product": "NRE", "profile": PROFILE_D},
        "MANUAL_REVIEW",
        "RISK_HIGH",
        72,
        "HIGH",
    ),
]
FULL_PATH = ["INITIATED", "DOCS_SUBMITTED", "SCREENED", "CLASSIFIED"]


def evidence(engine: Engine, case_id: str) -> dict[str, Any]:
    (assessment,) = rows(
        engine, "SELECT score, band FROM risk_assessments WHERE case_id=:c", c=case_id
    )
    (decision,) = rows(
        engine,
        "SELECT outcome, reason_code, type FROM decisions WHERE case_id=:c",
        c=case_id,
    )
    return {"score": assessment[0], "band": assessment[1], "decision": tuple(decision)}


@pytest.mark.ac("AC-07")
@pytest.mark.parametrize(("label", "kwargs", "state", "reason", "score", "band"), SCENARIOS)
def test_ac07_5_advance_drives_each_example_case_to_its_outcome(
    client: TestClient,
    engine: Engine,
    label: str,
    kwargs: dict[str, Any],
    state: str,
    reason: str,
    score: int,
    band: str,
) -> None:
    """Cases A-D through POST /advance: history, score, band, decision and reason."""
    lead = submitted_case(client, **kwargs)
    response = step(client, lead, "advance")
    assert response.status_code == 200, label
    body = response.json()
    assert body["state"] == state and body["steps_run"] == ["screen", "classify", "decide"]
    assert body["decision"]["reason_code"] == reason and body["decision"]["type"] == "AUTO"
    assert history(engine, lead["case_id"]) == [*FULL_PATH, state]
    found = evidence(engine, lead["case_id"])
    assert (found["score"], found["band"], found["decision"]) == (
        score,
        band,
        (state, reason, "AUTO"),
    )


@pytest.mark.ac("AC-07")
@pytest.mark.parametrize(("label", "kwargs", "state", "reason", "score", "band"), SCENARIOS)
def test_ac07_5_auto_advance_on_submit_runs_the_whole_pipeline(
    auto_client: TestClient,
    engine: Engine,
    label: str,
    kwargs: dict[str, Any],
    state: str,
    reason: str,
    score: int,
    band: str,
) -> None:
    """DD-13: with AUTO_ADVANCE_ON_SUBMIT on, one submit call reaches the final state."""
    lead = ready_case(auto_client, **kwargs)
    response = submit(auto_client, lead)
    assert response.status_code == 200, label
    assert response.json()["state"] == "DOCS_SUBMITTED"
    assert state_of(auto_client, lead) == state
    assert history(engine, lead["case_id"]) == [*FULL_PATH, state]
    assert evidence(engine, lead["case_id"])["score"] == score


@pytest.mark.ac("AC-07")
def test_ac07_5_advance_is_idempotent_with_no_new_rows(client: TestClient, engine: Engine) -> None:
    lead = submitted_case(client)
    first = step(client, lead, "advance").json()
    counts = [
        rows(engine, f"SELECT COUNT(*) FROM {t}")[0][0]
        for t in (
            "state_history",
            "screening_results",
            "risk_assessments",
            "decisions",
            "audit_log",
        )
    ]
    second = step(client, lead, "advance").json()
    assert second["steps_run"] == [] and second["state"] == first["state"]
    assert second["decision"] == first["decision"]
    assert counts == [
        rows(engine, f"SELECT COUNT(*) FROM {t}")[0][0]
        for t in (
            "state_history",
            "screening_results",
            "risk_assessments",
            "decisions",
            "audit_log",
        )
    ]


@pytest.mark.ac("AC-07")
def test_ac07_5_advance_resumes_from_a_partially_advanced_case(client: TestClient) -> None:
    """Steps already committed stay; advance runs only the remaining ones."""
    lead = submitted_case(client)
    step(client, lead, "screen")
    body = step(client, lead, "advance").json()
    assert body["steps_run"] == ["classify", "decide"] and body["state"] == "APPROVED"


@pytest.mark.ac("AC-07")
def test_ac07_5_advance_on_an_initiated_case_is_409(client: TestClient) -> None:
    response = step(client, create_lead(client), "advance")
    assert response.status_code == 409 and response.json()["error"]["code"] == "INVALID_STATE"


@pytest.mark.ac("AC-07")
def test_ac07_5_advance_on_a_manual_review_case_is_a_no_op_returning_the_decision(
    client: TestClient,
) -> None:
    lead = submitted_case(client, name="Test Person One")
    step(client, lead, "advance")
    again = step(client, lead, "advance").json()
    assert again["steps_run"] == [] and again["state"] == "MANUAL_REVIEW"
    assert again["decision"]["reason_code"] == "AML_HIT"


@pytest.mark.ac("AC-07")
def test_ac07_advance_on_an_approved_case_is_a_no_op(client: TestClient) -> None:
    lead = submitted_case(client)
    step(client, lead, "advance")
    again = step(client, lead, "advance")
    assert again.status_code == 200 and again.json()["steps_run"] == []


@pytest.mark.ac("AC-07")
@pytest.mark.parametrize("user", ["analyst1", "admin1"])
def test_ac07_advance_is_allowed_for_analyst_and_admin(client: TestClient, user: str) -> None:
    lead = submitted_case(client)
    response = step(client, lead, "advance", user)
    assert response.status_code == 200
    assert response.json()["decision"]["actor"] == user


@pytest.mark.ac("AC-07")
def test_ac07_auto_advance_attributes_steps_to_the_system_actor(
    auto_client: TestClient, engine: Engine
) -> None:
    lead = ready_case(auto_client)
    submit(auto_client, lead)
    actors = {
        r[0]
        for r in rows(
            engine,
            "SELECT actor FROM state_history WHERE case_id=:c AND to_state NOT IN"
            " ('INITIATED','DOCS_SUBMITTED')",
            c=lead["case_id"],
        )
    }
    assert actors == {"system"}
    (role,) = {r[0] for r in rows(engine, "SELECT role FROM audit_log WHERE event='CASE_SCREENED'")}
    assert role == "system"


@pytest.mark.ac("AC-07")
def test_ac07_auto_advance_repeat_submit_after_the_pipeline_is_409(auto_client: TestClient) -> None:
    """AC-02.9: a later state makes a repeated submit an INVALID_STATE."""
    lead = ready_case(auto_client)
    assert submit(auto_client, lead).status_code == 200
    assert submit(auto_client, lead).status_code == 409


@pytest.mark.ac("AC-07")
def test_ac07_auto_advance_failure_does_not_fail_the_submit_and_advance_resumes(
    auto_client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing pipeline step is logged; submit stays 200; staff advance finishes the job."""
    services: Services = auto_client.app.state.services  # type: ignore[attr-defined]
    original = services.risk.classify

    def boom(**_kwargs: Any) -> None:
        raise NotFoundError("rule_set")

    monkeypatch.setattr(services.risk, "classify", boom)
    lead = ready_case(auto_client)
    with caplog.at_level("ERROR"):
        assert submit(auto_client, lead).status_code == 200
    assert state_of(auto_client, lead) == "SCREENED"
    failures = [r for r in caplog.records if r.getMessage() == "auto-advance failed"]
    assert failures and failures[0].__dict__["case_id"] == lead["case_id"]
    monkeypatch.setattr(services.risk, "classify", original)
    resumed = step(auto_client, lead, "advance").json()
    assert resumed["steps_run"] == ["classify", "decide"] and resumed["state"] == "APPROVED"


@pytest.mark.ac("AC-07")
def test_ac07_1_approved_case_detail_shows_masked_account_and_no_missing_items(
    client: TestClient,
) -> None:
    lead = submitted_case(client)
    step(client, lead, "advance")
    detail = get_case(client, lead)
    assert detail["state"] == "APPROVED" and detail["missing_items"] == []
    assert (
        detail["account_number_masked"].startswith("SAV") and "*" in detail["account_number_masked"]
    )
    staff = client.get(f"/api/v1/cases/{lead['case_id']}", headers=staff_headers(client))
    assert staff.json()["account_number_masked"] == detail["account_number_masked"]
    assert staff.json()["profile"] is None


@pytest.mark.ac("AC-07")
def test_ac07_2_manual_review_case_has_no_account_in_its_detail(client: TestClient) -> None:
    lead = submitted_case(client, name="Test Person One")
    step(client, lead, "advance")
    assert get_case(client, lead)["account_number_masked"] is None


@pytest.mark.ac("AC-07")
def test_ac07_6_account_numbers_are_unique_per_case_and_match_the_product_prefix(
    client: TestClient, engine: Engine
) -> None:
    for product in ("Savings", "Current", "NRE"):
        step(client, submitted_case(client, product=product), "advance")
    found = [r[0] for r in rows(engine, "SELECT account_number FROM accounts ORDER BY seq")]
    assert [n[:3] for n in found] == ["SAV", "CUR", "NRE"] and len(set(found)) == 3
    assert all(len(n) == 15 and n[3:].isdigit() for n in found)


def floats_in(value: Any) -> list[float]:
    if isinstance(value, float):
        return [value]
    if isinstance(value, dict):
        return [f for v in value.values() for f in floats_in(v)]
    if isinstance(value, list):
        return [f for v in value for f in floats_in(v)]
    return []


@pytest.mark.nfr("NFR-01")
def test_nfr01_no_float_appears_in_any_pipeline_response(client: TestClient) -> None:
    lead = submitted_case(client, product="Current", profile=PROFILE_C)
    headers = staff_headers(client)
    for name in ("screen", "classify", "decide", "advance"):
        body = client.post(f"/api/v1/cases/{lead['case_id']}/{name}", headers=headers).json()
        assert floats_in(body) == [], name


@pytest.mark.ac("AC-07")
def test_ac07_steps_after_manual_review_are_refused_by_the_state_machine(
    client: TestClient,
) -> None:
    lead = submitted_case(client, name="Test Person One")
    step(client, lead, "advance")
    for name in ("screen", "classify"):
        assert step(client, lead, name).status_code == 409
    assert step(client, lead, "decide").status_code == 200  # idempotent original decision


@pytest.mark.ac("AC-04")
def test_ac04_pipeline_history_rows_form_a_single_path_with_no_duplicates(
    client: TestClient, engine: Engine
) -> None:
    lead = submitted_case(client)
    step(client, lead, "advance")
    step(client, lead, "advance")
    path = history(engine, lead["case_id"])
    assert path == [*FULL_PATH, "APPROVED"] and len(path) == len(set(path))
    audits = rows(
        engine,
        "SELECT COUNT(*) FROM audit_log WHERE event='STATE_TRANSITION' AND case_id=:c",
        c=lead["case_id"],
    )
    assert audits[0][0] == 4


@pytest.mark.nfr("NFR-04")
def test_nfr04_prospect_token_cannot_reach_staff_views_of_the_pipeline(client: TestClient) -> None:
    lead = submitted_case(client)
    assert (
        client.post(
            f"/api/v1/cases/{lead['case_id']}/advance", headers=lead_headers(lead)
        ).status_code
        == 403
    )
