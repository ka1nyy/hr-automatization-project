"""Cross-version assignment guards for organization publication."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.modules.organization.infrastructure.external_validation import (
    SqlAlchemyExternalStructureValidationAdapter,
)


def _assignment(*, fte: str = "1", effective_to: date | None = None):  # type: ignore[no-untyped-def]
    return SimpleNamespace(
        id=uuid4(),
        status="active",
        effective_from=date(2026, 1, 1),
        effective_to=effective_to,
        full_time_equivalent=Decimal(fte),
    )


def _slot(
    *,
    stable_key=None,  # type: ignore[no-untyped-def]
    unit_id=None,  # type: ignore[no-untyped-def]
    position_id=None,  # type: ignore[no-untyped-def]
    status: str = "occupied",
    fte: str = "1",
    effective_to: date | None = None,
):  # type: ignore[no-untyped-def]
    return SimpleNamespace(
        id=uuid4(),
        stable_key=stable_key or uuid4(),
        organization_unit_id=unit_id or uuid4(),
        position_definition_id=position_id or uuid4(),
        status=status,
        effective_from=date(2026, 1, 1),
        effective_to=effective_to,
        full_time_equivalent=Decimal(fte),
    )


def test_publication_rejects_silent_unit_or_position_transfer() -> None:
    publish_on = date(2027, 1, 1)
    slot_key = uuid4()
    source_unit_key = uuid4()
    target_unit_key = uuid4()
    source = _slot(stable_key=slot_key, position_id=uuid4())
    target = _slot(
        stable_key=slot_key,
        unit_id=uuid4(),
        position_id=source.position_definition_id,
    )
    assignment = _assignment()

    moved_issues = SqlAlchemyExternalStructureValidationAdapter._transition_issues(
        ((assignment, source, source_unit_key),),  # type: ignore[arg-type]
        target_slots=(target,),  # type: ignore[arg-type]
        target_unit_keys={target.organization_unit_id: target_unit_key},
        effective_from=publish_on,
    )
    assert [item.path for item in moved_issues] == ["employeeAssignments.organizationUnitId"]

    target.position_definition_id = uuid4()
    position_issues = SqlAlchemyExternalStructureValidationAdapter._transition_issues(
        ((assignment, source, source_unit_key),),  # type: ignore[arg-type]
        target_slots=(target,),  # type: ignore[arg-type]
        target_unit_keys={target.organization_unit_id: source_unit_key},
        effective_from=publish_on,
    )
    assert [item.path for item in position_issues] == ["employeeAssignments.positionDefinitionId"]


def test_publication_rejects_missing_closed_date_conflicting_and_under_fte_slots() -> None:
    publish_on = date(2027, 1, 1)
    slot_key = uuid4()
    unit_key = uuid4()
    source = _slot(stable_key=slot_key)
    open_assignment = _assignment()

    missing = SqlAlchemyExternalStructureValidationAdapter._transition_issues(
        ((open_assignment, source, unit_key),),  # type: ignore[arg-type]
        target_slots=(),
        target_unit_keys={},
        effective_from=publish_on,
    )
    assert [item.code for item in missing] == ["EMPLOYEE_ASSIGNMENT_OUTSIDE_VERSION"]

    target = _slot(
        stable_key=slot_key,
        unit_id=uuid4(),
        position_id=source.position_definition_id,
        status="closed",
    )
    unit_map = {target.organization_unit_id: unit_key}
    closed = SqlAlchemyExternalStructureValidationAdapter._transition_issues(
        ((open_assignment, source, unit_key),),  # type: ignore[arg-type]
        target_slots=(target,),  # type: ignore[arg-type]
        target_unit_keys=unit_map,
        effective_from=publish_on,
    )
    assert [item.path for item in closed] == ["employeeAssignments.staffingSlotId"]

    target.status = "closing"
    target.effective_to = date(2027, 6, 30)
    date_conflict = SqlAlchemyExternalStructureValidationAdapter._transition_issues(
        ((open_assignment, source, unit_key),),  # type: ignore[arg-type]
        target_slots=(target,),  # type: ignore[arg-type]
        target_unit_keys=unit_map,
        effective_from=publish_on,
    )
    assert [item.code for item in date_conflict] == ["ASSIGNMENT_DATE_CONFLICT"]

    target.status = "occupied"
    target.effective_to = None
    target.full_time_equivalent = Decimal("1")
    first = _assignment(fte="0.75")
    second = _assignment(fte="0.75")
    fte_issues = SqlAlchemyExternalStructureValidationAdapter._transition_issues(
        (
            (first, source, unit_key),
            (second, source, unit_key),
        ),  # type: ignore[arg-type]
        target_slots=(target,),  # type: ignore[arg-type]
        target_unit_keys=unit_map,
        effective_from=publish_on,
    )
    assert [item.code for item in fte_issues] == ["STAFFING_FTE_EXCEEDED"]


def test_assignment_ended_before_publication_does_not_block_candidate_version() -> None:
    publish_on = date(2027, 1, 1)
    unit_key = uuid4()
    source = _slot()
    assignment = _assignment(effective_to=date(2026, 12, 31))

    issues = SqlAlchemyExternalStructureValidationAdapter._transition_issues(
        ((assignment, source, unit_key),),  # type: ignore[arg-type]
        target_slots=(),
        target_unit_keys={},
        effective_from=publish_on,
    )

    assert issues == []
