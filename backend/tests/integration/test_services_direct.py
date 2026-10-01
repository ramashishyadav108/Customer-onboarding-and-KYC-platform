"""Service-level checks that are awkward over HTTP: account stub, profile inputs, settings."""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

from api_helpers import create_lead
from helpers import insert_case
from onboardx.config.settings import Settings
from onboardx.controllers.dependencies.services import Services
from onboardx.domain.entities import CaseProfile
from onboardx.domain.errors import InvalidOnboardingStateException, MissingProfileFieldError
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.risk_service import inputs_from_profile
from pipeline_helpers import PDF_BYTES, rows


def case_in_state(engine: Any, state: str) -> str:
    with engine.begin() as conn:
        return insert_case(conn, state=state)


@pytest.mark.ac("AC-07")
def test_ac07_7_account_creation_on_a_non_approved_case_raises_and_writes_nothing(
    services: Services, uow_factory: UnitOfWorkFactory, engine: Any
) -> None:
    case_id = case_in_state(engine, "CLASSIFIED")
    from onboardx.services.account_service import AccountService
    from onboardx.services.audit_service import AuditService

    clock = services.onboarding._clock  # noqa: SLF001 - reuse the fake clock
    accounts = AccountService(clock, AuditService(clock))
    with uow_factory() as uow, pytest.raises(InvalidOnboardingStateException):
        accounts.create_account(uow, case_id=case_id, actor="t", role="admin")
    assert rows(engine, "SELECT COUNT(*) FROM accounts")[0][0] == 0


@pytest.mark.ac("AC-07")
def test_ac07_8_creating_an_account_twice_returns_the_same_number_and_one_row(
    services: Services, uow_factory: UnitOfWorkFactory, engine: Any
) -> None:
    case_id = case_in_state(engine, "APPROVED")
    from onboardx.services.account_service import AccountService
    from onboardx.services.audit_service import AuditService

    clock = services.onboarding._clock  # noqa: SLF001
    accounts = AccountService(clock, AuditService(clock))
    with uow_factory() as uow:
        first = accounts.create_account(uow, case_id=case_id, actor="t", role="admin")
        again = accounts.create_account(uow, case_id=case_id, actor="t", role="admin")
        uow.commit()
    assert first.account_number == again.account_number
    assert rows(engine, "SELECT COUNT(*) FROM accounts")[0][0] == 1
    assert rows(engine, "SELECT COUNT(*) FROM audit_log WHERE event='ACCOUNT_CREATED'")[0][0] == 1


@pytest.mark.ac("AC-07")
def test_ac07_account_creation_for_an_unknown_case_is_not_found(
    services: Services, uow_factory: UnitOfWorkFactory
) -> None:
    from onboardx.domain.errors import NotFoundError
    from onboardx.services.account_service import AccountService
    from onboardx.services.audit_service import AuditService

    clock = services.onboarding._clock  # noqa: SLF001
    with uow_factory() as uow, pytest.raises(NotFoundError):
        AccountService(clock, AuditService(clock)).create_account(
            uow, case_id="nope", actor="t", role="admin"
        )


PROFILE = CaseProfile("c", __import__("datetime").date(1990, 1, 1), 1, "SALARIED", "IN", "MH", "t")


@pytest.mark.ac("AC-06")
def test_ac06_10_inputs_from_a_complete_profile() -> None:
    inputs = inputs_from_profile(PROFILE)
    assert (inputs.annual_income, inputs.country_code, inputs.state_code) == (1, "IN", "MH")


@pytest.mark.ac("AC-06")
def test_ac06_10_absent_profile_names_the_first_field() -> None:
    with pytest.raises(MissingProfileFieldError) as excinfo:
        inputs_from_profile(None)
    assert excinfo.value.details == {"field": "date_of_birth"}


@pytest.mark.ac("AC-06")
def test_ac06_10_home_country_without_state_names_state_code() -> None:
    incomplete = CaseProfile("c", PROFILE.date_of_birth, 1, "SALARIED", "IN", None, "t")
    with pytest.raises(MissingProfileFieldError) as excinfo:
        inputs_from_profile(incomplete)
    assert excinfo.value.field == "state_code"


@pytest.mark.ac("AC-06")
def test_ac06_10_foreign_profile_needs_no_state() -> None:
    foreign = CaseProfile("c", PROFILE.date_of_birth, 1, "SALARIED", "GB", None, "t")
    assert inputs_from_profile(foreign).state_code is None


