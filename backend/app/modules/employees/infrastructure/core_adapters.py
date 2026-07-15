"""Adapters that keep employee application ports independent of core implementations."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.domain import AuditEvent
from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.events.domain import ApplicationEvent, EventName
from app.core.events.repository import SqlAlchemyTransactionalOutbox
from app.core.logging.context import get_request_id

from ..application.ports import AuditEntry, AuditSink, OutboxSink, PendingEvent


def _current_request_uuid() -> UUID | None:
    value = get_request_id()
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


class CoreAuditSink(AuditSink):
    def __init__(self, session: AsyncSession, organization_id: UUID | None = None) -> None:
        self._repository = SqlAlchemyAuditLog(session)
        self._organization_id = organization_id

    async def append(self, entry: AuditEntry) -> None:
        await self._repository.append(
            AuditEvent(
                actor_id=entry.actor_id,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                before_state=entry.before,
                after_state=entry.after,
                reason=entry.reason,
                request_id=_current_request_uuid(),
                organization_id=entry.organization_id or self._organization_id,
            )
        )


class CoreOutboxSink(OutboxSink):
    def __init__(self, session: AsyncSession) -> None:
        self._repository = SqlAlchemyTransactionalOutbox(session)

    async def add(self, event: PendingEvent) -> None:
        await self._repository.append(
            ApplicationEvent(
                name=EventName(event.event_type),
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                payload=event.payload,
            )
        )
