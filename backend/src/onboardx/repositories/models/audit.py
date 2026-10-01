"""Audit log (append-only) and idempotency key models."""

from typing import Any

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from onboardx.repositories.models.base import Base


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    audit_id: Mapped[str]
    case_id: Mapped[str | None]
    event: Mapped[str]
    actor: Mapped[str]
    role: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    correlation_id: Mapped[str]
    created_at: Mapped[str]


class IdempotencyKeyModel(Base):
    __tablename__ = "idempotency_keys"

    scope: Mapped[str] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(primary_key=True)
    request_hash: Mapped[str]
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[str]
