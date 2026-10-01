import type { Reports } from '@/types';
import { formatBp, formatDuration, humanize } from '@/lib/format';
import { ChartWithTable } from './data';

// Seven report panels, each a chart plus an accessible table and text summary (AC-10).
export function ReportPanels({ reports }: { reports: Reports }) {
  const { tat, funnel, backlog, timePerStage, rejections, autoApproval, droppedLeads } = reports;
  const top = rejections.items[0];
  return (
    <div className="grid-2">
      <ChartWithTable
        title="Turnaround time by product"
        summary={tat.items.length ? `Average time from start to decision for ${tat.items.length} product(s).` : 'No closed cases.'}
        valueHeader="Average"
        data={tat.items.map((t) => ({
          label: t.product,
          value: t.avg_seconds,
          display: formatDuration(t.avg_seconds),
          cells: { Cases: String(t.count), Min: formatDuration(t.min_seconds), Max: formatDuration(t.max_seconds) },
        }))}
      />
      <ChartWithTable
        title="Approval funnel"
        summary={funnel.stages.length ? `${funnel.stages[0].count} case(s) started; ${funnel.stages[funnel.stages.length - 1].count} in the last stage.` : 'No cases.'}
        valueHeader="Cases"
        data={funnel.stages.map((s) => ({ label: humanize(s.stage), value: s.count, display: String(s.count), cells: { 'Conversion': formatBp(s.conversion_bp) } }))}
      />
      <ChartWithTable
        title="Manual-review backlog"
        summary={`${backlog.count} case(s) waiting; oldest ${backlog.oldest_age_minutes} minutes.`}
        valueHeader="Cases"
        data={backlog.buckets.map((b) => ({ label: humanize(b.label), value: b.count, display: String(b.count) }))}
      />
      <ChartWithTable
        title="Average time per stage"
        summary={timePerStage.stages.length ? 'Mean time between consecutive stage transitions.' : 'No stage transitions yet.'}
        valueHeader="Average"
        data={timePerStage.stages.map((s) => ({ label: `${humanize(s.from_state)} to ${humanize(s.to_state)}`, value: s.avg_seconds, display: formatDuration(s.avg_seconds), cells: { Cases: String(s.count) } }))}
      />
      <ChartWithTable
        title="Top rejection reasons"
        summary={top ? `Most frequent: ${top.reason_code} (${top.count}).` : 'No rejections.'}
        valueHeader="Count"
        data={rejections.items.map((r) => ({ label: r.reason_code, value: r.count, display: String(r.count) }))}
      />
      <ChartWithTable
        title="Auto-approval rate"
        summary={`${formatBp(autoApproval.rate_bp)} of decided cases were auto-approved; target ${formatBp(autoApproval.target_bp)}. Target ${autoApproval.met ? 'met' : 'not met'}.`}
        valueHeader="Cases"
        data={[
          { label: 'Auto-approved', value: autoApproval.auto_approved, display: String(autoApproval.auto_approved), cells: { Rate: formatBp(autoApproval.rate_bp) } },
          { label: 'Decided', value: autoApproval.decided, display: String(autoApproval.decided), cells: { Rate: '' } },
        ]}
      />
      <ChartWithTable
        title="Dropped leads"
        summary={droppedLeads.total ? `${droppedLeads.total} open case(s) have had no activity for more than ${droppedLeads.older_than_days} days.` : `No open cases have been inactive for more than ${droppedLeads.older_than_days} days.`}
        valueHeader="Cases"
        data={droppedLeads.stages.map((s) => ({ label: humanize(s.stage), value: s.count, display: String(s.count) }))}
      />
    </div>
  );
}
