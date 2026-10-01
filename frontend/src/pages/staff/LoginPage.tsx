import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ROUTES, homeFor } from '@/config';
import { Banner, FormField, SkipLink } from '@/components/ui';
import { useLogin } from '@/hooks/useProspect';
import { useAuth } from '@/state/AuthContext';

// Synthetic seeded staff accounts, shown in development builds only (never in production).
const DEMO_STAFF = [
  { username: 'analyst1', role: 'KYC analyst' },
  { username: 'officer1', role: 'Compliance officer' },
  { username: 'admin1', role: 'Admin' },
];

export function LoginPage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const { login, busy, error } = useLogin();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  if (session) return <Navigate to={homeFor(session.role, session.caseId)} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const v: Record<string, string> = {};
    if (!username.trim()) v.username = 'Enter your username.';
    if (!password) v.password = 'Enter your password.';
    setErrors(v);
    if (Object.keys(v).length > 0) return;
    const res = await login(username.trim(), password);
    if (res) navigate(homeFor(res.role, res.case_id));
  };

  return (
    <>
      <SkipLink />
      <header className="top">
        <h1>OnboardX</h1>
      </header>
      <main id="main" tabIndex={-1}>
        <section className="card" aria-labelledby="h">
          <h2 id="h">Sign in</h2>
          <p className="meta">Customers and bank staff sign in here. You are taken to the page for your role.</p>
          {error && <Banner kind="e">{error}</Banner>}
          <form onSubmit={onSubmit} noValidate>
            <FormField label="Username" name="username" autoComplete="username" value={username} error={errors.username} onChange={(e) => setUsername(e.target.value)} />
            <FormField label="Password" name="password" type="password" autoComplete="current-password" value={password} error={errors.password} onChange={(e) => setPassword(e.target.value)} />
            <div className="row" style={{ marginTop: 16 }}>
              <button type="submit" disabled={busy}>
                {busy ? 'Signing in...' : 'Sign in'}
              </button>
            </div>
          </form>
          <p>
            New customer? <Link to={ROUTES.signup}>Create an account</Link> or <Link to={ROUTES.register}>apply without an account</Link>.
          </p>
          {import.meta.env.DEV && (
            <aside aria-label="Demo accounts" className="meta">
              <p>
                <strong>Demo staff accounts (synthetic, development only)</strong>
              </p>
              <ul>
                {DEMO_STAFF.map((d) => (
                  <li key={d.username}>
                    {d.role}: <code>{d.username}</code> / <code>demo-{d.username}-pass</code>
                  </li>
                ))}
              </ul>
            </aside>
          )}
        </section>
      </main>
    </>
  );
}
