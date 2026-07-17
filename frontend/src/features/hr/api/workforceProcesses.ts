import { ApiClient } from '../../../repositories/apiRepositories';
import type { PersonaId } from '../../../shared/types';
import { DEMO_ORGANIZATION_ID } from './hiringRequests';

export type ProcessKind = 'leave' | 'trip' | 'termination';
export type ProcessDecision = 'approve' | 'return' | 'reject';

export type LeaveType = { id: string; code: string; name: string; paid: boolean; requires_balance: boolean };
export type LeaveBalance = { id: string; employee_id: string; leave_type_id: string; year: number; entitlement_days: number; used_days: number; reserved_days: number; revision: number };
export type LeaveProcess = {
  id: string; employee_id: string; unit_id: string; leave_type_id: string;
  start_date: string; end_date: string; requested_days: number; reason?: string;
  status: string; returned_from_stage?: string; cancellation_reason?: string;
  revision: number; submitted_at: string; approved_at?: string; cancelled_at?: string;
};
export type TripProcess = {
  id: string; employee_id: string; unit_id: string; destination: string;
  start_date: string; end_date: string; purpose: string; estimated_cost: number; currency: string;
  funding_details: Record<string, unknown>; status: string; returned_from_stage?: string;
  cancellation_reason?: string; revision: number; submitted_at: string; approved_at?: string; registered_at?: string;
};
export type TerminationReason = { id: string; code: string; name: string; legal_review_required: boolean; employee_initiated: boolean };
export type TerminationTask = {
  id: string; termination_case_id: string; task_type: string; assigned_user_id?: string;
  assigned_employee_id?: string; assigned_unit_id?: string; status: 'pending' | 'completed' | 'waived' | 'cancelled';
  due_at?: string; completed_at?: string; revision: number;
};
export type TerminationProcess = {
  id: string; employee_id: string; reason_id: string; requested_date: string; effective_date?: string;
  status: string; revision: number; created_at: string; order_document_id?: string;
  process_instance_id?: string; primary_assignment_id?: string; secondary_assignment_plan?: Array<{ assignmentId: string; action: 'end' | 'retain' }>;
  cancellation_reason?: string;
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
  return {
    secretary: 'admin', 'process-designer': 'admin',
    employee: 'employee', executive: 'director', 'board-chairman': 'chairman',
    'hr-specialist': 'hr', 'hr-initiator': 'hr.initiator', 'hr-director': 'hr.director',
    'economic-director': 'economic.director', accountant: 'accountant',
    'legal-reviewer': 'legal', 'it-specialist': 'it.specialist',
    'commission-reviewer': 'commission'
  }[persona] ?? 'admin';
}

