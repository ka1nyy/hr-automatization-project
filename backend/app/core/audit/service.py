"""Audit recording service with mandatory sensitive-field redaction."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.audit.domain import AuditEvent, AuditPage, AuditQuery
from app.core.audit.ports import AuditLogPort
from app.core.logging.context import get_request_id

_SENSITIVE_FRAGMENTS = (
    "iin",
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "filecontent",
    "contentbytes",
)
_IIN_PATTERN = re.compile(r"(?<!\d)\d{12}(?!\d)")
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_CREDENTIAL_KEYS = (
    r"password|passwd|client[_-]?secret|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|api[_-]?key|authorization|token|secret"
)
_QUOTED_CREDENTIAL_PATTERN = re.compile(
    rf"(?i)(?P<prefix>[\"']?(?:{_CREDENTIAL_KEYS})[\"']?\s*[:=]\s*)"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)"
)
_AUTHORIZATION_SCHEME_PATTERN = re.compile(
    r"(?i)(?P<prefix>[\"']?authorization[\"']?\s*[:=]\s*)"
    r"(?:basic|bearer)\s+[^\s,;}\]]+"
)
_UNQUOTED_CREDENTIAL_PATTERN = re.compile(
    rf"(?i)(?P<prefix>[\"']?(?:{_CREDENTIAL_KEYS})[\"']?\s*[:=]\s*)"
    r"(?![\"']|\[REDACTED\])(?P<value>[^\s,;}\]]+)"
)


def sanitize_audit_text(value: str) -> str:
    """Mask common credentials and Kazakhstan IIN-shaped values in free text."""

    without_assignments = _QUOTED_CREDENTIAL_PATTERN.sub(
        lambda match: (
            f"{match.group('prefix')}{match.group('quote')}[REDACTED]{match.group('quote')}"
        ),
        value,
    )
    without_assignments = _AUTHORIZATION_SCHEME_PATTERN.sub(
        lambda match: f"{match.group('prefix')}[REDACTED]",
        without_assignments,
    )
    without_assignments = _UNQUOTED_CREDENTIAL_PATTERN.sub(
        lambda match: f"{match.group('prefix')}[REDACTED]",
        without_assignments,
    )
    without_tokens = _BEARER_PATTERN.sub("Bearer [REDACTED]", without_assignments)
    return _IIN_PATTERN.sub("[REDACTED_IIN]", without_tokens)


def sanitize_audit_state(value: Any, *, key: str = "") -> Any:
    """Recursively produce JSON-safe state while redacting sensitive material."""

    normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
    if any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(child_key): sanitize_audit_state(child, key=str(child_key))
            for child_key, child in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [sanitize_audit_state(item, key=key) for item in value]
    if isinstance(value, (datetime, date, UUID, Decimal)):
        return str(value)
    if isinstance(value, str):
        return sanitize_audit_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


class AuditService:
    def __init__(self, audit_log: AuditLogPort) -> None:
        self._audit_log = audit_log

    async def record(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID,
        before_state: Mapping[str, Any] | None = None,
        after_state: Mapping[str, Any] | None = None,
        reason: str | None = None,
        organization_id: UUID | None = None,
    ) -> AuditEvent:
        raw_request_id = get_request_id()
        try:
            request_id = UUID(raw_request_id)
        except ValueError:
            request_id = None
        event = AuditEvent(
            organization_id=organization_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=(sanitize_audit_state(before_state) if before_state is not None else None),
            after_state=(sanitize_audit_state(after_state) if after_state is not None else None),
            reason=sanitize_audit_text(reason) if reason is not None else None,
            request_id=request_id,
        )
        await self._audit_log.append(event)
        return event

    async def list_events(self, query: AuditQuery) -> AuditPage:
        return await self._audit_log.list(query)
