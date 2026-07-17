import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from './apiRepositories';

describe('ApiClient runtime routing', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses the same-origin API path when no build-time URL is configured', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { activeTasks: 2 }, meta: { requestId: 'test-request' } })
    });
    vi.stubGlobal('fetch', fetchMock);

    await new ApiClient().get('/operations/dashboard');

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/operations/dashboard', expect.objectContaining({
      headers: expect.objectContaining({ 'X-Dev-User': 'hr' })
    }));
  });

  it('allows a feature to use its dedicated development identity', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: {}, meta: { requestId: 'test-request' } })
    });
    vi.stubGlobal('fetch', fetchMock);

    await new ApiClient().post('/hiring-requests', {}, 'hr.initiator');

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/hiring-requests', expect.objectContaining({
      headers: expect.objectContaining({ 'X-Dev-User': 'hr.initiator' })
    }));
  });
});
