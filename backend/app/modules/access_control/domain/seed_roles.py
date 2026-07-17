"""Deterministic demonstration role definitions; authorization never checks these names."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid5

from app.modules.access_control.domain.permissions import REQUIRED_PERMISSION_CODES

ROLE_ID_NAMESPACE = UUID("6704552d-cee9-4b05-b5f7-d1b6e73a214b")


@dataclass(frozen=True, slots=True)
class SeedRoleDefinition:
    code: str
    name: str
    permission_codes: frozenset[str]

    @property
    def id(self) -> UUID:
        return uuid5(ROLE_ID_NAMESPACE, self.code)


SEED_ROLES: tuple[SeedRoleDefinition, ...] = (
    SeedRoleDefinition(
        code="system-administrator",
        name="System Administrator",
        permission_codes=REQUIRED_PERMISSION_CODES,
    ),
    SeedRoleDefinition(
        code="organization-viewer",
        name="Organization Viewer",
        permission_codes=frozenset(
            {
                "organization.read",
                "organization.structure.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hr-administrator",
        name="HR Administrator",
        permission_codes=frozenset(
            {
                "organization.read",
                "organization.structure.read",
                "organization.structure.draft.create",
                "organization.structure.edit",
                "organization.unit.manage",
                "organization.relationship.manage",
                "organization.staffing.manage",
                "employees.read",
                "employees.read_sensitive",
                "employees.edit",
                "employees.assign",
                "employees.transfer",
                "employees.absence.vacation",
                "employees.absence.sick_leave",
                "employees.absence.business_trip",
                "employees.absence.day_off",
                "employees.absence.cancel",
                "delegations.manage",
                "audit.read",
                "workflow.definition.read",
                "workflow.instance.read",
                "workflow.task.read",
                "workflow.task.act",
                "documents.read",
                "documents.read_sensitive",
                "documents.create",
                "documents.upload",
                "documents.review",
                "documents.sign_request",
                "documents.register",
                "documents.acknowledge",
                "documents.acknowledge_assign",
                "recruitment.request.read",
                "recruitment.request.review_hr",
                "recruitment.vacancy.manage",
                "recruitment.vacancy.publish",
                "recruitment.candidate.read",
                "recruitment.candidate.read_sensitive",
                "recruitment.candidate.manage",
                "recruitment.screen",
                "recruitment.interview.manage",
                "recruitment.offer.manage",
                "recruitment.hiring.manage",
                "termination.read_all",
                "termination.review_hr",
                "termination.complete",
                "hiring.request.create",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.request.dispatch",
                "absence.read_all",
                "absence.read_self",
                "leave.review_hr",
                "leave.balance.manage",
                "business_trip.register",
            }
        ),
    ),
    SeedRoleDefinition(
        code="department-director",
        name="Department Director",
        permission_codes=frozenset(
            {
                "organization.read",
                "organization.structure.read",
                "organization.staffing.manage",
                "employees.read",
                "employees.edit",
                "employees.assign",
                "delegations.manage",
                "recruitment.request.create",
                "recruitment.request.read",
                "recruitment.interview.evaluate",
                "termination.initiate_unit",
                "termination.read_unit",
                "termination.handover",
                "absence.read_unit",
                "absence.read_self",
                "leave.review_manager",
                "business_trip.review_manager",
            }
        ),
    ),
    SeedRoleDefinition(
        code="employee",
        name="Employee",
        permission_codes=frozenset(
            {
                "organization.read",
                "organization.structure.read",
                "employees.read",
                "workflow.task.read",
                "workflow.task.act",
                "documents.read",
                "documents.acknowledge",
                "termination.initiate_self",
                "termination.read_self",
                "absence.read_self",
                "leave.request",
                "business_trip.request",
            }
        ),
    ),
    SeedRoleDefinition(
        code="organization-reviewer",
        name="Organization Reviewer",
        permission_codes=frozenset(
            {
                "organization.read",
                "organization.structure.read",
                "organization.structure.review",
            }
        ),
    ),
    SeedRoleDefinition(
        code="organization-publisher",
        name="Organization Publisher",
        permission_codes=frozenset(
            {
                "organization.read",
                "organization.structure.read",
                "organization.structure.publish",
            }
        ),
    ),
    SeedRoleDefinition(
        code="auditor",
        name="Auditor",
        permission_codes=frozenset(
            {
                "organization.read",
                "organization.structure.read",
                "employees.read",
                "audit.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hr-request-initiator",
        name="Сотрудник HR",
        permission_codes=frozenset(
            {
                "organization.read",
                "organization.structure.read",
                "hiring.request.create",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.request.dispatch",
                "documents.read",
                "documents.read_sensitive",
                "documents.create",
                "documents.upload",
                "audit.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hr-document-management-director",
        name="Директор департамента документооборота и управления персоналом",
        permission_codes=frozenset(
            {
                "organization.read",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.approve.hr_director",
                "documents.read_sensitive",
                "documents.create",
                "documents.upload",
                "audit.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="economic-planning-director",
        name="Директор департамента экономического планирования",
        permission_codes=frozenset(
            {
                "organization.read",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.approve.economic",
                "documents.read_sensitive",
                "audit.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="competition-commission-reviewer",
        name="Конкурсная комиссия",
        permission_codes=frozenset(
            {
                "organization.read",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.approve.commission",
                "documents.read_sensitive",
                "audit.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="legal-department-reviewer",
        name="Юридический департамент",
        permission_codes=frozenset(
            {
                "organization.read",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.approve.legal",
                "documents.read_sensitive",
                "audit.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="management-board-chairman",
        name="Председатель правления",
        permission_codes=frozenset(
            {
                "organization.read",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.approve.chairman",
                "documents.read_sensitive",
                "documents.create",
                "documents.upload",
                "audit.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="accountant",
        name="Бухгалтер",
        permission_codes=frozenset(
            {
                "organization.read",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.request.acknowledge",
                "documents.read_sensitive",
            }
        ),
    ),
    SeedRoleDefinition(
        code="it-department-specialist",
        name="Специалист IT-отдела",
        permission_codes=frozenset(
            {
                "organization.read",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.request.acknowledge",
                "documents.read_sensitive",
            }
        ),
    ),
)
