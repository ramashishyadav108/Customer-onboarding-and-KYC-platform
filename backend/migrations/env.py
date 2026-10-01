"""Alembic environment. The database URL comes from Settings (DATABASE_URL), never from ini."""

from alembic import context
from sqlalchemy import Connection

from onboardx.config.settings import load_settings
from onboardx.repositories.database import create_db_engine


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    url = context.config.attributes.get("database_url") or load_settings().database_url
    engine = create_db_engine(url)
    try:
        with engine.begin() as new_connection:
            _run(new_connection)
    finally:
        engine.dispose()


run_migrations_online()
