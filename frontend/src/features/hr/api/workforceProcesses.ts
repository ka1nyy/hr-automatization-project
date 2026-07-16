import { ApiClient } from '../../../repositories/apiRepositories';
import type { PersonaId } from '../../../shared/types';
import { DEMO_ORGANIZATION_ID } from './hiringRequests';

export type ProcessKind = 'leave' | 'trip' | 'termination';
export type ProcessDecision = 'approve' | 'return' | 'reject';

export type LeaveType = { id: string; code: string; name: string; paid: boolean; requires_balance: boolean };
export type LeaveProcess = {
  id: string; employee_id: string; unit_id: string; leave_type_id: string;
  start_date: string; end_date: string; requested_days: number; reason?: string;
  status: string; returned_from_stage?: string; revision: number; submitted_at: string;
};
export type TripProcess = {
  id: string; employee_id: string; unit_id: string; destination: string;
  start_date: string; end_date: string; purpose: string; estimated_cost: number; currency: string;
  funding_details: Record<string, unknown>; status: string; returned_from_stage?: string;
  revision: number; submitted_at: string;
};
export type TerminationReason = { id: string; code: string; name: string; legalReviewRequired: boolean; employeeInitiated: boolean };
export type TerminationProcess = {
  id: string; employee_id: string; reason_id: string; requested_date: string; effective_date?: string;
  status: string; revision: number; created_at: string; order_document_id?: string;
};
export type WorkforceProcess = LeaveProcess | TripProcess | TerminationProcess;

const api = new ApiClient();

function currentPersona(): PersonaId {
  try {
    const stored = JSON.parse(localStorage.getItem('ertis-developer-settings') ?? '{}') as { state?: { persona?: PersonaId } };
    return stored.state?.persona ?? 'hr-specialist';
  } catch {
    return 'hr-specialist';
  }
}

function devUser() {
  const persona = currentPersona();
  if (persona === 'employee') return 'employee';
  if (['hr-specialist', 'hr-initiator', 'hr-director'].includes(persona)) return 'hr';
  return 'admin';
}

function scope() { return currentPersona() === 'employee' ? 'self' : 'all'; }
const orgQuery = `organizationId=${DEMO_ORGANIZATION_ID}`;

export const processStatusLabels: Record<string, string> = {
  manager_review: 'Решение руководителя', hr_review: 'Проверка HR', finance_review: 'Проверка финансов',
  hr_registration: 'Регистрация HR', legal_review: 'Юридическая проверка', signature: 'Подписание',
  registration: 'Регистрация приказа', offboarding: 'Офбординг', scheduled: 'Запланировано',
  effective: 'Вступило в силу', approved: 'Одобрено', registered: 'Зарегистрировано',
  returned: 'Возвращено', rejected: 'Отклонено', cancelled: 'Отменено', completed: 'Завершено'
};

export function canActOnProcess(persona: PersonaId, kind: ProcessKind, status: string) {
  if (kind === 'leave') {
    if (status === 'manager_review') return persona === 'executive' || persona === 'board-chairman';
    return status === 'hr_review' && ['hr-specialist', 'hr-initiator', 'hr-director'].includes(persona);
  }
  if (kind === 'trip') {
    if (status === 'manager_review') return persona === 'executive' || persona === 'board-chairman';
    if (status === 'finance_review') return persona === 'economic-director' || persona === 'accountant';
    return status === 'hr_registration' && ['hr-specialist', 'hr-initiator', 'hr-director'].includes(persona);
  }
  if (status === 'hr_review' || status === 'registration' || status === 'offboarding' || status === 'scheduled' || status === 'effective') {
    return ['hr-specialist', 'hr-initiator', 'hr-director'].includes(persona);
  }
  if (status === 'legal_review') return persona === 'legal-reviewer';
  if (status === 'signature') return persona === 'executive' || persona === 'board-chairman';
  return false;
}

