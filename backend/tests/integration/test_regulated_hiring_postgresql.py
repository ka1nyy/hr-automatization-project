from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.security.identity import Principal
from app.modules.regulated_hiring.application.service import RegulatedHiringService
from app.seed import DIRECTOR_EMPLOYEE_ID, ORGANIZATION_ID, _development_user_id
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_regulated_catalog_seed_and_case_progression(
    seeded_database: AsyncEngine,
) -> None:
    async with seeded_database.connect() as connection:
        counts = (
            await connection.execute(
                text(
                    """
                    SELECT
                        (SELECT count(*) FROM regulated_hiring_stage_definitions
                         WHERE active = true) AS stages,
                        (SELECT count(*) FROM regulated_hiring_form_definitions
                         WHERE active = true) AS forms,
                        (SELECT count(*) FROM normative_sources) AS sources,
                        (SELECT count(*) FROM authority_bindings
                         WHERE authority_status = 'confirmed') AS confirmed_bindings
                    """
                )
            )
        ).one()
        slot = (
            await connection.execute(
                text(
                    """
                    SELECT slot.id, slot.organization_unit_id, slot.position_definition_id
                    FROM staffing_slots AS slot
                    JOIN authority_bindings AS binding
                      ON binding.entity_type = 'staffing_slot'
                     AND binding.entity_id = slot.id
                     AND binding.authority_status = 'confirmed'
                    WHERE slot.status = 'vacant'
                    ORDER BY slot.id
                    LIMIT 1
                    """
                )
            )
        ).one()

    assert dict(counts._mapping) == {
        "stages": 23,
        "forms": 21,
        "sources": 10,
        "confirmed_bindings": 8,
    }

    request_id = uuid4()
    async with seeded_database.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO recruitment_requests (
                    id, organization_id, requesting_unit_id, requested_by_employee_id,
                    staffing_slot_id, position_definition_id, requested_fte,
                    employment_type, desired_start_date, reason, responsibilities,
                    requirements, proposed_compensation, status, process_instance_id,
                    revision, created_at, updated_at
                ) VALUES (
                    :id, :organization_id, :unit_id, :employee_id, :slot_id, :position_id,
                    1.00, 'permanent', DATE '2026-08-01', 'Confirmed need',
                    'Department management', 'Approved requirements', NULL, 'approved',
                    NULL, 1, now(), now()
                )
                """
            ),
            {
                "id": request_id,
                "organization_id": ORGANIZATION_ID,
                "unit_id": slot.organization_unit_id,
                "employee_id": DIRECTOR_EMPLOYEE_ID,
                "slot_id": slot.id,
                "position_id": slot.position_definition_id,
            },
        )

    from app.core.database import session as database_session

    service = RegulatedHiringService(database_session.async_session_factory)
    principal = Principal(
        user_id=_development_user_id("admin"),
        subject="integration-admin",
        organization_id=ORGANIZATION_ID,
        role_codes=frozenset({"system-administrator"}),
    )
    case = await service.start_case(
        principal,
        organization_id=ORGANIZATION_ID,
        recruitment_request_id=request_id,
        staffing_slot_id=slot.id,
        business_key=f"NAIM-{request_id}",
        process_engine="local",
        camunda_process_instance_key=None,
    )
    assert case["currentStageSequence"] == 0

    stage_one = await service.act_on_stage(
        principal,
        case_id=case["id"],
        organization_id=ORGANIZATION_ID,
        expected_revision=case["revision"],
        action="complete",
        idempotency_key=f"{request_id}:need",
        reason=None,
        evidence={},
        return_to_sequence=None,
    )
    assert stage_one["currentStageSequence"] == 1

    stage_two = await service.act_on_stage(
        principal,
        case_id=case["id"],
        organization_id=ORGANIZATION_ID,
        expected_revision=stage_one["revision"],
        action="complete",
        idempotency_key=f"{request_id}:slot",
        reason=None,
        evidence={"slotConfirmed": True, "slotVacant": True},
        return_to_sequence=None,
    )
    assert stage_two["currentStageSequence"] == 2
