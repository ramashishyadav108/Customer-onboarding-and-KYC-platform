"""Typed application settings loaded from environment variables (E1-S1 AC4)."""

from pathlib import Path
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
    token_ttl_seconds: int = Field(default=1800, gt=0, validation_alias="TOKEN_TTL_SECONDS")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )
    upload_dir: Path = Field(default=Path("../uploads"), validation_alias="UPLOAD_DIR")
    auto_advance_on_submit: bool = Field(default=True, validation_alias="AUTO_ADVANCE_ON_SUBMIT")
    # auto: clean LOW-risk cases are approved automatically (AC-07); manual: a compliance officer
    # decides every case (AC-15).
    review_policy: Literal["auto", "manual"] = Field(
        default="auto", validation_alias="REVIEW_POLICY"
    )


def load_settings() -> Settings:
    """Build Settings from the environment, naming every offending variable on failure."""
    try:
        return Settings()
    except ValidationError as error:
        problems = sorted(
            {
                f"{'.'.join(str(part) for part in item['loc'])} ({item['msg']})"
                for item in error.errors()
            }
        )
        raise ConfigurationError("Invalid configuration: " + "; ".join(problems)) from None
