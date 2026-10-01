import { useDocumentFile } from '@/hooks/useDocumentFile';

export function DocumentViewButton({ caseId, documentId, label }: { caseId: string; documentId: string; label: string }) {
  const { open, busy, error } = useDocumentFile(caseId, documentId);
  return (
    <span>
      <button type="button" className="sec" style={{ whiteSpace: 'nowrap' }} disabled={busy} onClick={open} aria-label={`View ${label}`}>
        {busy ? 'Opening...' : 'View'}
      </button>
      {error && <span className="err" role="alert"> {error}</span>}
    </span>
  );
}
