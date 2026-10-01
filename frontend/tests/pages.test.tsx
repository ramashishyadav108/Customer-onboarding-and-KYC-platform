import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LeadFormPage } from '@/pages/prospect/LeadFormPage';
import { ProfilePage } from '@/pages/prospect/ProfilePage';
import { UploadPage } from '@/pages/prospect/UploadPage';
import { StatusPage } from '@/pages/prospect/StatusPage';
import { LoginPage } from '@/pages/staff/LoginPage';
import { ReviewPanel } from '@/pages/staff/ReviewPanel';
import { ReviewQueuePage } from '@/pages/staff/ReviewQueuePage';
import { WorkbenchPage } from '@/pages/staff/WorkbenchPage';
import { DashboardPage } from '@/pages/admin/DashboardPage';
import { WatchlistPage } from '@/pages/admin/WatchlistPage';
import { getAccessToken, setAccessToken } from '@/api/client';
import type { Evidence } from '@/types';
import { makeCase, makeNotification, mockFetch, officerSession, prospectSession, renderApp } from './helpers';

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

const CASE_URL = `GET /api/v1/cases/${prospectSession.caseId}`;

describe('LeadFormPage', () => {
  it('AC-01.7: shows field errors and creates nothing when the form is invalid', async () => {
    const { calls } = mockFetch({});
    renderApp(<LeadFormPage />);
    await userEvent.click(screen.getByRole('button', { name: 'Start application' }));
    expect(screen.getByLabelText('Full name')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('Choose a product.')).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });

  it('AC-01: registers a lead, stores the prospect token and continues to the profile step', async () => {
    const { calls } = mockFetch({
      'POST /api/v1/leads': { status: 201, body: { case_id: 'c-1', state: 'INITIATED', product: 'NRE', access_token: 'prospect-jwt', token_type: 'bearer', expires_in: 1800 } },
    });
    renderApp(<LeadFormPage />);
    await userEvent.type(screen.getByLabelText('Full name'), 'Meera Nair');
    await userEvent.type(screen.getByLabelText('Contact (phone or email)'), '9876543221');
    await userEvent.selectOptions(screen.getByLabelText('Account type'), 'NRE');
    await userEvent.click(screen.getByRole('button', { name: 'Start application' }));
    expect(await screen.findByText('profile screen')).toBeInTheDocument();
    expect(calls[0].body).toEqual({ name: 'Meera Nair', contact: '9876543221', product: 'NRE' });
    expect(getAccessToken()).toBe('prospect-jwt');
  });

  it('AC-01: surfaces server-side field errors from a 422 response', async () => {
    mockFetch({
      'POST /api/v1/leads': { status: 422, body: { error: { code: 'VALIDATION_ERROR', message: 'Invalid lead', details: { fields: [{ field: 'contact', message: 'Contact already blocked' }] } } } },
    });
    renderApp(<LeadFormPage />);
    await userEvent.type(screen.getByLabelText('Full name'), 'Meera Nair');
    await userEvent.type(screen.getByLabelText('Contact (phone or email)'), '9876543221');
    await userEvent.selectOptions(screen.getByLabelText('Account type'), 'Savings');
    await userEvent.click(screen.getByRole('button', { name: 'Start application' }));
    expect(await screen.findByText('Contact already blocked')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid lead');
  });
});

describe('ProfilePage', () => {
  it('AC-06: requires state code for country IN and hides it for other countries', async () => {
    mockFetch({ [CASE_URL]: makeCase() });
    renderApp(<ProfilePage />, { session: prospectSession });
    await waitFor(() => expect(screen.queryByText('Loading...')).not.toBeInTheDocument());
    expect(screen.getByLabelText(/State code/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Date of birth'), '1990-04-12');
    await userEvent.type(screen.getByLabelText('Annual income (INR)'), '3000000');
    await userEvent.selectOptions(screen.getByLabelText('Occupation'), 'SALARIED');
    await userEvent.click(screen.getByRole('button', { name: 'Save and continue' }));
    expect(screen.getByText(/two-letter state code/)).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText('Country code'));
    await userEvent.type(screen.getByLabelText('Country code'), 'gb');
    expect(screen.getByLabelText('Country code')).toHaveValue('GB');
    expect(screen.queryByLabelText(/State code/)).not.toBeInTheDocument();
  });

  it('AC-06: saves the profile with an integer income and moves to documents', async () => {
    const { calls } = mockFetch({
      [CASE_URL]: makeCase(),
      [`PUT /api/v1/cases/${prospectSession.caseId}/profile`]: makeCase({ profile_complete: true }),
      [`GET /api/v1/cases/${prospectSession.caseId}`]: makeCase(),
    });
    renderApp(<ProfilePage />, { session: prospectSession });
    await userEvent.type(await screen.findByLabelText('Date of birth'), '1990-04-12');
    await userEvent.type(screen.getByLabelText('Annual income (INR)'), '3000000');
    await userEvent.selectOptions(screen.getByLabelText('Occupation'), 'SELF_EMPLOYED');
    await userEvent.type(screen.getByLabelText(/State code/), 'mh');
    await userEvent.click(screen.getByRole('button', { name: 'Save and continue' }));
    await waitFor(() => expect(calls.some((c) => c.key.startsWith('PUT'))).toBe(true));
    const put = calls.find((c) => c.key.startsWith('PUT'));
    expect(put?.body).toEqual({ date_of_birth: '1990-04-12', annual_income: 3000000, occupation_category: 'SELF_EMPLOYED', country_code: 'IN', state_code: 'MH' });
  });
});

describe('UploadPage', () => {
  it('AC-02: blocks submission and names the missing mandatory documents', async () => {
    mockFetch({ [CASE_URL]: makeCase() });
    renderApp(<UploadPage />, { session: prospectSession });
    const submit = await screen.findByRole('button', { name: 'Submit documents' });
    expect(submit).toBeDisabled();
    expect(screen.getByText(/Still missing: Address proof, Photograph/)).toBeInTheDocument();
  });

  it('AC-02: enables submission when every mandatory item is present', async () => {
    const c = makeCase();
    c.checklist_items = c.checklist_items.map((i) => ({ ...i, status: 'VERIFIED' as const }));
    mockFetch({ [CASE_URL]: { ...c, missing_items: [] } });
    renderApp(<UploadPage />, { session: prospectSession });
    expect(await screen.findByRole('button', { name: 'Submit documents' })).toBeEnabled();
  });

  it('AC-03: shows immediate classification feedback after uploading a known fixture', async () => {
    const { calls } = mockFetch({
      [CASE_URL]: makeCase(),
      [`POST /api/v1/cases/${prospectSession.caseId}/documents`]: { status: 201, body: { document_id: 'd2', checklist_item: 'ADDRESS_PROOF', version: 1, doc_class: 'UTILITY_BILL', status: 'VERIFIED', reason_code: null, confidence_bp: 9500, rule_version: 1 } },
    });
    renderApp(<UploadPage />, { session: prospectSession });
    const input = await screen.findByLabelText('Upload Address proof');
    await userEvent.upload(input, new File(['%PDF'], 'utility-bill_valid.pdf', { type: 'application/pdf' }));
    expect(await screen.findByText(/Classified as UTILITY_BILL: verified/)).toBeInTheDocument();
    expect(calls.some((c) => c.key.startsWith('POST'))).toBe(true);
  });

  it('AC-03: flags an unrecognised upload with its reason code', async () => {
    mockFetch({
      [CASE_URL]: makeCase(),
      [`POST /api/v1/cases/${prospectSession.caseId}/documents`]: { status: 201, body: { document_id: 'd3', checklist_item: 'PHOTOGRAPH', version: 1, doc_class: 'UNRECOGNISED', status: 'FLAGGED', reason_code: 'DOC_UNRECOGNISED', confidence_bp: 0, rule_version: 1 } },
    });
    renderApp(<UploadPage />, { session: prospectSession });
    await userEvent.upload(await screen.findByLabelText('Upload Photograph'), new File(['x'], 'unknown_scan.pdf', { type: 'application/pdf' }));
    expect(await screen.findByText(/flagged for review \(DOC_UNRECOGNISED\)/)).toBeInTheDocument();
  });

  it('AC-02: rejects a disallowed file type client-side without calling the API', async () => {
    const { calls } = mockFetch({ [CASE_URL]: makeCase() });
    renderApp(<UploadPage />, { session: prospectSession });
    const input = await screen.findByLabelText('Upload Address proof');
    await userEvent.upload(input, new File(['x'], 'bad_type.exe'), { applyAccept: false });
    expect(await screen.findByText('Only PDF, JPG or PNG files are accepted.')).toBeInTheDocument();
    expect(calls.filter((c) => c.key.startsWith('POST'))).toHaveLength(0);
  });

  it('AC-09: lets a prospect re-upload a rejected document after submission', async () => {
    const c = makeCase({
      state: 'DOCS_SUBMITTED',
      missing_items: [],
      action_required: [{ item_code: 'ADDRESS_PROOF', status: 'REJECTED', reason_code: 'DOC_EXPIRED' }],
    });
    c.checklist_items[1] = { ...c.checklist_items[1], status: 'REJECTED', reason_code: 'DOC_EXPIRED', doc_class: 'UTILITY_BILL', doc_version: 1, document_id: 'd9' };
    c.checklist_items[2] = { ...c.checklist_items[2], status: 'VERIFIED' };
    mockFetch({ [CASE_URL]: c });
    renderApp(<UploadPage />, { session: prospectSession });
    expect(await screen.findByText(/Action required: Address proof \(rejected\)/)).toBeInTheDocument();
    expect(screen.getByLabelText('Upload Address proof')).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Submit documents' })).not.toBeInTheDocument();
  });

  it('AC-02: locks uploads once the case is approved', async () => {
    mockFetch({ [CASE_URL]: makeCase({ state: 'APPROVED' }) });
    renderApp(<UploadPage />, { session: prospectSession });
    expect(await screen.findByText(/can no longer be changed/)).toBeInTheDocument();
    expect(screen.getByLabelText('Replace ID proof')).toBeDisabled();
  });
});

describe('StatusPage', () => {
  it('AC-09: shows the current state, reason codes and notifications for the owner', async () => {
    mockFetch({
      [CASE_URL]: makeCase({ state: 'MANUAL_REVIEW' }),
      [`GET /api/v1/cases/${prospectSession.caseId}/notifications`]: { case_id: 'c', notifications: [makeNotification('MANUAL_REVIEW', 'PEP_HIT'), makeNotification('INITIATED')] },
    });
    renderApp(<StatusPage />, { session: prospectSession });
    expect(await screen.findByText(/needs an additional review/)).toBeInTheDocument();
    expect((await screen.findAllByText(/PEP_HIT/)).length).toBeGreaterThan(0);
    expect(screen.getByRole('list', { name: 'Notifications' })).toBeInTheDocument();
  });

  it('AC-07: shows the masked account number when approved', async () => {
    mockFetch({
      [CASE_URL]: makeCase({ state: 'APPROVED', account_number_masked: 'SAV********3456' }),
      [`GET /api/v1/cases/${prospectSession.caseId}/notifications`]: { case_id: 'c', notifications: [] },
    });
    renderApp(<StatusPage />, { session: prospectSession });
    expect(await screen.findByText(/SAV\*+3456/)).toBeInTheDocument();
  });
});

describe('LoginPage', () => {
  it('NFR-04: requires both fields, then signs in and redirects by role', async () => {
    mockFetch({ 'POST /api/v1/auth/login': { body: { access_token: 'staff-jwt', token_type: 'bearer', role: 'kyc-analyst', expires_in: 1800, case_id: null } } });
    renderApp(<LoginPage />);
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByText('Enter your username.')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Username'), 'analyst1');
    await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('workbench screen')).toBeInTheDocument();
  });

  it('NFR-04: shows a generic error for wrong credentials', async () => {
    mockFetch({ 'POST /api/v1/auth/login': { status: 401, body: { error: { code: 'UNAUTHENTICATED', message: 'Invalid credentials', details: {} } } } });
    renderApp(<LoginPage />);
    await userEvent.type(screen.getByLabelText('Username'), 'analyst1');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid credentials');
  });
});

const evidence: Evidence = {
  case_id: 'aaaaaaaa-1111-2222-3333-444444444444',
  state: 'MANUAL_REVIEW',
  product: 'Savings',
  documents: [{ document_id: 'd1', checklist_item: 'ID_PROOF', version: 1, status: 'VERIFIED', doc_class: 'PAN', reason_code: null, confidence_bp: 9500, rule_version: 1, superseded: false, size_bytes: 1000, sha256: 'ab', uploaded_at: '2026-10-01T09:30:00Z' }],
  screening: { id: 's1', case_id: 'c', hits: [{ entry_id: 'e1', list_type: 'AML', reason_code: 'AML_HIT' }], requires_manual_review: true, watchlist_version: 2, screened_at: '2026-10-01T09:31:00Z' },
  risk_assessment: { assessment_id: 'r1', case_id: 'c', score: 35, band: 'MEDIUM', rule_version: 1, source: 'RULE_ENGINE', breakdown: [{ factor: 'age', value_label: '25-60', points: 0, weight: 20, contribution: 0 }], created_at: '2026-10-01T09:32:00Z' },
  decision: { decision_id: 'dec1', case_id: 'c', type: 'AUTO', outcome: 'MANUAL_REVIEW', reason_code: 'AML_HIT', rule_version: 1, actor: 'system', created_at: '2026-10-01T09:33:00Z' },
  override: null,
  review_reason_code: 'AML_HIT',
  account_number_masked: null,
};

describe('review workflow', () => {
  it('AC-08.7: disables the decision button until a reason code is selected and filters reasons by direction', async () => {
    mockFetch({ [`GET /api/v1/cases/${evidence.case_id}/evidence`]: evidence });
    renderApp(<ReviewPanel caseId={evidence.case_id} onDone={() => undefined} />, { session: officerSession });
    const approve = await screen.findByRole('button', { name: 'Approve case' });
    expect(approve).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText('Reason code'), 'FALSE_POSITIVE_CLEARED');
    expect(approve).toBeEnabled();
    await userEvent.click(screen.getByLabelText('Reject'));
    expect(screen.getByRole('button', { name: 'Reject case' })).toBeDisabled();
    expect(within(screen.getByLabelText('Reason code')).getByRole('option', { name: 'Risk too high' })).toBeInTheDocument();
  });

  it('AC-08: records an override after confirmation and reports the audited outcome', async () => {
    const onDone = vi.fn();
    const { calls } = mockFetch({
      [`GET /api/v1/cases/${evidence.case_id}/evidence`]: evidence,
      [`POST /api/v1/cases/${evidence.case_id}/override`]: { body: { case_id: evidence.case_id, state: 'APPROVED', account_number: 'SAV123456789012', override: { override_id: 'o1', case_id: evidence.case_id, actor: 'officer1', previous_state: 'MANUAL_REVIEW', decision: 'APPROVE', reason_code: 'FALSE_POSITIVE_CLEARED', comment: null, rule_version: 1, created_at: '2026-10-01T10:00:00Z' } } },
    });
    renderApp(<ReviewPanel caseId={evidence.case_id} onDone={onDone} />, { session: officerSession });
    await userEvent.selectOptions(await screen.findByLabelText('Reason code'), 'FALSE_POSITIVE_CLEARED');
    await userEvent.click(screen.getByRole('button', { name: 'Approve case' }));
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirm decision' }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(calls.find((c) => c.key.endsWith('/override'))?.body).toEqual({ decision: 'APPROVE', reason_code: 'FALSE_POSITIVE_CLEARED' });
    expect(onDone.mock.calls[0][0]).toMatch(/approved.*audit trail/);
    expect(onDone.mock.calls[0][0]).toContain('Account number: SAV123456789012');
  });

  it('AC-08: shows a server error and keeps the panel open when the override fails', async () => {
    const onDone = vi.fn();
    mockFetch({
      [`GET /api/v1/cases/${evidence.case_id}/evidence`]: evidence,
      [`POST /api/v1/cases/${evidence.case_id}/override`]: { status: 409, body: { error: { code: 'INVALID_STATE', message: 'Transition not allowed', details: {} } } },
    });
    renderApp(<ReviewPanel caseId={evidence.case_id} onDone={onDone} />, { session: officerSession });
    await userEvent.selectOptions(await screen.findByLabelText('Reason code'), 'FALSE_POSITIVE_CLEARED');
    await userEvent.click(screen.getByRole('button', { name: 'Approve case' }));
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirm decision' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Transition not allowed');
    expect(onDone).not.toHaveBeenCalled();
  });

  it('AC-08: lists the manual-review queue with reason codes and opens the evidence panel', async () => {
    mockFetch({
      'GET /api/v1/review-queue': { total: 1, items: [{ case_id: evidence.case_id, product: 'Savings', reason_code: 'AML_HIT', age_minutes: 125, entered_review_at: '2026-10-01T09:33:00Z' }] },
      [`GET /api/v1/cases/${evidence.case_id}/evidence`]: evidence,
    });
    renderApp(<ReviewQueuePage />, { session: officerSession });
    expect(await screen.findByText(/AML_HIT - Possible AML/)).toBeInTheDocument();
    expect(screen.getByText('2 h 5 min')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Review aaaaaaaa/ }));
    expect(await screen.findByRole('heading', { name: 'Review panel' })).toBeInTheDocument();
  });

  it('AC-08: shows an empty state for an empty queue', async () => {
    mockFetch({ 'GET /api/v1/review-queue': { total: 0, items: [] } });
    renderApp(<ReviewQueuePage />, { session: officerSession });
    expect(await screen.findByText('No cases are waiting for manual review.')).toBeInTheDocument();
  });
});

