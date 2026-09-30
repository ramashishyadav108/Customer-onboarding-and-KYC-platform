"""The single state-transition function (AC-04, NFR-02, NFR-08).

Every case state change goes through ``OnboardingService.transition``: validate against the
frozen lifecycle table, update the case, append a state-history row and an audit row in the
caller's transaction, call the observer hook, and record the idempotency key. The caller
commits; any exception before commit rolls everything back.
"""

import hashlib
import uuid
from typing import Any

from onboardx.domain.entities import StateHistoryEntry, TransitionResult
from onboardx.domain.enums import AuditEvent, CaseState
from onboardx.domain.errors import NotFoundError
from onboardx.domain.lifecycle import assert_transition
from onboardx.domain.ports import Clock, TransitionObserver
from onboardx.domain.timeutil import to_iso_z
from onboardx.repositories.idempotency_repository import IdempotencyRecord
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService


def _scope(case_id: str, to_state: CaseState) -> str:
    return f"transition:{case_id}:{to_state}"


def _result_to_json(result: TransitionResult) -> dict[str, Any]:
    return {
        "case_id": result.case_id,
        "from_state": None if result.from_state is None else str(result.from_state),
        "to_state": str(result.to_state),
        "history_id": result.history_id,
        "created_at": result.created_at,
    }


def _result_from_json(data: dict[str, Any]) -> TransitionResult:
    return TransitionResult(
        case_id=data["case_id"],
        from_state=None if data["from_state"] is None else CaseState(data["from_state"]),
        to_state=CaseState(data["to_state"]),
        history_id=data["history_id"],
        created_at=data["created_at"],
        replayed=True,
    )


class OnboardingService:
    def __init__(
        self, clock: Clock, audit: AuditService, observer: TransitionObserver | None = None
    ) -> None:
        self._clock = clock
        self._audit = audit
        self._observer = observer

    def start_case(self, uow: UnitOfWork, *, case_id: str, actor: str, role: str) -> None:
        """Append the initial INITIATED history row (from_state null) for a new case."""
        now = to_iso_z(self._clock.now())
        entry = StateHistoryEntry(
            str(uuid.uuid4()), case_id, None, CaseState.INITIATED, actor, None, None, now
        )
        uow.state_history.add(entry)
        if self._observer is not None:
            self._observer.on_transition(case_id, None, CaseState.INITIATED)

    def transition(
        self,
        uow: UnitOfWork,
        *,
        case_id: str,
        to_state: CaseState,
        actor: str,
        role: str,
        reason_code: str | None = None,
        idempotency_key: str | None = None,
    ) -> TransitionResult:
        """Move a case to ``to_state`` or raise InvalidOnboardingStateException."""
        replay = self._replay(uow, case_id, to_state, idempotency_key)
        if replay is not None:
            return replay
        case = uow.cases.get(case_id)
        if case is None:
            raise NotFoundError("case")
        assert_transition(case_id, case.state, to_state)
        now = to_iso_z(self._clock.now())
        uow.cases.update_state(case_id, to_state, now)
        history = StateHistoryEntry(
            str(uuid.uuid4()),
            case_id,
            case.state,
            to_state,
            actor,
            reason_code,
            idempotency_key,
            now,
        )
        uow.state_history.add(history)
        self._audit.record(
            uow,
            event=AuditEvent.STATE_TRANSITION,
            actor=actor,
            role=role,
            case_id=case_id,
            payload={
                "from_state": str(case.state),
                "to_state": str(to_state),
                "reason_code": reason_code,
            },
        )
        if self._observer is not None:
            self._observer.on_transition(case_id, case.state, to_state)
        result = TransitionResult(case_id, case.state, to_state, history.history_id, now)
        self._remember(uow, idempotency_key, result, now)
        return result

    def transition_and_commit(
        self, uow_factory: UnitOfWorkFactory, **kwargs: Any
    ) -> TransitionResult:
        """Convenience for callers with no surrounding transaction."""
        with uow_factory() as uow:
            result = self.transition(uow, **kwargs)
            uow.commit()
        return result

    def _replay(
        self, uow: UnitOfWork, case_id: str, to_state: CaseState, key: str | None
    ) -> TransitionResult | None:
        if key is None:
            return None
        record = uow.idempotency.get(_scope(case_id, to_state), key)
        return None if record is None else _result_from_json(record.response)

    def _remember(
        self, uow: UnitOfWork, key: str | None, result: TransitionResult, now: str
    ) -> None:
        if key is None:
            return
        digest = hashlib.sha256(f"{result.case_id}|{result.to_state}".encode()).hexdigest()
        uow.idempotency.add(
            IdempotencyRecord(
                _scope(result.case_id, result.to_state), key, digest, _result_to_json(result), now
            )
        )
