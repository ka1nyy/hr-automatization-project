import { ApiClient } from '../../../repositories/apiRepositories';
import type { CreateLeaveRequestInput, HrEmployee, HrOverview, LeaveRequest } from '../model/types';
import type { HrRepository } from './contracts';

export class ApiHrRepository implements HrRepository {
  constructor(private readonly api = new ApiClient()) {}

  getOverview() { return this.api.get<HrOverview>('/hr/overview'); }
  listEmployees() { return this.api.get<HrEmployee[]>('/hr/employees'); }
  getEmployee(id: string) { return this.api.get<HrEmployee>(`/hr/employees/${id}`); }
  getCurrentEmployee() { return this.api.get<HrEmployee>('/hr/employees/me'); }
  listLeaveRequests() { return this.api.get<LeaveRequest[]>('/hr/leave-requests'); }
  createLeaveRequest(input: CreateLeaveRequestInput) { return this.api.post<LeaveRequest>('/hr/leave-requests', input); }
  reviewLeaveRequest(id: string, decision: 'approve' | 'reject') {
    return this.api.post<LeaveRequest>(`/hr/leave-requests/${id}/review`, { decision, reason: decision === 'reject' ? 'Returned for correction by the reviewer' : '' });
  }
  submitHiringRequest(values: Record<string, unknown>, attachments: Array<{ name: string; size: number; category: string }>) {
    return this.api.post<{ id: string; number: string; status: string; currentStep: string }>('/hr/hiring/requests', { values, attachments });
  }
  async reset() { /* Server records and audit history are intentionally immutable. */ }
}