describe('workbench and admin pages', () => {
  it('AC-09: workbench filters the case list by state via query parameters', async () => {
    const { calls } = mockFetch({
      'GET /api/v1/cases': { items: [{ case_id: 'bbbbbbbb-1111-2222-3333-444444444444', product: 'Current', state: 'DOCS_SUBMITTED', age_minutes: 30, created_at: '2026-10-01T09:00:00Z' }], page: 1, page_size: 25, total: 1 },
    });
    renderApp(<WorkbenchPage />, { session: { token: 't', role: 'kyc-analyst', caseId: null } });
    expect(await screen.findByRole('link', { name: 'bbbbbbbb' })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('State'), 'DOCS_SUBMITTED');
    await waitFor(() => expect(calls.some((c) => c.url.includes('state=DOCS_SUBMITTED'))).toBe(true));
  });

  it('AC-10: dashboard refreshes all panels when the product filter changes', async () => {
    const empty = { items: [], stages: [], buckets: [], count: 0, oldest_age_minutes: 0, auto_approved: 0, decided: 0, rate_bp: 0, target_bp: 6000, met: false };
    const { calls } = mockFetch(Object.fromEntries(['tat', 'funnel', 'backlog', 'time-per-stage', 'rejection-reasons', 'auto-approval', 'dropped-leads'].map((p) => [`GET /api/v1/admin/reports/${p}`, { body: empty }])));
    renderApp(<DashboardPage />, { session: { token: 't', role: 'admin', caseId: null } });
    expect(await screen.findAllByRole('region')).toHaveLength(7);
    await userEvent.selectOptions(screen.getByLabelText('Product'), 'NRE');
    await waitFor(() => expect(calls.filter((c) => c.url.includes('product=NRE'))).toHaveLength(7));
  });

  it('AC-05: watchlist add validates the name and deactivates entries', async () => {
    const entry = { entry_id: 'e1', name: 'Test Person Two', aliases: [], list_type: 'AML', active: true, added_at: '2026-10-01T00:00:00Z', deactivated_at: null };
    const { calls } = mockFetch({
      'GET /api/v1/admin/watchlist': { watchlist_version: 1, items: [entry] },
      'POST /api/v1/admin/watchlist/e1/deactivate': { body: { ...entry, active: false } },
    });
    renderApp(<WatchlistPage />, { session: { token: 't', role: 'admin', caseId: null } });
    await userEvent.click(await screen.findByRole('button', { name: 'Add entry' }));
    expect(screen.getByText(/1 to 100 characters/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Deactivate Test Person Two' }));
    await waitFor(() => expect(calls.some((c) => c.key.endsWith('/deactivate'))).toBe(true));
  });
});
