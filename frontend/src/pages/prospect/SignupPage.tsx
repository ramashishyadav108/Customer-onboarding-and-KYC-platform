import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ROUTES, SIGNUP_ACCOUNT_TYPES, homeFor } from '@/config';
import { Banner, FormField, SelectField, SkipLink } from '@/components/ui';
import { useSignup, useSignupOptions } from '@/hooks/useProspect';
import { validateSignup, type FieldErrors } from '@/lib/validation';
import { useAuth } from '@/state/AuthContext';

function PendingNotice({ role }: { role: string }) {
  const label = SIGNUP_ACCOUNT_TYPES.find((t) => t.value === role)?.label.replace(/ \(.*\)$/, '') ?? role;
  return (
    <section className="card" aria-labelledby="h">
      <h2 id="h">Request received</h2>
      <Banner kind="ok">Your {label} account request was sent to the administrators.</Banner>
      <p>You cannot sign in until an administrator approves it. Staff accounts are never opened automatically.</p>
      <p>
        <Link to={ROUTES.login}>Back to sign in</Link>
      </p>
    </section>
  );
}

// Public sign-up (AC-14): customers are signed in at once; a staff role waits for admin approval.
export function SignupPage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const { signup, busy, error, fieldErrors } = useSignup();
  const { adminRequiresApproval } = useSignupOptions();
  const [form, setForm] = useState({ role: 'prospect', username: '', password: '', confirm: '' });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [pendingRole, setPendingRole] = useState<string | null>(null);
  const shown = { ...fieldErrors, ...errors };
  const isStaff = form.role !== 'prospect';
  const needsApproval = isStaff && (form.role !== 'admin' || adminRequiresApproval);

  if (session) return <Navigate to={homeFor(session.role, session.caseId)} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const v = validateSignup(form);
    setErrors(v);
    if (Object.keys(v).length > 0) return;
    const res = await signup(form.username.trim(), form.password, form.role);
    if (!res) return;
    if (res.status === 'PENDING_APPROVAL') setPendingRole(res.role);
    else navigate(homeFor(res.role, res.case_id));
  };

  return (
    <>
      <SkipLink />
      <header className="top">
        <h1>OnboardX - Open your account</h1>
      </header>
      <main id="main" tabIndex={-1}>
        {pendingRole ? (
          <PendingNotice role={pendingRole} />
        ) : (
          <section className="card" aria-labelledby="h">
            <h2 id="h">Create your account</h2>
            {error && !fieldErrors.username && <Banner kind="e">{error}</Banner>}
            <form onSubmit={onSubmit} noValidate aria-label="Create account">
              <SelectField label="I am a" name="role" options={SIGNUP_ACCOUNT_TYPES} value={form.role} error={shown.role} onChange={(e) => setForm({ ...form, role: e.target.value })} />
              {needsApproval ? (
                <p className="hint" role="note">
                  Bank staff accounts must be approved by an administrator before you can sign in.
                </p>
              ) : isStaff ? (
                <p className="hint" role="note">
                  Admin sign-up is open on this server, so this account is created and signed in immediately.
                </p>
              ) : (
                <p className="hint">Customers can start an application as soon as the account is created.</p>
              )}
              <FormField label="Username" name="username" autoComplete="username" hint="3 to 50 characters: a-z, 0-9, dot, underscore or hyphen." value={form.username} error={shown.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
              <FormField label="Password" name="password" type="password" autoComplete="new-password" hint="At least 10 characters." value={form.password} error={shown.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
              <FormField label="Confirm password" name="confirm" type="password" autoComplete="new-password" value={form.confirm} error={shown.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
              <div className="row" style={{ marginTop: 16 }}>
                <button type="submit" disabled={busy}>
                  {busy ? 'Creating account...' : needsApproval ? 'Request account' : 'Create account'}
                </button>
              </div>
            </form>
            <p>
              Already have an account? <Link to={ROUTES.login}>Sign in</Link>
            </p>
          </section>
        )}
      </main>
    </>
  );
}
