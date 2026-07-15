"""Draft creation, cloning, primary-tree editing, and locking behavior."""

from datetime import date
from uuid import uuid4

import pytest
from app.modules.organization.application.commands import (
    AddUnitCommand,
    CreateDraftCommand,
    MoveUnitCommand,
    UpdateUnitCommand,
)
from app.modules.organization.domain.entities import (
    OrganizationRelationship,
    OrganizationStructureVersion,
)
from app.modules.organization.domain.enums import StructureVersionStatus
from app.modules.organization.domain.errors import (
    ConcurrencyConflictError,
    MultipleRootsError,
    StructureCycleError,
)

from .fakes import OrganizationScenario


@pytest.mark.asyncio
async def test_structure_version_sort_is_applied_before_pagination(
    scenario: OrganizationScenario,
) -> None:
    scenario.uow.versions.seed(
        OrganizationStructureVersion(
            organization_id=scenario.organization.id,
            version_number=1,
            name="First",
            created_by=scenario.actor.user_id,
        )
    )
    scenario.uow.versions.seed(
        OrganizationStructureVersion(
            organization_id=scenario.organization.id,
            version_number=2,
            name="Second",
            created_by=scenario.actor.user_id,
        )
    )

    items, total = await scenario.service.list_versions(
        scenario.organization.id,
        scenario.actor,
        page=1,
        page_size=1,
        sort="-versionNumber",
    )

    assert total == 2
    assert [item.version_number for item in items] == [2]


@pytest.mark.asyncio
async def test_create_draft_then_add_and_rename_root_records_full_change_history(
    scenario: OrganizationScenario,
) -> None:
    version = await scenario.service.create_draft(
        CreateDraftCommand(
            organization_id=scenario.organization.id,
            name="  FY 2027   design  ",
        ),
        scenario.actor,
    )

    assert version.status is StructureVersionStatus.DRAFT
    assert version.name == "FY 2027 design"
    assert version.version_number == 1
    assert version.based_on_version_id is None
    policy = await scenario.uow.policies.get_for_version(version.id)
    assert policy is not None
    assert policy.structure_publish_requires_review is True

    unit_type = scenario.add_unit_type(code="HOLDING", name="Holding company")
    root = await scenario.service.add_unit(
        AddUnitCommand(
            version_id=version.id,
            version_revision=version.revision,
            code=" root ",
            name="Corporate Center",
            short_name="HQ",
            unit_type_id=unit_type.id,
            parent_unit_id=None,
        ),
        scenario.actor,
    )
    renamed = await scenario.service.update_unit(
        UpdateUnitCommand(
            version_id=version.id,
            unit_id=root.id,
            version_revision=version.revision,
            unit_revision=root.revision,
            changes={"name": "  Executive   Center ", "short_name": "EC"},
        ),
        scenario.actor,
    )

    assert renamed is root
    assert renamed.code == "ROOT"
    assert renamed.name == "Executive Center"
    assert renamed.short_name == "EC"
    assert renamed.revision == 2
    assert version.revision == 3
    assert scenario.uow.units.persisted_revisions[root.id] == 2
    assert scenario.uow.versions.persisted_revisions[version.id] == 3
    assert scenario.uow.commits == 3

    actions = [item.action for item in scenario.uow.audit.items]
    assert actions == [
        "organizationStructureDraftCreated",
        "organizationUnitCreated",
        "organizationUnitChanged",
    ]
    rename_audit = scenario.uow.audit.items[-1]
    assert rename_audit.before is not None
    assert rename_audit.before["name"] == "Corporate Center"
    assert rename_audit.after is not None
    assert rename_audit.after["name"] == "Executive Center"
    assert rename_audit.request_id == scenario.actor.request_id
    assert [item.event_type for item in scenario.uow.outbox.items] == [
        "organizationUnitChanged",
        "organizationUnitChanged",
    ]
    assert scenario.uow.outbox.items[-1].payload == {
        "action": "updated",
        "versionId": str(version.id),
    }


