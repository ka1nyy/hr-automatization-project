"""Audit persistence port."""

from __future__ import annotations

from typing import Protocol

from app.core.audit.domain import AuditEvent, AuditPage, AuditQuery


class AuditLogPort(Protocol):
    async def append(self, event: AuditEvent) -> None: ...

    async def list(self, query: AuditQuery) -> AuditPage: ...
