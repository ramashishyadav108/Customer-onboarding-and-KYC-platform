import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { App } from '@/App';
import { AuthProvider, type Session } from '@/state/AuthContext';
import { ForbiddenPage } from '@/pages/ForbiddenPage';
import { RuleSetsPage } from '@/pages/admin/RuleSetsPage';
import { CaseDetailPage } from '@/pages/staff/CaseDetailPage';
import { StatusPage } from '@/pages/prospect/StatusPage';
import { setAccessToken } from '@/api/client';
import type { Evidence, RuleSet } from '@/types';
import { makeCase, mockFetch, prospectSession, renderApp } from './helpers';

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

const analyst: Session = { token: 't-an', role: 'kyc-analyst', caseId: null };
const admin: Session = { token: 't-ad', role: 'admin', caseId: null };

function renderRoutes(path: string, session: Session | null) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initial={session}>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('App routing and shell', () => {
  it('NFR-04: sends an anonymous visitor at / to the registration form', () => {
    mockFetch({});
    renderRoutes('/', null);
    expect(screen.getByRole('button', { name: 'Start application' })).toBeInTheDocument();
  });

  it('NFR-04: sends a signed-in admin at / to the dashboard shell with admin navigation', async () => {
    mockFetch({});
    renderRoutes('/', admin);
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: 'Rule sets' })).toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: 'Watchlist' })).toBeInTheDocument();
    expect(screen.getByText('Signed in as admin')).toBeInTheDocument();
  });

  it('NFR-04: shows the forbidden page when a prospect opens an admin route', async () => {
    mockFetch({});
    renderRoutes('/admin/rule-sets', prospectSession);
    expect(await screen.findByRole('heading', { name: '403 Forbidden' })).toBeInTheDocument();
  });

  it('NFR-04: sign out returns staff to the login page', async () => {
    mockFetch({});
    renderRoutes('/staff/workbench', analyst);
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('NFR-04: sign out returns a prospect to registration', async () => {
    mockFetch({ [`GET /api/v1/cases/${prospectSession.caseId}`]: makeCase(), [`GET /api/v1/cases/${prospectSession.caseId}/notifications`]: { items: [] } });
    renderRoutes('/portal/status', prospectSession);
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('button', { name: 'Start application' })).toBeInTheDocument();
  });
});

describe('ForbiddenPage', () => {
  it('NFR-04: links a signed-in user to their role home and an anonymous one to login', () => {
    const { unmount } = renderApp(<ForbiddenPage />, { session: analyst });
    expect(screen.getByRole('link', { name: 'Go to your home page' })).toHaveAttribute('href', '/staff/workbench');
    unmount();
    renderApp(<ForbiddenPage />);
    expect(screen.getByRole('link', { name: 'Go to your home page' })).toHaveAttribute('href', '/login');
  });
});

