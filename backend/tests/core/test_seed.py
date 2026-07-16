"""Static invariants for the deterministic demonstration seed."""

from app.modules.access_control.domain.permissions import REQUIRED_PERMISSION_CODES
from app.modules.access_control.domain.seed_roles import SEED_ROLES
from app.seed import (
    DEMO_EMPLOYMENTS,
    DEVELOPMENT_ROLE_CODES,
    DEVELOPMENT_SCOPE_TYPES,
    DIRECTOR_EMPLOYEE_ID,
    DIRECTOR_PERSON_ID,
    EMPLOYEE_EMPLOYEE_ID,
    EMPLOYEE_PERSON_ID,
    OCCUPIED_SLOT_KEYS,
    ORGANIZATION_ID,
    ORGANIZATION_VIEWER_HANDLES,
    ORGANIZATION_VIEWER_ROLE_CODE,
    _all_slots,
    _demo_assignment_rows,
    _demo_employee_rows,
    _demo_person_rows,
    _development_user_id,
)


def test_seed_roles_are_unique_and_reference_only_catalog_permissions() -> None:
    role_codes = [role.code for role in SEED_ROLES]

    assert len(role_codes) == len(set(role_codes))
    assert len({role.id for role in SEED_ROLES}) == len(SEED_ROLES)
    assert all(role.permission_codes <= REQUIRED_PERMISSION_CODES for role in SEED_ROLES)


def test_organization_viewer_is_read_only_and_additive_for_scoped_personas() -> None:
    roles_by_code = {role.code: role for role in SEED_ROLES}

    assert roles_by_code[ORGANIZATION_VIEWER_ROLE_CODE].permission_codes == frozenset(
        {"organization.read", "organization.structure.read"}
    )
    assert ORGANIZATION_VIEWER_HANDLES == ("director", "employee")
    assert DEVELOPMENT_ROLE_CODES["director"] == "department-director"
    assert DEVELOPMENT_SCOPE_TYPES["director"] == "own_unit_and_descendants"
    assert DEVELOPMENT_ROLE_CODES["employee"] == "employee"
    assert DEVELOPMENT_SCOPE_TYPES["employee"] == "self"


def test_demo_employments_have_deterministic_identity_and_current_assignments() -> None:
    employments_by_handle = {item.handle: item for item in DEMO_EMPLOYMENTS}
    person_rows = _demo_person_rows()
    employee_rows = _demo_employee_rows()
    assignment_rows = _demo_assignment_rows()

    assert set(employments_by_handle) == {"director", "employee"}
    assert employments_by_handle["director"].person_id == DIRECTOR_PERSON_ID
    assert employments_by_handle["director"].employee_id == DIRECTOR_EMPLOYEE_ID
    assert employments_by_handle["employee"].person_id == EMPLOYEE_PERSON_ID
    assert employments_by_handle["employee"].employee_id == EMPLOYEE_EMPLOYEE_ID
    assert len(person_rows) == len({row["id"] for row in person_rows}) == 2
    assert len(employee_rows) == len({row["id"] for row in employee_rows}) == 2
    assert len(assignment_rows) == len({row["id"] for row in assignment_rows}) == 2
    assert all(row["organization_id"] == ORGANIZATION_ID for row in employee_rows)
    assert all(row["created_by"] == _development_user_id("admin") for row in employee_rows)
    assert all(row["primary"] and row["status"] == "active" for row in assignment_rows)
    assert {item.staffing_slot_key for item in DEMO_EMPLOYMENTS} == OCCUPIED_SLOT_KEYS
    assert {slot.key for slot in _all_slots()} >= OCCUPIED_SLOT_KEYS
