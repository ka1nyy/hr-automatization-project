"""Isolated OIDC/JWKS bearer-token authentication adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from uuid import UUID

import jwt
from jwt import PyJWKClient

from app.core.errors import UnauthenticatedError
from app.core.security.identity import Principal
from app.shared.identifiers import deterministic_uuid


@dataclass(frozen=True, slots=True)
class OidcConfiguration:
    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...] = ("RS256",)
    jwks_cache_seconds: int = 300


def _strings(value: object) -> frozenset[str]:
    if isinstance(value, str):
        return frozenset(part for part in value.replace(",", " ").split() if part)
    if isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        return frozenset(str(part) for part in value)
    return frozenset()


def _uuid(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise UnauthenticatedError(
            "Authentication token contains an invalid identity claim."
        ) from exc


def _uuid_values(value: object) -> frozenset[UUID]:
    raw_values = value if isinstance(value, list) else []
    try:
        return frozenset(UUID(str(item)) for item in raw_values)
    except ValueError as exc:
        raise UnauthenticatedError("Authentication token contains an invalid scope claim.") from exc


class JwksJwtAuthenticator:
    """Validate provider tokens while exposing only provider-neutral identity fields."""

    def __init__(self, configuration: OidcConfiguration) -> None:
        self._configuration = configuration
        self._jwks = PyJWKClient(
            configuration.jwks_url,
            cache_keys=True,
            lifespan=configuration.jwks_cache_seconds,
        )

    async def authenticate(self, bearer_token: str) -> Principal:
        try:
            signing_key = await asyncio.to_thread(
                self._jwks.get_signing_key_from_jwt,
                bearer_token,
            )
            claims: dict[str, Any] = jwt.decode(
                bearer_token,
                signing_key.key,
                algorithms=list(self._configuration.algorithms),
                audience=self._configuration.audience,
                issuer=self._configuration.issuer,
                options={"require": ["exp", "sub"]},
            )
        except (jwt.PyJWTError, OSError, ValueError) as exc:
            raise UnauthenticatedError("Invalid or expired authentication token.") from exc

        subject = str(claims["sub"])
        permissions = _strings(claims.get("permissions")) | _strings(claims.get("scope"))
        safe_attributes = MappingProxyType(
            {
                "authenticationMethod": "oidc-jwt",
                "issuer": str(claims.get("iss", "")),
            }
        )
        return Principal(
            user_id=_uuid(claims.get("user_id") or claims.get("userId"))
            or deterministic_uuid(f"{self._configuration.issuer}:{subject}"),
            subject=subject,
            organization_id=_uuid(claims.get("organization_id") or claims.get("organizationId")),
            employee_id=_uuid(claims.get("employee_id") or claims.get("employeeId")),
            permissions=permissions,
            role_codes=_strings(claims.get("roles")),
            unit_ids=_uuid_values(claims.get("unit_ids") or claims.get("unitIds")),
            is_service=bool(claims.get("is_service", False)),
            attributes=safe_attributes,
        )
