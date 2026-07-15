"""Stable organization errors independent of HTTP and persistence libraries."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID


class OrganizationError(Exception):
    """Base error consumed by the application's centralized error adapter."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        status_code: int = 422,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})
        self.status_code = status_code


class ResourceNotFoundError(OrganizationError):
    def __init__(self, resource: str, resource_id: UUID | str) -> None:
        super().__init__(
            "RESOURCE_NOT_FOUND",
            f"{resource} was not found.",
            details={"resource": resource, "resourceId": str(resource_id)},
            status_code=404,
        )


class PermissionDeniedError(OrganizationError):
    def __init__(self, permission: str, *, scope_violation: bool = False) -> None:
        super().__init__(
            "AUTH_SCOPE_VIOLATION" if scope_violation else "AUTH_FORBIDDEN",
            "The actor is not allowed to perform this operation.",
            details={"permission": permission},
            status_code=403,
        )


class StructureNotEditableError(OrganizationError):
    def __init__(self, version_id: UUID, status: str) -> None:
        super().__init__(
            "ORG_STRUCTURE_NOT_EDITABLE",
            "Only draft structure versions are editable.",
            details={"versionId": str(version_id), "status": status},
            status_code=409,
        )


class ConcurrencyConflictError(OrganizationError):
    def __init__(self, entity: str, entity_id: UUID, expected_revision: int) -> None:
        super().__init__(
            "CONCURRENCY_CONFLICT",
            "The record was changed by another request.",
            details={
                "entity": entity,
                "entityId": str(entity_id),
                "expectedRevision": expected_revision,
            },
            status_code=409,
        )


class StructureCycleError(OrganizationError):
    def __init__(self, *, unit_id: UUID | None = None) -> None:
        details = {"unitId": str(unit_id)} if unit_id is not None else {}
        super().__init__(
            "ORG_STRUCTURE_CYCLE",
            "The operation would create a cycle.",
            details=details,
            status_code=409,
        )


class MultipleRootsError(OrganizationError):
    def __init__(self, *, existing_root_id: UUID | None = None) -> None:
        super().__init__(
            "ORG_STRUCTURE_MULTIPLE_ROOTS",
            "A structure version must contain exactly one active root unit.",
            details={
                "existingRootId": str(existing_root_id) if existing_root_id is not None else None
            },
            status_code=409,
        )


class InvalidRelationshipError(OrganizationError):
    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            "ORG_STRUCTURE_INVALID_RELATIONSHIP",
            message,
            details=details,
            status_code=422,
        )


class VersionConflictError(OrganizationError):
    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            "ORG_STRUCTURE_VERSION_CONFLICT",
            message,
            details=details,
            status_code=409,
        )


class DraftValidationError(OrganizationError):
    def __init__(self, issues: list[Mapping[str, Any]]) -> None:
        super().__init__(
            "VALIDATION_FAILED",
            "The structure draft contains validation errors.",
            details={"issues": [dict(issue) for issue in issues]},
            status_code=422,
        )


class StaffingFteExceededError(OrganizationError):
    def __init__(self, value: str) -> None:
        super().__init__(
            "STAFFING_FTE_EXCEEDED",
            "Staffing slot FTE must be greater than zero and no more than one.",
            details={"fullTimeEquivalent": value},
            status_code=422,
        )


class StaffingSlotNotAvailableError(OrganizationError):
    def __init__(self, slot_id: UUID, status: str) -> None:
        super().__init__(
            "STAFFING_SLOT_NOT_AVAILABLE",
            "The staffing slot is not available for this operation.",
            details={"staffingSlotId": str(slot_id), "status": status},
            status_code=409,
        )
