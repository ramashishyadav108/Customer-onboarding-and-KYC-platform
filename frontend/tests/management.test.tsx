import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UsersPage } from '@/pages/admin/UsersPage';
import { ChecklistsPage } from '@/pages/admin/ChecklistsPage';
import { CaseQueries } from '@/components/CaseQueries';
import { StatusPage } from '@/pages/prospect/StatusPage';
import { setAccessToken } from '@/api/client';
import { tokenSubject } from '@/lib/token';
import { validateChecklistDraft, validateNewUser, validateQueryMessage } from '@/lib/validation';
import type { CaseQuery, ChecklistVersion, ManagedUser } from '@/types';
import type { Session } from '@/state/AuthContext';
import { makeCase, mockFetch, prospectSession, renderApp } from './helpers';

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

const jwt = (sub: string) => `h.${Buffer.from(JSON.stringify({ sub })).toString('base64url')}.s`;
const adminSession: Session = { token: jwt('admin1'), role: 'admin', caseId: null };
const CASE_ID = prospectSession.caseId as string;

const user = (over: Partial<ManagedUser>): ManagedUser => ({ user_id: 'u1', username: 'analyst1', role: 'kyc-analyst', active: true, status: 'ACTIVE', created_at: '2026-10-01T00:00:00Z', ...over });
const USERS = [user({ user_id: 'u0', username: 'admin1', role: 'admin' }), user({}), user({ user_id: 'u2', username: 'old.officer', role: 'compliance-officer', active: false, status: 'DEACTIVATED' })];

describe('token helper', () => {
  it('NFR-04: reads the subject claim and tolerates malformed tokens', () => {
    expect(tokenSubject(jwt('admin1'))).toBe('admin1');
    expect(tokenSubject('not-a-token')).toBeNull();
    expect(tokenSubject(null)).toBeNull();
    expect(tokenSubject(`h.${Buffer.from(JSON.stringify({ sub: 5 })).toString('base64url')}.s`)).toBeNull();
  });
});

describe('management validators', () => {
  it('AC-11: validates username, password and role', () => {
    expect(validateNewUser({ username: 'Bad Name', password: 'short', role: '' })).toEqual({
      username: expect.any(String),
      password: expect.any(String),
      role: expect.any(String),
    });
    expect(validateNewUser({ username: 'ok.user', password: 'long-enough-1', role: 'admin' })).toEqual({});
  });
  it('AC-13: validates query messages', () => {
    expect(validateQueryMessage('  ')).toMatch(/Enter/);
    expect(validateQueryMessage('x'.repeat(501))).toMatch(/500/);
    expect(validateQueryMessage('fine')).toBeNull();
  });
  it('AC-12: requires the three baseline items mandatory and classes for included items', () => {
    const rows = ['ID_PROOF', 'ADDRESS_PROOF', 'PHOTOGRAPH'].map((c) => ({ item_code: c, included: true, mandatory: true, classes: 'PAN' }));
    expect(validateChecklistDraft(rows)).toBeNull();
    expect(validateChecklistDraft(rows.slice(1))).toMatch(/id proof/);
    expect(validateChecklistDraft([{ ...rows[0], mandatory: false }, ...rows.slice(1)])).toMatch(/mandatory/);
    expect(validateChecklistDraft([{ ...rows[0], classes: ' , ' }, ...rows.slice(1)])).toMatch(/at least one/);
  });
});

