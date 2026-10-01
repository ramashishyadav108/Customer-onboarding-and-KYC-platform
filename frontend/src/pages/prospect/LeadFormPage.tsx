import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { PRODUCTS, ROUTES } from '@/config';
import { Banner, FormField, SelectField } from '@/components/ui';
import { useLeadRegistration } from '@/hooks/useProspect';
import { validateLead } from '@/lib/validation';
import { useAuth } from '@/state/AuthContext';

export function LeadFormPage() {
  const navigate = useNavigate();
  const { session } = useAuth();
  const { register, busy, error, fieldErrors } = useLeadRegistration();
  const [form, setForm] = useState({ name: '', contact: '', product: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const shown = { ...fieldErrors, ...errors };

  // A signed-in prospect already has an application: resume it instead of starting another.
  if (session?.role === 'prospect' && session.caseId) return <Navigate to={ROUTES.status} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const v = validateLead(form);
    setErrors(v);
    if (Object.keys(v).length > 0) return;
    const res = await register({ name: form.name.trim(), contact: form.contact.trim(), product: form.product as (typeof PRODUCTS)[number] });
    if (res) navigate(ROUTES.profile);
  };

  return (
    <section className="card" aria-labelledby="h">
      <h2 id="h">Register your interest</h2>
      <p className="meta">Tell us who you are and which account you want. You will add your profile and documents next.</p>
      {!session && (
        <p className="meta">
          Have an account? <Link to={ROUTES.login}>Sign in</Link> or <Link to={ROUTES.signup}>create an account</Link> to come back to your application later.
        </p>
      )}
      {error && <Banner kind="e">{error}</Banner>}
      <form onSubmit={onSubmit} noValidate>
        <FormField label="Full name" name="name" autoComplete="name" value={form.name} error={shown.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <FormField
          label="Contact (phone or email)"
          name="contact"
          autoComplete="email"
          hint="10-digit phone number or email address."
          value={form.contact}
          error={shown.contact}
          onChange={(e) => setForm({ ...form, contact: e.target.value })}
        />
        <SelectField
          label="Account type"
          name="product"
          placeholder="Choose a product"
          options={PRODUCTS.map((p) => ({ value: p, label: p }))}
          value={form.product}
          error={shown.product}
          onChange={(e) => setForm({ ...form, product: e.target.value })}
        />
        <div className="row" style={{ marginTop: 16 }}>
          <button type="submit" disabled={busy}>
            {busy ? 'Registering...' : 'Start application'}
          </button>
        </div>
      </form>
    </section>
  );
}
