"""Compliance-officer manual review: review queue, override and reclassify (AC-08, NFR-02/08).

An override moves MANUAL_REVIEW to APPROVED or REJECTED through OnboardingService.transition
and appends one Override row plus an OVERRIDE_APPLIED audit entry in the same transaction. A
risk-band reassignment always writes its RISK_RECLASSIFIED audit entry first and is refused by
RiskService.reassign_band if that record is missing.
"""

import logging
import uuid

from onboardx.domain.entities import Override, RiskAssessment
from onboardx.domain.enums import (
    OVERRIDE_REASONS_BY_DECISION,
    AuditEvent,
    CaseState,
    OverrideDecision,
    ReclassifyReason,
    RiskBand,
)
from onboardx.domain.errors import (
    InvalidOnboardingStateException,
    NotFoundError,
    UnknownReasonCodeError,
    ValidationError,
)
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import parse_iso, to_iso_z
from onboardx.domain.views import OverrideResult, ReviewQueueItem
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.account_service import AccountService
from onboardx.services.audit_service import AuditService
from onboardx.services.onboarding_service import OnboardingService
from onboardx.services.risk_service import RiskService

logger = logging.getLogger("onboardx.override")
MAX_COMMENT = 500
SECONDS_PER_MINUTE = 60
_OUTCOME = {
    OverrideDecision.APPROVE: CaseState.APPROVED,
    OverrideDecision.REJECT: CaseState.REJECTED,
}


def _decision(value: str) -> OverrideDecision:
    try:
        return OverrideDecision(value)
    except ValueError:
        raise ValidationError.single("decision", "must be APPROVE or REJECT") from None


def _check_comment(comment: str | None) -> str | None:
    if comment is not None and len(comment) > MAX_COMMENT:
        raise ValidationError.single("comment", f"at most {MAX_COMMENT} characters")
    return comment


def _override_reason(decision: OverrideDecision, reason_code: str) -> str:
    allowed = [str(code) for code in OVERRIDE_REASONS_BY_DECISION[decision]]
    if reason_code not in allowed:
        raise UnknownReasonCodeError(allowed)
    return reason_code


def _reclassify_inputs(band: str, reason_code: str) -> tuple[RiskBand, str]:
    try:
        parsed = RiskBand(band)
    except ValueError:
        raise ValidationError.single("band", "must be LOW, MEDIUM or HIGH") from None
    allowed = [str(code) for code in ReclassifyReason]
    if reason_code not in allowed:
        raise UnknownReasonCodeError(allowed)
    return parsed, reason_code


class OverrideService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        audit: AuditService,
        onboarding: OnboardingService,
        accounts: AccountService,
        risk: RiskService,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit
        self._onboarding = onboarding
        self._accounts = accounts
        self._risk = risk

    def review_queue(
        self, *, product: str | None = None, reason_code: str | None = None
    ) -> list[ReviewQueueItem]:
        """MANUAL_REVIEW cases oldest first with reason code and age in whole minutes."""
        with self._uow_factory() as uow:
            rows = uow.review.queue(product=product, reason_code=reason_code)
        now = self._clock.now()
        return [
            ReviewQueueItem(
                case_id,
                prod,
                reason,
                int((now - parse_iso(entered)).total_seconds()) // SECONDS_PER_MINUTE,
                entered,
            )
            for case_id, prod, reason, entered in rows
        ]

    def override(
        self,
        *,
        case_id: str,
        decision: str,
        reason_code: str,
        comment: str | None,
        actor: str,
        role: str,
    ) -> OverrideResult:
        """Resolve a MANUAL_REVIEW case; 422 on bad input, 409 INVALID_STATE otherwise."""
        chosen = _decision(decision)
        reason = _override_reason(chosen, reason_code)
        note = _check_comment(comment)
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            if case.state is not CaseState.MANUAL_REVIEW:
                raise InvalidOnboardingStateException(case_id, case.state, _OUTCOME[chosen])
            override = self._append(uow, case_id, chosen, reason, note, actor)
            self._onboarding.transition(
                uow,
                case_id=case_id,
                to_state=_OUTCOME[chosen],
                actor=actor,
                role=role,
                reason_code=reason,
            )
            account = None
            if chosen is OverrideDecision.APPROVE:
                created = self._accounts.create_account(
                    uow, case_id=case_id, actor=actor, role=role
                )
                account = created.account_number
            self._audit_override(uow, override, actor, role)
            uow.commit()
        logger.info(
            "override applied",
            extra={"case_id": case_id, "decision": override.decision, "reason": reason},
        )
        return OverrideResult(case_id, str(_OUTCOME[chosen]), override, account)

    def reclassify(
        self,
        *,
        case_id: str,
        band: str,
        reason_code: str,
        comment: str | None,
        actor: str,
        role: str,
    ) -> RiskAssessment:
        """Reassign the risk band in MANUAL_REVIEW; always audited, never changes the state."""
        new_band, reason = _reclassify_inputs(band, reason_code)
        _check_comment(comment)
        with self._uow_factory() as uow:
            previous = uow.assessments.latest(case_id)
            if previous is None:
                raise NotFoundError("risk_assessment")
            entry = self._audit.record(
                uow,
                event=AuditEvent.RISK_RECLASSIFIED,
                actor=actor,
                role=role,
                case_id=case_id,
                payload={
                    "previous_band": previous.band,
                    "new_band": str(new_band),
                    "reason_code": reason,
                    "rule_version": previous.rule_version,
                    "has_comment": bool(comment),
                },
            )
            assessment = self._risk.reassign_band(uow, case_id=case_id, band=new_band, audit=entry)
            uow.commit()
        logger.info("risk band reassigned", extra={"case_id": case_id, "band": assessment.band})
        return assessment

    def _append(
        self,
        uow: UnitOfWork,
        case_id: str,
        decision: OverrideDecision,
        reason: str,
        comment: str | None,
        actor: str,
    ) -> Override:
        recorded = uow.decisions.get_for_case(case_id)
        assessment = uow.assessments.latest(case_id)
        source = recorded or assessment
        override = Override(
            str(uuid.uuid4()),
            case_id,
            actor,
            str(decision),
            reason,
            comment,
            source.rule_version if source else 1,
            to_iso_z(self._clock.now()),
        )
        uow.review.add_override(override)
        return override

    def _audit_override(self, uow: UnitOfWork, override: Override, actor: str, role: str) -> None:
        self._audit.record(
            uow,
            event=AuditEvent.OVERRIDE_APPLIED,
            actor=actor,
            role=role,
            case_id=override.case_id,
            payload={
                "override_id": override.override_id,
                "previous_state": str(CaseState.MANUAL_REVIEW),
                "decision": override.decision,
                "reason_code": override.reason_code,
                "rule_version": override.rule_version,
                "has_comment": override.comment is not None,
            },
        )
