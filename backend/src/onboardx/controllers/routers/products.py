"""GET /api/v1/products/{product}/checklist (any authenticated user, E1-S5)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.auth import require_role
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.cases import ChecklistOut, checklist_out

router = APIRouter(prefix="/api/v1", tags=["checklists"])


@router.get("/products/{product}/checklist", dependencies=[Depends(require_role())])
def get_checklist(
    product: str, services: Annotated[Services, Depends(get_services)]
) -> ChecklistOut:
    return checklist_out(services.checklists.latest_for_product(product))
