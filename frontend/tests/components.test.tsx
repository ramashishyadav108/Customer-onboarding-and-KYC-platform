import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StatusTimeline, ChartWithTable } from '@/components/data';
import { ReportPanels } from '@/components/ReportPanels';
import { ConfirmDialog, FormField, ReasonSelect } from '@/components/ui';
import { OVERRIDE_REASONS } from '@/config';
import type { Reports } from '@/types';
import { makeNotification } from './helpers';

const reports: Reports = {
  tat: { items: [{ product: 'Savings', count: 12, avg_seconds: 2700, min_seconds: 600, max_seconds: 7200 }, { product: 'NRE', count: 4, avg_seconds: 5400, min_seconds: 1800, max_seconds: 9000 }] },
  funnel: { stages: [{ stage: 'INITIATED', count: 50, conversion_bp: 10000 }, { stage: 'DOCS_SUBMITTED', count: 40, conversion_bp: 8000 }, { stage: 'MANUAL_REVIEW', count: 10, conversion_bp: 2500 }] },
  backlog: { count: 3, oldest_age_minutes: 1500, buckets: [{ label: 'under_60', min_minutes: 0, max_minutes: 59, count: 1 }, { label: '60_to_1440', min_minutes: 60, max_minutes: 1440, count: 1 }, { label: 'over_1440', min_minutes: 1441, max_minutes: null, count: 1 }] },
  timePerStage: { stages: [{ from_state: 'INITIATED', to_state: 'DOCS_SUBMITTED', count: 40, avg_seconds: 900 }] },
  rejections: { items: [{ reason_code: 'RISK_TOO_HIGH', count: 5 }, { reason_code: 'DOCS_INSUFFICIENT', count: 2 }] },
  autoApproval: { auto_approved: 30, decided: 50, rate_bp: 6000, target_bp: 6000, met: true },
};

describe('StatusTimeline', () => {
  it('AC-09: marks completed steps and the current step', () => {
    render(<StatusTimeline state="SCREENED" notifications={[]} />);
    const items = within(screen.getByRole('list', { name: 'Application progress' })).getAllByRole('listitem');
    expect(items).toHaveLength(4);
    expect(items[0]).toHaveTextContent('(completed)');
    expect(items[2]).toHaveAttribute('aria-current', 'step');
    expect(items[3]).toHaveTextContent('(upcoming)');
    expect(screen.getByText('No notifications yet.')).toBeInTheDocument();
  });
  it('AC-09: shows the manual review step with its reason code', () => {
    render(<StatusTimeline state="MANUAL_REVIEW" notifications={[makeNotification('MANUAL_REVIEW', 'AML_HIT')]} />);
    const items = screen.getAllByRole('listitem');
    expect(screen.getByText('Under manual review')).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Application progress' })).getByText(/AML_HIT/)).toBeInTheDocument();
    expect(items.length).toBeGreaterThan(5);
  });
  it('AC-09: lists stubbed notifications with item and reason codes for rejected documents', () => {
    const n = { ...makeNotification('DOC_REJECTED'), details: { item_code: 'ADDRESS_PROOF', reason_code: 'DOC_EXPIRED' } };
    render(<StatusTimeline state="INITIATED" notifications={[n]} />);
    const list = screen.getByRole('list', { name: 'Notifications' });
    expect(list).toHaveTextContent('Item: ADDRESS_PROOF');
    expect(list).toHaveTextContent('Reason: DOC_EXPIRED');
  });
  it('AC-09: shows an approved final step', () => {
    render(<StatusTimeline state="APPROVED" notifications={[]} />);
    expect(screen.getByText('Approved').closest('li')).toHaveAttribute('aria-current', 'step');
  });
});

describe('report panels', () => {
  it('AC-10: renders six panels each with an accessible table alternative', () => {
    render(<ReportPanels reports={reports} />);
    expect(screen.getAllByRole('table')).toHaveLength(6);
    expect(screen.getAllByRole('img')).toHaveLength(6);
    for (const t of ['Turnaround time by product', 'Approval funnel', 'Manual-review backlog', 'Average time per stage', 'Top rejection reasons', 'Auto-approval rate']) {
      expect(screen.getByRole('region', { name: t })).toBeInTheDocument();
    }
  });
  it('AC-10: TAT table shows count, average, min and max per product', () => {
    render(<ReportPanels reports={reports} />);
    const table = screen.getByRole('table', { name: 'Turnaround time by product (table)' });
    const row = within(table).getByRole('row', { name: /Savings/ });
    expect(row).toHaveTextContent('45 min 0 s');
    expect(row).toHaveTextContent('12');
    expect(row).toHaveTextContent('2 h 0 min');
  });
  it('AC-10: funnel table shows conversion in percent derived from basis points', () => {
    render(<ReportPanels reports={reports} />);
    const row = within(screen.getByRole('table', { name: 'Approval funnel (table)' })).getByRole('row', { name: /Docs submitted/ });
    expect(row).toHaveTextContent('80.00%');
  });
  it('AC-10: auto-approval summary states target met', () => {
    render(<ReportPanels reports={reports} />);
    expect(screen.getByText(/Target met/)).toBeInTheDocument();
  });
  it('AC-10: shows explicit empty states when there is no data', () => {
    const empty: Reports = { ...reports, tat: { items: [] }, rejections: { items: [] } };
    render(<ReportPanels reports={empty} />);
    expect(screen.getAllByText('No data for the selected filters.').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('No rejections.')).toBeInTheDocument();
  });
  it('AC-10: ChartWithTable scales bars relative to the maximum value', () => {
    render(<ChartWithTable title="Demo" summary="s" valueHeader="Count" data={[{ label: 'a', value: 10, display: '10' }, { label: 'b', value: 5, display: '5' }]} />);
    const fills = document.querySelectorAll<HTMLElement>('.bar-fill');
    expect(fills[0].style.width).toBe('100%');
    expect(fills[1].style.width).toBe('50%');
  });
});

describe('form building blocks', () => {
  it('AC-01: FormField links label, hint and error for assistive tech', () => {
    render(<FormField label="Full name" hint="As on ID" error="Enter your full name." />);
    const input = screen.getByLabelText('Full name');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input.getAttribute('aria-describedby')).toMatch(/hint.*err/);
  });
  it('AC-08: ReasonSelect lists only the reasons for the chosen direction', () => {
    render(<ReasonSelect options={OVERRIDE_REASONS.REJECT} value="" onChange={() => undefined} />);
    const select = screen.getByLabelText('Reason code');
    expect(within(select).getAllByRole('option')).toHaveLength(5);
    expect(within(select).queryByRole('option', { name: 'Risk accepted' })).not.toBeInTheDocument();
  });
  it('AC-08: ConfirmDialog cancels on Escape, traps Tab focus and confirms on click', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(<ConfirmDialog title="Record approval" confirmLabel="Confirm decision" onConfirm={onConfirm} onCancel={onCancel}><p>body</p></ConfirmDialog>);
    expect(screen.getByRole('dialog', { name: 'Record approval' })).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Confirm decision' })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await user.click(screen.getByRole('button', { name: 'Confirm decision' }));
    expect(onConfirm).toHaveBeenCalled();
    await user.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalled();
  });
});
