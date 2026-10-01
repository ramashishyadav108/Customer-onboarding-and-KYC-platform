import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginPage } from '@/pages/staff/LoginPage';
import { SignupPage } from '@/pages/prospect/SignupPage';
import { LeadFormPage } from '@/pages/prospect/LeadFormPage';
import { AuthProvider, type Session } from '@/state/AuthContext';
import { getAccessToken, setAccessToken } from '@/api/client';
import { homeFor } from '@/config';
import { validateSignup } from '@/lib/validation';
import { mockFetch, prospectSession } from './helpers';

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

function renderAt(path: string, session: Session | null = null) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initial={session}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/portal/register" element={<><LeadFormPage /><p>register screen</p></>} />
          <Route path="/portal/profile" element={<p>profile screen</p>} />
          <Route path="/portal/status" element={<p>status screen</p>} />
          <Route path="/staff/workbench" element={<p>workbench screen</p>} />
          <Route path="/staff/review" element={<p>review queue screen</p>} />
          <Route path="/admin/dashboard" element={<p>dashboard screen</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

const loginBody = (role: string, caseId: string | null) => ({ access_token: `${role}-jwt`, token_type: 'bearer', role, expires_in: 1800, case_id: caseId });
const signupBody = (role: string) => ({ status: 'ACTIVE', ...loginBody(role, null) });
const pendingBody = (role: string) => ({ status: 'PENDING_APPROVAL', access_token: null, token_type: 'bearer', role, expires_in: null, case_id: null });

async function signInAs(username: string) {
  await userEvent.type(screen.getByLabelText('Username'), username);
  await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass');
  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
}

describe('homeFor', () => {
  it('NFR-04: maps each role (and a prospect without a case) to its landing page', () => {
    expect(homeFor('prospect', null)).toBe('/portal/register');
    expect(homeFor('prospect', 'c1')).toBe('/portal/status');
    expect(homeFor('kyc-analyst', null)).toBe('/staff/workbench');
    expect(homeFor('compliance-officer', null)).toBe('/staff/review');
    expect(homeFor('admin', null)).toBe('/admin/dashboard');
  });
});

describe('LoginPage redirects by role', () => {
  it.each([
    ['kyc-analyst', null, 'workbench screen'],
    ['compliance-officer', null, 'review queue screen'],
    ['admin', null, 'dashboard screen'],
    ['prospect', 'case-1', 'status screen'],
  ])('AC-14.7: %s lands on the right page', async (role, caseId, screenText) => {
    mockFetch({ 'POST /api/v1/auth/login': { body: loginBody(role, caseId) } });
    renderAt('/login');
    await signInAs('someone');
    expect(await screen.findByText(screenText)).toBeInTheDocument();
  });

  it('AC-14.7: a prospect account without a case is sent to registration', async () => {
    mockFetch({ 'POST /api/v1/auth/login': { body: loginBody('prospect', null) } });
    renderAt('/login');
    await signInAs('meera.nair');
    expect(await screen.findByText('register screen')).toBeInTheDocument();
  });

  it('AC-14.7: a signed-in user visiting /login is redirected to their home', () => {
    renderAt('/login', { token: 't', role: 'compliance-officer', caseId: null });
    expect(screen.getByText('review queue screen')).toBeInTheDocument();
  });

  it('AC-14.7: links to sign-up and shows synthetic demo staff accounts in development builds', () => {
    renderAt('/login');
    expect(screen.getByRole('link', { name: 'Create an account' })).toHaveAttribute('href', '/signup');
    const demo = screen.getByRole('complementary', { name: 'Demo accounts' });
    expect(demo).toHaveTextContent('officer1');
    expect(demo).toHaveTextContent('demo-officer1-pass');
  });
});

describe('SignupPage', () => {
  it('AC-14.7: validates username, password and confirmation without calling the API', async () => {
    const { calls } = mockFetch({});
    renderAt('/signup');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByLabelText('Username')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Password')).toHaveAttribute('aria-invalid', 'true');
    await userEvent.type(screen.getByLabelText('Username'), 'meera.nair');
    await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass-123');
    await userEvent.type(screen.getByLabelText('Confirm password'), 'different-pass-123');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByText('The passwords do not match.')).toBeInTheDocument();
    expect(calls.some((c) => c.key.startsWith('POST'))).toBe(false);
  });

  it('AC-14.1: creates the account, signs in and continues to registration', async () => {
    const { calls } = mockFetch({ 'POST /api/v1/auth/signup': { status: 201, body: signupBody('prospect') } });
    renderAt('/signup');
    await userEvent.type(screen.getByLabelText('Username'), 'meera.nair');
    await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass-123');
    await userEvent.type(screen.getByLabelText('Confirm password'), 'synthetic-pass-123');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('register screen')).toBeInTheDocument();
    expect(calls.find((c) => c.key === 'POST /api/v1/auth/signup')?.body).toEqual({ username: 'meera.nair', password: 'synthetic-pass-123', role: 'prospect' });
    expect(getAccessToken()).toBe('prospect-jwt');
  });

  it('AC-14.10: asks for the account type and explains that staff accounts need approval', async () => {
    renderAt('/signup');
    const type = screen.getByLabelText('I am a');
    expect(within(type).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Customer (applying for an account)',
      'KYC analyst (bank staff)',
      'Compliance officer (bank staff)',
      'Admin (bank staff)',
    ]);
    expect(screen.getByRole('button', { name: 'Create account' })).toBeInTheDocument();
    await userEvent.selectOptions(type, 'compliance-officer');
    expect(screen.getByRole('note')).toHaveTextContent('must be approved by an administrator');
    expect(screen.getByRole('button', { name: 'Request account' })).toBeInTheDocument();
  });

  it('AC-14.11: admin sign-up is open on this server, so Admin skips approval but staff roles do not', async () => {
    mockFetch({ 'GET /api/v1/auth/signup-options': { admin_requires_approval: false, staff_requires_approval: true } });
    renderAt('/signup');
    const type = screen.getByLabelText('I am a');
    await userEvent.selectOptions(type, 'admin');
    expect(await screen.findByRole('button', { name: 'Create account' })).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('Admin sign-up is open on this server');
    await userEvent.selectOptions(type, 'kyc-analyst');
    expect(screen.getByRole('button', { name: 'Request account' })).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('must be approved by an administrator');
    await userEvent.selectOptions(type, 'compliance-officer');
    expect(screen.getByRole('button', { name: 'Request account' })).toBeInTheDocument();
  });

  it('AC-14.11: an open admin sign-up signs the new admin in and opens the dashboard', async () => {
    const { calls } = mockFetch({
      'GET /api/v1/auth/signup-options': { admin_requires_approval: false, staff_requires_approval: true },
      'POST /api/v1/auth/signup': { status: 201, body: signupBody('admin') },
    });
    renderAt('/signup');
    await userEvent.selectOptions(screen.getByLabelText('I am a'), 'admin');
    await userEvent.type(screen.getByLabelText('Username'), 'new.admin');
    await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass-123');
    await userEvent.type(screen.getByLabelText('Confirm password'), 'synthetic-pass-123');
    await userEvent.click(await screen.findByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('dashboard screen')).toBeInTheDocument();
    expect(calls.find((c) => c.key === 'POST /api/v1/auth/signup')?.body).toEqual({ username: 'new.admin', password: 'synthetic-pass-123', role: 'admin' });
    expect(getAccessToken()).toBe('admin-jwt');
  });

  it('AC-14.11: by default (and while the options load or fail) Admin needs approval too', async () => {
    mockFetch({ 'GET /api/v1/auth/signup-options': { admin_requires_approval: true, staff_requires_approval: true } });
    const { unmount } = renderAt('/signup');
    await userEvent.selectOptions(screen.getByLabelText('I am a'), 'admin');
    expect(screen.getByRole('button', { name: 'Request account' })).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('must be approved by an administrator');
    unmount();
    mockFetch({});
    renderAt('/signup');
    await userEvent.selectOptions(screen.getByLabelText('I am a'), 'admin');
    expect(screen.getByRole('button', { name: 'Request account' })).toBeInTheDocument();
  });

  it('AC-14.2: a staff request shows a confirmation and never signs in', async () => {
    const { calls } = mockFetch({ 'POST /api/v1/auth/signup': { status: 201, body: pendingBody('compliance-officer') } });
    renderAt('/signup');
    await userEvent.selectOptions(screen.getByLabelText('I am a'), 'compliance-officer');
    await userEvent.type(screen.getByLabelText('Username'), 'officer.two');
    await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass-123');
    await userEvent.type(screen.getByLabelText('Confirm password'), 'synthetic-pass-123');
    await userEvent.click(screen.getByRole('button', { name: 'Request account' }));
    expect(await screen.findByRole('heading', { name: 'Request received' })).toBeInTheDocument();
    expect(screen.getByText(/cannot sign in until an administrator approves/)).toBeInTheDocument();
    expect(calls.find((c) => c.key === 'POST /api/v1/auth/signup')?.body).toEqual({ username: 'officer.two', password: 'synthetic-pass-123', role: 'compliance-officer' });
    expect(getAccessToken()).toBeNull();
    expect(screen.queryByText('register screen')).not.toBeInTheDocument();
  });

  it('AC-14.8: the sign-in page shows the pending-approval message', async () => {
    mockFetch({ 'POST /api/v1/auth/login': { status: 403, body: { error: { code: 'ACCOUNT_PENDING', message: 'Your account is waiting for administrator approval', details: {} } } } });
    renderAt('/login');
    await signInAs('officer.two');
    expect(await screen.findByRole('alert')).toHaveTextContent('waiting for administrator approval');
  });

  it('AC-14.1: shows a taken username inline', async () => {
    mockFetch({ 'POST /api/v1/auth/signup': { status: 409, body: { error: { code: 'USERNAME_TAKEN', message: 'Username is already in use', details: {} } } } });
    renderAt('/signup');
    await userEvent.type(screen.getByLabelText('Username'), 'admin1');
    await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass-123');
    await userEvent.type(screen.getByLabelText('Confirm password'), 'synthetic-pass-123');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('That username is already taken.')).toBeInTheDocument();
  });

  it('AC-14.1: surfaces server-side field errors', async () => {
    mockFetch({ 'POST /api/v1/auth/signup': { status: 422, body: { error: { code: 'VALIDATION_ERROR', message: 'Request validation failed', details: { fields: [{ field: 'password', message: 'too weak' }] } } } } });
    renderAt('/signup');
    await userEvent.type(screen.getByLabelText('Username'), 'meera.nair');
    await userEvent.type(screen.getByLabelText('Password'), 'synthetic-pass-123');
    await userEvent.type(screen.getByLabelText('Confirm password'), 'synthetic-pass-123');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('too weak')).toBeInTheDocument();
  });

  it('AC-14.7: links back to sign-in; a signed-in user is redirected away', () => {
    const { unmount } = renderAt('/signup');
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
    unmount();
    renderAt('/signup', prospectSession);
    expect(screen.getByText('status screen')).toBeInTheDocument();
  });

  it('AC-14.1: validateSignup mirrors the server rules', () => {
    expect(validateSignup({ username: 'ok.user', password: 'long-enough-1', confirm: 'long-enough-1' })).toEqual({});
    expect(validateSignup({ username: 'Bad', password: 'short', confirm: 'x' })).toEqual({ username: expect.any(String), password: expect.any(String) });
  });
});

