"""Override model (append-only, one row per case)."""

from sqlalchemy.orm import Mapped, mapped_column

from onboardx.repositories.models.base import Base


class OverrideModel(Base):
    __tablename__ = "overrides"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    override_id: Mapped[str]
    case_id: Mapped[str]
    actor: Mapped[str]
    previous_state: Mapped[str]
    decision: Mapped[str]
    reason_code: Mapped[str]
    comment: Mapped[str | None]
    rule_version: Mapped[int]
    created_at: Mapped[str]
