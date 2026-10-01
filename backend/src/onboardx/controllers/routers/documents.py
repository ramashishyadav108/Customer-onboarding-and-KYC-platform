"""Document endpoints: upload (owner), list (owner or staff) and reject (kyc-analyst)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from onboardx.controllers.dependencies.auth import (
    Principal,
    require_case_access,
    require_case_owner,
    require_role,
)
from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.error_handlers import ApiError
from onboardx.controllers.schemas.pipeline import (
    DocumentListOut,
    RejectRequest,
    RejectResponse,
    UploadResponse,
    document_list_out,
    reject_out,
    upload_out,
)
from onboardx.domain.documents import MAX_UPLOAD_BYTES
from onboardx.domain.enums import Role

router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.post("/cases/{case_id}/documents", status_code=201)
async def upload_document(
    case_id: str,
    principal: Annotated[Principal, Depends(require_case_owner)],
    services: Annotated[Services, Depends(get_services)],
    checklist_item: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> UploadResponse:
    """Read at most the limit plus one byte so oversize files are rejected without buffering."""
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    view = await run_in_threadpool(
        services.documents.upload,
        case_id=case_id,
        actor=principal.subject,
        checklist_item=checklist_item,
        filename=file.filename or "",
        content_type=file.content_type,
        content=content,
    )
    return upload_out(view)


@router.get("/cases/{case_id}/documents")
def list_documents(
    case_id: str,
    principal: Annotated[Principal, Depends(require_case_access)],
    services: Annotated[Services, Depends(get_services)],
    include_superseded: bool = False,
) -> DocumentListOut:
    if include_superseded and principal.role is Role.PROSPECT:
        raise ApiError(403, "FORBIDDEN", "Only staff may list superseded versions")
    views = services.documents.list_documents(case_id, include_superseded=include_superseded)
    return document_list_out(case_id, views)


@router.post("/cases/{case_id}/documents/{document_id}/reject")
def reject_document(
    case_id: str,
    document_id: str,
    body: RejectRequest,
    principal: Annotated[Principal, Depends(require_role(Role.KYC_ANALYST))],
    services: Annotated[Services, Depends(get_services)],
) -> RejectResponse:
    rejection = services.documents.reject(
        case_id=case_id,
        document_id=document_id,
        actor=principal.subject,
        reason_code=body.reason_code,
        comment=body.comment,
    )
    return reject_out(rejection)
