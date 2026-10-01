"""Builds PII-free audit entries and appends them through the unit of work (NFR-02, NFR-03)."""

import uuid
from typing import Any

from onboardx.config.logging_setup import get_correlation_id
from onboardx.config.redaction import PII_KEYS
from onboardx.domain.entities import AuditEntry
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.repositories.unit_of_work import UnitOfWork


class AuditService:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def record(
        self,
        uow: UnitOfWork,
        *,
        event: str,
        actor: str,
        role: str,
        case_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Append one audit row in the caller's transaction; PII keys are refused."""
        body = payload or {}
        forbidden = sorted(key for key in body if key.lower() in PII_KEYS)
        if forbidden:
            raise ValueError(f"audit payload must be PII-free; offending keys: {forbidden}")
        entry = AuditEntry(
            audit_id=str(uuid.uuid4()),
            case_id=case_id,
            event=event,
            actor=actor,
            role=role,
            payload=body,
            correlation_id=get_correlation_id() or "none",
            created_at=to_iso_z(self._clock.now()),
        )
        uow.audit.add(entry)
        return entry
