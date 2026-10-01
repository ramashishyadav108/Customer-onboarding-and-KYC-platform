import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '@/config';
import { Banner, StatusChip } from '@/components/ui';
import { StatusTimeline } from '@/components/data';
import { ReuploadList } from '@/components/ReuploadList';
import { useCase, useChecklistUpload, useNotifications } from '@/hooks/useProspect';
import { useAuth } from '@/state/AuthContext';

export function StatusPage() {
  const { session } = useAuth();
  const caseId = session?.caseId ?? null;
  const c = useCase(caseId);
  const n = useNotifications(caseId);
  const { reload: reloadCase } = c;
  const { reload: reloadNotes } = n;
  const refresh = useCallback(() => { reloadCase(); reloadNotes(); }, [reloadCase, reloadNotes]);
  const up = useChecklistUpload(caseId ?? '', refresh);

  if (!caseId) {
    return (
      <Banner kind="i">
        You have no application yet. <Link to={ROUTES.register}>Start one</Link>.
      </Banner>
    );
  }
  if (c.loading && !c.data) return <p role="status">Loading status...</p>;
  if (c.error && !c.data) return <Banner kind="e">{c.error}</Banner>;
  if (!c.data) return null;
  const d = c.data;

  return (
    <section className="card" aria-labelledby="h">
      <h2 id="h">Application status</h2>
      <p>
        Case <code>{d.case_id}</code> - {d.product} - current status: <StatusChip status={d.state} />
      </p>
      {d.state === 'APPROVED' && d.account_number_masked && <Banner kind="ok">Your account is open: {d.account_number_masked}</Banner>}
      {d.state === 'REJECTED' && <Banner kind="e" live={false}>Your application was not approved.</Banner>}
      {d.state === 'MANUAL_REVIEW' && <Banner kind="i">Your application needs an additional review by our compliance team.</Banner>}
      {d.action_required.length > 0 && (
        <Banner kind="w">
          Action required on {d.action_required.length} document(s). <Link to={ROUTES.documents}>Go to documents</Link> to re-upload.
        </Banner>
      )}
      {(d.action_required.length > 0 || Object.keys(up.feedback).length > 0) && <ReuploadList detail={d} up={up} />}
      {n.error && <Banner kind="e">{n.error}</Banner>}
      <StatusTimeline state={d.state} notifications={n.data ?? []} />
      <div className="row" style={{ marginTop: 12 }}>
        <button type="button" className="sec" onClick={refresh}>
          Refresh status
        </button>
      </div>
    </section>
  );
}
