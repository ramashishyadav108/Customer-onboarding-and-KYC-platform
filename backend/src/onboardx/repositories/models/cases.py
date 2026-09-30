"""Case, profile, checklist and state-history models."""

from sqlalchemy import JSON, Boolean, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from onboardx.repositories.models.base import Base


class CaseModel(Base):
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    contact: Mapped[str]
    product: Mapped[str]
    state: Mapped[str]
    checklist_version: Mapped[int]
    created_at: Mapped[str]
    updated_at: Mapped[str]


class CaseProfileModel(Base):
    __tablename__ = "case_profiles"

    case_id: Mapped[str] = mapped_column(primary_key=True)
    date_of_birth: Mapped[str]
    annual_income: Mapped[int]
    occupation_category: Mapped[str]
    country_code: Mapped[str]
    state_code: Mapped[str | None]
    updated_at: Mapped[str]


class ChecklistTemplateModel(Base):
    __tablename__ = "checklist_templates"

    product: Mapped[str] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[str]


class ChecklistItemModel(Base):
    __tablename__ = "checklist_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product", "version"], ["checklist_templates.product", "checklist_templates.version"]
        ),
    )

    product: Mapped[str] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    item_code: Mapped[str] = mapped_column(primary_key=True)
    mandatory: Mapped[bool] = mapped_column(Boolean)
    accepted_classes: Mapped[list[str]] = mapped_column(JSON)


class StateHistoryModel(Base):
    __tablename__ = "state_history"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    history_id: Mapped[str]
    case_id: Mapped[str]
    from_state: Mapped[str | None]
    to_state: Mapped[str]
    actor: Mapped[str]
    reason_code: Mapped[str | None]
    idempotency_key: Mapped[str | None]
    created_at: Mapped[str]
