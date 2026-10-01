import { describe, expect, it } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UploadPage } from '@/pages/prospect/UploadPage';
import { exampleNames, flaggedExplanation, uploadErrorMessage, validateUploadFile } from '@/lib/uploadHelp';
import { makeCase, mockFetch, prospectSession, renderApp } from './helpers';

const CASE_URL = `GET /api/v1/cases/${prospectSession.caseId}`;
const DOC_URL = `POST /api/v1/cases/${prospectSession.caseId}/documents`;

async function uploadTo(label: string, file: File) {
  await userEvent.upload(await screen.findByLabelText(label), file, { applyAccept: false });
}
const pdf = (name: string) => new File(['%PDF-1.4 x'], name, { type: 'application/pdf' });

function errorFor(status: number, code: string, message: string) {
  return { status, body: { error: { code, message, details: {} } } };
}

describe('upload help block', () => {
  it('AC-02: shows the file-name prefix table, types, size limit and real-file note', async () => {
    mockFetch({ [CASE_URL]: makeCase() });
    renderApp(<UploadPage />, { session: prospectSession });
    const help = await screen.findByRole('region', { name: 'How to name your files (demo classifier)' });
    const table = within(help).getByRole('table', { name: 'File name prefixes' });
    for (const prefix of ['pan_', 'aadhaar_', 'passport_', 'utility-bill_', 'photograph_', 'gst-certificate_', 'visa_']) {
      expect(within(table).getByRole('rowheader', { name: prefix })).toBeInTheDocument();
    }
    expect(within(help).getByText(/PDF, JPG\/JPEG, PNG/)).toBeInTheDocument();
    expect(within(help).getByText(/Maximum size: 5 MB/)).toBeInTheDocument();
    expect(within(help).getByText(/real PDF, JPG or PNG files/)).toBeInTheDocument();
  });

  it('AC-02: shows an example file name per checklist item from its accepted classes', async () => {
    mockFetch({ [CASE_URL]: makeCase() });
    renderApp(<UploadPage />, { session: prospectSession });
    const address = await screen.findByTestId('item-ADDRESS_PROOF');
    expect(within(address).getByText(/utility-bill_march\.pdf/)).toBeInTheDocument();
    expect(within(screen.getByTestId('item-PHOTOGRAPH')).getByText(/photograph_me\.jpg/)).toBeInTheDocument();
    expect(within(screen.getByTestId('item-ID_PROOF')).getByText(/pan_card\.pdf/)).toBeInTheDocument();
  });

  it('AC-02: derives examples for business and overseas items and falls back by item code', () => {
    expect(exampleNames('BUSINESS_PROOF', ['GST_CERTIFICATE'])).toEqual(['gst-certificate_firm.pdf']);
    expect(exampleNames('OVERSEAS_ADDRESS_PROOF', ['VISA'])).toEqual(['visa_page.pdf']);
    expect(exampleNames('ID_PROOF', [])).toEqual(['pan_card.pdf']);
  });
});

describe('upload error mapping', () => {
  const cases: [string, number, string, string, RegExp][] = [
    ['AC-02: maps 415 to a type/content mismatch message', 415, 'UNSUPPORTED_MEDIA_TYPE', 'bad', /content must match its type/],
    ['AC-02: maps 413 to a larger-than-5 MB message', 413, 'FILE_TOO_LARGE', 'big', /larger than 5 MB/],
    ['AC-02: maps 422 to a validation message using the API text', 422, 'UNKNOWN_CHECKLIST_ITEM', 'Item is not on the checklist', /Item is not on the checklist/],
    ['AC-09: maps 409 CASE_LOCKED to a locked-application message', 409, 'CASE_LOCKED', 'locked', /decided \(approved or rejected\)/],
    ['AC-09: maps 409 INVALID_STATE to a state message', 409, 'INVALID_STATE', 'nope', /current state/],
    ['AC-02: maps 401 to a session-expired message', 401, 'UNAUTHENTICATED', 'x', /session has expired/],
    ['AC-02: maps 403 to a permission message', 403, 'FORBIDDEN', 'x', /do not have permission/],
  ];
  it.each(cases)('%s', async (_n, status, code, message, expected) => {
    mockFetch({ [CASE_URL]: makeCase(), [DOC_URL]: errorFor(status, code, message) });
    renderApp(<UploadPage />, { session: prospectSession });
    await uploadTo('Upload Photograph', pdf('photograph_me.pdf'));
    const row = screen.getByTestId('item-PHOTOGRAPH');
    expect(await within(row).findByText(expected)).toBeInTheDocument();
    expect(row.querySelector('[aria-live="polite"]')).toHaveTextContent(expected);
  });

  it('AC-02: maps a network failure to a connection message', () => {
    expect(uploadErrorMessage({ status: 0, code: 'NETWORK_ERROR', message: '' })).toMatch(/Cannot reach the server/);
  });

  it('AC-02: never shows a raw stack trace from the server', () => {
    const msg = uploadErrorMessage({ status: 500, code: 'X', message: 'Traceback (most recent call last):\n  File "a.py"' });
    expect(msg).not.toMatch(/Traceback/);
    expect(uploadErrorMessage({ status: 422, code: 'X', message: 'Traceback\nboom' })).not.toMatch(/boom/);
  });
});

