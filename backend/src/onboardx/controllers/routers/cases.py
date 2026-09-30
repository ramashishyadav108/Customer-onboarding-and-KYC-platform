"""Case endpoints: list (staff), read (owner or staff) and profile upsert (owner)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from onboardx.controllers.dependencies.auth import (
    Principal,
    require_case_access,
    require_case_owner,
    require_role,
)
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.cases import (
    CaseDetailOut,
    CaseListOut,
    ProfileRequest,
    SortOrder,
    case_detail_out,
    case_list_out,
)
from onboardx.domain.enums import CaseState, Product, Role

router = APIRouter(prefix="/api/v1", tags=["cases"])

StaffOnly = Depends(require_role(Role.KYC_ANALYST, Role.COMPLIANCE_OFFICER, Role.ADMIN))


@router.get("/cases", dependencies=[StaffOnly])
def list_cases(
    services: Annotated[Services, Depends(get_services)],
    state: CaseState | None = None,
    product: Product | None = None,
    sort: SortOrder = "age_desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> CaseListOut:
    result = services.cases.list_cases(
        state=state,
        product=product,
        oldest_first=sort == "age_desc",
        page=page,
        page_size=page_size,
    )
    return case_list_out(result)


@router.get("/cases/{case_id}")
def get_case(
    case_id: str,
    principal: Annotated[Principal, Depends(require_case_access)],
    services: Annotated[Services, Depends(get_services)],
) -> CaseDetailOut:
    detail = services.cases.get_case_detail(
        case_id, include_profile=principal.role is Role.PROSPECT
    )
    return case_detail_out(detail)


@router.put("/cases/{case_id}/profile")
def put_profile(
    case_id: str,
    body: ProfileRequest,
    principal: Annotated[Principal, Depends(require_case_owner)],
    services: Annotated[Services, Depends(get_services)],
) -> CaseDetailOut:
    services.leads.update_profile(
        case_id=case_id,
        date_of_birth=date.fromisoformat(body.date_of_birth),
        annual_income=body.annual_income,
        occupation_category=str(body.occupation_category),
        country_code=body.country_code,
        state_code=body.state_code,
        actor=principal.subject,
    )
    return case_detail_out(services.cases.get_case_detail(case_id, include_profile=True))
