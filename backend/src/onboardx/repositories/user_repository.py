"""Read-only user lookup."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from onboardx.domain.entities import User
from onboardx.domain.enums import Role
from onboardx.repositories.models.identity import UserModel


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> User | None:
        query = select(UserModel).where(UserModel.username == username)
        row = self._session.scalars(query).first()
        if row is None:
            return None
        return User(row.user_id, row.username, row.password_hash, Role(row.role), row.case_id)
