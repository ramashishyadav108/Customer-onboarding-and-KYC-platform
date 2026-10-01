"""Risk classification step: SCREENED to CLASSIFIED with the latest published rule set (AC-06).

Integers only. Every evaluation appends a RiskAssessment with its rule version and breakdown.
"""

import logging
import uuid

from onboardx.domain.entities import AuditEntry, CaseProfile, RiskAssessment
from onboardx.domain.enums import AssessmentSource, AuditEvent, CaseState, RiskBand
from onboardx.domain.errors import (
    CaseLockedError,
    InvalidOnboardingStateException,
    MissingProfileFieldError,
    NotFoundError,
    OverrideAuditRequiredError,
)
from onboardx.domain.lifecycle import is_terminal
from onboardx.domain.ports import Clock
from onboardx.domain.risk import ProfileInputs, score_profile
from onboardx.domain.timeutil import to_iso_z
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.onboarding_service import OnboardingService

logger = logging.getLogger("onboardx.risk")
HOME_COUNTRY = "IN"


def inputs_from_profile(profile: CaseProfile | None) -> ProfileInputs:
    """Profile values needed by the rules; a missing one raises MissingProfileFieldError."""
    if profile is None:
        raise MissingProfileFieldError("date_of_birth")
    if profile.country_code == HOME_COUNTRY and profile.state_code is None:
        raise MissingProfileFieldError("state_code")
    return ProfileInputs(
        profile.date_of_birth,
        profile.annual_income,
        profile.occupation_category,
        profile.country_code,
        profile.state_code,
    )


class RiskService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        audit: AuditService,
        onboarding: OnboardingService,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit
        self._onboarding = onboarding

    def classify(self, *, case_id: str, actor: str, role: str) -> RiskAssessment:
        """Score a SCREENED case, append the assessment and move it to CLASSIFIED."""
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            if case.state is not CaseState.SCREENED:
                raise InvalidOnboardingStateException(case_id, case.state, CaseState.CLASSIFIED)
            inputs = inputs_from_profile(uow.profiles.get(case_id))
            rule_set = uow.rule_sets.latest_published()
            if rule_set is None:
                raise NotFoundError("rule_set")
            now = self._clock.now()
            scored = score_profile(inputs, rule_set, now.date())
            assessment = RiskAssessment(
                str(uuid.uuid4()),
                case_id,
                scored.score,
                str(scored.band),
                scored.rule_version,
                str(AssessmentSource.RULE_ENGINE),
                scored.breakdown,
                to_iso_z(now),
            )
            uow.assessments.add(assessment)
            self._onboarding.transition(
                uow, case_id=case_id, to_state=CaseState.CLASSIFIED, actor=actor, role=role
            )
            self._audit.record(
                uow,
                event=AuditEvent.CASE_CLASSIFIED,
                actor=actor,
                role=role,
                case_id=case_id,
                payload={
                    "assessment_id": assessment.assessment_id,
                    "score": assessment.score,
                    "band": assessment.band,
                    "rule_version": assessment.rule_version,
                },
            )
            uow.commit()
        logger.info("case classified", extra={"case_id": case_id, "band": assessment.band})
        return assessment

    def reassign_band(
        self, uow: UnitOfWork, *, case_id: str, band: RiskBand, audit: AuditEntry | None
    ) -> RiskAssessment:
        """Append an OFFICER_RECLASSIFY assessment (MANUAL_REVIEW only, NFR-08).

        Refused with OverrideAuditRequiredError unless ``audit`` is a RISK_RECLASSIFIED entry
        for this case that is already persisted in the same transaction.
        """
        if not _audit_present(uow, case_id, audit):
            raise OverrideAuditRequiredError(case_id)
        case = uow.cases.get(case_id)
        if case is None:
            raise NotFoundError("case")
        if is_terminal(case.state):
            raise CaseLockedError(case_id, case.state)
        if case.state is not CaseState.MANUAL_REVIEW:
            raise InvalidOnboardingStateException(case_id, case.state, CaseState.MANUAL_REVIEW)
        previous = uow.assessments.latest(case_id)
        if previous is None:
            raise NotFoundError("risk_assessment")
        assessment = RiskAssessment(
            str(uuid.uuid4()),
            case_id,
            previous.score,
            str(band),
            previous.rule_version,
            str(AssessmentSource.OFFICER_RECLASSIFY),
            previous.breakdown,
            to_iso_z(self._clock.now()),
        )
        uow.assessments.add(assessment)
        return assessment


def _audit_present(uow: UnitOfWork, case_id: str, audit: AuditEntry | None) -> bool:
    if audit is None or audit.case_id != case_id:
        return False
    if audit.event != str(AuditEvent.RISK_RECLASSIFIED):
        return False
    return any(row.audit_id == audit.audit_id for row in uow.audit.list_for_case(case_id))
