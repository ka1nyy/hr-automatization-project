/// <reference types="vite/client" />

type Envelope<T> = { data: T; meta: { requestId: string } };
type ErrorEnvelope = { error?: { code?: string; message?: string; requestId?: string } };

const personaToDevUser: Record<string, string> = {
  secretary: 'admin',
  executive: 'director',
  employee: 'employee',
  'hr-specialist': 'hr',
  'process-designer': 'admin'
  , 'hr-initiator': 'hr.initiator', 'hr-director': 'hr.director', 'economic-director': 'economic.director'
  , 'commission-reviewer': 'commission', 'legal-reviewer': 'legal', 'board-chairman': 'chairman'
  , accountant: 'accountant', 'it-specialist': 'it.specialist'
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
  patch<T>(path: string, body: unknown) { return this.request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }); }
  upload<T>(path: string, body: FormData) { return this.request<T>(path, { method: 'POST', body }); }
}

