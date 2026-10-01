"""Manual review (compliance officer), evidence (staff) and account lookup (owner or staff)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.auth import Principal, require_case_access, require_role
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.pipeline import AssessmentOut, assessment_out
from onboardx.controllers.schemas.review import (
    AccountOut,
    EvidenceOut,
    OverrideRequest,
    OverrideResponse,
    ReclassifyRequest,
    ReviewQueueOut,
    account_out,
    evidence_out,
    override_out,
    queue_out,
)
from onboardx.domain.enums import DecisionReason, Product, Role
from onboardx.domain.masking import mask_account_number

router = APIRouter(prefix="/api/v1", tags=["review"])

Officer = Annotated[Principal, Depends(require_role(Role.COMPLIANCE_OFFICER))]
Staff = Depends(require_role(Role.KYC_ANALYST, Role.COMPLIANCE_OFFICER, Role.ADMIN))
Svc = Annotated[Services, Depends(get_services)]


@router.get("/review-queue")
def review_queue(
    _officer: Officer,
    services: Svc,
    product: Product | None = None,
    reason_code: DecisionReason | None = None,
) -> ReviewQueueOut:
    items = services.overrides.review_queue(
        product=None if product is None else str(product),
        reason_code=None if reason_code is None else str(reason_code),
    )
    return queue_out(items)


@router.get("/cases/{case_id}/evidence", dependencies=[Staff])
def get_evidence(case_id: str, services: Svc) -> EvidenceOut:
    return evidence_out(services.evidence.get_evidence(case_id))


@router.post("/cases/{case_id}/override")
def override_case(
    case_id: str, body: OverrideRequest, officer: Officer, services: Svc
) -> OverrideResponse:
    result = services.overrides.override(
        case_id=case_id,
        decision=body.decision,
        reason_code=body.reason_code,
        comment=body.comment,
        actor=officer.subject,
        role=str(officer.role),
    )
    return override_out(result)


@router.post("/cases/{case_id}/reclassify")
def reclassify_case(
    case_id: str, body: ReclassifyRequest, officer: Officer, services: Svc
) -> AssessmentOut:
    assessment = services.overrides.reclassify(
        case_id=case_id,
        band=body.band,
        reason_code=body.reason_code,
        comment=body.comment,
        actor=officer.subject,
        role=str(officer.role),
    )
    return assessment_out(assessment)


@router.get("/cases/{case_id}/account")
def get_account(
    case_id: str,
    principal: Annotated[Principal, Depends(require_case_access)],
    services: Svc,
) -> AccountOut:
    """Stub account of an APPROVED case: the owner sees it masked, staff see the number."""
    view = services.evidence.get_account(case_id)
    masked = mask_account_number(view.account_number) if principal.role is Role.PROSPECT else None
    return account_out(view, masked=masked)
