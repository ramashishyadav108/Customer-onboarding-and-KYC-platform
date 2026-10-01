"""Admin metrics derived from append-only history (AC-10, NFR-01): integers only.

Durations are whole seconds, ratios are basis points, averages use floor division.
"""

from datetime import timedelta

from onboardx.domain.ports import Clock
from onboardx.domain.reports import (
    MAX_REASONS,
    AutoApproval,
    Backlog,
    DroppedStage,
    FunnelStage,
    ReasonCount,
    ReportFilters,
    StageTime,
    TatRow,
    age_minutes,
    build_auto_approval,
    build_backlog,
    build_funnel,
    floor_avg,
)
from onboardx.domain.timeutil import parse_iso, to_iso_z
from onboardx.repositories.unit_of_work import UnitOfWorkFactory


class ReportService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    def tat_by_product(self, filters: ReportFilters) -> tuple[TatRow, ...]:
        """Closed cases only: seconds from INITIATED to APPROVED or REJECTED."""
        with self._uow_factory() as uow:
            rows = uow.reports.tat(filters)
        return tuple(TatRow(p, n, floor_avg(total, n), lo, hi) for p, n, total, lo, hi in rows)

    def funnel(self, filters: ReportFilters) -> tuple[FunnelStage, ...]:
        with self._uow_factory() as uow:
            counts = uow.reports.funnel_counts(filters)
        return build_funnel(counts)

    def backlog(self, filters: ReportFilters) -> Backlog:
        """Current MANUAL_REVIEW snapshot; from/to filter on the time the case entered review."""
        with self._uow_factory() as uow:
            entered = uow.reports.backlog_entries(filters)
        now = int(self._clock.now().timestamp())
        ages = [age_minutes(now, int(parse_iso(at).timestamp())) for at in entered]
        return build_backlog(ages)

    def time_per_stage(self, filters: ReportFilters) -> tuple[StageTime, ...]:
        with self._uow_factory() as uow:
            rows = uow.reports.stage_durations(filters)
        return tuple(StageTime(a, b, n, floor_avg(total, n)) for a, b, n, total in rows)

    def rejection_reasons(self, filters: ReportFilters) -> tuple[ReasonCount, ...]:
        with self._uow_factory() as uow:
            rows = uow.reports.rejection_reasons(filters, MAX_REASONS)
        return tuple(ReasonCount(code, count) for code, count in rows)

    def auto_approval(self, filters: ReportFilters) -> AutoApproval:
        with self._uow_factory() as uow:
            decided, approved = uow.reports.decision_counts(filters)
        return build_auto_approval(approved, decided)

    def dropped_leads(
        self, older_than_days: int, product: str | None = None
    ) -> tuple[DroppedStage, ...]:
        """Open INITIATED / DOCS_SUBMITTED cases idle for more than ``older_than_days``."""
        cutoff = to_iso_z(self._clock.now() - timedelta(days=older_than_days))
        with self._uow_factory() as uow:
            counts = uow.reports.dropped(product, cutoff)
        return tuple(DroppedStage(s, counts.get(s, 0)) for s in ("INITIATED", "DOCS_SUBMITTED"))
