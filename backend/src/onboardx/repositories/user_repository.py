"""User lookup and administration (AC-11); users are never deleted, only deactivated."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from onboardx.domain.entities import User
from onboardx.domain.enums import Role
from onboardx.repositories.models.identity import UserModel


def _to_user(row: UserModel) -> User:
    return User(
        row.user_id,
        row.username,
        row.password_hash,
        Role(row.role),
        row.case_id,
        bool(row.active),
        row.created_at,
        bool(row.pending),
    )


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> User | None:
        query = select(UserModel).where(UserModel.username == username)
        row = self._session.scalars(query).first()
        return None if row is None else _to_user(row)

    def get(self, user_id: str) -> User | None:
        row = self._session.get(UserModel, user_id)
        return None if row is None else _to_user(row)

    def list_all(self) -> list[User]:
        query = select(UserModel).order_by(UserModel.created_at, UserModel.username)
        return [_to_user(row) for row in self._session.scalars(query)]

    def add(self, user: User) -> None:
        self._session.add(
            UserModel(
                user_id=user.user_id,
                username=user.username,
                password_hash=user.password_hash,
                role=str(user.role),
                case_id=user.case_id,
                created_at=user.created_at,
                active=int(user.active),
                pending=int(user.pending),
            )
        )
        self._session.flush()

    def set_role(self, user_id: str, role: Role) -> None:
        statement = update(UserModel).where(UserModel.user_id == user_id).values(role=str(role))
        self._session.execute(statement)

    def set_active(self, user_id: str, active: bool) -> None:
        statement = update(UserModel).where(UserModel.user_id == user_id).values(active=int(active))
        self._session.execute(statement)

    def approve(self, user_id: str, role: Role) -> None:
        """Activate a pending staff account with the (possibly adjusted) role."""
        statement = (
            update(UserModel)
            .where(UserModel.user_id == user_id)
            .values(active=1, pending=0, role=str(role))
        )
        self._session.execute(statement)

    def close_request(self, user_id: str) -> None:
        """Reject a pending request: it stays inactive and is no longer pending."""
        statement = update(UserModel).where(UserModel.user_id == user_id).values(pending=0)
        self._session.execute(statement)

    def set_case(self, user_id: str, case_id: str) -> None:
        """Link a prospect account to its single case (AC-14.3)."""
        statement = update(UserModel).where(UserModel.user_id == user_id).values(case_id=case_id)
        self._session.execute(statement)

    def count_active_admins(self) -> int:
        query = (
            select(func.count())
            .select_from(UserModel)
            .where(UserModel.role == str(Role.ADMIN), UserModel.active == 1)
        )
        return int(self._session.scalar(query) or 0)
