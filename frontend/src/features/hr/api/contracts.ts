import type { CreateLeaveRequestInput, HrEmployee, HrOverview, LeaveRequest } from '../model/types';

export interface HrRepository {
  getOverview(): Promise<HrOverview>;
  listEmployees(): Promise<HrEmployee[]>;
  getEmployee(id: string): Promise<HrEmployee>;
  getCurrentEmployee(): Promise<HrEmployee>;
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