describe('lead registration with an account', () => {
  const lead = { case_id: 'c-1', state: 'INITIATED', product: 'NRE', access_token: 'case-jwt', token_type: 'bearer', expires_in: 1800 };
  const fillLead = async () => {
    await userEvent.type(screen.getByLabelText('Full name'), 'Meera Nair');
    await userEvent.type(screen.getByLabelText('Contact (phone or email)'), '9876543221');
    await userEvent.selectOptions(screen.getByLabelText('Account type'), 'NRE');
    await userEvent.click(screen.getByRole('button', { name: 'Start application' }));
  };

  it('AC-14.3: a signed-in prospect without a case sends its token so the case is linked', async () => {
    const { calls } = mockFetch({ 'POST /api/v1/leads': { status: 201, body: lead } });
    renderAt('/portal/register', { token: 'account-jwt', role: 'prospect', caseId: null });
    await fillLead();
    expect(await screen.findByText('profile screen')).toBeInTheDocument();
    expect(calls[0].headers.Authorization).toBe('Bearer account-jwt');
    expect(getAccessToken()).toBe('case-jwt');
  });

  it('AC-14.3: an anonymous visitor registers without any token and sees account links', async () => {
    const { calls } = mockFetch({ 'POST /api/v1/leads': { status: 201, body: lead } });
    renderAt('/portal/register');
    expect(screen.getByRole('link', { name: 'create an account' })).toHaveAttribute('href', '/signup');
    await fillLead();
    expect(await screen.findByText('profile screen')).toBeInTheDocument();
    expect(calls[0].headers.Authorization).toBeUndefined();
  });

  it('AC-14.3: a prospect who already has a case is sent to the status page instead of the form', () => {
    renderAt('/portal/register', prospectSession);
    expect(screen.getByText('status screen')).toBeInTheDocument();
    expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument();
  });

  it('AC-14.3: a second application from the same account shows the server message', async () => {
    mockFetch({ 'POST /api/v1/leads': { status: 409, body: { error: { code: 'CASE_EXISTS', message: 'This account already has an application', details: {} } } } });
    renderAt('/portal/register', { token: 'account-jwt', role: 'prospect', caseId: null });
    await fillLead();
    expect(await screen.findByRole('alert')).toHaveTextContent('already has an application');
  });
});
