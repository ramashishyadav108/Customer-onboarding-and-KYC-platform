"""Watchlist reads (active entries, version) and append-only screening results."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from onboardx.domain.entities import ScreeningResult, WatchlistEntry
from onboardx.repositories.models.pipeline import (
    ScreeningResultModel,
    WatchlistDeactivationModel,
    WatchlistEntryModel,
)


def _to_entry(row: WatchlistEntryModel) -> WatchlistEntry:
    return WatchlistEntry(
        entry_id=row.entry_id,
        name=row.name,
        aliases=tuple(row.aliases),
        list_type=row.list_type,
        name_tokens=row.name_tokens,
        alias_tokens=tuple(row.alias_tokens),
    )


def _to_result(row: ScreeningResultModel) -> ScreeningResult:
    return ScreeningResult(
        result_id=row.id,
        case_id=row.case_id,
        hits=tuple(dict(hit) for hit in row.hits),
        requires_manual_review=bool(row.requires_manual_review),
        watchlist_version=row.watchlist_version,
        screened_at=row.screened_at,
    )


class ScreeningRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def active_entries(self) -> list[WatchlistEntry]:
        """Entries with no deactivation row, in insertion order."""
        deactivated = select(WatchlistDeactivationModel.entry_id)
        rows = self._session.scalars(
            select(WatchlistEntryModel)
            .where(WatchlistEntryModel.entry_id.not_in(deactivated))
            .order_by(WatchlistEntryModel.seq)
        ).all()
        return [_to_entry(row) for row in rows]

    def watchlist_version(self) -> int:
        """Rows in entries plus deactivations; monotonic because nothing is ever deleted."""
        entries = self._session.scalar(select(func.count()).select_from(WatchlistEntryModel))
        stops = self._session.scalar(select(func.count()).select_from(WatchlistDeactivationModel))
        return int(entries or 0) + int(stops or 0)

    def add_result(self, result: ScreeningResult) -> None:
        self._session.add(
            ScreeningResultModel(
                id=result.result_id,
                case_id=result.case_id,
                hits=[dict(hit) for hit in result.hits],
                requires_manual_review=result.requires_manual_review,
                watchlist_version=result.watchlist_version,
                screened_at=result.screened_at,
            )
        )
        self._session.flush()

    def latest_result(self, case_id: str) -> ScreeningResult | None:
        row = self._session.scalars(
            select(ScreeningResultModel)
            .where(ScreeningResultModel.case_id == case_id)
            .order_by(ScreeningResultModel.seq.desc())
            .limit(1)
        ).first()
        return None if row is None else _to_result(row)

    def list_results(self, case_id: str) -> list[ScreeningResult]:
        rows = self._session.scalars(
            select(ScreeningResultModel)
            .where(ScreeningResultModel.case_id == case_id)
            .order_by(ScreeningResultModel.seq)
        ).all()
        return [_to_result(row) for row in rows]
