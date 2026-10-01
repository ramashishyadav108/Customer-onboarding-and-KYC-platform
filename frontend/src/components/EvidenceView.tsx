import type { Evidence } from '@/types';
import { ITEM_LABELS } from '@/config';
import { formatDateTime } from '@/lib/format';
import { DataTable } from './data';
import { DocumentViewButton } from './DocumentViewButton';
import { StatusChip, reasonLabel } from './ui';

export function EvidenceView({ ev }: { ev: Evidence }) {
  return (
    <div>
      <p>
        State: <StatusChip status={ev.state} /> {ev.review_reason_code && <span>Review reason: <strong>{ev.review_reason_code}</strong> - {reasonLabel(ev.review_reason_code)}</span>}
      </p>
      <h3>Documents</h3>
      <DataTable
        caption="Current documents"
        rows={ev.documents.filter((d) => !d.superseded)}
        rowKey={(d) => d.document_id}
        empty="No documents uploaded."
        columns={[
          { header: 'Item', cell: (d) => ITEM_LABELS[d.checklist_item] ?? d.checklist_item },
          { header: 'Class', cell: (d) => d.doc_class },
          { header: 'Status', cell: (d) => <StatusChip status={d.status} /> },
          { header: 'Reason', cell: (d) => d.reason_code ?? '-' },
          { header: 'Version', cell: (d) => d.version },
          { header: 'Uploaded', cell: (d) => formatDateTime(d.uploaded_at) },
          { header: 'File', cell: (d) => <DocumentViewButton caseId={ev.case_id} documentId={d.document_id} label={`${ITEM_LABELS[d.checklist_item] ?? d.checklist_item} (version ${d.version})`} /> },
        ]}
      />
      {ev.documents.some((d) => d.superseded) && (
        <DataTable
          caption="Earlier versions (replaced by a newer upload)"
          rows={ev.documents.filter((d) => d.superseded)}
          rowKey={(d) => d.document_id}
          columns={[
            { header: 'Item', cell: (d) => ITEM_LABELS[d.checklist_item] ?? d.checklist_item },
            { header: 'Version', cell: (d) => d.version },
            { header: 'Uploaded', cell: (d) => formatDateTime(d.uploaded_at) },
            { header: 'File', cell: (d) => <DocumentViewButton caseId={ev.case_id} documentId={d.document_id} label={`${ITEM_LABELS[d.checklist_item] ?? d.checklist_item} (version ${d.version}, replaced)`} /> },
          ]}
        />
      )}
      <h3>Screening</h3>
      {ev.screening ? (
        ev.screening.hits.length === 0 ? (
          <p>No watchlist hits (watchlist v{ev.screening.watchlist_version}).</p>
        ) : (
          <ul>
            {ev.screening.hits.map((h) => (
              <li key={h.entry_id}>
                {h.list_type} hit - {h.reason_code}
              </li>
            ))}
          </ul>
        )
      ) : (
        <p className="meta">Not screened yet.</p>
      )}
      <h3>Risk assessment</h3>
      {ev.risk_assessment ? (
        <>
          <p>
            Score {ev.risk_assessment.score} - band <StatusChip status={ev.risk_assessment.band} /> (rule set v{ev.risk_assessment.rule_version}, {ev.risk_assessment.source === 'RULE_ENGINE' ? 'rule engine' : 'officer reclassification'})
          </p>
          <DataTable
            caption="Risk score breakdown"
            rows={ev.risk_assessment.breakdown}
            rowKey={(b) => b.factor}
            columns={[
              { header: 'Factor', cell: (b) => b.factor },
              { header: 'Value', cell: (b) => b.value_label },
              { header: 'Points', cell: (b) => b.points },
              { header: 'Weight', cell: (b) => b.weight },
              { header: 'Contribution', cell: (b) => b.contribution },
            ]}
          />
        </>
      ) : (
        <p className="meta">Not classified yet.</p>
      )}
      {ev.decision && (
        <p>
          Decision: {ev.decision.outcome} ({ev.decision.reason_code}) by {ev.decision.actor}
        </p>
      )}
      {ev.override && (
        <p>
          Override: {ev.override.decision} - {ev.override.reason_code} by {ev.override.actor} at {formatDateTime(ev.override.created_at)}
        </p>
      )}
    </div>
  );
}
