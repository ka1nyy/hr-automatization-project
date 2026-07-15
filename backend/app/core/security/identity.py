"""Authentication identity contract shared with authorization use cases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated caller identity; authorization remains database-authoritative."""

    user_id: UUID
    subject: str
    organization_id: UUID | None = None
    employee_id: UUID | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    role_codes: frozenset[str] = field(default_factory=frozenset)
    unit_ids: frozenset[UUID] = field(default_factory=frozenset)
    is_service: bool = False
    attributes: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def has_permission(self, permission: str) -> bool:
        return "*" in self.permissions or permission in self.permissions
