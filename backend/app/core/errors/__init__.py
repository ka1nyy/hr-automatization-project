"""Stable domain/application errors and FastAPI adapters."""

from app.core.errors.codes import ErrorCode
from app.core.errors.exceptions import (
    ApplicationError,
    AssignmentDateConflictError,
    ConcurrencyConflictError,
    ConflictError,
    DelegationDateConflictError,
    EmployeeAlreadyAssignedError,
    ForbiddenError,
    OrganizationStructureCycleError,
    OrganizationStructureInvalidRelationshipError,
    OrganizationStructureMultipleRootsError,
    OrganizationStructureNotEditableError,
    OrganizationStructureVersionConflictError,
    ResourceNotFoundError,
    ScopeViolationError,
    SensitiveDataForbiddenError,
    StaffingFteExceededError,
    StaffingSlotNotAvailableError,
    UnauthenticatedError,
    ValidationError,
)
from app.core.errors.handlers import install_exception_handlers

__all__ = [
    "ApplicationError",
    "AssignmentDateConflictError",
    "ConcurrencyConflictError",
    "ConflictError",
    "DelegationDateConflictError",
    "EmployeeAlreadyAssignedError",
    "ErrorCode",
    "ForbiddenError",
    "OrganizationStructureCycleError",
    "OrganizationStructureInvalidRelationshipError",
    "OrganizationStructureMultipleRootsError",
    "OrganizationStructureNotEditableError",
    "OrganizationStructureVersionConflictError",
    "ResourceNotFoundError",
    "ScopeViolationError",
    "SensitiveDataForbiddenError",
    "StaffingFteExceededError",
    "StaffingSlotNotAvailableError",
    "UnauthenticatedError",
    "ValidationError",
    "install_exception_handlers",
]
