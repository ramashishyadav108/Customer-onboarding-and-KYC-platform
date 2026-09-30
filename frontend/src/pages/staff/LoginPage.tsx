import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ROLE_HOME } from '@/config';
import { Banner, FormField, SkipLink } from '@/components/ui';
import { useLogin } from '@/hooks/useProspect';
import { useAuth } from '@/state/AuthContext';

export function LoginPage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const { login, busy, error } = useLogin();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  if (session) return <Navigate to={ROLE_HOME[session.role]} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const v: Record<string, string> = {};
    if (!username.trim()) v.username = 'Enter your username.';
    if (!password) v.password = 'Enter your password.';
    setErrors(v);
    if (Object.keys(v).length > 0) return;
    const role = await login(username.trim(), password);
    if (role) navigate(ROLE_HOME[role]);
  };

  return (
    <>
      <SkipLink />
      <header className="top">
        <h1>OnboardX Staff Console</h1>
      </header>
      <main id="main" tabIndex={-1}>
        <section className="card" aria-labelledby="h">
          <h2 id="h">Staff sign in</h2>
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
        </section>
      </main>
    </>
  );
}
