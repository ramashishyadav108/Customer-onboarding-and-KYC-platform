"""Shared fixtures: migrated SQLite databases, app factory and token helpers."""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from helpers import JWT_SECRET, sqlite_url
from sqlalchemy import Engine

from onboardx.config.settings import Settings
from onboardx.main import create_app
from onboardx.repositories.database import create_db_engine, upgrade_to_head


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
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
