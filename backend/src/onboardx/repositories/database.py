"""SQLite engine and session factory plus the Alembic upgrade entry point."""

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from onboardx.config.constants import ALEMBIC_INI, MIGRATIONS_DIR


def is_in_memory(url: str) -> bool:
    parsed = make_url(url)
    return parsed.get_backend_name() == "sqlite" and parsed.database in (None, "", ":memory:")


def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(url: str) -> Engine:
    """Create a SQLite engine with foreign keys enforced; in-memory uses one shared connection."""
    kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
    if is_in_memory(url):
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    event.listen(engine, "connect", _enable_foreign_keys)
    return engine


def create_session_factory(engine: Engine) -> "sessionmaker[Session]":
    return sessionmaker(bind=engine, expire_on_commit=False)


def upgrade_to_head(target: str | Engine, script_location: Path | None = None) -> None:
    """Apply every migration to a database URL or an existing engine."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(script_location or MIGRATIONS_DIR))
    if isinstance(target, Engine):
        with target.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    else:
        config.attributes["database_url"] = target
        command.upgrade(config, "head")
