"""Atomic audit and outbox adapter for access-control changes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.audit.service import AuditService
from app.core.events.domain import ApplicationEvent, EventName
from app.core.events.repository import SqlAlchemyTransactionalOutbox
from app.modules.access_control.application.ports import AccessChangeRecorder
from app.modules.access_control.domain.entities import Permission, Role, UserRoleAssignment


def _permission_state(permission: Permission) -> dict[str, object]:
    return {
        "id": str(permission.id),
        "code": permission.code,
        "name": permission.name,
        "description": permission.description,
        "active": permission.active,
        "system": permission.system,
        "revision": permission.revision,
    }


def _role_state(role: Role) -> dict[str, object]:
    return {
        "id": str(role.id),
        "organizationId": str(role.organization_id) if role.organization_id else None,
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "permissionCodes": sorted(role.permission_codes),
        "active": role.active,
        "system": role.system,
        "revision": role.revision,
    }


def _assignment_state(assignment: UserRoleAssignment) -> dict[str, object]:
    return {
        "id": str(assignment.id),
        "userId": str(assignment.user_id),
        "roleId": str(assignment.role_id),
        "scope": {
            "id": str(assignment.scope.id),
            "type": assignment.scope.scope_type.value,
            "organizationId": (
                str(assignment.scope.organization_id) if assignment.scope.organization_id else None
            ),
            "unitIds": sorted(str(unit_id) for unit_id in assignment.scope.unit_ids),
        },
        "effectiveFrom": assignment.effective_from.isoformat(),
        "effectiveTo": assignment.effective_to.isoformat() if assignment.effective_to else None,
        "revokedAt": assignment.revoked_at.isoformat() if assignment.revoked_at else None,
        "revokedBy": str(assignment.revoked_by) if assignment.revoked_by else None,
        "revocationReason": assignment.revocation_reason,
        "revision": assignment.revision,
    }


class SqlAlchemyAccessChangeRecorder(AccessChangeRecorder):
    """Uses the business session so mutations, audit, and events commit atomically."""

    def __init__(self, session: AsyncSession) -> None:
        self._audit = AuditService(SqlAlchemyAuditLog(session))
        self._outbox = SqlAlchemyTransactionalOutbox(session)

    async def role_created(
        self,
        *,
        role: Role,
        actor_id: UUID,
        reason: str | None,
    ) -> None:
        await self._audit.record(
            actor_id=actor_id,
            action="access.role.created",
            entity_type="role",
            entity_id=role.id,
            after_state=_role_state(role),
            reason=reason,
            organization_id=role.organization_id,
        )

    async def role_changed(
        self,
        *,
        role: Role,
        actor_id: UUID,
        action: str,
        reason: str | None,
    ) -> None:
        await self._audit.record(
            actor_id=actor_id,
            action=f"access.role.{action}",
            entity_type="role",
            entity_id=role.id,
            # A deletion has no after-state; the audit row keeps the last known one so the
            # trail still says what was removed.
            after_state=None if action == "deleted" else _role_state(role),
            before_state=_role_state(role) if action == "deleted" else None,
            reason=reason,
            organization_id=role.organization_id,
        )

    async def permission_changed(
        self,
        *,
        permission: Permission,
        actor_id: UUID,
        action: str,
        reason: str | None,
    ) -> None:
        await self._audit.record(
            actor_id=actor_id,
            action=f"access.permission.{action}",
            entity_type="permission",
            entity_id=permission.id,
            after_state=None if action == "deleted" else _permission_state(permission),
            before_state=_permission_state(permission) if action == "deleted" else None,
            reason=reason,
            organization_id=None,
        )

    async def role_assignment_changed(
        self,
        *,
        assignment: UserRoleAssignment,
        actor_id: UUID,
        action: str,
        reason: str | None,
    ) -> None:
        state = _assignment_state(assignment)
        await self._audit.record(
            actor_id=actor_id,
            action=f"access.role_assignment.{action}",
            entity_type="userRoleAssignment",
            entity_id=assignment.id,
            after_state=state,
            reason=reason,
            organization_id=assignment.scope.organization_id,
        )
        await self._outbox.append(
            ApplicationEvent(
                name=EventName.ROLE_ASSIGNMENT_CHANGED,
                aggregate_type="userRoleAssignment",
                aggregate_id=assignment.id,
                payload={
                    "assignmentId": str(assignment.id),
                    "userId": str(assignment.user_id),
                    "roleId": str(assignment.role_id),
                    "organizationId": (
                        str(assignment.scope.organization_id)
                        if assignment.scope.organization_id
                        else None
                    ),
                    "change": action,
                    "revision": assignment.revision,
                },
            )
        )
