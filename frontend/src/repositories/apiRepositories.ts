/// <reference types="vite/client" />

import type { Correspondence, DashboardSnapshot, Employee, IncomingLetterInput, ProcessDefinition, WorkTask } from '../shared/types';
import type { CorrespondenceRepository, OperationsRepository, OrganizationRepository, TaskRepository, WorkflowRepository } from './contracts';

type Envelope<T> = { data: T; meta: { requestId: string } };
type ErrorEnvelope = { error?: { code?: string; message?: string; requestId?: string } };

const personaToDevUser: Record<string, string> = {
  secretary: 'admin',
  executive: 'director',
  employee: 'employee',
  'hr-specialist': 'hr',
  'process-designer': 'admin'
};

function currentDevUser() {
  try {
    const stored = JSON.parse(localStorage.getItem('ertis-developer-settings') ?? '{}') as { state?: { persona?: string } };
    return personaToDevUser[stored.state?.persona ?? ''] ?? 'admin';
  } catch {
    return 'admin';
  }
}

export class ApiClient {
  constructor(readonly baseUrl = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1') {}

  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const isFormData = init?.body instanceof FormData;
    const response = await fetch(`${this.baseUrl.replace(/\/$/, '')}${path}`, {
      ...init,
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        'X-Dev-User': currentDevUser(),
        ...init?.headers
      }
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as ErrorEnvelope;
      const detail = payload.error;
      throw new Error([detail?.code ?? `API_${response.status}`, detail?.message, detail?.requestId && `request ${detail.requestId}`].filter(Boolean).join(': '));
    }
    return ((await response.json()) as Envelope<T>).data;
  }

  get<T>(path: string) { return this.request<T>(path); }
  post<T>(path: string, body?: unknown) { return this.request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }); }
}

export class ApiCorrespondenceRepository implements CorrespondenceRepository {
  constructor(private readonly api: ApiClient) {}
  listIncoming() { return this.api.get<Correspondence[]>('/operations/correspondence/incoming'); }
  getIncoming(id: string) { return this.api.get<Correspondence>(`/operations/correspondence/incoming/${id}`); }
  checkDuplicate(sender: string, senderNumber: string) { return this.api.get<Correspondence | null>(`/operations/correspondence/incoming/duplicate?sender=${encodeURIComponent(sender)}&senderNumber=${encodeURIComponent(senderNumber)}`); }
  registerIncoming(input: IncomingLetterInput) { return this.api.post<Correspondence>('/operations/correspondence/incoming', input); }
  sendForResolution(id: string) { return this.api.post<Correspondence>(`/operations/correspondence/incoming/${id}/resolution`); }
}

export class ApiTaskRepository implements TaskRepository {
  constructor(private readonly api: ApiClient) {}
  list() { return this.api.get<WorkTask[]>('/operations/tasks'); }
  claim(id: string) { return this.api.post<WorkTask>(`/operations/tasks/${id}/claim`); }
  complete(id: string) { return this.api.post<WorkTask>(`/operations/tasks/${id}/complete`); }
}

export class ApiWorkflowRepository implements WorkflowRepository {
  constructor(private readonly api: ApiClient) {}
  listDefinitions() { return this.api.get<ProcessDefinition[]>('/operations/processes'); }
  retryIncident(id: string) { return this.api.post<ProcessDefinition>(`/operations/processes/${id}/retry`); }
}

export class ApiOrganizationRepository implements OrganizationRepository {
  constructor(private readonly api: ApiClient) {}
  listEmployees() { return this.api.get<Employee[]>('/operations/directory/employees'); }
}

export class ApiOperationsRepository implements OperationsRepository {
  constructor(private readonly api: ApiClient) {}
  dashboard() { return this.api.get<DashboardSnapshot>('/operations/dashboard'); }
  async reset() { /* Production-backed data is never deleted from a developer toolbar. */ }
}

export function createApiRepositories(api = new ApiClient()) {
  return {
    correspondence: new ApiCorrespondenceRepository(api),
    tasks: new ApiTaskRepository(api),
    workflows: new ApiWorkflowRepository(api),
    organization: new ApiOrganizationRepository(api),
    operations: new ApiOperationsRepository(api)
  };
}
