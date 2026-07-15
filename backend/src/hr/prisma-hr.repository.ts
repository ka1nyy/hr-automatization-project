import { Injectable } from '@nestjs/common';
import { EmployeeStatus, LeaveRequestStatus, Prisma, StaffingStatus } from '@prisma/client';
import { RequestContext } from '../auth/auth.types';
import { errors } from '../common/domain-error';
import { PrismaService } from '../database/prisma.service';
import {
  CreateEmployeeCommand,
  CreateLeaveCommand,
  EmployeeListQuery,
  EmployeeRecord,
  HrOverviewRecord,
  HrRepository,
  LeaveListQuery,
  LeavePreparation,
  LeaveRecord,
  Paginated,
  ReviewLeaveCommand
} from './hr.repository';

const employeeInclude = {
  department: true,
  position: true,
  manager: { select: { fullName: true } },
  leaveBalances: { where: { leaveType: 'ANNUAL_PAID', year: new Date().getUTCFullYear() } }
} satisfies Prisma.EmployeeInclude;

type EmployeeWithRelations = Prisma.EmployeeGetPayload<{ include: typeof employeeInclude }>;
type LeaveWithRelations = Prisma.LeaveRequestGetPayload<{ include: { employee: { select: { fullName: true } }; substitute: { select: { fullName: true } } } }>;

const mapEmployee = (employee: EmployeeWithRelations): EmployeeRecord => ({
  id: employee.id,
  employeeNumber: employee.employeeNumber,
  status: employee.status,
  availability: employee.availability,
  fullName: employee.fullName,
  initials: employee.initials,
  workEmail: employee.workEmail,
  workPhone: employee.workPhone,
  departmentId: employee.departmentId,
  departmentName: employee.department.name,
  positionId: employee.positionId,
  positionName: employee.position.name,
  staffingPositionId: employee.staffingPositionId,
  managerId: employee.managerId,
  managerName: employee.manager?.fullName ?? null,
  locationId: employee.locationId,
  employmentType: employee.employmentType,
  startDate: employee.startDate,
  contractEndDate: employee.contractEndDate,
  probationEndDate: employee.probationEndDate,
  personnelFileCompleteness: employee.personnelFileCompleteness,
  salary: employee.salary?.toNumber() ?? null,
  currency: employee.currency,
  leaveBalance: employee.leaveBalances[0]?.available.toNumber() ?? 0,
  candidateGroups: employee.candidateGroups,
  skills: employee.skills,
  version: employee.version
});

const mapLeave = (leave: LeaveWithRelations): LeaveRecord => ({
  id: leave.id,
  employeeId: leave.employeeId,
  employeeName: leave.employee.fullName,
  leaveType: leave.leaveType,
  startDate: leave.startDate,
  endDate: leave.endDate,
  requestedDuration: leave.requestedDuration.toNumber(),
  substituteEmployeeId: leave.substituteEmployeeId,
  substituteName: leave.substitute?.fullName ?? null,
  comment: leave.comment,
  status: leave.status,
  documentId: leave.documentId,
  documentNumber: leave.documentNumber,
  workflowInstanceId: leave.workflowInstanceId,
  workflowStep: leave.workflowStep,
  createdAt: leave.createdAt,
  version: leave.version
});

@Injectable()
export class PrismaHrRepository implements HrRepository {
  constructor(private readonly prisma: PrismaService) {}

  async listEmployees(query: EmployeeListQuery): Promise<Paginated<EmployeeRecord>> {
    const where: Prisma.EmployeeWhereInput = {
      status: query.status,
      departmentId: query.departmentId,
      ...(query.search ? { OR: [
        { fullName: { contains: query.search, mode: 'insensitive' } },
        { employeeNumber: { contains: query.search, mode: 'insensitive' } },
        { workEmail: { contains: query.search, mode: 'insensitive' } }
      ] } : {})
    };
    const [items, total] = await this.prisma.$transaction([
      this.prisma.employee.findMany({ where, include: employeeInclude, skip: (query.page - 1) * query.pageSize, take: query.pageSize, orderBy: { [query.sortBy]: query.sortOrder } }),
      this.prisma.employee.count({ where })
    ]);
    return { items: items.map(mapEmployee), page: query.page, pageSize: query.pageSize, total };
  }

