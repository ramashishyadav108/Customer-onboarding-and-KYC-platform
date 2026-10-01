"""Admin user and role management (AC-11); admin only, enforced here (NFR-04)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.auth import Principal, require_role
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.management import (
    ApproveIn,
    RoleIn,
    UserIn,
    UserListOut,
    UserOut,
    user_out,
)
from onboardx.domain.enums import Role

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])

AdminOnly = Annotated[Principal, Depends(require_role(Role.ADMIN))]
Svc = Annotated[Services, Depends(get_services)]


@router.get("")
def list_users(_admin: AdminOnly, services: Svc) -> UserListOut:
    return UserListOut(items=[user_out(v) for v in services.user_admin.list_users()])


@router.post("", status_code=201)
def create_user(body: UserIn, admin: AdminOnly, services: Svc) -> UserOut:
    view = services.user_admin.create(
        username=body.username, password=body.password, role=body.role, actor=admin.subject
    )
    return user_out(view)


@router.put("/{user_id}/role")
def change_role(user_id: str, body: RoleIn, admin: AdminOnly, services: Svc) -> UserOut:
    view = services.user_admin.change_role(user_id=user_id, role=body.role, actor=admin.subject)
    return user_out(view)


@router.post("/{user_id}/deactivate")
def deactivate_user(user_id: str, admin: AdminOnly, services: Svc) -> UserOut:
    return user_out(services.user_admin.deactivate(user_id=user_id, actor=admin.subject))


@router.post("/{user_id}/reactivate")
def reactivate_user(user_id: str, admin: AdminOnly, services: Svc) -> UserOut:
    return user_out(services.user_admin.reactivate(user_id=user_id, actor=admin.subject))


@router.post("/{user_id}/approve")
def approve_user(
    user_id: str, admin: AdminOnly, services: Svc, body: ApproveIn | None = None
) -> UserOut:
    """Approve a staff sign-up request, optionally with a different staff role."""
    role = body.role if body is not None else None
    return user_out(services.user_admin.approve(user_id=user_id, role=role, actor=admin.subject))


@router.post("/{user_id}/reject")
def reject_user(user_id: str, admin: AdminOnly, services: Svc) -> UserOut:
    return user_out(services.user_admin.reject(user_id=user_id, actor=admin.subject))
