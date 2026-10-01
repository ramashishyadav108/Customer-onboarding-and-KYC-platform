"""Declarative base. Schema is owned by Alembic migrations; models never create tables."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models (persistence only, never returned to services)."""
