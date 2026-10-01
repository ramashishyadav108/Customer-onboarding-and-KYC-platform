import { useState } from 'react';
import { Banner } from '@/components/ui';
import { DataTable } from '@/components/data';
import { useReviewQueue } from '@/hooks/useStaff';
import { formatAge } from '@/lib/format';
import { reasonLabel } from '@/components/ui';
import { ReviewPanel } from './ReviewPanel';

export function ReviewQueuePage() {
  const queue = useReviewQueue();
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  return (
    <div className="grid-2">
      <section className="card" aria-labelledby="h">
        <h2 id="h">Manual review queue</h2>
        {queue.error && <Banner kind="e">{queue.error}</Banner>}
        {result && <Banner kind="ok">{result}</Banner>}
        {queue.loading && !queue.data && <p role="status">Loading queue...</p>}
        {queue.data && (
          <DataTable
            caption={`${queue.data.total} case(s) awaiting review, oldest first`}
            rows={queue.data.items}
            rowKey={(i) => i.case_id}
            empty="No cases are waiting for manual review."
            columns={[
              { header: 'Case', cell: (i) => i.case_id.slice(0, 8) },
              { header: 'Product', cell: (i) => i.product },
              { header: 'Reason', cell: (i) => `${i.reason_code} - ${reasonLabel(i.reason_code)}` },
              { header: 'Waiting', cell: (i) => formatAge(i.age_minutes) },
              { header: 'Action', cell: (i) => <button type="button" className="sec" onClick={() => { setSelected(i.case_id); setResult(null); }}>Review {i.case_id.slice(0, 8)}</button> },
            ]}
          />
        )}
      </section>
      {selected && (
        <ReviewPanel
          key={selected}
          caseId={selected}
          onDone={(msg) => {
            setResult(msg);
            setSelected(null);
            queue.reload();
          }}
        />
      )}
    </div>
  );
}
