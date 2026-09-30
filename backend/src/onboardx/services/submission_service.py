"""Case submission (AC-02.6-9): INITIATED to DOCS_SUBMITTED once documents and profile are in.

With AUTO_ADVANCE_ON_SUBMIT (DD-13) the pipeline then runs synchronously. A pipeline failure
after a committed submit is logged and never fails the submit; staff can advance later.
"""

import logging

from onboardx.domain.documents import blocking_items, build_item_views
from onboardx.domain.enums import AuditEvent, CaseState, Role
from onboardx.domain.errors import (
    ConcurrentUpdateError,
    DomainError,
    InvalidOnboardingStateException,
    MissingDocumentsError,
    MissingProfileError,
    NotFoundError,
)
from onboardx.domain.views import SubmitResult
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.onboarding_service import OnboardingService
from onboardx.services.pipeline_service import PipelineService

logger = logging.getLogger("onboardx.submission")
SYSTEM_ACTOR = "system"
PROFILE_FIELDS = ("date_of_birth", "annual_income", "occupation_category", "country_code")


class SubmissionService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        audit: AuditService,
        onboarding: OnboardingService,
        pipeline: PipelineService,
        *,
        auto_advance: bool,
    ) -> None:
        self._uow_factory = uow_factory
        self._audit = audit
        self._onboarding = onboarding
        self._pipeline = pipeline
        self._auto_advance = auto_advance

    def submit(self, *, case_id: str, actor: str) -> SubmitResult:
        """Submit a case. The result always reports the submit step (DOCS_SUBMITTED, per the
        contract); the state reached by auto-advance is read from the case itself."""
        try:
            self._submit_once(case_id, actor)
        except ConcurrentUpdateError:
            self._submit_once(case_id, actor)
        if self._auto_advance:
            self._advance(case_id)
        return SubmitResult(case_id, str(CaseState.DOCS_SUBMITTED), ())

    def _submit_once(self, case_id: str, actor: str) -> None:
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            if case.state is CaseState.DOCS_SUBMITTED:
                return
            if case.state is not CaseState.INITIATED:
                raise InvalidOnboardingStateException(case_id, case.state, CaseState.DOCS_SUBMITTED)
            document_ids = self._check_complete(uow, case_id)
            self._onboarding.transition(
                uow,
                case_id=case_id,
                to_state=CaseState.DOCS_SUBMITTED,
                actor=actor,
                role=str(Role.PROSPECT),
            )
            self._audit.record(
                uow,
                event=AuditEvent.DOCUMENTS_SUBMITTED,
                actor=actor,
                role=str(Role.PROSPECT),
                case_id=case_id,
                payload={"document_ids": document_ids},
            )
            uow.commit()

    def _check_complete(self, uow: UnitOfWork, case_id: str) -> list[str]:
        case = uow.cases.get(case_id)
        checklist = (
            None if case is None else uow.checklists.get(case.product, case.checklist_version)
        )
        if checklist is None:
            raise NotFoundError("checklist")
        current = uow.documents.list_views(case_id)
        missing = blocking_items(build_item_views(checklist, current))
        if missing:
            raise MissingDocumentsError(missing)
        if uow.profiles.get(case_id) is None:
            raise MissingProfileError(list(PROFILE_FIELDS))
        return [d.document_id for d in current]

    def _advance(self, case_id: str) -> None:
        try:
            self._pipeline.advance(case_id=case_id, actor=SYSTEM_ACTOR, role=SYSTEM_ACTOR)
        except DomainError as error:
            logger.error(
                "auto-advance failed", extra={"case_id": case_id, "error_code": error.code}
            )
