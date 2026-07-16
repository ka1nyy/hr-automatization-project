from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

TerminationView = Mapping[str, object]


class TerminationOperationsPort(Protocol):
    async def list_cases(
        self,
        organization_id: UUID,
        offset: int,
        limit: int,
        employee_id: UUID | None = None,
        unit_id: UUID | None = None,
    ) -> tuple[Sequence[TerminationView], int]: ...
    async def get_case(
        self,
        case_id: UUID,
        organization_id: UUID,
        employee_id: UUID | None = None,
        unit_id: UUID | None = None,
    ) -> TerminationView: ...
    async def initiate(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> TerminationView: ...
    async def decide(
        self, case_id: UUID, actor_id: UUID, revision: int, stage: str, decision: str, comment: str
    ) -> TerminationView: ...
    async def resubmit(
        self, case_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> TerminationView: ...
    async def register_order(
        self, case_id: UUID, actor_id: UUID, revision: int, document_id: UUID
    ) -> TerminationView: ...
    async def create_tasks(
        self, case_id: UUID, actor_id: UUID, tasks: Sequence[Mapping[str, object]]
    ) -> Sequence[TerminationView]: ...
    async def complete_task(
        self, task_id: UUID, actor_id: UUID, revision: int, evidence: Mapping[str, object]
    ) -> TerminationView: ...
    async def waive_task(
        self, task_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> TerminationView: ...
    async def schedule(
        self,
        case_id: UUID,
        actor_id: UUID,
        revision: int,
        effective_date: object,
        secondary_plan: list[dict[str, object]],
    ) -> TerminationView: ...
    async def complete(self, case_id: UUID, actor_id: UUID, revision: int) -> TerminationView: ...
    async def cancel(
        self, case_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> TerminationView: ...
