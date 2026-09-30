"""Idempotency keys: insert and lookup only (never updated)."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from onboardx.repositories.models.audit import IdempotencyKeyModel


@dataclass(frozen=True)
class IdempotencyRecord:
    scope: str
    key: str
    request_hash: str
    response: dict[str, Any]
    created_at: str


class IdempotencyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, scope: str, key: str) -> IdempotencyRecord | None:
        row = self._session.get(IdempotencyKeyModel, (scope, key))
        if row is None:
            return None
        return IdempotencyRecord(
            row.scope, row.key, row.request_hash, dict(row.response), row.created_at
        )

    def add(self, record: IdempotencyRecord) -> None:
        self._session.add(
            IdempotencyKeyModel(
                scope=record.scope,
                key=record.key,
                request_hash=record.request_hash,
                response=record.response,
                created_at=record.created_at,
            )
        )
        self._session.flush()