describe('StatusPage', () => {
  const base = `GET /api/v1/cases/${prospectSession.caseId}`;
  const empty = { [`${base}/notifications`]: { items: [] } };

  it('AC-04: invites a prospect without a case to start an application', () => {
    mockFetch({});
    renderApp(<StatusPage />, { session: { token: 't', role: 'prospect', caseId: null } });
    expect(screen.getByRole('link', { name: 'Start one' })).toBeInTheDocument();
  });

  it('AC-04: shows an error when the case cannot be loaded', async () => {
    mockFetch({ [base]: { status: 500, body: { error: { code: 'INTERNAL', message: 'Boom', details: {} } } }, ...empty });
    renderApp(<StatusPage />, { session: prospectSession });
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('AC-07: announces the masked account number once approved', async () => {
    mockFetch({ [base]: makeCase({ state: 'APPROVED', account_number_masked: '******4321' }), ...empty });
    renderApp(<StatusPage />, { session: prospectSession });
    expect(await screen.findByText(/Your account is open: \*{6}4321/)).toBeInTheDocument();
  });

  it('AC-07: explains rejection and manual review without leaking internal reason codes', async () => {
    mockFetch({ [base]: makeCase({ state: 'REJECTED' }), ...empty });
    const { unmount } = renderApp(<StatusPage />, { session: prospectSession });
    expect(await screen.findByText('Your application was not approved.')).toBeInTheDocument();
    unmount();
    mockFetch({ [base]: makeCase({ state: 'MANUAL_REVIEW' }), ...empty });
    renderApp(<StatusPage />, { session: prospectSession });
    expect(await screen.findByText(/additional review by our compliance team/)).toBeInTheDocument();
  });

  it('AC-03: flags documents needing action and refreshes on demand', async () => {
    const { calls } = mockFetch({
      [base]: makeCase({ action_required: [{ item_code: 'ID_PROOF', status: 'REJECTED', reason_code: 'DOC_EXPIRED' }] }),
      ...empty,
    });
    renderApp(<StatusPage />, { session: prospectSession });
    expect(await screen.findByText(/Action required on 1 document/)).toBeInTheDocument();
    const before = calls.length;
    await userEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    await screen.findByText(/Action required on 1 document/);
    expect(calls.length).toBeGreaterThan(before);
  });
});

const CASE_ID = 'aaaaaaaa-1111-2222-3333-444444444444';
const evidence: Evidence = {
  case_id: CASE_ID,
  state: 'DOCS_SUBMITTED',
  product: 'Savings',
  documents: [
    { document_id: 'd1', checklist_item: 'ID_PROOF', version: 1, status: 'VERIFIED', doc_class: 'PAN', reason_code: null, confidence_bp: 9500, rule_version: 1, superseded: false, size_bytes: 1000, sha256: 'ab', uploaded_at: '2026-10-01T09:30:00Z' },
    { document_id: 'd0', checklist_item: 'ID_PROOF', version: 0, status: 'REJECTED', doc_class: 'PAN', reason_code: 'DOC_EXPIRED', confidence_bp: 0, rule_version: 1, superseded: true, size_bytes: 900, sha256: 'cd', uploaded_at: '2026-10-01T09:20:00Z' },
  ],
  screening: null,
  risk_assessment: null,
  decision: null,
  override: null,
  review_reason_code: null,
  account_number_masked: null,
};

describe('CaseDetailPage', () => {
  const urls = {
    [`GET /api/v1/cases/${CASE_ID}/evidence`]: evidence,
    [`GET /api/v1/cases/${CASE_ID}`]: makeCase({ case_id: CASE_ID, state: 'DOCS_SUBMITTED' }),
  };

  it('AC-08: requires a reason before rejecting a document, then confirms and reloads', async () => {
    const { calls } = mockFetch({ ...urls, [`POST /api/v1/cases/${CASE_ID}/documents/d1/reject`]: { body: { document_id: 'd1', status: 'REJECTED', reason_code: 'DOC_EXPIRED' } } });
    renderApp(<CaseDetailPage />, { session: analyst, path: `/staff/cases/${CASE_ID}`, route: '/staff/cases/:caseId' });
    await userEvent.click(await screen.findByRole('button', { name: /^Reject / }));
    await userEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }));
    expect(calls.some((c) => c.key.startsWith('POST'))).toBe(false);
    await userEvent.selectOptions(screen.getByLabelText('Reason code'), 'DOC_EXPIRED');
    await userEvent.click(screen.getByRole('button', { name: 'Confirm rejection' }));
    expect(await screen.findByText(/Document rejected \(DOC_EXPIRED\)/)).toBeInTheDocument();
    expect(calls.find((c) => c.key.startsWith('POST'))?.body).toMatchObject({ reason_code: 'DOC_EXPIRED' });
  });

  it('AC-04: lets an analyst run the pipeline for a submitted case', async () => {
    const { calls } = mockFetch({ ...urls, [`POST /api/v1/cases/${CASE_ID}/advance`]: { body: { case_id: CASE_ID, state: 'CLASSIFIED', steps_run: ['screen'] } } });
    renderApp(<CaseDetailPage />, { session: analyst, path: `/staff/cases/${CASE_ID}`, route: '/staff/cases/:caseId' });
    await userEvent.click(await screen.findByRole('button', { name: 'Run screening, classification and decision' }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === `POST /api/v1/cases/${CASE_ID}/advance`)).toBe(true));
  });

  it('NFR-04: hides document rejection from admins and shows backend errors', async () => {
    mockFetch({ [`GET /api/v1/cases/${CASE_ID}/evidence`]: { status: 403, body: { error: { code: 'FORBIDDEN', message: 'Not allowed', details: {} } } }, [`GET /api/v1/cases/${CASE_ID}`]: makeCase({ case_id: CASE_ID }) });
    renderApp(<CaseDetailPage />, { session: admin, path: `/staff/cases/${CASE_ID}`, route: '/staff/cases/:caseId' });
    expect((await screen.findAllByRole('alert'))[0]).toHaveTextContent(/./);
    expect(screen.queryByRole('button', { name: /^Reject / })).not.toBeInTheDocument();
  });
});

