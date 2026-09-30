"""AC-04 / NFR-02 / NFR-08 / E1-S4: transition service, audit, atomicity, idempotency."""

import pytest
from sqlalchemy import Engine

from helpers import FakeClock, insert_case
from onboardx.controllers.dependencies.services import Services
from onboardx.domain.enums import CaseState
from onboardx.domain.errors import CaseLockedError, InvalidOnboardingStateException, NotFoundError
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.onboarding_service import OnboardingService

S = CaseState
PIPELINE = [S.DOCS_SUBMITTED, S.SCREENED, S.CLASSIFIED, S.APPROVED]


def new_case(services: Services) -> str:
    return services.leads.register(
        name="Test Person Alpha", contact="9999999921", product="Savings"
    ).case_id


def move(
    services: Services, uow_factory: UnitOfWorkFactory, case_id: str, to: CaseState, **kw: object
):  # type: ignore[no-untyped-def]
    return services.onboarding.transition_and_commit(
        uow_factory, case_id=case_id, to_state=to, actor="analyst1", role="kyc-analyst", **kw
    )


def history(uow_factory: UnitOfWorkFactory, case_id: str) -> list[tuple[str | None, str]]:
    with uow_factory() as uow:
        return [
            (None if h.from_state is None else str(h.from_state), str(h.to_state))
            for h in uow.state_history.list_for_case(case_id)
        ]


def state_of(uow_factory: UnitOfWorkFactory, case_id: str) -> CaseState:
    with uow_factory() as uow:
        case = uow.cases.get(case_id)
        assert case is not None
        return case.state


@pytest.mark.ac("AC-04")
def test_ac04_happy_path_appends_history_and_audit_for_every_step(
    services: Services, uow_factory: UnitOfWorkFactory
) -> None:
    """AC-04 / E1-S4 AC3: each transition appends a history row and a STATE_TRANSITION audit row."""
    case_id = new_case(services)
    for target in PIPELINE:
        result = move(services, uow_factory, case_id, target, reason_code="TEST")
        assert result.to_state is target and not result.replayed
    assert history(uow_factory, case_id) == [
        (None, "INITIATED"),
        ("INITIATED", "DOCS_SUBMITTED"),
        ("DOCS_SUBMITTED", "SCREENED"),
        ("SCREENED", "CLASSIFIED"),
        ("CLASSIFIED", "APPROVED"),
    ]
    with uow_factory() as uow:
        events = [a.event for a in uow.audit.list_for_case(case_id)]
        rows = uow.state_history.list_for_case(case_id)
    assert events == ["LEAD_CREATED"] + ["STATE_TRANSITION"] * 4
    assert rows[1].actor == "analyst1" and rows[1].reason_code == "TEST"
    assert rows[1].created_at.endswith("Z")


@pytest.mark.ac("AC-04")
def test_ac04_invalid_transition_raises_and_leaves_state_unchanged(
    services: Services, uow_factory: UnitOfWorkFactory
) -> None:
    """AC-04 (E1-S4 AC2): INITIATED -> APPROVED raises with case_id/from/to; nothing changes."""
    case_id = new_case(services)
    with pytest.raises(InvalidOnboardingStateException) as info:
        move(services, uow_factory, case_id, S.APPROVED)
    assert (info.value.case_id, info.value.from_state, info.value.to_state) == (
        case_id, S.INITIATED, S.APPROVED,
    )  # fmt: skip
    assert state_of(uow_factory, case_id) is S.INITIATED
    assert history(uow_factory, case_id) == [(None, "INITIATED")]


@pytest.mark.ac("AC-04")
@pytest.mark.nfr("NFR-08")
@pytest.mark.parametrize("terminal", [S.APPROVED, S.REJECTED])
@pytest.mark.parametrize("target", list(CaseState))
def test_nfr08_every_transition_out_of_a_terminal_state_raises(
    services: Services,
    uow_factory: UnitOfWorkFactory,
    engine: Engine,
    terminal: CaseState,
    target: CaseState,
) -> None:
    """E1-S4 AC4 / NFR-08: no transition leaves APPROVED or REJECTED."""
    with engine.begin() as conn:
        case_id = insert_case(conn, state=str(terminal))
    with pytest.raises(InvalidOnboardingStateException):
        move(services, uow_factory, case_id, target)
    assert state_of(uow_factory, case_id) is terminal