function scope() {
  const persona = currentPersona();
  if (persona === 'employee') return 'self';
  if (persona === 'executive') return 'unit';
  return 'all';
}
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
    if (status === 'manager_review') return persona === 'executive';
    return status === 'hr_review' && ['hr-specialist', 'hr-initiator', 'hr-director'].includes(persona);
  }
  if (kind === 'trip') {
    if (status === 'manager_review') return persona === 'executive';
    if (status === 'finance_review') return persona === 'economic-director' || persona === 'accountant';
    return status === 'hr_registration' && ['hr-specialist', 'hr-initiator', 'hr-director'].includes(persona);
  }
  if (['hr_review', 'registration', 'offboarding', 'scheduled', 'effective'].includes(status)) {
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
  getTermination: (id: string) => api.get<TerminationProcess>(`/terminations/${id}?${orgQuery}&scope=${scope()}`, devUser()),
  listLeaveTypes: () => api.get<LeaveType[]>(`/absence/leave-types?${orgQuery}`, devUser()),
  listLeaveBalances: (employeeId?: string) => api.get<LeaveBalance[]>(`/absence/leave-balances?${orgQuery}${employeeId ? `&employeeId=${employeeId}` : ''}`, devUser()),
  listTerminationReasons: () => api.get<TerminationReason[]>(`/terminations/reasons?${orgQuery}`, devUser()),
  listTerminationTasks: (id: string) => api.get<TerminationTask[]>(`/terminations/${id}/tasks?${orgQuery}&scope=${scope()}`, devUser()),
  currentEmployee: () => api.get<{ id: string; displayName: string }>('/employees/me', 'employee'),

  createLeave: (input: { employeeId: string; leaveTypeId: string; startDate: string; endDate: string; reason: string }) =>
    api.post<LeaveProcess>('/absence/leave-requests', { organizationId: DEMO_ORGANIZATION_ID, ...input }, 'employee'),
  decideLeave: (item: LeaveProcess, decision: ProcessDecision, comment: string) => {
    const action = item.status === 'manager_review' ? 'manager-review' : 'hr-review';
    return api.post<LeaveProcess>(`/absence/leave-requests/${item.id}/${action}`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, decision, comment }, devUser());
  },
  resubmitLeave: (item: LeaveProcess, input: { startDate: string; endDate: string; reason: string }) =>
    api.post<LeaveProcess>(`/absence/leave-requests/${item.id}/resubmit`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, ...input }, 'employee'),
  cancelLeave: (item: LeaveProcess, reason: string) => api.post<LeaveProcess>(`/absence/leave-requests/${item.id}/cancel`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, reason }, 'employee'),

  createTrip: (input: { employeeId: string; destination: string; startDate: string; endDate: string; purpose: string; estimatedCost: number; currency: string; fundingDetails?: Record<string, unknown> }) =>
    api.post<TripProcess>('/absence/business-trips', { organizationId: DEMO_ORGANIZATION_ID, fundingDetails: {}, ...input }, 'employee'),
  decideTrip: (item: TripProcess, decision: ProcessDecision, comment: string) => {
    const action = { manager_review: 'manager-review', finance_review: 'finance-review', hr_registration: 'register' }[item.status];
    if (!action) throw new Error('Для текущего этапа действие недоступно.');
    return api.post<TripProcess>(`/absence/business-trips/${item.id}/${action}`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, decision, comment }, devUser());
  },
  resubmitTrip: (item: TripProcess, input: { destination: string; startDate: string; endDate: string; purpose: string; estimatedCost: number; currency: string; fundingDetails?: Record<string, unknown> }) =>
    api.post<TripProcess>(`/absence/business-trips/${item.id}/resubmit`, { organizationId: DEMO_ORGANIZATION_ID, employeeId: item.employee_id, revision: item.revision, fundingDetails: {}, ...input }, 'employee'),
  cancelTrip: (item: TripProcess, reason: string) => api.post<TripProcess>(`/absence/business-trips/${item.id}/cancel`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, reason }, 'employee'),

  createTermination: (input: { employeeId: string; unitId: string; reasonId: string; requestedDate: string; legalBasis: string }) =>
    api.post<TerminationProcess>('/terminations', { organizationId: DEMO_ORGANIZATION_ID, ...input }, 'hr'),
  decideTermination: (item: TerminationProcess, decision: ProcessDecision, comment: string) => {
    const action = { hr_review: 'hr-review', legal_review: 'legal-review', signature: 'sign' }[item.status];
    if (!action) throw new Error('Для текущего этапа действие недоступно.');
    return api.post<TerminationProcess>(`/terminations/${item.id}/${action}`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, decision, comment }, devUser());
  },
  resubmitTermination: (item: TerminationProcess, input: { employeeId: string; unitId: string; legalBasis: string; requestedDate: string }) =>
    api.post<TerminationProcess>(`/terminations/${item.id}/resubmit`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, ...input }, devUser()),
  createAndRegisterTerminationOrder: async (item: TerminationProcess, input: { registrationNumber: string; registrationDate: string }) => {
    const types = await api.get<Array<{ id: string; code: string }>>(`/documents/types?${orgQuery}`, 'hr');
    const type = types.find((entry) => entry.code === 'termination_order');
    if (!type) throw new Error('Тип документа «Приказ об увольнении» не настроен.');
    const document = await api.post<{ id: string; revision: number }>('/documents/records', {
      organizationId: DEMO_ORGANIZATION_ID, documentTypeId: type.id, businessEntityType: 'terminationCase',
      businessEntityId: item.id, title: `Приказ об увольнении ${input.registrationNumber}`, confidentialityLevel: 'restricted'
    }, 'hr');
    const registered = await api.post<{ id: string }>(`/documents/records/${document.id}/register`, {
      organizationId: DEMO_ORGANIZATION_ID, revision: document.revision,
      registrationNumber: input.registrationNumber, registrationDate: input.registrationDate
    }, 'hr');
    return api.post<TerminationProcess>(`/terminations/${item.id}/register-order`, {
      organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, documentId: registered.id
    }, 'hr');
  },
  createTerminationTasks: (item: TerminationProcess, tasks: Array<{ taskType: string; assignedEmployeeId?: string; assignedUnitId?: string; dueAt?: string }>) =>
    api.post<TerminationTask[]>(`/terminations/${item.id}/tasks`, { organizationId: DEMO_ORGANIZATION_ID, tasks }, 'hr'),
  completeTerminationTask: (task: TerminationTask, evidence: Record<string, unknown> = {}) =>
    api.post<TerminationTask>(`/terminations/tasks/${task.id}/complete`, { organizationId: DEMO_ORGANIZATION_ID, revision: task.revision, evidence }, devUser()),
  waiveTerminationTask: (task: TerminationTask, reason: string) =>
    api.post<TerminationTask>(`/terminations/tasks/${task.id}/waive`, { organizationId: DEMO_ORGANIZATION_ID, revision: task.revision, reason }, 'hr'),
  scheduleTermination: (item: TerminationProcess, effectiveDate: string, secondaryAssignments: Array<{ assignmentId: string; action: 'end' | 'retain' }> = []) => api.post<TerminationProcess>(`/terminations/${item.id}/schedule`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, effectiveDate, secondaryAssignments }, 'hr'),
  completeTermination: (item: TerminationProcess) => api.post<TerminationProcess>(`/terminations/${item.id}/complete`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision }, 'hr'),
  cancelTermination: (item: TerminationProcess, reason: string) => api.post<TerminationProcess>(`/terminations/${item.id}/cancel`, { organizationId: DEMO_ORGANIZATION_ID, revision: item.revision, reason }, 'hr')
};

export async function listWorkforceProcesses(kind: ProcessKind): Promise<WorkforceProcess[]> {
  if (kind === 'leave') return workforceProcessesApi.listLeaves();
  if (kind === 'trip') return workforceProcessesApi.listTrips();
  return workforceProcessesApi.listTerminations();
}
