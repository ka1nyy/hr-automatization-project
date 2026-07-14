import type { CreateLeaveRequestInput, HrEmployee, HrOverview, LeaveRequest } from '../model/types';

export interface HrRepository {
  getOverview(): Promise<HrOverview>;
  listEmployees(): Promise<HrEmployee[]>;
  getEmployee(id: string): Promise<HrEmployee>;
  listLeaveRequests(): Promise<LeaveRequest[]>;
  createLeaveRequest(input: CreateLeaveRequestInput): Promise<LeaveRequest>;
  reviewLeaveRequest(id: string, decision: 'approve' | 'reject'): Promise<LeaveRequest>;
  reset(): Promise<void>;
}

export interface HrApiAdapter {
  get<T>(path: string): Promise<T>;
  post<T>(path: string, body: unknown): Promise<T>;
}
