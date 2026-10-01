"""Admin watchlist endpoints (E3-S4): list, add, deactivate; no edit and no delete."""

from typing import Annotated

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.auth import Principal, require_role
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.watchlist import (
    WatchlistEntryIn,
    WatchlistEntryOut,
    WatchlistOut,
    entry_out,
    watchlist_out,
)
from onboardx.domain.enums import Role

router = APIRouter(prefix="/api/v1/admin/watchlist", tags=["admin-watchlist"])

AdminOnly = Annotated[Principal, Depends(require_role(Role.ADMIN))]
Svc = Annotated[Services, Depends(get_services)]


@router.get("")
def list_watchlist(_admin: AdminOnly, services: Svc, active: bool | None = None) -> WatchlistOut:
    return watchlist_out(services.watchlist.list_entries(active=active))


@router.post("", status_code=201)
def add_entry(body: WatchlistEntryIn, admin: AdminOnly, services: Svc) -> WatchlistEntryOut:
    view = services.watchlist.add(
        name=body.name, aliases=body.aliases, list_type=body.list_type, actor=admin.subject
    )
    return entry_out(view)


@router.post("/{entry_id}/deactivate")
def deactivate_entry(entry_id: str, admin: AdminOnly, services: Svc) -> WatchlistEntryOut:
    return entry_out(services.watchlist.deactivate(entry_id=entry_id, actor=admin.subject))
