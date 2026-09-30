"""Decision step (AC-07): CLASSIFIED to APPROVED or MANUAL_REVIEW, exactly one decision per case.

A repeated decide returns the original decision without writing anything.
"""

import logging
import uuid

from onboardx.domain.decision import decide
from onboardx.domain.entities import Case, Decision
from onboardx.domain.enums import AuditEvent, CaseState, RiskBand
from onboardx.domain.errors import InvalidOnboardingStateException, NotFoundError
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.domain.views import DecisionResult
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.account_service import AccountService
from onboardx.services.audit_service import AuditService
from onboardx.services.onboarding_service import OnboardingService

logger = logging.getLogger("onboardx.decision")


class DecisionService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        audit: AuditService,
        onboarding: OnboardingService,
        accounts: AccountService,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit
        self._onboarding = onboarding
        self._accounts = accounts

    def decide(self, *, case_id: str, actor: str, role: str) -> DecisionResult:
        """Decide a CLASSIFIED case (idempotent: a later call returns the original decision)."""
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            existing = uow.decisions.get_for_case(case_id)
            if existing is not None:
                return self._result(uow, case, existing)
            if case.state is not CaseState.CLASSIFIED:
                raise InvalidOnboardingStateException(case_id, case.state, CaseState.APPROVED)
            decision = self._record(uow, case_id, actor, role)
            uow.commit()
            case = uow.cases.get(case_id) or case
            result = self._result(uow, case, decision)
        logger.info(
            "decision recorded",
            extra={"case_id": case_id, "outcome": decision.outcome, "reason": decision.reason_code},
        )
        return result

    def _record(self, uow: UnitOfWork, case_id: str, actor: str, role: str) -> Decision:
        assessment = uow.assessments.latest(case_id)
        if assessment is None:
            raise NotFoundError("risk_assessment")
        screening = uow.screenings.latest_result(case_id)
        statuses = [d.status for d in uow.documents.list_views(case_id)]
        outcome = decide(RiskBand(assessment.band), screening.hits if screening else (), statuses)
        decision = Decision(
            str(uuid.uuid4()),
            case_id,
            str(outcome.outcome),
            str(outcome.reason),
            assessment.rule_version,
            actor,
            to_iso_z(self._clock.now()),
        )
        uow.decisions.add(decision)
        self._onboarding.transition(
            uow,
            case_id=case_id,
            to_state=outcome.outcome,
            actor=actor,
            role=role,
            reason_code=str(outcome.reason),
        )
        if outcome.outcome is CaseState.APPROVED:
            self._accounts.create_account(uow, case_id=case_id, actor=actor, role=role)
        self._audit.record(
            uow,
            event=AuditEvent.DECISION_RECORDED,
            actor=actor,
            role=role,
            case_id=case_id,
            payload={
                "decision_id": decision.decision_id,
                "outcome": decision.outcome,
                "reason_code": decision.reason_code,
                "rule_version": decision.rule_version,
            },
        )
        return decision

    def _result(self, uow: UnitOfWork, case: Case, decision: Decision) -> DecisionResult:
        account = uow.accounts.get_for_case(case.case_id)
        return DecisionResult(
            case.case_id,
            str(case.state),
            decision,
            None if account is None else account.account_number,
        )
