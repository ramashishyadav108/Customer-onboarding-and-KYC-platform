import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/config';
import { useAuth } from '@/state/AuthContext';
import type { Role } from '@/types';
import { SkipLink } from './ui';

const NAV: Record<Role, { to: string; label: string }[]> = {
  prospect: [
    { to: ROUTES.profile, label: '1 Profile' },
    { to: ROUTES.documents, label: '2 Documents' },
    { to: ROUTES.status, label: '3 Status' },
  ],
  'kyc-analyst': [{ to: ROUTES.workbench, label: 'Case workbench' }],
  'compliance-officer': [{ to: ROUTES.reviewQueue, label: 'Review queue' }],
  admin: [
    { to: ROUTES.dashboard, label: 'Reports' },
    { to: ROUTES.ruleSets, label: 'Rule sets' },
    { to: ROUTES.watchlist, label: 'Watchlist' },
    { to: ROUTES.users, label: 'Users' },
    { to: ROUTES.checklists, label: 'Checklists' },
    { to: ROUTES.workbench, label: 'Cases' },
  ],
};

export function AppShell({ title, wide }: { title: string; wide?: boolean }) {
  const { session, signOut } = useAuth();
  const navigate = useNavigate();
  const links = session ? NAV[session.role] : [];
  return (
    <>
      <SkipLink />
      <header className="top">
        <h1>{title}</h1>
        {session && (
          <div className="who">
            <span>Signed in as {session.role}</span>
            <button
              type="button"
              className="sec"
              onClick={() => {
                signOut();
                navigate(session.role === 'prospect' ? ROUTES.register : ROUTES.login);
              }}
            >
              Sign out
            </button>
          </div>
        )}
      </header>
      {links.length > 0 && (
        <nav className="tabs" aria-label="Main">
          {links.map((l) => (
            <NavLink key={l.to} to={l.to}>
              {l.label}
            </NavLink>
          ))}
        </nav>
      )}
      <main id="main" tabIndex={-1} className={wide ? 'wide' : undefined}>
        <Outlet />
      </main>
    </>
  );
}
