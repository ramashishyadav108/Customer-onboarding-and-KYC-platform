import { describe, expect, it } from 'vitest';
import { screen, render, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RequireRole } from '@/state/RequireRole';
import { AuthProvider, loadSession, useAuth } from '@/state/AuthContext';
import { getAccessToken } from '@/api/client';
import { officerSession, prospectSession, renderApp } from './helpers';

describe('route guards', () => {
  it('NFR-04: redirects anonymous users to login', () => {
    renderApp(<RequireRole roles={['admin']}><p>secret admin page</p></RequireRole>, { session: null, path: '/admin/dashboard' });
    expect(screen.getByText('login screen')).toBeInTheDocument();
  });
  it('NFR-04: redirects anonymous prospects to registration when loginPath is set', () => {
    renderApp(<RequireRole roles={['prospect']} loginPath="/portal/register"><p>portal</p></RequireRole>, { session: null });
    expect(screen.getByText('register screen')).toBeInTheDocument();
  });
  it('AC-08: sends a prospect away from the compliance queue to /forbidden', () => {
    renderApp(<RequireRole roles={['compliance-officer']}><p>queue</p></RequireRole>, { session: prospectSession });
    expect(screen.getByText('forbidden screen')).toBeInTheDocument();
    expect(screen.queryByText('queue')).not.toBeInTheDocument();
  });
  it('AC-08: lets the compliance officer into the queue', () => {
    renderApp(<RequireRole roles={['compliance-officer']}><p>queue</p></RequireRole>, { session: officerSession });
    expect(screen.getByText('queue')).toBeInTheDocument();
  });
  it('AC-10: blocks a kyc-analyst from the admin dashboard', () => {
    renderApp(<RequireRole roles={['admin']}><p>dash</p></RequireRole>, { session: { token: 't', role: 'kyc-analyst', caseId: null } });
    expect(screen.getByText('forbidden screen')).toBeInTheDocument();
  });
});

describe('auth state', () => {
  function Probe() {
    const { session, signIn, signOut } = useAuth();
    return (
      <div>
        <p>role:{session?.role ?? 'none'}</p>
        <button onClick={() => signIn({ token: 'abc', role: 'admin', caseId: null })}>in</button>
        <button onClick={signOut}>out</button>
      </div>
    );
  }
  it('NFR-04: stores the session in sessionStorage and the api client token on sign in, clears on sign out', () => {
    render(<MemoryRouter><AuthProvider initial={null}><Probe /></AuthProvider></MemoryRouter>);
    act(() => screen.getByText('in').click());
    expect(screen.getByText('role:admin')).toBeInTheDocument();
    expect(loadSession()?.token).toBe('abc');
    expect(getAccessToken()).toBe('abc');
    act(() => screen.getByText('out').click());
    expect(loadSession()).toBeNull();
    expect(getAccessToken()).toBeNull();
  });
  it('NFR-04: restores a session from sessionStorage and ignores corrupt data', () => {
    sessionStorage.setItem('onboardx.session', JSON.stringify({ token: 't1', role: 'kyc-analyst', caseId: null }));
    render(<MemoryRouter><AuthProvider><Probe /></AuthProvider></MemoryRouter>);
    expect(screen.getByText('role:kyc-analyst')).toBeInTheDocument();
    sessionStorage.setItem('onboardx.session', '{not json');
    expect(loadSession()).toBeNull();
  });
});
