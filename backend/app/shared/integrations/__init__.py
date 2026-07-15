"""Ports reserved for later modules; no external adapter is implemented in Module 1."""

from app.shared.integrations.ports import (
    DocumentReference,
    DocumentServicePort,
    EmploymentRegistryPort,
    NotificationMessage,
    NotificationServicePort,
    PayrollIntegrationPort,
    SignatureRequest,
    SignatureServicePort,
    WorkflowInstance,
    WorkflowOrchestratorPort,
)

__all__ = [
    "DocumentReference",
    "DocumentServicePort",
    "EmploymentRegistryPort",
    "NotificationMessage",
    "NotificationServicePort",
    "PayrollIntegrationPort",
    "SignatureRequest",
    "SignatureServicePort",
    "WorkflowInstance",
    "WorkflowOrchestratorPort",
]
