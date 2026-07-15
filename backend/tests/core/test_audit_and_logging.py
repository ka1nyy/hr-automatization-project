"""Audit and request correlation preserve integrity without leaking secrets."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.core.audit.domain import AuditEvent, AuditPage
from app.core.audit.repository import SqlAlchemyAuditLog
from app.core.audit.service import AuditService, sanitize_audit_state, sanitize_audit_text
from app.core.logging.context import get_request_id
from app.core.logging.middleware import RequestContextMiddleware
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


class AuditLog:
    def __init__(self) -> None:
        self.events = []

    async def append(self, event):  # type: ignore[no-untyped-def]
        self.events.append(event)

    async def list(self, query):  # type: ignore[no-untyped-def]
        return AuditPage(tuple(self.events), len(self.events))


def test_audit_sanitizer_redacts_nested_sensitive_values() -> None:
    value = sanitize_audit_state(
        {
            "displayName": "Safe",
            "iin": "900101350001",
            "nested": {"accessToken": "secret", "note": "Bearer abc.def"},
        }
    )
    assert value == {
        "displayName": "Safe",
        "iin": "[REDACTED]",
        "nested": {"accessToken": "[REDACTED]", "note": "Bearer [REDACTED]"},
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("password=hunter2", "password=[REDACTED]"),
        ("token: abc.def", "token: [REDACTED]"),
        ("Authorization: Basic xyz", "Authorization: [REDACTED]"),
        ('"client_secret":"shh"', '"client_secret":"[REDACTED]"'),
        ("token expired during password reset", "token expired during password reset"),
    ],
)
def test_audit_text_masks_credential_assignments_without_redacting_prose(
    raw: str, expected: str
) -> None:
    assert sanitize_audit_text(raw) == expected


@pytest.mark.asyncio
async def test_audit_repository_redacts_every_adapter_at_the_persistence_boundary() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = SqlAlchemyAuditLog(session)

    await repository.append(
        AuditEvent(
            actor_id=uuid4(),
            action="organization.changed",
            entity_type="organizationUnit",
            entity_id=uuid4(),
            before_state={
                "customFields": {"iin": "900101350001"},
                "fileContent": "raw document",
                "nested": {"contentBytes": "raw bytes"},
            },
            after_state={"note": "Bearer raw.secret"},
            reason="Approved for 900101350001 using Bearer raw.secret",
        )
    )

    model = session.add.call_args.args[0]
    assert model.before_state == {
        "customFields": {"iin": "[REDACTED]"},
        "fileContent": "[REDACTED]",
        "nested": {"contentBytes": "[REDACTED]"},
    }
    assert model.after_state == {"note": "Bearer [REDACTED]"}
    assert model.reason == "Approved for [REDACTED_IIN] using Bearer [REDACTED]"


@pytest.mark.asyncio
async def test_audit_event_is_append_only_value_and_keeps_request_id() -> None:
    repository = AuditLog()
    service = AuditService(repository)
    event = await service.record(
        actor_id=uuid4(),
        action="organization.changed",
        entity_type="organizationUnit",
        entity_id=uuid4(),
        after_state={"name": "New name", "protectedIin": "900101350001"},
        reason="Approved",
    )
    assert event.after_state == {"name": "New name", "protectedIin": "[REDACTED]"}
    assert event.request_id is not None
    with pytest.raises(AttributeError):
        event.action = "rewritten"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_request_id_is_consistent_in_header_and_envelope() -> None:
    app = FastAPI()

    @app.get("/test")
    async def endpoint():  # type: ignore[no-untyped-def]
        return {"requestId": get_request_id()}

    wrapped = RequestContextMiddleware(app)
    supplied = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=wrapped), base_url="http://test") as client:
        response = await client.get("/test", headers={"X-Request-Id": supplied})
    assert response.headers["X-Request-Id"] == supplied
    assert response.json()["requestId"] == supplied
