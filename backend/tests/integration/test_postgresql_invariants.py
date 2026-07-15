"""Integration coverage for invariants that only a real PostgreSQL DB can prove."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "access_scope_units",
    "access_scopes",
    "alembic_version",
    "audit_events",
    "delegations",
    "employee_assignment_review_requests",
    "employee_assignments",
    "employees",
    "organization_policies",
    "organization_relationship_types",
    "organization_relationships",
    "organization_structure_review_requests",
    "organization_structure_versions",
    "organization_unit_type_allowed_parents",
    "organization_unit_types",
    "organization_units",
    "organizations",
    "outbox_events",
    "people",
    "permissions",
    "position_definitions",
    "role_permissions",
    "roles",
    "staffing_slots",
    "user_accounts",
    "user_role_assignments",
}


def _schema_snapshot(connection: Connection) -> tuple[set[str], str]:
    tables = set(inspect(connection).get_table_names(schema="public"))
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    return tables, revision


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


async def _insert_atomic_pair(
    connection: AsyncConnection,
    *,
    organization_id: UUID,
    event_id: UUID,
    suffix: str,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO organizations
                (id, code, legal_name, display_name, status)
            VALUES
                (:id, :code, :legal_name, :display_name, 'active')
            """
        ),
        {
            "id": organization_id,
            "code": f"TX-{suffix}",
            "legal_name": f"Transaction test {suffix}",
            "display_name": f"Transaction test {suffix}",
        },
    )
    await connection.execute(
        text(
            """
            INSERT INTO outbox_events
                (id, event_name, aggregate_type, aggregate_id, payload, schema_version)
            VALUES
                (:id, 'organizationCreated', 'organization', :aggregate_id, '{}'::jsonb, 1)
            """
        ),
        {"id": event_id, "aggregate_id": organization_id},
    )


@pytest.mark.asyncio
async def test_alembic_upgrade_from_empty_creates_complete_schema(
    migrated_database: AsyncEngine,
) -> None:
    async with migrated_database.connect() as connection:
        tables, revision = await connection.run_sync(_schema_snapshot)

    from app.core.database import Base

    assert tables == EXPECTED_TABLES
    assert set(Base.metadata.tables) == EXPECTED_TABLES - {"alembic_version"}
    assert revision == "0001_module1_initial"


