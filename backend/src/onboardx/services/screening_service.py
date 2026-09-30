"""AML/PEP screening step: DOCS_SUBMITTED to SCREENED (AC-05, NFR-02).

A hit is recorded and the case continues; the decision step routes it to MANUAL_REVIEW. Logs
carry case_id and hit count only, never the applicant name (AC-05.10).
"""

import logging
import uuid

from onboardx.domain.entities import ScreeningResult
from onboardx.domain.enums import AuditEvent, CaseState
from onboardx.domain.errors import InvalidOnboardingStateException, NotFoundError
from onboardx.domain.ports import Clock
from onboardx.domain.screening import screen_name
from onboardx.domain.timeutil import to_iso_z
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.onboarding_service import OnboardingService

logger = logging.getLogger("onboardx.screening")
SCREENABLE = frozenset({CaseState.DOCS_SUBMITTED, CaseState.SCREENED})


class ScreeningService:
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

    def screen(self, *, case_id: str, actor: str, role: str) -> ScreeningResult:
        """Screen a DOCS_SUBMITTED case; a repeat on SCREENED with an unchanged watchlist
        version returns the existing result, a changed version appends a new row."""
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            if case.state not in SCREENABLE:
                raise InvalidOnboardingStateException(case_id, case.state, CaseState.SCREENED)
            version = uow.screenings.watchlist_version()
            latest = uow.screenings.latest_result(case_id)
            if case.state is CaseState.SCREENED and latest and latest.watchlist_version == version:
                return latest
            result = self._append_result(uow, case_id, case.name, version)
            if case.state is CaseState.DOCS_SUBMITTED:
                self._onboarding.transition(
                    uow,
                    case_id=case_id,
                    to_state=CaseState.SCREENED,
                    actor=actor,
                    role=role,
                    reason_code=result.hits[0]["reason_code"] if result.hits else None,
                )
            self._audit.record(
                uow,
                event=AuditEvent.CASE_SCREENED,
                actor=actor,
                role=role,
                case_id=case_id,
                payload={
                    "result_id": result.result_id,
                    "hit_count": len(result.hits),
                    "watchlist_version": version,
                },
            )
            uow.commit()
        logger.info("case screened", extra={"case_id": case_id, "hit_count": len(result.hits)})
        return result

    def _append_result(
        self, uow: UnitOfWork, case_id: str, name: str, version: int
    ) -> ScreeningResult:
        outcome = screen_name(name, uow.screenings.active_entries())
        result = ScreeningResult(
            str(uuid.uuid4()),
            case_id,
            outcome.hits,
            outcome.requires_manual_review,
            version,
            to_iso_z(self._clock.now()),
        )
        uow.screenings.add_result(result)
        return result