describe('flagged explanations', () => {
  it('AC-03: explains DOC_UNRECOGNISED with the allowed prefixes and the manual-review consequence', async () => {
    mockFetch({
      [CASE_URL]: makeCase(),
      [DOC_URL]: { status: 201, body: { document_id: 'd3', checklist_item: 'PHOTOGRAPH', version: 1, doc_class: 'UNRECOGNISED', status: 'FLAGGED', reason_code: 'DOC_UNRECOGNISED', confidence_bp: 0, rule_version: 1 } },
    });
    renderApp(<UploadPage />, { session: prospectSession });
    await uploadTo('Upload Photograph', pdf('scan1.pdf'));
    const row = screen.getByTestId('item-PHOTOGRAPH');
    expect(await within(row).findByText(/Rename it to start with one of: pan_, aadhaar_/)).toBeInTheDocument();
    expect(within(row).getByText(/do not block submission, but the case goes to manual review/)).toBeInTheDocument();
  });

  it('AC-03: explains DOC_CLASS_MISMATCH with the detected and accepted classes', async () => {
    mockFetch({
      [CASE_URL]: makeCase(),
      [DOC_URL]: { status: 201, body: { document_id: 'd4', checklist_item: 'PHOTOGRAPH', version: 1, doc_class: 'UTILITY_BILL', status: 'FLAGGED', reason_code: 'DOC_CLASS_MISMATCH', confidence_bp: 0, rule_version: 1 } },
    });
    renderApp(<UploadPage />, { session: prospectSession });
    await uploadTo('Upload Photograph', pdf('utility-bill_x.pdf'));
    expect(await screen.findByText(/This looks like Utility bill but this item accepts Photograph\./)).toBeInTheDocument();
  });

  it('AC-03: builds explanations for each reason code', () => {
    expect(flaggedExplanation('DOC_CLASS_MISMATCH', 'PAN', ['PHOTOGRAPH'])).toBe('This looks like PAN card but this item accepts Photograph.');
    expect(flaggedExplanation('DOC_UNRECOGNISED', 'UNRECOGNISED', [])).toMatch(/visa_\.$/);
  });
});

describe('client-side pre-checks', () => {
  it('AC-02: rejects an oversize file before calling the API with the 413 wording', async () => {
    const { calls } = mockFetch({ [CASE_URL]: makeCase() });
    renderApp(<UploadPage />, { session: prospectSession });
    const big = new File(['x'], 'photograph_big.pdf', { type: 'application/pdf' });
    Object.defineProperty(big, 'size', { value: 5 * 1024 * 1024 + 1 });
    await uploadTo('Upload Photograph', big);
    expect(await screen.findByText(/File is larger than 5 MB\./)).toBeInTheDocument();
    expect(calls.filter((c) => c.key.startsWith('POST'))).toHaveLength(0);
  });

  it('AC-02: rejects an empty file and a wrong extension client-side', () => {
    expect(validateUploadFile({ name: 'a.pdf', size: 0 })).toMatch(/empty/);
    expect(validateUploadFile({ name: 'a.gif', size: 5 })).toBe('Only PDF, JPG or PNG files are accepted.');
    expect(validateUploadFile({ name: 'a.JPEG', size: 5 })).toBeNull();
  });
});
