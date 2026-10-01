import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ROUTES, homeFor } from '@/config';
import { Banner, FormField, SkipLink } from '@/components/ui';
import { useSignup } from '@/hooks/useProspect';
import { validateSignup, type FieldErrors } from '@/lib/validation';
import { useAuth } from '@/state/AuthContext';

// Public prospect sign-up (AC-14): creates a prospect account only; staff accounts come from an admin.
export function SignupPage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const { signup, busy, error, fieldErrors } = useSignup();
  const [form, setForm] = useState({ username: '', password: '', confirm: '' });
  const [errors, setErrors] = useState<FieldErrors>({});
  const shown = { ...fieldErrors, ...errors };

  if (session) return <Navigate to={homeFor(session.role, session.caseId)} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const v = validateSignup(form);
    setErrors(v);
    if (Object.keys(v).length > 0) return;
    const res = await signup(form.username.trim(), form.password);
    if (res) navigate(ROUTES.register);
  };

  return (
    <>
      <SkipLink />
      <header className="top">
        <h1>OnboardX - Open your account</h1>
      </header>
      <main id="main" tabIndex={-1}>
        <section className="card" aria-labelledby="h">
          <h2 id="h">Create your account</h2>
          <p className="meta">This creates a customer account so you can come back to your application. Bank staff accounts are created by an administrator.</p>
          {error && !fieldErrors.username && <Banner kind="e">{error}</Banner>}
          <form onSubmit={onSubmit} noValidate aria-label="Create account">
            <FormField label="Username" name="username" autoComplete="username" hint="3 to 50 characters: a-z, 0-9, dot, underscore or hyphen." value={form.username} error={shown.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            <FormField label="Password" name="password" type="password" autoComplete="new-password" hint="At least 10 characters." value={form.password} error={shown.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <FormField label="Confirm password" name="confirm" type="password" autoComplete="new-password" value={form.confirm} error={shown.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
            <div className="row" style={{ marginTop: 16 }}>
              <button type="submit" disabled={busy}>
                {busy ? 'Creating account...' : 'Create account'}
              </button>
            </div>
          </form>
          <p>
            Already have an account? <Link to={ROUTES.login}>Sign in</Link>
          </p>
        </section>
      </main>
    </>
  );
}
