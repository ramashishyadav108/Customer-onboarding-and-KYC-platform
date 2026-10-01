"""Report filters and response models (api-contracts 2.8): aggregates only, integers only."""

import re
from dataclasses import asdict
from datetime import date
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

from onboardx.domain.enums import Product
from onboardx.domain.errors import ValidationError
from onboardx.domain.reports import (
    AutoApproval,
    Backlog,
    DroppedStage,
    FunnelStage,
    ReasonCount,
    ReportFilters,
    StageTime,
    TatRow,
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
Filters = dict[str, str | None]
Rows = list[dict[str, int | str]]


def _parse_date(value: str | None, field: str) -> date | None:
    if value is None:
        return None
    if not _ISO_DATE.match(value):
        raise ValidationError.single(field, "must be an ISO date YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError.single(field, "must be a valid calendar date") from None


def report_filters(
    product: Product | None = None,
    date_from: Annotated[str | None, Query(alias="from")] = None,
    date_to: Annotated[str | None, Query(alias="to")] = None,
) -> ReportFilters:
    """Dependency: validates the shared product, from and to parameters (422 names the field)."""
    return ReportFilters(product, _parse_date(date_from, "from"), _parse_date(date_to, "to"))


def filters_body(filters: ReportFilters) -> Filters:
    return {
        "product": None if filters.product is None else str(filters.product),
        "from": None if filters.date_from is None else filters.date_from.isoformat(),
        "to": None if filters.date_to is None else filters.date_to.isoformat(),
    }


class TatReport(BaseModel):
    filters: Filters
    items: Rows


class FunnelReport(BaseModel):
    filters: Filters
    stages: Rows


class BacklogReport(BaseModel):
    filters: Filters
    count: int
    oldest_age_minutes: int
    buckets: list[dict[str, int | str | None]]


class TimePerStageReport(BaseModel):
    filters: Filters
    stages: Rows


class RejectionReport(BaseModel):
    filters: Filters
    items: Rows


class AutoApprovalReport(BaseModel):
    filters: Filters
    auto_approved: int
    decided: int
    rate_bp: int
    target_bp: int
    met: bool


class DroppedLeadsReport(BaseModel):
    older_than_days: int
    total: int
    stages: Rows


def tat_report(filters: ReportFilters, rows: tuple[TatRow, ...]) -> TatReport:
    return TatReport(filters=filters_body(filters), items=[asdict(r) for r in rows])


def funnel_report(filters: ReportFilters, stages: tuple[FunnelStage, ...]) -> FunnelReport:
    return FunnelReport(filters=filters_body(filters), stages=[asdict(s) for s in stages])


def backlog_report(filters: ReportFilters, backlog: Backlog) -> BacklogReport:
    return BacklogReport(
        filters=filters_body(filters),
        count=backlog.count,
        oldest_age_minutes=backlog.oldest_age_minutes,
        buckets=[asdict(b) for b in backlog.buckets],
    )


def stage_report(filters: ReportFilters, rows: tuple[StageTime, ...]) -> TimePerStageReport:
    return TimePerStageReport(filters=filters_body(filters), stages=[asdict(r) for r in rows])


def rejection_report(filters: ReportFilters, rows: tuple[ReasonCount, ...]) -> RejectionReport:
    return RejectionReport(filters=filters_body(filters), items=[asdict(r) for r in rows])


def auto_report(filters: ReportFilters, result: AutoApproval) -> AutoApprovalReport:
    return AutoApprovalReport(filters=filters_body(filters), **asdict(result))


def dropped_report(days: int, stages: tuple[DroppedStage, ...]) -> DroppedLeadsReport:
    return DroppedLeadsReport(
        older_than_days=days,
        total=sum(s.count for s in stages),
        stages=[asdict(s) for s in stages],
    )
