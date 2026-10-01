import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, buildQuery, describeError, request, setAccessToken, setUnauthorizedHandler } from '@/api/client';
import { casesApi, documentsApi, leadsApi } from '@/api/resources';
import { reportsApi } from '@/api/admin';
import { mockFetch } from './helpers';

afterEach(() => {
  setAccessToken(null);
  setUnauthorizedHandler(null);
  vi.unstubAllGlobals();
});

describe('api client', () => {
  it('AC-01: POST /leads sends no bearer token and returns the prospect token', async () => {
    setAccessToken('stale');
    const { calls } = mockFetch({
      'POST /api/v1/leads': { body: { case_id: 'c1', state: 'INITIATED', product: 'Savings', access_token: 'jwt', token_type: 'bearer', expires_in: 1800 } },
    });
    const res = await leadsApi.create({ name: 'Meera Nair', contact: '9876543221', product: 'Savings' }, 'idem-1');
    expect(res.state).toBe('INITIATED');
    expect(calls[0].headers.Authorization).toBeUndefined();
    expect(calls[0].headers['Idempotency-Key']).toBe('idem-1');
    expect(calls[0].body).toEqual({ name: 'Meera Nair', contact: '9876543221', product: 'Savings' });
  });

  it('NFR-04: attaches the bearer token and a correlation id to authenticated requests', async () => {
    setAccessToken('jwt-abc');
    const { calls } = mockFetch({ 'GET /api/v1/cases/c1': { body: { case_id: 'c1' } } });
    await casesApi.get('c1');
    expect(calls[0].headers.Authorization).toBe('Bearer jwt-abc');
    expect(calls[0].headers['X-Correlation-ID']).toMatch(/.+/);
  });

  it('AC-01: maps the error envelope to ApiError with code, details and correlation id', async () => {
    mockFetch({
      'POST /api/v1/leads': { status: 422, body: { error: { code: 'VALIDATION_ERROR', message: 'Invalid', details: { fields: [{ field: 'contact', message: 'bad' }] } } } },
    });
    const err = await leadsApi.create({ name: 'x', contact: 'y', product: 'NRE' }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const api = err as ApiError;
    expect(api.status).toBe(422);
    expect(api.code).toBe('VALIDATION_ERROR');
    expect(api.correlationId).toBe('corr-1234567890');
    expect(describeError(api)).toContain('ref corr-123');
  });

  it('AC-02: upload sends multipart form data with checklist_item and file', async () => {
    const { fn } = mockFetch({ 'POST /api/v1/cases/c1/documents': { status: 201, body: { document_id: 'd1', status: 'VERIFIED' } } });
    await documentsApi.upload('c1', 'ID_PROOF', new File(['x'], 'pan_valid.pdf', { type: 'application/pdf' }));
    const init = fn.mock.calls[0][1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get('checklist_item')).toBe('ID_PROOF');
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined();
  });

  it('NFR-04: invokes the unauthorized handler on a 401 from an authenticated call', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    setAccessToken('expired');
    mockFetch({ 'GET /api/v1/cases/c1': { status: 401, body: { error: { code: 'UNAUTHENTICATED', message: 'Expired', details: {} } } } });
    await expect(casesApi.get('c1')).rejects.toMatchObject({ code: 'UNAUTHENTICATED' });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('AC-01: reports a network failure as NETWORK_ERROR', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await expect(request('/health')).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: 0 });
  });

  it('AC-01: falls back to UNKNOWN_ERROR when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 })));
    await expect(request('/cases')).rejects.toMatchObject({ code: 'UNKNOWN_ERROR', status: 502 });
  });

  it('AC-10: builds report queries skipping empty filters', () => {
    expect(buildQuery({ product: '', from: '2026-09-01', to: undefined })).toBe('?from=2026-09-01');
    expect(buildQuery()).toBe('');
  });

  it('AC-10: loads all seven report endpoints with the same filters', async () => {
    const empty = { items: [], stages: [], buckets: [], count: 0, oldest_age_minutes: 0, auto_approved: 0, decided: 0, rate_bp: 0, target_bp: 6000, met: false };
    const { calls } = mockFetch(
      Object.fromEntries(['tat', 'funnel', 'backlog', 'time-per-stage', 'rejection-reasons', 'auto-approval', 'dropped-leads'].map((p) => [`GET /api/v1/admin/reports/${p}`, { body: empty }])),
    );
    const r = await reportsApi.all({ product: 'NRE', from: '2026-09-01', to: '2026-09-30' });
    expect(calls).toHaveLength(7);
    expect(calls.every((c) => c.url.includes('product=NRE') && c.url.includes('from=2026-09-01'))).toBe(true);
    expect(r.autoApproval.target_bp).toBe(6000);
  });

  it('AC-10: describeError handles non-API errors', () => {
    expect(describeError(new Error('boom'))).toBe('boom');
    expect(describeError('x')).toBe('Something went wrong.');
  });
});
