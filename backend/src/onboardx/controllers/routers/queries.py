"""Analyst queries on a case (AC-13): analysts raise and close, the owning prospect answers."""

from typing import Annotated

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.auth import (
    Principal,
    require_case_access,
    require_case_owner,
    require_role,
)
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.management import MessageIn, QueryListOut, QueryOut, query_out
from onboardx.domain.enums import Role

router = APIRouter(prefix="/api/v1/cases/{case_id}/queries", tags=["queries"])

Analyst = Annotated[Principal, Depends(require_role(Role.KYC_ANALYST))]
Owner = Annotated[Principal, Depends(require_case_owner)]
Reader = Annotated[Principal, Depends(require_case_access)]
Svc = Annotated[Services, Depends(get_services)]


@router.get("")
def list_queries(case_id: str, _reader: Reader, services: Svc) -> QueryListOut:
    return QueryListOut(items=[query_out(v) for v in services.queries.list_for_case(case_id)])


@router.post("", status_code=201)
def raise_query(case_id: str, body: MessageIn, analyst: Analyst, services: Svc) -> QueryOut:
    view = services.queries.raise_query(
        case_id=case_id, message=body.message, actor=analyst.subject
    )
    return query_out(view)


@router.post("/{query_id}/responses", status_code=201)
def respond(case_id: str, query_id: str, body: MessageIn, owner: Owner, services: Svc) -> QueryOut:
    view = services.queries.respond(
        case_id=case_id, query_id=query_id, message=body.message, actor=owner.subject
    )
    return query_out(view)


@router.post("/{query_id}/close")
def close_query(case_id: str, query_id: str, analyst: Analyst, services: Svc) -> QueryOut:
    view = services.queries.close(case_id=case_id, query_id=query_id, actor=analyst.subject)
    return query_out(view)
