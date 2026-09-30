"""Typed application settings loaded from environment variables (E1-S1 AC4)."""

from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(Exception):
    """Raised at startup when required configuration is missing or invalid."""


class Settings(BaseSettings):
    """Environment-driven settings; values are never hardcoded in source."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    jwt_secret: str | None = Field(default=None, validation_alias="JWT_SECRET")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )


def load_settings() -> Settings:
    """Build Settings from the environment, naming every offending variable on failure."""
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as error:
        problems = sorted(
            {f"{'.'.join(str(part) for part in item['loc'])} ({item['msg']})" for item in error.errors()}
        )
        raise ConfigurationError("Invalid configuration: " + "; ".join(problems)) from None
