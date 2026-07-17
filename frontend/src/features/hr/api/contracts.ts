import type {
  CoreEmployeeRecord,
  CreateLeaveRequestInput,
  EmployeeAbsence,
  EmployeeAbsences,
  EmployeeFunctionDescriptor,
  HrEmployee,
  HrOverview,
  InitiateTerminationInput,
  LeaveRequest,
  StaffingSlotOption,
  TerminationCase,
  TerminationReason
} from '../model/types';

export interface HrRepository {
  getOverview(): Promise<HrOverview>;
  listEmployees(): Promise<HrEmployee[]>;
  getEmployee(id: string): Promise<HrEmployee>;
  getCurrentEmployee(): Promise<HrEmployee>;
  listCollectionFunctions(): Promise<EmployeeFunctionDescriptor[]>;
  listEmployeeFunctions(employeeId: string): Promise<EmployeeFunctionDescriptor[]>;
  invokeEmployeeFunction(employeeId: string, key: string, payload: Record<string, unknown>): Promise<unknown>;
  invokeCollectionFunction(key: string, payload: Record<string, unknown>): Promise<unknown>;
  getCoreEmployee(employeeId: string): Promise<CoreEmployeeRecord>;
  listVacantSlots(): Promise<StaffingSlotOption[]>;
  listAbsences(employeeId: string): Promise<EmployeeAbsences>;
  listActiveAbsences(): Promise<EmployeeAbsence[]>;
  listTerminationReasons(unitId?: string | null): Promise<TerminationReason[]>;
  listTerminationCases(employeeId: string): Promise<TerminationCase[]>;
  initiateTermination(input: InitiateTerminationInput): Promise<TerminationCase>;
  decideTermination(caseId: string, decision: 'approve' | 'return' | 'reject', comment: string, revision: number): Promise<TerminationCase>;
  cancelTermination(caseId: string, revision: number, reason: string): Promise<TerminationCase>;
  listLeaveRequests(): Promise<LeaveRequest[]>;
  createLeaveRequest(input: CreateLeaveRequestInput): Promise<LeaveRequest>;
  reviewLeaveRequest(id: string, decision: 'approve' | 'reject'): Promise<LeaveRequest>;
  submitHiringRequest(values: Record<string, unknown>, attachments: Array<{ name: string; size: number; category: string }>): Promise<{ id: string; number: string; status: string; currentStep: string }>;
  reset(): Promise<void>;
}

export interface HrApiAdapter {
  get<T>(path: string): Promise<T>;
  post<T>(path: string, body: unknown): Promise<T>;
}
