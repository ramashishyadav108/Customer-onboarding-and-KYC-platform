import type { ReactElement } from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';
import { AuthProvider, type Session } from '@/state/AuthContext';
import type { CaseDetail, Notification } from '@/types';

export type Handler = (req: { url: string; method: string; body: unknown; headers: Record<string, string> }) => { status?: number; body?: unknown };

// Stubs global fetch; handlers keyed by "METHOD /path" (path without query).
export function mockFetch(handlers: Record<string, Handler | unknown>) {
  const calls: { key: string; url: string; body: unknown; headers: Record<string, string> }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    const path = url.split('?')[0];
    const key = `${method} ${path}`;
    const headers = (init?.headers ?? {}) as Record<string, string>;
    let body: unknown = init?.body;
    if (typeof body === 'string') body = JSON.parse(body);
    calls.push({ key, url, body, headers });
    const h = handlers[key];
    if (h === undefined) return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: `no mock for ${key}`, details: {} } }), { status: 404 });
    const out = typeof h === 'function' ? (h as Handler)({ url, method, body, headers }) : typeof h === 'object' && h !== null && 'body' in h ? (h as { body: unknown; status?: number }) : { body: h };
    return new Response(JSON.stringify(out.body ?? {}), { status: out.status ?? 200, headers: { 'X-Correlation-ID': 'corr-1234567890' } });
  });
  vi.stubGlobal('fetch', fn);
  return { fn, calls };
}

export function renderApp(ui: ReactElement, opts: { session?: Session | null; path?: string; route?: string } = {}) {
  const session = opts.session === undefined ? null : opts.session;
  return render(
    <MemoryRouter initialEntries={[opts.path ?? '/']}>
      <AuthProvider initial={session}>
        <Routes>
          <Route path={opts.route ?? '*'} element={ui} />
          <Route path="/login" element={<p>login screen</p>} />
          <Route path="/portal/register" element={<p>register screen</p>} />
          <Route path="/forbidden" element={<p>forbidden screen</p>} />
          <Route path="/portal/profile" element={<p>profile screen</p>} />
          <Route path="/portal/status" element={<p>status screen</p>} />
          <Route path="/staff/workbench" element={<p>workbench screen</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

export const prospectSession: Session = { token: 'tok-prospect', role: 'prospect', caseId: '3f0c2c9e-7a54-4b7e-9d3e-5b1f6a2e9c10' };
export const officerSession: Session = { token: 'tok-officer', role: 'compliance-officer', caseId: null };

export function makeCase(over: Partial<CaseDetail> = {}): CaseDetail {
  return {
    case_id: '3f0c2c9e-7a54-4b7e-9d3e-5b1f6a2e9c10',
    name: 'Meera Nair',
    contact_masked: '********21',
    product: 'Savings',
    state: 'INITIATED',
    checklist_version: 1,
    checklist_items: [
      { item_code: 'ID_PROOF', mandatory: true, accepted_classes: ['PAN', 'AADHAAR', 'PASSPORT'], status: 'VERIFIED', document_id: 'd1', doc_version: 1, doc_class: 'PAN', reason_code: null },
      { item_code: 'ADDRESS_PROOF', mandatory: true, accepted_classes: ['UTILITY_BILL', 'AADHAAR'], status: 'MISSING', document_id: null, doc_version: null, doc_class: null, reason_code: null },
      { item_code: 'PHOTOGRAPH', mandatory: true, accepted_classes: ['PHOTOGRAPH'], status: 'MISSING', document_id: null, doc_version: null, doc_class: null, reason_code: null },
    ],
    missing_items: ['ADDRESS_PROOF', 'PHOTOGRAPH'],
    action_required: [],
    profile: null,
    profile_complete: false,
    account_number_masked: null,
    created_at: '2026-10-01T09:30:00Z',
    updated_at: '2026-10-01T09:31:12Z',
    ...over,
  };
}

export function makeNotification(event: string, reason?: string, id = event): Notification {
  return {
    notification_id: id,
    case_id: '3f0c2c9e-7a54-4b7e-9d3e-5b1f6a2e9c10',
    event,
    template: event.toLowerCase(),
    text: `Status changed to ${event}`,
    details: reason ? { reason_code: reason } : {},
    created_at: '2026-10-01T09:40:00Z',
  };
}
