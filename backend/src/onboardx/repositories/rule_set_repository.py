"""Risk rule sets: drafts insert/update, publish, read. Published rows are trigger-protected."""

from typing import Any

from sqlalchemy import Delete, Update, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from onboardx.domain.enums import RuleSetStatus
from onboardx.domain.risk import RuleSet
from onboardx.domain.ruleset_codec import ruleset_from_dict, ruleset_to_dict
from onboardx.repositories._errors import (
    IMMUTABLE_RULESET_MESSAGE,
    is_trigger_error,
    ruleset_immutable,
)
from onboardx.repositories.models.risk import RiskRuleSetModel


def _to_rule_set(row: RiskRuleSetModel) -> RuleSet:
    return ruleset_from_dict(
        {
            "version": row.version,
            "status": row.status,
            "weights": row.weights,
            "points": row.points,
            "geography_map": row.geography_map,
            "geography_default": row.geography_default,
            "border_states": row.border_states,
            "thresholds": {"low_max": row.low_max, "medium_max": row.medium_max},
            "author": row.author,
            "created_at": row.created_at,
            "published_at": row.published_at,
        }
    )


def _columns(rule_set: RuleSet) -> dict[str, Any]:
    data = ruleset_to_dict(rule_set)
    return {
        "weights": data["weights"],
        "points": data["points"],
        "geography_map": data["geography_map"],
        "geography_default": data["geography_default"],
        "border_states": data["border_states"],
        "low_max": rule_set.low_max,
        "medium_max": rule_set.medium_max,
    }


class RuleSetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, version: int) -> RuleSet | None:
        row = self._session.get(RiskRuleSetModel, version)
        return None if row is None else _to_rule_set(row)

    def list_all(self) -> list[RuleSet]:
        rows = self._session.scalars(select(RiskRuleSetModel).order_by(RiskRuleSetModel.version))
        return [_to_rule_set(row) for row in rows]

    def latest(self) -> RuleSet | None:
        query = select(RiskRuleSetModel).order_by(RiskRuleSetModel.version.desc()).limit(1)
        row = self._session.scalars(query).first()
        return None if row is None else _to_rule_set(row)

    def latest_published(self) -> RuleSet | None:
        query = (
            select(RiskRuleSetModel)
            .where(RiskRuleSetModel.status == str(RuleSetStatus.PUBLISHED))
            .order_by(RiskRuleSetModel.version.desc())
            .limit(1)
        )
        row = self._session.scalars(query).first()
        return None if row is None else _to_rule_set(row)

    def draft(self) -> RuleSet | None:
        query = select(RiskRuleSetModel).where(RiskRuleSetModel.status == str(RuleSetStatus.DRAFT))
        row = self._session.scalars(query.limit(1)).first()
        return None if row is None else _to_rule_set(row)

    def max_version(self) -> int:
        return int(self._session.scalar(select(func.max(RiskRuleSetModel.version))) or 0)

    def add_draft(self, rule_set: RuleSet) -> None:
        self._session.add(
            RiskRuleSetModel(
                version=rule_set.version,
                status=str(RuleSetStatus.DRAFT),
                author=rule_set.author,
                created_at=rule_set.created_at,
                published_at=None,
                **_columns(rule_set),
            )
        )
        self._session.flush()

    def update_draft(self, rule_set: RuleSet) -> None:
        statement = (
            update(RiskRuleSetModel)
            .where(RiskRuleSetModel.version == rule_set.version)
            .values(**_columns(rule_set))
        )
        self._execute(statement, rule_set.version)

    def mark_published(self, version: int, published_at: str) -> None:
        statement = (
            update(RiskRuleSetModel)
            .where(RiskRuleSetModel.version == version)
            .values(status=str(RuleSetStatus.PUBLISHED), published_at=published_at)
        )
        self._execute(statement, version)

    def delete(self, version: int) -> None:
        self._execute(delete(RiskRuleSetModel).where(RiskRuleSetModel.version == version), version)

    def _execute(self, statement: Update | Delete, version: int) -> None:
        try:
            self._session.execute(statement)
        except IntegrityError as error:
            if is_trigger_error(error, IMMUTABLE_RULESET_MESSAGE):
                raise ruleset_immutable(version) from error
            raise
        self._session.expire_all()
