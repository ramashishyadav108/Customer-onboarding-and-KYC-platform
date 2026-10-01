"""POST /api/v1/auth/login (public, E1-S2) and /auth/signup (public, AC-14)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.schemas.auth import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    SignupResponse,
)

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


@router.post("/signup", status_code=201)
def signup(
    body: SignupRequest, services: Annotated[Services, Depends(get_services)]
) -> SignupResponse:
    """Create an account: a customer is signed in; a staff request waits for an admin."""
    result = services.signup.signup(username=body.username, password=body.password, role=body.role)
    return SignupResponse(
        status=result.status,
        access_token=result.access_token,
        role=result.role,
        expires_in=result.expires_in,
        case_id=result.case_id,
    )
