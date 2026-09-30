"""Submission and pipeline steps: submit (owner); screen, classify, decide, advance (staff)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.auth import Principal, require_case_owner, require_role
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.pipeline import (
    AdvanceResponse,
    ClassifyResponse,
    DecideResponse,
    NotificationListOut,
    ScreenResponse,
    SubmitOut,
    advance_out,
    assessment_out,
    decide_out,
    notification_list_out,
    screening_out,
    submit_out,
)
from onboardx.domain.enums import CaseState, Role

router = APIRouter(prefix="/api/v1", tags=["pipeline"])

StepCaller = Annotated[Principal, Depends(require_role(Role.KYC_ANALYST, Role.ADMIN))]
ServicesDep = Annotated[Services, Depends(get_services)]


@router.post("/cases/{case_id}/submit")
def submit_case(
    case_id: str,
    principal: Annotated[Principal, Depends(require_case_owner)],
    services: ServicesDep,
) -> SubmitOut:
    return submit_out(services.submission.submit(case_id=case_id, actor=principal.subject))


@router.post("/cases/{case_id}/screen")
def screen_case(case_id: str, principal: StepCaller, services: ServicesDep) -> ScreenResponse:
    result = services.screening.screen(
        case_id=case_id, actor=principal.subject, role=str(principal.role)
    )
    return ScreenResponse(state=str(CaseState.SCREENED), result=screening_out(result))


@router.post("/cases/{case_id}/classify")
def classify_case(case_id: str, principal: StepCaller, services: ServicesDep) -> ClassifyResponse:
    assessment = services.risk.classify(
        case_id=case_id, actor=principal.subject, role=str(principal.role)
    )
    return ClassifyResponse(
        case_id=case_id, state=str(CaseState.CLASSIFIED), assessment=assessment_out(assessment)
    )


@router.post("/cases/{case_id}/decide")
def decide_case(case_id: str, principal: StepCaller, services: ServicesDep) -> DecideResponse:
    result = services.decisions.decide(
        case_id=case_id, actor=principal.subject, role=str(principal.role)
    )
    return decide_out(result)


@router.post("/cases/{case_id}/advance")
def advance_case(case_id: str, principal: StepCaller, services: ServicesDep) -> AdvanceResponse:
    result = services.pipeline.advance(
        case_id=case_id, actor=principal.subject, role=str(principal.role)
    )
    return advance_out(result)


@router.get("/cases/{case_id}/notifications")
def list_notifications(
    case_id: str,
    _principal: Annotated[Principal, Depends(require_case_owner)],
    services: ServicesDep,
) -> NotificationListOut:
    return notification_list_out(case_id, services.notifications.list_for_case(case_id))
