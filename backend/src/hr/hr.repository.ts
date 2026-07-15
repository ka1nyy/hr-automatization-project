import { Availability, EmployeeStatus, LeaveRequestStatus } from '@prisma/client';
import { RequestContext } from '../auth/auth.types';
import { DocumentReference, WorkflowReference } from '../integrations/integration.ports';

export interface EmployeeRecord {
  id: string;
  employeeNumber: string;
  status: EmployeeStatus;
  availability: Availability;
  fullName: string;
  initials: string;
  workEmail: string;
  workPhone: string;
  departmentId: string;
  departmentName: string;
  positionId: string;
  positionName: string;
  staffingPositionId: string | null;
  managerId: string | null;
  managerName: string | null;
  locationId: string;
  employmentType: string;
  startDate: Date;
  contractEndDate: Date | null;
  probationEndDate: Date | null;
  personnelFileCompleteness: number;
  salary: number | null;
  currency: string;
  leaveBalance: number;
  candidateGroups: string[];
  skills: string[];
  version: number;
}

export interface LeaveRecord {
  id: string;
  employeeId: string;
  employeeName: string;
  leaveType: string;
  startDate: Date;
  endDate: Date;
  requestedDuration: number;
  substituteEmployeeId: string | null;
  substituteName: string | null;
  comment: string | null;
  status: LeaveRequestStatus;
  documentId: string | null;
  documentNumber: string | null;
  workflowInstanceId: string | null;
  workflowStep: string | null;
  createdAt: Date;
  version: number;
}

export interface Paginated<T> { items: T[]; page: number; pageSize: number; total: number; }

export interface EmployeeListQuery {
  page: number;
  pageSize: number;
  search?: string;
  status?: EmployeeStatus;
  departmentId?: string;
  sortBy: 'fullName' | 'employeeNumber' | 'startDate' | 'status';
  sortOrder: 'asc' | 'desc';
}

export interface LeaveListQuery {
  page: number;
  pageSize: number;
  employeeId?: string;
  managerId?: string;
  status?: LeaveRequestStatus;
}

export interface CreateEmployeeCommand {
  employeeNumber: string;
  fullName: string;
  initials: string;
  workEmail: string;
  workPhone: string;
  departmentId: string;
  positionId: string;
  staffingPositionId: string;
  managerId?: string;
  legalEntityId: string;
  locationId: string;
  employmentType: string;
  workScheduleId: string;
  startDate: Date;
  contractEndDate?: Date;
  probationEndDate?: Date;
  salary?: number;
  candidateGroups: string[];
  skills: string[];
}

export interface LeavePreparation {
  employee: { id: string; status: EmployeeStatus; managerId: string | null };
  substituteExists: boolean;
  availableBalance: number;
  overlap: boolean;
}

export interface CreateLeaveCommand {
  employeeId: string;
  leaveType: string;
  startDate: Date;
  endDate: Date;
  requestedDuration: number;
  substituteEmployeeId?: string;
  comment?: string;
  contactDuringLeave?: string;
  idempotencyKey: string;
  document: DocumentReference;
  workflow: WorkflowReference;
}

export interface ReviewLeaveCommand {
  id: string;
  expectedStatus: LeaveRequestStatus;
  nextStatus: LeaveRequestStatus;
  expectedVersion: number;
  reason?: string;
  eventType: string;
  deductBalance: boolean;
}

export interface HrOverviewRecord {
  totalEmployees: number;
  activeEmployees: number;
  onProbation: number;
  onLeave: number;
  onSickLeave: number;
  incompleteFiles: number;
  expiringContracts: number;
}

export interface HrRepository {
  listEmployees(query: EmployeeListQuery): Promise<Paginated<EmployeeRecord>>;
  getEmployee(id: string): Promise<EmployeeRecord | null>;
  createEmployee(command: CreateEmployeeCommand, context: RequestContext): Promise<EmployeeRecord>;
  getOverview(): Promise<HrOverviewRecord>;
  listLeaveRequests(query: LeaveListQuery): Promise<Paginated<LeaveRecord>>;
  getLeaveRequest(id: string): Promise<LeaveRecord | null>;
  getLeaveByIdempotencyKey(key: string): Promise<LeaveRecord | null>;
  prepareLeave(employeeId: string, substituteEmployeeId: string | undefined, leaveType: string, startDate: Date, endDate: Date): Promise<LeavePreparation>;
  createLeave(command: CreateLeaveCommand, context: RequestContext): Promise<LeaveRecord>;
  reviewLeave(command: ReviewLeaveCommand, context: RequestContext): Promise<LeaveRecord>;
  recordSecurityAudit(aggregateType: string, aggregateId: string, action: string, context: RequestContext, reason: string): Promise<void>;
}

export const HR_REPOSITORY = Symbol('HR_REPOSITORY');
