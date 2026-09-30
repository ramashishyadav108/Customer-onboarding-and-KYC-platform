import { useState } from 'react';
import { OVERRIDE_REASONS, RECLASSIFY_REASONS } from '@/config';
import { Banner, ConfirmDialog, ReasonSelect, SelectField } from '@/components/ui';
import { EvidenceView } from '@/components/EvidenceView';
import { useEvidence, useOverride } from '@/hooks/useStaff';
import type { OverrideDecision, RiskBand } from '@/types';

export function ReviewPanel({ caseId, onDone }: { caseId: string; onDone: (message: string) => void }) {
  const ev = useEvidence(caseId);
  const act = useOverride(caseId, () => ev.reload());
  const [decision, setDecision] = useState<OverrideDecision>('APPROVE');
  const [reason, setReason] = useState('');
  const [comment, setComment] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [band, setBand] = useState<RiskBand>('MEDIUM');
  const [bandReason, setBandReason] = useState('');

  const submit = async () => {
    const res = await act.override({ decision, reason_code: reason, comment: comment.trim() || undefined });
    setConfirming(false);
    if (res) onDone(`Case ${caseId.slice(0, 8)} ${res.state.toLowerCase()} with reason ${res.override.reason_code}. The override was recorded in the audit trail.`);
  };

  return (
    <section className="card" aria-labelledby="rp">
      <h2 id="rp">Review panel</h2>
      {ev.error && <Banner kind="e">{ev.error}</Banner>}
      {act.error && <Banner kind="e">{act.error}</Banner>}
      {ev.data && <EvidenceView ev={ev.data} />}
      <h3>Record decision</h3>
      <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
        <legend className="field-label">Decision</legend>
        <div className="row">
          {(['APPROVE', 'REJECT'] as const).map((d) => (
            <label key={d} className="row">
              <input type="radio" name="decision" value={d} checked={decision === d} onChange={() => { setDecision(d); setReason(''); }} />
              {d === 'APPROVE' ? 'Approve' : 'Reject'}
            </label>
          ))}
        </div>
      </fieldset>
      <ReasonSelect options={OVERRIDE_REASONS[decision]} value={reason} onChange={(e) => setReason(e.target.value)} />
      <div className="field">
        <label htmlFor="comment">Comment (optional)</label>
        <textarea id="comment" maxLength={500} rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <button type="button" disabled={!reason || act.busy} onClick={() => setConfirming(true)}>
          {decision === 'APPROVE' ? 'Approve case' : 'Reject case'}
        </button>
      </div>
      <h3>Reclassify risk band</h3>
      <div className="row">
        <SelectField label="New band" value={band} options={(['LOW', 'MEDIUM', 'HIGH'] as const).map((b) => ({ value: b, label: b }))} onChange={(e) => setBand(e.target.value as RiskBand)} />
        <ReasonSelect label="Reclassify reason" options={RECLASSIFY_REASONS} value={bandReason} onChange={(e) => setBandReason(e.target.value)} />
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <button type="button" className="sec" disabled={!bandReason || act.busy} onClick={() => act.reclassify(band, bandReason)}>
          Reclassify band
        </button>
      </div>
      {confirming && (
        <ConfirmDialog title={`Record ${decision === 'APPROVE' ? 'approval' : 'rejection'}`} confirmLabel="Confirm decision" onConfirm={submit} onCancel={() => setConfirming(false)} busy={act.busy}>
          <p>
            You are about to <strong>{decision.toLowerCase()}</strong> this case with reason <strong>{reason}</strong>. This is recorded in the audit trail and cannot be undone.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
