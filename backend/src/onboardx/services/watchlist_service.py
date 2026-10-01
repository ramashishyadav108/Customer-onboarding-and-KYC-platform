"""Watchlist administration (AC-05, NFR-02): append-only entries and deactivations, audited."""

import uuid

from onboardx.domain.enums import AuditEvent, ListType, Role
from onboardx.domain.errors import AlreadyDeactivatedError, NotFoundError, ValidationError
from onboardx.domain.matching import token_key
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.domain.views import WatchlistEntryView, WatchlistPage
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService

MAX_NAME = 100
MAX_ALIASES = 10


def _clean(value: str, field: str) -> str:
    text = value.strip()
    if not text or len(text) > MAX_NAME or not token_key(text):
        raise ValidationError.single(field, f"must be 1 to {MAX_NAME} characters with a letter")
    return text


def _validated(name: str, aliases: list[str], list_type: str) -> tuple[str, list[str], str]:
    if list_type not in {str(item) for item in ListType}:
        raise ValidationError.single("list_type", "must be AML or PEP")
    if len(aliases) > MAX_ALIASES:
        raise ValidationError.single("aliases", f"at most {MAX_ALIASES} aliases")
    return _clean(name, "name"), [_clean(alias, "aliases") for alias in aliases], list_type


class WatchlistService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, audit: AuditService) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit

    def list_entries(self, *, active: bool | None = None) -> WatchlistPage:
        with self._uow_factory() as uow:
            items = uow.watchlist.list_views(active=active)
            return WatchlistPage(uow.screenings.watchlist_version(), tuple(items))

    def add(
        self, *, name: str, aliases: list[str], list_type: str, actor: str
    ) -> WatchlistEntryView:
        """Append an entry; it is used by every screening that happens afterwards."""
        clean_name, clean_aliases, kind = _validated(name, aliases, list_type)
        entry_id = str(uuid.uuid4())
        now = to_iso_z(self._clock.now())
        with self._uow_factory() as uow:
            uow.watchlist.add_entry(
                entry_id=entry_id,
                name=clean_name,
                aliases=clean_aliases,
                list_type=kind,
                name_tokens=token_key(clean_name),
                alias_tokens=[token_key(alias) for alias in clean_aliases],
                added_by=actor,
                created_at=now,
            )
            self._record(uow, AuditEvent.WATCHLIST_ENTRY_ADDED, actor, entry_id, kind)
            uow.commit()
        return WatchlistEntryView(entry_id, clean_name, tuple(clean_aliases), kind, True, now, None)

    def deactivate(self, *, entry_id: str, actor: str) -> WatchlistEntryView:
        """Append a deactivation row; 404 for unknown, 409 ALREADY_DEACTIVATED on repeat."""
        now = to_iso_z(self._clock.now())
        with self._uow_factory() as uow:
            entry = uow.watchlist.get_view(entry_id)
            if entry is None:
                raise NotFoundError("watchlist entry")
            if not entry.active:
                raise AlreadyDeactivatedError(entry_id)
            uow.watchlist.add_deactivation(
                row_id=str(uuid.uuid4()), entry_id=entry_id, deactivated_by=actor, created_at=now
            )
            event = AuditEvent.WATCHLIST_ENTRY_DEACTIVATED
            self._record(uow, event, actor, entry_id, entry.list_type)
            uow.commit()
        return WatchlistEntryView(
            entry.entry_id, entry.name, entry.aliases, entry.list_type, False, entry.added_at, now
        )

    def _record(
        self, uow: UnitOfWork, event: AuditEvent, actor: str, entry_id: str, list_type: str
    ) -> None:
        """Audit holds entry_id and list_type only, never the name (AC-05.10)."""
        self._audit.record(
            uow,
            event=event,
            actor=actor,
            role=str(Role.ADMIN),
            case_id=None,
            payload={"entry_id": entry_id, "list_type": list_type},
        )
