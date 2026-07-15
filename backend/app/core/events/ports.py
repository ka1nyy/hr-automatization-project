"""Transactional outbox application port."""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol
from uuid import UUID

from app.core.events.domain import ApplicationEvent, OutboxMessage


class TransactionalOutboxPort(Protocol):
    async def append(self, event: ApplicationEvent) -> None: ...

    async def claim_batch(self, *, limit: int = 100) -> tuple[OutboxMessage, ...]: ...

    async def mark_processed(self, event_id: UUID) -> None: ...

    async def mark_failed(
        self,
        event_id: UUID,
        *,
        error: str,
        retry_after: timedelta,
    ) -> None: ...
