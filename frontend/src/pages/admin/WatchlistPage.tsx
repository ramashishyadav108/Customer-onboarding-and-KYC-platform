import { useState, type FormEvent } from 'react';
import { Banner, FormField, SelectField } from '@/components/ui';
import { DataTable } from '@/components/data';
import { useWatchlist } from '@/hooks/useAdmin';

export function WatchlistPage() {
  const wl = useWatchlist();
  const [name, setName] = useState('');
  const [aliases, setAliases] = useState('');
  const [listType, setListType] = useState<'AML' | 'PEP'>('AML');
  const [nameError, setNameError] = useState<string | undefined>();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 100) {
      setNameError('Enter a name of 1 to 100 characters.');
      return;
    }
    setNameError(undefined);
    const list = aliases.split(',').map((a) => a.trim()).filter(Boolean);
    if (list.length > 10) {
      setNameError('At most 10 aliases are allowed.');
      return;
    }
    const r = await wl.add({ name: trimmed, aliases: list, list_type: listType });
    if (r) {
      setName('');
      setAliases('');
    }
  };

  return (
    <section className="card" aria-labelledby="h">
      <h2 id="h">Admin: watchlist</h2>
      <p className="meta">Entries cannot be edited or deleted; deactivate instead. {wl.list.data ? `Watchlist version ${wl.list.data.watchlist_version}.` : ''}</p>
      {(wl.list.error || wl.error) && <Banner kind="e">{wl.list.error ?? wl.error}</Banner>}
      <form onSubmit={onSubmit} noValidate aria-label="Add watchlist entry">
        <FormField label="Name" value={name} error={nameError} onChange={(e) => setName(e.target.value)} />
        <FormField label="Aliases (comma separated)" value={aliases} onChange={(e) => setAliases(e.target.value)} />
        <SelectField label="List type" value={listType} options={[{ value: 'AML', label: 'AML' }, { value: 'PEP', label: 'PEP' }]} onChange={(e) => setListType(e.target.value as 'AML' | 'PEP')} />
        <div className="row" style={{ marginTop: 12 }}>
          <button type="submit" disabled={wl.busy}>Add entry</button>
        </div>
      </form>
      {wl.list.data && (
        <DataTable
          caption="Watchlist entries"
          rows={wl.list.data.items}
          rowKey={(e) => e.entry_id}
          empty="The watchlist is empty."
          columns={[
            { header: 'Name', cell: (e) => e.name },
            { header: 'Aliases', cell: (e) => e.aliases.join(', ') || '-' },
            { header: 'Type', cell: (e) => e.list_type },
            { header: 'Status', cell: (e) => (e.active ? 'Active' : 'Deactivated') },
            { header: 'Action', cell: (e) => (e.active ? <button type="button" className="sec" onClick={() => wl.deactivate(e.entry_id)}>Deactivate {e.name}</button> : '-') },
          ]}
        />
      )}
    </section>
  );
}
