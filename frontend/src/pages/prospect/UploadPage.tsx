import { useNavigate } from 'react-router-dom';
import { ITEM_LABELS, ROUTES, UPLOAD_ALLOWED_STATES } from '@/config';
import { Banner } from '@/components/ui';
import { UploadHelp } from '@/components/UploadHelp';
import { UploadItemRow } from '@/components/UploadItemRow';
import { useCase, useChecklistUpload } from '@/hooks/useProspect';
import { useAuth } from '@/state/AuthContext';

export function UploadPage() {
  const { session } = useAuth();
  const caseId = session?.caseId ?? null;
  const navigate = useNavigate();
  const { data, loading, error, reload } = useCase(caseId);
  const up = useChecklistUpload(caseId ?? '', reload);

  const onSubmit = async () => {
    const res = await up.submit();
    if (res) navigate(ROUTES.status);
  };

  if (loading && !data) return <p role="status">Loading checklist...</p>;
  if (error && !data) return <Banner kind="e">{error}</Banner>;
  if (!data) return null;

  const canUpload = UPLOAD_ALLOWED_STATES.includes(data.state);
  const mandatoryMissing = data.checklist_items.filter((i) => i.mandatory && (i.status === 'MISSING' || i.status === 'REJECTED')).map((i) => i.item_code);
  const missingLabels = mandatoryMissing.map((c) => ITEM_LABELS[c] ?? c);
  const canSubmit = data.state === 'INITIATED' && mandatoryMissing.length === 0;

  return (
    <section className="card" aria-labelledby="h">
      <h2 id="h">Upload your documents</h2>
      <p className="meta">Product: {data.product}. Accepted files: PDF, JPG or PNG up to 5 MB.</p>
      <UploadHelp />
      {data.action_required.length > 0 && data.state !== 'INITIATED' && (
        <Banner kind="w">Action required: {data.action_required.map((a) => `${ITEM_LABELS[a.item_code] ?? a.item_code} (${a.status.toLowerCase()})`).join(', ')}. Re-upload to continue; your case does not restart.</Banner>
      )}
      {!canUpload && <Banner kind="i">Documents can no longer be changed while your application is {data.state.replace('_', ' ').toLowerCase()}.</Banner>}
      <ul className="items" aria-label="Document checklist">
        {data.checklist_items.map((item) => (
          <UploadItemRow key={item.item_code} item={item} feedback={up.feedback[item.item_code]} disabled={!canUpload} onFile={(f) => up.upload(item.item_code, f)} />
        ))}
      </ul>
      {up.submitError && <Banner kind="e">{up.submitError}</Banner>}
      {data.state === 'INITIATED' && (
        <div style={{ marginTop: 16 }}>
          {mandatoryMissing.length > 0 && (
            <p className="hint" id="submit-hint">
              Submission is blocked. Still missing: {missingLabels.join(', ')}.
            </p>
          )}
          <button type="button" onClick={onSubmit} disabled={!canSubmit || up.submitting} aria-describedby={mandatoryMissing.length > 0 ? 'submit-hint' : undefined}>
            {up.submitting ? 'Submitting...' : 'Submit documents'}
          </button>
        </div>
      )}
    </section>
  );
}
