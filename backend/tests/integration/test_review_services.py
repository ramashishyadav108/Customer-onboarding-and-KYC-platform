"""NFR-08 / NFR-02 / AC-08 at service level: audited reassignment and immutable approved cases."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from helpers import FakeClock
from onboardx.controllers.dependencies.services import Services
from onboardx.domain.entities import AuditEntry
from onboardx.domain.enums import AuditEvent, CaseState, RiskBand
from onboardx.domain.errors import (
    CaseLockedError,
    DomainError,
    InvalidOnboardingStateException,
    NotFoundError,
    OverrideAuditRequiredError,
    UnknownReasonCodeError,
    ValidationError,
)
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from pipeline_helpers import PDF_BYTES, rows
from review_helpers import case_in, case_in_review

ACTOR = {"actor": "officer1", "role": "compliance-officer"}


def reclassify_audit(audit: AuditService, uow: Any, case_id: str) -> AuditEntry:
    return audit.record(
        uow,
        event=AuditEvent.RISK_RECLASSIFIED,
        actor="officer1",
        role="compliance-officer",
        case_id=case_id,
        payload={"new_band": "HIGH"},
    )


@pytest.mark.nfr("NFR-08")
@pytest.mark.ac("AC-08")
def test_nfr08_reassignment_without_an_audit_record_is_refused(
    client: TestClient, services: Services, uow_factory: UnitOfWorkFactory, engine: Engine
) -> None:
    """E5-S5 AC3: reassign_band(audit=None) fails and appends nothing."""
    lead = case_in_review(client, "MEDIUM")
    with uow_factory() as uow, pytest.raises(OverrideAuditRequiredError) as info:
        services.risk.reassign_band(uow, case_id=lead["case_id"], band=RiskBand.LOW, audit=None)
        uow.commit()
    assert info.value.code == "OVERRIDE_AUDIT_REQUIRED"
    count = rows(
        engine, "SELECT COUNT(*) FROM risk_assessments WHERE case_id=:c", c=lead["case_id"]
    )
    assert count[0][0] == 1


@pytest.mark.nfr("NFR-08")
def test_nfr08_a_fabricated_audit_entry_that_was_never_persisted_is_refused(
    client: TestClient, services: Services, uow_factory: UnitOfWorkFactory, clock: FakeClock
) -> None:
    """NFR-08: an AuditEntry object that is not in audit_log does not count as a record."""
    lead = case_in_review(client, "MEDIUM")
    fake = AuditEntry(
        "fake-id", lead["case_id"], "RISK_RECLASSIFIED", "officer1", "compliance-officer", {},
        "none", "2026-10-01T00:00:00Z",
    )  # fmt: skip
    with uow_factory() as uow, pytest.raises(OverrideAuditRequiredError):
        services.risk.reassign_band(uow, case_id=lead["case_id"], band=RiskBand.LOW, audit=fake)


@pytest.mark.nfr("NFR-08")
def test_nfr08_an_audit_entry_of_the_wrong_event_or_case_is_refused(
    client: TestClient, services: Services, uow_factory: UnitOfWorkFactory, clock: FakeClock
) -> None:
    """NFR-08: the record must be RISK_RECLASSIFIED and for the same case."""
    lead = case_in_review(client, "MEDIUM")
    other = case_in_review(client, "HIGH")
    audit = AuditService(clock)
    with uow_factory() as uow:
        wrong_event = audit.record(
            uow, event=AuditEvent.CASE_CLASSIFIED, actor="x", role="admin", case_id=lead["case_id"]
        )
        with pytest.raises(OverrideAuditRequiredError):
            services.risk.reassign_band(
                uow, case_id=lead["case_id"], band=RiskBand.LOW, audit=wrong_event
            )
        other_case = reclassify_audit(audit, uow, other["case_id"])
        with pytest.raises(OverrideAuditRequiredError):
            services.risk.reassign_band(
                uow, case_id=lead["case_id"], band=RiskBand.LOW, audit=other_case
            )


@pytest.mark.nfr("NFR-08")
@pytest.mark.ac("AC-08")
def test_nfr08_reassignment_with_a_persisted_audit_record_succeeds(
    client: TestClient,
    services: Services,
    uow_factory: UnitOfWorkFactory,
    clock: FakeClock,
    engine: Engine,
) -> None:
    """E5-S5 AC3: with the record the reassignment succeeds and both rows exist."""
    lead = case_in_review(client, "MEDIUM")
    cid = lead["case_id"]
    with uow_factory() as uow:
        entry = reclassify_audit(AuditService(clock), uow, cid)
        assessment = services.risk.reassign_band(uow, case_id=cid, band=RiskBand.HIGH, audit=entry)
        uow.commit()
    assert assessment.band == "HIGH" and assessment.source == "OFFICER_RECLASSIFY"
    assert assessment.score == 45 and assessment.rule_version == 1
    events = rows(engine, "SELECT COUNT(*) FROM audit_log WHERE event='RISK_RECLASSIFIED'")
    assert events[0][0] == 1
    latest = rows(
        engine, "SELECT band FROM risk_assessments WHERE case_id=:c ORDER BY seq DESC", c=cid
    )
    assert latest[0][0] == "HIGH"


@pytest.mark.nfr("NFR-08")
def test_nfr08_reclassify_service_entry_points_reject_bad_input_before_writing(
    client: TestClient, services: Services, engine: Engine
) -> None:
    """Service-level validation: band, reason and comment length."""
    lead = case_in_review(client, "MEDIUM")
    base = {"case_id": lead["case_id"], **ACTOR}
    with pytest.raises(ValidationError):
        services.overrides.reclassify(
            band="EXTREME", reason_code="SCORING_ERROR", comment=None, **base
        )
    with pytest.raises(UnknownReasonCodeError):
        services.overrides.reclassify(band="LOW", reason_code="NOPE", comment=None, **base)
    with pytest.raises(ValidationError):
        services.overrides.reclassify(
            band="LOW", reason_code="SCORING_ERROR", comment="x" * 501, **base
        )
    with pytest.raises(NotFoundError):
        services.overrides.reclassify(
            case_id="nope", band="LOW", reason_code="SCORING_ERROR", comment=None, **ACTOR
        )
    assert rows(engine, "SELECT COUNT(*) FROM audit_log WHERE event='RISK_RECLASSIFIED'")[0][0] == 0


@pytest.mark.nfr("NFR-08")
def test_nfr08_a_refused_reclassify_rolls_back_its_audit_row(
    client: TestClient, services: Services, engine: Engine
) -> None:
    """A reclassify on an APPROVED case raises CaseLockedError and leaves no audit row."""
    lead = case_in(client, "CLEAN")
    with pytest.raises(CaseLockedError):
        services.overrides.reclassify(
            case_id=lead["case_id"], band="HIGH", reason_code="SCORING_ERROR", comment=None, **ACTOR
        )
    assert rows(engine, "SELECT COUNT(*) FROM audit_log WHERE event='RISK_RECLASSIFIED'")[0][0] == 0
    assert rows(engine, "SELECT COUNT(*) FROM risk_assessments")[0][0] == 1


def snapshot(engine: Engine, case_id: str) -> dict[str, Any]:
    tables = ("documents", "state_history", "risk_assessments", "screening_results",
              "decisions", "overrides", "accounts", "audit_log", "notifications")  # fmt: skip
    counts = {
        t: rows(engine, f"SELECT COUNT(*) FROM {t} WHERE case_id=:c", c=case_id)[0][0]
        for t in tables
    }
    state = rows(engine, "SELECT state, updated_at FROM cases WHERE case_id=:c", c=case_id)[0]
    return {**counts, "state": tuple(state)}


@pytest.mark.nfr("NFR-08")
@pytest.mark.ac("AC-07")
@pytest.mark.parametrize("kind", ["CLEAN", "AML"])
def test_nfr08_a_closed_case_cannot_be_modified_through_any_service_entry_point(
    client: TestClient,
    services: Services,
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    kind: str,
) -> None:
    """E5-S5 AC2: upload, profile, screen, classify, transition, override, reclassify all refuse."""
    from datetime import date

    lead = case_in(client, kind) if kind == "CLEAN" else case_in_review(client, kind)
    cid = lead["case_id"]
    if kind == "AML":
        closed = services.overrides.override(
            case_id=cid, decision="REJECT", reason_code="POLICY_OTHER", comment=None, **ACTOR
        )
        assert closed.state == "REJECTED"
    before = snapshot(engine, cid)
    attempts = [
        lambda: services.documents.upload(
            case_id=cid, actor="p", checklist_item="ID_PROOF", filename="pan_2.pdf",
            content_type="application/pdf", content=PDF_BYTES,
        ),
        lambda: services.leads.update_profile(
            case_id=cid, date_of_birth=date(1990, 1, 1), annual_income=1,
            occupation_category="SALARIED", country_code="IN", state_code="MH", actor="p",
        ),
        lambda: services.screening.screen(case_id=cid, actor="a", role="admin"),
        lambda: services.risk.classify(case_id=cid, actor="a", role="admin"),
        lambda: services.overrides.override(
            case_id=cid, decision="APPROVE", reason_code="RISK_ACCEPTED", comment=None, **ACTOR
        ),
        lambda: services.overrides.reclassify(
            case_id=cid, band="HIGH", reason_code="SCORING_ERROR", comment=None, **ACTOR
        ),
        lambda: services.onboarding.transition_and_commit(
            uow_factory, case_id=cid, to_state=CaseState.MANUAL_REVIEW, actor="a", role="admin"
        ),
    ]  # fmt: skip
    for attempt in attempts:
        with pytest.raises((CaseLockedError, InvalidOnboardingStateException)):
            attempt()
    assert snapshot(engine, cid) == before


@pytest.mark.nfr("NFR-08")
def test_nfr08_decide_on_an_approved_case_returns_the_original_without_new_rows(
    client: TestClient, services: Services, engine: Engine
) -> None:
    """AC-07.4: a repeated decide is a read; nothing is written."""
    lead = case_in(client, "CLEAN")
    before = snapshot(engine, lead["case_id"])
    result = services.decisions.decide(case_id=lead["case_id"], actor="a", role="admin")
    assert result.decision.reason_code == "AUTO_APPROVED"
    assert snapshot(engine, lead["case_id"]) == before


@pytest.mark.nfr("NFR-08")
def test_nfr08_direct_database_update_of_a_closed_case_is_refused(
    client: TestClient, engine: Engine
) -> None:
    """NFR-08: the locked-case trigger refuses an UPDATE even from raw SQL."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    lead = case_in(client, "CLEAN")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET state='REJECTED' WHERE case_id=:c"), {"c": lead["case_id"]}
        )


