"""Shared fixtures: migrated SQLite databases, app factory, services and token helpers."""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from helpers import JWT_SECRET, FakeClock, sqlite_url
from onboardx.config.settings import Settings
from onboardx.controllers.dependencies.services import Services
from onboardx.main import create_app
from onboardx.repositories.database import (
    create_db_engine,
    create_session_factory,
    upgrade_to_head,
)
from onboardx.repositories.unit_of_work import UnitOfWorkFactory, make_uow_factory


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One database with every migration applied; copied per test for isolation."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    upgrade_to_head(sqlite_url(path))
    return path


@pytest.fixture
def db_url(migrated_template: Path, tmp_path: Path) -> str:
    target = tmp_path / "test.db"
    shutil.copy(migrated_template, target)
    return sqlite_url(target)


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    eng = create_db_engine(db_url)
    yield eng
    eng.dispose()


@pytest.fixture
def settings(db_url: str) -> Settings:
    return Settings(_env_file=None, database_url=db_url, jwt_secret=JWT_SECRET)  # type: ignore[call-arg]


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def app(settings: Settings, clock: FakeClock) -> FastAPI:
    return create_app(settings, clock=clock)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def services(app: FastAPI) -> Services:
    services: Services = app.state.services
    return services


@pytest.fixture
def uow_factory(engine: Engine) -> UnitOfWorkFactory:
    return make_uow_factory(create_session_factory(engine))
