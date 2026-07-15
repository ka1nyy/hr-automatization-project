"""Whole-draft validation, publication, review policy, and version history."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.modules.organization.application.commands import (
    CreateDraftCommand,
    PublishStructureCommand,
    SubmitReviewCommand,
)
from app.modules.organization.application.service import OrganizationService
from app.modules.organization.domain.entities import (
    OrganizationRelationship,
    OrganizationUnit,
    StaffingSlot,
)
from app.modules.organization.domain.enums import (
    EmploymentType,
    ReviewRequestStatus,
    StaffingSlotStatus,
    StructureVersionStatus,
    ValidationSeverity,
)
from app.modules.organization.domain.errors import (
    DraftValidationError,
    OrganizationError,
    VersionConflictError,
)
from app.modules.organization.domain.validation import ValidationIssue

from .fakes import OrganizationScenario, StubExternalValidator


@pytest.mark.asyncio
async def test_validate_draft_collects_all_internal_and_external_problems(
    scenario: OrganizationScenario,
) -> None:
    version = scenario.add_version()
    version.effective_from = date(2027, 12, 31)
    version.effective_to = date(2027, 1, 1)
    unit_type = scenario.add_unit_type()
    missing_type_id = uuid4()
    shared_stable_key = uuid4()
    first = OrganizationUnit(
        id=uuid4(),
        structure_version_id=version.id,
        stable_key=shared_stable_key,
        code="DUPLICATE",
        name="First",
        unit_type_id=unit_type.id,
        parent_unit_id=None,
    )
    second = OrganizationUnit(
        id=uuid4(),
        structure_version_id=version.id,
        stable_key=shared_stable_key,
        code="duplicate",
        name="Second",
        unit_type_id=missing_type_id,
        parent_unit_id=first.id,
    )
    first.parent_unit_id = second.id
    orphan = OrganizationUnit(
        id=uuid4(),
        structure_version_id=version.id,
        code="ORPHAN",
        name="Orphan",
        unit_type_id=unit_type.id,
        parent_unit_id=uuid4(),
    )
    for unit in (first, second, orphan):
        scenario.uow.units.seed(unit)

    relationship_type = scenario.add_relationship_type(prevents_cycles=True)
    relationships = (
        OrganizationRelationship(
            id=uuid4(),
            structure_version_id=version.id,
            relationship_type_id=relationship_type.id,
            source_unit_id=first.id,
            target_unit_id=second.id,
        ),
        OrganizationRelationship(
            id=uuid4(),
            structure_version_id=version.id,
            relationship_type_id=relationship_type.id,
            source_unit_id=second.id,
            target_unit_id=first.id,
        ),
        OrganizationRelationship(
            id=uuid4(),
            structure_version_id=version.id,
            relationship_type_id=relationship_type.id,
            source_unit_id=first.id,
            target_unit_id=first.id,
        ),
    )
    relationships[-1].effective_from = date(2027, 8, 1)
    relationships[-1].effective_to = date(2027, 7, 1)
    for relationship in relationships:
        scenario.uow.relationships.seed(relationship)

    bad_slot = StaffingSlot(
        id=uuid4(),
        structure_version_id=version.id,
        organization_unit_id=uuid4(),
        position_definition_id=uuid4(),
        reports_to_slot_id=uuid4(),
        full_time_equivalent=Decimal("0.5"),
        employment_type=EmploymentType.PERMANENT,
        status=StaffingSlotStatus.PLANNED,
        effective_from=date(2027, 6, 1),
        effective_to=date(2027, 6, 30),
    )
    bad_slot.full_time_equivalent = Decimal("1.5")
    bad_slot.effective_to = date(2027, 5, 1)
    scenario.uow.staffing.seed(bad_slot)
    scenario.add_policy(version)

    external_issue = ValidationIssue(
        code="EMPLOYEE_ASSIGNMENT_OUTSIDE_VERSION",
        message="An active employee assignment points outside the draft.",
        severity=ValidationSeverity.ERROR,
        path="employeeAssignments",
    )
    external = StubExternalValidator((external_issue,))
    service = OrganizationService(
        scenario.uow,
        authorizer=scenario.authorizer,
        external_validator=external,
    )

    outcome = await service.validate_draft(version.id, scenario.actor)

    codes = {issue.code for issue in outcome.report.issues}
    assert {
        "ORG_STRUCTURE_INVALID_DATE_RANGE",
        "ORG_STRUCTURE_MULTIPLE_ROOTS",
        "ORG_STRUCTURE_ORPHAN_UNIT",
        "ORG_STRUCTURE_INVALID_UNIT_TYPE",
        "ORG_STRUCTURE_DUPLICATE_UNIT_CODE",
        "ORG_STRUCTURE_DUPLICATE_STABLE_KEY",
        "ORG_STRUCTURE_CYCLE",
        "ORG_STRUCTURE_INVALID_RELATIONSHIP",
        "ORG_STRUCTURE_INVALID_STAFFING_REFERENCE",
        "STAFFING_FTE_EXCEEDED",
        "EMPLOYEE_ASSIGNMENT_OUTSIDE_VERSION",
    } <= codes
    bad_slot_paths = {
        issue.path for issue in outcome.report.issues if issue.entity_id == bad_slot.id
    }
    assert bad_slot_paths == {
        "organizationUnitId",
        "positionDefinitionId",
        "fullTimeEquivalent",
        "effectiveTo",
        "reportsToSlotId",
    }
    assert outcome.report.is_valid is False
    assert outcome.report.error_count >= 14
    assert outcome.report.warning_count == 3
    assert external.version_ids == [version.id]
    assert external.effective_dates == [None]
    validation_audit = scenario.uow.audit.items[-1]
    assert validation_audit.action == "organizationStructureValidated"
    assert validation_audit.after is not None
    assert validation_audit.after["errorCount"] == outcome.report.error_count
    assert len(validation_audit.after["issues"]) == len(outcome.report.issues)
    assert scenario.uow.commits == 1


@pytest.mark.asyncio
async def test_valid_draft_with_warnings_can_publish_and_emits_event(
    scenario: OrganizationScenario,
) -> None:
    version, _unit_type, root, _policy = scenario.add_valid_draft()

    outcome = await scenario.service.validate_draft(version.id, scenario.actor)
    assert outcome.report.is_valid is True
    assert outcome.report.error_count == 0
    assert outcome.report.warning_count == 1
    assert outcome.report.issues[0].entity_id == root.id

    external = StubExternalValidator()
    service = OrganizationService(
        scenario.uow,
        authorizer=scenario.authorizer,
        external_validator=external,
    )
    published = await service.publish_structure(
        PublishStructureCommand(
            version_id=version.id,
            revision=version.revision,
            effective_from=date(2027, 1, 1),
            reason="Approved annual operating model",
        ),
        scenario.actor,
    )

    assert published.status is StructureVersionStatus.PUBLISHED
    assert published.effective_from == date(2027, 1, 1)
    assert published.published_by == scenario.actor.user_id
    assert published.published_at is not None
    assert published.revision == 2
    assert scenario.uow.audit.items[-1].action == "organizationStructurePublished"
    assert scenario.uow.audit.items[-1].reason == "Approved annual operating model"
    event = scenario.uow.outbox.items[-1]
    assert event.event_type == "organizationStructurePublished"
    assert event.aggregate_id == version.id
    assert event.payload["effectiveFrom"] == "2027-01-01"
    assert event.payload["revision"] == 2
    assert external.effective_dates == [date(2027, 1, 1)]


@pytest.mark.asyncio
async def test_invalid_draft_cannot_publish_or_write_audit_and_outbox(
    scenario: OrganizationScenario,
) -> None:
    version = scenario.add_version()
    scenario.add_policy(
        version,
        structure_publish_requires_review=False,
        staffing_changes_require_finance_review=False,
    )

    with pytest.raises(DraftValidationError) as invalid:
        await scenario.service.publish_structure(
            PublishStructureCommand(
                version_id=version.id,
                revision=version.revision,
                effective_from=date(2027, 1, 1),
                reason="Premature publication",
            ),
            scenario.actor,
        )

    assert invalid.value.details["issues"] == [
        {
            "code": "ORG_STRUCTURE_MULTIPLE_ROOTS",
            "message": "A structure version must contain exactly one active root unit.",
            "severity": "error",
            "path": "units",
            "entityId": None,
            "details": {"rootCount": 0, "rootIds": []},
        }
    ]
    stored = await scenario.uow.versions.get(version.id)
    assert stored is not None
    assert stored.status is StructureVersionStatus.DRAFT
    assert stored.revision == 1
    assert scenario.uow.audit.items == []
    assert scenario.uow.outbox.items == []
    assert scenario.uow.commits == 0


@pytest.mark.asyncio
async def test_publishing_successor_closes_but_preserves_prior_version_history(
    scenario: OrganizationScenario,
) -> None:
    prior = scenario.add_version(
        status=StructureVersionStatus.PUBLISHED,
        name="2026 structure",
        effective_from=date(2026, 1, 1),
    )
    unit_type = scenario.add_unit_type()
    prior_root = scenario.add_unit(
        prior,
        unit_type,
        code="ROOT",
        name="Historic Corporate Center",
    )
    scenario.add_policy(
        prior,
        structure_publish_requires_review=False,
        staffing_changes_require_finance_review=False,
    )
    successor = await scenario.service.create_draft(
        CreateDraftCommand(
            organization_id=scenario.organization.id,
            name="2027 structure",
            based_on_version_id=prior.id,
        ),
        scenario.actor,
    )
    successor_root = next(
        item
        for item in await scenario.uow.units.list_by_version(successor.id)
        if item.stable_key == prior_root.stable_key
    )

    await scenario.service.publish_structure(
        PublishStructureCommand(
            version_id=successor.id,
            revision=successor.revision,
            effective_from=date(2027, 1, 1),
            reason="Annual transition",
        ),
        scenario.actor,
    )

    assert prior.status is StructureVersionStatus.PUBLISHED
    assert prior.effective_from == date(2026, 1, 1)
    assert prior.effective_to == date(2026, 12, 31)
    assert prior.revision == 2
    assert successor.status is StructureVersionStatus.PUBLISHED
    assert successor_root.id != prior_root.id
    assert successor_root.stable_key == prior_root.stable_key
    assert prior_root.name == "Historic Corporate Center"
    old_view = await scenario.service.read_active_structure(
        scenario.organization.id, scenario.actor, on_date=date(2026, 6, 1)
    )
    new_view = await scenario.service.read_active_structure(
        scenario.organization.id, scenario.actor, on_date=date(2027, 6, 1)
    )
    assert old_view.version.id == prior.id
    assert old_view.root is not None and old_view.root.unit.id == prior_root.id
    assert new_view.version.id == successor.id
    assert new_view.root is not None and new_view.root.unit.id == successor_root.id
    publish_audit = scenario.uow.audit.items[-1]
    assert publish_audit.after is not None
    assert publish_audit.after["closedVersionIds"] == [str(prior.id)]


@pytest.mark.asyncio
async def test_structure_review_policy_requires_pending_review_and_approves_it_on_publish(
    scenario: OrganizationScenario,
) -> None:
    version, _unit_type, _root, _policy = scenario.add_valid_draft(
        structure_publish_requires_review=True
    )
    publish = PublishStructureCommand(
        version_id=version.id,
        revision=version.revision,
        effective_from=date(2027, 1, 1),
        reason="Board approval",
    )

    with pytest.raises(VersionConflictError) as review_required:
        await scenario.service.publish_structure(publish, scenario.actor)
    assert review_required.value.details == {"reviewReasons": ["structurePolicy"]}

    review = await scenario.service.submit_for_review(
        SubmitReviewCommand(
            version_id=version.id,
            revision=version.revision,
            reason="Ready for board review",
        ),
        scenario.actor,
    )
    in_review = await scenario.uow.versions.get(version.id)
    assert in_review is not None
    assert in_review.status is StructureVersionStatus.IN_REVIEW
    assert in_review.revision == 2
    assert review.status is ReviewRequestStatus.PENDING

    with pytest.raises(OrganizationError) as missing_revision:
        await scenario.service.publish_structure(
            PublishStructureCommand(
                version_id=version.id,
                revision=in_review.revision,
                effective_from=date(2027, 1, 1),
                reason="Board approval",
            ),
            scenario.actor,
        )
    assert missing_revision.value.details == {"field": "reviewRevision"}

    published = await scenario.service.publish_structure(
        PublishStructureCommand(
            version_id=version.id,
            revision=in_review.revision,
            effective_from=date(2027, 1, 1),
            reason="Board approval",
            review_revision=review.revision,
        ),
        scenario.actor,
    )
    stored_review = await scenario.uow.review_requests.get(review.id)
    assert stored_review is not None
    assert stored_review.status is ReviewRequestStatus.APPROVED
    assert stored_review.resolved_by == scenario.actor.user_id
    assert stored_review.resolution_reason == "Board approval"
    assert stored_review.revision == 2
    assert published.status is StructureVersionStatus.PUBLISHED
    assert [item.action for item in scenario.uow.audit.items] == [
        "organizationStructureSubmittedForReview",
        "organizationStructurePublished",
    ]


@pytest.mark.asyncio
async def test_staffing_finance_policy_requires_review_only_when_staffing_changed(
    scenario: OrganizationScenario,
) -> None:
    version, _unit_type, root, _policy = scenario.add_valid_draft(
        staffing_changes_require_finance_review=True
    )
    position = scenario.add_position(code="PLANNER")
    scenario.add_slot(version, root, position)

    with pytest.raises(VersionConflictError) as review_required:
        await scenario.service.publish_structure(
            PublishStructureCommand(
                version_id=version.id,
                revision=version.revision,
                effective_from=date(2027, 1, 1),
                reason="Staffing plan",
            ),
            scenario.actor,
        )

    assert review_required.value.details == {"reviewReasons": ["staffingFinancePolicy"]}
    stored = await scenario.uow.versions.get(version.id)
    assert stored is not None and stored.status is StructureVersionStatus.DRAFT
    assert scenario.uow.audit.items == []
    assert scenario.uow.outbox.items == []
