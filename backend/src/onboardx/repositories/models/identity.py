"""User model (seeded by migration 0003)."""

from sqlalchemy.orm import Mapped, mapped_column

from onboardx.repositories.models.base import Base


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str]
    password_hash: Mapped[str]
    role: Mapped[str]
    case_id: Mapped[str | None]
    created_at: Mapped[str]
