"""Admin report endpoints (E5-S3): aggregates only, admin role only (AC-10, NFR-04)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from onboardx.controllers.dependencies.auth import require_role
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.reports import (
    AutoApprovalReport,
    BacklogReport,
    DroppedLeadsReport,
    FunnelReport,
    RejectionReport,
    TatReport,
    TimePerStageReport,
    auto_report,
    backlog_report,
    dropped_report,
    funnel_report,
    rejection_report,
    report_filters,
    stage_report,
    tat_report,
)
from onboardx.domain.enums import Product, Role
from onboardx.domain.reports import ReportFilters

router = APIRouter(
    prefix="/api/v1/admin/reports",
    tags=["admin-reports"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)

Svc = Annotated[Services, Depends(get_services)]
Filters = Annotated[ReportFilters, Depends(report_filters)]


@router.get("/tat")
def tat(filters: Filters, services: Svc) -> TatReport:
    return tat_report(filters, services.reports.tat_by_product(filters))


@router.get("/funnel")
def funnel(filters: Filters, services: Svc) -> FunnelReport:
    return funnel_report(filters, services.reports.funnel(filters))


@router.get("/backlog")
def backlog(filters: Filters, services: Svc) -> BacklogReport:
    return backlog_report(filters, services.reports.backlog(filters))


@router.get("/time-per-stage")
def time_per_stage(filters: Filters, services: Svc) -> TimePerStageReport:
    return stage_report(filters, services.reports.time_per_stage(filters))


@router.get("/rejection-reasons")
def rejection_reasons(filters: Filters, services: Svc) -> RejectionReport:
    return rejection_report(filters, services.reports.rejection_reasons(filters))


@router.get("/auto-approval")
def auto_approval(filters: Filters, services: Svc) -> AutoApprovalReport:
    return auto_report(filters, services.reports.auto_approval(filters))


@router.get("/dropped-leads")
def dropped_leads(
    services: Svc,
    older_than_days: Annotated[int, Query(ge=1, le=365)] = 7,
    product: Product | None = None,
) -> DroppedLeadsReport:
    """Dropped-lead analysis (brief 6.2): open INITIATED / DOCS_SUBMITTED cases gone quiet."""
    stages = services.reports.dropped_leads(
        older_than_days, None if product is None else str(product)
    )
    return dropped_report(older_than_days, stages)
