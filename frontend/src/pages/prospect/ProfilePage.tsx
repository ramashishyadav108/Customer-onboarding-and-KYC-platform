import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { OCCUPATIONS, ROUTES } from '@/config';
import { Banner, FormField, SelectField } from '@/components/ui';
import { useCase, useProfileSave } from '@/hooks/useProspect';
import { useAuth } from '@/state/AuthContext';
import { validateProfile, type FieldErrors } from '@/lib/validation';

export function ProfilePage() {
  const { session } = useAuth();
  const caseId = session?.caseId ?? null;
  const navigate = useNavigate();
  const { data, loading, error: loadError } = useCase(caseId);
  const { save, busy, error, code } = useProfileSave(caseId ?? '');
  const [form, setForm] = useState({ date_of_birth: '', annual_income: '', occupation_category: '', country_code: 'IN', state_code: '' });
  const [errors, setErrors] = useState<FieldErrors>({});

  useEffect(() => {
    const p = data?.profile;
    if (p) {
      setForm({
        date_of_birth: p.date_of_birth,
        annual_income: String(p.annual_income),
        occupation_category: p.occupation_category,
        country_code: p.country_code,
        state_code: p.state_code ?? '',
      });
    }
  }, [data]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const v = validateProfile(form);
    setErrors(v);
    if (Object.keys(v).length > 0) return;
    const res = await save({
      date_of_birth: form.date_of_birth,
      annual_income: Number(form.annual_income),
      occupation_category: form.occupation_category as never,
      country_code: form.country_code,
      ...(form.country_code === 'IN' ? { state_code: form.state_code } : {}),
    });
    if (res) navigate(ROUTES.documents);
  };

  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  const locked = code === 'PROFILE_LOCKED' || (data !== null && data.state !== 'INITIATED');

  return (
    <section className="card" aria-labelledby="h">
      <h2 id="h">Your profile</h2>
      {loading && <p role="status">Loading...</p>}
      {loadError && <Banner kind="e">{loadError}</Banner>}
      {error && <Banner kind="e">{error}</Banner>}
      {locked && <Banner kind="i">Your profile can no longer be changed because documents were submitted.</Banner>}
      <form onSubmit={onSubmit} noValidate>
        <FormField label="Date of birth" type="date" name="date_of_birth" value={form.date_of_birth} error={errors.date_of_birth} onChange={set('date_of_birth')} />
        <FormField
          label="Annual income (INR)"
          inputMode="numeric"
          name="annual_income"
          hint="Whole rupees, digits only."
          value={form.annual_income}
          error={errors.annual_income}
          onChange={set('annual_income')}
        />
        <SelectField
          label="Occupation"
          name="occupation_category"
          placeholder="Choose an occupation"
          options={OCCUPATIONS}
          value={form.occupation_category}
          error={errors.occupation_category}
          onChange={set('occupation_category')}
        />
        <FormField
          label="Country code"
          name="country_code"
          maxLength={2}
          hint="Two capital letters, for example IN."
          value={form.country_code}
          error={errors.country_code}
          onChange={(e) => setForm({ ...form, country_code: e.target.value.toUpperCase() })}
        />
        {form.country_code === 'IN' && (
          <FormField
            label="State code (required for India)"
            name="state_code"
            maxLength={2}
            hint="Two capital letters, for example MH."
            value={form.state_code}
            error={errors.state_code}
            onChange={(e) => setForm({ ...form, state_code: e.target.value.toUpperCase() })}
          />
        )}
        <div className="row" style={{ marginTop: 16 }}>
          <button type="submit" disabled={busy || locked}>
            {busy ? 'Saving...' : 'Save and continue'}
          </button>
        </div>
      </form>
    </section>
  );
}
