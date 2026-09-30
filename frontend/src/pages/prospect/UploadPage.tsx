import { useNavigate } from 'react-router-dom';
import { ITEM_LABELS, ROUTES, UPLOAD_ALLOWED_STATES } from '@/config';
import { Banner, StatusChip, reasonLabel } from '@/components/ui';
import { useCase, useChecklistUpload } from '@/hooks/useProspect';
import { useAuth } from '@/state/AuthContext';
import type { CaseItemView } from '@/types';

function ItemRow({
  item,
  feedback,
  disabled,
  onFile,
}: {
  item: CaseItemView;
  feedback?: { result?: { doc_class: string; status: string; reason_code: string | null }; error?: string; uploading?: boolean };
  disabled: boolean;
  onFile: (file: File) => void;
}) {
  const label = ITEM_LABELS[item.item_code] ?? item.item_code;
  const inputId = `file-${item.item_code}`;
  const status = feedback?.uploading ? 'UPLOADED' : item.status;
  const needsAction = item.status === 'MISSING' || item.status === 'REJECTED';
  return (
    <li data-testid={`item-${item.item_code}`}>
      <div className="row">
        <strong className="grow">
          {label}
          {item.mandatory ? '' : ' (optional)'}
        </strong>
        <StatusChip status={status} />
      </div>
      <span className="meta">Accepted: {item.accepted_classes.join(', ')}</span>
      {item.doc_class && <span className="meta">Detected as {item.doc_class}, version {item.doc_version}</span>}
      {item.reason_code && <span className="err">{reasonLabel(item.reason_code)} ({item.reason_code})</span>}
      <div>
        <label htmlFor={inputId} className="field-label">
          {needsAction ? `Upload ${label}` : `Replace ${label}`}
        </label>
        <input id={inputId} type="file" accept=".pdf,.jpg,.jpeg,.png" disabled={disabled} onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
      </div>
      <div aria-live="polite">
        {feedback?.uploading && <span className="meta">Uploading...</span>}
        {feedback?.error && <span className="err">{feedback.error}</span>}
        {feedback?.result && (
          <span className={feedback.result.status === 'VERIFIED' ? 'banner ok' : 'banner w'} style={{ display: 'block' }}>
            Classified as {feedback.result.doc_class}: {feedback.result.status === 'VERIFIED' ? 'verified' : `flagged for review${feedback.result.reason_code ? ` (${feedback.result.reason_code})` : ''}`}
          </span>
        )}
      </div>
    </li>
  );
}

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
      {data.action_required.length > 0 && data.state !== 'INITIATED' && (
        <Banner kind="w">Action required: {data.action_required.map((a) => `${ITEM_LABELS[a.item_code] ?? a.item_code} (${a.status.toLowerCase()})`).join(', ')}. Re-upload to continue; your case does not restart.</Banner>
      )}
      {!canUpload && <Banner kind="i">Documents can no longer be changed while your application is {data.state.replace('_', ' ').toLowerCase()}.</Banner>}
      <ul className="items" aria-label="Document checklist">
        {data.checklist_items.map((item) => (
          <ItemRow key={item.item_code} item={item} feedback={up.feedback[item.item_code]} disabled={!canUpload} onFile={(f) => up.upload(item.item_code, f)} />
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
