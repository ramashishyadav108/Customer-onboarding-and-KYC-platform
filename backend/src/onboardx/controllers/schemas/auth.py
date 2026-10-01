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
    """Only credentials: any other field (such as a role) is ignored, never read."""

    username: str = Field(max_length=100)
    password: str = Field(max_length=200)
