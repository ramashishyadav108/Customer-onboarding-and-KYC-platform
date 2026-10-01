import { useState, type FormEvent } from 'react';
import { Banner, FormField, SelectField } from '@/components/ui';
import { DataTable } from '@/components/data';
import { STAFF_ROLE_OPTIONS } from '@/config';
import { useUsers } from '@/hooks/useAdmin';
import { formatDateTime } from '@/lib/format';
import { tokenSubject } from '@/lib/token';
import { validateNewUser, type FieldErrors } from '@/lib/validation';
import { useAuth } from '@/state/AuthContext';
import type { ManagedUser, StaffRole } from '@/types';

const ROLE_LABEL: Record<string, string> = { prospect: 'Prospect', ...Object.fromEntries(STAFF_ROLE_OPTIONS.map((o) => [o.value, o.label])) };

function RoleCell({ user, busy, onChange }: { user: ManagedUser; busy: boolean; onChange: (role: StaffRole) => void }) {
  if (user.role === 'prospect') return <>{ROLE_LABEL.prospect}</>;
  return (
    <select aria-label={`Role for ${user.username}`} value={user.role} disabled={busy} onChange={(e) => onChange(e.target.value as StaffRole)}>
      {STAFF_ROLE_OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function UsersPage() {
  const { session } = useAuth();
  const me = tokenSubject(session?.token);
  const users = useUsers();
  const [form, setForm] = useState({ username: '', password: '', role: '' });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [notice, setNotice] = useState<string | null>(null);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    const v = validateNewUser(form);
    setErrors(v);
    if (Object.keys(v).length > 0) return;
    const r = await users.create({ username: form.username, password: form.password, role: form.role as StaffRole });
    if (r) {
      setNotice(`User ${r.username} created.`);
      setForm({ username: '', password: '', role: '' });
    }
  };

  const act = async (fn: () => Promise<unknown>, message: string) => {
    setNotice(null);
    if (await fn()) setNotice(message);
  };

  return (
    <section className="card" aria-labelledby="h">
      <h2 id="h">Admin: users and roles</h2>
      <p className="meta">Staff accounts only. Deactivated users cannot sign in and their tokens stop working immediately.</p>
      {(users.list.error || users.error) && <Banner kind="e">{users.list.error ?? users.error}</Banner>}
      {notice && <Banner kind="ok">{notice}</Banner>}
      <form onSubmit={create} noValidate aria-label="Create user">
        <FormField label="Username" autoComplete="off" value={form.username} error={errors.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
        <FormField label="Password" type="password" autoComplete="new-password" value={form.password} error={errors.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <SelectField label="Role" value={form.role} placeholder="Choose a role" options={STAFF_ROLE_OPTIONS} error={errors.role} onChange={(e) => setForm({ ...form, role: e.target.value })} />
        <div className="row" style={{ marginTop: 12 }}>
          <button type="submit" disabled={users.busy}>Create user</button>
        </div>
      </form>
      {users.list.data && (
        <DataTable
          caption="Users"
          rows={users.list.data.items}
          rowKey={(u) => u.user_id}
          columns={[
            { header: 'Username', cell: (u) => u.username },
            { header: 'Role', cell: (u) => (u.username === me ? ROLE_LABEL[u.role] : <RoleCell user={u} busy={users.busy} onChange={(role) => act(() => users.changeRole(u.user_id, role), `Role for ${u.username} changed.`)} />) },
            { header: 'Status', cell: (u) => (u.active ? 'Active' : 'Deactivated') },
            { header: 'Created', cell: (u) => formatDateTime(u.created_at) },
            {
              header: 'Action',
              cell: (u) => {
                if (u.username === me || u.role === 'prospect') return '-';
                return u.active ? (
                  <button type="button" className="sec" disabled={users.busy} onClick={() => act(() => users.deactivate(u.user_id), `${u.username} deactivated.`)}>
                    Deactivate {u.username}
                  </button>
                ) : (
                  <button type="button" className="sec" disabled={users.busy} onClick={() => act(() => users.reactivate(u.user_id), `${u.username} reactivated.`)}>
                    Reactivate {u.username}
                  </button>
                );
              },
            },
          ]}
        />
      )}
    </section>
  );
}