@pytest.mark.ac("AC-08")
def test_ac08_service_override_validates_direction_reasons_and_state(
    client: TestClient, services: Services
) -> None:
    """Service-level: wrong-direction reason, bad decision, long comment, unknown case."""
    lead = case_in_review(client, "AML")
    base: dict[str, Any] = {"case_id": lead["case_id"], "comment": None, **ACTOR}
    with pytest.raises(UnknownReasonCodeError):
        services.overrides.override(decision="APPROVE", reason_code="RISK_TOO_HIGH", **base)
    with pytest.raises(ValidationError):
        services.overrides.override(decision="HOLD", reason_code="RISK_TOO_HIGH", **base)
    with pytest.raises(ValidationError):
        services.overrides.override(
            decision="APPROVE", reason_code="RISK_ACCEPTED", **{**base, "comment": "y" * 501}
        )
    with pytest.raises(NotFoundError):
        services.overrides.override(
            decision="APPROVE", reason_code="RISK_ACCEPTED", **{**base, "case_id": "nope"}
        )
    assert isinstance(DomainError("x"), Exception)


@pytest.mark.ac("AC-08")
def test_ac08_service_queue_age_uses_the_injected_clock(
    client: TestClient, services: Services, clock: FakeClock
) -> None:
    """AC-08.1: age_minutes is whole minutes since entering MANUAL_REVIEW."""
    case_in_review(client, "AML")
    clock.advance(59)
    assert services.overrides.review_queue()[0].age_minutes == 0
    clock.advance(1)
    assert services.overrides.review_queue()[0].age_minutes == 1
    clock.advance(3600 * 5)
    assert services.overrides.review_queue()[0].age_minutes == 301


