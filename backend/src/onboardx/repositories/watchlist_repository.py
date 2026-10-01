"""Watchlist administration: entries and deactivations are append-only rows (NFR-02)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from onboardx.domain.views import WatchlistEntryView
from onboardx.repositories._errors import flush_unique
from onboardx.repositories.models.pipeline import WatchlistDeactivationModel, WatchlistEntryModel


def _view(row: WatchlistEntryModel, deactivated_at: str | None) -> WatchlistEntryView:
    return WatchlistEntryView(
        entry_id=row.entry_id,
        name=row.name,
        aliases=tuple(row.aliases),
        list_type=row.list_type,
        active=deactivated_at is None,
        added_at=row.created_at,
        deactivated_at=deactivated_at,
    )


class WatchlistRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_entry(
        self,
        *,
        entry_id: str,
        name: str,
        aliases: list[str],
        list_type: str,
        name_tokens: str,
        alias_tokens: list[str],
        added_by: str,
        created_at: str,
    ) -> None:
        self._session.add(
            WatchlistEntryModel(
                entry_id=entry_id,
                name=name,
                aliases=aliases,
                list_type=list_type,
                name_tokens=name_tokens,
                alias_tokens=alias_tokens,
                added_by=added_by,
                created_at=created_at,
            )
        )
        self._session.flush()

    def add_deactivation(
        self, *, row_id: str, entry_id: str, deactivated_by: str, created_at: str
    ) -> None:
        self._session.add(
            WatchlistDeactivationModel(
                id=row_id, entry_id=entry_id, deactivated_by=deactivated_by, created_at=created_at
            )
        )
        flush_unique(self._session)

    def _deactivations(self) -> dict[str, str]:
        rows = self._session.execute(
            select(WatchlistDeactivationModel.entry_id, WatchlistDeactivationModel.created_at)
        )
        return {str(entry_id): str(at) for entry_id, at in rows}

    def list_views(self, *, active: bool | None) -> list[WatchlistEntryView]:
        stops = self._deactivations()
        rows = self._session.scalars(select(WatchlistEntryModel).order_by(WatchlistEntryModel.seq))
        views = [_view(row, stops.get(row.entry_id)) for row in rows]
        return [v for v in views if active is None or v.active is active]

    def get_view(self, entry_id: str) -> WatchlistEntryView | None:
        row = self._session.scalars(
            select(WatchlistEntryModel).where(WatchlistEntryModel.entry_id == entry_id)
        ).first()
        if row is None:
            return None
        return _view(row, self._deactivations().get(entry_id))
