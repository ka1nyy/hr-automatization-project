"""Stable permission identifiers exposed by Module 1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    code: str
    name: str
    description: str


PERMISSION_CATALOG: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("organization.read", "Read organization", "View organization details."),
    PermissionDefinition(
        "organization.structure.read",
        "Read organization structures",
        "View current and historical structures.",
    ),
    PermissionDefinition(
        "organization.structure.draft.create",
        "Create structure drafts",
        "Create a draft structure version.",
    ),
    PermissionDefinition(
        "organization.structure.edit",
        "Edit structure drafts",
        "Edit an organization structure draft.",
    ),
    PermissionDefinition(
        "organization.structure.review",
        "Review structure drafts",
        "Submit, approve, or return a draft.",
    ),
    PermissionDefinition(
        "organization.structure.publish",
        "Publish structures",
        "Publish a validated structure version.",
    ),
    PermissionDefinition(
        "organization.unit.manage", "Manage units", "Create, edit, move, and deactivate units."
    ),
    PermissionDefinition(
        "organization.relationship.manage",
        "Manage relationships",
        "Maintain additional organization relationships.",
    ),
    PermissionDefinition(
        "organization.staffing.manage", "Manage staffing", "Create, edit, and close staffing slots."
    ),
    PermissionDefinition("employees.read", "Read employees", "View non-sensitive employee data."),
    PermissionDefinition(
        "employees.read_sensitive",
        "Read sensitive employee data",
        "View explicitly protected employee fields.",
    ),
    PermissionDefinition("employees.create", "Create employees", "Create employee draft records."),
    PermissionDefinition("employees.edit", "Edit employees", "Edit employee records."),
    PermissionDefinition(
        "employees.assign", "Assign employees", "Create and end employee assignments."
    ),
    PermissionDefinition(
        "delegations.manage", "Manage delegations", "Create and revoke temporary delegations."
    ),
    PermissionDefinition(
        "roles.manage", "Manage roles", "Create roles and maintain role assignments."
    ),
    PermissionDefinition("audit.read", "Read audit history", "View immutable audit events."),
)

REQUIRED_PERMISSION_CODES: frozenset[str] = frozenset(item.code for item in PERMISSION_CATALOG)
