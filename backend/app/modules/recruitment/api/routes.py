from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.core.database.session import async_session_factory
from app.core.errors import ResourceNotFoundError
from app.core.security.authorization import get_authorization_port
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.core.security.ports import AuthorizationPort
from app.modules.employees.infrastructure.crypto import FernetSensitiveDataProtector
from app.shared.api import DataResponse, ListResponse, PageMeta

from ..application.service import RecruitmentService
from ..infrastructure.operations import SqlAlchemyRecruitmentOperations
from .schemas import (
    ApplicationCreate,
    CancelBody,
    CandidateAnonymize,
    CandidateCreate,
    ChannelCreate,
    CommissionCreate,
    CommissionDecisionBody,
    EvaluationBody,
    HiringComplete,
    HiringStart,
    InterviewBody,
    OfferCreate,
    OfferResponse,
    OnboardingTaskComplete,
    OnboardingTaskCreate,
    PublishBody,
    RequestCorrection,
    RequestCreate,
    ReviewBody,
    ScreeningBody,
    StaffingReviewBody,
    VacancyCreate,
)

router = APIRouter(prefix="/recruitment", tags=["recruitment"])


def get_service(
    auth: Annotated[AuthorizationPort, Depends(get_authorization_port)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RecruitmentService:
    return RecruitmentService(
        SqlAlchemyRecruitmentOperations(
            async_session_factory,
            FernetSensitiveDataProtector(settings.require_sensitive_data_key()),
        ),
        auth,
    )


Service = Annotated[RecruitmentService, Depends(get_service)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.get("/interviews/my", response_model=ListResponse[dict[str, Any]])
async def my_interviews(
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: PrincipalDep,
    offset: int = 0,
    limit: int = Query(default=50, ge=1, le=200),
) -> ListResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.interview.evaluate", organization_id)
    rows, total = await service.operations.list_my_interviews(
        organization_id, principal.user_id, offset, limit
    )
    return ListResponse(
        data=[dict(item) for item in rows],
        meta=PageMeta(page=offset // limit + 1, page_size=limit, total=total),
    )


@router.post("/publication-channels", response_model=DataResponse[dict[str, Any]], status_code=201)
async def create_channel(
    body: ChannelCreate, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.vacancy.manage", body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.create_publication_channel(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post("/commissions", response_model=DataResponse[dict[str, Any]], status_code=201)
async def create_commission(
    body: CommissionCreate, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.commission.manage", body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.create_commission(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.get("/{resource}", response_model=ListResponse[dict[str, Any]])
async def list_resource(
    resource: str,
    organization_id: Annotated[UUID, Query(alias="organizationId")],
    service: Service,
    principal: PrincipalDep,
    offset: int = 0,
    limit: int = Query(default=50, ge=1, le=200),
    unit_id: Annotated[UUID | None, Query(alias="unitId")] = None,
) -> ListResponse[dict[str, Any]]:
    permission = {
        "requests": "recruitment.request.read",
        "vacancies": "recruitment.request.read",
        "candidates": "recruitment.candidate.read",
        "applications": "recruitment.candidate.read",
        "offers": "recruitment.offer.manage",
        "hiring-cases": "recruitment.hiring.manage",
    }.get(resource)
    if permission is None:
        raise ResourceNotFoundError("recruitment resource")
    await service.require(principal, permission, organization_id, unit_id)
    rows, total = await service.operations.list_resources(
        resource, organization_id, offset, limit, unit_id
    )
    return ListResponse(
        data=[dict(x) for x in rows],
        meta=PageMeta(page=offset // limit + 1, page_size=limit, total=total),
    )


@router.post("/requests", response_model=DataResponse[dict[str, Any]], status_code=201)
async def create_request(
    body: RequestCreate, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    return DataResponse(
        data=dict(
            await service.create_request(
                principal,
                body.organization_id,
                body.requesting_unit_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.patch("/requests/{item_id}", response_model=DataResponse[dict[str, Any]])
async def correct_request(
    item_id: UUID, body: RequestCorrection, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(
        principal, "recruitment.request.create", body.organization_id, body.requesting_unit_id
    )
    await service.operations.require_organization("request", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.correct_request(
                item_id,
                principal.user_id,
                body.revision,
                body.model_dump(by_alias=True, exclude={"organization_id", "revision"}),
            )
        )
    )


@router.post("/requests/{item_id}/hr-review", response_model=DataResponse[dict[str, Any]])
async def hr_review(
    item_id: UUID, body: ReviewBody, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.operations.require_organization("request", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.review_hr(
                principal, body.organization_id, item_id, body.revision, body.decision, body.comment
            )
        )
    )


@router.post("/requests/{item_id}/staffing-review", response_model=DataResponse[dict[str, Any]])
async def staffing_review(
    item_id: UUID, body: StaffingReviewBody, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.operations.require_organization("request", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.review_staffing(
                principal,
                body.organization_id,
                item_id,
                body.revision,
                body.decision,
                body.comment,
                body.model_dump(
                    by_alias=True, exclude={"organization_id", "revision", "decision", "comment"}
                ),
            )
        )
    )


@router.post(
    "/requests/{item_id}/vacancies", response_model=DataResponse[dict[str, Any]], status_code=201
)
async def vacancy(
    item_id: UUID, body: VacancyCreate, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.vacancy.manage", body.organization_id)
    await service.operations.require_organization("request", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.create_vacancy(
                item_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post("/vacancies/{item_id}/publish", response_model=DataResponse[dict[str, Any]])
async def publish(
    item_id: UUID, body: PublishBody, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.vacancy.publish", body.organization_id)
    await service.operations.require_organization("vacancy", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.publish_vacancy(
                item_id,
                principal.user_id,
                body.revision,
                body.model_dump(by_alias=True, exclude={"organization_id", "revision"}),
            )
        )
    )


@router.post("/candidates", response_model=DataResponse[dict[str, Any]], status_code=201)
async def candidate(
    body: CandidateCreate, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.candidate.manage", body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.create_candidate(
                body.organization_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post("/candidates/{item_id}/anonymize", response_model=DataResponse[dict[str, Any]])
async def anonymize_candidate(
    item_id: UUID, body: CandidateAnonymize, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.candidate.manage", body.organization_id)
    await service.operations.require_organization("candidate", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.anonymize_candidate(
                item_id, principal.user_id, body.revision, body.reason
            )
        )
    )


@router.post("/applications", response_model=DataResponse[dict[str, Any]], status_code=201)
async def application(
    body: ApplicationCreate, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.candidate.manage", body.organization_id)
    await service.operations.require_organization("vacancy", body.vacancy_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.create_application(
                principal.user_id, body.model_dump(by_alias=True, exclude={"organization_id"})
            )
        )
    )


@router.post("/applications/{item_id}/screen", response_model=DataResponse[dict[str, Any]])
async def screen(
    item_id: UUID, body: ScreeningBody, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.screen", body.organization_id)
    await service.operations.require_organization("application", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.screen(
                item_id,
                principal.user_id,
                body.revision,
                body.model_dump(by_alias=True, exclude={"organization_id", "revision"}),
            )
        )
    )


@router.post(
    "/applications/{item_id}/interviews",
    response_model=DataResponse[dict[str, Any]],
    status_code=201,
)
async def interview(
    item_id: UUID, body: InterviewBody, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.interview.manage", body.organization_id)
    await service.operations.require_organization("application", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.schedule_interview(
                item_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post(
    "/interviews/{item_id}/evaluations",
    response_model=DataResponse[dict[str, Any]],
    status_code=201,
)
async def evaluate(
    item_id: UUID, body: EvaluationBody, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.interview.evaluate", body.organization_id)
    await service.operations.require_organization("interview", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.evaluate_interview(
                item_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post(
    "/applications/{item_id}/commission-decision", response_model=DataResponse[dict[str, Any]]
)
async def commission(
    item_id: UUID, body: CommissionDecisionBody, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.commission.decide", body.organization_id)
    await service.operations.require_organization("application", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.record_commission_decision(
                item_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post(
    "/applications/{item_id}/offers", response_model=DataResponse[dict[str, Any]], status_code=201
)
async def offer(
    item_id: UUID, body: OfferCreate, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.offer.manage", body.organization_id)
    await service.operations.require_organization("application", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.create_offer(
                item_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post("/offers/{item_id}/response", response_model=DataResponse[dict[str, Any]])
async def offer_response(
    item_id: UUID, body: OfferResponse, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.operations.require_organization("offer", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.respond_offer(
                principal, body.organization_id, item_id, body.revision, body.accepted, body.reason
            )
        )
    )


@router.post(
    "/applications/{item_id}/hiring", response_model=DataResponse[dict[str, Any]], status_code=201
)
async def start_hiring(
    item_id: UUID, body: HiringStart, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.hiring.manage", body.organization_id)
    await service.operations.require_organization("application", item_id, body.organization_id)
    return DataResponse(
        data=dict(await service.operations.start_hiring(item_id, principal.user_id, {}))
    )


@router.post("/hiring-cases/{item_id}/complete", response_model=DataResponse[dict[str, Any]])
async def complete_hiring(
    item_id: UUID, body: HiringComplete, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.operations.require_organization("hiring", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.complete_hiring(
                principal,
                body.organization_id,
                item_id,
                body.revision,
                body.model_dump(by_alias=True, exclude={"organization_id", "revision"}),
            )
        )
    )


@router.post("/hiring-cases/{item_id}/cancel", response_model=DataResponse[dict[str, Any]])
async def cancel_hiring(
    item_id: UUID, body: CancelBody, service: Service, principal: PrincipalDep
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.hiring.manage", body.organization_id)
    await service.operations.require_organization("hiring", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.cancel_hiring(
                item_id, principal.user_id, body.revision, body.reason
            )
        )
    )


@router.post(
    "/hiring-cases/{item_id}/onboarding-tasks",
    response_model=DataResponse[dict[str, Any]],
    status_code=201,
)
async def create_onboarding_task(
    item_id: UUID,
    body: OnboardingTaskCreate,
    service: Service,
    principal: PrincipalDep,
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.hiring.manage", body.organization_id)
    await service.operations.require_organization("hiring", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.create_onboarding_task(
                item_id,
                principal.user_id,
                body.model_dump(by_alias=True, exclude={"organization_id"}),
            )
        )
    )


@router.post("/onboarding-tasks/{item_id}/complete", response_model=DataResponse[dict[str, Any]])
async def complete_onboarding_task(
    item_id: UUID,
    body: OnboardingTaskComplete,
    service: Service,
    principal: PrincipalDep,
) -> DataResponse[dict[str, Any]]:
    await service.require(principal, "recruitment.hiring.manage", body.organization_id)
    await service.operations.require_organization("onboarding", item_id, body.organization_id)
    return DataResponse(
        data=dict(
            await service.operations.complete_onboarding_task(
                item_id, principal.user_id, body.revision, body.evidence
            )
        )
    )
