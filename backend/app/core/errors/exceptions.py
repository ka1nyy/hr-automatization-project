"""Framework-independent application exceptions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.errors.codes import ErrorCode

ErrorDetails = Mapping[str, Any]


class ApplicationError(Exception):
    """Expected domain/application failure safe to return through the API."""

    default_code = ErrorCode.VALIDATION_FAILED
    default_message = "The operation could not be completed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: ErrorCode | None = None,
        details: ErrorDetails | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.message = message or self.default_message
        self.details = dict(details or {})
        super().__init__(self.message)


class UnauthenticatedError(ApplicationError):
    default_code = ErrorCode.AUTH_UNAUTHENTICATED
    default_message = "Authentication is required."


class ForbiddenError(ApplicationError):
    default_code = ErrorCode.AUTH_FORBIDDEN
    default_message = "You do not have permission to perform this operation."


class ScopeViolationError(ApplicationError):
    default_code = ErrorCode.AUTH_SCOPE_VIOLATION
    default_message = "The requested resource is outside your access scope."


class ResourceNotFoundError(ApplicationError):
    default_code = ErrorCode.RESOURCE_NOT_FOUND
    default_message = "The requested resource was not found."

    def __init__(self, resource: str, resource_id: object | None = None) -> None:
        details: dict[str, Any] = {"resource": resource}
        if resource_id is not None:
            details["resourceId"] = str(resource_id)
        super().__init__(details=details)


class ValidationError(ApplicationError):
    default_code = ErrorCode.VALIDATION_FAILED
    default_message = "The request failed validation."

    def __init__(
        self,
        message: str | None = None,
        *,
        problems: Sequence[Mapping[str, Any]] | None = None,
        details: ErrorDetails | None = None,
        code: ErrorCode | None = None,
    ) -> None:
        combined = dict(details or {})
        if problems is not None:
            combined["problems"] = [dict(problem) for problem in problems]
        super().__init__(message, code=code, details=combined)


class ConflictError(ApplicationError):
    """State conflict with a caller-selectable stable conflict code."""

    default_code = ErrorCode.CONCURRENCY_CONFLICT
    default_message = "The resource state conflicts with this operation."


class ConcurrencyConflictError(ConflictError):
    default_code = ErrorCode.CONCURRENCY_CONFLICT
    default_message = "The resource was changed by another operation."


class OrganizationStructureNotEditableError(ConflictError):
    default_code = ErrorCode.ORG_STRUCTURE_NOT_EDITABLE
    default_message = "Only draft organization structures can be edited."


class OrganizationStructureCycleError(ConflictError):
    default_code = ErrorCode.ORG_STRUCTURE_CYCLE
    default_message = "The operation would create a cycle."


class OrganizationStructureMultipleRootsError(ConflictError):
    default_code = ErrorCode.ORG_STRUCTURE_MULTIPLE_ROOTS
    default_message = "An organization structure must have exactly one root."


class OrganizationStructureInvalidRelationshipError(ConflictError):
    default_code = ErrorCode.ORG_STRUCTURE_INVALID_RELATIONSHIP
    default_message = "The organization relationship is invalid."


class OrganizationStructureVersionConflictError(ConflictError):
    default_code = ErrorCode.ORG_STRUCTURE_VERSION_CONFLICT
    default_message = "The organization structure version conflicts with an active version."


class StaffingSlotNotAvailableError(ConflictError):
    default_code = ErrorCode.STAFFING_SLOT_NOT_AVAILABLE
    default_message = "The staffing slot is not available for this operation."


class StaffingFteExceededError(ConflictError):
    default_code = ErrorCode.STAFFING_FTE_EXCEEDED
    default_message = "The staffing slot full-time-equivalent capacity would be exceeded."


class EmployeeAlreadyAssignedError(ConflictError):
    default_code = ErrorCode.EMPLOYEE_ALREADY_ASSIGNED
    default_message = "The employee already has a conflicting assignment."


class AssignmentDateConflictError(ConflictError):
    default_code = ErrorCode.ASSIGNMENT_DATE_CONFLICT
    default_message = "The assignment dates conflict with an existing record."


class DelegationDateConflictError(ConflictError):
    default_code = ErrorCode.DELEGATION_DATE_CONFLICT
    default_message = "The delegation dates conflict with an existing delegation."


class SensitiveDataForbiddenError(ForbiddenError):
    default_code = ErrorCode.SENSITIVE_DATA_FORBIDDEN
    default_message = "Permission to access sensitive data is required."
