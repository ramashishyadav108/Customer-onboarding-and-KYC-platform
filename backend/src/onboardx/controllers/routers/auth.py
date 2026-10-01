"""POST /api/v1/auth/login (public, E1-S2)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(
    body: LoginRequest, services: Annotated[Services, Depends(get_services)]
) -> LoginResponse:
    result = services.auth.login(body.username, body.password)
    return LoginResponse(
        access_token=result.access_token,
        role=result.role,
        expires_in=result.expires_in,
        case_id=result.case_id,
    )
