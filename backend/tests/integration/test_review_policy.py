"""AC-15 / AC-07 / AC-08: REVIEW_POLICY=manual sends every case to a compliance officer."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_helpers import bearer, staff_headers
from helpers import JWT_SECRET, FakeClock
from onboardx.config.settings import ConfigurationError, Settings, load_settings
from onboardx.domain.decision import decide
from onboardx.domain.enums import CaseState, DecisionReason, RiskBand
from onboardx.main import create_app
from pipeline_helpers import notifications, submitted_case
from review_helpers import officer

VERIFIED = ["VERIFIED", "VERIFIED", "VERIFIED"]


@pytest.fixture
def manual_client(db_url: str, upload_dir: Path, clock: FakeClock) -> Iterator[TestClient]:
    """Default pipeline behaviour (submit runs everything) with the manual review policy."""
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url=db_url,
        jwt_secret=JWT_SECRET,
        upload_dir=upload_dir,
        review_policy="manual",
    )
    with TestClient(create_app(settings, clock=clock)) as client:
        yield client


@pytest.mark.ac("AC-15.1")
def test_ac15_1_auto_policy_is_the_default_and_still_auto_approves() -> None:
    outcome = decide(RiskBand.LOW, [], VERIFIED)
    assert (outcome.outcome, outcome.reason) == (CaseState.APPROVED, DecisionReason.AUTO_APPROVED)
    settings = Settings(database_url="sqlite:///:memory:", _env_file=None)  # type: ignore[call-arg]
    assert settings.review_policy == "auto"


@pytest.mark.ac("AC-15.2")
def test_ac15_2_manual_policy_routes_a_clean_low_risk_case_to_review() -> None:
    outcome = decide(RiskBand.LOW, [], VERIFIED, manual_policy=True)
    assert outcome.outcome is CaseState.MANUAL_REVIEW
    assert outcome.reason is DecisionReason.MANUAL_POLICY


@pytest.mark.ac("AC-15.2")
@pytest.mark.parametrize(
    ("band", "hits", "statuses", "expected"),
    [
        (RiskBand.LOW, [{"reason_code": "AML_HIT"}], VERIFIED, DecisionReason.AML_HIT),
        (RiskBand.LOW, [{"reason_code": "PEP_HIT"}], VERIFIED, DecisionReason.PEP_HIT),
        (RiskBand.LOW, [], ["FLAGGED", "VERIFIED"], DecisionReason.DOC_UNRECOGNISED),
        (RiskBand.MEDIUM, [], VERIFIED, DecisionReason.RISK_MEDIUM),
        (RiskBand.HIGH, [], VERIFIED, DecisionReason.RISK_HIGH),
    ],
)
def test_ac15_2_specific_reasons_keep_precedence_over_the_policy_reason(
    band: RiskBand, hits: list[dict[str, str]], statuses: list[str], expected: DecisionReason
) -> None:
    assert decide(band, hits, statuses, manual_policy=True).reason is expected


@pytest.mark.ac("AC-15.3")
def test_ac15_3_manual_policy_end_to_end_officer_approves_and_account_appears(
    manual_client: TestClient,
) -> None:
    lead = submitted_case(manual_client)
    case = f"/api/v1/cases/{lead['case_id']}"
    staff = staff_headers(manual_client, "analyst1")
    assert manual_client.get(case, headers=staff).json()["state"] == "MANUAL_REVIEW"
    evidence = manual_client.get(f"{case}/evidence", headers=staff).json()
    assert evidence["decision"]["reason_code"] == "MANUAL_POLICY"
    assert evidence["screening"] is not None and evidence["risk_assessment"]["band"] == "LOW"
    assert manual_client.get(f"{case}/account", headers=staff).status_code == 404

    queue = manual_client.get("/api/v1/review-queue", headers=officer(manual_client)).json()
    assert [(i["case_id"], i["reason_code"]) for i in queue["items"]] == [
        (lead["case_id"], "MANUAL_POLICY")
    ]
    done = manual_client.post(
        f"{case}/override",
        json={"decision": "APPROVE", "reason_code": "DOCS_CONFIRMED"},
        headers=officer(manual_client),
    )
    assert done.status_code == 200, done.text
    assert done.json()["state"] == "APPROVED" and done.json()["account_number"]
    assert manual_client.get(f"{case}/account", headers=staff).status_code == 200
    events = [n["event"] for n in notifications(manual_client, lead)]
    assert "MANUAL_REVIEW" in events and "APPROVED" in events


@pytest.mark.ac("AC-15.3")
def test_ac15_3_manual_policy_officer_can_reject_and_no_account_is_created(
    manual_client: TestClient,
) -> None:
    lead = submitted_case(manual_client)
    case = f"/api/v1/cases/{lead['case_id']}"
    rejected = manual_client.post(
        f"{case}/override",
        json={"decision": "REJECT", "reason_code": "RISK_TOO_HIGH"},
        headers=officer(manual_client),
    )
    assert rejected.status_code == 200 and rejected.json()["state"] == "REJECTED"
    assert (
        manual_client.get(f"{case}/account", headers=staff_headers(manual_client)).status_code
        == 404
    )


@pytest.mark.ac("AC-15.3")
def test_ac15_3_only_the_compliance_officer_can_decide_a_policy_case(
    manual_client: TestClient,
) -> None:
    lead = submitted_case(manual_client)
    url = f"/api/v1/cases/{lead['case_id']}/override"
    body = {"decision": "APPROVE", "reason_code": "DOCS_CONFIRMED"}
    for user in ("analyst1", "admin1", "prospect1"):
        assert (
            manual_client.post(
                url, json=body, headers=staff_headers(manual_client, user)
            ).status_code
            == 403
        )
    assert (
        manual_client.post(url, json=body, headers=bearer(lead["access_token"])).status_code == 403
    )


@pytest.mark.ac("AC-15.4")
def test_ac15_4_an_unknown_review_policy_fails_fast_naming_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("REVIEW_POLICY", "sometimes")
    with pytest.raises(ConfigurationError, match="REVIEW_POLICY"):
        load_settings()