export const workforceProcessesApi = {
  listLeaves: () => api.get<LeaveProcess[]>(`/absence/leave-requests?${orgQuery}&scope=${scope()}&pageSize=100`, devUser()),
  listTrips: () => api.get<TripProcess[]>(`/absence/business-trips?${orgQuery}&scope=${scope()}&pageSize=100`, devUser()),
  listTerminations: () => api.get<TerminationProcess[]>(`/terminations?${orgQuery}&scope=${scope()}&pageSize=100`, devUser()),
  listLeaveTypes: () => api.get<LeaveType[]>(`/absence/leave-types?${orgQuery}`, devUser()),
  listTerminationReasons: () => api.get<TerminationReason[]>(`/terminations/reasons?${orgQuery}`, devUser()),
  currentEmployee: () => api.get<{ id: string; displayName: string }>('/employees/me', 'employee'),

  createLeave: (input: { employeeId: string; leaveTypeId: string; startDate: string; endDate: string; reason: string }) =>
    api.post<LeaveProcess>('/absence/leave-requests', { organizationId: DEMO_ORGANIZATION_ID, ...input }, 'employee'),
  decideLeave: (item: LeaveProcess, decision: ProcessDecision, comment: string) => {
    const action = item.status === 'manager_review' ? 'manager-review' : 'hr-review';
    return api.post<LeaveProcess>(`/absence/leave-requests/${item.id}/${action}`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, decision, comment }, devUser());
  },
  cancelLeave: (item: LeaveProcess, reason: string) => api.post<LeaveProcess>(`/absence/leave-requests/${item.id}/cancel`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, reason }, 'employee'),

  createTrip: (input: { employeeId: string; destination: string; startDate: string; endDate: string; purpose: string; estimatedCost: number; currency: string }) =>
    api.post<TripProcess>('/absence/business-trips', { organizationId: DEMO_ORGANIZATION_ID, fundingDetails: {}, ...input }, 'employee'),
  decideTrip: (item: TripProcess, decision: ProcessDecision, comment: string) => {
    const action = { manager_review: 'manager-review', finance_review: 'finance-review', hr_registration: 'register' }[item.status];
    if (!action) throw new Error('Для текущего этапа действие недоступно.');
    return api.post<TripProcess>(`/absence/business-trips/${item.id}/${action}`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, decision, comment }, devUser());
  },
  cancelTrip: (item: TripProcess, reason: string) => api.post<TripProcess>(`/absence/business-trips/${item.id}/cancel`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, reason }, 'employee'),

  createTermination: (input: { employeeId: string; unitId: string; reasonId: string; requestedDate: string; legalBasis: string }) =>
    api.post<TerminationProcess>('/terminations', { organizationId: DEMO_ORGANIZATION_ID, ...input }, 'admin'),
  decideTermination: (item: TerminationProcess, decision: ProcessDecision, comment: string) => {
    const action = { hr_review: 'hr-review', legal_review: 'legal-review', signature: 'sign' }[item.status];
    if (!action) throw new Error('Для текущего этапа действие недоступно.');
    return api.post<TerminationProcess>(`/terminations/${item.id}/${action}`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, decision, comment }, devUser());
  },
  registerTerminationOrder: (item: TerminationProcess, documentId: string) => api.post<TerminationProcess>(`/terminations/${item.id}/register-order`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, documentId }, 'hr'),
  scheduleTermination: (item: TerminationProcess, effectiveDate: string) => api.post<TerminationProcess>(`/terminations/${item.id}/schedule`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, effectiveDate, secondaryAssignments: [] }, 'hr'),
  completeTermination: (item: TerminationProcess) => api.post<TerminationProcess>(`/terminations/${item.id}/complete`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision }, 'hr')
};

export async function listWorkforceProcesses(kind: ProcessKind): Promise<WorkforceProcess[]> {
  if (kind === 'leave') return workforceProcessesApi.listLeaves();
  if (kind === 'trip') return workforceProcessesApi.listTrips();
  return workforceProcessesApi.listTerminations();
}
