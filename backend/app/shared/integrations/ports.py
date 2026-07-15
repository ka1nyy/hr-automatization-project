"""Provider-neutral future-integration contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class WorkflowInstance:
    instance_id: str
    process_key: str
    business_key: str


class WorkflowOrchestratorPort(Protocol):
    async def start_process(
        self,
        *,
        process_key: str,
        business_key: str,
        variables: Mapping[str, Any],
    ) -> WorkflowInstance: ...

    async def correlate_message(
        self,
        *,
        message_name: str,
        business_key: str,
        variables: Mapping[str, Any],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class DocumentReference:
    document_id: UUID
    filename: str
    content_type: str
    checksum: str


class DocumentServicePort(Protocol):
    async def store(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        metadata: Mapping[str, str],
    ) -> DocumentReference: ...

    async def read(self, document_id: UUID) -> bytes: ...


@dataclass(frozen=True, slots=True)
class SignatureRequest:
    request_id: str
    document_id: UUID
    signer_user_id: UUID


class SignatureServicePort(Protocol):
    async def request_signature(
        self,
        *,
        document_id: UUID,
        signer_user_id: UUID,
        expires_at: datetime | None = None,
    ) -> SignatureRequest: ...

    async def is_signed(self, request_id: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    recipient_user_ids: tuple[UUID, ...]
    template_key: str
    context: Mapping[str, Any] = field(default_factory=dict)


class NotificationServicePort(Protocol):
    async def send(self, message: NotificationMessage) -> None: ...


class EmploymentRegistryPort(Protocol):
    async def submit_employment_event(
        self,
        *,
        event_id: UUID,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> str: ...


class PayrollIntegrationPort(Protocol):
    async def submit_employee_change(
        self,
        *,
        event_id: UUID,
        employee_id: UUID,
        payload: Mapping[str, Any],
    ) -> str: ...
