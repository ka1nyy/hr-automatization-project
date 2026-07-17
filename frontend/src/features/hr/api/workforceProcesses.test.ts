import { afterEach, describe, expect, it, vi } from 'vitest';
import { canActOnProcess, workforceProcessesApi } from './workforceProcesses';

describe('workforce process frontend routing', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('loads the employee self-service leave queue through the employee identity', async () => {
    localStorage.setItem('ertis-developer-settings', JSON.stringify({ state: { persona: 'employee' } }));
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: [], meta: { requestId: 'test' } }) });
    vi.stubGlobal('fetch', fetchMock);

    await workforceProcessesApi.listLeaves();

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('scope=self'), expect.objectContaining({ headers: expect.objectContaining({ 'X-Dev-User': 'employee' }) }));
  });

  it('loads organization queues through authorized development identities', async () => {
    localStorage.setItem('ertis-developer-settings', JSON.stringify({ state: { persona: 'hr-specialist' } }));
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: [], meta: { requestId: 'test' } }) });
    vi.stubGlobal('fetch', fetchMock);

    await workforceProcessesApi.listTerminations();

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('scope=all'), expect.objectContaining({ headers: expect.objectContaining({ 'X-Dev-User': 'hr' }) }));
  });

  it('loads a manager queue with unit scope instead of leaking the organization queue', async () => {
    localStorage.setItem('ertis-developer-settings', JSON.stringify({ state: { persona: 'executive' } }));
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ data: [], meta: { requestId: 'test' } }) });
    vi.stubGlobal('fetch', fetchMock);

    await workforceProcessesApi.listLeaves();

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('scope=unit'), expect.objectContaining({ headers: expect.objectContaining({ 'X-Dev-User': 'director' }) }));
  });

  it('matches every workflow stage to the intended frontend role', () => {
    expect(canActOnProcess('executive', 'leave', 'manager_review')).toBe(true);
    expect(canActOnProcess('hr-specialist', 'leave', 'hr_review')).toBe(true);
    expect(canActOnProcess('economic-director', 'trip', 'finance_review')).toBe(true);
    expect(canActOnProcess('hr-director', 'termination', 'hr_review')).toBe(true);
    expect(canActOnProcess('economic-director', 'termination', 'economic_review')).toBe(true);
    expect(canActOnProcess('legal-reviewer', 'termination', 'legal_review')).toBe(true);
    expect(canActOnProcess('board-chairman', 'termination', 'signature')).toBe(true);
    expect(canActOnProcess('executive', 'termination', 'signature')).toBe(false);
    expect(canActOnProcess('board-chairman', 'leave', 'manager_review')).toBe(false);
    expect(canActOnProcess('secretary', 'termination', 'signature')).toBe(false);
  });
});
