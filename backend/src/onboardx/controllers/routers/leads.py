"""POST /api/v1/leads (public, DD-6): register a lead, get a case-bound prospect token."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from onboardx.controllers.dependencies.auth import Principal, optional_principal
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.cases import LeadRequest, LeadResponse
from onboardx.domain.enums import Role
from onboardx.services.auth_service import ANONYMOUS_PREFIX

router = APIRouter(prefix="/api/v1", tags=["leads"])


@router.post("/leads", status_code=201)
def create_lead(
    body: LeadRequest,
    response: Response,
    services: Annotated[Services, Depends(get_services)],
    principal: Annotated[Principal | None, Depends(optional_principal)],
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
) -> LeadResponse:
    result = services.leads.register(
        name=body.name,
        contact=body.contact,
        product=str(body.product),
        idempotency_key=idempotency_key,
        owner=_account_owner(principal),
    )
    if not result.created:
        response.status_code = 200
    return LeadResponse(
        case_id=result.case_id,
        state=result.state,
        product=result.product,
        access_token=result.access_token,
        expires_in=result.expires_in,
    )


def _account_owner(principal: Principal | None) -> str | None:
    """A signed-in prospect account owns the lead; staff and anonymous case tokens do not."""
    if principal is None or principal.role is not Role.PROSPECT:
        return None
    return None if principal.subject.startswith(ANONYMOUS_PREFIX) else principal.subject
