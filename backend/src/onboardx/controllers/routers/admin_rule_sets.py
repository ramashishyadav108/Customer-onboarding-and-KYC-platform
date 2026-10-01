"""Admin rule-set endpoints (E3-S2 data model, admin only): draft, edit draft, publish."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.auth import Principal, require_role
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.admin import RuleSetUpdate
from onboardx.domain.enums import Role
from onboardx.domain.ruleset_codec import ruleset_to_dict

router = APIRouter(prefix="/api/v1/admin/rule-sets", tags=["admin-rule-sets"])

AdminOnly = Annotated[Principal, Depends(require_role(Role.ADMIN))]
Svc = Annotated[Services, Depends(get_services)]
SUMMARY_FIELDS = ("version", "status", "author", "created_at", "published_at")


@router.get("")
def list_rule_sets(_admin: AdminOnly, services: Svc) -> dict[str, Any]:
    items = [
        {k: v for k, v in ruleset_to_dict(r).items() if k in SUMMARY_FIELDS}
        for r in services.rule_sets.list_rule_sets()
    ]
    return {"items": items}


@router.get("/{version}")
def get_rule_set(version: int, _admin: AdminOnly, services: Svc) -> dict[str, Any]:
    return ruleset_to_dict(services.rule_sets.get(version))


@router.post("", status_code=201)
def create_draft(admin: AdminOnly, services: Svc) -> dict[str, Any]:
    return ruleset_to_dict(services.rule_sets.create_draft(admin.subject))


@router.put("/{version}")
def update_draft(
    version: int, body: RuleSetUpdate, admin: AdminOnly, services: Svc
) -> dict[str, Any]:
    changes = body.model_dump(exclude_unset=True)
    return ruleset_to_dict(services.rule_sets.update_draft(version, changes, admin.subject))


@router.post("/{version}/publish")
def publish(version: int, admin: AdminOnly, services: Svc) -> dict[str, Any]:
    return ruleset_to_dict(services.rule_sets.publish(version, admin.subject))
