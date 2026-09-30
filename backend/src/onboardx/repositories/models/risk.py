"""Risk rule set model (mutable only while DRAFT; trigger-protected once PUBLISHED)."""

from typing import Any

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from onboardx.repositories.models.base import Base


class RiskRuleSetModel(Base):
    __tablename__ = "risk_rule_sets"

    version: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    status: Mapped[str]
    weights: Mapped[dict[str, Any]] = mapped_column(JSON)
    points: Mapped[dict[str, Any]] = mapped_column(JSON)
    geography_map: Mapped[dict[str, Any]] = mapped_column(JSON)
    geography_default: Mapped[str]
    border_states: Mapped[list[str]] = mapped_column(JSON)
    low_max: Mapped[int]
    medium_max: Mapped[int]
    author: Mapped[str]
    created_at: Mapped[str]
    published_at: Mapped[str | None]
