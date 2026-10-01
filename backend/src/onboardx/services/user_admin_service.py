"""Admin user and role management (AC-11): audited, never exposes hashes (NFR-03, NFR-04)."""

import uuid

from onboardx.domain.admin_rules import parse_staff_role, validate_new_user
from onboardx.domain.entities import User
from onboardx.domain.enums import AuditEvent, Role
from onboardx.domain.errors import (
    LastAdminError,
    NotFoundError,
    SelfModificationError,
    UsernameTakenError,
)
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.domain.views import UserView
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.passwords import hash_password


def _view(user: User) -> UserView:
    return UserView(user.user_id, user.username, str(user.role), user.active, user.created_at)


class UserAdminService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, audit: AuditService) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit = audit

    def list_users(self) -> list[UserView]:
        with self._uow_factory() as uow:
            return [_view(user) for user in uow.users.list_all()]

    def create(self, *, username: str, password: str, role: str, actor: str) -> UserView:
        parsed = validate_new_user(username, password, role)
        user = User(
            user_id=str(uuid.uuid4()),
            username=username,
            password_hash=hash_password(password),
            role=parsed,
            case_id=None,
            active=True,
            created_at=to_iso_z(self._clock.now()),
        )
        with self._uow_factory() as uow:
            if uow.users.get_by_username(username) is not None:
                raise UsernameTakenError
            uow.users.add(user)
            self._record(uow, AuditEvent.USER_CREATED, actor, user.user_id, {"role": str(parsed)})
            uow.commit()
        return _view(user)

    def change_role(self, *, user_id: str, role: str, actor: str) -> UserView:
        parsed = parse_staff_role(role, "role")
        assert parsed is not None  # noqa: S101 - parse_staff_role raises when problems is None
        with self._uow_factory() as uow:
            user = self._target(uow, user_id, actor)
            if user.role is Role.ADMIN and parsed is not Role.ADMIN:
                self._require_other_admin(uow, user)
            uow.users.set_role(user_id, parsed)
            payload = {"from_role": str(user.role), "to_role": str(parsed)}
            self._record(uow, AuditEvent.USER_ROLE_CHANGED, actor, user_id, payload)
            uow.commit()
        return _view(
            User(user.user_id, user.username, "", parsed, None, user.active, user.created_at)
        )

    def deactivate(self, *, user_id: str, actor: str) -> UserView:
        with self._uow_factory() as uow:
            user = self._target(uow, user_id, actor)
            if user.role is Role.ADMIN and user.active:
                self._require_other_admin(uow, user)
            uow.users.set_active(user_id, False)
            self._record(uow, AuditEvent.USER_DEACTIVATED, actor, user_id, {"role": str(user.role)})
            uow.commit()
        return _view(User(user.user_id, user.username, "", user.role, None, False, user.created_at))

    def reactivate(self, *, user_id: str, actor: str) -> UserView:
        with self._uow_factory() as uow:
            user = self._target(uow, user_id, actor)
            uow.users.set_active(user_id, True)
            self._record(uow, AuditEvent.USER_REACTIVATED, actor, user_id, {"role": str(user.role)})
            uow.commit()
        return _view(User(user.user_id, user.username, "", user.role, None, True, user.created_at))

    def _target(self, uow: UnitOfWork, user_id: str, actor: str) -> User:
        """Load the target; an admin may not modify their own account."""
        user = uow.users.get(user_id)
        if user is None:
            raise NotFoundError("user")
        if user.username == actor:
            raise SelfModificationError
        return user

    def _require_other_admin(self, uow: UnitOfWork, user: User) -> None:
        """Removing an active admin needs another active admin to remain (AC-11.6)."""
        remaining = uow.users.count_active_admins() - (1 if user.active else 0)
        if remaining < 1:
            raise LastAdminError

    def _record(
        self, uow: UnitOfWork, event: AuditEvent, actor: str, user_id: str, extra: dict[str, str]
    ) -> None:
        """Audit holds ids and role names only; never usernames' secrets or hashes."""
        self._audit.record(
            uow,
            event=event,
            actor=actor,
            role=str(Role.ADMIN),
            case_id=None,
            payload={"user_id": user_id, **extra},
        )
