import { useState } from 'react';
import { Banner } from '@/components/ui';
import { DOC_CLASS_HINT, ITEM_LABELS } from '@/config';
import { useChecklists } from '@/hooks/useAdmin';
import { formatDateTime } from '@/lib/format';
import { validateChecklistDraft, type ChecklistDraftRow } from '@/lib/validation';
import type { ChecklistVersion } from '@/types';

const ALL_ITEMS = Object.keys(ITEM_LABELS);

function toRows(v: ChecklistVersion): ChecklistDraftRow[] {
  return ALL_ITEMS.map((code) => {
    const found = v.items.find((i) => i.item_code === code);
    return { item_code: code, included: Boolean(found), mandatory: found?.mandatory ?? false, classes: (found?.accepted_classes ?? []).join(', ') };
  });
}

function ProductEditor({ version, busy, onPublish }: { version: ChecklistVersion; busy: boolean; onPublish: (rows: ChecklistDraftRow[]) => Promise<boolean> }) {
  const [rows, setRows] = useState(() => toRows(version));
  const [error, setError] = useState<string | null>(null);
  const set = (code: string, patch: Partial<ChecklistDraftRow>) => setRows(rows.map((r) => (r.item_code === code ? { ...r, ...patch } : r)));
  const name = version.product;

  const publish = async () => {
    const problem = validateChecklistDraft(rows);
    setError(problem);
    if (problem) return;
    await onPublish(rows);
  };

  return (
    <section className="card" aria-labelledby={`cl-${name}`}>
      <h3 id={`cl-${name}`}>
        {name} checklist - version {version.version}
      </h3>
      <p className="meta">Published {formatDateTime(version.created_at)}. Publishing appends a new version; existing cases keep theirs.</p>
      {error && <Banner kind="e">{error}</Banner>}
      <ul className="items" aria-label={`${name} checklist items`}>
        {rows.map((r) => (
          <li key={r.item_code}>
            <div className="row">
              <label className="grow">
                <input type="checkbox" checked={r.included} onChange={(e) => set(r.item_code, { included: e.target.checked, mandatory: e.target.checked ? r.mandatory : false })} /> Include {ITEM_LABELS[r.item_code]} for {name}
              </label>
              <label>
                <input type="checkbox" checked={r.mandatory} disabled={!r.included} onChange={(e) => set(r.item_code, { mandatory: e.target.checked })} /> Mandatory {ITEM_LABELS[r.item_code]} for {name}
              </label>
            </div>
            <label className="field-label" htmlFor={`cls-${name}-${r.item_code}`}>
              Accepted classes for {ITEM_LABELS[r.item_code]} ({name})
            </label>
            <input id={`cls-${name}-${r.item_code}`} value={r.classes} disabled={!r.included} onChange={(e) => set(r.item_code, { classes: e.target.value.toUpperCase() })} />
          </li>
        ))}
      </ul>
      <p className="hint">Known classes: {DOC_CLASS_HINT}.</p>
      <div className="row">
        <button type="button" disabled={busy} onClick={publish}>
          Publish new {name} version
        </button>
      </div>
    </section>
  );
}

export function ChecklistsPage() {
  const cl = useChecklists();
  const [notice, setNotice] = useState<string | null>(null);

  const publish = (product: ChecklistVersion['product']) => async (rows: ChecklistDraftRow[]) => {
    setNotice(null);
    const items = rows
      .filter((r) => r.included)
      .map((r) => ({ item_code: r.item_code, mandatory: r.mandatory, accepted_classes: r.classes.split(',').map((c) => c.trim()).filter(Boolean) }));
    const r = await cl.publish(product, items);
    if (r) setNotice(`${r.product} checklist version ${r.version} published. New cases will use it.`);
    return Boolean(r);
  };

  return (
    <section aria-labelledby="h">
      <h2 id="h">Admin: product checklists</h2>
      {(cl.list.error || cl.error) && <Banner kind="e">{cl.list.error ?? cl.error}</Banner>}
      {notice && <Banner kind="ok">{notice}</Banner>}
      {cl.list.data?.items.map((v) => (
        <ProductEditor key={`${v.product}-${v.version}`} version={v} busy={cl.busy} onPublish={publish(v.product)} />
      ))}
    </section>
  );
}
