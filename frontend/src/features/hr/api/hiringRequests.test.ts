import { afterEach, describe, expect, it, vi } from 'vitest';
import { canPersonaAcknowledgeRequest, canPersonaApproveRequest, hiringRequestsApi, type HiringRequest } from './hiringRequests';

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

  it('requests only final-approved packages for the HR dispatch queue', async () => {
    localStorage.setItem('ertis-developer-settings', JSON.stringify({ state: { persona: 'hr-specialist' } }));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: [
          { id: 'ready', status: 'final_approved' },
          { id: 'done', status: 'completed' }
        ],
        meta: { requestId: 'test-request' }
      })
    });
    vi.stubGlobal('fetch', fetchMock);

    const requests = await hiringRequestsApi.list('dispatch');

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('scope=dispatch'), expect.objectContaining({
      headers: expect.objectContaining({ 'X-Dev-User': 'hr.initiator' })
    }));
    expect(requests).toEqual([expect.objectContaining({ id: 'ready', status: 'final_approved' })]);
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

  it('routes the primary executive persona through the chairman identity', async () => {
    localStorage.setItem('ertis-developer-settings', JSON.stringify({ state: { persona: 'executive' } }));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], meta: { requestId: 'test-request' } })
    });
    vi.stubGlobal('fetch', fetchMock);

    await hiringRequestsApi.list('inbox');

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('scope=inbox'), expect.objectContaining({
      headers: expect.objectContaining({ 'X-Dev-User': 'chairman' })
    }));
  });

  it('uses the hiring initiator for a generic unified-workspace persona', async () => {
    localStorage.setItem('ertis-developer-settings', JSON.stringify({ state: { persona: 'secretary' } }));
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

  it('only enables a decision for the persona assigned to the current backend stage', () => {
    const request = { status: 'under_review', currentStageCode: 'economic_director' } as HiringRequest;

    expect(canPersonaApproveRequest('economic-director', request)).toBe(true);
    expect(canPersonaApproveRequest('hr-director', request)).toBe(false);
    expect(canPersonaApproveRequest('secretary', request)).toBe(false);

    const chairmanRequest = { status: 'under_review', currentStageCode: 'chairman' } as HiringRequest;
    expect(canPersonaApproveRequest('executive', chairmanRequest)).toBe(true);
    expect(canPersonaApproveRequest('board-chairman', chairmanRequest)).toBe(true);
  });

  it('only enables receipt confirmation for the pending assigned recipient', () => {
    const request = {
      status: 'partially_acknowledged',
      dispatches: [
        { recipientType: 'accounting', status: 'acknowledged' },
        { recipientType: 'it', status: 'assigned' }
      ]
    } as HiringRequest;

    expect(canPersonaAcknowledgeRequest('accountant', request)).toBe(false);
    expect(canPersonaAcknowledgeRequest('it-specialist', request)).toBe(true);
  });
});
