"""Authentication and authorisation dependencies: the ONLY place roles are enforced (NFR-04)."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from onboardx.controllers.dependencies.services import Services, get_services
from onboardx.controllers.error_handlers import ApiError
from onboardx.domain.entities import STAFF_ROLES
from onboardx.domain.enums import Role
from onboardx.domain.errors import AuthenticationError

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    role: Role
    case_id: str | None


def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    services: Annotated[Services, Depends(get_services)],
) -> Principal:
    """Decode the bearer token; missing, malformed or expired tokens are 401."""
    if credentials is None:
        raise ApiError(401, "UNAUTHENTICATED", "Authentication required")
    try:
        claims = services.auth.verify_token(credentials.credentials)
    except AuthenticationError as error:
        raise ApiError(401, "UNAUTHENTICATED", "Authentication required") from error
    return Principal(claims.subject, claims.role, claims.case_id)


def optional_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    services: Annotated[Services, Depends(get_services)],
) -> Principal | None:
    """Public routes that behave differently when a valid token is sent; a bad token is 401."""
    if credentials is None:
        return None
    return current_principal(credentials, services)


def require_role(*roles: Role) -> Callable[..., Principal]:
    """Dependency factory: 403 unless the caller has one of ``roles`` (any role if empty)."""
    allowed = frozenset(roles)

    def dependency(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if allowed and principal.role not in allowed:
            raise ApiError(
                403, "FORBIDDEN", "Role not permitted",
                {"required_roles": sorted(str(r) for r in allowed)},
            )  # fmt: skip
        return principal

    return dependency


def _forbid_other_case(principal: Principal, case_id: str) -> None:
    if principal.case_id != case_id:
        raise ApiError(403, "FORBIDDEN", "Token is bound to a different case")


def require_case_access(
    case_id: str, principal: Annotated[Principal, Depends(current_principal)]
) -> Principal:
    """Owner (prospect token bound to this case) or any staff role."""
    if principal.role is Role.PROSPECT:
        _forbid_other_case(principal, case_id)
    elif principal.role not in STAFF_ROLES:
        raise ApiError(403, "FORBIDDEN", "Role not permitted")
    return principal


def require_case_owner(
    case_id: str, principal: Annotated[Principal, Depends(current_principal)]
) -> Principal:
    """Only the prospect whose token is bound to this case."""
    if principal.role is not Role.PROSPECT:
        raise ApiError(403, "FORBIDDEN", "Role not permitted", {"required_roles": ["prospect"]})
    _forbid_other_case(principal, case_id)
    return principal