  async getEmployee(id: string) {
    const employee = await this.prisma.employee.findUnique({ where: { id }, include: employeeInclude });
    return employee ? mapEmployee(employee) : null;
  }

  async createEmployee(command: CreateEmployeeCommand, context: RequestContext) {
    return this.prisma.$transaction(async (transaction) => {
      const staffing = await transaction.staffingPosition.findUnique({ where: { id: command.staffingPositionId } });
      if (!staffing || staffing.status !== StaffingStatus.VACANT || staffing.departmentId !== command.departmentId || staffing.positionId !== command.positionId) {
        throw errors.conflict('STAFFING_POSITION_UNAVAILABLE', 'Staffing position is not available for this assignment');
      }
      const employee = await transaction.employee.create({
        data: {
          employeeNumber: command.employeeNumber,
          status: EmployeeStatus.ACTIVE,
          fullName: command.fullName,
          initials: command.initials,
          workEmail: command.workEmail,
          workPhone: command.workPhone,
          departmentId: command.departmentId,
          positionId: command.positionId,
          staffingPositionId: command.staffingPositionId,
          managerId: command.managerId,
          legalEntityId: command.legalEntityId,
          locationId: command.locationId,
          employmentType: command.employmentType,
          workScheduleId: command.workScheduleId,
          startDate: command.startDate,
          contractEndDate: command.contractEndDate,
          probationEndDate: command.probationEndDate,
          salary: command.salary,
          candidateGroups: command.candidateGroups,
          skills: command.skills,
          createdBy: context.userId,
          updatedBy: context.userId,
          leaveBalances: { create: { leaveType: 'ANNUAL_PAID', year: command.startDate.getUTCFullYear(), available: 28 } }
        },
        include: employeeInclude
      });
      await transaction.staffingPosition.update({ where: { id: command.staffingPositionId }, data: { status: StaffingStatus.OCCUPIED, version: { increment: 1 } } });
      await transaction.auditEvent.create({ data: { aggregateType: 'Employee', aggregateId: employee.id, action: 'EmployeeCreated', actorId: context.userId, actorRole: context.role, correlationId: context.correlationId, changes: { status: EmployeeStatus.ACTIVE } } });
      await transaction.outboxEvent.create({ data: { eventType: 'EmployeeCreated', aggregateType: 'Employee', aggregateId: employee.id, correlationId: context.correlationId, payload: { employeeId: employee.id, departmentId: employee.departmentId, staffingPositionId: employee.staffingPositionId } } });
      return mapEmployee(employee);
    });
  }

  async getOverview(): Promise<HrOverviewRecord> {
    const now = new Date();
    const ninetyDays = new Date(now);
    ninetyDays.setUTCDate(ninetyDays.getUTCDate() + 90);
    const [totalEmployees, activeEmployees, onProbation, onLeave, onSickLeave, incompleteFiles, expiringContracts] = await this.prisma.$transaction([
      this.prisma.employee.count(),
      this.prisma.employee.count({ where: { status: EmployeeStatus.ACTIVE } }),
      this.prisma.employee.count({ where: { status: EmployeeStatus.ACTIVE, probationEndDate: { gte: now } } }),
      this.prisma.employee.count({ where: { status: { in: [EmployeeStatus.ON_LEAVE, EmployeeStatus.LONG_TERM_LEAVE] } } }),
      this.prisma.employee.count({ where: { status: EmployeeStatus.SICK_LEAVE } }),
      this.prisma.employee.count({ where: { personnelFileCompleteness: { lt: 90 } } }),
      this.prisma.employee.count({ where: { contractEndDate: { gte: now, lte: ninetyDays } } })
    ]);
    return { totalEmployees, activeEmployees, onProbation, onLeave, onSickLeave, incompleteFiles, expiringContracts };
  }

