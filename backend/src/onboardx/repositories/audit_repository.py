"""Audit log: append-only. Exposes add() and reads only (NFR-02)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from onboardx.domain.entities import AuditEntry
from onboardx.repositories.models.audit import AuditLogModel


def _to_entry(row: AuditLogModel) -> AuditEntry:
    return AuditEntry(
        audit_id=row.audit_id,
        case_id=row.case_id,
        event=row.event,
        actor=row.actor,
        role=row.role,
        payload=dict(row.payload),
        correlation_id=row.correlation_id,
        created_at=row.created_at,
    )


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: AuditEntry) -> None:
        self._session.add(
            AuditLogModel(
                audit_id=entry.audit_id,
                case_id=entry.case_id,
                event=entry.event,
                actor=entry.actor,
                role=entry.role,
                payload=entry.payload,
                correlation_id=entry.correlation_id,
                created_at=entry.created_at,
            )
        )
        self._session.flush()

    def list_for_case(self, case_id: str) -> list[AuditEntry]:
        query = select(AuditLogModel).where(AuditLogModel.case_id == case_id)
        rows = self._session.scalars(query.order_by(AuditLogModel.seq)).all()
        return [_to_entry(row) for row in rows]

    def list_by_event(self, event: str) -> list[AuditEntry]:
        query = select(AuditLogModel).where(AuditLogModel.event == event)
        rows = self._session.scalars(query.order_by(AuditLogModel.seq)).all()
        return [_to_entry(row) for row in rows]
