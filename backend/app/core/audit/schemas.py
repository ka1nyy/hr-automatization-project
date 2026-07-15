"""API-safe audit DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.shared.api import CamelModel


class AuditEventDto(CamelModel):
    id: UUID
    organization_id: UUID | None
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    reason: str | None
    request_id: UUID | None
    occurred_at: datetime
