"""Deterministic, idempotent development seed for Module 1."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid5

from sqlalchemy import Table, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import FromClause

from app.core.database import session_scope
from app.module2_seed import seed_module2
from app.modules.access_control.domain.permissions import PERMISSION_CATALOG
from app.modules.access_control.domain.seed_roles import SEED_ROLES
from app.modules.access_control.infrastructure.models import (
    AccessScopeModel,
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    UserRoleAssignmentModel,
)
from app.modules.employees.infrastructure.models import (
    EmployeeAssignmentModel,
    EmployeeModel,
    PersonModel,
)
from app.modules.identity.infrastructure.models import UserAccountModel
from app.modules.organization.infrastructure.models import (
    OrganizationModel,
    OrganizationPolicyModel,
    OrganizationRelationshipTypeModel,
    OrganizationStructureVersionModel,
    OrganizationUnitModel,
    OrganizationUnitTypeAllowedParentModel,
    OrganizationUnitTypeModel,
    PositionDefinitionModel,
    StaffingSlotModel,
)
from app.shared.identifiers import deterministic_uuid

SEED_TIMESTAMP = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
SEED_EFFECTIVE_DATE = date(2025, 1, 1)
PERMISSION_ID_NAMESPACE = UUID("de7a53f1-8d76-4a12-9cd8-b5f3d61655b2")


def _seed_id(kind: str, key: str) -> UUID:
    return deterministic_uuid(f"seed:{kind}:{key}")


def _development_user_id(handle: str) -> UUID:
    """Match the IDs emitted by the development authentication adapter."""

    return deterministic_uuid(f"development-user:{handle}")


ORGANIZATION_ID = _seed_id("organization", "spk-ertis")
STRUCTURE_VERSION_ID = _seed_id("structure-version", "spk-ertis:1")
DIRECTOR_PERSON_ID = _seed_id("person", "development-director")
DIRECTOR_EMPLOYEE_ID = _seed_id("employee", "development-director")
EMPLOYEE_PERSON_ID = _seed_id("person", "development-employee")
EMPLOYEE_EMPLOYEE_ID = _seed_id("employee", "development-employee")


@dataclass(frozen=True, slots=True)
class UnitTypeSeed:
    code: str
    name: str
    description: str


UNIT_TYPES: tuple[UnitTypeSeed, ...] = (
    UnitTypeSeed("board", "Board", "Board or other governing body."),
    UnitTypeSeed("management", "Management", "Executive management body."),
    UnitTypeSeed("department", "Department", "Department-level organization unit."),
    UnitTypeSeed("service", "Service", "Specialized internal service."),
    UnitTypeSeed("division", "Division", "Division within an organization unit."),
    UnitTypeSeed("team", "Team", "Team-level organization unit."),
    UnitTypeSeed("hr", "HR Unit", "Human-resources organization unit."),
    UnitTypeSeed("it_support", "IT Support", "Information-technology support unit."),
    UnitTypeSeed("archive", "Archive", "Records and archive unit."),
    UnitTypeSeed("other", "Other", "Configurable organization unit type."),
)

ALLOWED_PARENT_TYPE_CODES: dict[str, tuple[str, ...]] = {
    "management": ("board",),
    "department": ("board", "management"),
    "service": ("management", "department"),
    "division": ("department", "service"),
    "team": ("department", "service", "division"),
    "hr": ("department",),
    "it_support": ("department",),
    "archive": ("department",),
    "other": ("board", "management", "department", "service", "division", "team"),
}


@dataclass(frozen=True, slots=True)
class RelationshipTypeSeed:
    code: str
    name: str
    description: str
    directed: bool = True
    prevents_cycles: bool = False


RELATIONSHIP_TYPES: tuple[RelationshipTypeSeed, ...] = (
    RelationshipTypeSeed(
        "administrative_subordination",
        "Administrative Subordination",
        "Additional administrative reporting outside the primary tree.",
        prevents_cycles=True,
    ),
    RelationshipTypeSeed(
        "functional_supervision",
        "Functional Supervision",
        "Functional oversight that does not change the primary tree.",
        prevents_cycles=True,
    ),
    RelationshipTypeSeed(
        "curator",
        "Curator Relationship",
        "Executive curation or sponsorship of an organization unit.",
        prevents_cycles=True,
    ),
    RelationshipTypeSeed(
        "shared_service",
        "Shared Service",
        "A service delivered across organization-unit boundaries.",
    ),
    RelationshipTypeSeed(
        "coordination",
        "Coordination",
        "A non-hierarchical coordination relationship.",
        directed=False,
    ),
    RelationshipTypeSeed(
        "temporary_supervision",
        "Temporary Supervision",
        "A date-bounded supervisory relationship.",
        prevents_cycles=True,
    ),
)


@dataclass(frozen=True, slots=True)
class UnitSeed:
    code: str
    name: str
    unit_type_code: str
    parent_code: str | None
    sort_order: int
    short_name: str | None = None


UNITS: tuple[UnitSeed, ...] = (
    UnitSeed("BOARD", "Board of Directors", "board", None, 0, "Board"),
    UnitSeed("MANAGEMENT", "Management Board", "management", "BOARD", 10, "Management"),
    UnitSeed(
        "STABILIZATION_FUND",
        "Stabilization Fund Department",
        "department",
        "MANAGEMENT",
        10,
    ),
    UnitSeed(
        "ECONOMIC_PLANNING",
        "Economic Planning Department",
        "department",
        "MANAGEMENT",
        20,
    ),
    UnitSeed("LEGAL", "Legal Department", "department", "MANAGEMENT", 30),
    UnitSeed("INVESTMENT", "Investment Department", "department", "MANAGEMENT", 40),
    UnitSeed("CREDIT", "Credit Department", "department", "MANAGEMENT", 50),
    UnitSeed("CONSTRUCTION", "Construction Department", "department", "MANAGEMENT", 60),
    UnitSeed("ASSET", "Asset Department", "department", "MANAGEMENT", 70),
    UnitSeed(
        "ACCOUNTING_REPORTING",
        "Accounting and Reporting Department",
        "department",
        "MANAGEMENT",
        80,
        "Accounting",
    ),
    UnitSeed(
        "DOCUMENT_SUPPORT_PERSONNEL",
        "Document Support and Personnel Management Department",
        "department",
        "MANAGEMENT",
        90,
        "Document Support and Personnel",
    ),
    UnitSeed("HR", "HR", "hr", "DOCUMENT_SUPPORT_PERSONNEL", 10),
    UnitSeed(
        "EDM_ARCHIVE",
        "Electronic Document Management and Archive",
        "archive",
        "DOCUMENT_SUPPORT_PERSONNEL",
        20,
        "EDM and Archive",
    ),
    UnitSeed(
        "IT_SUPPORT",
        "IT Support",
        "it_support",
        "DOCUMENT_SUPPORT_PERSONNEL",
        30,
    ),
    UnitSeed(
        "PR_COMMUNICATIONS",
        "PR and Communications",
        "service",
        "DOCUMENT_SUPPORT_PERSONNEL",
        40,
    ),
)


@dataclass(frozen=True, slots=True)
class PositionSeed:
    code: str
    name: str
    job_family: str
    grade: str | None = None


POSITIONS: tuple[PositionSeed, ...] = (
    PositionSeed("auditor", "Auditor", "governance"),
    PositionSeed(
        "chairman_management_board",
        "Chairman of the Management Board",
        "executive_management",
        "executive",
    ),
    PositionSeed("compliance_officer", "Compliance Officer", "governance"),
    PositionSeed(
        "head_administration_corporate_secretary",
        "Head of Administration / Corporate Secretary",
        "corporate_administration",
        "executive",
    ),
    PositionSeed("advisor_chairman", "Advisor to the Chairman", "executive_advisory"),
    PositionSeed("risk_manager", "Risk Manager", "risk"),
    PositionSeed(
        "deputy_stabilization_economics_legal",
        "Deputy Chairman for Stabilization, Economics and Legal",
        "executive_management",
        "executive",
    ),
    PositionSeed(
        "deputy_investments_credit",
        "Deputy Chairman for Investments and Credit",
        "executive_management",
        "executive",
    ),
    PositionSeed(
        "deputy_construction_assets",
        "Deputy Chairman for Construction and Assets",
        "executive_management",
        "executive",
    ),
    PositionSeed("department_director", "Department Director", "management", "director"),
    PositionSeed("unit_lead", "Unit Lead", "management", "manager"),
    PositionSeed("specialist", "Specialist", "general"),
)


@dataclass(frozen=True, slots=True)
class SlotSeed:
    key: str
    unit_code: str
    position_code: str
    reports_to_key: str | None
    head_of_unit: bool = False


BASE_SLOTS: tuple[SlotSeed, ...] = (
    SlotSeed("chairman", "MANAGEMENT", "chairman_management_board", None, True),
    SlotSeed("auditor", "BOARD", "auditor", "chairman"),
    SlotSeed("compliance-officer", "BOARD", "compliance_officer", "chairman"),
    SlotSeed(
        "head-administration",
        "BOARD",
        "head_administration_corporate_secretary",
        "chairman",
    ),
    SlotSeed("advisor-chairman", "MANAGEMENT", "advisor_chairman", "chairman"),
    SlotSeed("risk-manager", "MANAGEMENT", "risk_manager", "chairman"),
    SlotSeed(
        "stabilization-specialist-vacancy",
        "STABILIZATION_FUND",
        "specialist",
        "stabilization-fund-director",
    ),
    SlotSeed(
        "deputy-stabilization",
        "MANAGEMENT",
        "deputy_stabilization_economics_legal",
        "chairman",
    ),
    SlotSeed(
        "deputy-investments",
        "MANAGEMENT",
        "deputy_investments_credit",
        "chairman",
    ),
    SlotSeed(
        "deputy-construction",
        "MANAGEMENT",
        "deputy_construction_assets",
        "chairman",
    ),
    SlotSeed(
        "development-employee",
        "IT_SUPPORT",
        "specialist",
        "it-support-lead",
    ),
)

DEPARTMENT_REPORTING: dict[str, str] = {
    "STABILIZATION_FUND": "deputy-stabilization",
    "ECONOMIC_PLANNING": "deputy-stabilization",
    "LEGAL": "deputy-stabilization",
    "INVESTMENT": "deputy-investments",
    "CREDIT": "deputy-investments",
    "CONSTRUCTION": "deputy-construction",
    "ASSET": "deputy-construction",
    "ACCOUNTING_REPORTING": "chairman",
    "DOCUMENT_SUPPORT_PERSONNEL": "head-administration",
}

SUBUNIT_CODES: tuple[str, ...] = (
    "HR",
    "EDM_ARCHIVE",
    "IT_SUPPORT",
    "PR_COMMUNICATIONS",
)

DEVELOPMENT_ROLE_CODES: dict[str, str] = {
    "admin": "system-administrator",
    "hr": "hr-administrator",
    "director": "department-director",
    "employee": "employee",
    "reviewer": "organization-reviewer",
    "publisher": "organization-publisher",
    "auditor": "auditor",
    "hr.initiator": "hr-request-initiator",
    "hr.director": "hr-document-management-director",
    "economic.director": "economic-planning-director",
    "commission": "competition-commission-reviewer",
    "legal": "legal-department-reviewer",
    "chairman": "management-board-chairman",
    "accountant": "accountant",
    "it.specialist": "it-department-specialist",
}

DEVELOPMENT_SCOPE_TYPES: dict[str, str] = {
    "admin": "organization",
    "hr": "organization",
    "director": "own_unit_and_descendants",
    "employee": "self",
    "reviewer": "organization",
    "publisher": "organization",
    "auditor": "organization",
    "hr.initiator": "organization",
    "hr.director": "organization",
    "economic.director": "organization",
    "commission": "organization",
    "legal": "organization",
    "chairman": "organization",
    "accountant": "organization",
    "it.specialist": "organization",
}

DEVELOPMENT_DISPLAY_NAMES: dict[str, str] = {
    "admin": "Development System Administrator",
    "hr": "Development HR Administrator",
    "director": "Development Department Director",
    "employee": "Development Employee",
    "reviewer": "Development Organization Reviewer",
    "publisher": "Development Organization Publisher",
    "auditor": "Development Auditor",
    "hr.initiator": "Айгерим Садыкова",
    "hr.director": "Данияр Ахметов",
    "economic.director": "Алия Нуртаева",
    "commission": "Представитель конкурсной комиссии",
    "legal": "Марат Ибраев",
    "chairman": "Председатель правления",
    "accountant": "Бухгалтер демо",
    "it.specialist": "IT-специалист демо",
}

ORGANIZATION_VIEWER_HANDLES: tuple[str, ...] = ("director", "employee")
ORGANIZATION_VIEWER_ROLE_CODE = "organization-viewer"


@dataclass(frozen=True, slots=True)
class DemoEmploymentSeed:
    handle: str
    first_name: str
    last_name: str
    display_name: str
    employee_number: str
    corporate_email: str
    staffing_slot_key: str

    @property
    def person_id(self) -> UUID:
        return _seed_id("person", f"development-{self.handle}")

    @property
    def employee_id(self) -> UUID:
        return _seed_id("employee", f"development-{self.handle}")


DEMO_EMPLOYMENTS: tuple[DemoEmploymentSeed, ...] = (
    DemoEmploymentSeed(
        handle="director",
        first_name="Development",
        last_name="Director",
        display_name="Development Department Director",
        employee_number="DEMO-DIRECTOR-001",
        corporate_email="director@example.invalid",
        staffing_slot_key="stabilization-fund-director",
    ),
    DemoEmploymentSeed(
        handle="employee",
        first_name="Development",
        last_name="Employee",
        display_name="Development Employee",
        employee_number="DEMO-EMPLOYEE-001",
        corporate_email="employee@example.invalid",
        staffing_slot_key="development-employee",
    ),
)

OCCUPIED_SLOT_KEYS = frozenset(item.staffing_slot_key for item in DEMO_EMPLOYMENTS)


async def _insert_rows(
    session: AsyncSession,
    table: FromClause,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    statement = postgresql_insert(cast(Table, table)).values(rows).on_conflict_do_nothing()
    await session.execute(statement)


def _all_slots() -> tuple[SlotSeed, ...]:
    department_slots = tuple(
        SlotSeed(
            f"{unit_code.casefold().replace('_', '-')}-director",
            unit_code,
            "department_director",
            reports_to,
            True,
        )
        for unit_code, reports_to in DEPARTMENT_REPORTING.items()
    )
    subunit_slots = tuple(
        SlotSeed(
            f"{unit_code.casefold().replace('_', '-')}-lead",
            unit_code,
            "unit_lead",
            "document-support-personnel-director",
            True,
        )
        for unit_code in SUBUNIT_CODES
    )
    return BASE_SLOTS + department_slots + subunit_slots


async def _seed_foundation(session: AsyncSession) -> None:
    await _insert_rows(
        session,
        OrganizationModel.__table__,
        [
            {
                "id": ORGANIZATION_ID,
                "code": "SPK-ERTIS",
                "legal_name": "JSC SPK Ertis",
                "display_name": "SPK Ertis",
                "status": "active",
                "created_at": SEED_TIMESTAMP,
                "updated_at": SEED_TIMESTAMP,
            }
        ],
    )
    await _insert_rows(
        session,
        UserAccountModel.__table__,
        [
            {
                "id": _development_user_id(handle),
                "external_subject": f"development:{handle}",
                "username": handle,
                "email": f"{handle}@demo.local"
                if handle
                in {
                    "admin",
                    "hr.initiator",
                    "hr.director",
                    "economic.director",
                    "commission",
                    "legal",
                    "chairman",
                    "accountant",
                    "it.specialist",
                }
                else f"{handle}@example.invalid",
                "display_name": display_name,
                "employee_id": None,
                "status": "active",
                "active": True,
                "last_login_at": None,
                "created_at": SEED_TIMESTAMP,
                "updated_at": SEED_TIMESTAMP,
                "revision": 1,
            }
            for handle, display_name in DEVELOPMENT_DISPLAY_NAMES.items()
        ],
    )


async def _seed_permissions_and_roles(session: AsyncSession) -> None:
    admin_user_id = _development_user_id("admin")
    permission_ids = {
        item.code: uuid5(PERMISSION_ID_NAMESPACE, item.code) for item in PERMISSION_CATALOG
    }
    await _insert_rows(
        session,
        PermissionModel.__table__,
        [
            {
                "id": permission_ids[item.code],
                "code": item.code,
                "name": item.name,
                "description": item.description,
                "active": True,
                # Everything in the catalogue is checked by the source tree, so the
                # administration API must refuse to delete or deactivate it.
                "system": True,
                "revision": 1,
                "created_at": SEED_TIMESTAMP,
                "updated_at": SEED_TIMESTAMP,
            }
            for item in PERMISSION_CATALOG
        ],
    )
    await _insert_rows(
        session,
        RoleModel.__table__,
        [
            {
                "id": role.id,
                "organization_id": None,
                "code": role.code,
                "name": role.name,
                "description": f"Built-in Module 1 role: {role.name}.",
                "active": True,
                "system": True,
                "revision": 1,
                "created_at": SEED_TIMESTAMP,
                "updated_at": SEED_TIMESTAMP,
            }
            for role in SEED_ROLES
        ],
    )
    await _insert_rows(
        session,
        RolePermissionModel.__table__,
        [
            {
                "role_id": role.id,
                "permission_id": permission_ids[permission_code],
                "granted_at": SEED_TIMESTAMP,
                "granted_by": admin_user_id,
            }
            for role in SEED_ROLES
            for permission_code in sorted(role.permission_codes)
        ],
    )


async def _seed_reference_data(session: AsyncSession) -> None:
    unit_type_ids = {item.code: _seed_id("unit-type", item.code) for item in UNIT_TYPES}
    await _insert_rows(
        session,
        OrganizationUnitTypeModel.__table__,
        [
            {
                "id": unit_type_ids[item.code],
                "organization_id": ORGANIZATION_ID,
                "code": item.code.upper(),
                "name": item.name,
                "description": item.description,
                "active": True,
                "custom_fields_schema": {},
                "revision": 1,
                "created_at": SEED_TIMESTAMP,
                "updated_at": SEED_TIMESTAMP,
            }
            for item in UNIT_TYPES
        ],
    )
    await _insert_rows(
        session,
        OrganizationUnitTypeAllowedParentModel.__table__,
        [
            {
                "unit_type_id": unit_type_ids[unit_type_code],
                "parent_type_id": unit_type_ids[parent_type_code],
            }
            for unit_type_code, parent_type_codes in ALLOWED_PARENT_TYPE_CODES.items()
            for parent_type_code in parent_type_codes
        ],
    )
    await _insert_rows(
        session,
        OrganizationRelationshipTypeModel.__table__,
        [
            {
                "id": _seed_id("relationship-type", item.code),
                "organization_id": ORGANIZATION_ID,
                "code": item.code.upper(),
                "name": item.name,
                "description": item.description,
                "directed": item.directed,
                "prevents_cycles": item.prevents_cycles,
                "allow_self_link": False,
                "active": True,
                "metadata_schema": {},
                "revision": 1,
                "created_at": SEED_TIMESTAMP,
                "updated_at": SEED_TIMESTAMP,
            }
            for item in RELATIONSHIP_TYPES
        ],
    )
    await _insert_rows(
        session,
        PositionDefinitionModel.__table__,
        [
            {
                "id": _seed_id("position", item.code),
                "organization_id": ORGANIZATION_ID,
                "code": item.code.upper(),
                "name": item.name,
                "description": None,
                "job_family": item.job_family,
                "grade": item.grade,
                "active": True,
                "custom_fields": {},
                "revision": 1,
                "created_at": SEED_TIMESTAMP,
                "updated_at": SEED_TIMESTAMP,
            }
            for item in POSITIONS
        ],
    )


async def _seed_structure(session: AsyncSession) -> None:
    admin_user_id = _development_user_id("admin")
    publisher_user_id = _development_user_id("publisher")
    await _insert_rows(
        session,
        OrganizationStructureVersionModel.__table__,
        [
            {
                "id": STRUCTURE_VERSION_ID,
                "organization_id": ORGANIZATION_ID,
                "version_number": 1,
                "name": "Initial published structure",
                "status": "published",
                "based_on_version_id": None,
                "effective_from": SEED_EFFECTIVE_DATE,
                "effective_to": None,
                "revision": 1,
                "created_by": admin_user_id,
                "published_by": publisher_user_id,
                "created_at": SEED_TIMESTAMP,
                "published_at": SEED_TIMESTAMP,
            }
        ],
    )
    unit_ids = {item.code: _seed_id("unit", item.code) for item in UNITS}
    await _insert_rows(
        session,
        OrganizationUnitModel.__table__,
        [
            {
                "id": unit_ids[item.code],
                "structure_version_id": STRUCTURE_VERSION_ID,
                "stable_key": _seed_id("unit-stable-key", item.code),
                "code": item.code,
                "name": item.name,
                "short_name": item.short_name,
                "unit_type_id": _seed_id("unit-type", item.unit_type_code),
                "parent_unit_id": unit_ids[item.parent_code] if item.parent_code else None,
                "sort_order": item.sort_order,
                "description": None,
                "active": True,
                "custom_fields": {},
                "revision": 1,
            }
            for item in UNITS
        ],
    )
    slots = _all_slots()
    slot_ids = {item.key: _seed_id("staffing-slot", item.key) for item in slots}
    await _insert_rows(
        session,
        StaffingSlotModel.__table__,
        [
            {
                "id": slot_ids[item.key],
                "structure_version_id": STRUCTURE_VERSION_ID,
                "stable_key": _seed_id("staffing-slot-stable-key", item.key),
                "organization_unit_id": unit_ids[item.unit_code],
                "position_definition_id": _seed_id("position", item.position_code),
                "reports_to_slot_id": (
                    slot_ids[item.reports_to_key] if item.reports_to_key is not None else None
                ),
                "head_of_unit": item.head_of_unit,
                "full_time_equivalent": Decimal("1.00"),
                "employment_type": "permanent",
                "status": "occupied" if item.key in OCCUPIED_SLOT_KEYS else "vacant",
                "effective_from": SEED_EFFECTIVE_DATE,
                "effective_to": None,
                "revision": 1,
                "custom_fields": {},
            }
            for item in slots
        ],
    )
    await _insert_rows(
        session,
        OrganizationPolicyModel.__table__,
        [
            {
                "id": _seed_id("organization-policy", "spk-ertis:1"),
                "organization_id": ORGANIZATION_ID,
                "structure_version_id": STRUCTURE_VERSION_ID,
                "effective_from": SEED_EFFECTIVE_DATE,
                "effective_to": None,
                "managers_can_create_employee_drafts": True,
                "managers_can_assign_existing_employees": False,
                "manager_changes_require_hr_approval": True,
                "managers_can_create_staffing_slots": False,
                "staffing_changes_require_finance_review": True,
                "structure_publish_requires_review": True,
                "allow_multiple_unit_heads": False,
                "allow_cross_unit_relationships": True,
                "revision": 1,
                "created_by": admin_user_id,
                "created_at": SEED_TIMESTAMP,
                "updated_at": SEED_TIMESTAMP,
            }
        ],
    )


def _demo_person_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": item.person_id,
            "first_name": item.first_name,
            "last_name": item.last_name,
            "middle_name": None,
            "display_name": item.display_name,
            "protected_iin": None,
            "birth_date": None,
            "personal_email": None,
            "phone": None,
            "status": "active",
            "created_at": SEED_TIMESTAMP,
            "updated_at": SEED_TIMESTAMP,
            "revision": 1,
        }
        for item in DEMO_EMPLOYMENTS
    ]


def _demo_employee_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": item.employee_id,
            "organization_id": ORGANIZATION_ID,
            "created_by": _development_user_id("admin"),
            "person_id": item.person_id,
            "employee_number": item.employee_number,
            "employment_status": "active",
            "hire_date": SEED_EFFECTIVE_DATE,
            "termination_date": None,
            "corporate_email": item.corporate_email,
            "active": True,
            "created_at": SEED_TIMESTAMP,
            "updated_at": SEED_TIMESTAMP,
            "revision": 1,
        }
        for item in DEMO_EMPLOYMENTS
    ]


def _demo_assignment_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": _seed_id("employee-assignment", f"development-{item.handle}"),
            "employee_id": item.employee_id,
            "staffing_slot_id": _seed_id("staffing-slot", item.staffing_slot_key),
            "assignment_type": "permanent",
            "full_time_equivalent": Decimal("1.00"),
            "effective_from": SEED_EFFECTIVE_DATE,
            "effective_to": None,
            "primary": True,
            "acting": False,
            "status": "active",
            "source_document_id": None,
            "created_at": SEED_TIMESTAMP,
            "updated_at": SEED_TIMESTAMP,
            "revision": 1,
        }
        for item in DEMO_EMPLOYMENTS
    ]


async def _seed_demo_employment(session: AsyncSession) -> None:
    await _insert_rows(
        session,
        PersonModel.__table__,
        _demo_person_rows(),
    )
    await _insert_rows(
        session,
        EmployeeModel.__table__,
        _demo_employee_rows(),
    )
    for item in DEMO_EMPLOYMENTS:
        await session.execute(
            update(UserAccountModel)
            .where(
                UserAccountModel.id == _development_user_id(item.handle),
                UserAccountModel.employee_id.is_(None),
            )
            .values(employee_id=item.employee_id)
        )
    await _insert_rows(
        session,
        EmployeeAssignmentModel.__table__,
        _demo_assignment_rows(),
    )
    for item in DEMO_EMPLOYMENTS:
        await session.execute(
            update(StaffingSlotModel)
            .where(
                StaffingSlotModel.id == _seed_id("staffing-slot", item.staffing_slot_key),
                StaffingSlotModel.status == "vacant",
            )
            .values(status="occupied")
        )


async def _seed_role_assignments(session: AsyncSession) -> None:
    admin_user_id = _development_user_id("admin")
    roles_by_code = {role.code: role for role in SEED_ROLES}
    scope_ids = {
        handle: _seed_id("access-scope", f"development:{handle}")
        for handle in DEVELOPMENT_ROLE_CODES
    }
    viewer_scope_ids = {
        handle: _seed_id("access-scope", f"development:{handle}:organization-viewer")
        for handle in ORGANIZATION_VIEWER_HANDLES
    }
    await _insert_rows(
        session,
        AccessScopeModel.__table__,
        [
            {
                "id": scope_ids[handle],
                "scope_type": DEVELOPMENT_SCOPE_TYPES[handle],
                "organization_id": ORGANIZATION_ID,
                "created_at": SEED_TIMESTAMP,
            }
            for handle in DEVELOPMENT_ROLE_CODES
        ]
        + [
            {
                "id": viewer_scope_ids[handle],
                "scope_type": "organization",
                "organization_id": ORGANIZATION_ID,
                "created_at": SEED_TIMESTAMP,
            }
            for handle in ORGANIZATION_VIEWER_HANDLES
        ],
    )
    await _insert_rows(
        session,
        UserRoleAssignmentModel.__table__,
        [
            {
                "id": _seed_id("role-assignment", f"development:{handle}:{role_code}"),
                "user_id": _development_user_id(handle),
                "role_id": roles_by_code[role_code].id,
                "scope_id": scope_ids[handle],
                "effective_from": SEED_TIMESTAMP,
                "effective_to": None,
                "created_by": admin_user_id,
                "created_at": SEED_TIMESTAMP,
                "revoked_at": None,
                "revoked_by": None,
                "revocation_reason": None,
                "revision": 1,
            }
            for handle, role_code in DEVELOPMENT_ROLE_CODES.items()
        ]
        + [
            {
                "id": _seed_id(
                    "role-assignment",
                    f"development:{handle}:{ORGANIZATION_VIEWER_ROLE_CODE}",
                ),
                "user_id": _development_user_id(handle),
                "role_id": roles_by_code[ORGANIZATION_VIEWER_ROLE_CODE].id,
                "scope_id": viewer_scope_ids[handle],
                "effective_from": SEED_TIMESTAMP,
                "effective_to": None,
                "created_by": admin_user_id,
                "created_at": SEED_TIMESTAMP,
                "revoked_at": None,
                "revoked_by": None,
                "revocation_reason": None,
                "revision": 1,
            }
            for handle in ORGANIZATION_VIEWER_HANDLES
        ],
    )


async def seed_database() -> None:
    """Insert the complete demo dataset without replacing user-edited seed rows."""

    async with session_scope() as session:
        await _seed_foundation(session)
        await _seed_permissions_and_roles(session)
        await _seed_reference_data(session)
        await _seed_structure(session)
        await _seed_demo_employment(session)
        await _seed_role_assignments(session)
        await seed_module2(
            session,
            organization_id=ORGANIZATION_ID,
            actor_id=_development_user_id("admin"),
            timestamp=SEED_TIMESTAMP,
            seed_id=_seed_id,
            insert_rows=_insert_rows,
        )


def main() -> None:
    # psycopg async requires a selector loop on Windows; it is also valid on POSIX.
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(seed_database())
    print(f"Module 1 and Module 2 seed completed for organization {ORGANIZATION_ID}.")


if __name__ == "__main__":
    main()
