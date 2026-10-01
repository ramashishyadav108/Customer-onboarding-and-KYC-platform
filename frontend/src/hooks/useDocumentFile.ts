import { useCallback, useState } from 'react';
import { describeError } from '@/api/client';
import { documentsApi } from '@/api/resources';

const REVOKE_AFTER_MS = 60_000;

// Opens an uploaded document in a new tab. The file needs the bearer token, so it is fetched and
// shown from a short-lived object URL instead of a plain link (AC-16).
export function useDocumentFile(caseId: string, documentId: string) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = useCallback(async () => {
    setBusy(true);
    setError(null);
    const tab = window.open('about:blank', '_blank');
    try {
      const url = URL.createObjectURL(await documentsApi.file(caseId, documentId));
      if (tab) tab.location.href = url;
      else window.location.assign(url);
      window.setTimeout(() => URL.revokeObjectURL(url), REVOKE_AFTER_MS);
    } catch (e) {
      tab?.close();
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }, [caseId, documentId]);

  return { open, busy, error };
}
