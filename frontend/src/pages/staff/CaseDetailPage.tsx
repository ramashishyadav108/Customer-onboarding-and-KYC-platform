import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { DOC_REJECT_REASONS, ITEM_LABELS, ROUTES } from '@/config';
import { Banner, ConfirmDialog, ReasonSelect, StatusChip } from '@/components/ui';
import { CaseQueries } from '@/components/CaseQueries';
import { EvidenceView } from '@/components/EvidenceView';
import { useDocumentReview, useEvidence, useStaffCase } from '@/hooks/useStaff';
import { useAuth } from '@/state/AuthContext';
import { validateReasonSelected } from '@/lib/validation';
import type { DocumentView } from '@/types';

export function CaseDetailPage() {
  const { caseId = '' } = useParams();
  const { session } = useAuth();
  const ev = useEvidence(caseId);
  const c = useStaffCase(caseId);
  const reload = () => {
    ev.reload();
    c.reload();
  };
  const review = useDocumentReview(caseId, reload);
  const [target, setTarget] = useState<DocumentView | null>(null);
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const isAnalyst = session?.role === 'kyc-analyst';
  const canAdvance = (isAnalyst || session?.role === 'admin') && c.data?.state === 'DOCS_SUBMITTED';

  const confirmReject = async () => {
    const err = validateReasonSelected(reason);
    setReasonError(err);
    if (err || !target) return;
    const res = await review.reject(target.document_id, reason);
    if (res) {
      setNotice(`Document rejected (${reason}). The prospect has been notified.`);
      setTarget(null);
      setReason('');
    }
  };

  return (
    <section className="card" aria-labelledby="h">
      <p><Link to={ROUTES.workbench}>Back to workbench</Link></p>
      <h2 id="h">Case detail</h2>
      <p className="meta">Case {caseId}{c.data ? ` - ${c.data.product} - contact ${c.data.contact_masked}` : ''}</p>
      {(ev.error || c.error) && <Banner kind="e">{ev.error ?? c.error}</Banner>}
      {review.error && <Banner kind="e">{review.error}</Banner>}
      {notice && <Banner kind="ok">{notice}</Banner>}
      {canAdvance && (
        <div className="row">
          <button type="button" onClick={() => review.advance()} disabled={review.busy}>Run screening, classification and decision</button>
        </div>
      )}
      {ev.data && <EvidenceView ev={ev.data} />}
      {isAnalyst && ev.data && ev.data.state !== 'APPROVED' && ev.data.state !== 'REJECTED' && (
        <>
          <h3>Document review</h3>
          <p className="meta">Documents are verified automatically by the classifier; analysts can reject a document with a reason code.</p>
          <ul className="items">
            {ev.data.documents.filter((d) => !d.superseded).map((d) => (
              <li key={d.document_id}>
                <div className="row">
                  <span className="grow">{ITEM_LABELS[d.checklist_item] ?? d.checklist_item} ({d.doc_class})</span>
                  <StatusChip status={d.status} />
                  <button type="button" className="sec" disabled={d.status === 'REJECTED'} onClick={() => { setTarget(d); setReason(''); setReasonError(null); }}>
                    Reject {ITEM_LABELS[d.checklist_item] ?? d.checklist_item}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
      <CaseQueries caseId={caseId} mode={isAnalyst ? 'analyst' : 'readonly'} />
      {target && (
        <ConfirmDialog title="Reject document" confirmLabel="Confirm rejection" onConfirm={confirmReject} onCancel={() => setTarget(null)} busy={review.busy}>
          <p>The prospect will be notified with this reason.</p>
          <ReasonSelect options={DOC_REJECT_REASONS} value={reason} error={reasonError ?? undefined} onChange={(e) => setReason(e.target.value)} />
        </ConfirmDialog>
      )}
    </section>
  );
}
