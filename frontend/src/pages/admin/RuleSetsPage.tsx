import { useState } from 'react';
import { Banner, ConfirmDialog, FormField } from '@/components/ui';
import { DataTable } from '@/components/data';
import { useRuleSets } from '@/hooks/useAdmin';
import { formatDateTime } from '@/lib/format';
import { validateRuleSetDraft, type FieldErrors } from '@/lib/validation';
import type { RuleSet } from '@/types';

const FACTORS = ['age', 'income_band', 'occupation_category', 'geography'];

function DraftEditor({ draft, onSave, busy }: { draft: RuleSet; onSave: (body: Pick<RuleSet, 'weights' | 'points' | 'geography_map' | 'geography_default' | 'thresholds'>) => void; busy: boolean }) {
  const [weights, setWeights] = useState<Record<string, string>>(Object.fromEntries(FACTORS.map((f) => [f, String(draft.weights[f] ?? 0)])));
  const [low, setLow] = useState(String(draft.thresholds.low_max));
  const [med, setMed] = useState(String(draft.thresholds.medium_max));
  const [errors, setErrors] = useState<FieldErrors>({});

  const save = () => {
    const v = validateRuleSetDraft(weights, low, med);
    setErrors(v);
    if (Object.keys(v).length > 0) return;
    onSave({
      weights: Object.fromEntries(FACTORS.map((f) => [f, Number(weights[f])])),
      points: draft.points,
      geography_map: draft.geography_map,
      geography_default: draft.geography_default,
      thresholds: { low_max: Number(low), medium_max: Number(med) },
    });
  };

  return (
    <div>
      <h3>Edit draft version {draft.version}</h3>
      <p className="meta">Integer values only. Published versions are immutable.</p>
      {errors.weights && <p className="err">{errors.weights}</p>}
      {errors.thresholds && <p className="err">{errors.thresholds}</p>}
      <div className="row">
        {FACTORS.map((f) => (
          <FormField key={f} label={`Weight: ${f}`} inputMode="numeric" value={weights[f]} error={errors[f]} onChange={(e) => setWeights({ ...weights, [f]: e.target.value })} />
        ))}
        <FormField label="LOW max score" inputMode="numeric" value={low} error={errors.low_max} onChange={(e) => setLow(e.target.value)} />
        <FormField label="MEDIUM max score" inputMode="numeric" value={med} error={errors.medium_max} onChange={(e) => setMed(e.target.value)} />
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <button type="button" className="sec" onClick={save} disabled={busy}>Save draft</button>
      </div>
    </div>
  );
}

export function RuleSetsPage() {
  const rs = useRuleSets();
  const [editing, setEditing] = useState<RuleSet | null>(null);
  const [confirm, setConfirm] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const hasDraft = rs.list.data?.items.some((i) => i.status === 'DRAFT') ?? false;

  const edit = async (version: number) => {
    const full = await rs.load(version);
    if (full) setEditing(full);
  };
  const publish = async () => {
    if (confirm === null) return;
    const r = await rs.publish(confirm);
    setConfirm(null);
    if (r) {
      setNotice(`Rule set version ${r.version} published. It is now immutable.`);
      setEditing(null);
    }
  };

  return (
    <section className="card" aria-labelledby="h">
      <h2 id="h">Admin: rule sets</h2>
      {(rs.list.error || rs.error) && <Banner kind="e">{rs.list.error ?? rs.error}</Banner>}
      {notice && <Banner kind="ok">{notice}</Banner>}
      <div className="row">
        <button type="button" onClick={async () => { const r = await rs.createDraft(); if (r) { setEditing(r); setNotice(null); } }} disabled={rs.busy || hasDraft}>
          Create draft from latest
        </button>
        {hasDraft && <span className="meta">A draft already exists.</span>}
      </div>
      {rs.list.data && (
        <DataTable
          caption="Rule set versions"
          rows={rs.list.data.items}
          rowKey={(i) => String(i.version)}
          columns={[
            { header: 'Version', cell: (i) => i.version },
            { header: 'Status', cell: (i) => i.status },
            { header: 'Author', cell: (i) => i.author },
            { header: 'Created', cell: (i) => formatDateTime(i.created_at) },
            { header: 'Published', cell: (i) => (i.published_at ? formatDateTime(i.published_at) : '-') },
            {
              header: 'Actions',
              cell: (i) =>
                i.status === 'DRAFT' ? (
                  <span className="row">
                    <button type="button" className="sec" onClick={() => edit(i.version)}>Edit v{i.version}</button>
                    <button type="button" onClick={() => setConfirm(i.version)}>Publish v{i.version}</button>
                  </span>
                ) : (
                  <span className="meta">Immutable</span>
                ),
            },
          ]}
        />
      )}
      {editing && editing.status === 'DRAFT' && <DraftEditor key={editing.version} draft={editing} busy={rs.busy} onSave={async (b) => { const r = await rs.saveDraft(editing.version, b); if (r) { setEditing(r); setNotice('Draft saved.'); } }} />}
      {confirm !== null && (
        <ConfirmDialog title={`Publish version ${confirm}`} confirmLabel="Publish" onConfirm={publish} onCancel={() => setConfirm(null)} busy={rs.busy}>
          <p>Publishing makes this version immutable. New classifications will use it.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
