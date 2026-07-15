"""Build authentication adapters from validated settings."""

from __future__ import annotations

from app.core.config import Settings
from app.core.security.jwt import JwksJwtAuthenticator, OidcConfiguration
from app.core.security.ports import AuthenticationPort


def build_token_authenticator(settings: Settings) -> AuthenticationPort | None:
    values = (settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)
    if not any(values):
        return None
    if not all(values):
        msg = "SPK_OIDC_ISSUER, SPK_OIDC_AUDIENCE, and SPK_OIDC_JWKS_URL must be set together"
        raise ValueError(msg)
    return JwksJwtAuthenticator(
        OidcConfiguration(
            issuer=settings.oidc_issuer or "",
            audience=settings.oidc_audience or "",
            jwks_url=settings.oidc_jwks_url or "",
            algorithms=tuple(settings.oidc_algorithms),
            jwks_cache_seconds=settings.oidc_jwks_cache_seconds,
        )
    )