describe('UsersPage', () => {
  it('AC-11.9: lists users and hides role and action controls on the admin’s own row', async () => {
    mockFetch({ 'GET /api/v1/admin/users': { items: USERS } });
    renderApp(<UsersPage />, { session: adminSession });
    expect(await screen.findByRole('cell', { name: 'analyst1' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Role for admin1')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deactivate admin1' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Role for analyst1')).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Reactivate old.officer' })).toBeInTheDocument();
  });

  it('AC-11: shows field errors and sends nothing for an invalid new user', async () => {
    const { calls } = mockFetch({ 'GET /api/v1/admin/users': { items: USERS } });
    renderApp(<UsersPage />, { session: adminSession });
    await userEvent.click(await screen.findByRole('button', { name: 'Create user' }));
    expect(screen.getByLabelText('Username')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('Choose a role.')).toBeInTheDocument();
    expect(calls.some((c) => c.key.startsWith('POST'))).toBe(false);
  });

  it('AC-11: creates a staff user and confirms', async () => {
    const { calls } = mockFetch({
      'GET /api/v1/admin/users': { items: USERS },
      'POST /api/v1/admin/users': { status: 201, body: user({ user_id: 'u9', username: 'analyst.two' }) },
    });
    renderApp(<UsersPage />, { session: adminSession });
    await userEvent.type(await screen.findByLabelText('Username'), 'analyst.two');
    await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass-123');
    await userEvent.selectOptions(screen.getByLabelText('Role'), 'kyc-analyst');
    await userEvent.click(screen.getByRole('button', { name: 'Create user' }));
    expect(await screen.findByText('User analyst.two created.')).toBeInTheDocument();
    expect(calls.find((c) => c.key === 'POST /api/v1/admin/users')?.body).toEqual({ username: 'analyst.two', password: 'synthetic-pass-123', role: 'kyc-analyst' });
  });

  it('AC-11: surfaces a server error such as a duplicate username', async () => {
    mockFetch({
      'GET /api/v1/admin/users': { items: USERS },
      'POST /api/v1/admin/users': { status: 409, body: { error: { code: 'USERNAME_TAKEN', message: 'Username is already in use', details: {} } } },
    });
    renderApp(<UsersPage />, { session: adminSession });
    await userEvent.type(await screen.findByLabelText('Username'), 'analyst1');
    await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass-123');
    await userEvent.selectOptions(screen.getByLabelText('Role'), 'admin');
    await userEvent.click(screen.getByRole('button', { name: 'Create user' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('already in use');
  });

  it('AC-11: changes a role, deactivates and reactivates', async () => {
    const { calls } = mockFetch({
      'GET /api/v1/admin/users': { items: USERS },
      'PUT /api/v1/admin/users/u1/role': user({ role: 'admin' }),
      'POST /api/v1/admin/users/u1/deactivate': user({ active: false }),
      'POST /api/v1/admin/users/u2/reactivate': user({ user_id: 'u2', username: 'old.officer', role: 'compliance-officer' }),
    });
    renderApp(<UsersPage />, { session: adminSession });
    await userEvent.selectOptions(await screen.findByLabelText('Role for analyst1'), 'admin');
    expect(await screen.findByText('Role for analyst1 changed.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Deactivate analyst1' }));
    expect(await screen.findByText('analyst1 deactivated.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Reactivate old.officer' }));
    expect(await screen.findByText('old.officer reactivated.')).toBeInTheDocument();
    expect(calls.find((c) => c.key.endsWith('/u1/role'))?.body).toEqual({ role: 'admin' });
  });

  it('AC-14.9: pending staff requests show Approve and Reject and are approved or rejected', async () => {
    const pending = user({ user_id: 'p1', username: 'officer.two', role: 'compliance-officer', active: false, status: 'PENDING' });
    const { calls } = mockFetch({
      'GET /api/v1/admin/users': { items: [...USERS, pending] },
      'POST /api/v1/admin/users/p1/approve': { ...pending, active: true, status: 'ACTIVE' },
      'POST /api/v1/admin/users/p1/reject': { ...pending, status: 'DEACTIVATED' },
    });
    renderApp(<UsersPage />, { session: adminSession });
    expect(await screen.findByText('Pending approval')).toBeInTheDocument();
    expect(screen.queryByLabelText('Role for officer.two')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Approve officer.two' }));
    expect(await screen.findByText('officer.two approved as Compliance officer.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Reject officer.two' }));
    expect(await screen.findByText('Request from officer.two rejected.')).toBeInTheDocument();
    expect(calls.some((c) => c.key === 'POST /api/v1/admin/users/p1/approve')).toBe(true);
  });

  it('AC-11: prospect rows are listed without controls', async () => {
    mockFetch({ 'GET /api/v1/admin/users': { items: [user({ user_id: 'p', username: 'prospect1', role: 'prospect' })] } });
    renderApp(<UsersPage />, { session: adminSession });
    expect(await screen.findByRole('cell', { name: 'Prospect' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Deactivate/ })).not.toBeInTheDocument();
  });
});

const savings: ChecklistVersion = {
  product: 'Savings',
  version: 1,
  created_at: '2026-10-01T00:00:00Z',
  items: [
    { item_code: 'ID_PROOF', mandatory: true, accepted_classes: ['PAN', 'AADHAAR'] },
    { item_code: 'ADDRESS_PROOF', mandatory: true, accepted_classes: ['UTILITY_BILL'] },
    { item_code: 'PHOTOGRAPH', mandatory: true, accepted_classes: ['PHOTOGRAPH'] },
  ],
};

describe('ChecklistsPage', () => {
  it('AC-12.7: shows the latest version per product and validates before publishing', async () => {
    const { calls } = mockFetch({ 'GET /api/v1/admin/checklists': { items: [savings] } });
    renderApp(<ChecklistsPage />, { session: adminSession });
    expect(await screen.findByRole('heading', { name: 'Savings checklist - version 1' })).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText('Mandatory Photograph for Savings'));
    await userEvent.click(screen.getByRole('button', { name: 'Publish new Savings version' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/photograph must be included and mandatory/);
    expect(calls.some((c) => c.key.startsWith('POST'))).toBe(false);
  });

  it('AC-12: publishes a new version with the edited items', async () => {
    const { calls } = mockFetch({
      'GET /api/v1/admin/checklists': { items: [savings] },
      'POST /api/v1/admin/checklists/Savings': { status: 201, body: { ...savings, version: 2 } },
    });
    renderApp(<ChecklistsPage />, { session: adminSession });
    const classes = await screen.findByLabelText('Accepted classes for ID proof (Savings)');
    await userEvent.clear(classes);
    await userEvent.type(classes, 'pan, passport');
    await userEvent.click(screen.getByLabelText('Include Business proof for Savings'));
    await userEvent.type(screen.getByLabelText('Accepted classes for Business proof (Savings)'), 'gst_certificate');
    await userEvent.click(screen.getByRole('button', { name: 'Publish new Savings version' }));
    expect(await screen.findByText(/Savings checklist version 2 published/)).toBeInTheDocument();
    const body = calls.find((c) => c.key === 'POST /api/v1/admin/checklists/Savings')?.body as { items: { item_code: string; mandatory: boolean; accepted_classes: string[] }[] };
    expect(body.items.find((i) => i.item_code === 'ID_PROOF')?.accepted_classes).toEqual(['PAN', 'PASSPORT']);
    expect(body.items.find((i) => i.item_code === 'BUSINESS_PROOF')).toEqual({ item_code: 'BUSINESS_PROOF', mandatory: false, accepted_classes: ['GST_CERTIFICATE'] });
  });

  it('AC-12: unticking an item clears its mandatory flag and disables its classes', async () => {
    mockFetch({ 'GET /api/v1/admin/checklists': { items: [savings] } });
    renderApp(<ChecklistsPage />, { session: adminSession });
    await userEvent.click(await screen.findByLabelText('Include Photograph for Savings'));
    expect(screen.getByLabelText('Mandatory Photograph for Savings')).not.toBeChecked();
    expect(screen.getByLabelText('Accepted classes for Photograph (Savings)')).toBeDisabled();
  });
});

const query = (over: Partial<CaseQuery> = {}): CaseQuery => ({ query_id: 'q1', case_id: CASE_ID, raised_by: 'analyst1', message: 'Please resend the address proof', status: 'OPEN', created_at: '2026-10-01T09:00:00Z', responses: [], ...over });
const LIST = `GET /api/v1/cases/${CASE_ID}/queries`;

describe('CaseQueries', () => {
  it('AC-13.8: analyst raises a query and closes an open one', async () => {
    const { calls } = mockFetch({
      [LIST]: { items: [query()] },
      [`POST /api/v1/cases/${CASE_ID}/queries`]: { status: 201, body: query({ query_id: 'q2' }) },
      [`POST /api/v1/cases/${CASE_ID}/queries/q1/close`]: query({ status: 'CLOSED' }),
    });
    renderApp(<CaseQueries caseId={CASE_ID} mode="analyst" />, { session: { token: 't', role: 'kyc-analyst', caseId: null } });
    expect(await screen.findByText('Please resend the address proof')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Raise query' }));
    expect(screen.getByText('Enter a message.')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('New query to the prospect'), 'Is the PAN current?');
    await userEvent.click(screen.getByRole('button', { name: 'Raise query' }));
    await waitFor(() => expect(calls.find((c) => c.key === `POST /api/v1/cases/${CASE_ID}/queries`)?.body).toEqual({ message: 'Is the PAN current?' }));
    await userEvent.click(screen.getByRole('button', { name: 'Close query' }));
    await waitFor(() => expect(calls.some((c) => c.key.endsWith('/q1/close'))).toBe(true));
  });

  it('AC-13: shows replies and no actions for closed queries', async () => {
    mockFetch({ [LIST]: { items: [query({ status: 'CLOSED', responses: [{ response_id: 'r1', author: 'prospect', message: 'Sent it', created_at: '2026-10-01T10:00:00Z' }] })] } });
    renderApp(<CaseQueries caseId={CASE_ID} mode="analyst" />, { session: { token: 't', role: 'kyc-analyst', caseId: null } });
    expect(await screen.findByText(/Sent it/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Close query' })).not.toBeInTheDocument();
  });

  it('AC-13: prospect replies to an open query; the form is hidden once closed', async () => {
    const { calls } = mockFetch({
      [LIST]: { items: [query(), query({ query_id: 'q3', message: 'Old question', status: 'CLOSED' })] },
      [`POST /api/v1/cases/${CASE_ID}/queries/q1/responses`]: { status: 201, body: query({ status: 'ANSWERED' }) },
    });
    renderApp(<CaseQueries caseId={CASE_ID} mode="prospect" />, { session: prospectSession });
    const open = await screen.findByTestId('query-q1');
    expect(within(screen.getByTestId('query-q3')).queryByLabelText('Reply to query')).not.toBeInTheDocument();
    await userEvent.type(within(open).getByLabelText('Reply to query'), 'Uploaded again');
    await userEvent.click(within(open).getByRole('button', { name: 'Send reply' }));
    await waitFor(() => expect(calls.find((c) => c.key.endsWith('/q1/responses'))?.body).toEqual({ message: 'Uploaded again' }));
  });

  it('AC-13: read-only mode shows queries without controls; prospect with none renders nothing', async () => {
    mockFetch({ [LIST]: { items: [query()] } });
    const { unmount } = renderApp(<CaseQueries caseId={CASE_ID} mode="readonly" />, { session: adminSession });
    expect(await screen.findByText('Please resend the address proof')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Close query' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('New query to the prospect')).not.toBeInTheDocument();
    unmount();
    mockFetch({ [LIST]: { items: [] } });
    renderApp(<CaseQueries caseId={CASE_ID} mode="prospect" />, { session: prospectSession });
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Questions from our team' })).not.toBeInTheDocument());
  });

  it('AC-13: shows an empty note for analysts and surfaces load errors', async () => {
    mockFetch({ [LIST]: { items: [] } });
    const { unmount } = renderApp(<CaseQueries caseId={CASE_ID} mode="analyst" />, { session: { token: 't', role: 'kyc-analyst', caseId: null } });
    expect(await screen.findByText('No queries on this case.')).toBeInTheDocument();
    unmount();
    mockFetch({ [LIST]: { status: 403, body: { error: { code: 'FORBIDDEN', message: 'Role not permitted', details: {} } } } });
    renderApp(<CaseQueries caseId={CASE_ID} mode="prospect" />, { session: prospectSession });
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('AC-13: the prospect status page shows open queries from the analyst', async () => {
    const base = `/api/v1/cases/${CASE_ID}`;
    mockFetch({
      [`GET ${base}`]: makeCase(),
      [`GET ${base}/notifications`]: { notifications: [] },
      [LIST]: { items: [query()] },
    });
    renderApp(<StatusPage />, { session: prospectSession });
    expect(await screen.findByRole('heading', { name: 'Questions from our team' })).toBeInTheDocument();
    expect(screen.getByLabelText('Reply to query')).toBeInTheDocument();
  });
});
