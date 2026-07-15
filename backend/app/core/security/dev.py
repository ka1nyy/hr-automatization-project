"""Deterministic local header authentication, gated to development settings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from app.core.config import Environment, Settings
from app.core.errors import UnauthenticatedError
from app.core.security.identity import Principal
from app.shared.identifiers import deterministic_uuid


@dataclass(frozen=True, slots=True)
class DevelopmentUser:
    handle: str
    role_codes: frozenset[str]
    permissions: frozenset[str] = frozenset()

    @property
    def user_id(self) -> UUID:
        return deterministic_uuid(f"development-user:{self.handle}")


DEFAULT_DEVELOPMENT_USERS: Mapping[str, DevelopmentUser] = {
    "admin": DevelopmentUser("admin", frozenset({"system-administrator"}), frozenset({"*"})),
    "hr": DevelopmentUser("hr", frozenset({"hr-administrator"})),
    "director": DevelopmentUser("director", frozenset({"department-director"})),
    "employee": DevelopmentUser("employee", frozenset({"employee"})),
    "reviewer": DevelopmentUser("reviewer", frozenset({"organization-reviewer"})),
    "publisher": DevelopmentUser("publisher", frozenset({"organization-publisher"})),
    "auditor": DevelopmentUser("auditor", frozenset({"auditor"})),
}


def _optional_uuid(headers: Mapping[str, str], name: str) -> UUID | None:
    raw = headers.get(name)
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError as exc:
        raise UnauthenticatedError("Development identity contains an invalid UUID.") from exc


def _uuid_set(headers: Mapping[str, str], name: str) -> frozenset[UUID]:
    raw = headers.get(name, "")
    try:
        return frozenset(UUID(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise UnauthenticatedError("Development identity contains an invalid unit UUID.") from exc


def _string_set(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.replace(" ", ",").split(",") if item.strip())


class DevelopmentHeaderAuthenticator:
    """Local-only adapter. Settings validation makes production use impossible."""

    def __init__(
        self,
        settings: Settings,
        users: Mapping[str, DevelopmentUser] = DEFAULT_DEVELOPMENT_USERS,
    ) -> None:
        if settings.environment is not Environment.DEVELOPMENT or not settings.dev_auth_enabled:
            msg = "development authentication is disabled"
            raise RuntimeError(msg)
        self._default_user = settings.dev_default_user
        self._users = users

    async def authenticate(self, headers: Mapping[str, str]) -> Principal:
        handle = headers.get("x-dev-user", self._default_user).strip().casefold()
        profile = self._users.get(handle)
        if profile is None:
            raise UnauthenticatedError("Unknown development user.")

        explicit_permissions = _string_set(headers.get("x-dev-permissions", ""))
        permissions = explicit_permissions or profile.permissions
        explicit_roles = _string_set(headers.get("x-dev-roles", ""))
        roles = explicit_roles or profile.role_codes
        return Principal(
            user_id=profile.user_id,
            subject=f"development:{profile.handle}",
            organization_id=_optional_uuid(headers, "x-dev-organization-id"),
            employee_id=_optional_uuid(headers, "x-dev-employee-id"),
            permissions=permissions,
            role_codes=roles,
            unit_ids=_uuid_set(headers, "x-dev-unit-ids"),
            attributes={"authenticationMethod": "development-header"},
        )
