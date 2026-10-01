"""Admin user and role management (AC-11, AC-14.9): audited, never exposes hashes."""

import uuid

from onboardx.domain.admin_rules import parse_staff_role, validate_new_user
from onboardx.domain.entities import User
from onboardx.domain.enums import AuditEvent, Role
from onboardx.domain.errors import (
    LastAdminError,
    NotFoundError,
    NotPendingError,
    SelfModificationError,
    UsernameTakenError,
)
from onboardx.domain.ports import Clock
from onboardx.domain.timeutil import to_iso_z
from onboardx.domain.views import UserView
from onboardx.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory
from onboardx.services.audit_service import AuditService
from onboardx.services.passwords import hash_password


def _status(user: User) -> str:
    if user.pending:
        return "PENDING"
    return "ACTIVE" if user.active else "DEACTIVATED"


def _view(user: User) -> UserView:
    return UserView(
        user.user_id, user.username, str(user.role), user.active, user.created_at, _status(user)
    )


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
        return self._reload(user_id)

    def deactivate(self, *, user_id: str, actor: str) -> UserView:
        with self._uow_factory() as uow:
            user = self._target(uow, user_id, actor)
            if user.role is Role.ADMIN and user.active:
                self._require_other_admin(uow, user)
            uow.users.set_active(user_id, False)
            self._record(uow, AuditEvent.USER_DEACTIVATED, actor, user_id, {"role": str(user.role)})
            uow.commit()
        return self._reload(user_id)

    def reactivate(self, *, user_id: str, actor: str) -> UserView:
        with self._uow_factory() as uow:
            user = self._target(uow, user_id, actor)
            uow.users.set_active(user_id, True)
            self._record(uow, AuditEvent.USER_REACTIVATED, actor, user_id, {"role": str(user.role)})
            uow.commit()
        return self._reload(user_id)

    def approve(self, *, user_id: str, role: str | None, actor: str) -> UserView:
        """Activate a staff sign-up request, optionally with a different staff role (AC-14.9)."""
        chosen = None if role is None else parse_staff_role(role, "role")
        with self._uow_factory() as uow:
            user = self._pending(uow, user_id)
            final = chosen or user.role
            uow.users.approve(user_id, final)
            payload = {"requested_role": str(user.role), "role": str(final)}
            self._record(uow, AuditEvent.USER_APPROVED, actor, user_id, payload)
            uow.commit()
        return self._reload(user_id)

    def reject(self, *, user_id: str, actor: str) -> UserView:
        """Close a staff sign-up request; the account stays inactive (AC-14.9)."""
        with self._uow_factory() as uow:
            user = self._pending(uow, user_id)
            uow.users.close_request(user_id)
            self._record(uow, AuditEvent.USER_REJECTED, actor, user_id, {"role": str(user.role)})
            uow.commit()
        return self._reload(user_id)

    def _reload(self, user_id: str) -> UserView:
        with self._uow_factory() as uow:
            user = uow.users.get(user_id)
        if user is None:
            raise NotFoundError("user")
        return _view(user)

    def _pending(self, uow: UnitOfWork, user_id: str) -> User:
        user = uow.users.get(user_id)
        if user is None:
            raise NotFoundError("user")
        if not user.pending:
            raise NotPendingError
        return user

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
