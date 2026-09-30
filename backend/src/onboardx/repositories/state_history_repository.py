"""State history: append-only. Exposes add() and reads only (NFR-02)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from onboardx.domain.entities import StateHistoryEntry
from onboardx.domain.enums import CaseState
from onboardx.repositories._errors import flush_unique
from onboardx.repositories.models.cases import StateHistoryModel


def _to_entry(row: StateHistoryModel) -> StateHistoryEntry:
    return StateHistoryEntry(
        history_id=row.history_id,
        case_id=row.case_id,
        from_state=None if row.from_state is None else CaseState(row.from_state),
        to_state=CaseState(row.to_state),
        actor=row.actor,
        reason_code=row.reason_code,
        idempotency_key=row.idempotency_key,
        created_at=row.created_at,
    )


class StateHistoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: StateHistoryEntry) -> None:
        self._session.add(
            StateHistoryModel(
                history_id=entry.history_id,
                case_id=entry.case_id,
                from_state=None if entry.from_state is None else str(entry.from_state),
                to_state=str(entry.to_state),
                actor=entry.actor,
                reason_code=entry.reason_code,
                idempotency_key=entry.idempotency_key,
                created_at=entry.created_at,
            )
        )
        flush_unique(self._session)

    def list_for_case(self, case_id: str) -> list[StateHistoryEntry]:
        rows = self._session.scalars(
            select(StateHistoryModel)
            .where(StateHistoryModel.case_id == case_id)
            .order_by(StateHistoryModel.seq)
        ).all()
        return [_to_entry(row) for row in rows]
