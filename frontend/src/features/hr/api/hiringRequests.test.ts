import { afterEach, describe, expect, it, vi } from 'vitest';
import { hiringRequestsApi } from './hiringRequests';

describe('hiring request development identity', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('routes the HR specialist through the hiring initiator identity', async () => {
    localStorage.setItem('ertis-developer-settings', JSON.stringify({ state: { persona: 'hr-specialist' } }));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], meta: { requestId: 'test-request' } })
    });
    vi.stubGlobal('fetch', fetchMock);

    await hiringRequestsApi.list();

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/hiring-requests'), expect.objectContaining({
      headers: expect.objectContaining({ 'X-Dev-User': 'hr.initiator' })
    }));
  });

  it('keeps approver identities unchanged', async () => {
    localStorage.setItem('ertis-developer-settings', JSON.stringify({ state: { persona: 'hr-director' } }));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], meta: { requestId: 'test-request' } })
    });
    vi.stubGlobal('fetch', fetchMock);

    await hiringRequestsApi.list('inbox');

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/hiring-requests'), expect.objectContaining({
      headers: expect.objectContaining({ 'X-Dev-User': 'hr.director' })
    }));
  });
});
