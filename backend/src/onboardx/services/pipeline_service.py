"""Pipeline orchestration (AC-07.5): runs screen, classify, decide through the step services.

Each step commits on its own, so a mid-way failure leaves the case at the last good state and a
retry resumes. The loop re-reads the state before every step, which makes it idempotent and
race-safe: a competing advance that wins a step is simply observed on the next read.
"""

import logging

from onboardx.domain.entities import Decision
from onboardx.domain.enums import CaseState
from onboardx.domain.errors import (
    ConcurrentUpdateError,
    InvalidOnboardingStateException,
    NotFoundError,
)
from onboardx.domain.views import AdvanceResult
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.decision_service import DecisionService
from onboardx.services.risk_service import RiskService
from onboardx.services.screening_service import ScreeningService

logger = logging.getLogger("onboardx.pipeline")
STEP_BY_STATE = {
    CaseState.DOCS_SUBMITTED: "screen",
    CaseState.SCREENED: "classify",
    CaseState.CLASSIFIED: "decide",
}
MAX_CONFLICTS = 5


class PipelineService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        screening: ScreeningService,
        risk: RiskService,
        decisions: DecisionService,
    ) -> None:
        self._uow_factory = uow_factory
        self._screening = screening
        self._risk = risk
        self._decisions = decisions

    def advance(self, *, case_id: str, actor: str, role: str) -> AdvanceResult:
        """Run every pending step of a submitted case; INITIATED cases are refused (409)."""
        if self._state(case_id) is CaseState.INITIATED:
            raise InvalidOnboardingStateException(
                case_id, CaseState.INITIATED, CaseState.DOCS_SUBMITTED
            )
        steps: list[str] = []
        conflicts = 0
        while (step := STEP_BY_STATE.get(self._state(case_id))) is not None:
            try:
                self._run(step, case_id, actor, role)
                steps.append(step)
            except (ConcurrentUpdateError, InvalidOnboardingStateException):
                conflicts += 1
                if conflicts > MAX_CONFLICTS:
                    raise
        state, decision = self._final(case_id)
        logger.info("pipeline advanced", extra={"case_id": case_id, "steps": ",".join(steps)})
        return AdvanceResult(case_id, str(state), tuple(steps), decision)

    def _run(self, step: str, case_id: str, actor: str, role: str) -> None:
        if step == "screen":
            self._screening.screen(case_id=case_id, actor=actor, role=role)
        elif step == "classify":
            self._risk.classify(case_id=case_id, actor=actor, role=role)
        else:
            self._decisions.decide(case_id=case_id, actor=actor, role=role)

    def _state(self, case_id: str) -> CaseState:
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            return case.state

    def _final(self, case_id: str) -> tuple[CaseState, Decision | None]:
        with self._uow_factory() as uow:
            case = uow.cases.get(case_id)
            if case is None:
                raise NotFoundError("case")
            return case.state, uow.decisions.get_for_case(case_id)
