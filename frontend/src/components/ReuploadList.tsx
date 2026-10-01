import { ITEM_LABELS, UPLOAD_ALLOWED_STATES } from '@/config';
import { StatusChip, reasonLabel } from '@/components/ui';
import type { useChecklistUpload } from '@/hooks/useProspect';
import type { CaseDetail } from '@/types';

// Status-page action-required list: each entry has an in-place Re-upload control (E2-S5 AC3, AC-09.3f).
export function ReuploadList({ detail, up }: { detail: CaseDetail; up: ReturnType<typeof useChecklistUpload> }) {
  const allowed = UPLOAD_ALLOWED_STATES.includes(detail.state);
  const results = Object.entries(up.feedback);
  return (
    <div>
      <ul className="items" aria-label="Action required">
        {detail.action_required.map((a) => {
          const label = ITEM_LABELS[a.item_code] ?? a.item_code;
          const inputId = `reupload-${a.item_code}`;
          return (
            <li key={a.item_code} data-testid={`action-${a.item_code}`}>
              <div className="row">
                <strong className="grow">{label}</strong>
                <StatusChip status={a.status} />
              </div>
              {a.reason_code && <span className="err">{reasonLabel(a.reason_code)} ({a.reason_code})</span>}
              <label htmlFor={inputId} className="field-label">Re-upload {label}</label>
              <input id={inputId} type="file" accept=".pdf,.jpg,.jpeg,.png" disabled={!allowed} aria-describedby="reupload-status" onChange={(e) => e.target.files?.[0] && up.upload(a.item_code, e.target.files[0])} />
            </li>
          );
        })}
      </ul>
      <div aria-live="polite" id="reupload-status">
        {results.map(([code, f]) => (
          <p key={code} className={f.error ? 'err' : 'meta'}>
            {ITEM_LABELS[code] ?? code}: {f.uploading ? 'Uploading...' : f.error ?? (f.result ? `classified as ${f.result.doc_class}, ${f.result.status.toLowerCase()}.` : '')}
          </p>
        ))}
      </div>
    </div>
  );
}
