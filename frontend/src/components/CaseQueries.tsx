import { useId, useState, type FormEvent } from 'react';
import { Banner, StatusChip } from '@/components/ui';
import { useCaseQueries } from '@/hooks/useQueries';
import { formatDateTime } from '@/lib/format';
import { validateQueryMessage } from '@/lib/validation';
import type { CaseQuery } from '@/types';

export type QueryMode = 'analyst' | 'prospect' | 'readonly';

function MessageForm({ label, button, busy, onSend }: { label: string; button: string; busy: boolean; onSend: (message: string) => Promise<unknown> }) {
  const id = useId();
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const problem = validateQueryMessage(text);
    setError(problem);
    if (problem) return;
    if (await onSend(text.trim())) setText('');
  };
  return (
    <form onSubmit={submit} noValidate>
      <label htmlFor={id} className="field-label">{label}</label>
      <textarea id={id} rows={3} maxLength={600} value={text} aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-err` : undefined} onChange={(e) => setText(e.target.value)} />
      {error && <p className="err" id={`${id}-err`}>{error}</p>}
      <div className="row">
        <button type="submit" className="sec" disabled={busy}>{button}</button>
      </div>
    </form>
  );
}

function QueryItem({ q, mode, busy, onClose, onRespond }: { q: CaseQuery; mode: QueryMode; busy: boolean; onClose: () => void; onRespond: (message: string) => Promise<unknown> }) {
  return (
    <li data-testid={`query-${q.query_id}`}>
      <div className="row">
        <strong className="grow">{q.message}</strong>
        <StatusChip status={q.status} />
      </div>
      <span className="meta">Raised {formatDateTime(q.created_at)}</span>
      {q.responses.map((r) => (
        <p key={r.response_id} className="meta">Reply {formatDateTime(r.created_at)}: {r.message}</p>
      ))}
      {mode === 'analyst' && q.status !== 'CLOSED' && (
        <button type="button" className="sec" disabled={busy} onClick={onClose}>Close query</button>
      )}
      {mode === 'prospect' && q.status !== 'CLOSED' && <MessageForm label="Reply to query" button="Send reply" busy={busy} onSend={onRespond} />}
    </li>
  );
}

// Analyst queries on a case (AC-13): analysts raise and close, the prospect replies, others read.
export function CaseQueries({ caseId, mode }: { caseId: string; mode: QueryMode }) {
  const queries = useCaseQueries(caseId);
  const items = queries.list.data ?? [];
  if (mode === 'prospect' && items.length === 0 && !queries.list.error) return null;
  return (
    <section aria-labelledby="queries-h">
      <h3 id="queries-h">{mode === 'prospect' ? 'Questions from our team' : 'Queries'}</h3>
      {(queries.list.error || queries.error) && <Banner kind="e">{queries.list.error ?? queries.error}</Banner>}
      {queries.list.data && items.length === 0 && <p className="meta" role="status">No queries on this case.</p>}
      {items.length > 0 && (
        <ul className="items" aria-label="Case queries">
          {items.map((q) => (
            <QueryItem key={q.query_id} q={q} mode={mode} busy={queries.busy} onClose={() => queries.close(q.query_id)} onRespond={(m) => queries.respond(q.query_id, m)} />
          ))}
        </ul>
      )}
      {mode === 'analyst' && <MessageForm label="New query to the prospect" button="Raise query" busy={queries.busy} onSend={queries.raise} />}
    </section>
  );
}
