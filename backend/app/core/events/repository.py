"""SQLAlchemy outbox repository sharing the business transaction's session."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.service import sanitize_audit_state, sanitize_audit_text
from app.core.errors import ResourceNotFoundError
from app.core.events.domain import ApplicationEvent, EventName, OutboxMessage
from app.core.events.models import OutboxEventModel
from app.shared.time import utc_now


def _to_message(model: OutboxEventModel) -> OutboxMessage:
    return OutboxMessage(
        event=ApplicationEvent(
            id=model.id,
            name=EventName(model.event_name),
            aggregate_type=model.aggregate_type,
            aggregate_id=model.aggregate_id,
            payload=model.payload,
            occurred_at=model.occurred_at,
            schema_version=model.schema_version,
        ),
        attempts=model.attempts,
        available_at=model.available_at,
    )


class SqlAlchemyTransactionalOutbox:
    """No commit is issued here: event and aggregate changes commit atomically."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: ApplicationEvent) -> None:
        safe_payload = sanitize_audit_state(event.payload)
        self._session.add(
            OutboxEventModel(
                id=event.id,
                event_name=event.name.value,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                payload=safe_payload,
                schema_version=event.schema_version,
                occurred_at=event.occurred_at,
                available_at=event.occurred_at,
            )
        )

    async def claim_batch(self, *, limit: int = 100) -> tuple[OutboxMessage, ...]:
        now = utc_now()
        statement = (
            select(OutboxEventModel)
            .where(
                OutboxEventModel.processed_at.is_(None),
                OutboxEventModel.available_at <= now,
            )
            .order_by(OutboxEventModel.occurred_at, OutboxEventModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        models = (await self._session.scalars(statement)).all()
        for model in models:
            model.attempts += 1
        await self._session.flush()
        return tuple(_to_message(model) for model in models)

    async def mark_processed(self, event_id: UUID) -> None:
        model = await self._get_pending(event_id)
        model.processed_at = utc_now()
        model.last_error = None
        await self._session.flush()

    async def mark_failed(
        self,
        event_id: UUID,
        *,
        error: str,
        retry_after: timedelta,
    ) -> None:
        model = await self._get_pending(event_id)
        model.available_at = utc_now() + retry_after
        model.last_error = sanitize_audit_text(error)[:2_000]
        await self._session.flush()

    async def _get_pending(self, event_id: UUID) -> OutboxEventModel:
        statement = select(OutboxEventModel).where(
            OutboxEventModel.id == event_id,
            OutboxEventModel.processed_at.is_(None),
        )
        model = await self._session.scalar(statement)
        if model is None:
            raise ResourceNotFoundError("pending outbox event", event_id)
        return model