@pytest.mark.asyncio
async def test_clone_published_draft_remaps_internal_ids_and_preserves_stable_history(
    scenario: OrganizationScenario,
) -> None:
    base = scenario.add_version(
        status=StructureVersionStatus.PUBLISHED,
        name="Current structure",
        effective_from=date(2026, 1, 1),
    )
    unit_type = scenario.add_unit_type()
    root = scenario.add_unit(
        base,
        unit_type,
        code="ROOT",
        custom_fields={"costCenter": "1000"},
    )
    branch = scenario.add_unit(
        base,
        unit_type,
        code="FIN",
        name="Finance",
        parent=root,
        custom_fields={"costCenter": "1100"},
    )
    relationship_type = scenario.add_relationship_type()
    relationship = scenario.uow.relationships.seed(
        OrganizationRelationship(
            id=uuid4(),
            structure_version_id=base.id,
            relationship_type_id=relationship_type.id,
            source_unit_id=root.id,
            target_unit_id=branch.id,
            metadata={"purpose": "oversight"},
            revision=4,
        )
    )
    manager_position = scenario.add_position(code="CFO")
    analyst_position = scenario.add_position(code="ANALYST")
    manager = scenario.add_slot(
        base,
        branch,
        manager_position,
        head_of_unit=True,
        custom_fields={"budgetOwner": True},
    )
    analyst = scenario.add_slot(base, branch, analyst_position, reports_to=manager)
    base_policy = scenario.add_policy(
        base,
        managers_can_create_staffing_slots=True,
        allow_cross_unit_relationships=False,
    )
    root.revision = 7
    scenario.uow.units.persisted_revisions[root.id] = 7

    cloned = await scenario.service.create_draft(
        CreateDraftCommand(
            organization_id=scenario.organization.id,
            name="Future structure",
            based_on_version_id=base.id,
        ),
        scenario.actor,
    )

    cloned_units = list(await scenario.uow.units.list_by_version(cloned.id, include_inactive=True))
    cloned_by_key = {item.stable_key: item for item in cloned_units}
    cloned_root = cloned_by_key[root.stable_key]
    cloned_branch = cloned_by_key[branch.stable_key]
    assert cloned.based_on_version_id == base.id
    assert cloned.version_number == 2
    assert {item.id for item in cloned_units}.isdisjoint({root.id, branch.id})
    assert cloned_root.revision == 1
    assert cloned_branch.parent_unit_id == cloned_root.id
    assert cloned_root.custom_fields == root.custom_fields
    assert cloned_root.custom_fields is not root.custom_fields

    cloned_relationships = list(
        await scenario.uow.relationships.list_by_version(cloned.id, include_inactive=True)
    )
    assert len(cloned_relationships) == 1
    cloned_relationship = cloned_relationships[0]
    assert cloned_relationship.id != relationship.id
    assert cloned_relationship.revision == 1
    assert (cloned_relationship.source_unit_id, cloned_relationship.target_unit_id) == (
        cloned_root.id,
        cloned_branch.id,
    )
    assert cloned_relationship.metadata == relationship.metadata
    assert cloned_relationship.metadata is not relationship.metadata

    cloned_slots = list(await scenario.uow.staffing.list_by_version(cloned.id))
    cloned_slots_by_key = {item.stable_key: item for item in cloned_slots}
    cloned_manager = cloned_slots_by_key[manager.stable_key]
    cloned_analyst = cloned_slots_by_key[analyst.stable_key]
    assert cloned_manager.id != manager.id
    assert cloned_analyst.reports_to_slot_id == cloned_manager.id
    assert cloned_manager.organization_unit_id == cloned_branch.id
    assert all(item.revision == 1 for item in cloned_slots)

    cloned_policy = await scenario.uow.policies.get_for_version(cloned.id)
    assert cloned_policy is not None
    assert cloned_policy.id != base_policy.id
    assert cloned_policy.managers_can_create_staffing_slots is True
    assert cloned_policy.allow_cross_unit_relationships is False
    assert base.status is StructureVersionStatus.PUBLISHED
    assert base.effective_to is None
    assert root.id in scenario.uow.units.items


@pytest.mark.asyncio
async def test_move_updates_parent_but_rejects_cycle_and_second_root(
    scenario: OrganizationScenario,
) -> None:
    version, unit_type, root, _policy = scenario.add_valid_draft()
    finance = scenario.add_unit(version, unit_type, code="FIN", parent=root, sort_order=0)
    accounting = scenario.add_unit(version, unit_type, code="ACC", parent=finance, sort_order=0)

    moved = await scenario.service.move_unit(
        MoveUnitCommand(
            version_id=version.id,
            unit_id=accounting.id,
            version_revision=version.revision,
            unit_revision=accounting.revision,
            parent_unit_id=root.id,
            sort_order=1,
        ),
        scenario.actor,
    )
    assert moved.parent_unit_id == root.id
    assert moved.sort_order == 1
    assert moved.revision == 2
    assert scenario.uow.audit.items[-1].action == "organizationUnitMoved"
    assert scenario.uow.outbox.items[-1].payload["action"] == "moved"

    commits_after_move = scenario.uow.commits
    with pytest.raises(StructureCycleError) as cycle:
        await scenario.service.move_unit(
            MoveUnitCommand(
                version_id=version.id,
                unit_id=root.id,
                version_revision=version.revision,
                unit_revision=root.revision,
                parent_unit_id=finance.id,
                sort_order=0,
            ),
            scenario.actor,
        )
    assert cycle.value.code == "ORG_STRUCTURE_CYCLE"
    assert root.parent_unit_id is None

    with pytest.raises(MultipleRootsError) as roots:
        await scenario.service.add_unit(
            AddUnitCommand(
                version_id=version.id,
                version_revision=version.revision,
                code="SECOND_ROOT",
                name="Second root",
                unit_type_id=unit_type.id,
                parent_unit_id=None,
            ),
            scenario.actor,
        )
    assert roots.value.details["existingRootId"] == str(root.id)
    assert scenario.uow.commits == commits_after_move


@pytest.mark.asyncio
async def test_stale_unit_and_version_revisions_fail_without_writes(
    scenario: OrganizationScenario,
) -> None:
    version, unit_type, root, _policy = scenario.add_valid_draft()

    with pytest.raises(ConcurrencyConflictError) as stale_unit:
        await scenario.service.update_unit(
            UpdateUnitCommand(
                version_id=version.id,
                unit_id=root.id,
                version_revision=version.revision,
                unit_revision=root.revision + 10,
                changes={"name": "Should not persist"},
            ),
            scenario.actor,
        )
    assert stale_unit.value.details == {
        "entity": "organizationUnit",
        "entityId": str(root.id),
        "expectedRevision": 11,
    }
    assert root.name == "Corporate Center"

    with pytest.raises(ConcurrencyConflictError) as stale_version:
        await scenario.service.add_unit(
            AddUnitCommand(
                version_id=version.id,
                version_revision=version.revision + 1,
                code="NEW",
                name="New unit",
                unit_type_id=unit_type.id,
                parent_unit_id=root.id,
            ),
            scenario.actor,
        )
    assert stale_version.value.details["entity"] == "organizationStructureVersion"
    assert stale_version.value.details["expectedRevision"] == 2
    assert len(await scenario.uow.units.list_by_version(version.id)) == 1
    assert scenario.uow.audit.items == []
    assert scenario.uow.outbox.items == []
    assert scenario.uow.commits == 0
