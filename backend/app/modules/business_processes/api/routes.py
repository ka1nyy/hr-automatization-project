"""Thin HTTP routes for integrated operational and HR workflow use cases."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import ResourceNotFoundError
from app.core.security.dependencies import get_current_principal
from app.core.security.identity import Principal
from app.shared.api import DataResponse

from ..application.service import BusinessProcessService, EmployeeRow
from ..infrastructure.models import (
    CorrespondenceModel,
    LeaveRequestModel,
    ProcessDefinitionModel,
    WorkTaskModel,
)
from .schemas import (
    AuditEntryDto,
    CorrespondenceDto,
    CreateLeaveRequest,
    DashboardDto,
    DirectoryEmployeeDto,
    HiringRequestDto,
    HiringSubmission,
    HrEmployeeDto,
    HrOverviewDto,
    IncomingLetterRequest,
    LeaveRequestDto,
    ProcessDefinitionDto,
    ReviewRequest,
    WorkTaskDto,
)

router = APIRouter(tags=["business-processes"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def _service(session: AsyncSession, principal: Principal) -> BusinessProcessService:
    return BusinessProcessService(session, principal)


def _audit(items: list[dict[str, object]]) -> list[AuditEntryDto]:
    return [AuditEntryDto.model_validate(item) for item in items]


def _correspondence(item: CorrespondenceModel) -> CorrespondenceDto:
    return CorrespondenceDto(
        id=item.id,
        number=item.number,
        sender=item.sender,
        sender_number=item.sender_number,
        sender_date=item.sender_date,
        received_at=item.received_at,
        subject=item.subject,
        summary=item.summary,
        document_type=item.document_type,
        channel=item.channel,
        department=item.department,
        executive=item.executive,
        executor=item.executor,
        due_date=item.due_date,
        priority=item.priority,
        status=item.status,
        workflow_step=item.workflow_step,
        confidentiality=item.confidentiality,
        response_required=item.response_required,
        attachments=item.attachments,
        tags=item.tags,
        audit=_audit(item.audit_log),
    )


def _task(item: WorkTaskModel) -> WorkTaskDto:
    return WorkTaskDto.model_validate(item)


def _process(item: ProcessDefinitionModel) -> ProcessDefinitionDto:
    return ProcessDefinitionDto.model_validate(item)


def _leave(item: LeaveRequestModel) -> LeaveRequestDto:
    return LeaveRequestDto(
        id=item.id,
        employee_id=item.employee_id,
        employee_name=item.employee_name,
        leave_type=item.leave_type,
        start_date=item.start_date,
        end_date=item.end_date,
        days=item.days,
        comment=item.comment,
        substitute=item.substitute,
        status=item.status,
        document_number=item.document_number,
        workflow_step=item.workflow_step,
        created_at=item.created_at,
        audit=_audit(item.audit_log),
    )


async def _hr_employee_dto(
    session: AsyncSession,
    row: EmployeeRow,
) -> HrEmployeeDto:
    employee, person, assignment, slot, position, unit = row
    today = date.today()
    on_leave = (
        await session.execute(
            select(LeaveRequestModel.id)
            .where(
                LeaveRequestModel.employee_id == employee.id,
                LeaveRequestModel.status == "approved",
                LeaveRequestModel.start_date <= today,
                LeaveRequestModel.end_date >= today,
            )
            .limit(1)
        )
    ).scalar_one_or_none() is not None
    used = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(LeaveRequestModel.days), 0)).where(
                    LeaveRequestModel.employee_id == employee.id,
                    LeaveRequestModel.status == "approved",
                    func.extract("year", LeaveRequestModel.start_date) == today.year,
                )
            )
        ).scalar_one()
        or 0
    )
    completeness_fields = [
        person.birth_date,
        person.personal_email,
        person.phone,
        employee.corporate_email,
        assignment,
        slot,
    ]
    completeness = round(
        sum(value is not None for value in completeness_fields) / len(completeness_fields) * 100
    )
    probation_end = employee.hire_date + timedelta(days=90)
    status_name = "on_leave" if on_leave else ("probation" if today <= probation_end else "active")
    custom_fields = slot.custom_fields if slot is not None else {}
    position_fields = position.custom_fields if position is not None else {}
    return HrEmployeeDto(
        id=employee.id,
        employee_number=employee.employee_number,
        full_name=person.display_name,
        initials="".join(part[0] for part in person.display_name.split()[:2]).upper(),
        position=position.name if position is not None else "Position not assigned",
        department=unit.name if unit is not None else "Department not assigned",
        manager=None,
        work_email=employee.corporate_email or "",
        phone=person.phone or "",
        start_date=employee.hire_date,
        location=str(custom_fields.get("location", "Pavlodar - Main office")),
        status=status_name,
        availability="away" if on_leave else "available",
        employment_type=slot.employment_type if slot is not None else "not_assigned",
        contract_end=assignment.effective_to if assignment is not None else None,
        probation_end=probation_end if today <= probation_end else None,
        leave_balance=max(0, 24 - used),
        personnel_file_completeness=completeness,
        salary=int(custom_fields.get("salary", 0)),
        skills=[str(value) for value in position_fields.get("skills", [])],
    )


@router.get(
    "/operations/correspondence/incoming", response_model=DataResponse[list[CorrespondenceDto]]
)
async def list_correspondence(
    session: Session, principal: CurrentPrincipal
) -> DataResponse[list[CorrespondenceDto]]:
    items = await _service(session, principal).list_correspondence()
    return DataResponse(data=[_correspondence(item) for item in items])


@router.get(
    "/operations/correspondence/incoming/duplicate",
    response_model=DataResponse[CorrespondenceDto | None],
)
async def find_duplicate(
    sender: str,
    sender_number: Annotated[str, Query(alias="senderNumber")],
    session: Session,
    principal: CurrentPrincipal,
) -> DataResponse[CorrespondenceDto | None]:
    item = await _service(session, principal).find_duplicate(sender, sender_number)
    return DataResponse(data=_correspondence(item) if item is not None else None)


@router.get(
    "/operations/correspondence/incoming/{item_id}", response_model=DataResponse[CorrespondenceDto]
)
async def get_correspondence(
    item_id: UUID, session: Session, principal: CurrentPrincipal
) -> DataResponse[CorrespondenceDto]:
    return DataResponse(
        data=_correspondence(await _service(session, principal).get_correspondence(item_id))
    )


@router.post(
    "/operations/correspondence/incoming",
    response_model=DataResponse[CorrespondenceDto],
    status_code=status.HTTP_201_CREATED,
)
async def register_correspondence(
    body: IncomingLetterRequest, session: Session, principal: CurrentPrincipal
) -> DataResponse[CorrespondenceDto]:
    return DataResponse(
        data=_correspondence(await _service(session, principal).register_correspondence(body))
    )


@router.post(
    "/operations/correspondence/incoming/{item_id}/resolution",
    response_model=DataResponse[CorrespondenceDto],
)
async def send_for_resolution(
    item_id: UUID, session: Session, principal: CurrentPrincipal
) -> DataResponse[CorrespondenceDto]:
    return DataResponse(
        data=_correspondence(await _service(session, principal).send_for_resolution(item_id))
    )


@router.get("/operations/tasks", response_model=DataResponse[list[WorkTaskDto]])
async def list_tasks(
    session: Session, principal: CurrentPrincipal
) -> DataResponse[list[WorkTaskDto]]:
    return DataResponse(
        data=[_task(item) for item in await _service(session, principal).list_tasks()]
    )


@router.post("/operations/tasks/{task_id}/{action}", response_model=DataResponse[WorkTaskDto])
async def change_task(
    task_id: UUID, action: str, session: Session, principal: CurrentPrincipal
) -> DataResponse[WorkTaskDto]:
    return DataResponse(data=_task(await _service(session, principal).change_task(task_id, action)))


@router.get("/operations/processes", response_model=DataResponse[list[ProcessDefinitionDto]])
async def list_processes(
    session: Session, principal: CurrentPrincipal
) -> DataResponse[list[ProcessDefinitionDto]]:
    return DataResponse(
        data=[_process(item) for item in await _service(session, principal).list_processes()]
    )


@router.post(
    "/operations/processes/{process_id}/retry", response_model=DataResponse[ProcessDefinitionDto]
)
async def retry_process(
    process_id: str, session: Session, principal: CurrentPrincipal
) -> DataResponse[ProcessDefinitionDto]:
    return DataResponse(data=_process(await _service(session, principal).retry_process(process_id)))


@router.get("/operations/dashboard", response_model=DataResponse[DashboardDto])
async def dashboard(session: Session, principal: CurrentPrincipal) -> DataResponse[DashboardDto]:
    return DataResponse(data=DashboardDto(**await _service(session, principal).dashboard()))


@router.get("/hr/leave-requests", response_model=DataResponse[list[LeaveRequestDto]])
async def list_leaves(
    session: Session, principal: CurrentPrincipal
) -> DataResponse[list[LeaveRequestDto]]:
    return DataResponse(
        data=[_leave(item) for item in await _service(session, principal).list_leaves()]
    )


@router.post(
    "/hr/leave-requests",
    response_model=DataResponse[LeaveRequestDto],
    status_code=status.HTTP_201_CREATED,
)
async def create_leave(
    body: CreateLeaveRequest, session: Session, principal: CurrentPrincipal
) -> DataResponse[LeaveRequestDto]:
    item = await _service(session, principal).create_leave(**body.model_dump())
    return DataResponse(data=_leave(item))


@router.post("/hr/leave-requests/{item_id}/review", response_model=DataResponse[LeaveRequestDto])
async def review_leave(
    item_id: UUID, body: ReviewRequest, session: Session, principal: CurrentPrincipal
) -> DataResponse[LeaveRequestDto]:
    return DataResponse(
        data=_leave(
            await _service(session, principal).review_leave(item_id, body.decision, body.reason)
        )
    )


@router.get("/hr/employees", response_model=DataResponse[list[HrEmployeeDto]])
async def list_hr_employees(
    session: Session, principal: CurrentPrincipal
) -> DataResponse[list[HrEmployeeDto]]:
    rows = await _service(session, principal).employee_rows()
    return DataResponse(data=[await _hr_employee_dto(session, row) for row in rows])


@router.get("/hr/employees/me", response_model=DataResponse[HrEmployeeDto])
async def get_current_hr_employee(
    session: Session, principal: CurrentPrincipal
) -> DataResponse[HrEmployeeDto]:
    rows = await _service(session, principal).employee_rows()
    row = next(
        (item for item in rows if item[0].id == principal.employee_id), rows[0] if rows else None
    )
    if row is None:
        raise ResourceNotFoundError("current_employee")
    return DataResponse(data=await _hr_employee_dto(session, row))


@router.get("/hr/employees/{employee_id}", response_model=DataResponse[HrEmployeeDto])
async def get_hr_employee(
    employee_id: UUID, session: Session, principal: CurrentPrincipal
) -> DataResponse[HrEmployeeDto]:
    rows = await _service(session, principal).employee_rows()
    row = next((item for item in rows if item[0].id == employee_id), None)
    if row is None:
        raise ResourceNotFoundError("employee", employee_id)
    return DataResponse(data=await _hr_employee_dto(session, row))


@router.get(
    "/operations/directory/employees", response_model=DataResponse[list[DirectoryEmployeeDto]]
)
async def list_directory(
    session: Session, principal: CurrentPrincipal
) -> DataResponse[list[DirectoryEmployeeDto]]:
    rows = await _service(session, principal).employee_rows()
    data = [
        DirectoryEmployeeDto(
            id=employee.id,
            name=person.display_name,
            initials="".join(part[0] for part in person.display_name.split()[:2]).upper(),
            role=position.name if position is not None else "Position not assigned",
            department=unit.name if unit is not None else "Department not assigned",
            candidate_groups=[],
            status="acting" if assignment is not None and assignment.acting else "active",
        )
        for employee, person, assignment, _slot, position, unit in rows
    ]
    return DataResponse(data=data)


@router.get("/hr/overview", response_model=DataResponse[HrOverviewDto])
async def hr_overview(session: Session, principal: CurrentPrincipal) -> DataResponse[HrOverviewDto]:
    service = _service(session, principal)
    employees = [await _hr_employee_dto(session, row) for row in await service.employee_rows()]
    leaves = await service.list_leaves()
    tasks = await service.list_tasks()
    return DataResponse(
        data=HrOverviewDto(
            total_employees=len(employees),
            active_employees=sum(item.status in {"active", "probation"} for item in employees),
            on_probation=sum(item.status == "probation" for item in employees),
            on_leave=sum(item.status == "on_leave" for item in employees),
            on_sick_leave=sum(item.status == "sick_leave" for item in employees),
            on_business_trip=0,
            onboarding_cases=0,
            overdue_tasks=sum(item.state == "overdue" for item in tasks),
            incomplete_files=sum(item.personnel_file_completeness < 90 for item in employees),
            expiring_contracts=sum(
                item.contract_end is not None
                and item.contract_end <= date.today() + timedelta(days=90)
                for item in employees
            ),
            active_processes=sum(
                item.status in {"pending_manager", "hr_review"} for item in leaves
            ),
        )
    )


@router.post(
    "/hr/hiring/requests",
    response_model=DataResponse[HiringRequestDto],
    status_code=status.HTTP_201_CREATED,
)
async def submit_hiring(
    body: HiringSubmission, session: Session, principal: CurrentPrincipal
) -> DataResponse[HiringRequestDto]:
    item = await _service(session, principal).create_hiring_request(body.values, body.attachments)
    return DataResponse(data=HiringRequestDto.model_validate(item))
