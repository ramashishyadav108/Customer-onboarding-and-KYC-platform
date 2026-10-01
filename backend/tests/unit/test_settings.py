"""E1-S1 AC4: typed Settings from environment (F007)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from onboardx.config.settings import ConfigurationError, Settings, load_settings
from onboardx.main import create_app


def test_ac4_missing_database_url_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-04 (E1-S1 AC4): Settings without DATABASE_URL raises an error naming it."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "DATABASE_URL" in str(excinfo.value)


def test_ac4_app_startup_fails_naming_database_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC-04: starting the app with DATABASE_URL unset aborts with a clear message."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigurationError) as excinfo:
        create_app()
    assert "DATABASE_URL" in str(excinfo.value)


def test_ac4_settings_load_typed_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-04: values come from the environment and are typed."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("JWT_SECRET", "synthetic")
    loaded = load_settings()
    assert loaded.database_url == "sqlite:///./x.db"
    assert loaded.log_level == "DEBUG"
    assert loaded.jwt_secret == "synthetic"


def test_ac4_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-04: optional settings have defaults."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    loaded = Settings(_env_file=None)  # type: ignore[call-arg]
    assert loaded.log_level == "INFO"
    assert loaded.jwt_secret is None


def test_ac4_invalid_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """AC-04: an invalid typed value is a ConfigurationError naming the variable."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings()
    assert "LOG_LEVEL" in str(excinfo.value)
