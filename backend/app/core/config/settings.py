"""Validated runtime settings loaded from ``SPK_`` environment variables."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Self

from pydantic import BeforeValidator, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


def _parse_csv(value: object) -> object:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


CsvList = Annotated[list[str], NoDecode, BeforeValidator(_parse_csv)]


class Settings(BaseSettings):
    """Application settings with secure production defaults."""

    model_config = SettingsConfigDict(
        env_prefix="SPK_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "SPK Ertis Corporate HR API"
    environment: Environment = Environment.DEVELOPMENT
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://spk:spk@localhost:5432/spk_hr"
    database_echo: bool = False
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=100)
    sensitive_data_key: SecretStr | None = None
    log_level: str = "INFO"
    cors_origins: CsvList = Field(default_factory=lambda: ["http://localhost:5173"])
    frontend_dist_path: str | None = None

    dev_auth_enabled: bool = False
    dev_default_user: str = "admin"

    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_algorithms: CsvList = Field(default_factory=lambda: ["RS256"])
    oidc_jwks_cache_seconds: int = Field(default=300, ge=30, le=86_400)

    @model_validator(mode="after")
    def validate_security_mode(self) -> Self:
        if self.dev_auth_enabled and self.environment is not Environment.DEVELOPMENT:
            msg = "development header authentication can only run in development"
            raise ValueError(msg)
        if self.is_production:
            if (
                self.sensitive_data_key is None
                or not self.sensitive_data_key.get_secret_value().strip()
            ):
                msg = "SPK_SENSITIVE_DATA_KEY must be nonblank in production"
                raise ValueError(msg)
            oidc_settings = {
                "SPK_OIDC_ISSUER": self.oidc_issuer,
                "SPK_OIDC_AUDIENCE": self.oidc_audience,
                "SPK_OIDC_JWKS_URL": self.oidc_jwks_url,
            }
            missing = [
                name for name, value in oidc_settings.items() if not value or not value.strip()
            ]
            if missing:
                msg = f"production requires complete OIDC settings; missing: {', '.join(missing)}"
                raise ValueError(msg)
        return self

    @property
    def is_development(self) -> bool:
        return self.environment is Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    def require_sensitive_data_key(self) -> str:
        """Reveal the encryption key only at the adapter construction boundary."""

        if (
            self.sensitive_data_key is None
            or not self.sensitive_data_key.get_secret_value().strip()
        ):
            msg = "SPK_SENSITIVE_DATA_KEY is not configured"
            raise RuntimeError(msg)
        return self.sensitive_data_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
