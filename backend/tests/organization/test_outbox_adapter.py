"""Organization events must pass the strict core event vocabulary."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.modules.organization.domain.ports import OutboxRecord
from app.modules.organization.infrastructure.repositories import SqlAlchemyOutboxRepository
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_scheduled_staffing_closure_is_accepted_by_runtime_outbox_adapter() -> None:
    session = MagicMock(spec=AsyncSession)
    repository = SqlAlchemyOutboxRepository(session)

    await repository.add(
        OutboxRecord(
            id=uuid4(),
            organization_id=uuid4(),
            event_type="staffingSlotClosureScheduled",
            aggregate_type="staffingSlot",
            aggregate_id=uuid4(),
            payload={},
            occurred_at=datetime.now(UTC),
        )
    )

    model = session.add.call_args.args[0]
    assert model.event_name == "staffingSlotClosureScheduled"