@pytest.mark.ac("AC-07")
def test_ac07_override_approve_calls_account_creation_exactly_once(
    client: TestClient, services: Services, engine: Engine
) -> None:
    """AC-07.11: one account row and one ACCOUNT_CREATED audit per approved case."""
    lead = case_in_review(client, "AML")
    services.overrides.override(
        case_id=lead["case_id"],
        decision="APPROVE",
        reason_code="RISK_ACCEPTED",
        comment=None,
        **ACTOR,
    )
    accounts = rows(engine, "SELECT COUNT(*) FROM accounts WHERE case_id=:c", c=lead["case_id"])
    audits = rows(
        engine, "SELECT COUNT(*) FROM audit_log WHERE event='ACCOUNT_CREATED' AND case_id=:c",
        c=lead["case_id"],
    )  # fmt: skip
    assert accounts[0][0] == 1 and audits[0][0] == 1


@pytest.mark.ac("AC-07")
def test_ac07_account_lookup_service_paths(client: TestClient, services: Services) -> None:
    """EvidenceService.get_account: NotFound for unknown case and for an unapproved case."""
    lead = case_in_review(client, "AML")
    with pytest.raises(NotFoundError):
        services.evidence.get_account("nope")
    with pytest.raises(NotFoundError):
        services.evidence.get_account(lead["case_id"])
    done = case_in(client, "CLEAN")
    assert services.evidence.get_account(done["case_id"]).account_number.startswith("SAV")
