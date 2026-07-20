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
                "termination.exit_interview.manage",
                "hiring.request.create",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.request.dispatch",
                "absence.read_all",
                "absence.read_self",
                "leave.review_hr",
                "leave.balance.manage",
                "business_trip.register",
                "regulated_hiring.read",
                "regulated_hiring.start",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "regulated_hiring.authority.manage",
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
                "regulated_hiring.read",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
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
                "employees.read",
                "employees.lifecycle.override",
                "hiring.request.create",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.request.dispatch",
                "documents.read",
                "documents.read_sensitive",
                "documents.create",
                "documents.upload",
                "documents.register",
                "absence.read_all",
                "leave.review_hr",
                "business_trip.register",
                "termination.initiate_unit",
                "termination.read_all",
                "termination.review_hr",
                "termination.complete",
                "termination.exit_interview.manage",
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
                "organization.structure.read",
                "employees.read",
                "employees.lifecycle.override",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.approve.hr_director",
                "documents.read_sensitive",
                "documents.create",
                "documents.upload",
                "documents.register",
                "absence.read_all",
                "leave.review_hr",
                "business_trip.register",
                "termination.initiate_unit",
                "termination.read_all",
                "termination.review_hr",
                "termination.complete",
                "termination.exit_interview.manage",
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
                "absence.read_all",
                "business_trip.review_finance",
                "termination.read_all",
                "termination.review_economic",
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
                "termination.read_all",
                "termination.review_legal",
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
                "termination.read_all",
                "termination.sign",
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
                "employees.read",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.request.acknowledge",
                "documents.read_sensitive",
                "absence.read_all",
                "business_trip.review_finance",
                "termination.read_all",
                "termination.assets.confirm",
                "termination.settlement.confirm",
            }
        ),
    ),
    SeedRoleDefinition(
        code="it-department-specialist",
        name="Специалист IT-отдела",
        permission_codes=frozenset(
            {
                "organization.read",
                "employees.read",
                "hiring.request.read",
                "hiring.request.read_sensitive",
                "hiring.request.acknowledge",
                "documents.read_sensitive",
                "termination.read_all",
                "termination.access.confirm",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-process-owner",
        name="Владелец процесса найма — директор ДДО",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.start",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "recruitment.request.read",
                "recruitment.candidate.read",
                "documents.read",
                "audit.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-hr-recruiter",
        name="HR-бизнес-партнер / рекрутер",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.start",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "recruitment.request.create",
                "recruitment.request.read",
                "recruitment.vacancy.manage",
                "recruitment.vacancy.publish",
                "recruitment.candidate.read",
                "recruitment.candidate.read_sensitive",
                "recruitment.candidate.manage",
                "recruitment.screen",
                "recruitment.interview.manage",
                "recruitment.offer.manage",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-hr-inspector",
        name="HR-инспектор / специалист по кадровому администрированию",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "recruitment.hiring.manage",
                "documents.read_sensitive",
                "documents.create",
                "documents.upload",
                "documents.generate",
                "documents.register",
                "employees.create",
                "employees.hire",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-department-director",
        name="Директор нанимающего департамента",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.start",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "recruitment.request.create",
                "recruitment.request.read",
                "recruitment.interview.evaluate",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-economic-reviewer",
        name="Согласующий ДЭП по бюджету найма",
        permission_codes=frozenset(
            {"regulated_hiring.read", "regulated_hiring.stage.act", "regulated_hiring.form.manage"}
        ),
    ),
    SeedRoleDefinition(
        code="hiring-legal-reviewer",
        name="Согласующий ЮД по найму",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "documents.read_sensitive",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-compliance-officer",
        name="Комплаенс-офицер процесса найма",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "audit.read",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-curating-deputy",
        name="Курирующий заместитель Председателя",
        permission_codes=frozenset(
            {"regulated_hiring.read", "regulated_hiring.stage.act", "regulated_hiring.form.manage"}
        ),
    ),
    SeedRoleDefinition(
        code="hiring-authorized-signatory",
        name="Председатель Правления / уполномоченное лицо",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "documents.sign_request",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-commission-chair",
        name="Председатель конкурсной комиссии",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "recruitment.commission.decide",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-commission-member",
        name="Член конкурсной комиссии",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.stage.act",
                "regulated_hiring.form.manage",
                "recruitment.interview.evaluate",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-commission-secretary",
        name="Секретарь конкурсной комиссии без права голоса",
        permission_codes=frozenset(
            {
                "regulated_hiring.read",
                "regulated_hiring.form.manage",
                "recruitment.commission.manage",
            }
        ),
    ),
    SeedRoleDefinition(
        code="hiring-it-executor",
        name="IT-исполнитель найма",
        permission_codes=frozenset(
            {"regulated_hiring.read", "regulated_hiring.stage.act", "regulated_hiring.form.manage"}
        ),
    ),
    SeedRoleDefinition(
        code="hiring-system-owner",
        name="Владелец системы или данных",
        permission_codes=frozenset({"regulated_hiring.read", "regulated_hiring.form.manage"}),
    ),
)
