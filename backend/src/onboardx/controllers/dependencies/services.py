"""Builds the service container once at startup and hands it to routes."""

from dataclasses import dataclass

from fastapi import Request

from onboardx.config.settings import Settings
from onboardx.domain.ports import Clock
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.auth_service import AuthService
from onboardx.services.case_view_service import CaseViewService
from onboardx.services.checklist_service import ChecklistService
from onboardx.services.lead_service import LeadService
from onboardx.services.onboarding_service import OnboardingService
from onboardx.services.rule_set_service import RuleSetService


@dataclass(frozen=True)
class Services:
    auth: AuthService
    leads: LeadService
    checklists: ChecklistService
    cases: CaseViewService
    rule_sets: RuleSetService
    onboarding: OnboardingService


def build_services(
    settings: Settings, uow_factory: UnitOfWorkFactory, clock: Clock, secret: str
) -> Services:
    audit = AuditService(clock)
    onboarding = OnboardingService(clock, audit)
    auth = AuthService(uow_factory, secret, clock, settings.token_ttl_seconds)
    return Services(
        auth=auth,
        leads=LeadService(uow_factory, clock, onboarding, audit, auth, secret),
        checklists=ChecklistService(uow_factory),
        cases=CaseViewService(uow_factory, clock),
        rule_sets=RuleSetService(uow_factory, clock, audit),
        onboarding=onboarding,
    )


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services