  async listLeaveRequests(query: LeaveListQuery): Promise<Paginated<LeaveRecord>> {
    const where: Prisma.LeaveRequestWhereInput = {
      employeeId: query.employeeId,
      status: query.status,
      employee: query.managerId ? { managerId: query.managerId } : undefined
    };
    const include = { employee: { select: { fullName: true } }, substitute: { select: { fullName: true } } } as const;
    const [items, total] = await this.prisma.$transaction([
      this.prisma.leaveRequest.findMany({ where, include, orderBy: { createdAt: 'desc' }, skip: (query.page - 1) * query.pageSize, take: query.pageSize }),
      this.prisma.leaveRequest.count({ where })
    ]);
    return { items: items.map(mapLeave), page: query.page, pageSize: query.pageSize, total };
  }

  async getLeaveRequest(id: string) {
    const leave = await this.prisma.leaveRequest.findUnique({ where: { id }, include: { employee: { select: { fullName: true } }, substitute: { select: { fullName: true } } } });
    return leave ? mapLeave(leave) : null;
  }

  async getLeaveByIdempotencyKey(key: string) {
    const leave = await this.prisma.leaveRequest.findUnique({ where: { idempotencyKey: key }, include: { employee: { select: { fullName: true } }, substitute: { select: { fullName: true } } } });
    return leave ? mapLeave(leave) : null;
  }

  async prepareLeave(employeeId: string, substituteEmployeeId: string | undefined, leaveType: string, startDate: Date, endDate: Date): Promise<LeavePreparation> {
    const year = startDate.getUTCFullYear();
    const [employee, substitute, balance, overlap] = await Promise.all([
      this.prisma.employee.findUnique({ where: { id: employeeId }, select: { id: true, status: true, managerId: true } }),
      substituteEmployeeId ? this.prisma.employee.findUnique({ where: { id: substituteEmployeeId }, select: { id: true } }) : Promise.resolve(null),
      this.prisma.leaveBalance.findUnique({ where: { employeeId_leaveType_year: { employeeId, leaveType, year } }, select: { available: true } }),
      this.prisma.leaveRequest.findFirst({ where: { employeeId, status: { in: [LeaveRequestStatus.SUBMITTED, LeaveRequestStatus.MANAGER_REVIEW, LeaveRequestStatus.HR_REVIEW, LeaveRequestStatus.APPROVED, LeaveRequestStatus.IN_PROGRESS] }, startDate: { lte: endDate }, endDate: { gte: startDate } }, select: { id: true } })
    ]);
    if (!employee) throw errors.notFound('employee');
    return { employee, substituteExists: !substituteEmployeeId || Boolean(substitute), availableBalance: balance?.available.toNumber() ?? 0, overlap: Boolean(overlap) };
  }

  async createLeave(command: CreateLeaveCommand, context: RequestContext) {
    return this.prisma.$transaction(async (transaction) => {
      const leave = await transaction.leaveRequest.create({
        data: {
          employeeId: command.employeeId,
          leaveType: command.leaveType,
          startDate: command.startDate,
          endDate: command.endDate,
          requestedDuration: command.requestedDuration,
          substituteEmployeeId: command.substituteEmployeeId,
          comment: command.comment,
          contactDuringLeave: command.contactDuringLeave,
          balanceSnapshot: (await transaction.leaveBalance.findUniqueOrThrow({ where: { employeeId_leaveType_year: { employeeId: command.employeeId, leaveType: command.leaveType, year: command.startDate.getUTCFullYear() } } })).available,
          status: LeaveRequestStatus.MANAGER_REVIEW,
          documentId: command.document.documentId,
          documentNumber: command.document.documentNumber,
          workflowInstanceId: command.workflow.workflowInstanceId,
          workflowStep: command.workflow.workflowStep,
          auditCorrelationId: context.correlationId,
          idempotencyKey: command.idempotencyKey,
          createdBy: context.userId,
          updatedBy: context.userId
        },
        include: { employee: { select: { fullName: true } }, substitute: { select: { fullName: true } } }
      });
      await transaction.auditEvent.create({ data: { aggregateType: 'LeaveRequest', aggregateId: leave.id, action: 'LeaveRequestSubmitted', actorId: context.userId, actorRole: context.role, correlationId: context.correlationId, workflowInstanceId: leave.workflowInstanceId, changes: { status: leave.status, requestedDuration: command.requestedDuration } } });
      await transaction.outboxEvent.create({ data: { eventType: 'LeaveRequestSubmitted', aggregateType: 'LeaveRequest', aggregateId: leave.id, correlationId: context.correlationId, payload: { leaveRequestId: leave.id, employeeId: leave.employeeId, workflowInstanceId: leave.workflowInstanceId, documentId: leave.documentId } } });
      return mapLeave(leave);
    });
  }

