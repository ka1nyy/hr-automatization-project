from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

RecruitmentView = Mapping[str, object]


class RecruitmentOperationsPort(Protocol):
    async def require_organization(
        self, resource: str, resource_id: UUID, organization_id: UUID
    ) -> None: ...
    async def list_resources(
        self,
        resource: str,
        organization_id: UUID,
        offset: int,
        limit: int,
        unit_id: UUID | None = None,
    ) -> tuple[Sequence[RecruitmentView], int]: ...
    async def list_my_interviews(
        self, organization_id: UUID, user_id: UUID, offset: int, limit: int
    ) -> tuple[Sequence[RecruitmentView], int]: ...
    async def create_request(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def correct_request(
        self, request_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def review_request(
        self,
        request_id: UUID,
        actor_id: UUID,
        revision: int,
        decision: str,
        comment: str,
        staffing: Mapping[str, object] | None = None,
    ) -> RecruitmentView: ...
    async def create_vacancy(
        self, request_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def publish_vacancy(
        self, vacancy_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def create_candidate(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def anonymize_candidate(
        self, candidate_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> RecruitmentView: ...
    async def create_publication_channel(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def create_commission(
        self, organization_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def create_application(
        self, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def screen(
        self, application_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def schedule_interview(
        self, application_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def evaluate_interview(
        self, interview_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def record_commission_decision(
        self, application_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def create_offer(
        self, application_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def respond_offer(
        self, offer_id: UUID, actor_id: UUID, revision: int, accepted: bool, reason: str | None
    ) -> RecruitmentView: ...
    async def start_hiring(
        self, application_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def complete_hiring(
        self, case_id: UUID, actor_id: UUID, revision: int, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def cancel_hiring(
        self, case_id: UUID, actor_id: UUID, revision: int, reason: str
    ) -> RecruitmentView: ...
    async def create_onboarding_task(
        self, case_id: UUID, actor_id: UUID, data: Mapping[str, object]
    ) -> RecruitmentView: ...
    async def complete_onboarding_task(
        self, task_id: UUID, actor_id: UUID, revision: int, evidence: Mapping[str, object]
    ) -> RecruitmentView: ...
