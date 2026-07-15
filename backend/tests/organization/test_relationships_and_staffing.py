"""Additional relationships, staffing lines, reporting chains, and staffing policy."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from app.modules.organization.application.commands import (
    AddRelationshipCommand,
    CloseStaffingSlotCommand,
    CreateStaffingSlotCommand,
    UpdateStaffingSlotCommand,
)
from app.modules.organization.application.service import (
    PERMISSION_STAFFING_MANAGE,
    OrganizationService,
)
from app.modules.organization.domain.enums import EmploymentType, StaffingSlotStatus
from app.modules.organization.domain.errors import (
    InvalidRelationshipError,
    OrganizationError,
    PermissionDeniedError,
    StaffingSlotNotAvailableError,
    StructureCycleError,
)

from .fakes import OrganizationScenario, RecordingAuthorizer


@pytest.mark.asyncio
async def test_additional_relationship_accepts_valid_edge_and_rejects_duplicate_self_and_cycle(
    scenario: OrganizationScenario,
) -> None:
    version, unit_type, root, _policy = scenario.add_valid_draft()
    finance = scenario.add_unit(version, unit_type, code="FIN", parent=root, sort_order=0)
    operations = scenario.add_unit(version, unit_type, code="OPS", parent=root, sort_order=1)
    relationship_type = scenario.add_relationship_type(prevents_cycles=True)

    relationship = await scenario.service.add_relationship(
        AddRelationshipCommand(
            version_id=version.id,
            version_revision=version.revision,
            relationship_type_id=relationship_type.id,
            source_unit_id=finance.id,
            target_unit_id=operations.id,
            effective_from=date(2027, 1, 1),
            metadata={"scope": "budget consultation"},
        ),
        scenario.actor,
    )

    assert relationship.active is True
    assert relationship.metadata == {"scope": "budget consultation"}
    assert version.revision == 2
    assert scenario.uow.audit.items[-1].action == "organizationRelationshipCreated"
    assert scenario.uow.outbox.items[-1].payload["action"] == "relationshipCreated"

    invalid_commands = (
        AddRelationshipCommand(
            version_id=version.id,
            version_revision=version.revision,
            relationship_type_id=relationship_type.id,
            source_unit_id=finance.id,
            target_unit_id=operations.id,
            effective_from=date(2027, 1, 1),
            metadata={"scope": "duplicate"},
        ),
        AddRelationshipCommand(
            version_id=version.id,
            version_revision=version.revision,
            relationship_type_id=relationship_type.id,
            source_unit_id=finance.id,
            target_unit_id=finance.id,
        ),
        AddRelationshipCommand(
            version_id=version.id,
            version_revision=version.revision,
            relationship_type_id=relationship_type.id,
            source_unit_id=operations.id,
            target_unit_id=finance.id,
        ),
    )
    expected_messages = (
        "Duplicate active relationships",
        "cannot link a unit to itself",
        "prohibits cycles",
    )
    for command, message in zip(invalid_commands, expected_messages, strict=True):
        with pytest.raises(InvalidRelationshipError, match=message):
            await scenario.service.add_relationship(command, scenario.actor)

    stored = await scenario.uow.relationships.list_by_version(version.id)
    assert tuple(item.id for item in stored) == (relationship.id,)
    assert version.revision == 2
    assert scenario.uow.commits == 1


def staffing_command(
    *,
    version_id: UUID,
    version_revision: int,
    unit_id: UUID,
    position_id: UUID,
    reports_to_slot_id: UUID | None = None,
    head_of_unit: bool = False,
) -> CreateStaffingSlotCommand:
    return CreateStaffingSlotCommand(
        version_id=version_id,
        version_revision=version_revision,
        organization_unit_id=unit_id,
        position_definition_id=position_id,
        reports_to_slot_id=reports_to_slot_id,
        head_of_unit=head_of_unit,
        full_time_equivalent=Decimal("1.00"),
        employment_type=EmploymentType.PERMANENT,
        status=StaffingSlotStatus.PLANNED,
        effective_from=date(2027, 1, 1),
    )


@pytest.mark.asyncio
async def test_staffing_creation_builds_reporting_chain_and_rejects_reporting_cycle(
    scenario: OrganizationScenario,
) -> None:
    version, _unit_type, root, _policy = scenario.add_valid_draft()
    manager_position = scenario.add_position(code="CEO")
    specialist_position = scenario.add_position(code="SPECIALIST")

    manager = await scenario.service.create_staffing_slot(
        staffing_command(
            version_id=version.id,
            version_revision=version.revision,
            unit_id=root.id,
            position_id=manager_position.id,
            head_of_unit=True,
        ),
        scenario.actor,
    )
    specialist = await scenario.service.create_staffing_slot(
        staffing_command(
            version_id=version.id,
            version_revision=version.revision,
            unit_id=root.id,
            position_id=specialist_position.id,
            reports_to_slot_id=manager.id,
        ),
        scenario.actor,
    )

    assert specialist.reports_to_slot_id == manager.id
    assert version.revision == 3
    assert [item.action for item in scenario.uow.audit.items] == [
        "staffingSlotCreated",
        "staffingSlotCreated",
    ]
    assert [item.event_type for item in scenario.uow.outbox.items] == [
        "staffingSlotCreated",
        "staffingSlotCreated",
    ]

    with pytest.raises(StructureCycleError) as cycle:
        await scenario.service.update_staffing_slot(
            UpdateStaffingSlotCommand(
                slot_id=manager.id,
                version_revision=version.revision,
                slot_revision=manager.revision,
                changes={"reports_to_slot_id": specialist.id},
            ),
            scenario.actor,
        )
    assert cycle.value.code == "ORG_STRUCTURE_CYCLE"
    stored_manager = await scenario.uow.staffing.get(manager.id)
    assert stored_manager is not None
    assert stored_manager.reports_to_slot_id is None

    with pytest.raises(OrganizationError, match="already has an active head"):
        await scenario.service.create_staffing_slot(
            staffing_command(
                version_id=version.id,
                version_revision=version.revision,
                unit_id=root.id,
                position_id=specialist_position.id,
                head_of_unit=True,
            ),
            scenario.actor,
        )
    assert len(await scenario.uow.staffing.list_by_version(version.id)) == 2
    assert scenario.uow.commits == 2


@pytest.mark.asyncio
async def test_manager_staffing_creation_respects_version_policy(
    scenario: OrganizationScenario,
) -> None:
    version, _unit_type, root, policy = scenario.add_valid_draft()
    position = scenario.add_position(code="COORDINATOR")
    manager_authorizer = RecordingAuthorizer(
        deny_organization_wide=frozenset({PERMISSION_STAFFING_MANAGE})
    )
    service = OrganizationService(scenario.uow, authorizer=manager_authorizer)
    command = staffing_command(
        version_id=version.id,
        version_revision=version.revision,
        unit_id=root.id,
        position_id=position.id,
    )

    with pytest.raises(PermissionDeniedError) as denied:
        await service.create_staffing_slot(command, scenario.actor)
    assert denied.value.code == "AUTH_FORBIDDEN"
    assert [call.unit_id for call in manager_authorizer.calls] == [root.id, None]
    assert await scenario.uow.staffing.list_by_version(version.id) == ()

    stored_policy = await scenario.uow.policies.get_for_version(version.id)
    assert stored_policy is not None
    stored_policy.managers_can_create_staffing_slots = True
    manager_authorizer.calls.clear()
    created = await service.create_staffing_slot(command, scenario.actor)

    assert created.organization_unit_id == root.id
    assert [call.unit_id for call in manager_authorizer.calls] == [root.id]
    assert policy.id == stored_policy.id


@pytest.mark.asyncio
async def test_future_slot_closure_requires_reassignment_and_uses_closing_state(
    scenario: OrganizationScenario,
) -> None:
    version, _unit_type, root, _policy = scenario.add_valid_draft()
    manager_position = scenario.add_position(code="CLOSE-MANAGER")
    specialist_position = scenario.add_position(code="CLOSE-SPECIALIST")
    manager = await scenario.service.create_staffing_slot(
        staffing_command(
            version_id=version.id,
            version_revision=version.revision,
            unit_id=root.id,
            position_id=manager_position.id,
            head_of_unit=True,
        ),
        scenario.actor,
    )
    specialist = await scenario.service.create_staffing_slot(
        staffing_command(
            version_id=version.id,
            version_revision=version.revision,
            unit_id=root.id,
            position_id=specialist_position.id,
            reports_to_slot_id=manager.id,
        ),
        scenario.actor,
    )
    close_on = date.today() + timedelta(days=365)

    with pytest.raises(OrganizationError, match="active direct reports"):
        await scenario.service.close_staffing_slot(
            CloseStaffingSlotCommand(
                slot_id=manager.id,
                version_revision=version.revision,
                slot_revision=manager.revision,
                effective_to=close_on,
                reason="Planned reorganization",
            ),
            scenario.actor,
        )

    scheduled = await scenario.service.close_staffing_slot(
        CloseStaffingSlotCommand(
            slot_id=specialist.id,
            version_revision=version.revision,
            slot_revision=specialist.revision,
            effective_to=close_on,
            reason="Planned reorganization",
        ),
        scenario.actor,
    )
    assert scheduled.status is StaffingSlotStatus.CLOSING
    assert scheduled.effective_status() is StaffingSlotStatus.CLOSING
    assert scenario.uow.audit.items[-1].action == "staffingSlotClosureScheduled"
    assert scenario.uow.outbox.items[-1].event_type == "staffingSlotClosureScheduled"

    with pytest.raises(OrganizationError, match="active direct reports"):
        await scenario.service.close_staffing_slot(
            CloseStaffingSlotCommand(
                slot_id=manager.id,
                version_revision=version.revision,
                slot_revision=manager.revision,
                effective_to=close_on - timedelta(days=100),
                reason="Manager cannot close before the direct report",
            ),
            scenario.actor,
        )

    with pytest.raises(StaffingSlotNotAvailableError):
        await scenario.service.create_staffing_slot(
            staffing_command(
                version_id=version.id,
                version_revision=version.revision,
                unit_id=root.id,
                position_id=specialist_position.id,
                reports_to_slot_id=scheduled.id,
            ),
            scenario.actor,
        )

    current_version = await scenario.uow.versions.get(version.id)
    assert current_version is not None
    manager_closure = await scenario.service.close_staffing_slot(
        CloseStaffingSlotCommand(
            slot_id=manager.id,
            version_revision=current_version.revision,
            slot_revision=manager.revision,
            effective_to=close_on + timedelta(days=1),
            reason="Manager closes after the direct report",
        ),
        scenario.actor,
    )
    assert manager_closure.status is StaffingSlotStatus.CLOSING
