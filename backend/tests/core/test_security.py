"""Development identities are deterministic and impossible in production."""

import pytest
from app.core.config.settings import Environment, Settings
from app.core.security.dev import DevelopmentHeaderAuthenticator
from pydantic import ValidationError


@pytest.mark.asyncio
async def test_development_user_is_deterministic() -> None:
    settings = Settings(
        environment=Environment.DEVELOPMENT,
        dev_auth_enabled=True,
        sensitive_data_key=None,
    )
    authenticator = DevelopmentHeaderAuthenticator(settings)
    first = await authenticator.authenticate({"x-dev-user": "admin"})
    second = await authenticator.authenticate({"x-dev-user": "admin"})
    assert first.user_id == second.user_id
    assert first.permissions == frozenset({"*"})


def test_development_auth_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="development header authentication"):
        Settings(
            environment=Environment.PRODUCTION,
            dev_auth_enabled=True,
            sensitive_data_key="test-key",
        )


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.PRODUCTION,
        "dev_auth_enabled": False,
        "sensitive_data_key": "production-key",
        "oidc_issuer": "https://identity.example.test/",
        "oidc_audience": "spk-api",
        "oidc_jwks_url": "https://identity.example.test/.well-known/jwks.json",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize("key", [None, "", "   "])
def test_production_requires_nonblank_sensitive_data_key(key: str | None) -> None:
    with pytest.raises(ValidationError, match="SPK_SENSITIVE_DATA_KEY must be nonblank"):
        _production_settings(sensitive_data_key=key)


@pytest.mark.parametrize(
    ("setting_name", "environment_name"),
    [
        ("oidc_issuer", "SPK_OIDC_ISSUER"),
        ("oidc_audience", "SPK_OIDC_AUDIENCE"),
        ("oidc_jwks_url", "SPK_OIDC_JWKS_URL"),
    ],
)
def test_production_requires_every_oidc_setting(setting_name: str, environment_name: str) -> None:
    with pytest.raises(ValidationError, match=environment_name):
        _production_settings(**{setting_name: "  "})


def test_complete_production_security_configuration_is_valid() -> None:
    settings = _production_settings()

    assert settings.is_production