const draft: RuleSet = {
  version: 2,
  status: 'DRAFT',
  author: 'admin1',
  created_at: '2026-10-01T09:00:00Z',
  published_at: null,
  weights: { age: 25, income_band: 25, occupation_category: 25, geography: 25 },
  points: {},
  geography_map: {},
  geography_default: 'MEDIUM',
  border_states: [],
  thresholds: { low_max: 30, medium_max: 60 },
};
const published: RuleSet = { ...draft, version: 1, status: 'PUBLISHED', published_at: '2026-09-30T09:00:00Z' };

describe('RuleSetsPage', () => {
  const listBoth = { items: [published, draft] };

  it('AC-06: lists versions, marks published ones immutable and blocks a second draft', async () => {
    mockFetch({ 'GET /api/v1/admin/rule-sets': listBoth });
    renderApp(<RuleSetsPage />, { session: admin });
    expect(await screen.findByText('Immutable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create draft from latest' })).toBeDisabled();
    expect(screen.getByText('A draft already exists.')).toBeInTheDocument();
  });

  it('AC-06: rejects non-integer weights and thresholds that break ordering', async () => {
    mockFetch({ 'GET /api/v1/admin/rule-sets': listBoth, 'GET /api/v1/admin/rule-sets/2': draft });
    renderApp(<RuleSetsPage />, { session: admin });
    await userEvent.click(await screen.findByRole('button', { name: 'Edit v2' }));
    const age = await screen.findByLabelText('Weight: age');
    await userEvent.clear(age);
    await userEvent.type(age, '2.5');
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    expect(await screen.findByText('Whole number required (no decimals).')).toBeInTheDocument();
    await userEvent.clear(age);
    await userEvent.type(age, '25');
    const low = screen.getByLabelText('LOW max score');
    await userEvent.clear(low);
    await userEvent.type(low, '70');
    await userEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    expect(await screen.findByText(/low max < medium max < 100/)).toBeInTheDocument();
  });

  it('AC-06: saves a valid draft with integer values', async () => {
    const { calls } = mockFetch({
      'GET /api/v1/admin/rule-sets': listBoth,
      'GET /api/v1/admin/rule-sets/2': draft,
      'PUT /api/v1/admin/rule-sets/2': { body: draft },
    });
    renderApp(<RuleSetsPage />, { session: admin });
    await userEvent.click(await screen.findByRole('button', { name: 'Edit v2' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Save draft' }));
    expect(await screen.findByText('Draft saved.')).toBeInTheDocument();
    const put = calls.find((c) => c.key === 'PUT /api/v1/admin/rule-sets/2');
    expect(put?.body).toMatchObject({ thresholds: { low_max: 30, medium_max: 60 }, weights: { age: 25 } });
  });

  it('AC-06: publishing needs confirmation and can be cancelled', async () => {
    const { calls } = mockFetch({
      'GET /api/v1/admin/rule-sets': listBoth,
      'POST /api/v1/admin/rule-sets/2/publish': { body: { ...draft, status: 'PUBLISHED' } },
    });
    renderApp(<RuleSetsPage />, { session: admin });
    await userEvent.click(await screen.findByRole('button', { name: 'Publish v2' }));
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(calls.some((c) => c.key.startsWith('POST'))).toBe(false);
    await userEvent.click(screen.getByRole('button', { name: 'Publish v2' }));
    await userEvent.click(screen.getByRole('button', { name: 'Publish' }));
    expect(await screen.findByText(/version 2 published\. It is now immutable/)).toBeInTheDocument();
  });

  it('AC-06: creates a draft from the latest published version', async () => {
    const { calls } = mockFetch({
      'GET /api/v1/admin/rule-sets': { items: [published] },
      'POST /api/v1/admin/rule-sets': { status: 201, body: draft },
    });
    renderApp(<RuleSetsPage />, { session: admin });
    await userEvent.click(await screen.findByRole('button', { name: 'Create draft from latest' }));
    expect(await screen.findByText('Edit draft version 2')).toBeInTheDocument();
    expect(calls.some((c) => c.key === 'POST /api/v1/admin/rule-sets')).toBe(true);
  });
});
