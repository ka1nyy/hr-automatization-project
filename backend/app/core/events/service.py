"""Application-facing event recorder."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from app.core.audit.service import sanitize_audit_state
from app.core.events.domain import ApplicationEvent, EventName
from app.core.events.ports import TransactionalOutboxPort


class ApplicationEventRecorder:
    def __init__(self, outbox: TransactionalOutboxPort) -> None:
        self._outbox = outbox

    async def record(
        self,
        *,
        name: EventName,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: Mapping[str, Any],
    ) -> ApplicationEvent:
        event = ApplicationEvent(
            name=name,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=sanitize_audit_state(payload),
        )
        await self._outbox.append(event)
        return event
