"""Self sign-up (AC-14): customers get an active prospect account; a requested staff role is created
inactive and pending, and gives no access until an admin approves it (NFR-04)."""

import uuid
from dataclasses import dataclass

from onboardx.domain.admin_rules import parse_signup_role, validate_credentials
from onboardx.domain.entities import User
from onboardx.domain.enums import AuditEvent, Role
from onboardx.domain.errors import UsernameTakenError
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.auth_service import AuthService
from onboardx.services.passwords import hash_password

ACTIVE = "ACTIVE"
PENDING_APPROVAL = "PENDING_APPROVAL"


@dataclass(frozen=True)
class SignupResult:
    status: str
    role: Role
    access_token: str | None
    expires_in: int | None
    case_id: str | None


class SignupService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, audit: AuditService, auth: AuthService
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit
        self._auth = auth

    def signup(self, *, username: str, password: str, role: str | None = None) -> SignupResult:
        validate_credentials(username, password)
        requested = parse_signup_role(role)
        needs_approval = requested is not Role.PROSPECT
        user = User(
            user_id=str(uuid.uuid4()),
            username=username,
            password_hash=hash_password(password),
            role=requested,
            case_id=None,
            active=not needs_approval,
            created_at=to_iso_z(self._clock.now()),
            pending=needs_approval,
        )
        with self._uow_factory() as uow:
            if uow.users.get_by_username(username) is not None:
                raise UsernameTakenError
            uow.users.add(user)
            self._audit.record(
                uow,
                event=AuditEvent.USER_SIGNED_UP,
                actor=user.user_id,
                role=str(requested),
                case_id=None,
                payload={"user_id": user.user_id, "role": str(requested)},
            )
            uow.commit()
        if needs_approval:
            return SignupResult(PENDING_APPROVAL, requested, None, None, None)
        issued = self._auth.issue_token(username, Role.PROSPECT, None)
        return SignupResult(ACTIVE, Role.PROSPECT, issued.access_token, issued.expires_in, None)
