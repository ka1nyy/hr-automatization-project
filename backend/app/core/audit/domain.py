"""Framework-independent immutable audit records and queries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.shared.identifiers import new_uuid
from app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class AuditEvent:
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID
    before_state: Mapping[str, Any] | None = None
    after_state: Mapping[str, Any] | None = None
    reason: str | None = None
    request_id: UUID | None = None
    organization_id: UUID | None = None
    id: UUID = field(default_factory=new_uuid)
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class AuditQuery:
    organization_id: UUID | None = None
    actor_id: UUID | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    action: str | None = None
    page: int = 1
    page_size: int = 20
    sort: str = "-occurredAt"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class AuditPage:
    items: tuple[AuditEvent, ...]
    total: int
