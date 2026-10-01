"""Login request and response."""

from pydantic import BaseModel, Field

from onboardx.domain.enums import Role


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - token scheme name, not a secret
    role: Role
    expires_in: int
    case_id: str | None


class SignupRequest(BaseModel):
    """Credentials plus the requested account type; a staff role stays pending until approved."""

    username: str = Field(max_length=100)
    password: str = Field(max_length=200)
    role: str | None = None


class SignupResponse(BaseModel):
    """ACTIVE with a token for customers; PENDING_APPROVAL (no token) for requested staff roles."""

    status: str
    access_token: str | None
    token_type: str = "bearer"  # noqa: S105 - token scheme name, not a secret
    role: Role
    expires_in: int | None
    case_id: str | None
