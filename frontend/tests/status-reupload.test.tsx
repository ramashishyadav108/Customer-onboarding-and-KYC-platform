import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StatusPage } from '@/pages/prospect/StatusPage';
import { setAccessToken } from '@/api/client';
import type { ActionRequired } from '@/types';
import { makeCase, mockFetch, prospectSession, renderApp } from './helpers';

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

const base = `/api/v1/cases/${prospectSession.caseId}`;
const flagged: ActionRequired[] = [{ item_code: 'ADDRESS_PROOF', status: 'FLAGGED', reason_code: 'DOC_CLASS_MISMATCH' }];
const file = (name: string) => new File(['%PDF-1.4 x'], name, { type: 'application/pdf' });

describe('StatusPage in-place re-upload (E2-S5 AC3, AC-09.3f)', () => {
  it('AC-09: lists each action-required item with a Re-upload control and uploads without leaving the page', async () => {
    let verified = false;
    const { calls } = mockFetch({
      [`GET ${base}`]: () => ({ body: makeCase({ state: 'MANUAL_REVIEW', action_required: verified ? [] : flagged }) }),
      [`GET ${base}/notifications`]: { notifications: [] },
      [`POST ${base}/documents`]: () => {
        verified = true;
        return { status: 201, body: { document_id: 'd9', checklist_item: 'ADDRESS_PROOF', version: 2, doc_class: 'UTILITY_BILL', status: 'VERIFIED', reason_code: null, confidence_bp: 9500, rule_version: 1 } };
      },
    });
    renderApp(<StatusPage />, { session: prospectSession });
    const row = await screen.findByTestId('action-ADDRESS_PROOF');
    expect(within(row).getByText(/DOC_CLASS_MISMATCH/)).toBeInTheDocument();
    await userEvent.upload(within(row).getByLabelText('Re-upload Address proof'), file('utility-bill_v2.pdf'), { applyAccept: false });
    expect(await screen.findByText(/Address proof: classified as UTILITY_BILL, verified/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId('action-ADDRESS_PROOF')).not.toBeInTheDocument());
    expect(calls.some((c) => c.key === `POST ${base}/documents`)).toBe(true);
    expect(screen.getByRole('heading', { name: 'Application status' })).toBeInTheDocument();
  });

  it('AC-02: shows the client-side file-type error for a re-upload instead of calling the API', async () => {
    const { calls } = mockFetch({
      [`GET ${base}`]: makeCase({ state: 'MANUAL_REVIEW', action_required: flagged }),
      [`GET ${base}/notifications`]: { notifications: [] },
    });
    renderApp(<StatusPage />, { session: prospectSession });
    const input = await screen.findByLabelText('Re-upload Address proof');
    await userEvent.upload(input, new File(['MZ'], 'bad.exe', { type: 'application/octet-stream' }), { applyAccept: false });
    expect(await screen.findByText(/Only PDF, JPG or PNG files are accepted/)).toBeInTheDocument();
    expect(calls.some((c) => c.key.startsWith('POST'))).toBe(false);
  });

  it('AC-09: disables re-upload once the case is locked', async () => {
    mockFetch({
      [`GET ${base}`]: makeCase({ state: 'REJECTED', action_required: flagged }),
      [`GET ${base}/notifications`]: { notifications: [] },
    });
    renderApp(<StatusPage />, { session: prospectSession });
    expect(await screen.findByLabelText('Re-upload Address proof')).toBeDisabled();
  });
});
