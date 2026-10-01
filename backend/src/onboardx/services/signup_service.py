"""Prospect self sign-up (AC-14): creates only prospect accounts; never a staff role."""

import uuid

from onboardx.domain.admin_rules import validate_credentials
from onboardx.domain.entities import User
from onboardx.domain.enums import AuditEvent, Role
from onboardx.domain.errors import UsernameTakenError
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.repositories.unit_of_work import UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.auth_service import AuthService, LoginResult
from onboardx.services.passwords import hash_password


class SignupService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, audit: AuditService, auth: AuthService
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit
        self._auth = auth

    def signup(self, *, username: str, password: str) -> LoginResult:
        validate_credentials(username, password)
        user = User(
            user_id=str(uuid.uuid4()),
            username=username,
            password_hash=hash_password(password),
            role=Role.PROSPECT,
            case_id=None,
            active=True,
            created_at=to_iso_z(self._clock.now()),
        )
        with self._uow_factory() as uow:
            if uow.users.get_by_username(username) is not None:
                raise UsernameTakenError
            uow.users.add(user)
            self._audit.record(
                uow,
                event=AuditEvent.USER_SIGNED_UP,
                actor=user.user_id,
                role=str(Role.PROSPECT),
                case_id=None,
                payload={"user_id": user.user_id, "role": str(Role.PROSPECT)},
            )
            uow.commit()
        issued = self._auth.issue_token(username, Role.PROSPECT, None)
        return LoginResult(issued.access_token, Role.PROSPECT, issued.expires_in, None)