@pytest.mark.ac("AC-07")
def test_ac07_decide_without_an_assessment_reports_not_found(
    services: Services, engine: Any
) -> None:
    """A CLASSIFIED case that somehow has no assessment cannot be decided."""
    from onboardx.domain.errors import NotFoundError

    case_id = case_in_state(engine, "CLASSIFIED")
    with pytest.raises(NotFoundError):
        services.decisions.decide(case_id=case_id, actor="t", role="admin")


@pytest.mark.ac("AC-06")
def test_ac06_classify_unknown_case_is_not_found(services: Services) -> None:
    from onboardx.domain.errors import NotFoundError

    for call in (services.risk.classify, services.screening.screen, services.decisions.decide):
        with pytest.raises(NotFoundError):
            call(case_id="missing", actor="t", role="admin")
    with pytest.raises(NotFoundError):
        services.submission.submit(case_id="missing", actor="t")
    with pytest.raises(NotFoundError):
        services.notifications.list_for_case("missing")


@pytest.mark.ac("AC-07")
def test_ac07_pipeline_reports_failures_of_a_persistently_conflicting_step(
    services: Services, monkeypatch: pytest.MonkeyPatch, client: Any
) -> None:
    """After MAX_CONFLICTS conflicts the pipeline surfaces the error instead of spinning."""
    from onboardx.domain.errors import ConcurrentUpdateError
    from pipeline_helpers import submitted_case

    lead = submitted_case(client)

    def always_conflict(**_kwargs: Any) -> None:
        raise ConcurrentUpdateError

    monkeypatch.setattr(services.screening, "screen", always_conflict)
    with pytest.raises(ConcurrentUpdateError):
        services.pipeline.advance(case_id=lead["case_id"], actor="t", role="admin")


@pytest.mark.ac("AC-02")
def test_ac02_upload_retries_then_gives_up_on_persistent_conflicts(
    services: Services, monkeypatch: pytest.MonkeyPatch, client: Any
) -> None:
    from onboardx.domain.errors import ConcurrentUpdateError

    lead = create_lead(client)
    calls: list[int] = []

    def conflict(*_args: Any) -> None:
        calls.append(1)
        raise ConcurrentUpdateError

    monkeypatch.setattr(services.documents, "_upload_once", conflict)
    with pytest.raises(ConcurrentUpdateError):
        services.documents.upload(
            case_id=lead["case_id"],
            actor="t",
            checklist_item="ID_PROOF",
            filename="pan_1.pdf",
            content_type="application/pdf",
            content=PDF_BYTES,
        )
    assert len(calls) == 3


@pytest.mark.ac("AC-02")
def test_ac02_failed_commit_removes_the_stored_file(
    services: Services, monkeypatch: pytest.MonkeyPatch, client: Any, upload_dir: Path
) -> None:
    """If the transaction fails after the file was written, the orphan file is deleted."""
    lead = create_lead(client)

    def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(services.documents, "_record", boom)
    with pytest.raises(RuntimeError):
        services.documents.upload(
            case_id=lead["case_id"],
            actor="t",
            checklist_item="ID_PROOF",
            filename="pan_1.pdf",
            content_type="application/pdf",
            content=PDF_BYTES,
        )
    assert [p for p in upload_dir.rglob("*") if p.is_file()] == []


@pytest.mark.nfr("NFR-05")
def test_nfr05_no_schema_change_was_needed_for_the_pipeline(engine: Any) -> None:
    """Migrations 0001-0007 already carry every pipeline table; none were added."""
    with engine.connect() as conn:
        versions = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert versions == "0007"


@pytest.mark.ac("AC-02")
def test_ac02_settings_defaults_match_the_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    """DD-13: auto-advance defaults to on; UPLOAD_DIR defaults to ../uploads."""
    monkeypatch.delenv("UPLOAD_DIR", raising=False)
    monkeypatch.delenv("AUTO_ADVANCE_ON_SUBMIT", raising=False)
    defaults = Settings(_env_file=None, database_url="sqlite://")  # type: ignore[call-arg]
    assert defaults.auto_advance_on_submit is True
    assert defaults.upload_dir == Path("../uploads")


@pytest.mark.ac("AC-02")
def test_ac02_settings_read_upload_dir_and_auto_advance_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_DIR", "custom/dir")
    monkeypatch.setenv("AUTO_ADVANCE_ON_SUBMIT", "false")
    configured = Settings(_env_file=None, database_url="sqlite://")  # type: ignore[call-arg]
    assert configured.upload_dir == Path("custom/dir")
    assert configured.auto_advance_on_submit is False
