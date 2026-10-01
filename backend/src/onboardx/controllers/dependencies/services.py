"""Builds the service container once at startup and hands it to routes."""

from dataclasses import dataclass

from fastapi import Request

from onboardx.config.settings import Settings
from onboardx.domain.ports import Clock, NotificationSender
from onboardx.repositories.file_store import LocalFileStore
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.account_service import AccountService
from onboardx.services.audit_service import AuditService
from onboardx.services.auth_service import AuthService
from onboardx.services.case_view_service import CaseViewService
from onboardx.services.checklist_admin_service import ChecklistAdminService
from onboardx.services.checklist_service import ChecklistService
from onboardx.services.decision_service import DecisionService
from onboardx.services.document_service import DocumentService
from onboardx.services.evidence_service import EvidenceService
from onboardx.services.lead_service import LeadService
from onboardx.services.notification_service import NotificationService, StubNotificationSender
from onboardx.services.onboarding_service import OnboardingService
from onboardx.services.override_service import OverrideService
from onboardx.services.pipeline_service import PipelineService
from onboardx.services.query_service import QueryService
from onboardx.services.report_service import ReportService
from onboardx.services.risk_service import RiskService
from onboardx.services.rule_set_service import RuleSetService
from onboardx.services.screening_service import ScreeningService
from onboardx.services.signup_service import SignupService
from onboardx.services.submission_service import SubmissionService
from onboardx.services.user_admin_service import UserAdminService
from onboardx.services.watchlist_service import WatchlistService


@dataclass(frozen=True)
class Services:
    auth: AuthService
    leads: LeadService
    checklists: ChecklistService
    cases: CaseViewService
    rule_sets: RuleSetService
    onboarding: OnboardingService
    documents: DocumentService
    submission: SubmissionService
    screening: ScreeningService
    risk: RiskService
    decisions: DecisionService
    pipeline: PipelineService
    notifications: NotificationService
    overrides: OverrideService
    evidence: EvidenceService
    watchlist: WatchlistService
    reports: ReportService
    user_admin: UserAdminService
    checklist_admin: ChecklistAdminService
    queries: QueryService
    signup: SignupService


def build_services(
    settings: Settings,
    uow_factory: UnitOfWorkFactory,
    clock: Clock,
    secret: str,
    sender: NotificationSender | None = None,
) -> Services:
    audit = AuditService(clock)
    notifications = NotificationService(uow_factory, clock, sender or StubNotificationSender())
    onboarding = OnboardingService(clock, audit, recorder=notifications)
    auth = AuthService(uow_factory, secret, clock, settings.token_ttl_seconds)
    screening = ScreeningService(uow_factory, clock, audit, onboarding)
    risk = RiskService(uow_factory, clock, audit, onboarding)
    accounts = AccountService(clock, audit)
    decisions = DecisionService(
        uow_factory,
        clock,
        audit,
        onboarding,
        accounts,
        manual_policy=settings.review_policy == "manual",
    )
    pipeline = PipelineService(uow_factory, screening, risk, decisions)
    store = LocalFileStore(settings.upload_dir)
    return Services(
        auth=auth,
        leads=LeadService(uow_factory, clock, onboarding, audit, auth, secret),
        checklists=ChecklistService(uow_factory),
        cases=CaseViewService(uow_factory, clock),
        rule_sets=RuleSetService(uow_factory, clock, audit),
        onboarding=onboarding,
        documents=DocumentService(uow_factory, clock, audit, store, notifications),
        submission=SubmissionService(
            uow_factory, audit, onboarding, pipeline, auto_advance=settings.auto_advance_on_submit
        ),
        screening=screening,
        risk=risk,
        decisions=decisions,
        pipeline=pipeline,
        notifications=notifications,
        overrides=OverrideService(uow_factory, clock, audit, onboarding, accounts, risk),
        evidence=EvidenceService(uow_factory),
        watchlist=WatchlistService(uow_factory, clock, audit),
        reports=ReportService(uow_factory, clock),
        user_admin=UserAdminService(uow_factory, clock, audit),
        checklist_admin=ChecklistAdminService(uow_factory, clock, audit),
        queries=QueryService(uow_factory, clock, audit),
        signup=SignupService(uow_factory, clock, audit, auth),
    )


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services
