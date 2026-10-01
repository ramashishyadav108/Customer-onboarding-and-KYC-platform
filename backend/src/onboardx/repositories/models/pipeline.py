"""Screening, watchlist, risk assessment, decision, account and notification models."""

from typing import Any

from sqlalchemy import JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from onboardx.repositories.models.base import Base


class ScreeningResultModel(Base):
    __tablename__ = "screening_results"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id: Mapped[str]
    case_id: Mapped[str]
    hits: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    requires_manual_review: Mapped[bool] = mapped_column(Boolean)
    watchlist_version: Mapped[int]
    screened_at: Mapped[str]


class WatchlistEntryModel(Base):
    __tablename__ = "watchlist_entries"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[str]
    name: Mapped[str]
    aliases: Mapped[list[str]] = mapped_column(JSON)
    list_type: Mapped[str]
    name_tokens: Mapped[str]
    alias_tokens: Mapped[list[str]] = mapped_column(JSON)
    added_by: Mapped[str]
    created_at: Mapped[str]


class WatchlistDeactivationModel(Base):
    __tablename__ = "watchlist_deactivations"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id: Mapped[str]
    entry_id: Mapped[str]
    deactivated_by: Mapped[str]
    created_at: Mapped[str]


class RiskAssessmentModel(Base):
    __tablename__ = "risk_assessments"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    assessment_id: Mapped[str]
    case_id: Mapped[str]
    score: Mapped[int]
    band: Mapped[str]
    rule_version: Mapped[int]
    source: Mapped[str]
    breakdown: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[str]


class DecisionModel(Base):
    __tablename__ = "decisions"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    decision_id: Mapped[str]
    case_id: Mapped[str]
    type: Mapped[str]
    outcome: Mapped[str]
    reason_code: Mapped[str]
    rule_version: Mapped[int]
    actor: Mapped[str]
    created_at: Mapped[str]


class AccountModel(Base):
    __tablename__ = "accounts"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str]
    case_id: Mapped[str]
    product: Mapped[str]
    account_number: Mapped[str]
    created_at: Mapped[str]


class NotificationModel(Base):
    __tablename__ = "notifications"

    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    notification_id: Mapped[str]
    case_id: Mapped[str]
    event: Mapped[str]
    template: Mapped[str]
    text: Mapped[str]
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    contact_masked: Mapped[str]
    created_at: Mapped[str]
