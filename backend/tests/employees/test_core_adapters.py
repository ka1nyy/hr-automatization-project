"""Runtime adapter coverage for employee outbox events."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.employees.application.ports import PendingEvent
from app.modules.employees.domain.entities import Person
from app.modules.employees.infrastructure.core_adapters import CoreOutboxSink
from app.modules.employees.infrastructure.repositories import SqlAlchemyPersonRepository
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.parametrize(
    "event_type",
    [
        "employeeAssignmentEndScheduled",
        "employeeAssignmentReviewRequested",
        "employeeAssignmentReviewRejected",
        "employeeHired",
        "employeeTerminated",
        "employeeTerminationScheduled",
        "employeeTransferred",
    ],
)
async def test_employee_outbox_adapter_accepts_workflow_events(event_type: str) -> None:
    session = MagicMock(spec=AsyncSession)
    sink = CoreOutboxSink(session)

    await sink.add(
        PendingEvent(
            event_type=event_type,
            aggregate_type="employeeAssignment",
            aggregate_id=uuid4(),
            payload={},
        )
    )

    model = session.add.call_args.args[0]
    assert model.event_name == event_type


async def test_person_repository_flushes_principal_before_employee_insert() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = SqlAlchemyPersonRepository(session)

    await repository.add(Person(first_name="Aigul", last_name="Sarsenova"))

    session.add.assert_called_once()
    session.flush.assert_awaited_once_with()