@pytest.mark.ac("AC-04")
def test_ac04_3_failure_after_the_update_rolls_back_state_history_and_audit(
    clock: FakeClock, services: Services, uow_factory: UnitOfWorkFactory
) -> None:
    """E1-S4 AC3: a forced failure after the state update rolls everything back."""

    class Boom(Exception):
        pass

    class FailingObserver:
        def on_transition(self, case_id: str, from_state: object, to_state: object) -> None:
            raise Boom

    case_id = new_case(services)
    failing = OnboardingService(clock, AuditService(clock), FailingObserver())
    with pytest.raises(Boom), uow_factory() as uow:
        failing.transition(uow, case_id=case_id, to_state=S.DOCS_SUBMITTED, actor="a", role="admin")
        uow.commit()
    assert state_of(uow_factory, case_id) is S.INITIATED
    assert history(uow_factory, case_id) == [(None, "INITIATED")]
    with uow_factory() as uow:
        assert [a.event for a in uow.audit.list_for_case(case_id)] == ["LEAD_CREATED"]


@pytest.mark.ac("AC-04")
def test_ac04_6_same_idempotency_key_returns_original_without_second_row(
    services: Services, uow_factory: UnitOfWorkFactory
) -> None:
    """E1-S4 AC6: repeating a transition with the same key returns the original result."""
    case_id = new_case(services)
    first = move(services, uow_factory, case_id, S.DOCS_SUBMITTED, idempotency_key="k-1")
    second = move(services, uow_factory, case_id, S.DOCS_SUBMITTED, idempotency_key="k-1")
    assert not first.replayed and second.replayed
    assert second.history_id == first.history_id
    assert history(uow_factory, case_id).count(("INITIATED", "DOCS_SUBMITTED")) == 1
    assert len(history(uow_factory, case_id)) == 2


@pytest.mark.ac("AC-04")
def test_ac04_6_replay_is_honoured_after_the_case_has_moved_on(
    services: Services, uow_factory: UnitOfWorkFactory
) -> None:
    """E1-S4 AC6: a late retry still returns the original result, not an invalid-state error."""
    case_id = new_case(services)
    first = move(services, uow_factory, case_id, S.DOCS_SUBMITTED, idempotency_key="k-2")
    move(services, uow_factory, case_id, S.SCREENED)
    again = move(services, uow_factory, case_id, S.DOCS_SUBMITTED, idempotency_key="k-2")
    assert again.replayed and again.history_id == first.history_id
    assert state_of(uow_factory, case_id) is S.SCREENED


@pytest.mark.ac("AC-04")
def test_ac04_6_repeat_without_a_key_is_an_invalid_transition(
    services: Services, uow_factory: UnitOfWorkFactory
) -> None:
    """AC-04: without a key a repeated transition is rejected, never double-applied."""
    case_id = new_case(services)
    move(services, uow_factory, case_id, S.DOCS_SUBMITTED)
    with pytest.raises(InvalidOnboardingStateException):
        move(services, uow_factory, case_id, S.DOCS_SUBMITTED)
    assert len(history(uow_factory, case_id)) == 2


@pytest.mark.ac("AC-04")
def test_ac04_unknown_case_is_not_found(services: Services, uow_factory: UnitOfWorkFactory) -> None:
    """AC-04: transitioning a case that does not exist raises NotFoundError."""
    with pytest.raises(NotFoundError):
        move(services, uow_factory, "missing-case", S.DOCS_SUBMITTED)


@pytest.mark.nfr("NFR-08")
def test_nfr08_repository_update_on_approved_case_raises_case_locked(
    services: Services, uow_factory: UnitOfWorkFactory, engine: Engine
) -> None:
    """NFR-08: even a direct repository update of an approved case raises CaseLockedError."""
    with engine.begin() as conn:
        case_id = insert_case(conn, state="APPROVED")
    with uow_factory() as uow, pytest.raises(CaseLockedError) as info:
        uow.cases.update_state(case_id, S.REJECTED, "2026-10-01T00:00:00Z")
    assert info.value.state is S.APPROVED and info.value.code == "CASE_LOCKED"


@pytest.mark.nfr("NFR-02")
@pytest.mark.nfr("NFR-03")
def test_nfr03_audit_payload_with_pii_keys_is_refused(
    clock: FakeClock, uow_factory: UnitOfWorkFactory
) -> None:
    """NFR-03: the audit service refuses payload keys that carry PII."""
    audit = AuditService(clock)
    with uow_factory() as uow:
        for key in ("contact", "annual_income", "occupation_category", "pan"):
            with pytest.raises(ValueError, match="PII-free"):
                audit.record(uow, event="X", actor="a", role="r", case_id=None, payload={key: "v"})


@pytest.mark.nfr("NFR-02")
def test_nfr02_audit_rows_carry_actor_role_correlation_and_utc_time(
    services: Services, uow_factory: UnitOfWorkFactory
) -> None:
    """NFR-02 / audit catalogue: each row has actor, role, event, payload, correlation id, UTC."""
    case_id = new_case(services)
    with uow_factory() as uow:
        (entry,) = uow.audit.list_for_case(case_id)
    assert entry.event == "LEAD_CREATED" and entry.role == "prospect"
    assert entry.actor == f"prospect:{case_id}"
    assert entry.payload == {"product": "Savings"} and entry.created_at.endswith("Z")
    assert entry.correlation_id
