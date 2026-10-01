import { ITEM_LABELS } from '@/config';
import { StatusChip, reasonLabel } from '@/components/ui';
import { FLAGGED_NEXT_STEP, exampleNames, flaggedExplanation } from '@/lib/uploadHelp';
import type { UploadFeedback } from '@/hooks/useProspect';
import type { CaseItemView } from '@/types';

function Result({ item, result }: { item: CaseItemView; result: NonNullable<UploadFeedback['result']> }) {
  if (result.status === 'VERIFIED') {
    return (
      <span className="banner ok" style={{ display: 'block' }}>
        Classified as {result.doc_class}: verified
      </span>
    );
  }
  return (
    <span className="banner w" style={{ display: 'block' }}>
      Classified as {result.doc_class}: flagged for review{result.reason_code ? ` (${result.reason_code})` : ''}.{' '}
      {flaggedExplanation(result.reason_code, result.doc_class, item.accepted_classes)} {FLAGGED_NEXT_STEP}
    </span>
  );
}

export function UploadItemRow({
  item,
  feedback,
  disabled,
  onFile,
}: {
  item: CaseItemView;
  feedback?: UploadFeedback;
  disabled: boolean;
  onFile: (file: File) => void;
}) {
  const label = ITEM_LABELS[item.item_code] ?? item.item_code;
  const inputId = `file-${item.item_code}`;
  const status = feedback?.uploading ? 'UPLOADED' : item.status;
  const needsAction = item.status === 'MISSING' || item.status === 'REJECTED';
  const examples = exampleNames(item.item_code, item.accepted_classes);
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
      {examples.length > 0 && (
        <span className="meta" id={`${inputId}-example`}>
          Example file name{examples.length > 1 ? 's' : ''}: {examples.join(', ')}
        </span>
      )}
      {item.doc_class && <span className="meta">Detected as {item.doc_class}, version {item.doc_version}</span>}
      {item.reason_code && <span className="err">{reasonLabel(item.reason_code)} ({item.reason_code})</span>}
      <div>
        <label htmlFor={inputId} className="field-label">
          {needsAction ? `Upload ${label}` : `Replace ${label}`}
        </label>
        <input
          id={inputId}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          disabled={disabled}
          aria-describedby={examples.length > 0 ? `${inputId}-example ${inputId}-status` : `${inputId}-status`}
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
      </div>
      <div aria-live="polite" id={`${inputId}-status`}>
        {feedback?.uploading && <span className="meta">Uploading...</span>}
        {feedback?.error && <span className="err">{feedback.error}</span>}
        {feedback?.result && <Result item={item} result={feedback.result} />}
      </div>
    </li>
  );
}