  async reviewLeave(command: ReviewLeaveCommand, context: RequestContext) {
    return this.prisma.$transaction(async (transaction) => {
      const current = await transaction.leaveRequest.findUnique({ where: { id: command.id } });
      if (!current) throw errors.notFound('leave_request');
      if (current.status !== command.expectedStatus || current.version !== command.expectedVersion) {
        throw errors.conflict('LEAVE_REQUEST_VERSION_CONFLICT', 'Leave request changed before this decision', { currentStatus: current.status, currentVersion: current.version });
      }

      if (command.deductBalance) {
        const balance = await transaction.leaveBalance.findUnique({ where: { employeeId_leaveType_year: { employeeId: current.employeeId, leaveType: current.leaveType, year: current.startDate.getUTCFullYear() } } });
        if (!balance || balance.available.lessThan(current.requestedDuration)) throw errors.conflict('LEAVE_BALANCE_EXCEEDED', 'Available leave balance is insufficient');
        const balanceUpdate = await transaction.leaveBalance.updateMany({
          where: { id: balance.id, version: balance.version },
          data: { available: { decrement: current.requestedDuration }, used: { increment: current.requestedDuration }, version: { increment: 1 } }
        });
        if (balanceUpdate.count !== 1) throw errors.conflict('LEAVE_BALANCE_VERSION_CONFLICT', 'Leave balance changed before approval');
      }

      const updated = await transaction.leaveRequest.updateMany({ where: { id: current.id, version: current.version, status: current.status }, data: { status: command.nextStatus, workflowStep: command.nextStatus, updatedBy: context.userId, version: { increment: 1 } } });
      if (updated.count !== 1) throw errors.conflict('LEAVE_REQUEST_VERSION_CONFLICT', 'Leave request changed before this decision');
      await transaction.auditEvent.create({ data: { aggregateType: 'LeaveRequest', aggregateId: current.id, action: command.eventType, actorId: context.userId, actorRole: context.role, correlationId: context.correlationId, workflowInstanceId: current.workflowInstanceId, reason: command.reason, changes: { from: current.status, to: command.nextStatus } } });
      await transaction.outboxEvent.create({ data: { eventType: command.eventType, aggregateType: 'LeaveRequest', aggregateId: current.id, correlationId: context.correlationId, payload: { leaveRequestId: current.id, employeeId: current.employeeId, status: command.nextStatus, workflowInstanceId: current.workflowInstanceId } } });
      return mapLeave(await transaction.leaveRequest.findUniqueOrThrow({ where: { id: current.id }, include: { employee: { select: { fullName: true } }, substitute: { select: { fullName: true } } } }));
    });
  }

  async recordSecurityAudit(aggregateType: string, aggregateId: string, action: string, context: RequestContext, reason: string) {
    await this.prisma.auditEvent.create({
      data: {
        aggregateType,
        aggregateId,
        action,
        actorId: context.userId,
        actorRole: context.role,
        correlationId: context.correlationId,
        reason
      }
    });
  }
}
