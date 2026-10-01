import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EvidenceView } from '@/components/EvidenceView';
import { CaseDetailPage } from '@/pages/staff/CaseDetailPage';
import { ReviewPanel } from '@/pages/staff/ReviewPanel';
import { setAccessToken } from '@/api/client';
import type { Evidence } from '@/types';
import { makeCase, mockFetch, officerSession, renderApp } from './helpers';

const CASE = 'aaaaaaaa-1111-2222-3333-444444444444';
const doc = (over: Partial<Evidence['documents'][number]>): Evidence['documents'][number] => ({
  document_id: 'd1', checklist_item: 'ID_PROOF', version: 1, status: 'VERIFIED', doc_class: 'PAN', reason_code: null,
  confidence_bp: 9500, rule_version: 1, superseded: false, size_bytes: 1000, sha256: 'ab', uploaded_at: '2026-10-01T09:30:00Z', ...over,
});
const evidence: Evidence = {
  case_id: CASE, state: 'MANUAL_REVIEW', product: 'Savings',
  documents: [
    doc({}),
    doc({ document_id: 'd2', checklist_item: 'ADDRESS_PROOF', doc_class: 'UTILITY_BILL' }),
    doc({ document_id: 'd0', version: 0, superseded: true, status: 'REJECTED' }),
  ],
  screening: null, risk_assessment: null, decision: null, override: null, review_reason_code: null, account_number_masked: null,
};
const analyst = { token: 'tok-analyst', role: 'kyc-analyst' as const, caseId: null };

let tab: { location: { href: string }; close: ReturnType<typeof vi.fn> };

beforeEach(() => {
  tab = { location: { href: '' }, close: vi.fn() };
  vi.stubGlobal('open', vi.fn(() => tab));
  URL.createObjectURL = vi.fn(() => 'blob:fake-document');
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

describe('viewing uploaded documents (AC-16)', () => {
  it('AC-03.9: the staff documents table shows class, status and reason code per document', () => {
    const rejected = doc({ document_id: 'dx', checklist_item: 'PHOTOGRAPH', doc_class: 'UNRECOGNISED', status: 'FLAGGED', reason_code: 'DOC_UNRECOGNISED' });
    renderApp(<EvidenceView ev={{ ...evidence, documents: [doc({}), rejected] }} />, { session: analyst });
    const table = screen.getByRole('table', { name: 'Current documents' });
    expect(within(within(table).getByRole('row', { name: /ID proof/ })).getByText('PAN')).toBeInTheDocument();
    const flagged = within(table).getByRole('row', { name: /Photograph/ });
    expect(flagged).toHaveTextContent('UNRECOGNISED');
    expect(flagged).toHaveTextContent('Flagged');
    expect(flagged).toHaveTextContent('DOC_UNRECOGNISED');
  });


  it('AC-16.7: lists a View button for every current document and for earlier versions', () => {
    renderApp(<EvidenceView ev={evidence} />, { session: analyst });
    const current = screen.getByRole('table', { name: 'Current documents' });
    expect(within(current).getByRole('button', { name: 'View ID proof (version 1)' })).toBeInTheDocument();
    expect(within(current).getByRole('button', { name: 'View Address proof (version 1)' })).toBeInTheDocument();
    const earlier = screen.getByRole('table', { name: 'Earlier versions (replaced by a newer upload)' });
    expect(within(earlier).getByRole('button', { name: 'View ID proof (version 0, replaced)' })).toBeInTheDocument();
  });

  it('AC-16.7: hides the earlier-versions table when nothing was replaced', () => {
    renderApp(<EvidenceView ev={{ ...evidence, documents: [doc({})] }} />, { session: analyst });
    expect(screen.queryByRole('table', { name: /Earlier versions/ })).not.toBeInTheDocument();
  });

  it('AC-16.7: fetches the file with the bearer token and opens it in a new tab', async () => {
    const { calls } = mockFetch({ [`GET /api/v1/cases/${CASE}/documents/d1/file`]: { body: 'pdf-bytes' } });
    setAccessToken('tok-analyst');
    renderApp(<EvidenceView ev={evidence} />, { session: analyst });
    await userEvent.click(screen.getByRole('button', { name: 'View ID proof (version 1)' }));
    await waitFor(() => expect(tab.location.href).toBe('blob:fake-document'));
    expect(calls[0].headers.Authorization).toBe('Bearer tok-analyst');
    expect(window.open).toHaveBeenCalledWith('about:blank', '_blank');
  });

  it('AC-16.7: shows the server error and closes the blank tab when the file cannot be opened', async () => {
    mockFetch({ [`GET /api/v1/cases/${CASE}/documents/d1/file`]: { status: 404, body: { error: { code: 'NOT_FOUND', message: 'file not found', details: {} } } } });
    renderApp(<EvidenceView ev={evidence} />, { session: analyst });
    await userEvent.click(screen.getByRole('button', { name: 'View ID proof (version 1)' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('file not found');
    expect(tab.close).toHaveBeenCalled();
    expect(tab.location.href).toBe('');
  });

  it('AC-16.7: the analyst case page offers View on the customer documents', async () => {
    mockFetch({
      [`GET /api/v1/cases/${CASE}/evidence`]: evidence,
      [`GET /api/v1/cases/${CASE}`]: makeCase({ case_id: CASE, state: 'MANUAL_REVIEW' }),
      [`GET /api/v1/cases/${CASE}/queries`]: { items: [] },
    });
    renderApp(<CaseDetailPage />, { session: analyst, path: `/staff/cases/${CASE}`, route: '/staff/cases/:caseId' });
    expect(await screen.findByRole('button', { name: 'View Address proof (version 1)' })).toBeInTheDocument();
  });

  it('AC-16.7: the compliance officer review panel offers View on the customer documents', async () => {
    mockFetch({ [`GET /api/v1/cases/${CASE}/evidence`]: evidence });
    renderApp(<ReviewPanel caseId={CASE} onDone={() => undefined} />, { session: officerSession });
    expect(await screen.findByRole('button', { name: 'View ID proof (version 1)' })).toBeInTheDocument();
  });
});