@pytest.mark.asyncio
async def test_audit_events_reject_update_and_delete(
    migrated_database: AsyncEngine,
) -> None:
    event_id = uuid4()
    async with migrated_database.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO audit_events (id, action, entity_type, entity_id, reason)
                VALUES (:id, 'created', 'integrationTest', :entity_id, 'original')
                """
            ),
            {"id": event_id, "entity_id": uuid4()},
        )

    with pytest.raises(DBAPIError) as update_error:
        async with migrated_database.begin() as connection:
            await connection.execute(
                text("UPDATE audit_events SET reason = 'rewritten' WHERE id = :id"),
                {"id": event_id},
            )
    assert _sqlstate(update_error.value) == "55000"

    with pytest.raises(DBAPIError) as delete_error:
        async with migrated_database.begin() as connection:
            await connection.execute(
                text("DELETE FROM audit_events WHERE id = :id"),
                {"id": event_id},
            )
    assert _sqlstate(delete_error.value) == "55000"

    async with migrated_database.connect() as connection:
        reason = (
            await connection.execute(
                text("SELECT reason FROM audit_events WHERE id = :id"),
                {"id": event_id},
            )
        ).scalar_one()
    assert reason == "original"


@pytest.mark.asyncio
async def test_outbox_and_domain_write_commit_or_roll_back_together(
    migrated_database: AsyncEngine,
) -> None:
    rolled_back_organization_id = uuid4()
    rolled_back_event_id = uuid4()
    async with migrated_database.connect() as connection:
        transaction = await connection.begin()
        await _insert_atomic_pair(
            connection,
            organization_id=rolled_back_organization_id,
            event_id=rolled_back_event_id,
            suffix=rolled_back_organization_id.hex,
        )
        await transaction.rollback()

    async with migrated_database.connect() as connection:
        rolled_back_counts = (
            await connection.execute(
                text(
                    """
                    SELECT
                        (SELECT count(*) FROM organizations WHERE id = :organization_id),
                        (SELECT count(*) FROM outbox_events WHERE id = :event_id)
                    """
                ),
                {
                    "organization_id": rolled_back_organization_id,
                    "event_id": rolled_back_event_id,
                },
            )
        ).one()
    assert tuple(rolled_back_counts) == (0, 0)

    committed_organization_id = uuid4()
    committed_event_id = uuid4()
    async with migrated_database.begin() as connection:
        await _insert_atomic_pair(
            connection,
            organization_id=committed_organization_id,
            event_id=committed_event_id,
            suffix=committed_organization_id.hex,
        )

    async with migrated_database.connect() as connection:
        committed_counts = (
            await connection.execute(
                text(
                    """
                    SELECT
                        (SELECT count(*) FROM organizations WHERE id = :organization_id),
                        (SELECT count(*) FROM outbox_events WHERE id = :event_id)
                    """
                ),
                {
                    "organization_id": committed_organization_id,
                    "event_id": committed_event_id,
                },
            )
        ).one()
    assert tuple(committed_counts) == (1, 1)


@pytest.mark.asyncio
async def test_published_structure_versions_cannot_overlap(
    migrated_database: AsyncEngine,
) -> None:
    organization_id = uuid4()
    user_id = uuid4()
    first_version_id = uuid4()
    second_version_id = uuid4()

    async with migrated_database.connect() as connection:
        outer_transaction = await connection.begin()
        try:
            await connection.execute(
                text(
                    """
                    INSERT INTO organizations
                        (id, code, legal_name, display_name, status)
                    VALUES
                        (:id, :code, 'Overlap test', 'Overlap test', 'active')
                    """
                ),
                {"id": organization_id, "code": f"OVERLAP-{organization_id.hex}"},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO user_accounts
                        (id, external_subject, username, display_name, status, active)
                    VALUES
                        (:id, :subject, :username, 'Overlap test user', 'active', true)
                    """
                ),
                {
                    "id": user_id,
                    "subject": f"overlap-{user_id.hex}",
                    "username": f"overlap-{user_id.hex}",
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO organization_structure_versions
                        (id, organization_id, version_number, name, status,
                         effective_from, effective_to, created_by)
                    VALUES
                        (:id, :organization_id, 1, 'First', 'published',
                         :effective_from, :effective_to, :created_by)
                    """
                ),
                {
                    "id": first_version_id,
                    "organization_id": organization_id,
                    "effective_from": date(2026, 1, 1),
                    "effective_to": date(2026, 12, 31),
                    "created_by": user_id,
                },
            )

            with pytest.raises(IntegrityError) as overlap_error:
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO organization_structure_versions
                                (id, organization_id, version_number, name, status,
                                 effective_from, effective_to, created_by)
                            VALUES
                                (:id, :organization_id, 2, 'Second', 'published',
                                 :effective_from, :effective_to, :created_by)
                            """
                        ),
                        {
                            "id": second_version_id,
                            "organization_id": organization_id,
                            "effective_from": date(2026, 6, 1),
                            "effective_to": date(2027, 5, 31),
                            "created_by": user_id,
                        },
                    )
            assert _sqlstate(overlap_error.value) == "23P01"

            version_count = (
                await connection.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM organization_structure_versions
                        WHERE organization_id = :organization_id
                        """
                    ),
                    {"organization_id": organization_id},
                )
            ).scalar_one()
            assert version_count == 1
        finally:
            await outer_transaction.rollback()


@pytest.mark.asyncio
async def test_employee_primary_assignment_periods_cannot_overlap(
    seeded_database: AsyncEngine,
) -> None:
    async with seeded_database.connect() as connection:
        outer_transaction = await connection.begin()
        try:
            assignment_target = (
                await connection.execute(
                    text(
                        """
                        SELECT existing.employee_id, candidate.id AS staffing_slot_id
                        FROM employee_assignments AS existing
                        JOIN staffing_slots AS candidate
                          ON candidate.id <> existing.staffing_slot_id
                        WHERE existing."primary" = true
                          AND existing.status = 'active'
                        ORDER BY candidate.id
                        LIMIT 1
                        """
                    )
                )
            ).one()

            with pytest.raises(IntegrityError) as overlap_error:
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO employee_assignments
                                (id, employee_id, staffing_slot_id, assignment_type,
                                 full_time_equivalent, effective_from, effective_to,
                                 "primary", acting, status, created_at, updated_at, revision)
                            VALUES
                                (:id, :employee_id, :staffing_slot_id, 'concurrent',
                                 0.50, :effective_from, NULL,
                                 true, false, 'active', now(), now(), 1)
                            """
                        ),
                        {
                            "id": uuid4(),
                            "employee_id": assignment_target.employee_id,
                            "staffing_slot_id": assignment_target.staffing_slot_id,
                            "effective_from": date(2025, 6, 1),
                        },
                    )
            assert _sqlstate(overlap_error.value) == "23P01"

            primary_count = (
                await connection.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM employee_assignments
                        WHERE employee_id = :employee_id
                          AND "primary" = true
                          AND status IN
                              ('pending_review', 'planned', 'active', 'scheduled_end', 'ended')
                        """
                    ),
                    {"employee_id": assignment_target.employee_id},
                )
            ).scalar_one()
            assert primary_count == 1
        finally:
            await outer_transaction.rollback()


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_api_reports_database_ready(
    seeded_database: AsyncEngine,
) -> None:
    async with seeded_database.connect() as connection:
        seed_counts = (
            await connection.execute(
                text(
                    """
                    SELECT
                        (SELECT count(*) FROM organizations WHERE code = 'SPK-ERTIS')
                            AS organizations,
                        (SELECT count(*) FROM organization_structure_versions
                         WHERE status = 'published') AS published_versions,
                        (SELECT count(*) FROM organization_units) AS organization_units,
                        (SELECT count(*) FROM roles WHERE system = true) AS system_roles,
                        (SELECT count(*) FROM user_role_assignments) AS role_assignments,
                        (SELECT count(*) FROM employees) AS employees,
                        (SELECT count(*) FROM employee_assignments WHERE "primary" = true)
                            AS primary_assignments,
                        (
                            SELECT count(*)
                            FROM user_role_assignments AS assignment
                            JOIN roles AS role ON role.id = assignment.role_id
                            JOIN access_scopes AS scope ON scope.id = assignment.scope_id
                            JOIN user_accounts AS account ON account.id = assignment.user_id
                            WHERE role.code = 'organization-viewer'
                              AND scope.scope_type = 'organization'
                              AND account.username IN ('director', 'employee')
                        ) AS viewer_assignments,
                        (
                            SELECT count(*)
                            FROM user_accounts AS account
                            JOIN employees AS employee ON employee.id = account.employee_id
                            JOIN employee_assignments AS assignment
                              ON assignment.employee_id = employee.id
                            WHERE account.username IN ('director', 'employee')
                              AND employee.organization_id = (
                                  SELECT id FROM organizations WHERE code = 'SPK-ERTIS'
                              )
                              AND employee.created_by IS NOT NULL
                              AND assignment.status = 'active'
                              AND assignment.effective_from <= CURRENT_DATE
                              AND (
                                  assignment.effective_to IS NULL
                                  OR assignment.effective_to >= CURRENT_DATE
                              )
                        ) AS linked_current_personas
                    """
                )
            )
        ).one()
    assert dict(seed_counts._mapping) == {
        "organizations": 1,
        "published_versions": 1,
        "organization_units": 15,
        "system_roles": 8,
        "role_assignments": 9,
        "employees": 2,
        "primary_assignments": 2,
        "viewer_assignments": 2,
        "linked_current_personas": 2,
    }

    from app.core.config import Environment, Settings
    from app.main import create_app

    settings = Settings(
        environment=Environment.TEST,
        database_url=seeded_database.url.render_as_string(hide_password=False),
        dev_auth_enabled=False,
        oidc_issuer=None,
        oidc_audience=None,
        oidc_jwks_url=None,
    )
    application = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://integration.test",
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ready"}
