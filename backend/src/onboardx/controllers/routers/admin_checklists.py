"""Admin checklist management (AC-12): list latest versions, append a new version."""

from typing import Annotated

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.auth import Principal, require_role
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.management import (
    ChecklistIn,
    ChecklistListOut,
    ChecklistVersionOut,
    checklist_out,
)
from onboardx.domain.enums import Role

router = APIRouter(prefix="/api/v1/admin/checklists", tags=["admin-checklists"])

AdminOnly = Annotated[Principal, Depends(require_role(Role.ADMIN))]
Svc = Annotated[Services, Depends(get_services)]


@router.get("")
def list_checklists(_admin: AdminOnly, services: Svc) -> ChecklistListOut:
    views = services.checklist_admin.list_latest()
    return ChecklistListOut(items=[checklist_out(v) for v in views])


@router.post("/{product}", status_code=201)
def publish_checklist(
    product: str, body: ChecklistIn, admin: AdminOnly, services: Svc
) -> ChecklistVersionOut:
    items = [(i.item_code, i.mandatory, i.accepted_classes) for i in body.items]
    view = services.checklist_admin.publish_version(
        product=product, items=items, actor=admin.subject
    )
    return checklist_out(view)
