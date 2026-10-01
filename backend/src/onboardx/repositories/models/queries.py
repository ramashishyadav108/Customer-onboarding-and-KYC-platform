"""Analyst query models (append-only, migration 0008)."""

from sqlalchemy.orm import Mapped, mapped_column

from onboardx.repositories.models.base import Base


class CaseQueryModel(Base):
    __tablename__ = "case_queries"

    query_id: Mapped[str] = mapped_column(primary_key=True)
    case_id: Mapped[str]
    raised_by: Mapped[str]
    message: Mapped[str]
    created_at: Mapped[str]


class QueryResponseModel(Base):
    __tablename__ = "query_responses"

    response_id: Mapped[str] = mapped_column(primary_key=True)
    query_id: Mapped[str]
    case_id: Mapped[str]
    author: Mapped[str]
    message: Mapped[str]
    created_at: Mapped[str]


class QueryClosureModel(Base):
    __tablename__ = "query_closures"

    query_id: Mapped[str] = mapped_column(primary_key=True)
    closed_by: Mapped[str]
    created_at: Mapped[str]
