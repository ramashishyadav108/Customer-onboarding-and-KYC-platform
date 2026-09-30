import type { ReactNode } from 'react';
import type { Notification, CaseState } from '@/types';
import { formatDateTime, humanize } from '@/lib/format';
import { reasonLabel } from './ui';

export interface Column<T> {
  header: string;
  cell: (row: T) => ReactNode;
}

export function DataTable<T>({ caption, columns, rows, rowKey, empty }: { caption: string; columns: Column<T>[]; rows: T[]; rowKey: (row: T) => string; empty?: string }) {
  if (rows.length === 0) return <p className="meta" role="status">{empty ?? 'No data for the selected filters.'}</p>;
  return (
    <div className="table-wrap">
      <table className="data">
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.header} scope="col">
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)}>
              {columns.map((c) => (
                <td key={c.header}>{c.cell(r)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export interface Datum {
  label: string;
  value: number;
  display: string;
  cells?: Record<string, string>;
}

// Bar chart with a text summary and a full accessible table alternative (AC-10.10).
export function ChartWithTable({ title, summary, data, valueHeader, extra }: { title: string; summary: string; data: Datum[]; valueHeader: string; extra?: ReactNode }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <section className="card" aria-label={title}>
      <h2>{title}</h2>
      <p className="meta">{summary}</p>
      {data.length === 0 ? (
        <p className="meta" role="status">No data for the selected filters.</p>
      ) : (
        <>
          <div className="chart" role="img" aria-label={`${title} chart. ${summary}`}>
            {data.map((d) => (
              <div className="bar-row" key={d.label} aria-hidden="true">
                <span>{d.label}</span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${Math.floor((d.value * 100) / max)}%` }} />
                </div>
                <span>{d.display}</span>
              </div>
            ))}
          </div>
          <DataTable
            caption={`${title} (table)`}
            columns={[
              { header: 'Category', cell: (d: Datum) => d.label },
              { header: valueHeader, cell: (d: Datum) => d.display },
              ...Object.keys(data[0].cells ?? {}).map((k) => ({ header: k, cell: (d: Datum) => d.cells?.[k] ?? '' })),
            ]}
            rows={data}
            rowKey={(d) => d.label}
          />
        </>
      )}
      {extra}
    </section>
  );
}

export const TIMELINE_STEPS: CaseState[] = ['INITIATED', 'DOCS_SUBMITTED', 'SCREENED', 'CLASSIFIED'];

const STEP_TEXT: Record<string, string> = {
  INITIATED: 'Application started',
  DOCS_SUBMITTED: 'Documents submitted',
  SCREENED: 'Screening complete',
  CLASSIFIED: 'Risk assessment complete',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  MANUAL_REVIEW: 'Under manual review',
};

// Status timeline with reason codes and stubbed notifications (AC-09).
export function StatusTimeline({ state, notifications }: { state: CaseState; notifications: Notification[] }) {
  const isFinal = state === 'APPROVED' || state === 'REJECTED' || state === 'MANUAL_REVIEW';
  const steps: string[] = isFinal ? [...TIMELINE_STEPS, state] : TIMELINE_STEPS;
  const currentIdx = isFinal ? steps.length - 1 : steps.indexOf(state);
  const reasonFor = (ev: string) => notifications.find((n) => n.event === ev)?.details.reason_code;
  return (
    <div>
      <ol className="timeline" aria-label="Application progress">
        {steps.map((s, i) => {
          const cls = i < currentIdx ? 'done' : i === currentIdx ? 'current' : '';
          const reason = reasonFor(s);
          return (
            <li key={s} className={cls} aria-current={i === currentIdx ? 'step' : undefined}>
              {STEP_TEXT[s]}
              <span className="sr-only">{i < currentIdx ? ' (completed)' : i === currentIdx ? ' (current step)' : ' (upcoming)'}</span>
              {reason && <div className="meta">Reason: {reasonLabel(reason)} ({reason})</div>}
            </li>
          );
        })}
      </ol>
      <h3>Notifications</h3>
      {notifications.length === 0 ? (
        <p className="meta" role="status">No notifications yet.</p>
      ) : (
        <ul className="items" aria-label="Notifications">
          {notifications.map((n) => (
            <li key={n.notification_id}>
              <span>
                <strong>{humanize(n.event)}</strong> - {n.text}
              </span>
              {(n.details.item_code || n.details.reason_code) && (
                <span className="meta">
                  {n.details.item_code && `Item: ${n.details.item_code}. `}
                  {n.details.reason_code && `Reason: ${n.details.reason_code}.`}
                </span>
              )}
              <span className="meta">{formatDateTime(n.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
