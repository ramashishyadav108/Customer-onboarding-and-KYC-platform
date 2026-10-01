"""Rule set lifecycle: draft copy, edit draft, publish; published versions are immutable (AC-06)."""

from dataclasses import replace
from typing import Any

from onboardx.domain.enums import AuditEvent, Role, RuleSetStatus
from onboardx.domain.errors import (
    DraftExistsError,
    NotFoundError,
    PublishedRuleSetImmutableError,
    RuleSetInvalidError,
)
from onboardx.domain.ports import Clock
from onboardx.domain.risk import RuleSet, publish_problems
from onboardx.domain.ruleset_codec import ruleset_from_dict, ruleset_to_dict
from onboardx.domain.timeutil import to_iso_z
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService

EDITABLE_FIELDS = (
    "weights",
    "points",
    "geography_map",
    "geography_default",
    "thresholds",
    "border_states",
)


class RuleSetService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, audit: AuditService) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit

    def list_rule_sets(self) -> list[RuleSet]:
        with self._uow_factory() as uow:
            return uow.rule_sets.list_all()

    def get(self, version: int) -> RuleSet:
        with self._uow_factory() as uow:
            return self._require(uow, version)

    def create_draft(self, actor: str) -> RuleSet:
        """DRAFT copy of the latest version with version = max + 1 (AC-06.4)."""
        with self._uow_factory() as uow:
            latest = uow.rule_sets.latest()
            if latest is None:
                raise NotFoundError("rule set")
            existing = uow.rule_sets.draft()
            if existing is not None:
                raise DraftExistsError(existing.version)
            draft = replace(
                latest,
                version=uow.rule_sets.max_version() + 1,
                status=RuleSetStatus.DRAFT,
                author=actor,
                created_at=to_iso_z(self._clock.now()),
                published_at=None,
            )
            uow.rule_sets.add_draft(draft)
            self._audit_event(uow, AuditEvent.RULESET_DRAFT_CREATED, actor, draft.version)
            uow.commit()
        return draft

    def update_draft(self, version: int, changes: dict[str, Any], actor: str) -> RuleSet:
        """Replace whole sections of a DRAFT; a PUBLISHED version raises immutability error."""
        with self._uow_factory() as uow:
            current = self._require(uow, version)
            self._ensure_draft(current)
            merged = ruleset_to_dict(current)
            merged.update({k: v for k, v in changes.items() if k in EDITABLE_FIELDS})
            updated = ruleset_from_dict(merged)
            uow.rule_sets.update_draft(updated)
            self._audit_event(uow, AuditEvent.RULESET_DRAFT_UPDATED, actor, version)
            uow.commit()
        return updated

    def publish(self, version: int, actor: str) -> RuleSet:
        """Validate then set PUBLISHED and published_at (AC-06.3, AC-06.5)."""
        with self._uow_factory() as uow:
            current = self._require(uow, version)
            self._ensure_draft(current)
            problems = publish_problems(current)
            if problems:
                raise RuleSetInvalidError(problems)
            uow.rule_sets.mark_published(version, to_iso_z(self._clock.now()))
            self._audit_event(uow, AuditEvent.RULESET_PUBLISHED, actor, version)
            uow.commit()
            return self._require(uow, version)

    def delete_draft(self, version: int) -> None:
        """Delete a DRAFT; any published version raises PublishedRuleSetImmutableError."""
        with self._uow_factory() as uow:
            self._ensure_draft(self._require(uow, version))
            uow.rule_sets.delete(version)
            uow.commit()

    @staticmethod
    def _require(uow: UnitOfWork, version: int) -> RuleSet:
        rule_set = uow.rule_sets.get(version)
        if rule_set is None:
            raise NotFoundError("rule set")
        return rule_set

    @staticmethod
    def _ensure_draft(rule_set: RuleSet) -> None:
        if rule_set.is_published:
            raise PublishedRuleSetImmutableError(rule_set.version)

    def _audit_event(self, uow: UnitOfWork, event: AuditEvent, actor: str, version: int) -> None:
        self._audit.record(
            uow,
            event=event,
            actor=actor,
            role=str(Role.ADMIN),
            case_id=None,
            payload={"version": version},
        )
