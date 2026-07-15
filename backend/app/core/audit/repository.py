"""SQLAlchemy implementation of the append-only audit port."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.domain import AuditEvent, AuditPage, AuditQuery
from app.core.audit.models import AuditEventModel
from app.core.audit.service import sanitize_audit_state, sanitize_audit_text


def _to_domain(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=model.id,
        organization_id=model.organization_id,
        actor_id=model.actor_id,
        action=model.action,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        before_state=model.before_state,
        after_state=model.after_state,
        reason=model.reason,
        request_id=model.request_id,
        occurred_at=model.occurred_at,
    )


class SqlAlchemyAuditLog:
    """The caller's session makes audit writes atomic with the business change."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, audit_event: AuditEvent) -> None:
        safe_before = (
            cast(dict[str, Any], sanitize_audit_state(audit_event.before_state))
            if audit_event.before_state is not None
            else None
        )
        safe_after = (
            cast(dict[str, Any], sanitize_audit_state(audit_event.after_state))
            if audit_event.after_state is not None
            else None
        )
        self._session.add(
            AuditEventModel(
                id=audit_event.id,
                organization_id=audit_event.organization_id,
                actor_id=audit_event.actor_id,
                action=audit_event.action,
                entity_type=audit_event.entity_type,
                entity_id=audit_event.entity_id,
                before_state=safe_before,
                after_state=safe_after,
                reason=(
                    sanitize_audit_text(audit_event.reason)
                    if audit_event.reason is not None
                    else None
                ),
                request_id=audit_event.request_id,
                occurred_at=audit_event.occurred_at,
            )
        )

    async def list(self, query: AuditQuery) -> AuditPage:
        filters = []
        if query.organization_id is not None:
            filters.append(AuditEventModel.organization_id == query.organization_id)
        if query.actor_id is not None:
            filters.append(AuditEventModel.actor_id == query.actor_id)
        if query.entity_type is not None:
            filters.append(AuditEventModel.entity_type == query.entity_type)
        if query.entity_id is not None:
            filters.append(AuditEventModel.entity_id == query.entity_id)
        if query.action is not None:
            filters.append(AuditEventModel.action == query.action)

        count_statement = select(func.count()).select_from(AuditEventModel).where(*filters)
        total = int((await self._session.scalar(count_statement)) or 0)
        sort_column: Any = {
            "occurredAt": AuditEventModel.occurred_at.asc(),
            "-occurredAt": AuditEventModel.occurred_at.desc(),
            "action": AuditEventModel.action.asc(),
            "-action": AuditEventModel.action.desc(),
            "entityType": AuditEventModel.entity_type.asc(),
            "-entityType": AuditEventModel.entity_type.desc(),
        }[query.sort]
        statement = (
            select(AuditEventModel)
            .where(*filters)
            .order_by(sort_column, AuditEventModel.id.asc())
            .offset(query.offset)
            .limit(query.page_size)
        )
        models = (await self._session.scalars(statement)).all()
        return AuditPage(items=tuple(_to_domain(model) for model in models), total=total)
